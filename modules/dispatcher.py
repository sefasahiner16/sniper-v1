"""
Sniper V2 - The Dispatcher (Async Orchestrator)
================================================
Core V2 architecture: Producer-Consumer pattern with asyncio.Queue.

Components:
- Watchtower: Async scanner that finds opportunities (Producer)
- SniperSlot: Async worker that manages positions (Consumer)
- Dispatcher: Orchestrates everything
"""

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from config.settings import (
    SCAN_INTERVAL_SECONDS, MAX_CONCURRENT_SLOTS,
    PAPER_TRADING, INITIAL_BALANCE
)
from modules.scanner import get_scanner
from modules.analyzer import get_analyzer, AnalysisResult
from modules.executor import get_executor
from modules.capital_manager import get_capital_manager
from utils.notifier import send_message
from utils.logger import print_performance_summary


class SlotState(Enum):
    """State of a sniper slot."""
    IDLE = "IDLE"
    HUNTING = "HUNTING"  # Analyzing a candidate
    IN_POSITION = "IN_POSITION"
    EXITING = "EXITING"


@dataclass
class Opportunity:
    """An opportunity found by the Watchtower."""
    symbol: str
    ticker_data: Dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0  # Priority score


class Watchtower:
    """
    The Watchtower (Producer): Continuously scans for opportunities.
    
    Pushes opportunities to the queue without blocking on trade execution.
    """
    
    def __init__(self, queue: asyncio.Queue, scanner=None, analyzer=None):
        self.queue = queue
        self.scanner = scanner or get_scanner()
        self.analyzer = analyzer or get_analyzer()
        self.capital_manager = get_capital_manager()
        self.running = False
    
    async def scan_once(self) -> List[Opportunity]:
        """
        Perform a single scan cycle.
        
        Returns:
            List of opportunities found
        """
        opportunities = []
        
        # Check dead hours
        if self.capital_manager.is_dead_hours():
            is_dead, minutes_until = self.capital_manager.get_dead_hours_status()
            print(f"[WATCHTOWER] 🌙 Dead hours. Sleeping for {minutes_until} minutes...")
            return []
        
        print(f"\n[WATCHTOWER] 🔭 Scanning for opportunities...")
        
        # Generate watchlist
        watchlist = self.scanner.generate_watchlist()
        
        if not watchlist:
            print("[WATCHTOWER] No candidates found")
            return []
        
        print(f"[WATCHTOWER] Found {len(watchlist)} candidates")
        
        # Quick pre-filter and create opportunities
        for candidate in watchlist:
            opp = Opportunity(
                symbol=candidate['symbol'],
                ticker_data=candidate,
                score=abs(candidate.get('change_24h', 0))  # Bigger dips = higher priority
            )
            opportunities.append(opp)
        
        return opportunities
    
    async def scan_loop(self):
        """Main scanning loop."""
        self.running = True
        print("[WATCHTOWER] 🔭 Starting scan loop...")
        
        while self.running:
            try:
                opportunities = await self.scan_once()
                
                # Push opportunities to queue
                for opp in opportunities:
                    if not self.queue.full():
                        await self.queue.put(opp)
                        print(f"[WATCHTOWER] 📥 Queued: {opp.symbol}")
                    else:
                        print(f"[WATCHTOWER] ⚠️ Queue full, skipping {opp.symbol}")
                
                # Wait before next scan
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                
            except asyncio.CancelledError:
                print("[WATCHTOWER] Scan loop cancelled")
                break
            except Exception as e:
                print(f"[WATCHTOWER] Error in scan loop: {e}")
                await asyncio.sleep(30)  # Wait before retry
        
        self.running = False
    
    def stop(self):
        """Stop the scan loop."""
        self.running = False


