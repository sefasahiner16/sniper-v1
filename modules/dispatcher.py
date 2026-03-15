"""
Sniper V5 - The Dispatcher (Multi-Slot Async Orchestrator)
=============================================================
Core V3 architecture: Producer-Consumer pattern with multiple slots.

V5 Features:
- Handler integration (Capital Authority Layer)
- Regime-aware slot management
- Winner Protection (asymmetric exit rules)

Components:
- Watchtower: Async scanner that finds opportunities (Producer)
- SniperSlot: Async worker that manages ONE position (Consumer)
- Handler: Capital authority with final veto power
- Dispatcher: Orchestrates multiple slots
"""

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from config.settings import (
    SCAN_INTERVAL_SECONDS, MAX_CONCURRENT_SLOTS,
    PAPER_TRADING, INITIAL_BALANCE, BASE_TRADE_SIZE, WHALE_CAP,
    SECTOR_CAPS_ENABLED,
)
from modules.scanner import get_scanner
from modules.analyzer import get_analyzer, AnalysisResult
from modules.capital_manager import get_capital_manager
from modules.handler import get_handler, TradeDecision
# V5 regime_detector no longer used in dispatcher (simplified to V4 STRATEGY_MAP)
from utils.notifier import send_message, notify_buy, notify_sell, notify_startup
from utils.logger import log_trade_entry, log_trade_exit, print_performance_summary
from utils.helpers import Timer, calculate_pnl_pct


class SlotState(Enum):
    """State of a sniper slot."""
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    IN_POSITION = "IN_POSITION"
    EXITING = "EXITING"


@dataclass
class Opportunity:
    """An opportunity found by the Watchtower."""
    symbol: str
    ticker_data: Dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0


@dataclass
class SlotPosition:
    """A position managed by a SniperSlot."""
    symbol: str
    trade_id: str
    entry_price: float
    quantity: float
    take_profit: float
    stop_loss: float
    slot_id: int
    trailing_stop: Optional[float] = None
    trailing_activated: bool = False
    highest_price: float = field(default=0.0)
    entry_time: datetime = field(default_factory=datetime.now)
    timer: Timer = field(default_factory=Timer)
    # V4.1: Sector tracking
    # V4.1: Sector tracking
    sector: str = "DEFAULT"
    # V5: Server-side Stop Loss ID
    server_sl_order_id: Optional[str] = None
    
    def __post_init__(self):
        self.highest_price = self.entry_price
        self.timer.start()


