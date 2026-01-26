
# Simulation of Zombie Filter logic
ZOMBIE_VOLUME_RATIO = 0.1

def estimate_market_cap(volume):
    # Logic from scanner.py
    # Assume market cap is roughly 100x daily volume
    # This means MCap = 100 * Vol
    estimated_mcap = volume * 100
    return estimated_mcap

def check_zombie_filter(volume):
    market_cap = estimate_market_cap(volume)
    
    # Logic from scanner.py
    # ratio = volume_24h / market_cap
    ratio = volume / market_cap
    
    passed = ratio >= ZOMBIE_VOLUME_RATIO
    print(f"Volume: {volume}, Est Cap: {market_cap}, Ratio: {ratio:.4f}, Passed: {passed}")

print(f"Required Ratio: {ZOMBIE_VOLUME_RATIO}")
check_zombie_filter(100000)
check_zombie_filter(500000)
