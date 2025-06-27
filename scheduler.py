#!/usr/bin/env python3
"""
Faucet Claim Scheduler - Automated daily execution of faucet claims
Runs faucet claiming process every 24 hours with configurable parameters
"""

import time
import subprocess
import logging
import argparse
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
import json

# Contract address for the faucet
CONTRACT_ADDRESS = "0x1bA1526CF49Eb9ECcA86bDC015C4263300E21656"

class FaucetScheduler:
    def __init__(
        self,
        contract_address: str,
        db_path: str = "wallets.db",
        rpc_url: str = "https://sepolia-rollup.arbitrum.io/rpc",
        abi_path: str = "abi.json",
        batch_size: int = 500,
        delay_between_claims: float = 2.0,
        gas_limit: int = 100000,
        gas_price_gwei: float = 0.1,
        max_wallets: Optional[int] = None,
        schedule_interval_hours: int = 24
    ):
        self.contract_address = contract_address
        self.db_path = db_path
        self.rpc_url = rpc_url
        self.abi_path = abi_path
        self.batch_size = batch_size
        self.delay_between_claims = delay_between_claims
        self.gas_limit = gas_limit
        self.gas_price_gwei = gas_price_gwei
        self.max_wallets = max_wallets
        self.schedule_interval_hours = schedule_interval_hours
        
        # Control flags
        self.running = True
        self.force_run = False
        
        # Setup logging
        self.setup_logging()
        
        # Setup signal handlers for graceful shutdown
        self.setup_signal_handlers()
        
        # Track runs
        self.run_count = 0
        self.last_run_time = None
        self.next_run_time = None
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_filename = f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🕐 Faucet Scheduler initialized - Log file: {log_filename}")
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"🛑 Received signal {signum} - initiating graceful shutdown...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    def calculate_next_run_time(self) -> datetime:
        """Calculate the next scheduled run time"""
        now = datetime.now()
        if self.last_run_time is None:
            # First run - schedule immediately or at next interval
            return now
        else:
            # Schedule next run based on interval
            return self.last_run_time + timedelta(hours=self.schedule_interval_hours)
    
    def should_run_now(self) -> bool:
        """Check if it's time to run the faucet claiming process"""
        if self.force_run:
            self.force_run = False
            return True
            
        if self.next_run_time is None:
            return True
            
        return datetime.now() >= self.next_run_time
    
    def build_faucet_command(self) -> list:
        """Build the command to execute faucet claiming"""
        cmd = [
            sys.executable, "faucet_claim.py",
            "--contract-address", self.contract_address,
            "--db-path", self.db_path,
            "--rpc-url", self.rpc_url,
            "--abi-path", self.abi_path,
            "--batch-size", str(self.batch_size),
            "--delay", str(self.delay_between_claims),
            "--gas-limit", str(self.gas_limit),
            "--gas-price", str(self.gas_price_gwei)
        ]
        
        if self.max_wallets:
            cmd.extend(["--max-wallets", str(self.max_wallets)])
        
        return cmd
    
    def run_faucet_claiming(self) -> bool:
        """Execute the faucet claiming process"""
        self.logger.info("🚀 Starting faucet claiming process...")
        
        try:
            # Check if required files exist
            if not os.path.exists("faucet_claim.py"):
                self.logger.error("❌ faucet_claim.py not found!")
                return False
            
            if not os.path.exists(self.db_path):
                self.logger.error(f"❌ Database file not found: {self.db_path}")
                return False
            
            if not os.path.exists(self.abi_path):
                self.logger.error(f"❌ ABI file not found: {self.abi_path}")
                return False
            
            # Build and execute command
            cmd = self.build_faucet_command()
            self.logger.info(f"🔧 Executing command: {' '.join(cmd)}")
            
            start_time = time.time()
            
            # Run the faucet claiming process
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            execution_time = time.time() - start_time
            
            # Log results
            if process.returncode == 0:
                self.logger.info(f"✅ Faucet claiming completed successfully in {execution_time:.2f} seconds")
                self.logger.info("📄 Process output:")
                for line in process.stdout.split('\n'):
                    if line.strip():
                        self.logger.info(f"   {line}")
                return True
            else:
                self.logger.error(f"❌ Faucet claiming failed with return code: {process.returncode}")
                self.logger.error("📄 Error output:")
                for line in process.stderr.split('\n'):
                    if line.strip():
                        self.logger.error(f"   {line}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ Faucet claiming process timed out (1 hour limit)")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error executing faucet claiming: {e}")
            return False
    
    def save_run_stats(self, success: bool):
        """Save run statistics to file"""
        stats = {
            "run_count": self.run_count,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "last_run_success": success,
            "schedule_interval_hours": self.schedule_interval_hours
        }
        
        try:
            with open("scheduler_stats.json", "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            self.logger.error(f"❌ Failed to save run stats: {e}")
    
    def load_run_stats(self):
        """Load run statistics from file"""
        try:
            if os.path.exists("scheduler_stats.json"):
                with open("scheduler_stats.json", "r") as f:
                    stats = json.load(f)
                
                self.run_count = stats.get("run_count", 0)
                if stats.get("last_run_time"):
                    self.last_run_time = datetime.fromisoformat(stats["last_run_time"])
                if stats.get("next_run_time"):
                    self.next_run_time = datetime.fromisoformat(stats["next_run_time"])
                
                self.logger.info(f"📊 Loaded previous stats - Run count: {self.run_count}")
                if self.last_run_time:
                    self.logger.info(f"📅 Last run: {self.last_run_time}")
                if self.next_run_time:
                    self.logger.info(f"⏰ Next scheduled run: {self.next_run_time}")
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to load run stats: {e}")
    
    def wait_with_progress(self, seconds: float):
        """Wait with progress updates"""
        if seconds <= 0:
            return
            
        sleep_interval = min(300, seconds / 10)  # Update every 5 minutes or 10% of wait time
        remaining = seconds
        
        while remaining > 0 and self.running:
            if remaining <= sleep_interval:
                time.sleep(remaining)
                break
            
            time.sleep(sleep_interval)
            remaining -= sleep_interval
            
            # Progress update
            hours_remaining = remaining / 3600
            if hours_remaining >= 1:
                self.logger.info(f"⏳ Next run in {hours_remaining:.1f} hours...")
            else:
                minutes_remaining = remaining / 60
                self.logger.info(f"⏳ Next run in {minutes_remaining:.1f} minutes...")
    
    def run_scheduler(self):
        """Main scheduler loop"""
        self.logger.info("🕐 Starting Faucet Scheduler...")
        self.logger.info(f"📅 Schedule interval: {self.schedule_interval_hours} hours")
        self.logger.info(f"🎯 Contract address: {self.contract_address}")
        self.logger.info(f"📊 Batch size: {self.batch_size}, Delay: {self.delay_between_claims}s")
        
        # Load previous run stats
        self.load_run_stats()
        
        # Calculate initial next run time
        self.next_run_time = self.calculate_next_run_time()
        
        try:
            while self.running:
                if self.should_run_now():
                    self.run_count += 1
                    self.last_run_time = datetime.now()
                    
                    self.logger.info(f"🚀 Starting run #{self.run_count} at {self.last_run_time}")
                    
                    # Execute faucet claiming
                    success = self.run_faucet_claiming()
                    
                    # Calculate next run time
                    self.next_run_time = self.calculate_next_run_time()
                    
                    # Save stats
                    self.save_run_stats(success)
                    
                    if success:
                        self.logger.info(f"✅ Run #{self.run_count} completed successfully")
                    else:
                        self.logger.error(f"❌ Run #{self.run_count} failed")
                    
                    self.logger.info(f"⏰ Next run scheduled for: {self.next_run_time}")
                
                # Calculate wait time until next run
                now = datetime.now()
                if self.next_run_time > now:
                    wait_seconds = (self.next_run_time - now).total_seconds()
                    self.logger.info(f"😴 Waiting {wait_seconds/3600:.1f} hours until next run...")
                    self.wait_with_progress(wait_seconds)
                else:
                    # Small delay to prevent busy waiting
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            self.logger.info("⚠️  Scheduler interrupted by user")
        except Exception as e:
            self.logger.error(f"❌ Scheduler error: {e}")
        finally:
            self.logger.info("🛑 Faucet Scheduler shutting down...")

def main():
    parser = argparse.ArgumentParser(description="Automated Faucet Claiming Scheduler")
    parser.add_argument("--contract-address", default=CONTRACT_ADDRESS, help="Faucet contract address")
    parser.add_argument("--db-path", default="wallets.db", help="Path to wallets database")
    parser.add_argument("--rpc-url", default="https://sepolia-rollup.arbitrum.io/rpc", help="RPC endpoint URL")
    parser.add_argument("--abi-path", default="abi.json", help="Path to contract ABI file")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between claims (seconds)")
    parser.add_argument("--gas-limit", type=int, default=100000, help="Gas limit for transactions")
    parser.add_argument("--gas-price", type=float, default=0.1, help="Gas price in Gwei")
    parser.add_argument("--max-wallets", type=int, help="Maximum number of wallets to process per run")
    parser.add_argument("--interval-hours", type=int, default=24, help="Hours between runs (default: 24)")
    
    args = parser.parse_args()
    
    scheduler = FaucetScheduler(
        contract_address=args.contract_address,
        db_path=args.db_path,
        rpc_url=args.rpc_url,
        abi_path=args.abi_path,
        batch_size=args.batch_size,
        delay_between_claims=args.delay,
        gas_limit=args.gas_limit,
        gas_price_gwei=args.gas_price,
        max_wallets=args.max_wallets,
        schedule_interval_hours=args.interval_hours
    )
    
    scheduler.run_scheduler()

if __name__ == "__main__":
    main() 