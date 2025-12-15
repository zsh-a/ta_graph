"""
Database initialization script
Creates all tables and optionally seeds initial data
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, get_session
from src.database.models import ModelType
from src.database.account_manager import get_or_create_model_account
from dotenv import load_dotenv

load_dotenv()

def main():
    print("=== Database Initialization ===\n")
    
    # Create tables
    print("1. Creating database tables...")
    init_db()
    
    # Optional: Create sample model account
    create_sample = input("\n2. Create sample model account? (y/n): ").lower()
    
    if create_sample == 'y':
        model_type_str = input("   Model type (Qwen/Deepseek/QwenVLSFT): ") or "Qwen"
        name = input("   Display name: ") or "Qwen Model"
        api_key = input("   Bitget API Key: ") or "demo_key"
        api_secret = input("   Bitget API Secret: ") or "demo_secret"
        passphrase = input("   Bitget Passphrase (optional): ") or None
        
        try:
            model_type = ModelType[model_type_str]
            
            db = get_session()
            try:
                account = get_or_create_model_account(
                    model=model_type,
                    name=name,
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase,
                    db=db
                )
                print(f"\n✓ Model account created: {account.name} (ID: {account.id})")
            finally:
                db.close()
                
        except KeyError:
            print(f"Invalid model type: {model_type_str}")
            print(f"Valid options: {[m.name for m in ModelType]}")
    
    print("\n=== Initialization Complete ===")
    print(f"\nDatabase URL: {os.getenv('DATABASE_URL', 'sqlite:///./trading.db')}")
    print("\nNext steps:")
    print("  1. Configure .env with DATABASE_URL and DEFAULT_MODEL")
    print("  2. Run the trading agent: python main.py")

if __name__ == "__main__":
    main()
