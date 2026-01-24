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

## V3.0.0 - Multi-Slot Release (Planned)
**Tag:** `v3.0.0` | **Status:** 🚧 In Development

### Planned Features
| Feature | Status | Impact |
|---------|--------|--------|
| **Multi-Slot (3 trades)** | 🚧 | 3x trade volume |
| **Multi-Timeframe** | 📋 | +10% win rate |
| **Volume Capitulation** | 📋 | +5% win rate |
| **Momentum Breakout** | 📋 | +50% opportunities |

### Expected Performance
- Win Rate: ~70-75%
- Weekly: 2.0-2.5x

---

## Performance Tracking

| Version | Start Date | End Date | Start $ | End $ | Multiplier | Trades | Win% |
|---------|------------|----------|---------|-------|------------|--------|------|
| V2.0.0 | 2026-01-24 | - | $12.00 | - | - | - | - |

*Fill in results as they come in!*

---

## Publishing Checklist

- [ ] V2 runs for 2 weeks
- [ ] Document actual vs expected results
- [ ] Screenshot/export trade history
- [ ] V3 implementation
- [ ] V3 runs for 2 weeks
- [ ] Final comparison table
- [ ] Write blog post / Medium article
