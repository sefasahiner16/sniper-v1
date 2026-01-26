
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
import modules.analyzer

# Mock scanner to avoid connection
modules.analyzer.get_scanner = MagicMock()

analyzer = modules.analyzer.Analyzer()

def test_scenario(name, rsi_prev, rsi_curr, expected_pass):
    print(f"\n--- Testing Scenario: {name} ---")
    print(f"RSI: {rsi_prev} -> {rsi_curr}")
    
    # Dummy DF
    df = pd.DataFrame({'close': [100] * 50}) 
    
    # We need to mock:
    # 1. analyze_technicals (returns current indicators)
    # 2. calculate_rsi (returns series for hook detection)
    
    with patch('modules.analyzer.analyze_technicals') as mock_tech:
        with patch('modules.indicators.calculate_rsi') as mock_calc_rsi:
            
            # Setup analyze_technicals return
            # We set close=100 and bb_lower=110 so "Price < BB" condition is always TRUE
            # This ensures that if it fails, it's due to RSI logic, not BB logic.
            mock_tech.return_value = {
                'rsi': rsi_curr,
                'close': 100.0,
                'bb_lower': 110.0, 
                'rsi_prev': rsi_prev,
                # Add other required keys to avoid errors if accessed
                'volume': 1000,
                'volume_ma': 500,
                'atr': 1.0,
                'bb_mid': 105.0,
                'bb_upper': 110.0
            }
            
            # Setup calculate_rsi return (Series)
            # [..., prev, curr]
            rsi_series = pd.Series([50.0] * 48 + [rsi_prev, rsi_curr])
            mock_calc_rsi.return_value = rsi_series
            
            # Run
            # We use "UNKNOWN" regime to use default thresholds
            passed, _, hook, _ = analyzer.check_layer3_technical(df, "UNKNOWN")
            
            print(f"Hook Triggered: {hook}")
            print(f"Passed: {passed}")
            
            if passed == expected_pass:
                print("✅ TEST PASSED")
            else:
                print(f"❌ TEST FAILED (Expected {expected_pass}, got {passed})")

# Case 1: Falling Knife (RSI 28 -> 25)
# In Strict Mode: Hook=False. Should FAIL.
test_scenario("Falling Knife", 28.0, 25.0, False)

# Case 2: Perfect Hook (RSI 28 -> 31)
# In Strict Mode: Hook=True. Should PASS.
test_scenario("Perfect Hook", 28.0, 31.0, True)

# Case 3: Deep Oversold But No Cross (RSI 20 -> 22)
# In Strict Mode: Hook=False. Should FAIL.
test_scenario("Deep Oversold No Cross", 20.0, 22.0, False)
