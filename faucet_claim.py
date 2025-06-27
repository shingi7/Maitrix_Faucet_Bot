#!/usr/bin/env python3
"""
Faucet Claim System - Batch processing of wallet claims
Connects to Arbitrum Sepolia network and processes claims efficiently
"""

import sqlite3
import json
import time
import logging
from datetime import datetime
from typing import Generator, Tuple, List, Optional
from dataclasses import dataclass
from web3 import Web3
from eth_account import Account
from web3.exceptions import TransactionNotFound, TimeExhausted
import argparse
import os

# Contract address for the faucet
CONTRACT_ADDRESS = "0x1bA1526CF49Eb9ECcA86bDC015C4263300E21656"

@dataclass
class ClaimResult:
    address: str
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    gas_used: Optional[int] = None

class FaucetClaimer:
    def __init__(
        self, 
        db_path: str = "wallets.db",
        rpc_url: str = "https://sepolia-rollup.arbitrum.io/rpc",
        abi_path: str = "abi.json",
        contract_address: str = "",
        gas_limit: int = 100000,
        gas_price_gwei: float = 0.1
    ):
        self.db_path = db_path
        self.rpc_url = rpc_url
        self.abi_path = abi_path
        self.contract_address = contract_address
        self.gas_limit = gas_limit
        self.gas_price_gwei = gas_price_gwei
        
        # Initialize Web3 connection
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Setup logging
        self.setup_logging()
        
        # Load contract ABI and initialize contract
        self.contract = None
        self.load_contract()
        
        # Chain ID for Arbitrum Sepolia
        self.chain_id = 421614
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_filename = f"faucet_claims_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Create file handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        
        # Create console handler with proper encoding for Windows
        console_handler = logging.StreamHandler()
        
        # Set formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, console_handler]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Faucet Claimer initialized - Log file: {log_filename}")
        
    def load_contract(self):
        """Load contract ABI and initialize contract instance"""
        try:
            if not os.path.exists(self.abi_path):
                self.logger.warning(f"⚠️  ABI file not found: {self.abi_path}")
                return
                
            with open(self.abi_path, 'r') as f:
                abi = json.load(f)
            
            if self.contract_address:
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=abi
                )
                self.logger.info(f"✅ Contract loaded: {self.contract_address}")
            else:
                self.logger.warning("⚠️  Contract address not provided")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to load contract: {e}")
    
    def check_connection(self) -> bool:
        """Check Web3 connection and network"""
        try:
            if not self.w3.is_connected():
                self.logger.error("❌ Failed to connect to RPC endpoint")
                return False
            
            chain_id = self.w3.eth.chain_id
            latest_block = self.w3.eth.block_number
            
            self.logger.info(f"✅ Connected to network - Chain ID: {chain_id}, Latest block: {latest_block}")
            
            if chain_id != self.chain_id:
                self.logger.warning(f"⚠️  Expected chain ID {self.chain_id}, got {chain_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Connection check failed: {e}")
            return False
    
    def get_wallet_batches(self, batch_size: int = 500) -> Generator[List[Tuple[int, str, str]], None, None]:
        """Get wallets from database in batches"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT id, address, private_key FROM wallets ORDER BY id")
            
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                yield batch
                
        except sqlite3.Error as e:
            self.logger.error(f"❌ Database error: {e}")
        finally:
            conn.close()
    
    def get_nonce(self, address: str) -> int:
        """Get transaction nonce for address"""
        try:
            return self.w3.eth.get_transaction_count(address)
        except Exception as e:
            self.logger.error(f"❌ Failed to get nonce for {address}: {e}")
            return 0
    
    def build_claim_transaction(self, wallet_address: str, nonce: int) -> dict:
        """Build faucet claim transaction"""
        if not self.contract:
            raise Exception("Contract not initialized")
        
        # Build transaction data for requestTokens() function
        transaction = self.contract.functions.requestTokens().build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gas': self.gas_limit,
            'gasPrice': self.w3.to_wei(self.gas_price_gwei, 'gwei'),
            'chainId': self.chain_id
        })
        
        return transaction
    
    def sign_and_send_transaction(self, transaction: dict, private_key: str) -> ClaimResult:
        """Sign and send transaction"""
        try:
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            self.logger.info(f"📤 Transaction sent: {tx_hash_hex}")
            
            # Wait for transaction receipt (with timeout)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
                
                if receipt.status == 1:
                    return ClaimResult(
                        address=transaction['from'],
                        success=True,
                        tx_hash=tx_hash_hex,
                        gas_used=receipt.gasUsed
                    )
                else:
                    return ClaimResult(
                        address=transaction['from'],
                        success=False,
                        tx_hash=tx_hash_hex,
                        error="Transaction failed (status: 0)"
                    )
                    
            except TimeExhausted:
                # Transaction was sent but we timed out waiting for receipt
                return ClaimResult(
                    address=transaction['from'],
                    success=True,  # Assume success since transaction was sent
                    tx_hash=tx_hash_hex,
                    error="Receipt timeout (transaction may still succeed)"
                )
                
        except Exception as e:
            return ClaimResult(
                address=transaction['from'],
                success=False,
                error=str(e)
            )
    
    def process_wallet_claim(self, wallet_id: int, address: str, private_key: str) -> ClaimResult:
        """Process faucet claim for a single wallet"""
        try:
            # Get nonce
            nonce = self.get_nonce(address)
            
            # Build transaction
            transaction = self.build_claim_transaction(address, nonce)
            
            # Sign and send
            result = self.sign_and_send_transaction(transaction, private_key)
            
            # Log result
            if result.success:
                self.logger.info(f"✅ Claim successful for {address} - TX: {result.tx_hash}")
            else:
                self.logger.error(f"❌ Claim failed for {address} - Error: {result.error}")
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error processing {address}: {e}"
            self.logger.error(f"❌ {error_msg}")
            return ClaimResult(address=address, success=False, error=error_msg)
    
    def process_claims(
        self, 
        batch_size: int = 500, 
        delay_between_claims: float = 2.0,
        max_wallets: Optional[int] = None
    ):
        """Process faucet claims for all wallets"""
        if not self.check_connection():
            return
        
        if not self.contract:
            self.logger.error("❌ Contract not initialized - cannot process claims")
            return
        
        self.logger.info(f"🚀 Starting faucet claims - Batch size: {batch_size}, Delay: {delay_between_claims}s")
        
        total_processed = 0
        total_successful = 0
        total_failed = 0
        
        start_time = time.time()
        
        try:
            for batch in self.get_wallet_batches(batch_size):
                batch_start_time = time.time()
                batch_successful = 0
                batch_failed = 0
                
                self.logger.info(f"📦 Processing batch of {len(batch)} wallets...")
                
                for wallet_id, address, private_key in batch:
                    if max_wallets and total_processed >= max_wallets:
                        self.logger.info(f"🛑 Reached maximum wallet limit: {max_wallets}")
                        return
                    
                    # Process claim
                    result = self.process_wallet_claim(wallet_id, address, private_key)
                    
                    if result.success:
                        batch_successful += 1
                        total_successful += 1
                    else:
                        batch_failed += 1
                        total_failed += 1
                    
                    total_processed += 1
                    
                    # Delay between transactions to avoid rate limiting
                    if delay_between_claims > 0:
                        time.sleep(delay_between_claims)
                
                # Batch summary
                batch_time = time.time() - batch_start_time
                self.logger.info(
                    f"📊 Batch completed - Success: {batch_successful}, "
                    f"Failed: {batch_failed}, Time: {batch_time:.2f}s"
                )
                
                # Overall progress
                elapsed = time.time() - start_time
                rate = total_processed / elapsed if elapsed > 0 else 0
                self.logger.info(
                    f"📈 Overall progress - Processed: {total_processed}, "
                    f"Success rate: {(total_successful/total_processed)*100:.1f}%, "
                    f"Rate: {rate:.2f} claims/sec"
                )
                
        except KeyboardInterrupt:
            self.logger.info("⚠️  Processing interrupted by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal error during processing: {e}")
        finally:
            # Final summary
            total_time = time.time() - start_time
            self.logger.info(f"\n🏁 Faucet claiming completed!")
            self.logger.info(f"📊 Total processed: {total_processed}")
            self.logger.info(f"✅ Successful claims: {total_successful}")
            self.logger.info(f"❌ Failed claims: {total_failed}")
            self.logger.info(f"📈 Success rate: {(total_successful/total_processed)*100:.1f}%")
            self.logger.info(f"⏱️  Total time: {total_time:.2f} seconds")
            self.logger.info(f"🚀 Average rate: {total_processed/total_time:.2f} claims/second")

def main():
    parser = argparse.ArgumentParser(description="Automated Faucet Claiming System")
    parser.add_argument("--db-path", default="wallets.db", help="Path to wallets database")
    parser.add_argument("--rpc-url", default="https://sepolia-rollup.arbitrum.io/rpc", help="RPC endpoint URL")
    parser.add_argument("--abi-path", default="abi.json", help="Path to contract ABI file")
    parser.add_argument("--contract-address", default=CONTRACT_ADDRESS, help="Faucet contract address")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between claims (seconds)")
    parser.add_argument("--gas-limit", type=int, default=100000, help="Gas limit for transactions")
    parser.add_argument("--gas-price", type=float, default=0.1, help="Gas price in Gwei")
    parser.add_argument("--max-wallets", type=int, help="Maximum number of wallets to process")
    
    args = parser.parse_args()
    
    claimer = FaucetClaimer(
        db_path=args.db_path,
        rpc_url=args.rpc_url,
        abi_path=args.abi_path,
        contract_address=args.contract_address,
        gas_limit=args.gas_limit,
        gas_price_gwei=args.gas_price
    )
    
    claimer.process_claims(
        batch_size=args.batch_size,
        delay_between_claims=args.delay,
        max_wallets=args.max_wallets
    )

if __name__ == "__main__":
    main() 