class SniperSlot:
    """
    V3 SniperSlot: Independent trading slot that manages ONE position.
    
    Each slot:
    - Pulls opportunities from the shared queue
    - Runs full analysis
    - Manages its own position lifecycle
    """
    
    def __init__(self, slot_id: int, queue: asyncio.Queue, shared_state: Dict):
        self.slot_id = slot_id
        self.queue = queue
        self.shared_state = shared_state  # Shared state between slots
        self.state = SlotState.IDLE
        self.position: Optional[SlotPosition] = None
        
        self.scanner = get_scanner()
        self.analyzer = get_analyzer()
        self.capital_manager = get_capital_manager()
        self.handler = get_handler()  # V5: Handler integration
        
        # Slot-specific paper balance
        self.allocated_capital = 0.0
    
    def get_slot_name(self) -> str:
        return f"[SLOT-{self.slot_id}]"
    
    async def can_trade(self) -> bool:
        """
        Check if this slot can take a new trade.
        
        Checks basic guards (position, hours, drawdown, kill switch)
        and Handler risk authority. Strategy selection happens later in analyze().
        """
        if self.position is not None:
            return False
        
        if self.capital_manager.is_dead_hours(include_buffer=True):
            return False
        
        # V4.1: Check Daily Drawdown Guard
        if self.capital_manager.is_daily_drawdown_limit_hit():
            return False
        
        # V4.1: Check Kill Switch
        if self.capital_manager.is_kill_switch_active():
            return False
        
        # Handler has final authority over risk budgets
        try:
            decision = self.handler.approve_trade()
            if decision != TradeDecision.APPROVED:
                print(f"{self.get_slot_name()} ⛔ Handler blocked: {decision.value}")
                return False
        except Exception as e:
            print(f"{self.get_slot_name()} ⚠️ Handler check error: {e}")
        
        # Check if we have capital available
        total_allocated = sum(
            slot.allocated_capital 
            for slot in self.shared_state.get('slots', [])
            if slot.position is not None
        )
        available = self.shared_state.get('balance', INITIAL_BALANCE) - total_allocated
        
        if available < BASE_TRADE_SIZE:
            return False
        
        return True
    
    async def can_trade_symbol(self, symbol: str) -> bool:
        """
        V4.1: Check if this specific symbol can be traded (sector caps).
        
        Args:
            symbol: Trading pair to check
            
        Returns:
            True if sector cap allows, False otherwise
        """
        if not SECTOR_CAPS_ENABLED:
            return True
        
        sector = self.scanner.get_coin_sector(symbol)
        return self.capital_manager.can_open_sector_slot(sector)
    
    async def enter_position(self, analysis: AnalysisResult) -> bool:
        """Enter a new position based on analysis."""
        if not analysis.is_buy_signal:
            return False
        
        symbol = analysis.symbol
        price = analysis.price
        
        # V4.1: Check sector cap before entering
        if not await self.can_trade_symbol(symbol):
            print(f"{self.get_slot_name()} ❌ Sector cap reached for {symbol}")
            return False
        
        # Calculate position size using CapitalManager (correct slot count)
        if PAPER_TRADING:
            total_allocated = sum(
                slot.allocated_capital 
                for slot in self.shared_state.get('slots', [])
                if slot.position is not None
            )
            available = self.shared_state.get('balance', INITIAL_BALANCE) - total_allocated
        else:
            available = self.scanner.get_balance('USDT')
            self.shared_state['balance'] = available  # Keep in sync
        active_positions = sum(1 for s in self.shared_state.get('slots', []) if s.position is not None)
        slot_size = self.capital_manager.calculate_slot_size(available, active_positions)
        if slot_size <= 0:
            print(f"{self.get_slot_name()} ❌ No capital available for new trade")
            return False
        quantity = slot_size / price
        
        # Round quantity to exchange precision (prevent order rejection)
        try:
            self.scanner._ensure_markets_loaded()
            market = self.scanner.exchange.markets.get(symbol, {})
            precision = market.get('precision', {}).get('amount')
            if precision is not None:
                quantity = self.scanner.exchange.amount_to_precision(symbol, quantity)
                quantity = float(quantity)
        except Exception:
            quantity = float(int(quantity * 1000) / 1000)  # Fallback: 3 decimals
        
        # Create trade ID
        trade_id = f"SLOT{self.slot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # V4.1: Get sector for tracking
        sector = self.scanner.get_coin_sector(symbol)
        
        # Create position
        self.position = SlotPosition(
            symbol=symbol,
            trade_id=trade_id,
            entry_price=price,
            quantity=quantity,
            take_profit=analysis.take_profit,
            stop_loss=analysis.stop_loss,
            slot_id=self.slot_id,
            sector=sector
        )

        # LIVE: Place market buy order
        if not PAPER_TRADING:
            try:
                print(f"{self.get_slot_name()} 🚀 Placing LIVE MARKET BUY: {symbol} qty={quantity:.6f}")
                order = self.scanner.exchange.create_market_buy_order(symbol, quantity)
                # Update with actual filled price and quantity
                filled_price = float(order.get('average', price))
                filled_qty = float(order.get('filled', quantity))
                if filled_price > 0:
                    self.position.entry_price = filled_price
                if filled_qty > 0:
                    self.position.quantity = filled_qty
                    quantity = filled_qty
                print(f"{self.get_slot_name()} ✅ FILLED @ ${filled_price:.6f} (qty: {filled_qty:.6f})")
            except Exception as e:
                print(f"{self.get_slot_name()} ❌ LIVE BUY FAILED: {e}")
                self.position = None
                self.state = SlotState.IDLE
                return False

        # V5: Place Server-Side Stop Loss (Live Only)
        if not PAPER_TRADING:
            try:
                sl_id = self.scanner.create_stop_loss_order(symbol, quantity, analysis.stop_loss)
                if sl_id:
                    self.position.server_sl_order_id = sl_id
                    print(f"{self.get_slot_name()} 🛡️ Server-Side SL Placed: {sl_id} @ ${analysis.stop_loss:.6f}")
                else:
                    print(f"{self.get_slot_name()} ⚠️ Failed to place Server-Side SL!")
            except Exception as e:
                print(f"{self.get_slot_name()} ⚠️ Error placing Server-Side SL: {e}")
        self.allocated_capital = slot_size
        self.state = SlotState.IN_POSITION
        
        # V4.1: Register position with capital manager for sector tracking
        self.capital_manager.add_sector_position(symbol, sector)
        
        print(f"{self.get_slot_name()} 🎯 ENTERED: {symbol} @ ${price:.6f} (Size: ${slot_size:.2f}, Sector: {sector})")
        
        # Log and notify
        try:
            log_trade_entry(
                symbol=symbol,
                trade_id=trade_id,
                entry_price=price,
                quantity=quantity,
                take_profit=analysis.take_profit,
                stop_loss=analysis.stop_loss,
                balance_before=available
            )
        except Exception as e:
            print(f"{self.get_slot_name()} ⚠️ Logging failed: {e}")
        
        # Use market regime from analysis (avoids redundant API call)
        current_regime = analysis.market_regime or 'UNKNOWN'
        notify_buy(symbol, price, analysis.take_profit, analysis.stop_loss, 
                   regime=current_regime, slot_id=self.slot_id, slot_size=self.allocated_capital, balance=self.shared_state.get('balance', INITIAL_BALANCE))
        
        return True
    
    async def exit_position(self, reason: str, exit_price: Optional[float] = None) -> bool:
        """Exit the current position."""
        if self.position is None:
            return False
        
        pos = self.position
        
        # Get exit price if not provided
        if exit_price is None:
            ticker = self.scanner.exchange.fetch_ticker(pos.symbol)
            exit_price = ticker.get('last', pos.entry_price)
        
        # Calculate P&L
        pnl_pct = calculate_pnl_pct(pos.entry_price, exit_price)
        pnl_usd = (exit_price - pos.entry_price) * pos.quantity
        
        print(f"{self.get_slot_name()} 🏁 EXITED: {pos.symbol} @ ${exit_price:.6f} | {reason} | P&L: {pnl_pct:+.2f}%")
        
        # LIVE: Handle sell order
        if not PAPER_TRADING:
            # Check if server-side SL already sold the coins
            server_sl_already_filled = False
            if pos.server_sl_order_id:
                sl_status = self.scanner.check_order_status(pos.symbol, pos.server_sl_order_id)
                if sl_status == 'closed':
                    server_sl_already_filled = True
                    # Get actual fill price from the SL order
                    try:
                        sl_order = self.scanner.exchange.fetch_order(pos.server_sl_order_id, pos.symbol)
                        actual_exit = float(sl_order.get('average', exit_price))
                        if actual_exit > 0:
                            exit_price = actual_exit
                            pnl_pct = calculate_pnl_pct(pos.entry_price, exit_price)
                            pnl_usd = (exit_price - pos.entry_price) * pos.quantity
                        print(f"{self.get_slot_name()} 🛡️ Server SL filled @ ${exit_price:.6f}")
                    except Exception:
                        print(f"{self.get_slot_name()} 🛡️ Server SL filled (using estimated price)")
                    pos.server_sl_order_id = None
                else:
                    # Cancel SL before manual sell
                    try:
                        self.scanner.cancel_order(pos.symbol, pos.server_sl_order_id)
                        pos.server_sl_order_id = None
                    except Exception:
                        pass
            
            # Only place market sell if server SL didn't already sell
            if not server_sl_already_filled:
                try:
                    print(f"{self.get_slot_name()} 🚨 Placing LIVE MARKET SELL: {pos.symbol} qty={pos.quantity:.6f}")
                    sell_order = self.scanner.exchange.create_market_sell_order(pos.symbol, pos.quantity)
                    actual_exit = float(sell_order.get('average', exit_price))
                    if actual_exit > 0:
                        exit_price = actual_exit
                        pnl_pct = calculate_pnl_pct(pos.entry_price, exit_price)
                        pnl_usd = (exit_price - pos.entry_price) * pos.quantity
                    print(f"{self.get_slot_name()} ✅ SOLD @ ${exit_price:.6f}")
                except Exception as e:
                    print(f"{self.get_slot_name()} ❌ LIVE SELL FAILED: {e}")
                    # Don't return False — position tracking must still clean up
        
        # Update balance
        if PAPER_TRADING:
            self.shared_state['balance'] = self.shared_state.get('balance', INITIAL_BALANCE) + pnl_usd
        else:
            # Read real balance from exchange
            real_balance = self.scanner.get_balance('USDT')
            self.shared_state['balance'] = real_balance
        
        # V4.1: Record PnL for daily drawdown guard
        self.capital_manager.record_trade_pnl(pnl_pct)
        
        # V4.1: Remove sector position tracking
        self.capital_manager.remove_sector_position(pos.symbol, pos.sector)
        
        # Cancel any remaining server SL (paper mode cleanup or edge cases)
        if pos.server_sl_order_id:
            try:
                self.scanner.cancel_order(pos.symbol, pos.server_sl_order_id)
            except Exception:
                pass  # Already cancelled or triggered
        
        # Log and notify
        log_trade_exit(
            trade_id=pos.trade_id,
            exit_price=exit_price,
            exit_reason=reason,
            balance_after=self.shared_state['balance']
        )
        notify_sell(pos.symbol, pos.entry_price, exit_price, pnl_pct, pnl_usd, 
                    reason, self.shared_state['balance'], slot_id=pos.slot_id, slot_size=self.allocated_capital)
        
        # Clear position
        self.position = None
        self.allocated_capital = 0.0
        self.state = SlotState.IDLE
        
        return True
    
    async def monitor_position(self) -> Optional[str]:
        """Monitor position and check exit conditions with V5 Winner Protection."""
        if self.position is None:
            return None
        
        pos = self.position
        
        try:
            ticker = self.scanner.exchange.fetch_ticker(pos.symbol)
            current_price = ticker.get('last', 0)
        except:
            return None
        
        if current_price == 0:
            return None
        
        # V5: Server-Side SL Check (Live Only)
        if pos.server_sl_order_id:
            status = self.scanner.check_order_status(pos.symbol, pos.server_sl_order_id)
            if status == 'closed':
                await self.exit_position("SL_HIT", current_price)
                return "SL_HIT"
        
        # Update highest price (for ratchet trailing stop)
        if current_price > pos.highest_price:
            pos.highest_price = current_price
        
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        # V5: HARD STOP LOSS SAFETY (Paper & Live)
        from config.settings import HARD_STOP_LOSS_PCT, RATCHET_TRAILING_STOP
        if pnl_pct <= -HARD_STOP_LOSS_PCT:
             print(f"{self.get_slot_name()} 🚨 HARD STOP HIT: {pnl_pct:.2f}% <= -{HARD_STOP_LOSS_PCT}%")
             await self.exit_position("HARD_STOP", current_price)
             return "HARD_STOP"

        # V5: Get asymmetric exit rules from Handler
        exit_rules = self.handler.get_exit_rules(pnl_pct)
        
        # BREAK-EVEN: Move stop to +0.1% once profit hits +0.8%
        if not pos.trailing_activated and pnl_pct >= exit_rules.break_even_trigger_pct:
            be_price = pos.entry_price * (1 + exit_rules.break_even_target_pct / 100)
            if be_price > pos.stop_loss:
                old_sl = pos.stop_loss
                pos.stop_loss = be_price
                print(f"{self.get_slot_name()} 🔒 BE: SL ${old_sl:.6f} → ${be_price:.6f}")
                if not PAPER_TRADING and pos.server_sl_order_id:
                    try:
                        self.scanner.cancel_order(pos.symbol, pos.server_sl_order_id)
                        new_id = self.scanner.create_stop_loss_order(
                            pos.symbol, pos.quantity, be_price)
                        if new_id:
                            pos.server_sl_order_id = new_id
                    except Exception as e:
                        print(f"{self.get_slot_name()} ⚠️ BE SL update failed: {e}")
        
        # Take Profit
        if current_price >= pos.take_profit:
            await self.exit_position("TP_HIT", current_price)
            return "TP_HIT"
        
        # Stop Loss (Software Fallback)
        if current_price <= pos.stop_loss:
            await self.exit_position("SL_HIT", current_price)
            return "SL_HIT"
        
        # V5: Trailing Stop activation using Winner Protection rules
        if not pos.trailing_activated and pnl_pct >= exit_rules.trailing_activation_pct:
            pos.trailing_activated = True
            pos.trailing_stop = current_price * (1 - exit_rules.trailing_distance_pct / 100)
            is_winner = self.handler.is_winner(pnl_pct)
            winner_tag = "🏆 WINNER" if is_winner else ""
            print(f"{self.get_slot_name()} 📈 Trailing stop activated @ ${pos.trailing_stop:.6f} (Trail: {exit_rules.trailing_distance_pct}%) {winner_tag}")
            
            # V5: Update Server-Side SL immediately on activation
            if not PAPER_TRADING:
                try:
                    if pos.server_sl_order_id:
                        self.scanner.cancel_order(pos.symbol, pos.server_sl_order_id)
                    
                    new_id = self.scanner.create_stop_loss_order(pos.symbol, pos.quantity, pos.trailing_stop)
                    if new_id:
                        pos.server_sl_order_id = new_id
                        print(f"{self.get_slot_name()} 🛡️ Server SL Updated (Trail Active): ${pos.trailing_stop:.6f}")
                except Exception as e:
                    print(f"{self.get_slot_name()} ⚠️ Failed to update Server SL: {e}")
        
        # Ratchet trailing stop update (only moves UP)
        if pos.trailing_activated and RATCHET_TRAILING_STOP:
            new_stop = pos.highest_price * (1 - exit_rules.trailing_distance_pct / 100)
            if new_stop > pos.trailing_stop:
                old_stop = pos.trailing_stop
                pos.trailing_stop = new_stop
                
                # V5: Update Server-Side SL on Ratchet
                if not PAPER_TRADING:
                    try:
                        if pos.server_sl_order_id:
                            self.scanner.cancel_order(pos.symbol, pos.server_sl_order_id)
                        
                        new_id = self.scanner.create_stop_loss_order(pos.symbol, pos.quantity, pos.trailing_stop)
                        if new_id:
                            pos.server_sl_order_id = new_id
                            print(f"{self.get_slot_name()} ⤴️ Server SL Ratcheted: ${old_stop:.6f} -> ${pos.trailing_stop:.6f}")
                    except Exception as e:
                        print(f"{self.get_slot_name()} ⚠️ Failed to update Server SL: {e}")
        
        # Trailing Stop hit
        if pos.trailing_activated and pos.trailing_stop and current_price <= pos.trailing_stop:
            await self.exit_position("TRAILING_STOP", current_price)
            return "TRAILING_STOP"
        
        # V5: Time-based exit using Winner Protection rules
        if exit_rules.time_exit_enabled:
            from config.settings import TIME_EXIT_MIN_PROFIT_PCT
            if pos.timer.has_exceeded(exit_rules.time_exit_minutes) and pnl_pct < TIME_EXIT_MIN_PROFIT_PCT:
                await self.exit_position("TIME_EXIT", current_price)
                return "TIME_EXIT"
        
        return None
    
    async def run(self):
        """Main slot loop."""
        print(f"{self.get_slot_name()} 🎯 Starting...")
        
        while self.shared_state.get('running', False):
            try:
                # If in position, monitor it
                if self.position is not None:
                    await self.monitor_position()
                    await asyncio.sleep(15)  # Check every 15 seconds
                    continue
                
                # Otherwise, try to get an opportunity
                if await self.can_trade():
                    try:
                        opportunity = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                        
                        # Check symbol not already held by another slot
                        held_symbols = [
                            s.position.symbol 
                            for s in self.shared_state.get('slots', [])
                            if s.position is not None
                        ]
                        if opportunity.symbol in held_symbols:
                            print(f"{self.get_slot_name()} ⏭️ {opportunity.symbol} already held")
                            self.queue.task_done()
                            continue
                        
                        # Analyze
                        self.state = SlotState.ANALYZING
                        result = self.analyzer.analyze(opportunity.symbol, opportunity.ticker_data)
                        
                        if result.is_buy_signal:
                            await self.enter_position(result)
                        else:
                            print(f"{self.get_slot_name()} ❌ {opportunity.symbol}: {result.rejection_reason}")
                        
                        self.queue.task_done()
                        
                    except asyncio.TimeoutError:
                        pass
                else:
                    await asyncio.sleep(5)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"{self.get_slot_name()} Error: {e}")
                await asyncio.sleep(10)
        
        # Cleanup: exit any open position
        if self.position is not None:
            await self.exit_position("SHUTDOWN")


