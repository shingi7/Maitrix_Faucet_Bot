#!/usr/bin/env python3
"""
Simple Faucet Claim Test - Testing basic functionality
"""

import sqlite3
import json
import time
from web3 import Web3
from eth_account import Account

# Contract address for the faucet
CONTRACT_ADDRESS = "0x1bA1526CF49Eb9ECcA86bDC015C4263300E21656"

def test_faucet_claim():
    """Test faucet claiming with one wallet"""
    
    # Setup Web3 connection
    rpc_url = "https://sepolia-rollup.arbitrum.io/rpc"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    print("Testing connection...")
    if not w3.is_connected():
        print("ERROR: Failed to connect to RPC endpoint")
        return False
    
    print("Connected successfully!")
    print(f"Chain ID: {w3.eth.chain_id}")
    print(f"Latest block: {w3.eth.block_number}")
    
    # Load contract ABI
    with open("abi.json", "r") as f:
        abi = json.load(f)
    
    # Create contract instance
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=abi
    )
    
    print(f"Contract loaded: {CONTRACT_ADDRESS}")
    
    # Get one wallet from database
    conn = sqlite3.connect("wallets.db")
    cursor = conn.execute("SELECT address, private_key FROM wallets LIMIT 1")
    wallet = cursor.fetchone()
    conn.close()
    
    if not wallet:
        print("ERROR: No wallets found in database")
        return False
    
    address, private_key = wallet
    print(f"Testing with wallet: {address}")
    
    # Get nonce
    nonce = w3.eth.get_transaction_count(address)
    print(f"Wallet nonce: {nonce}")
    
    # Build transaction
    try:
        transaction = contract.functions.requestTokens().build_transaction({
            'from': address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.to_wei(0.1, 'gwei'),
            'chainId': 421614  # Arbitrum Sepolia
        })
        
        print("Transaction built successfully!")
        print(f"Gas limit: {transaction['gas']}")
        print(f"Gas price: {transaction['gasPrice']}")
        
        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
        print("Transaction signed successfully!")
        
        # Send transaction
        print("Sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        
        print(f"Transaction sent! Hash: {tx_hash_hex}")
        
        # Wait for receipt
        print("Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        
        if receipt.status == 1:
            print("SUCCESS: Transaction confirmed!")
            print(f"Gas used: {receipt.gasUsed}")
            print(f"Block number: {receipt.blockNumber}")
            return True
        else:
            print("ERROR: Transaction failed")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_faucet_claim()
    if success:
        print("\nTest completed successfully! The system is ready to use.")
    else:
        print("\nTest failed. Please check the configuration and try again.") 