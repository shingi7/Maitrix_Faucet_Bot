#!/usr/bin/env python3
"""
Show wallet information from database
"""

import sqlite3

def show_wallets(count=5):
    """Show wallet details from database"""
    try:
        conn = sqlite3.connect("wallets.db")
        cursor = conn.execute(f"SELECT id, address, private_key FROM wallets LIMIT {count}")
        wallets = cursor.fetchall()
        conn.close()
        
        if not wallets:
            print("No wallets found in database!")
            return
        
        print(f"Found {len(wallets)} wallet(s):")
        print("=" * 80)
        
        for wallet_id, address, private_key in wallets:
            print(f"Wallet ID: {wallet_id}")
            print(f"Address:   {address}")
            print(f"Private Key: {private_key}")
            print("-" * 80)
            
    except Exception as e:
        print(f"Error: {e}")

def get_wallet_count():
    """Get total number of wallets in database"""
    try:
        conn = sqlite3.connect("wallets.db")
        cursor = conn.execute("SELECT COUNT(*) FROM wallets")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting wallet count: {e}")
        return 0

if __name__ == "__main__":
    total_wallets = get_wallet_count()
    print(f"Total wallets in database: {total_wallets:,}")
    print()
    
    if total_wallets > 0:
        show_wallets(3)  # Show first 3 wallets
        
        print("\nThe first wallet shown above was used in the test.")
        print("You can import this wallet into MetaMask or any other wallet app using the private key.")
        print("\nTo fund this wallet with Arbitrum Sepolia ETH:")
        print("1. Copy the wallet address")
        print("2. Visit an Arbitrum Sepolia faucet (like Chainlink, Alchemy, or QuickNode)")
        print("3. Request test ETH to be sent to this address")
    else:
        print("No wallets found. Run: python wallet_generator.py --count 10") 