# Sniper Bot - Version History

A data-driven cryptocurrency trading bot for MEXC. This document tracks all versions for documentation and publishing.

---

## V1.0.0 - Initial Release
**Tag:** `v1.0.0` | **Date:** 2026-01-23

### Features
- 5-layer analysis filter (BTC sentiment, order book, RSI/BB, volume, ATR targets)
- Single position trading
- Paper trading mode with $12 starting balance
- Telegram notifications
- Circuit breaker (3 losses → 4hr pause)
- Trailing stop loss

### Architecture
- Synchronous `while True` loop
- Single-threaded operation

### Expected Performance
- Win Rate: ~40-50%
- Weekly: 1.0-1.3x (theoretical 2.22x)

---

## V2.0.0 - Anti-Knife Release 🔪
**Tag:** `v2.0.0` | **Date:** 2026-01-24

### New Features
| Feature | Description |
|---------|-------------|
| **RSI Hook** | Buy only when RSI crosses BACK above threshold |
| **Dead Hours** | No trading 03:00-08:00 UTC (06:00-11:00 Turkey) |
| **Chameleon Mode** | BULL=RSI 40, BEAR=RSI 25 thresholds |
| **Zombie Filter** | Reject low-liquidity coins |
| **Ratchet Stop** | Trailing stop only moves UP |
| **Vault** | Auto-buy BTC when balance overflows |

### Architecture
- Async dispatcher (producer-consumer pattern)
- `asyncio.Queue` for opportunities
- Ready for multi-slot trading

### Expected Performance
- Win Rate: ~60-70%
- Weekly: 1.5-1.8x

### Files Changed
- `config/settings.py` - 20+ new parameters
- `modules/dispatcher.py` - NEW (async orchestrator)
- `modules/capital_manager.py` - NEW (slots, vault, dead hours)
- `modules/scanner.py` - Zombie Filter, Chameleon Mode
- `modules/analyzer.py` - RSI Hook, dynamic thresholds
- `modules/executor.py` - Ratchet trailing stop
- `main.py` - V2 async entry point

---

## V3.0.0 - Multi-Slot Release 🎰
**Tag:** `v3.0.0` | **Date:** 2026-01-24

### New Features
| Feature | Description |
|---------|-------------|
| **Multi-Slot Trading** | 3 concurrent positions simultaneously |
| **Multi-Timeframe** | Confirm RSI on 5m AND 15m charts |
| **Volume Capitulation** | Detect 5x+ volume panic selling |
| **Independent Slots** | Each slot manages its own position lifecycle |
| **No Duplicates** | Same coin can't be held in multiple slots |

### Expected Performance
- Win Rate: ~70-75%
- Trades/Week: 18-30 (3x more than V2)
- Weekly Return: 2.0-2.5x

---

## Performance Tracking

| Version | Start Date | End Date | Start $ | End $ | Multiplier | Trades | Win% |
|---------|------------|----------|---------|-------|------------|--------|------|
| V2.0.0 | 2026-01-24 | - | $12.00 | - | - | - | - |
| V3.0.0 | 2026-01-24 | - | $12.00 | - | - | - | - |

*Fill in results as they come in!*

---

## Publishing Checklist

- [x] V2 implemented and tagged
- [x] V3 implemented and tagged
- [ ] V2 runs for 1 week
- [ ] V3 runs for 1 week (parallel comparison)
- [ ] Document actual vs expected results
- [ ] Screenshot/export trade history
- [ ] Final comparison table
- [ ] Write blog post / Medium article