class Watchtower:
    """The Watchtower (Producer): Continuously scans for opportunities."""
    
    def __init__(self, queue: asyncio.Queue, shared_state: Dict):
        self.queue = queue
        self.shared_state = shared_state
        self.scanner = get_scanner()
        self.capital_manager = get_capital_manager()
    
    async def scan_once(self) -> List[Opportunity]:
        """Perform a single scan cycle."""
        if self.capital_manager.is_dead_hours(include_buffer=True):
            is_dead, minutes_until = self.capital_manager.get_dead_hours_status()
            print(f"[WATCHTOWER] 🌙 Dead hours. Resuming in {minutes_until} minutes...")
            return []
        
        print(f"\n[WATCHTOWER] 🔭 Scanning...")
        watchlist = self.scanner.generate_watchlist()
        
        if not watchlist:
            return []
        
        opportunities = [
            Opportunity(
                symbol=c['symbol'],
                ticker_data=c,
                score=abs(c.get('change_24h', 0))
            )
            for c in watchlist
        ]
        
        print(f"[WATCHTOWER] Found {len(opportunities)} candidates")
        return opportunities
    
    async def run(self):
        """Main scanning loop."""
        print("[WATCHTOWER] 🔭 Starting...")
        
        while self.shared_state.get('running', False):
            try:
                opportunities = await self.scan_once()
                
                for opp in opportunities:
                    if not self.queue.full():
                        await self.queue.put(opp)
                
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WATCHTOWER] Error: {e}")
                await asyncio.sleep(30)


