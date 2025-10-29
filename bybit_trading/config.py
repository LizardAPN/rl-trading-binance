import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration for different environments
BYBIT_CONFIG = {
    "mainnet": {
        "api_key": os.getenv("BYBIT_MAINNET_API_KEY", "YOUR_MAINNET_API_KEY"),
        "api_secret": os.getenv("BYBIT_MAINNET_SECRET", "YOUR_MAINNET_SECRET"),
        "base_url": "https://api.bybit.com"
    },
    "testnet": {
        "api_key": os.getenv("BYBIT_TESTNET_API_KEY", "YOUR_TESTNET_API_KEY"), 
        "api_secret": os.getenv("BYBIT_TESTNET_SECRET", "YOUR_TESTNET_SECRET"),
        "base_url": "https://api-testnet.bybit.com"
    }
}

class TradingMode:
    """Trading modes for different environments"""
    DEMO = "demo"      # testnet + virtual balance
    PAPER = "paper"    # testnet + real balance (but test)
    LIVE = "live"      # mainnet + real balance
    
    @classmethod
    def get_config(cls, mode: str) -> Dict[str, Any]:
        """Get configuration based on trading mode"""
        if mode == cls.DEMO or mode == cls.PAPER:
            return BYBIT_CONFIG["testnet"]
        elif mode == cls.LIVE:
            return BYBIT_CONFIG["mainnet"]
        else:
            raise ValueError(f"Unknown trading mode: {mode}")
            
    @classmethod
    def is_testnet(cls, mode: str) -> bool:
        """Check if mode uses testnet"""
        return mode in [cls.DEMO, cls.PAPER]
        
    @classmethod
    def is_real_trading(cls, mode: str) -> bool:
        """Check if mode involves real trading"""
        return mode in [cls.PAPER, cls.LIVE]