class Dispatcher:
    """
    The Dispatcher: Orchestrates the entire V2 trading system.
    
    Manages:
    - Watchtower (scanning)
    - Queue of opportunities
    - Trade execution through the existing Executor
    - Vault rebalancing
    """
    
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self.watchtower = Watchtower(self.queue)
        self.executor = get_executor()
        self.analyzer = get_analyzer()
        self.capital_manager = get_capital_manager()
        self.running = False
        
        # V2: Simple single-slot mode (multi-slot ready for future)
        self.active_slots = 0
    
    async def process_opportunity(self, opportunity: Opportunity) -> bool:
        """
        Process a single opportunity from the queue.
        
        Args:
            opportunity: The opportunity to analyze and potentially trade
            
        Returns:
            True if a trade was opened
        """
        symbol = opportunity.symbol
        print(f"\n[DISPATCHER] 🎯 Processing: {symbol}")
        
        # Check if we can trade
        if not self.executor.can_trade():
            print(f"[DISPATCHER] Cannot trade right now")
            return False
        
        # Run full analysis
        result = self.analyzer.analyze(symbol, ticker_data=opportunity.ticker_data)
        
        if result.is_buy_signal:
            print(f"[DISPATCHER] ✅ BUY SIGNAL for {symbol}")
            
            # Enter position through executor
            success = self.executor.enter_position(result)
            
            if success:
                self.active_slots += 1
                return True
        else:
            print(f"[DISPATCHER] ❌ {symbol}: {result.rejection_reason}")
        
        return False
    
    async def opportunity_processor(self):
        """
        Consumer loop: Process opportunities from the queue.
        """
        print("[DISPATCHER] 🎯 Starting opportunity processor...")
        
        while self.running:
            try:
                # Wait for opportunities
                opportunity = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=10.0
                )
                
                await self.process_opportunity(opportunity)
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                # No opportunities in queue, check position
                if self.executor.current_position:
                    self.executor.monitor_position()
                continue
                
            except asyncio.CancelledError:
                print("[DISPATCHER] Processor cancelled")
                break
            except Exception as e:
                print(f"[DISPATCHER] Error processing opportunity: {e}")
    
    async def position_monitor(self):
        """
        Background task to monitor open positions.
        """
        print("[DISPATCHER] 📊 Starting position monitor...")
        
        while self.running:
            try:
                if self.executor.current_position:
                    self.executor.monitor_position()
                    
                    # Update slot count if position closed
                    if not self.executor.current_position:
                        self.active_slots = max(0, self.active_slots - 1)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[DISPATCHER] Monitor error: {e}")
                await asyncio.sleep(30)
    
    async def vault_manager(self):
        """
        Background task to manage vault rebalancing.
        """
        print("[DISPATCHER] 💰 Starting vault manager...")
        
        while self.running:
            try:
                # Check if vault should rebalance
                if self.capital_manager.should_rebalance_vault():
                    usdt_balance = self.executor.get_balance()
                    btc_balance = self.capital_manager.paper_btc_balance
                    
                    action, amount = self.capital_manager.check_vault_action(
                        usdt_balance, 
                        btc_balance
                    )
                    
                    if action != "NONE":
                        self.capital_manager.execute_vault_action(
                            action, 
                            amount, 
                            is_paper_mode=PAPER_TRADING
                        )
                
                # Check once per hour
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[DISPATCHER] Vault error: {e}")
                await asyncio.sleep(3600)
    
    async def run(self):
        """
        Main entry point: Run the dispatcher.
        """
        self.running = True
        
        print("\n" + "="*50)
        print("🚀 SNIPER V2 - DISPATCHER STARTING")
        print("="*50)
        print(f"Mode: {'PAPER TRADING' if PAPER_TRADING else '⚠️ LIVE TRADING'}")
        print(f"Balance: ${self.executor.get_balance():.2f}")
        print(f"Scan Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
        print("="*50 + "\n")
        
        # Send startup notification
        self.executor.startup()
        
        try:
            # Create tasks
            tasks = [
                asyncio.create_task(self.watchtower.scan_loop(), name="watchtower"),
                asyncio.create_task(self.opportunity_processor(), name="processor"),
                asyncio.create_task(self.position_monitor(), name="monitor"),
                asyncio.create_task(self.vault_manager(), name="vault"),
            ]
            
            # Wait for all tasks (or until cancelled)
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            print("\n[DISPATCHER] Shutting down...")
        finally:
            self.running = False
            self.watchtower.stop()
            
            # Close any open positions
            if self.executor.current_position:
                print("[DISPATCHER] Closing open position...")
                self.executor.exit_position("SHUTDOWN")
            
            # Print final stats
            print_performance_summary()
            print("Goodbye! 👋")
    
    def stop(self):
        """Stop the dispatcher."""
        self.running = False
        self.watchtower.stop()


# Singleton instance
_dispatcher_instance = None

def get_dispatcher() -> Dispatcher:
    """Get the global dispatcher instance."""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = Dispatcher()
    return _dispatcher_instance
