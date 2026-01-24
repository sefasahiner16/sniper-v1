"""
Sniper V3 - The Dispatcher (Multi-Slot Async Orchestrator)
===========================================================
Core V3 architecture: Producer-Consumer pattern with multiple slots.

Components:
- Watchtower: Async scanner that finds opportunities (Producer)
- SniperSlot: Async worker that manages ONE position (Consumer)
- Dispatcher: Orchestrates multiple slots

V3 Features:
- 3 concurrent trading slots
- Independent position management per slot
- Slot-aware notifications
"""

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from config.settings import (
    SCAN_INTERVAL_SECONDS, MAX_CONCURRENT_SLOTS,
    PAPER_TRADING, INITIAL_BALANCE, BASE_TRADE_SIZE, WHALE_CAP
)
from modules.scanner import get_scanner
from modules.analyzer import get_analyzer, AnalysisResult
from modules.capital_manager import get_capital_manager
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
        
        # Slot-specific paper balance
        self.allocated_capital = 0.0
    
    def get_slot_name(self) -> str:
        return f"[SLOT-{self.slot_id}]"
    
    async def can_trade(self) -> bool:
        """Check if this slot can take a new trade."""
        if self.position is not None:
            return False
        
        if self.capital_manager.is_dead_hours():
            return False
        
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
    
    async def enter_position(self, analysis: AnalysisResult) -> bool:
        """Enter a new position based on analysis."""
        if not analysis.is_buy_signal:
            return False
        
        symbol = analysis.symbol
        price = analysis.price
        
        # Calculate position size
        available = self.shared_state.get('balance', INITIAL_BALANCE)
        slot_size = min(available / MAX_CONCURRENT_SLOTS, WHALE_CAP)
        quantity = slot_size / price
        
        # Create trade ID
        trade_id = f"SLOT{self.slot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create position
        self.position = SlotPosition(
            symbol=symbol,
            trade_id=trade_id,
            entry_price=price,
            quantity=quantity,
            take_profit=analysis.take_profit,
            stop_loss=analysis.stop_loss,
            slot_id=self.slot_id
        )
        self.allocated_capital = slot_size
        self.state = SlotState.IN_POSITION
        
        print(f"{self.get_slot_name()} 🎯 ENTERED: {symbol} @ ${price:.6f} (Size: ${slot_size:.2f})")
        
        # Log and notify
        log_trade_entry(
            symbol=symbol,
            trade_id=trade_id,
            entry_price=price,
            quantity=quantity,
            take_profit=analysis.take_profit,
            stop_loss=analysis.stop_loss
        )
        notify_buy(symbol, price, analysis.take_profit, analysis.stop_loss)
        
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
        
        # Update paper balance
        self.shared_state['balance'] = self.shared_state.get('balance', INITIAL_BALANCE) + pnl_usd
        
        # Log and notify
        log_trade_exit(
            trade_id=pos.trade_id,
            exit_price=exit_price,
            exit_reason=reason,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd
        )
        notify_sell(pos.symbol, pos.entry_price, exit_price, pnl_pct, pnl_usd, reason)
        
        # Clear position
        self.position = None
        self.allocated_capital = 0.0
        self.state = SlotState.IDLE
        
        return True
    
    async def monitor_position(self) -> Optional[str]:
        """Monitor position and check exit conditions."""
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
        
        # Update highest price (for ratchet trailing stop)
        if current_price > pos.highest_price:
            pos.highest_price = current_price
        
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        # Check exit conditions
        from config.settings import (
            TRAILING_STOP_ACTIVATION_PCT, TRAILING_STOP_DISTANCE_PCT,
            TIME_EXIT_MINUTES, TIME_EXIT_MIN_PROFIT_PCT, RATCHET_TRAILING_STOP
        )
        
        # Take Profit
        if current_price >= pos.take_profit:
            await self.exit_position("TP_HIT", current_price)
            return "TP_HIT"
        
        # Stop Loss
        if current_price <= pos.stop_loss:
            await self.exit_position("SL_HIT", current_price)
            return "SL_HIT"
        
        # Trailing Stop activation
        if not pos.trailing_activated and pnl_pct >= TRAILING_STOP_ACTIVATION_PCT:
            pos.trailing_activated = True
            pos.trailing_stop = current_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            print(f"{self.get_slot_name()} 📈 Trailing stop activated @ ${pos.trailing_stop:.6f}")
        
        # Ratchet trailing stop update (only moves UP)
        if pos.trailing_activated and RATCHET_TRAILING_STOP:
            new_stop = pos.highest_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            if new_stop > pos.trailing_stop:
                pos.trailing_stop = new_stop
        
        # Trailing Stop hit
        if pos.trailing_activated and pos.trailing_stop and current_price <= pos.trailing_stop:
            await self.exit_position("TRAILING_STOP", current_price)
            return "TRAILING_STOP"
        
        # Time-based exit
        if pos.timer.has_exceeded(TIME_EXIT_MINUTES) and pnl_pct < TIME_EXIT_MIN_PROFIT_PCT:
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
        if self.capital_manager.is_dead_hours():
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
        self.shared_state: Dict = {
            'running': False,
            'balance': INITIAL_BALANCE,
            'slots': []
        }
        
        self.capital_manager = get_capital_manager()
        
        # V3: Create slots DYNAMICALLY based on balance
        # With $12 and BASE_TRADE_SIZE=$5, this creates 2 slots
        # As balance grows, more slots are added (up to MAX_CONCURRENT_SLOTS)
        initial_slot_count = self.capital_manager.calculate_slot_count(INITIAL_BALANCE)
        print(f"[DISPATCHER] Creating {initial_slot_count} slots for ${INITIAL_BALANCE:.2f} balance")
        
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
