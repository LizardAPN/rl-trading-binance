import unittest
import os
import sys
from unittest.mock import patch

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.config import TradingMode, BYBIT_CONFIG

class TestConfig(unittest.TestCase):
    """Test cases for the configuration module"""
    
    def test_trading_mode_constants(self):
        """Test that trading mode constants are correctly defined"""
        self.assertEqual(TradingMode.DEMO, "demo")
        self.assertEqual(TradingMode.PAPER, "paper")
        self.assertEqual(TradingMode.LIVE, "live")
    
    def test_bybit_config_structure(self):
        """Test that BYBIT_CONFIG has the correct structure"""
        self.assertIn("mainnet", BYBIT_CONFIG)
        self.assertIn("testnet", BYBIT_CONFIG)
        
        # Check mainnet config
        mainnet_config = BYBIT_CONFIG["mainnet"]
        self.assertIn("api_key", mainnet_config)
        self.assertIn("api_secret", mainnet_config)
        self.assertIn("base_url", mainnet_config)
        self.assertEqual(mainnet_config["base_url"], "https://api.bybit.com")
        
        # Check testnet config
        testnet_config = BYBIT_CONFIG["testnet"]
        self.assertIn("api_key", testnet_config)
        self.assertIn("api_secret", testnet_config)
        self.assertIn("base_url", testnet_config)
        self.assertEqual(testnet_config["base_url"], "https://api-testnet.bybit.com")
    
    def test_get_config_demo_mode(self):
        """Test getting config for demo mode"""
        config = TradingMode.get_config(TradingMode.DEMO)
        self.assertEqual(config, BYBIT_CONFIG["testnet"])
    
    def test_get_config_paper_mode(self):
        """Test getting config for paper mode"""
        config = TradingMode.get_config(TradingMode.PAPER)
        self.assertEqual(config, BYBIT_CONFIG["testnet"])
    
    def test_get_config_live_mode(self):
        """Test getting config for live mode"""
        config = TradingMode.get_config(TradingMode.LIVE)
        self.assertEqual(config, BYBIT_CONFIG["mainnet"])
    
    def test_get_config_invalid_mode(self):
        """Test getting config for invalid mode raises ValueError"""
        with self.assertRaises(ValueError):
            TradingMode.get_config("invalid_mode")
    
    def test_is_testnet(self):
        """Test is_testnet method"""
        self.assertTrue(TradingMode.is_testnet(TradingMode.DEMO))
        self.assertTrue(TradingMode.is_testnet(TradingMode.PAPER))
        self.assertFalse(TradingMode.is_testnet(TradingMode.LIVE))
        self.assertFalse(TradingMode.is_testnet("invalid"))
    
    def test_is_real_trading(self):
        """Test is_real_trading method"""
        self.assertFalse(TradingMode.is_real_trading(TradingMode.DEMO))
        self.assertTrue(TradingMode.is_real_trading(TradingMode.PAPER))
        self.assertTrue(TradingMode.is_real_trading(TradingMode.LIVE))
        self.assertFalse(TradingMode.is_real_trading("invalid"))

if __name__ == '__main__':
    unittest.main()
