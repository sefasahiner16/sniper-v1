"""
Sniper V4.1 - Capital Manager
==============================
Manages dynamic capital allocation, slot sizing, and the BTC vault.

Features:
- Auto-scaling slot count based on balance
- Elastic slot sizing (Bull Mode)
- Whale Cap enforcement
- BTC Treasury (Vault) overflow/refill

V4.1 Features:
- Daily Drawdown Guard
- Sector Slot Tracking (Correlation Protection)
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass

from config.settings import (
    BASE_TRADE_SIZE, WHALE_CAP, MIN_SLOT_SIZE, MAX_CONCURRENT_SLOTS,
    VAULT_ENABLED, VAULT_OVERFLOW_MULTIPLIER, VAULT_CRITICAL_LEVEL,
    VAULT_REBALANCE_HOUR_UTC, OPERATIONAL_CAP,
    DEAD_HOURS_ENABLED, DEAD_HOURS_START_UTC, DEAD_HOURS_END_UTC,
    # V4.1 imports
    DAILY_DRAWDOWN_GUARD_ENABLED, DAILY_DRAWDOWN_LIMIT_PCT,
    SECTOR_CAPS_ENABLED, SECTOR_CAPS
)


@dataclass
class CapitalAllocation:
    """Result of capital allocation calculation."""
    slot_count: int
    slot_size: float
    total_allocated: float
    reserve: float


class CapitalManager:
    """Manages capital allocation and vault operations."""
    
    def __init__(self):
        """Initialize the capital manager."""
        self.last_vault_rebalance: Optional[datetime] = None
        self.paper_btc_balance: float = 0.0  # For paper trading simulation
        
        # V4: BTC Flash Crash Kill Switch
        self.kill_switch_activated: Optional[datetime] = None
        
        # V4.1: Daily Drawdown Guard
        self.daily_realized_pnl: float = 0.0
        self.daily_pnl_reset_date: Optional[datetime] = None
        
        # V4.1: Sector Tracking
        self.sector_positions: Dict[str, List[str]] = {}  # sector -> [symbols]
    
    def calculate_slot_count(self, balance: float, max_slots_limit: int = MAX_CONCURRENT_SLOTS) -> int:
        """
        Calculate number of slots based on available balance.
        Rules:
        - Min 1 slot if balance is sufficient
        - Add 1 slot for every BASE_TRADE_SIZE ($6) increment
        - Cap at MAX_CONCURRENT_SLOTS (20) or strategy limit (e.g. 10 in Bunker)
        """
        if balance < MIN_SLOT_SIZE:
             return 0
             
        slots = int(balance / BASE_TRADE_SIZE)
        
        effective_limit = min(MAX_CONCURRENT_SLOTS, max_slots_limit)
        slot_count = max(1, min(slots, effective_limit))
        
        return slot_count
    
    def calculate_slot_size(
        self, 
        balance: float, 
        active_slots: int,
        queue_depth: int = 0,
        max_slots_limit: int = MAX_CONCURRENT_SLOTS
    ) -> float:
        """
        Calculate capital per slot with elastic sizing based on FREE balance.
        
        Args:
            balance: Available free USDT balance
            active_slots: Number of active slots
            queue_depth: Not heavily used, kept for compat.
            max_slots_limit: Dynamic limit from strategy.
            
        Returns:
            Capital to allocate per new slot
        """
        effective_limit = min(MAX_CONCURRENT_SLOTS, max_slots_limit)
        remaining_slots_limit = effective_limit - active_slots
        
        if remaining_slots_limit <= 0 or balance < MIN_SLOT_SIZE:
            return 0.0
            
        # Number of additional slots we WANT to open based on base size
        max_possible_new_slots = int(balance / BASE_TRADE_SIZE)
        new_slots_to_open = max(1, min(max_possible_new_slots, remaining_slots_limit))
        
        # Distribute the FREE balance equally among the new slots
        raw_size = balance / new_slots_to_open
        
        # Enforce limits
        slot_size = min(raw_size, WHALE_CAP)
        
        if slot_size < MIN_SLOT_SIZE:
            slot_size = MIN_SLOT_SIZE
            
        if slot_size > balance:
            slot_size = balance
            
        return slot_size
    
    def get_allocation(
        self, 
        balance: float, 
        active_slots: int = 0,
        queue_depth: int = 0,
        max_slots_limit: int = MAX_CONCURRENT_SLOTS
    ) -> CapitalAllocation:
        """
        Get full capital allocation recommendation.
        
        Args:
            balance: Available USDT balance
            active_slots: Currently active slot count
            queue_depth: Opportunities in queue
            max_slots_limit: Dynamic limit from strategy
        """
        slot_count = self.calculate_slot_count(balance, max_slots_limit)
        available_slots = max(0, slot_count - active_slots)
        slot_size = self.calculate_slot_size(balance, active_slots, queue_depth, max_slots_limit)
        
        total_allocated = available_slots * slot_size
        reserve = balance - total_allocated
        
        return CapitalAllocation(
            slot_count=slot_count,
            slot_size=slot_size,
            total_allocated=total_allocated,
            reserve=reserve
        )
    
    # =========================================================================
    # Dead Hours (Shift System)
    # =========================================================================
    
    def is_dead_hours(self, include_buffer: bool = False) -> bool:
        """
        Check if current time is within dead hours (or pre-buffer).
        """
        if not DEAD_HOURS_ENABLED:
            return False
            
        from config.settings import DEAD_HOURS_PRE_BUFFER_MINUTES
        
        current = datetime.now(timezone.utc)
        current_hour = current.hour
        current_minute = current.minute
        
        # Calculate effective start time (start - buffer)
        buffer_hours = DEAD_HOURS_PRE_BUFFER_MINUTES // 60
        buffer_minutes = DEAD_HOURS_PRE_BUFFER_MINUTES % 60
        
        # Check standard dead hours first
        in_dead_hours = False
        if DEAD_HOURS_START_UTC <= DEAD_HOURS_END_UTC:
            in_dead_hours = DEAD_HOURS_START_UTC <= current_hour < DEAD_HOURS_END_UTC
        else:
            in_dead_hours = current_hour >= DEAD_HOURS_START_UTC or current_hour < DEAD_HOURS_END_UTC
            
        if in_dead_hours:
            return True
            
        if not include_buffer:
            return False
            
        # Check buffer period
        # Simple check: are we within X minutes of start?
        # Calculate minutes from current time to start time
        if DEAD_HOURS_START_UTC > current_hour:
            minutes_until = (DEAD_HOURS_START_UTC - current_hour) * 60 - current_minute
        else:
            minutes_until = ((24 - current_hour) + DEAD_HOURS_START_UTC) * 60 - current_minute
            
        if 0 < minutes_until <= DEAD_HOURS_PRE_BUFFER_MINUTES:
            # We are in the buffer zone
            return True
            
        return False
    
    def get_dead_hours_status(self) -> Tuple[bool, Optional[int]]:
        """
        Get dead hours status with time until end.
        
        Returns:
            Tuple of (is_dead_hours, minutes_until_trading_resumes)
        """
        is_dead = self.is_dead_hours(include_buffer=True)
        
        if not is_dead:
            return False, None
        
        current = datetime.now(timezone.utc)
        current_hour = current.hour
        current_min = current.minute
        
        # Calculate minutes until dead hours end
        if DEAD_HOURS_START_UTC <= DEAD_HOURS_END_UTC:
            hours_until = DEAD_HOURS_END_UTC - current_hour
        else:
            if current_hour >= DEAD_HOURS_START_UTC:
                hours_until = (24 - current_hour) + DEAD_HOURS_END_UTC
            else:
                hours_until = DEAD_HOURS_END_UTC - current_hour
        
        minutes_until = (hours_until * 60) - current_min
        
        return True, minutes_until
    
    # =========================================================================
    # V4: BTC Flash Crash Kill Switch
    # =========================================================================
    
    def trigger_kill_switch(self):
        """Activate the kill switch - pauses all trading."""
        self.kill_switch_activated = datetime.now(timezone.utc)
        print(f"[KILL SWITCH] 🚨 ACTIVATED! Trading paused for emergency.")
    
    def is_kill_switch_active(self) -> bool:
        """
        Check if kill switch is currently active.
        
        Returns:
            True if trading should be paused due to kill switch
        """
        if self.kill_switch_activated is None:
            return False
        
        from config.settings import BTC_CRASH_PAUSE_HOURS
        
        now = datetime.now(timezone.utc)
        elapsed = now - self.kill_switch_activated
        pause_duration = timedelta(hours=BTC_CRASH_PAUSE_HOURS)
        
        if elapsed >= pause_duration:
            # Kill switch expired, reset it
            print(f"[KILL SWITCH] ✅ Expired. Trading can resume.")
            self.kill_switch_activated = None
            return False
        
        return True
    
    def get_kill_switch_status(self) -> Tuple[bool, Optional[int]]:
        """
        Get kill switch status with time until resume.
        
        Returns:
            Tuple of (is_active, minutes_until_resume)
        """
        if not self.is_kill_switch_active():
            return False, None
        
        from config.settings import BTC_CRASH_PAUSE_HOURS
        
        now = datetime.now(timezone.utc)
        elapsed = now - self.kill_switch_activated
        pause_duration = timedelta(hours=BTC_CRASH_PAUSE_HOURS)
        remaining = pause_duration - elapsed
        minutes_remaining = int(remaining.total_seconds() / 60)
        
        return True, minutes_remaining
    
    # =========================================================================
    # The Vault (BTC Treasury)
    # =========================================================================
    
    def should_rebalance_vault(self) -> bool:
        """
        Check if vault should be rebalanced.
        
        Vault rebalances once daily at the configured hour.
        
        Returns:
            True if rebalance should occur
        """
        if not VAULT_ENABLED:
            return False
        
        current = datetime.now(timezone.utc)
        
        # Check if it's the rebalance hour
        if current.hour != VAULT_REBALANCE_HOUR_UTC:
            return False
        
        # Check if we already rebalanced today
        if self.last_vault_rebalance:
            if self.last_vault_rebalance.date() == current.date():
                return False
        
        return True
    
    def check_vault_action(self, usdt_balance: float, btc_balance: float) -> Tuple[str, float]:
        """
        Determine what vault action to take.
        
        Logic:
        - OVERFLOW: If USDT > Operational Cap * Overflow Multiplier -> Buy BTC
        - CRITICAL: If USDT < Operational Cap * Critical Level -> Sell BTC
        - NONE: Otherwise
        
        Args:
            usdt_balance: Current USDT balance
            btc_balance: Current BTC balance (in USD value)
            
        Returns:
            Tuple of (action, amount_usd)
            action is one of: "BUY_BTC", "SELL_BTC", "NONE"
        """
        overflow_threshold = OPERATIONAL_CAP * VAULT_OVERFLOW_MULTIPLIER
        critical_threshold = OPERATIONAL_CAP * VAULT_CRITICAL_LEVEL
        
        if usdt_balance > overflow_threshold:
            # Surplus - buy BTC with excess
            excess = usdt_balance - OPERATIONAL_CAP
            return "BUY_BTC", excess
        
        elif usdt_balance < critical_threshold and btc_balance > 0:
            # Critical - sell BTC to refill
            needed = OPERATIONAL_CAP - usdt_balance
            sell_amount = min(needed, btc_balance)
            return "SELL_BTC", sell_amount
        
        return "NONE", 0.0
    
    def execute_vault_action(
        self, 
        action: str, 
        amount: float, 
        is_paper_mode: bool = True
    ) -> bool:
        """
        Execute a vault rebalance action.
        
        Args:
            action: "BUY_BTC" or "SELL_BTC"
            amount: USD amount to trade
            is_paper_mode: If True, simulate the trade
            
        Returns:
            True if successful
        """
        if action == "NONE":
            return True
        
        if is_paper_mode:
            # Simulate vault operation
            if action == "BUY_BTC":
                self.paper_btc_balance += amount
                print(f"[VAULT] 📦 Paper: Bought ${amount:.2f} worth of BTC")
            elif action == "SELL_BTC":
                self.paper_btc_balance = max(0, self.paper_btc_balance - amount)
                print(f"[VAULT] 📦 Paper: Sold ${amount:.2f} worth of BTC")
            
            self.last_vault_rebalance = datetime.now(timezone.utc)
            return True
        
        else:
            # TODO: Implement real vault trading
            print("[VAULT] Live vault trading not yet implemented")
            return False
    
    def get_vault_status(self) -> dict:
        """Get current vault status."""
        return {
            "enabled": VAULT_ENABLED,
            "btc_balance_usd": self.paper_btc_balance,
            "last_rebalance": self.last_vault_rebalance,
            "next_rebalance_hour_utc": VAULT_REBALANCE_HOUR_UTC
        }
    
    # =========================================================================
    # V4.1: Daily Drawdown Guard
    # =========================================================================
    
    def record_trade_pnl(self, pnl_pct: float) -> None:
        """
        V4.1: Record a trade's PnL for daily drawdown tracking.
        
        Args:
            pnl_pct: The P&L percentage of the closed trade
        """
        self._check_daily_reset()
        self.daily_realized_pnl += pnl_pct
        print(f"[CAPITAL] Daily P&L updated: {self.daily_realized_pnl:+.2f}%")
    
    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily PnL (new UTC day)."""
        now = datetime.now(timezone.utc)
        today = now.date()
        
        if self.daily_pnl_reset_date is None or self.daily_pnl_reset_date != today:
            if self.daily_realized_pnl != 0:
                print(f"[CAPITAL] 🌅 New UTC Day - Resetting daily P&L (was {self.daily_realized_pnl:+.2f}%)")
            self.daily_realized_pnl = 0.0
            self.daily_pnl_reset_date = today
    
    def is_daily_drawdown_limit_hit(self) -> bool:
        """
        V4.1: Check if daily drawdown limit has been hit.
        
        If True, new entries should be disabled until next UTC day.
        Open positions continue to be managed normally.
        
        Returns:
            True if daily PnL <= limit (e.g., -3%)
        """
        if not DAILY_DRAWDOWN_GUARD_ENABLED:
            return False
        
        self._check_daily_reset()
        
        if self.daily_realized_pnl <= DAILY_DRAWDOWN_LIMIT_PCT:
            print(f"[CAPITAL] 🚨 DAILY DRAWDOWN GUARD: P&L {self.daily_realized_pnl:.2f}% <= {DAILY_DRAWDOWN_LIMIT_PCT}% limit")
            return True
        
        return False
    
    def get_daily_drawdown_status(self) -> Tuple[bool, float]:
        """
        V4.1: Get daily drawdown guard status.
        
        Returns:
            Tuple of (is_limit_hit, current_daily_pnl)
        """
        self._check_daily_reset()
        is_hit = self.is_daily_drawdown_limit_hit()
        return is_hit, self.daily_realized_pnl
    
    # =========================================================================
    # V4.1: Sector Tracking (Correlation Protection)
    # =========================================================================
    
    def add_sector_position(self, symbol: str, sector: str) -> None:
        """
        V4.1: Track a new position by sector.
        
        Args:
            symbol: Trading pair (e.g., "DOGE/USDT")
            sector: Sector name (e.g., "MEME")
        """
        if sector not in self.sector_positions:
            self.sector_positions[sector] = []
        
        if symbol not in self.sector_positions[sector]:
            self.sector_positions[sector].append(symbol)
    
    def remove_sector_position(self, symbol: str, sector: str) -> None:
        """
        V4.1: Remove a position from sector tracking.
        
        Args:
            symbol: Trading pair
            sector: Sector name
        """
        if sector in self.sector_positions:
            if symbol in self.sector_positions[sector]:
                self.sector_positions[sector].remove(symbol)
    
    def get_sector_slot_count(self, sector: str) -> int:
        """
        V4.1: Get current slot count for a sector.
        
        Args:
            sector: Sector name
            
        Returns:
            Number of open positions in this sector
        """
        return len(self.sector_positions.get(sector, []))
    
    def can_open_sector_slot(self, sector: str) -> bool:
        """
        V4.1: Check if we can open another slot in this sector.
        
        Rules:
        - Check against sector cap
        - Never force-close existing positions
        
        Args:
            sector: Sector name
            
        Returns:
            True if sector cap allows, False otherwise
        """
        if not SECTOR_CAPS_ENABLED:
            return True
        
        current_count = self.get_sector_slot_count(sector)
        sector_cap = SECTOR_CAPS.get(sector, SECTOR_CAPS.get("DEFAULT", 10))
        
        if current_count >= sector_cap:
            print(f"[CAPITAL] 🚫 Sector cap reached: {sector} has {current_count}/{sector_cap} slots")
            return False
        
        return True


# Singleton instance
_capital_manager_instance = None


def get_capital_manager() -> CapitalManager:
    """Get the global capital manager instance."""
    global _capital_manager_instance
    if _capital_manager_instance is None:
        _capital_manager_instance = CapitalManager()
    return _capital_manager_instance
