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
    
    def calculate_slot_count(self, balance: float) -> int:
        """
        Calculate number of slots based on balance.
        
        Auto-Scaling Logic: Active Slots = Total Balance / Base Trade Size
        
        Args:
            balance: Available USDT balance
            
        Returns:
            Number of slots to run
        """
        if balance < MIN_SLOT_SIZE:
            return 0
        
        # Calculate ideal slot count
        slot_count = int(balance / BASE_TRADE_SIZE)
        
        # Clamp to limits
        slot_count = max(1, min(slot_count, MAX_CONCURRENT_SLOTS))
        
        return slot_count
    
    def calculate_slot_size(
        self, 
        balance: float, 
        active_slots: int,
        queue_depth: int = 0
    ) -> float:
        """
        Calculate capital per slot with elastic sizing.
        
        Elastic Slot Sizing (Bull Mode):
        - If queue is full of opportunities but funds are tight,
          reduce capital per slot to catch more opportunities.
        
        Args:
            balance: Available USDT balance
            active_slots: Number of currently active slots
            queue_depth: Number of opportunities waiting in queue
            
        Returns:
            Capital to allocate per slot
        """
        available_slots = self.calculate_slot_count(balance) - active_slots
        
        if available_slots <= 0:
            return 0.0
        
        # Base slot size
        slot_size = balance / available_slots
        
        # Bull Mode: If queue has many opportunities, reduce slot size
        # to diversify across more trades
        if queue_depth > available_slots and queue_depth > 0:
            # Reduce slot size to allow more concurrent trades
            # but never below minimum
            elasticity_factor = available_slots / queue_depth
            slot_size = max(MIN_SLOT_SIZE, slot_size * elasticity_factor)
        
        # Enforce Whale Cap
        slot_size = min(slot_size, WHALE_CAP)
        
        # Enforce minimum
        if slot_size < MIN_SLOT_SIZE:
            return 0.0
        
        return slot_size
    
    def get_allocation(
        self, 
        balance: float, 
        active_slots: int = 0,
        queue_depth: int = 0
    ) -> CapitalAllocation:
        """
        Get full capital allocation recommendation.
        
        Args:
            balance: Available USDT balance
            active_slots: Currently active slot count
            queue_depth: Opportunities in queue
            
        Returns:
            CapitalAllocation with slot count, size, and totals
        """
        slot_count = self.calculate_slot_count(balance)
        available_slots = max(0, slot_count - active_slots)
        slot_size = self.calculate_slot_size(balance, active_slots, queue_depth)
        
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
    
    def is_dead_hours(self) -> bool:
        """
        Check if current time is within dead hours.
        
        Dead hours are when trading volume is low and fake moves occur.
        
        Returns:
            True if trading should be paused
        """
        if not DEAD_HOURS_ENABLED:
            return False
        
        current_hour = datetime.now(timezone.utc).hour
        
        # Handle wrap-around (e.g., 22:00 - 06:00)
        if DEAD_HOURS_START_UTC <= DEAD_HOURS_END_UTC:
            # Simple range: e.g., 03:00 - 08:00
            return DEAD_HOURS_START_UTC <= current_hour < DEAD_HOURS_END_UTC
        else:
            # Wrap-around range: e.g., 22:00 - 06:00
            return current_hour >= DEAD_HOURS_START_UTC or current_hour < DEAD_HOURS_END_UTC
    
    def get_dead_hours_status(self) -> Tuple[bool, Optional[int]]:
        """
        Get dead hours status with time until end.
        
        Returns:
            Tuple of (is_dead_hours, minutes_until_trading_resumes)
        """
        is_dead = self.is_dead_hours()
        
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
        - OVERFLOW: If USDT > Operational Cap * Overflow Multiplier → Buy BTC
        - CRITICAL: If USDT < Operational Cap * Critical Level → Sell BTC
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
