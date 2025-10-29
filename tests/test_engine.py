import unittest
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.engine import BybitTradingEngine
from bybit_trading.config import TradingMode

class TestBybitTradingEngine(unittest.TestCase):
    """Test cases for the BybitTradingEngine class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.engine = BybitTradingEngine(
            mode=TradingMode.DEMO,
            symbols=self.symbols,
            config={
                "check_interval": 30,
                "max_position_pct": 0.05
            }
        )
    
    def test_initialization(self):
        """Test BybitTradingEngine initialization"""
        self.assertEqual(self.engine.mode, TradingMode.DEMO)
        self.assertEqual(self.engine.symbols, self.symbols)
        self.assertEqual(self.engine.config["check_interval"], 30)
        self.assertEqual(self.engine.config["max_position_pct"], 0.05)
        self.assertIsNone(self.engine.execution)
        self.assertIsNone(self.engine.data_stream)
        self.assertIsNone(self.engine.monitor)
        self.assertIsNone(self.engine.risk_manager)
        self.assertFalse(self.engine.running)
        self.assertEqual(self.engine.last_balance_update, 0)
    
    @patch('bybit_trading.engine.BybitExecution')
    @patch('bybit_trading.engine.BybitDataStream')
    @patch('bybit_trading.engine.SystemMonitor')
    @patch('bybit_trading.engine.RiskManager')
    async def test_initialize_success(self, mock_risk_manager, mock_system_monitor, mock_data_stream, mock_execution):
        """Test successful initialization of all components"""
        # Configure mocks
        mock_execution_instance = AsyncMock()
        mock_execution.return_value = mock_execution_instance
        
        mock_data_stream_instance = MagicMock()
        mock_data_stream.return_value = mock_data_stream_instance
        
        mock_monitor_instance = MagicMock()
        mock_system_monitor.return_value = mock_monitor_instance
        
        mock_risk_manager_instance = MagicMock()
        mock_risk_manager.return_value = mock_risk_manager_instance
        
        # Test initialization
        result = await self.engine.initialize()
        
        self.assertTrue(result)
        self.assertEqual(self.engine.execution, mock_execution_instance)
        self.assertEqual(self.engine.data_stream, mock_data_stream_instance)
        self.assertEqual(self.engine.monitor, mock_monitor_instance)
        self.assertEqual(self.engine.risk_manager, mock_risk_manager_instance)
        
        # Check that components were initialized with correct parameters
        mock_execution.assert_called_once_with(
            mode=TradingMode.DEMO,
            config=TradingMode.get_config(TradingMode.DEMO)
        )
        mock_data_stream.assert_called_once_with(symbols=self.symbols)
        mock_risk_manager.assert_called_once_with(max_position_size=0.05)
    
    @patch('bybit_trading.engine.BybitExecution')
    async def test_initialize_failure(self, mock_execution):
        """Test initialization failure"""
        # Configure mock to raise an exception
        mock_execution.side_effect = Exception("Initialization failed")
        
        # Test initialization
        result = await self.engine.initialize()
        
        self.assertFalse(result)
        self.assertIsNone(self.engine.execution)
    
    def test_setup_health_checks(self):
        """Test setting up health checks"""
        # Create mock monitor
        self.engine.monitor = MagicMock()
        
        # Create mock data stream
        self.engine.data_stream = MagicMock()
        
        # Create mock execution
        self.engine.execution = MagicMock()
        
        # Test setting up health checks
        self.engine._setup_health_checks()
        
        # Check that health checks were added
        self.assertEqual(self.engine.monitor.add_health_check.call_count, 2)
    
    def test_setup_data_callbacks(self):
        """Test setting up data stream callbacks"""
        # Create mock data stream
        mock_data_stream = MagicMock()
        self.engine.data_stream = mock_data_stream
        
        # Test setting up callbacks
        self.engine._setup_data_callbacks()
        
        # Check that callbacks were set
        mock_data_stream.set_on_message_callback.assert_called_once()
        mock_data_stream.set_on_error_callback.assert_called_once()
        mock_data_stream.set_on_disconnect_callback.assert_called_once()
    
    async def test_on_data_message(self):
        """Test handling of data messages"""
        # Create mock monitor
        mock_monitor = MagicMock()
        self.engine.monitor = mock_monitor
        
        # Test handling data message
        test_data = {"symbol": "BTCUSDT", "price": 40000.0}
        await self.engine._on_data_message(test_data)
        
        # No specific assertions needed, just ensuring no exceptions
    
    async def test_on_data_error(self):
        """Test handling of data stream errors"""
        # Create mock monitor
        mock_monitor = MagicMock()
        self.engine.monitor = mock_monitor
        
        # Test handling error
        test_error = Exception("Test error")
        await self.engine._on_data_error(test_error)
        
        # Check that error was logged
        mock_monitor.log_error.assert_called_once()
    
    async def test_on_data_disconnect(self):
        """Test handling of data stream disconnection"""
        # Create mock monitor
        mock_monitor = MagicMock()
        self.engine.monitor = mock_monitor
        
        # Test handling disconnection
        await self.engine._on_data_disconnect()
        
        # Check that error was logged
        mock_monitor.log_error.assert_called_once()
    
    @patch('bybit_trading.engine.BybitExecution')
    async def test_execute_trade_success(self, mock_execution):
        """Test successful trade execution"""
        # Configure mock execution
        mock_execution_instance = AsyncMock()
        mock_execution_instance.place_order.return_value = {
            "status": "success",
            "order_id": "12345"
        }
        self.engine.execution = mock_execution_instance
        
        # Create mock monitor
        mock_monitor = MagicMock()
        self.engine.monitor = mock_monitor
        
        # Test executing trade
        result = await self.engine.execute_trade(1, "BTCUSDT", 0.1)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["order_id"], "12345")
        
        # Check that order was placed
        mock_execution_instance.place_order.assert_called_once_with(1, "BTCUSDT", 0.1)
        
        # Check that order was logged
        mock_monitor.log_order.assert_called_once()
    
    @patch('bybit_trading.engine.BybitExecution')
    async def test_execute_trade_without_execution_module(self, mock_execution):
        """Test trade execution without execution module"""
        self.engine.execution = None
        
        # Test executing trade
        result = await self.engine.execute_trade(1, "BTCUSDT", 0.1)
        
        self.assertEqual(result["status"], "error")
        self.assertIn("not initialized", result["message"])
    
    def test_get_status(self):
        """Test getting engine status"""
        # Create mock monitor with return values
        mock_monitor = MagicMock()
        mock_monitor.get_performance_metrics.return_value = {"total_pnl": 100.0}
        mock_monitor.run_health_checks.return_value = {"websocket": {"connected": True}}
        self.engine.monitor = mock_monitor
        
        # Set running state
        self.engine.running = True
        
        # Test getting status
        status = self.engine.get_status()
        
        self.assertEqual(status["mode"], TradingMode.DEMO)
        self.assertEqual(status["symbols"], self.symbols)
        self.assertTrue(status["running"])
        self.assertIn("performance_metrics", status)
        self.assertIn("health_checks", status)
        self.assertEqual(status["performance_metrics"]["total_pnl"], 100.0)

if __name__ == '__main__':
    # Run async tests
    unittest.main()
