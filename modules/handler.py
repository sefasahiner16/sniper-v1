"""
Sniper V5 - The Handler (Capital Authority Layer)
==================================================
Final authority over all capital decisions.

Responsibilities:
1. Risk Budget Enforcement (daily/weekly/rolling limits)
2. Profit Locking (protect realized gains)
3. Winner Protection (asymmetric treatment of winning vs losing trades)
4. Emergency Overrides (market instability, correlation events)

Handler decisions override ALL other layers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum

from config.settings import (
    # Risk Budgets
    DAILY_LOSS_LIMIT_PCT, WEEKLY_LOSS_LIMIT_PCT, ROLLING_DRAWDOWN_LIMIT_PCT,
    # Profit Locking
    PROFIT_LOCK_TRIGGER_PCT, PROFIT_LOCK_RATIO,
    # Winner Protection
    WINNER_THRESHOLD_PCT, WINNER_TIME_EXIT_DISABLED,
    WINNER_TRAILING_ACTIVATION_PCT, WINNER_TRAILING_DISTANCE_PCT,
    # Existing settings
    TRAILING_STOP_ACTIVATION_PCT, TRAILING_STOP_DISTANCE_PCT,
    TIME_EXIT_MINUTES, BREAK_EVEN_TRIGGER_PCT, BREAK_EVEN_TARGET_PCT,
    INITIAL_BALANCE,
)
from utils.logger import load_trades


class TradeDecision(Enum):
    """Handler's decision on a trade request."""
    APPROVED = "APPROVED"
    DENIED_DAILY_LIMIT = "DENIED_DAILY_LIMIT"
    DENIED_WEEKLY_LIMIT = "DENIED_WEEKLY_LIMIT" 
    DENIED_DRAWDOWN_LIMIT = "DENIED_DRAWDOWN_LIMIT"
    DENIED_FAKE_REGIME = "DENIED_FAKE_REGIME"
    DENIED_EMERGENCY = "DENIED_EMERGENCY"


@dataclass
class ExitRules:
    """Position-specific exit rules (asymmetric for winners vs losers)."""
    time_exit_enabled: bool = True
    time_exit_minutes: int = TIME_EXIT_MINUTES
    trailing_activation_pct: float = TRAILING_STOP_ACTIVATION_PCT
    trailing_distance_pct: float = TRAILING_STOP_DISTANCE_PCT
    break_even_trigger_pct: float = BREAK_EVEN_TRIGGER_PCT
    break_even_target_pct: float = BREAK_EVEN_TARGET_PCT
    stop_tightening_speed: str = "NORMAL"  # FAST, NORMAL, SLOW


@dataclass
class RiskState:
    """Current risk state tracking."""
    daily_pnl_pct: float = 0.0
    weekly_pnl_pct: float = 0.0
    peak_balance: float = INITIAL_BALANCE
    current_balance: float = INITIAL_BALANCE
    locked_capital_pct: float = 0.0
    emergency_mode: bool = False
    last_update: datetime = field(default_factory=datetime.now)


