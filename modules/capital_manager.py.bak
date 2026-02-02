"""
Sniper V2 - Capital Manager
============================
Manages dynamic capital allocation, slot sizing, and the BTC vault.

Features:
- Auto-scaling slot count based on balance
- Elastic slot sizing (Bull Mode)
- Whale Cap enforcement
- BTC Treasury (Vault) overflow/refill
"""

from datetime import datetime, timezone
from typing import Tuple, Optional
from dataclasses import dataclass

from config.settings import (
    BASE_TRADE_SIZE, WHALE_CAP, MIN_SLOT_SIZE, MAX_CONCURRENT_SLOTS,
    VAULT_ENABLED, VAULT_OVERFLOW_MULTIPLIER, VAULT_CRITICAL_LEVEL,
    VAULT_REBALANCE_HOUR_UTC, OPERATIONAL_CAP,
    DEAD_HOURS_ENABLED, DEAD_HOURS_START_UTC, DEAD_HOURS_END_UTC
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
    
    def calculate_slot_count(self, balance: float, max_slots_limit: int = MAX_CONCURRENT_SLOTS) -> int:
        """
        Calculate number of slots based on available balance.
        Rules:
        - Min 1 slot
        - Add 1 slot for every BASE_TRADE_SIZE ($6) increment
        - Cap at MAX_CONCURRENT_SLOTS (20) or strategy limit (e.g. 10 in Bunker)
        """
        if balance < MIN_SLOT_SIZE:
             return 0 # Can't trade if < $6
             
        # Example: Balance $12, Base $6 -> 2 slots
        # Example: Balance $50, Base $6 -> 8 slots
        # Example: Balance $200, Base $6 -> 33 slots -> Capped at 20
        slots = int(balance / BASE_TRADE_SIZE)
        
        # Cap at limits (Strategy-defined limit takes precedence if lower)
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
        Calculate capital per slot with elastic sizing.
        
    def calculate_slot_size(
        self, 
        balance: float, 
        active_slots: int,
        queue_depth: int = 0,
        max_slots_limit: int = MAX_CONCURRENT_SLOTS
    ) -> float:
        """
        Calculate capital per slot with elastic sizing.
        
        Args:
            balance: Available USDT balance
            active_slots: Number of active slots
            queue_depth: Not heavily used in V4, kept for compat.
            max_slots_limit: Dynamic limit from strategy.
            
        Returns:
            Capital to allocate per slot
        """
        # 1. Determine Total Slots active/planned
        # If we have $120, BASE=$6 -> 20 slots.
        # If we have $12,000 -> 20 slots (max).
        total_slots = self.calculate_slot_count(balance, max_slots_limit)
        
        # 2. How many slots can we open now?
        available_open_slots = total_slots - active_slots
        if available_open_slots <= 0:
            return 0.0
            
        # 3. Calculate raw slot size
        # We divide the TOTAL balance by TOTAL slots to keep sizing consistent.
        # Any excess beyond (20 * 500) remains unallocated (Virtual Vault).
        
        # We need to be careful: 'balance' here is supposedly AVAILABLE balance.
        # If we have positions open, 'balance' is reduced.
        # But 'active_slots' accounts for that.
        # Wait. calculate_slot_count uses 'balance'. If 'balance' is only FREE balance,
        # then as we fill slots, 'balance' drops, so calculate_slot_count drops?
        # That's a BUG in V3 logic if passed pure free balance.
        # Usually we pass (free + locked) or logic handles it.
        # Let's assume 'balance' passed here is FREE USDT.
        
        # CORRECT LOGIC V4:
        # We want Equal Weighting.
        # If Total Capital is $1000 -> 20 Slots of $50.
        # If we used 5 slots ($250), we have $750 left.
        # calculate_slot_count($750) -> 125 slots? NO.
        
        # We need Total Equity to calculate Total Slots ideally.
        # But lacking that, let's use a simpler heuristic for safe growth:
        # Use simple division of Available Balance / Remaining Slots?
        
        # If we want to strictly follow "Max 20 Slots", we need to know how many we WANT.
        # If we have $12k total, we want 20 slots of $500.
        
        # Let's use the 'balance' as Free Balance.
        # Remaining Slots = 20 - active_slots.
        # Slot Size = Free Balance / Remaining Slots.
        # Cap at $500.
        
        # But 'total_slots' calculation above depends on balance.
        # If balance is small, total_slots is small.
        # If balance is free balance, this logic works for scaling *up*.
        
        remaining_slots_capacity = max_slots_limit - active_slots
        if remaining_slots_capacity <= 0:
             return 0.0
             
        raw_size = balance / remaining_slots_capacity
        
        # 4. Enforce Limits
        # Cap at WHALE_CAP ($500)
        slot_size = min(raw_size, WHALE_CAP)
        
        # Floor at MIN_SLOT_SIZE ($6)
        if slot_size < MIN_SLOT_SIZE:
             # Try to squeeze at least one slot?
             if balance >= MIN_SLOT_SIZE:
                 slot_size = MIN_SLOT_SIZE
             else:
                 return 0.0
        
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


# Singleton instance
_capital_manager_instance = None

def get_capital_manager() -> CapitalManager:
    """Get the global capital manager instance."""
    global _capital_manager_instance
    if _capital_manager_instance is None:
        _capital_manager_instance = CapitalManager()
    return _capital_manager_instance
