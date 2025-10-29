import unittest
import os
import sys
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from collections import deque

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.streaming import BybitDataStream

class TestBybitDataStream(unittest.TestCase):
    """Test cases for the BybitDataStream class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.stream = BybitDataStream(symbols=self.symbols, max_buffer_size=100)
    
    def test_initialization(self):
        """Test BybitDataStream initialization"""
        self.assertEqual(self.stream.symbols, self.symbols)
        self.assertEqual(self.stream.max_buffer_size, 100)
        self.assertIsInstance(self.stream.buffer, deque)
        self.assertEqual(self.stream.buffer.maxlen, 100)
        self.assertIsNone(self.stream.ws)
        self.assertFalse(self.stream.running)
        self.assertEqual(self.stream.reconnect_attempts, 0)
        self.assertEqual(self.stream.max_reconnect_attempts, 5)
        self.assertEqual(self.stream.reconnect_delay, 5)
        self.assertIsNone(self.stream.on_message_callback)
        self.assertIsNone(self.stream.on_error_callback)
        self.assertIsNone(self.stream.on_disconnect_callback)
    
    def test_set_callbacks(self):
        """Test setting callback functions"""
        def message_callback(data):
            pass
        
        def error_callback(error):
            pass
        
        def disconnect_callback():
            pass
        
        self.stream.set_on_message_callback(message_callback)
        self.stream.set_on_error_callback(error_callback)
        self.stream.set_on_disconnect_callback(disconnect_callback)
        
        self.assertEqual(self.stream.on_message_callback, message_callback)
        self.assertEqual(self.stream.on_error_callback, error_callback)
        self.assertEqual(self.stream.on_disconnect_callback, disconnect_callback)
    
    def test_parse_kline_valid_message(self):
        """Test parsing valid kline message"""
        message = {
            "topic": "kline.1.BTCUSDT",
            "data": {
                "start": 1640000000000,
                "open": "40000.0",
                "high": "41000.0",
                "low": "39000.0",
                "close": "40500.0",
                "volume": "100.0",
                "turnover": "4000000.0",
                "confirm": True
            }
        }
        
        parsed_data = self.stream._parse_kline(message)
        
        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["symbol"], "BTCUSDT")
        self.assertEqual(parsed_data["interval"], "1")
        self.assertEqual(parsed_data["open"], 40000.0)
        self.assertEqual(parsed_data["high"], 41000.0)
        self.assertEqual(parsed_data["low"], 39000.0)
        self.assertEqual(parsed_data["close"], 40500.0)
        self.assertEqual(parsed_data["volume"], 100.0)
        self.assertEqual(parsed_data["turnover"], 4000000.0)
        self.assertTrue(parsed_data["confirm"])
        self.assertIn("timestamp", parsed_data)
        self.assertIn("open_time", parsed_data)
    
    def test_parse_kline_invalid_topic(self):
        """Test parsing kline message with invalid topic format"""
        message = {
            "topic": "invalid_topic",
            "data": {
                "open": "40000.0"
            }
        }
        
        parsed_data = self.stream._parse_kline(message)
        
        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["symbol"], "UNKNOWN")
        self.assertEqual(parsed_data["interval"], "1")
        self.assertEqual(parsed_data["open"], 40000.0)
    
    def test_parse_kline_malformed_data(self):
        """Test parsing kline message with malformed data"""
        message = {
            "topic": "kline.1.BTCUSDT",
            "data": "invalid_data"
        }
        
        parsed_data = self.stream._parse_kline(message)
        
        # Should handle gracefully and return None or default values
        self.assertIsNotNone(parsed_data)
        # Most fields will be 0.0 or default values
        self.assertEqual(parsed_data["open"], 0.0)
    
    def test_get_buffer_data(self):
        """Test getting buffer data"""
        # Add some data to buffer
        test_data = {"symbol": "BTCUSDT", "price": 40000.0}
        self.stream.buffer.append(test_data)
        
        buffer_data = self.stream.get_buffer_data()
        self.assertEqual(len(buffer_data), 1)
        self.assertEqual(buffer_data[0], test_data)
    
    def test_clear_buffer(self):
        """Test clearing buffer"""
        # Add some data to buffer
        self.stream.buffer.append({"symbol": "BTCUSDT", "price": 40000.0})
        self.stream.buffer.append({"symbol": "ETHUSDT", "price": 3000.0})
        
        self.assertEqual(len(self.stream.buffer), 2)
        
        self.stream.clear_buffer()
        
        self.assertEqual(len(self.stream.buffer), 0)
    
    def test_health_check(self):
        """Test health check functionality"""
        # Test initial state
        health = self.stream.health_check()
        self.assertFalse(health["connected"])
        self.assertFalse(health["running"])
        self.assertEqual(health["buffer_size"], 0)
        self.assertEqual(health["max_buffer_size"], 100)
        self.assertEqual(health["symbols"], self.symbols)
        self.assertEqual(health["reconnect_attempts"], 0)
        
        # Modify some state and test again
        self.stream.ws = MagicMock()
        self.stream.running = True
        self.stream.buffer.append({"test": "data"})
        self.stream.reconnect_attempts = 2
        
        health = self.stream.health_check()
        self.assertTrue(health["connected"])
        self.assertTrue(health["running"])
        self.assertEqual(health["buffer_size"], 1)
        self.assertEqual(health["reconnect_attempts"], 2)

if __name__ == '__main__':
    unittest.main()
