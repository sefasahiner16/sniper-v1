"""
Sniper - Telegram Notification Module
=====================================
Sends trade notifications to Telegram with version labels.
"""

import os
import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Get bot version from environment (v2 or v3)
def get_version_label() -> str:
    """Get the version label for messages."""
    version = os.getenv("BOT_VERSION", "v3").upper()
    return version


def send_message(text: str) -> bool:
    """
    Send a message to the configured Telegram chat.
    
    Args:
        text: Message text to send (supports Markdown)
        
    Returns:
        bool: True if message sent successfully
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM] Not configured - would send: {text[:100]}...")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Error sending message: {e}")
        return False


def notify_buy(symbol: str, price: float, take_profit: float, stop_loss: float) -> bool:
    """
    Send notification when entering a position.
    
    Args:
        symbol: Trading pair (e.g., "SUI/USDT")
        price: Entry price
        take_profit: Target price
        stop_loss: Stop loss price
    """
    version = get_version_label()
    tp_pct = ((take_profit - price) / price) * 100
    sl_pct = ((stop_loss - price) / price) * 100
    
    message = f"""
🟢 *[{version}] BUY SIGNAL EXECUTED*

📊 *Symbol:* `{symbol}`
💰 *Entry Price:* ${price:.6f}

🎯 *Take Profit:* ${take_profit:.6f} (+{tp_pct:.2f}%)
🛑 *Stop Loss:* ${stop_loss:.6f} ({sl_pct:.2f}%)

⏰ _Paper Trading Mode_
"""
    return send_message(message.strip())


def notify_sell(symbol: str, entry_price: float, exit_price: float, 
                pnl_pct: float, pnl_usd: float, reason: str, balance: float) -> bool:
    """
    Send notification when exiting a position.
    
    Args:
        symbol: Trading pair
        entry_price: Original entry price
        exit_price: Exit/sale price
        pnl_pct: Profit/Loss percentage
        pnl_usd: Profit/Loss in USD
        reason: Exit reason (TP_HIT, SL_HIT, TRAILING_STOP, TIME_EXIT)
        balance: Current balance after trade
    """
    version = get_version_label()
    emoji = "🟢" if pnl_pct >= 0 else "🔴"
    win_loss = "WIN" if pnl_pct >= 0 else "LOSS"
    
    reason_text = {
        "TP_HIT": "✅ Take Profit Hit",
        "SL_HIT": "❌ Stop Loss Hit",
        "TRAILING_STOP": "📈 Trailing Stop Triggered",
        "TIME_EXIT": "⏰ Time-Based Exit",
        "MANUAL": "👤 Manual Exit",
        "SHUTDOWN": "🛑 Bot Shutdown"
    }.get(reason, reason)
    
    message = f"""
{emoji} *[{version}] POSITION CLOSED - {win_loss}*

📊 *Symbol:* `{symbol}`
📥 *Entry:* ${entry_price:.6f}
📤 *Exit:* ${exit_price:.6f}

💵 *P&L:* {pnl_pct:+.2f}% (${pnl_usd:+.4f})
💰 *Balance:* ${balance:.2f}
📝 *Reason:* {reason_text}

⏰ _Paper Trading Mode_
"""
    return send_message(message.strip())


def notify_error(error_message: str) -> bool:
    """
    Send notification for critical errors.
    
    Args:
        error_message: Description of the error
    """
    version = get_version_label()
    message = f"""
⚠️ *[{version}] SNIPER ERROR*

{error_message}

_Please check the bot logs._
"""
    return send_message(message.strip())


def notify_circuit_breaker(consecutive_losses: int, pause_hours: int) -> bool:
    """
    Send notification when circuit breaker is triggered.
    
    Args:
        consecutive_losses: Number of consecutive losses
        pause_hours: Hours the bot will pause
    """
    version = get_version_label()
    message = f"""
🚨 *[{version}] CIRCUIT BREAKER ACTIVATED*

📉 *Consecutive Losses:* {consecutive_losses}
⏸️ *Pausing for:* {pause_hours} hours

_Bot will resume automatically._
"""
    return send_message(message.strip())


def notify_startup(balance: float, mode: str, slots: int = 1) -> bool:
    """
    Send notification when bot starts.
    
    Args:
        balance: Current balance
        mode: "PAPER" or "LIVE"
        slots: Number of trading slots
    """
    version = get_version_label()
    message = f"""
🚀 *[{version}] SNIPER STARTED*

💰 *Balance:* ${balance:.2f}
🎮 *Mode:* {mode} Trading
🎰 *Slots:* {slots}
🔍 *Status:* Scanning for opportunities...
"""
    return send_message(message.strip())
