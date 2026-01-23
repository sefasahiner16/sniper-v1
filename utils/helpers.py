"""
Sniper V1 - Helper Utilities
=============================
Common utility functions used across modules.
"""

import time
from datetime import datetime
from typing import Optional


def timestamp_to_datetime(timestamp_ms: int) -> datetime:
    """Convert millisecond timestamp to datetime."""
    return datetime.fromtimestamp(timestamp_ms / 1000)


def calculate_pnl_pct(entry_price: float, current_price: float) -> float:
    """Calculate percentage change from entry to current price."""
    if entry_price == 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100


def format_price(price: float) -> str:
    """Format price with appropriate decimal places."""
    if price >= 1:
        return f"${price:.4f}"
    elif price >= 0.001:
        return f"${price:.6f}"
    else:
        return f"${price:.8f}"


def format_pct(pct: float) -> str:
    """Format percentage with sign."""
    return f"{pct:+.2f}%"


def retry_on_exception(func, max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry a function on exception.
    
    Args:
        func: Function to wrap
        max_retries: Maximum retry attempts
        delay: Delay between retries in seconds
    """
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
        raise last_exception
    return wrapper


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


class Timer:
    """Simple timer for tracking durations."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.time()
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def elapsed_minutes(self) -> float:
        """Get elapsed time in minutes."""
        return self.elapsed_seconds() / 60
    
    def has_exceeded(self, minutes: float) -> bool:
        """Check if timer has exceeded given minutes."""
        return self.elapsed_minutes() >= minutes
