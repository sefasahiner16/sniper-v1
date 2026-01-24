"""
Sniper V2 - Trade Logger
=========================
Logs all trades to JSON for performance analysis.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import LOG_FILE


def _ensure_log_file():
    """Ensure the log file exists."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            json.dump([], f)


def load_trades() -> List[Dict]:
    """Load all trades from the log file."""
    _ensure_log_file()
    try:
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_trades(trades: List[Dict]) -> None:
    """Save trades to the log file."""
    _ensure_log_file()
    with open(LOG_FILE, 'w') as f:
        json.dump(trades, f, indent=2, default=str)


def log_trade_entry(symbol: str, entry_price: float, quantity: float,
                    take_profit: float, stop_loss: float, balance_before: float) -> str:
    """
    Log a new trade entry.
    
    Returns:
        str: Trade ID for tracking
    """
    trades = load_trades()
    
    trade_id = f"{symbol.replace('/', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    trade = {
        "id": trade_id,
        "symbol": symbol,
        "status": "OPEN",
        "entry_time": datetime.now().isoformat(),
        "entry_price": entry_price,
        "quantity": quantity,
        "position_value": entry_price * quantity,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "balance_before": balance_before,
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "pnl_pct": None,
        "pnl_usd": None,
        "balance_after": None
    }
    
    trades.append(trade)
    save_trades(trades)
    
    return trade_id


def log_trade_exit(trade_id: str, exit_price: float, exit_reason: str,
                   balance_after: float) -> Optional[Dict]:
    """
    Log trade exit and calculate P&L.
    
    Returns:
        Dict: The completed trade record
    """
    trades = load_trades()
    
    for trade in trades:
        if trade["id"] == trade_id:
            entry_price = trade["entry_price"]
            quantity = trade["quantity"]
            
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            pnl_usd = (exit_price - entry_price) * quantity
            
            trade["status"] = "CLOSED"
            trade["exit_time"] = datetime.now().isoformat()
            trade["exit_price"] = exit_price
            trade["exit_reason"] = exit_reason
            trade["pnl_pct"] = round(pnl_pct, 4)
            trade["pnl_usd"] = round(pnl_usd, 6)
            trade["balance_after"] = balance_after
            
            save_trades(trades)
            return trade
    
    return None


def get_open_trade() -> Optional[Dict]:
    """Get the currently open trade (if any)."""
    trades = load_trades()
    for trade in reversed(trades):
        if trade["status"] == "OPEN":
            return trade
    return None


def get_performance_stats() -> Dict:
    """Calculate overall performance statistics."""
    trades = load_trades()
    closed_trades = [t for t in trades if t["status"] == "CLOSED"]
    
    if not closed_trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl_pct": 0,
            "total_pnl_usd": 0,
            "avg_win_pct": 0,
            "avg_loss_pct": 0,
            "best_trade_pct": 0,
            "worst_trade_pct": 0,
            "consecutive_losses": 0
        }
    
    wins = [t for t in closed_trades if t["pnl_pct"] >= 0]
    losses = [t for t in closed_trades if t["pnl_pct"] < 0]
    
    # Calculate consecutive losses (for circuit breaker)
    consecutive_losses = 0
    for trade in reversed(closed_trades):
        if trade["pnl_pct"] < 0:
            consecutive_losses += 1
        else:
            break
    
    return {
        "total_trades": len(closed_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed_trades) * 100, 2) if closed_trades else 0,
        "total_pnl_pct": round(sum(t["pnl_pct"] for t in closed_trades), 2),
        "total_pnl_usd": round(sum(t["pnl_usd"] for t in closed_trades), 4),
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
        "best_trade_pct": max(t["pnl_pct"] for t in closed_trades) if closed_trades else 0,
        "worst_trade_pct": min(t["pnl_pct"] for t in closed_trades) if closed_trades else 0,
        "consecutive_losses": consecutive_losses
    }


def print_performance_summary() -> None:
    """Print a formatted performance summary to console."""
    stats = get_performance_stats()
    
    print("\n" + "=" * 50)
    print("📊 SNIPER V3 - PERFORMANCE SUMMARY")
    print("=" * 50)
    print(f"Total Trades:     {stats['total_trades']}")
    print(f"Wins / Losses:    {stats['wins']} / {stats['losses']}")
    print(f"Win Rate:         {stats['win_rate']:.1f}%")
    print("-" * 50)
    print(f"Total P&L:        {stats['total_pnl_pct']:+.2f}% (${stats['total_pnl_usd']:+.4f})")
    print(f"Avg Win:          {stats['avg_win_pct']:+.2f}%")
    print(f"Avg Loss:         {stats['avg_loss_pct']:.2f}%")
    print(f"Best Trade:       {stats['best_trade_pct']:+.2f}%")
    print(f"Worst Trade:      {stats['worst_trade_pct']:.2f}%")
    print("=" * 50 + "\n")
