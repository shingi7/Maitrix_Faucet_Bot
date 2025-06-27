#!/usr/bin/env python3
"""
Ethereum Wallet Generator - SQLite-based for high volume wallet generation
Optimized for memory efficiency and incremental generation
"""

import sqlite3
import argparse
import os
from eth_account import Account
from typing import Generator, Tuple
import time

class WalletGenerator:
    def __init__(self, db_path: str = "wallets.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with optimized settings"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")  # Better performance for concurrent access
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
        conn.execute("PRAGMA cache_size=10000")  # Increase cache size
        
        # Create table with index on address for uniqueness
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                private_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster lookups
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_address ON wallets(address)")
        conn.commit()
        conn.close()
    
    def get_wallet_count(self) -> int:
        """Get current number of wallets in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM wallets")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def generate_wallet_batch(self, batch_size: int) -> Generator[Tuple[str, str], None, None]:
        """Generate wallets in batches to avoid memory issues"""
        for _ in range(batch_size):
            account = Account.create()
            yield (account.address, account.key.hex())
    
    def insert_wallets_batch(self, wallets_data: list, conn: sqlite3.Connection) -> int:
        """Insert batch of wallets with conflict handling"""
        try:
            cursor = conn.executemany(
                "INSERT OR IGNORE INTO wallets (address, private_key) VALUES (?, ?)",
                wallets_data
            )
            return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Database error during batch insert: {e}")
            return 0
    
    def generate_wallets(self, count: int, batch_size: int = 1000):
        """Generate specified number of wallets in batches"""
        print(f"🚀 Starting generation of {count:,} wallets...")
        
        initial_count = self.get_wallet_count()
        print(f"📊 Current wallets in database: {initial_count:,}")
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN TRANSACTION")
        
        total_inserted = 0
        processed = 0
        
        try:
            # Process in batches to avoid memory issues
            remaining = count
            
            while remaining > 0:
                current_batch_size = min(batch_size, remaining)
                
                # Generate batch of wallets
                wallet_batch = list(self.generate_wallet_batch(current_batch_size))
                
                # Insert batch into database
                inserted = self.insert_wallets_batch(wallet_batch, conn)
                total_inserted += inserted
                processed += current_batch_size
                remaining -= current_batch_size
                
                # Commit every few batches to avoid long transactions
                if processed % (batch_size * 5) == 0:
                    conn.commit()
                    conn.execute("BEGIN TRANSACTION")
                
                # Progress update
                if processed % batch_size == 0:
                    progress = (processed / count) * 100
                    print(f"⏳ Progress: {processed:,}/{count:,} ({progress:.1f}%) - "
                          f"Inserted: {total_inserted:,} new wallets")
            
            # Final commit
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error during wallet generation: {e}")
            raise
        finally:
            conn.close()
        
        final_count = self.get_wallet_count()
        duplicates_skipped = processed - total_inserted
        
        print(f"\n✅ Wallet generation completed!")
        print(f"📈 Total wallets in database: {final_count:,}")
        print(f"🆕 New wallets added: {total_inserted:,}")
        if duplicates_skipped > 0:
            print(f"⚠️  Duplicate addresses skipped: {duplicates_skipped:,}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate Ethereum wallets and store in SQLite database"
    )
    parser.add_argument(
        "--count", 
        type=int, 
        default=50000, 
        help="Number of wallets to generate (default: 50,000)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=1000, 
        help="Batch size for database operations (default: 1,000)"
    )
    parser.add_argument(
        "--db-path", 
        type=str, 
        default="wallets.db", 
        help="Path to SQLite database file (default: wallets.db)"
    )
    
    args = parser.parse_args()
    
    if args.count <= 0:
        print("❌ Count must be a positive integer")
        return
    
    if args.batch_size <= 0:
        print("❌ Batch size must be a positive integer")
        return
    
    start_time = time.time()
    
    try:
        generator = WalletGenerator(args.db_path)
        generator.generate_wallets(args.count, args.batch_size)
        
        elapsed = time.time() - start_time
        print(f"⏱️  Total time: {elapsed:.2f} seconds")
        print(f"🚀 Generation rate: {args.count/elapsed:.0f} wallets/second")
        
    except KeyboardInterrupt:
        print("\n⚠️  Generation interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()