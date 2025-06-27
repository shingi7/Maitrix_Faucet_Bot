#!/usr/bin/env python3
"""
Test gasless faucet claiming
"""

import sqlite3
import json
from web3 import Web3

CONTRACT_ADDRESS = "0x1bA1526CF49Eb9ECcA86bDC015C4263300E21656"

def test_gasless_claim():
    """Test faucet claiming with zero gas price"""
    
    # Setup Web3 connection
    rpc_url = "https://sepolia-rollup.arbitrum.io/rpc"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    print("Testing gasless transaction...")
    print(f"Network gas price: {w3.eth.gas_price}")
    
    # Load contract ABI
    with open("abi.json", "r") as f:
        abi = json.load(f)
    
    # Create contract instance
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=abi
    )
    
    # Get one wallet from database
    conn = sqlite3.connect("wallets.db")
    cursor = conn.execute("SELECT address, private_key FROM wallets LIMIT 1")
    wallet = cursor.fetchone()
    conn.close()
    
    address, private_key = wallet
    print(f"Testing with wallet: {address}")
    
    # Get nonce
    nonce = w3.eth.get_transaction_count(address)
    
    # Try different gas configurations
    gas_configs = [
        {"gas": 21000, "gasPrice": 0},  # Zero gas price
        {"gas": 21000, "gasPrice": 1},  # Minimal gas price
        {"gas": 100000, "gasPrice": 0},  # Zero gas price with higher limit
        {"gas": 100000, "gasPrice": w3.eth.gas_price},  # Network gas price
    ]
    
    for i, gas_config in enumerate(gas_configs):
        print(f"\n--- Test {i+1}: Gas={gas_config['gas']}, GasPrice={gas_config['gasPrice']} ---")
        
        try:
            # Build transaction
            transaction = contract.functions.requestTokens().build_transaction({
                'from': address,
                'nonce': nonce,
                'gas': gas_config['gas'],
                'gasPrice': gas_config['gasPrice'],
                'chainId': 421614
            })
            
            print("Transaction built successfully!")
            
            # Sign transaction
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            print("Transaction signed successfully!")
            
            # Try to send transaction
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            print(f"SUCCESS! Transaction sent: {tx_hash.hex()}")
            
            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            if receipt.status == 1:
                print(f"CONFIRMED! Gas used: {receipt.gasUsed}")
                return True
            else:
                print("Transaction failed")
                
        except Exception as e:
            print(f"Error: {e}")
            
        nonce = w3.eth.get_transaction_count(address)  # Update nonce for next attempt
    
    print("\nAll gasless attempts failed. This faucet requires gas fees.")
    return False

if __name__ == "__main__":
    test_gasless_claim() 