class Handler:
    """
    Capital Authority Layer
    
    The Handler is the absolute authority over capital.
    It does not search for opportunities and does not analyze markets.
    Its sole responsibility is: Preventing capital destruction while allowing capital growth.
    """
    
    def __init__(self):
        """Initialize the handler."""
        self.risk_state = RiskState()
        self._load_state()
    
    def _load_state(self):
        """Load state from trade history."""
        try:
            trades = load_trades()
            if not trades:
                return
            
            # Calculate daily PnL
            today = datetime.now().date()
            daily_pnl = 0.0
            
            # Calculate weekly PnL
            week_start = today - timedelta(days=today.weekday())
            weekly_pnl = 0.0
            
            # Find peak balance
            running_balance = INITIAL_BALANCE
            peak_balance = INITIAL_BALANCE
            
            for trade in trades:
                if 'exit_time' not in trade:
                    continue
                    
                pnl = trade.get('profit_loss', 0)
                running_balance += pnl
                peak_balance = max(peak_balance, running_balance)
                
                # Parse trade date
                try:
                    trade_date = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00')).date()
                except:
                    continue
                
                if trade_date == today:
                    daily_pnl += pnl
                
                if trade_date >= week_start:
                    weekly_pnl += pnl
            
            # Calculate percentages
            self.risk_state.daily_pnl_pct = (daily_pnl / INITIAL_BALANCE) * 100 if INITIAL_BALANCE > 0 else 0
            self.risk_state.weekly_pnl_pct = (weekly_pnl / INITIAL_BALANCE) * 100 if INITIAL_BALANCE > 0 else 0
            self.risk_state.peak_balance = peak_balance
            self.risk_state.current_balance = running_balance
            
        except Exception as e:
            print(f"[HANDLER] Error loading state: {e}")
    
    # =========================================================================
    # Risk Budget Enforcement
    # =========================================================================
    
    def check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit is breached.
        
        Returns:
            True if trading is allowed, False if blocked
        """
        self._load_state()  # Refresh
        return self.risk_state.daily_pnl_pct > DAILY_LOSS_LIMIT_PCT
    
    def check_weekly_loss_limit(self) -> bool:
        """
        Check if weekly loss limit is breached.
        
        Returns:
            True if trading is allowed, False if blocked
        """
        self._load_state()
        return self.risk_state.weekly_pnl_pct > WEEKLY_LOSS_LIMIT_PCT
    
    def check_rolling_drawdown(self) -> bool:
        """
        Check if rolling drawdown limit is breached.
        
        Returns:
            True if trading is allowed, False if blocked
        """
        if self.risk_state.peak_balance == 0:
            return True
            
        drawdown_pct = ((self.risk_state.current_balance - self.risk_state.peak_balance) 
                        / self.risk_state.peak_balance) * 100
        
        return drawdown_pct > ROLLING_DRAWDOWN_LIMIT_PCT
    
    def check_risk_budgets(self) -> TradeDecision:
        """
        Check all risk budgets.
        
        Returns:
            TradeDecision indicating if trade is allowed and why
        """
        if self.risk_state.emergency_mode:
            return TradeDecision.DENIED_EMERGENCY
        
        if not self.check_daily_loss_limit():
            print(f"[HANDLER] ⛔ DAILY LOSS LIMIT: {self.risk_state.daily_pnl_pct:.2f}% <= {DAILY_LOSS_LIMIT_PCT}%")
            return TradeDecision.DENIED_DAILY_LIMIT
        
        if not self.check_weekly_loss_limit():
            print(f"[HANDLER] ⛔ WEEKLY LOSS LIMIT: {self.risk_state.weekly_pnl_pct:.2f}% <= {WEEKLY_LOSS_LIMIT_PCT}%")
            return TradeDecision.DENIED_WEEKLY_LIMIT
        
        if not self.check_rolling_drawdown():
            print(f"[HANDLER] ⛔ DRAWDOWN LIMIT BREACHED")
            return TradeDecision.DENIED_DRAWDOWN_LIMIT
        
        return TradeDecision.APPROVED
    
    # =========================================================================
    # Profit Locking
    # =========================================================================
    
    def update_profit_lock(self) -> float:
        """
        Update profit lock based on daily gains.
        
        If daily gains exceed threshold, lock a portion from re-risking.
        
        Returns:
            Percentage of capital that is locked
        """
        self._load_state()
        
        if self.risk_state.daily_pnl_pct >= PROFIT_LOCK_TRIGGER_PCT:
            # Lock profits
            self.risk_state.locked_capital_pct = self.risk_state.daily_pnl_pct * PROFIT_LOCK_RATIO
            print(f"[HANDLER] 🔒 PROFIT LOCK: Locking {self.risk_state.locked_capital_pct:.2f}% of capital")
        else:
            # Reset lock at start of new day (handled by daily_pnl_pct reset)
            if self.risk_state.daily_pnl_pct < 0:
                self.risk_state.locked_capital_pct = 0.0
        
        return self.risk_state.locked_capital_pct
    
    def get_available_capital_pct(self) -> float:
        """
        Get percentage of capital available for trading.
        
        Returns:
            Percentage (0-100) of capital that can be risked
        """
        self.update_profit_lock()
        return max(0, 100.0 - self.risk_state.locked_capital_pct)
    
    # =========================================================================
    # Winner Protection (Asymmetric Exit Rules)
    # =========================================================================
    
    def is_winner(self, unrealized_pnl_pct: float) -> bool:
        """
        Determine if a position is considered a "winner".
        
        Winners get favorable exit rules (room to run).
        
        Args:
            unrealized_pnl_pct: Current unrealized P&L percentage
            
        Returns:
            True if position qualifies as winner
        """
        return unrealized_pnl_pct >= WINNER_THRESHOLD_PCT
    
    def get_exit_rules(self, unrealized_pnl_pct: float) -> ExitRules:
        """
        Get exit rules based on whether position is winner or loser.
        
        Core Asymmetry:
        - Losers: Fast stops, time exits enforced
        - Winners: Wide trailing, no time pressure
        
        Args:
            unrealized_pnl_pct: Current unrealized P&L percentage
            
        Returns:
            ExitRules configured for this position type
        """
        is_winner = self.is_winner(unrealized_pnl_pct)
        
        if is_winner:
            # WINNER: Give room to run
            return ExitRules(
                time_exit_enabled=not WINNER_TIME_EXIT_DISABLED,
                time_exit_minutes=TIME_EXIT_MINUTES * 3,  # 3x longer if enabled
                trailing_activation_pct=WINNER_TRAILING_ACTIVATION_PCT,
                trailing_distance_pct=WINNER_TRAILING_DISTANCE_PCT,
                break_even_trigger_pct=BREAK_EVEN_TRIGGER_PCT,
                break_even_target_pct=BREAK_EVEN_TARGET_PCT,
                stop_tightening_speed="SLOW"
            )
        else:
            # LOSER or NEUTRAL: Cut fast
            return ExitRules(
                time_exit_enabled=True,
                time_exit_minutes=TIME_EXIT_MINUTES,
                trailing_activation_pct=TRAILING_STOP_ACTIVATION_PCT,
                trailing_distance_pct=TRAILING_STOP_DISTANCE_PCT,
                break_even_trigger_pct=BREAK_EVEN_TRIGGER_PCT,
                break_even_target_pct=BREAK_EVEN_TARGET_PCT,
                stop_tightening_speed="FAST"
            )
    
    # =========================================================================
    # Emergency Overrides
    # =========================================================================
    
    def check_market_emergency(self, btc_1h_change: float) -> bool:
        """
        Check for market-wide emergency conditions.
        
        Args:
            btc_1h_change: BTC price change over last hour (%)
            
        Returns:
            True if emergency mode should be activated
        """
        # BTC flash crash detection (already exists, but now Handler controls it)
        if btc_1h_change <= -3.0:
            self.risk_state.emergency_mode = True
            print(f"[HANDLER] 🚨 EMERGENCY MODE: BTC crashed {btc_1h_change:.2f}% in 1h")
            return True
        
        return False
    
    def activate_emergency_mode(self, reason: str = "Manual"):
        """Activate emergency mode manually."""
        self.risk_state.emergency_mode = True
        print(f"[HANDLER] 🚨 EMERGENCY MODE ACTIVATED: {reason}")
    
    def deactivate_emergency_mode(self):
        """Deactivate emergency mode."""
        self.risk_state.emergency_mode = False
        print(f"[HANDLER] ✅ EMERGENCY MODE DEACTIVATED")
    
    # =========================================================================
    # Final Authority: Trade Approval
    # =========================================================================
    
    def approve_trade(self, regime_allows: bool = True) -> TradeDecision:
        """
        THE final gate for all trade requests.
        
        This is the single point of authority for capital deployment.
        Scanner and Watchtower requests must pass through here.
        
        Args:
            regime_allows: Whether the current regime allows new trades
            
        Returns:
            TradeDecision with approval status
        """
        # Check emergency mode first
        if self.risk_state.emergency_mode:
            return TradeDecision.DENIED_EMERGENCY
        
        # Check if regime blocks trading (FAKE/NO-TRADE)
        if not regime_allows:
            return TradeDecision.DENIED_FAKE_REGIME
        
        # Check risk budgets
        budget_decision = self.check_risk_budgets()
        if budget_decision != TradeDecision.APPROVED:
            return budget_decision
        
        # All checks passed
        return TradeDecision.APPROVED
    
    def get_status_summary(self) -> str:
        """Get a summary of current handler state for logging."""
        self._load_state()
        
        return (
            f"[HANDLER] Status: "
            f"Daily={self.risk_state.daily_pnl_pct:+.2f}% | "
            f"Weekly={self.risk_state.weekly_pnl_pct:+.2f}% | "
            f"Locked={self.risk_state.locked_capital_pct:.1f}% | "
            f"Emergency={'🚨 YES' if self.risk_state.emergency_mode else '✅ NO'}"
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_handler_instance: Optional[Handler] = None


def get_handler() -> Handler:
    """Get the global handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = Handler()
    return _handler_instance
