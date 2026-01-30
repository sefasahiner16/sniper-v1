"""
Sniper V3 - The Executor (State Machine)
=========================================
Manages trade lifecycle, position monitoring, and risk controls.

V2 Features:
- Ratchet Trailing Stop (only moves UP, never down)
- Dead hours integration
- Enhanced time-based exit
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from config.settings import (
    PAPER_TRADING, INITIAL_BALANCE,
    TRAILING_STOP_ACTIVATION_PCT, TRAILING_STOP_DISTANCE_PCT,
    BREAK_EVEN_TRIGGER_PCT, BREAK_EVEN_TARGET_PCT,
    TIME_EXIT_MINUTES, TIME_EXIT_MIN_PROFIT_PCT, HARD_STOP_LOSS_PCT,
    MAX_CONSECUTIVE_LOSSES, CIRCUIT_BREAKER_HOURS,
    RATCHET_TRAILING_STOP, MAX_CONCURRENT_SLOTS
)
from utils.helpers import Timer, calculate_pnl_pct, is_weekend
from modules.scanner import get_scanner
from modules.analyzer import AnalysisResult
from modules.capital_manager import get_capital_manager
from utils.logger import (
    log_trade_entry, log_trade_exit, get_open_trade,
    get_performance_stats, print_performance_summary
)
from utils.notifier import (
    notify_buy, notify_sell, notify_circuit_breaker, notify_startup
)
from utils.helpers import Timer, calculate_pnl_pct


class State(Enum):
    """Bot state machine states."""
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    ENTRY = "ENTRY"
    IN_POSITION = "IN_POSITION"
    EXIT = "EXIT"
    PAUSED = "PAUSED"  # Circuit breaker active


@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    trade_id: str
    entry_price: float
    quantity: float
    take_profit: float
    stop_loss: float
    trailing_stop: Optional[float] = None
    trailing_activated: bool = False
    highest_price: float = field(default=0.0)
    entry_time: datetime = field(default_factory=datetime.now)
    timer: Timer = field(default_factory=Timer)
    server_stop_order_id: Optional[str] = None  # V3: Server-side stop order ID
    
    def __post_init__(self):
        self.highest_price = self.entry_price
        self.timer.start()


class Executor:
    """The trade execution and position management engine."""
    
    def __init__(self):
        """Initialize the executor."""
        self.scanner = get_scanner()
        self.state = State.IDLE
        self.current_position: Optional[Position] = None
        
        # Paper trading balance
        self.paper_balance = INITIAL_BALANCE
        self.is_paper_mode = PAPER_TRADING
        
        # Circuit breaker
        self.circuit_breaker_until: Optional[datetime] = None
    
    def get_balance(self) -> float:
        """Get current balance (paper or real)."""
        if self.is_paper_mode:
            return self.paper_balance
        else:
            return self.scanner.get_balance('USDT')
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            ticker = self.scanner.exchange.fetch_ticker(symbol)
            return ticker.get('last', 0)
        except Exception as e:
            print(f"[EXECUTOR] Error fetching price for {symbol}: {e}")
            return None
    
    def check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is active.
        
        Returns:
            True if trading is allowed, False if paused
        """
        # Check time-based circuit breaker
        if self.circuit_breaker_until:
            if datetime.now() < self.circuit_breaker_until:
                remaining = (self.circuit_breaker_until - datetime.now()).seconds // 60
                print(f"[EXECUTOR] Circuit breaker active. {remaining} minutes remaining.")
                return False
            else:
                print("[EXECUTOR] Circuit breaker expired. Resuming trading.")
                self.circuit_breaker_until = None
        
        # Check consecutive losses
        stats = get_performance_stats()
        if stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
            print(f"[EXECUTOR] 🚨 CIRCUIT BREAKER: {stats['consecutive_losses']} consecutive losses!")
            self.circuit_breaker_until = datetime.now().replace(
                hour=datetime.now().hour + CIRCUIT_BREAKER_HOURS
            )
            self.state = State.PAUSED
            notify_circuit_breaker(stats['consecutive_losses'], CIRCUIT_BREAKER_HOURS)
            return False
        
        return True
    
    def can_trade(self) -> bool:
        """
        Check if we can open a new trade.
        """
        # Already in a position?
        if self.current_position is not None:
            return False
        
        # Check for open trade in logs
        open_trade = get_open_trade()
        if open_trade:
            print(f"[EXECUTOR] Found open trade: {open_trade['symbol']}")
            return False
        
        # V2: Check dead hours (Shift System)
        capital_manager = get_capital_manager()
        is_dead, minutes_until = capital_manager.get_dead_hours_status()
        if is_dead:
            print(f"[EXECUTOR] 🌙 Dead Hours active. Trading resumes in {minutes_until} minutes.")
            return False
        
        # Check circuit breaker
        if not self.check_circuit_breaker():
            return False
        
        # Check balance
        balance = self.get_balance()
        if balance < 1.0:  # Minimum $1 to trade
            print(f"[EXECUTOR] Insufficient balance: ${balance:.2f}")
            return False
        
        return True
    
    def enter_position(self, analysis: AnalysisResult) -> bool:
        """
        Enter a new position based on analysis result.
        """
        if not analysis.is_buy_signal:
            print("[EXECUTOR] Cannot enter - no buy signal")
            return False
        
        if not self.can_trade():
            print("[EXECUTOR] Cannot trade at this time")
            return False
        
        self.state = State.ENTRY
        
        symbol = analysis.symbol
        entry_price = analysis.price
        take_profit = analysis.take_profit
        stop_loss = analysis.stop_loss
        
        # Calculate position size (use full balance)
        balance = self.get_balance()
        quantity = balance / entry_price
        
        print(f"\n{'='*50}")
        print(f"[EXECUTOR] ENTERING POSITION")
        print(f"{'='*50}")
        print(f"Symbol:      {symbol}")
        print(f"Entry Price: ${entry_price:.6f}")
        print(f"Quantity:    {quantity:.4f}")
        print(f"Position:    ${balance:.2f}")
        print(f"Take Profit: ${take_profit:.6f}")
        print(f"Stop Loss:   ${stop_loss:.6f}")
        print(f"Mode:        {'PAPER' if self.is_paper_mode else 'LIVE'}")
        print('='*50)
        
        server_stop_id = None
        
        if self.is_paper_mode:
            # Paper trading - simulate entry
            trade_id = log_trade_entry(
                symbol=symbol,
                entry_price=entry_price,
                quantity=quantity,
                take_profit=take_profit,
                stop_loss=stop_loss,
                balance_before=balance
            )
            
            self.current_position = Position(
                symbol=symbol,
                trade_id=trade_id,
                entry_price=entry_price,
                quantity=quantity,
                take_profit=take_profit,
                stop_loss=stop_loss
            )
            
            # Update paper balance
            self.paper_balance = 0
            self.state = State.IN_POSITION
            notify_buy(symbol, entry_price, take_profit, stop_loss)
            print(f"[EXECUTOR] ✅ Paper trade opened: {trade_id}")
            return True
        
        else:
            # LIVE TRADING with LIMIT ORDERS
            try:
                print(f"[EXECUTOR] 🚀 Placing LIVE LIMIT BUY order for {symbol} at ${entry_price:.6f}")
                order = self.scanner.exchange.create_limit_buy_order(symbol, quantity, entry_price)
                
                trade_id = str(order.get('id', int(time.time())))
                
                # V3: Server-Side Stop Loss
                # Place stop order immediately after buy
                server_stop_id = self.scanner.create_stop_loss_order(symbol, quantity, stop_loss)
                if server_stop_id:
                    print(f"[EXECUTOR] 🛡️ Server-Side Stop Loss ACTIVE: Order ID {server_stop_id}")
                else:
                     print(f"[EXECUTOR] ⚠️ WARNING: Server-Side Stop Loss FAILED. Using Software fallback.")

                log_trade_entry(
                    symbol=symbol,
                    entry_price=entry_price,
                    quantity=quantity,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    balance_before=balance
                )
                
                self.current_position = Position(
                    symbol=symbol,
                    trade_id=trade_id,
                    entry_price=entry_price,
                    quantity=quantity,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    server_stop_order_id=server_stop_id
                )
                
                self.state = State.IN_POSITION
                notify_buy(symbol, entry_price, take_profit, stop_loss)
                print(f"[EXECUTOR] ✅ Live trade opened: {trade_id}")
                return True
                
            except Exception as e:
                print(f"[EXECUTOR] ❌ Live limit buy failed: {e}")
                notify_circuit_breaker(0, 0)
                self.state = State.IDLE
                return False
    
    def update_trailing_stop(self, current_price: float) -> None:
        """
        Update trailing stop based on current price (Dual-Stage Ratchet).
        
        Stage 1: Break-Even (Safety)
        - Trigger: +1.0% Profit
        - Action: Move Stop to +0.1% (Entry + Fees)
        
        Stage 2: Wide Trail (Growth)
        - Trigger: +2.0% Profit
        - Action: Trail by 1.5% (Wide Gap)
        """
        if self.current_position is None:
            return
        
        pos = self.current_position
        
        # Update highest price seen
        if current_price > pos.highest_price:
            pos.highest_price = current_price
        
        # Calculate P&L
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        new_stop_price = None
        
        # ---------------------------------------------------------------------
        # STAGE 2: WIDE TRAILING STOP (Growth Phase)
        # ---------------------------------------------------------------------
        if pnl_pct >= TRAILING_STOP_ACTIVATION_PCT:
            # Check if we are already trailing or need to start
            if not pos.trailing_activated:
                pos.trailing_activated = True
                print(f"[EXECUTOR] 🚀 Starting STAGE 2: Wide Trail Activated (+{pnl_pct:.2f}%)")
            
            # Calculate trail price (Highest Price - Distance)
            new_trailing = pos.highest_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            
            # Check if we should update (Ratchet: Only move UP)
            current_stop = pos.trailing_stop if pos.trailing_stop else pos.stop_loss
            
            if new_trailing > current_stop:
                pos.trailing_stop = new_trailing
                new_stop_price = new_trailing
                print(f"[EXECUTOR] 📈 Trailing Update: ${new_trailing:.6f} (Gap: {TRAILING_STOP_DISTANCE_PCT}%)")

        # ---------------------------------------------------------------------
        # STAGE 1: BREAK-EVEN (Safety Phase)
        # ---------------------------------------------------------------------
        elif pnl_pct >= BREAK_EVEN_TRIGGER_PCT and not pos.trailing_activated:
            # Target price = Entry * (1 + 0.1%)
            be_price = pos.entry_price * (1 + BREAK_EVEN_TARGET_PCT / 100)
            
            # Only update if current stop is below BE price
            current_stop = pos.trailing_stop if pos.trailing_stop else pos.stop_loss
            
            if be_price > current_stop:
                pos.trailing_stop = be_price
                new_stop_price = be_price
                print(f"[EXECUTOR] 🛡️ STAGE 1: Break-Even Triggered (+{pnl_pct:.2f}%) -> Stop moved to ${be_price:.6f}")

        # V3: Update Server-Side Stop Order if changed
        if new_stop_price and not self.is_paper_mode:
            self._update_server_stop(pos, new_stop_price)

    def _update_server_stop(self, pos: Position, new_price: float) -> None:
        """Internal helper to update server-side stop."""
        try:
            # Cancel old stop
            if pos.server_stop_order_id:
                print(f"[EXECUTOR] 🔄 Updating Server Stop: Cancelling {pos.server_stop_order_id}...")
                self.scanner.cancel_order(pos.symbol, pos.server_stop_order_id)
            
            # Place new stop
            new_id = self.scanner.create_stop_loss_order(pos.symbol, pos.quantity, new_price)
            if new_id:
                pos.server_stop_order_id = new_id
                print(f"[EXECUTOR] ✅ Server Stop Updated to ${new_price:.6f}")
            else:
                print(f"[EXECUTOR] ❌ Failed to update Server Stop!")
        except Exception as e:
            print(f"[EXECUTOR] ⚠️ Error updating server stop: {e}")

    def check_exit_conditions(self, current_price: float) -> Optional[str]:
        """Check exit conditions."""
        if self.current_position is None:
            return None
        
        pos = self.current_position
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        if current_price >= pos.take_profit: return "TP_HIT"
        if current_price <= pos.stop_loss: return "SL_HIT"
        if pos.trailing_activated and pos.trailing_stop and current_price <= pos.trailing_stop: return "TRAILING_STOP"
        
        # V4: Dynamic Strategy Timeout Override
        # Fetch current strategy config to get the correct timeout
        strategy = self.scanner.get_active_strategy()
        timeout_minutes = strategy.get('timeout_minutes', TIME_EXIT_MINUTES)
        
        if pos.timer.has_exceeded(timeout_minutes):
            if pnl_pct < TIME_EXIT_MIN_PROFIT_PCT: return "TIME_EXIT"
        
        if pnl_pct <= -HARD_STOP_LOSS_PCT: return "SL_HIT"
        
        return None
    
    def exit_position(self, reason: str, current_price: Optional[float] = None) -> bool:
        """Exit the current position."""
        if self.current_position is None:
            return False
        
        self.state = State.EXIT
        pos = self.current_position
        
        # Get exit price
        if current_price is None:
            current_price = self.get_current_price(pos.symbol)
            if current_price is None:
                self.state = State.IN_POSITION
                return False
        
        # V3: Cancel Server-Side Stop before selling
        if not self.is_paper_mode and pos.server_stop_order_id:
            print(f"[EXECUTOR] 🛑 Cancelling Stop Loss {pos.server_stop_order_id} before exit...")
            self.scanner.cancel_order(pos.symbol, pos.server_stop_order_id)
            pos.server_stop_order_id = None # Clear ID
        
        # Calculate P&L
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        pnl_usd = (current_price - pos.entry_price) * pos.quantity
        new_balance = pos.quantity * current_price
        
        print(f"\n{'='*50}")
        print(f"[EXECUTOR] EXITING POSITION - {reason}")
        print(f"{'='*50}")
        print(f"Symbol:      {pos.symbol}")
        print(f"Entry:       ${pos.entry_price:.6f}")
        print(f"Exit:        ${current_price:.6f}")
        print(f"P&L:         {pnl_pct:+.2f}% (${pnl_usd:+.4f})")
        print(f"Balance:     ${new_balance:.4f}")
        print('='*50)
        
        if self.is_paper_mode:
            log_trade_exit(pos.trade_id, current_price, reason, new_balance)
            self.paper_balance = new_balance
            stats = get_performance_stats()
            notify_sell(pos.symbol, pos.entry_price, current_price, pnl_pct, pnl_usd, reason, new_balance, stats)
        
        else:
            # LIVE TRADING EXIT
            try:
                if reason == "TP_HIT":
                    print(f"[EXECUTOR] 💰 Placing LIVE LIMIT SELL order (Take Profit) for {pos.symbol} at ${current_price:.6f}")
                    self.scanner.exchange.create_limit_sell_order(pos.symbol, pos.quantity, current_price)
                else:
                    print(f"[EXECUTOR] 🚨 Placing LIVE MARKET SELL order ({reason}) for {pos.symbol}")
                    self.scanner.exchange.create_market_sell_order(pos.symbol, pos.quantity)
                
                log_trade_exit(pos.trade_id, current_price, reason, new_balance)
                stats = get_performance_stats()
                notify_sell(pos.symbol, pos.entry_price, current_price, pnl_pct, pnl_usd, reason, new_balance, stats)
                
            except Exception as e:
                print(f"[EXECUTOR] ❌ Live exit failed: {e}")
        
        self.current_position = None
        self.state = State.IDLE
        return True
    
    def monitor_position(self) -> None:
        """Monitor the current position and check exit conditions."""
        if self.current_position is None:
            return
        
        pos = self.current_position
        current_price = self.get_current_price(pos.symbol)
        
        if current_price is None:
            print(f"[EXECUTOR] Could not fetch price for {pos.symbol}")
            return
        
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        elapsed_min = pos.timer.elapsed_minutes()
        
        print(f"[MONITOR] {pos.symbol} | Price: ${current_price:.6f} | P&L: {pnl_pct:+.2f}% | Time: {elapsed_min:.1f}m")
        
        # Update trailing stop
        self.update_trailing_stop(current_price)
        
        # Check exit conditions
        exit_reason = self.check_exit_conditions(current_price)
        
        if exit_reason:
            self.exit_position(exit_reason, current_price)
    
    def startup(self) -> None:
        """Run startup sequence."""
        import os
        version = os.getenv("BOT_VERSION", "v3").upper()
        mode = "PAPER" if self.is_paper_mode else "LIVE"
        balance = self.get_balance()
        
        print(f"\n{'='*50}")
        print(f"🚀 SNIPER {version} STARTED")
        print(f"{'='*50}")
        print(f"Mode:    {mode}")
        print(f"Balance: ${balance:.2f}")
        print('='*50 + "\n")
        
        # Only send 1 notification (slots=1 for V2 single-slot mode)
        notify_startup(balance, mode, slots=1)
        
        # Print current stats
        print_performance_summary()


# Singleton instance
_executor_instance = None

def get_executor() -> Executor:
    """Get the global executor instance."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = Executor()
    return _executor_instance
