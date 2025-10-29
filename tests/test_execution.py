import unittest
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.execution import BybitExecution
from bybit_trading.config import TradingMode

class TestBybitExecution(unittest.TestCase):
    """Test cases for the BybitExecution class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock configuration
        self.test_config = {
            "api_key": "test_api_key",
            "api_secret": "test_api_secret",
            "base_url": "https://api-testnet.bybit.com"
        }
        
        # Patch the HTTP client to avoid actual API calls
        self.http_patch = patch('bybit_trading.execution.HTTP')
        self.mock_http_class = self.http_patch.start()
        self.mock_http_instance = MagicMock()
        self.mock_http_class.return_value = self.mock_http_instance
    
    def tearDown(self):
        """Clean up after each test method."""
        self.http_patch.stop()
    
    def test_initialization_demo_mode(self):
        """Test initialization in demo mode"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        self.assertEqual(execution.mode, TradingMode.DEMO)
        self.assertEqual(execution.config, self.test_config)
        self.assertEqual(execution.max_retries, 3)
        self.mock_http_class.assert_called_once_with(
            testnet=True,
            api_key=self.test_config["api_key"],
            api_secret=self.test_config["api_secret"]
        )
    
    def test_initialization_live_mode(self):
        """Test initialization in live mode"""
        live_config = {
            "api_key": "live_api_key",
            "api_secret": "live_api_secret",
            "base_url": "https://api.bybit.com"
        }
        
        execution = BybitExecution(mode=TradingMode.LIVE, config=live_config)
        
        self.assertEqual(execution.mode, TradingMode.LIVE)
        self.mock_http_class.assert_called_once_with(
            testnet=False,
            api_key=live_config["api_key"],
            api_secret=live_config["api_secret"]
        )
    
    @patch('asyncio.sleep', return_value=None)
    async def test_retry_with_backoff_success(self, mock_sleep):
        """Test retry with backoff when function succeeds"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        async def successful_func():
            return "success"
        
        result = await execution._retry_with_backoff(successful_func)
        self.assertEqual(result, "success")
        mock_sleep.assert_not_called()
    
    @patch('asyncio.sleep', return_value=None)
    async def test_retry_with_backoff_failure(self, mock_sleep):
        """Test retry with backoff when function always fails"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        async def failing_func():
            raise Exception("Always fails")
        
        with self.assertRaises(Exception) as context:
            await execution._retry_with_backoff(failing_func)
        
        self.assertIn("Always fails", str(context.exception))
        self.assertEqual(mock_sleep.call_count, 2)  # 3 attempts = 2 sleeps
    
    @patch('asyncio.sleep', return_value=None)
    async def test_retry_with_backoff_eventual_success(self, mock_sleep):
        """Test retry with backoff when function succeeds on second attempt"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        attempt_count = 0
        
        async def sometimes_failing_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("First attempt fails")
            return "success"
        
        result = await execution._retry_with_backoff(sometimes_failing_func)
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count, 2)
        mock_sleep.assert_called_once()
    
    async def test_get_account_balance_success(self):
        """Test getting account balance successfully"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "coin": [
                            {"coin": "USDT", "walletBalance": "10000.50"},
                            {"coin": "BTC", "walletBalance": "0.5"}
                        ]
                    }
                ]
            }
        }
        self.mock_http_instance.get_wallet_balance.return_value = mock_response
        
        balance = await execution.get_account_balance()
        self.assertEqual(balance, 10000.50)
    
    async def test_get_account_balance_no_usdt(self):
        """Test getting account balance when no USDT balance"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response with no USDT
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "coin": [
                            {"coin": "BTC", "walletBalance": "0.5"}
                        ]
                    }
                ]
            }
        }
        self.mock_http_instance.get_wallet_balance.return_value = mock_response
        
        balance = await execution.get_account_balance()
        self.assertEqual(balance, 0.0)
    
    async def test_get_account_balance_api_error(self):
        """Test getting account balance when API returns error"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API error response
        mock_response = {
            "retCode": 10001,
            "retMsg": "Invalid API key"
        }
        self.mock_http_instance.get_wallet_balance.return_value = mock_response
        
        with self.assertRaises(Exception) as context:
            await execution.get_account_balance()
        
        self.assertIn("Failed to get balance", str(context.exception))
    
    async def test_get_symbol_info_success(self):
        """Test getting symbol info successfully"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "qtyStep": "0.001"
                        }
                    }
                ]
            }
        }
        self.mock_http_instance.get_instruments_info.return_value = mock_response
        
        symbol_info = await execution.get_symbol_info("BTCUSDT")
        self.assertEqual(symbol_info["symbol"], "BTCUSDT")
        self.assertIn("lotSizeFilter", symbol_info)
    
    async def test_get_symbol_info_not_found(self):
        """Test getting symbol info when symbol not found"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response with no symbols
        mock_response = {
            "retCode": 0,
            "result": {
                "list": []
            }
        }
        self.mock_http_instance.get_instruments_info.return_value = mock_response
        
        with self.assertRaises(Exception) as context:
            await execution.get_symbol_info("NONEXISTENT")
        
        self.assertIn("Symbol NONEXISTENT not found", str(context.exception))
    
    async def test_get_current_price_success(self):
        """Test getting current price successfully"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "50000.0"
                    }
                ]
            }
        }
        self.mock_http_instance.get_tickers.return_value = mock_response
        
        price = await execution.get_current_price("BTCUSDT")
        self.assertEqual(price, 50000.0)
    
    async def test_get_position_no_position(self):
        """Test getting position when no position exists"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response with no positions
        mock_response = {
            "retCode": 0,
            "result": {
                "list": []
            }
        }
        self.mock_http_instance.get_positions.return_value = mock_response
        
        position = await execution.get_position("BTCUSDT")
        self.assertIsNone(position)
    
    async def test_get_position_with_position(self):
        """Test getting position when position exists"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response with position
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "size": "0.1"
                    }
                ]
            }
        }
        self.mock_http_instance.get_positions.return_value = mock_response
        
        position = await execution.get_position("BTCUSDT")
        self.assertIsNotNone(position)
        self.assertEqual(position["symbol"], "BTCUSDT")
        self.assertEqual(position["side"], "Buy")
        self.assertEqual(position["size"], "0.1")
    
    async def test_place_order_hold_action(self):
        """Test placing order with hold action"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        result = await execution.place_order(0, "BTCUSDT")
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["message"], "No action taken")
    
    async def test_place_order_invalid_action(self):
        """Test placing order with invalid action"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        with self.assertRaises(ValueError) as context:
            await execution.place_order(99, "BTCUSDT")
        
        self.assertIn("Invalid action", str(context.exception))
    
    async def test_cancel_all_orders_success(self):
        """Test cancelling all orders successfully"""
        execution = BybitExecution(mode=TradingMode.DEMO, config=self.test_config)
        
        # Mock API response
        mock_response = {
            "retCode": 0,
            "retMsg": "OK"
        }
        self.mock_http_instance.cancel_all_orders.return_value = mock_response
        
        result = await execution.cancel_all_orders("BTCUSDT")
        self.assertEqual(result["status"], "success")
        self.assertIn("Cancelled all orders for BTCUSDT", result["message"])

if __name__ == '__main__':
    # Run async tests
    unittest.main()
