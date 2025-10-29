import unittest
import os
import sys
import json
import tempfile
import asyncio
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.monitoring import TradeLogger, TelegramNotifier, PerformanceMetrics, SystemMonitor

class TestTradeLogger(unittest.TestCase):
    """Test cases for the TradeLogger class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.log_file = self.temp_file.name
    
    def tearDown(self):
        """Clean up after each test method."""
        # Remove the temporary file
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
    
    def test_initialization(self):
        """Test TradeLogger initialization"""
        logger = TradeLogger(log_file=self.log_file)
        self.assertEqual(logger.log_file, self.log_file)
        
        # Check that log file was created with proper structure
        with open(self.log_file, 'r') as f:
            data = json.load(f)
            self.assertIn("session_start", data)
            self.assertIn("session_id", data)
            self.assertIn("events", data)
            self.assertEqual(data["events"], [])
    
    def test_log_event(self):
        """Test logging an event"""
        logger = TradeLogger(log_file=self.log_file)
        
        # Log an event
        event_data = {"order_id": "12345", "symbol": "BTCUSDT", "quantity": 0.1}
        logger.log_event("trade", event_data)
        
        # Check that event was logged
        with open(self.log_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(len(data["events"]), 1)
            event = data["events"][0]
            self.assertEqual(event["event_type"], "trade")
            self.assertEqual(event["data"], event_data)
            self.assertIn("timestamp", event)

class TestTelegramNotifier(unittest.TestCase):
    """Test cases for the TelegramNotifier class"""
    
    @patch('requests.post')
    def test_send_message_enabled(self, mock_post):
        """Test sending a message when enabled"""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat")
        self.assertTrue(notifier.enabled)
        
        # Send a message
        asyncio.run(notifier.send_message("Test message"))
        
        # Check that request was made
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['chat_id'], "test_chat")
        self.assertEqual(kwargs['json']['text'], "Test message")
    
    def test_send_message_disabled(self):
        """Test sending a message when disabled"""
        notifier = TelegramNotifier()
        self.assertFalse(notifier.enabled)
        
        # Should not raise an exception
        asyncio.run(notifier.send_message("Test message"))
    
    @patch('requests.post')
    def test_send_message_exception(self, mock_post):
        """Test handling of exceptions when sending message"""
        mock_post.side_effect = Exception("Network error")
        notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat")
        
        # Should not raise an exception
        asyncio.run(notifier.send_message("Test message"))

class TestPerformanceMetrics(unittest.TestCase):
    """Test cases for the PerformanceMetrics class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.metrics = PerformanceMetrics()
    
    def test_initialization(self):
        """Test PerformanceMetrics initialization"""
        self.assertEqual(len(self.metrics.trades), 0)
        self.assertEqual(len(self.metrics.balance_history), 0)
        self.assertEqual(self.metrics.start_balance, 0.0)
        self.assertEqual(self.metrics.current_balance, 0.0)
    
    def test_update_balance_first_time(self):
        """Test updating balance for the first time"""
        self.metrics.update_balance(10000.0)
        self.assertEqual(self.metrics.current_balance, 10000.0)
        self.assertEqual(self.metrics.start_balance, 10000.0)
        self.assertEqual(len(self.metrics.balance_history), 1)
    
    def test_update_balance_subsequent_times(self):
        """Test updating balance multiple times"""
        self.metrics.update_balance(10000.0)
        self.metrics.update_balance(10500.0)
        self.metrics.update_balance(10200.0)
        
        self.assertEqual(self.metrics.current_balance, 10200.0)
        self.assertEqual(self.metrics.start_balance, 10000.0)
        self.assertEqual(len(self.metrics.balance_history), 3)
    
    def test_record_trade(self):
        """Test recording a trade"""
        trade_data = {
            "symbol": "BTCUSDT",
            "pnl": 100.0,
            "commission": 0.1
        }
        self.metrics.record_trade(trade_data)
        
        self.assertEqual(len(self.metrics.trades), 1)
        recorded_trade = self.metrics.trades[0]
        self.assertEqual(recorded_trade["symbol"], "BTCUSDT")
        self.assertEqual(recorded_trade["pnl"], 100.0)
        self.assertEqual(recorded_trade["commission"], 0.1)
        self.assertIn("timestamp", recorded_trade)
    
    def test_calculate_pnl_no_trades(self):
        """Test PnL calculation with no trades"""
        pnl = self.metrics.calculate_pnl()
        self.assertEqual(pnl, 0.0)
    
    def test_calculate_pnl_with_trades(self):
        """Test PnL calculation with trades"""
        self.metrics.record_trade({"pnl": 100.0})
        self.metrics.record_trade({"pnl": -50.0})
        self.metrics.record_trade({"pnl": 75.0})
        
        pnl = self.metrics.calculate_pnl()
        self.assertEqual(pnl, 125.0)
    
    def test_calculate_max_drawdown_no_history(self):
        """Test max drawdown calculation with no history"""
        drawdown = self.metrics.calculate_max_drawdown()
        self.assertEqual(drawdown, 0.0)
    
    def test_calculate_max_drawdown_with_history(self):
        """Test max drawdown calculation with history"""
        # Set initial balance
        self.metrics.update_balance(10000.0)
        
        # Update with lower balances to create drawdown
        self.metrics.update_balance(9000.0)
        self.metrics.update_balance(9500.0)
        self.metrics.update_balance(8000.0)  # Maximum drawdown point
        self.metrics.update_balance(11000.0)
        
        drawdown = self.metrics.calculate_max_drawdown()
        # Max drawdown = (10000 - 8000) / 10000 = 0.2
        self.assertAlmostEqual(drawdown, 0.2, places=10)
    
    def test_calculate_win_rate_no_trades(self):
        """Test win rate calculation with no trades"""
        win_rate = self.metrics._calculate_win_rate()
        self.assertEqual(win_rate, 0.0)
    
    def test_calculate_win_rate_with_trades(self):
        """Test win rate calculation with trades"""
        self.metrics.record_trade({"pnl": 100.0})   # Win
        self.metrics.record_trade({"pnl": -50.0})   # Loss
        self.metrics.record_trade({"pnl": 75.0})    # Win
        self.metrics.record_trade({"pnl": -25.0})   # Loss
        
        win_rate = self.metrics._calculate_win_rate()
        # 2 wins out of 4 trades = 0.5
        self.assertEqual(win_rate, 0.5)
    
    def test_get_metrics(self):
        """Test getting all metrics"""
        # Set up some data
        self.metrics.update_balance(10000.0)
        self.metrics.update_balance(11000.0)
        self.metrics.record_trade({"pnl": 1000.0, "symbol": "BTCUSDT"})
        
        metrics = self.metrics.get_metrics()
        
        self.assertIn("total_pnl", metrics)
        self.assertIn("sharpe_ratio", metrics)
        self.assertIn("max_drawdown", metrics)
        self.assertIn("total_trades", metrics)
        self.assertIn("win_rate", metrics)
        self.assertIn("current_balance", metrics)
        self.assertIn("start_balance", metrics)
        self.assertIn("roi", metrics)
        
        self.assertEqual(metrics["total_pnl"], 1000.0)
        self.assertEqual(metrics["total_trades"], 1)
        self.assertEqual(metrics["current_balance"], 11000.0)
        self.assertEqual(metrics["start_balance"], 10000.0)