class Dispatcher:
    """V3 Dispatcher: Orchestrates multiple trading slots."""
    
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        
        self.capital_manager = get_capital_manager()
        
        # Get starting balance (real or paper)
        if PAPER_TRADING:
            start_balance = INITIAL_BALANCE
        else:
            scanner = get_scanner()
            start_balance = scanner.get_balance('USDT')
            if start_balance <= 0:
                print(f"[DISPATCHER] ⚠️ Could not read balance from Bybit, using INITIAL_BALANCE")
                start_balance = INITIAL_BALANCE
            else:
                print(f"[DISPATCHER] 💰 Bybit USDT Balance: ${start_balance:.2f}")
        
        self.shared_state: Dict = {
            'running': False,
            'balance': start_balance,
            'slots': []
        }
        
        # V3: Create slots DYNAMICALLY based on balance
        initial_slot_count = self.capital_manager.calculate_slot_count(start_balance)
        print(f"[DISPATCHER] Creating {initial_slot_count} slots for ${start_balance:.2f} balance")
        
        self.slots: List[SniperSlot] = []
        for i in range(initial_slot_count):
            slot = SniperSlot(i + 1, self.queue, self.shared_state)
            self.slots.append(slot)
        self.shared_state['slots'] = self.slots
        
        self.watchtower = Watchtower(self.queue, self.shared_state)
    
    def get_active_positions(self) -> int:
        """Count active positions across all slots."""
        return sum(1 for s in self.slots if s.position is not None)
    
    async def vault_manager(self):
        """Background vault rebalancing."""
        while self.shared_state.get('running', False):
            try:
                if self.capital_manager.should_rebalance_vault():
                    balance = self.shared_state.get('balance', INITIAL_BALANCE)
                    btc_balance = self.capital_manager.paper_btc_balance
                    action, amount = self.capital_manager.check_vault_action(balance, btc_balance)
                    
                    if action != "NONE":
                        self.capital_manager.execute_vault_action(action, amount, PAPER_TRADING)
                
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[VAULT] Error: {e}")
                await asyncio.sleep(3600)
    
    async def run(self):
        """Run the V3 dispatcher with multiple slots."""
        self.shared_state['running'] = True
        
        print("\n" + "="*50)
        print("🚀 SNIPER V3 - MULTI-SLOT DISPATCHER")
        print("="*50)
        print(f"Mode: {'PAPER TRADING' if PAPER_TRADING else '⚠️ LIVE TRADING'}")
        print(f"Balance: ${self.shared_state['balance']:.2f}")
        print(f"Slots: {MAX_CONCURRENT_SLOTS} concurrent")
        print(f"Scan Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
        print("="*50 + "\n")
        
        # Notify startup with version label
        mode = 'PAPER' if PAPER_TRADING else 'LIVE'
        notify_startup(self.shared_state['balance'], mode, len(self.slots))
        
        try:
            tasks = [
                asyncio.create_task(self.watchtower.run(), name="watchtower"),
                asyncio.create_task(self.vault_manager(), name="vault"),
            ]
            
            # Add slot tasks
            for slot in self.slots:
                tasks.append(asyncio.create_task(slot.run(), name=f"slot_{slot.slot_id}"))
            
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            print("\n[DISPATCHER] Shutting down...")
        finally:
            self.shared_state['running'] = False
            print_performance_summary()
            print("Goodbye! 👋")
    
    def stop(self):
        """Stop the dispatcher."""
        self.shared_state['running'] = False


# Singleton
_dispatcher_instance = None

def get_dispatcher() -> Dispatcher:
    """Get the global dispatcher instance."""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = Dispatcher()
    return _dispatcher_instance
