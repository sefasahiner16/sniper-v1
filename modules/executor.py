"""
Sniper V1 - The Executor (State Machine)
=========================================
Manages trade lifecycle, position monitoring, and risk controls.
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from config.settings import (
    PAPER_TRADING, INITIAL_BALANCE,
    TRAILING_STOP_ACTIVATION_PCT, TRAILING_STOP_DISTANCE_PCT,
    TIME_EXIT_MINUTES, HARD_STOP_LOSS_PCT,
    MAX_CONSECUTIVE_LOSSES, CIRCUIT_BREAKER_HOURS
)
from modules.scanner import get_scanner
from modules.analyzer import AnalysisResult
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
        """Check if we can open a new trade."""
        # Already in a position?
        if self.current_position is not None:
            return False
        
        # Check for open trade in logs
        open_trade = get_open_trade()
        if open_trade:
            print(f"[EXECUTOR] Found open trade: {open_trade['symbol']}")
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
        
        Args:
            analysis: AnalysisResult with buy signal
            
        Returns:
            True if entry successful
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
            
            # Update paper balance (we "spent" it)
            self.paper_balance = 0
            
            self.state = State.IN_POSITION
            
            # Send Telegram notification
            notify_buy(symbol, entry_price, take_profit, stop_loss)
            
            print(f"[EXECUTOR] ✅ Paper trade opened: {trade_id}")
            return True
        
        else:
            # TODO: Implement real trading with limit orders
            print("[EXECUTOR] Live trading not yet implemented")
            self.state = State.IDLE
            return False
    
    def update_trailing_stop(self, current_price: float) -> None:
        """Update trailing stop based on current price."""
        if self.current_position is None:
            return
        
        pos = self.current_position
        
        # Update highest price seen
        if current_price > pos.highest_price:
            pos.highest_price = current_price
        
        # Calculate current P&L
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        # Activate trailing stop if threshold reached
        if not pos.trailing_activated and pnl_pct >= TRAILING_STOP_ACTIVATION_PCT:
            pos.trailing_activated = True
            pos.trailing_stop = current_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            print(f"[EXECUTOR] 📈 Trailing stop ACTIVATED at ${pos.trailing_stop:.6f}")
        
        # Update trailing stop if price continues up
        elif pos.trailing_activated and current_price > pos.highest_price:
            new_trailing = current_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            if new_trailing > pos.trailing_stop:
                pos.trailing_stop = new_trailing
                print(f"[EXECUTOR] 📈 Trailing stop moved to ${pos.trailing_stop:.6f}")
    
    def check_exit_conditions(self, current_price: float) -> Optional[str]:
        """
        Check if any exit condition is met.
        
        Returns:
            Exit reason string or None
        """
        if self.current_position is None:
            return None
        
        pos = self.current_position
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        
        # Take Profit hit
        if current_price >= pos.take_profit:
            return "TP_HIT"
        
        # Hard Stop Loss hit
        if current_price <= pos.stop_loss:
            return "SL_HIT"
        
        # Trailing Stop hit
        if pos.trailing_activated and pos.trailing_stop and current_price <= pos.trailing_stop:
            return "TRAILING_STOP"
        
        # Time-based exit
        if pos.timer.has_exceeded(TIME_EXIT_MINUTES):
            if pnl_pct < 1.0:  # Less than 1% profit after 45 min
                return "TIME_EXIT"
        
        # Hard max loss (fallback)
        if pnl_pct <= -HARD_STOP_LOSS_PCT:
            return "SL_HIT"
        
        return None
    
    def exit_position(self, reason: str, current_price: Optional[float] = None) -> bool:
        """
        Exit the current position.
        
        Args:
            reason: Exit reason
            current_price: Exit price (fetched if not provided)
            
        Returns:
            True if exit successful
        """
        if self.current_position is None:
            print("[EXECUTOR] No position to exit")
            return False
        
        self.state = State.EXIT
        pos = self.current_position
        
        # Get exit price
        if current_price is None:
            current_price = self.get_current_price(pos.symbol)
            if current_price is None:
                print("[EXECUTOR] Could not get exit price")
                self.state = State.IN_POSITION
                return False
        
        # Calculate P&L
        pnl_pct = calculate_pnl_pct(pos.entry_price, current_price)
        pnl_usd = (current_price - pos.entry_price) * pos.quantity
        
        # Calculate new balance
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
            # Log the exit
            log_trade_exit(
                trade_id=pos.trade_id,
                exit_price=current_price,
                exit_reason=reason,
                balance_after=new_balance
            )
            
            # Update paper balance
            self.paper_balance = new_balance
            
            # Send Telegram notification
            notify_sell(pos.symbol, pos.entry_price, current_price, pnl_pct, pnl_usd, reason)
        
        # Clear position
        self.current_position = None
        self.state = State.IDLE
        
        emoji = "🟢" if pnl_pct >= 0 else "🔴"
        print(f"[EXECUTOR] {emoji} Position closed: {pnl_pct:+.2f}%")
        
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
        mode = "PAPER" if self.is_paper_mode else "LIVE"
        balance = self.get_balance()
        
        print(f"\n{'='*50}")
        print(f"🚀 SNIPER V1 STARTED")
        print(f"{'='*50}")
        print(f"Mode:    {mode}")
        print(f"Balance: ${balance:.2f}")
        print('='*50 + "\n")
        
        notify_startup(balance, mode)
        
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