class TestSystemMonitor(unittest.TestCase):
    """Test cases for the SystemMonitor class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.monitor = SystemMonitor()
    
    def test_initialization(self):
        """Test SystemMonitor initialization"""
        self.assertIsInstance(self.monitor.trade_logger, TradeLogger)
        self.assertIsInstance(self.monitor.metrics, PerformanceMetrics)
        self.assertIsInstance(self.monitor.telegram_notifier, TelegramNotifier)
        self.assertEqual(len(self.monitor.health_checks), 0)
    
    def test_update_balance(self):
        """Test updating balance"""
        self.monitor.update_balance(10000.0)
        # Check that balance was passed to metrics
        self.assertEqual(self.monitor.metrics.current_balance, 10000.0)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        metrics = self.monitor.get_performance_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn("total_pnl", metrics)
    
    def test_add_health_check(self):
        """Test adding a health check"""
        def test_check():
            return {"status": "ok"}
        
        self.monitor.add_health_check("test_check", test_check)
        self.assertEqual(len(self.monitor.health_checks), 1)
        self.assertEqual(self.monitor.health_checks[0]["name"], "test_check")
        self.assertEqual(self.monitor.health_checks[0]["function"], test_check)
    
    def test_run_health_checks(self):
        """Test running health checks"""
        def working_check():
            return {"status": "ok", "value": 42}
        
        def failing_check():
            raise Exception("Check failed")
        
        self.monitor.add_health_check("working", working_check)
        self.monitor.add_health_check("failing", failing_check)
        
        results = self.monitor.run_health_checks()
        self.assertIn("working", results)
        self.assertIn("failing", results)
        self.assertEqual(results["working"], {"status": "ok", "value": 42})
        self.assertEqual(results["failing"]["status"], "error")

if __name__ == '__main__':
    unittest.main()
