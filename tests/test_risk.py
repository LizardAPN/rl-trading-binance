import unittest
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bybit_trading.risk import RiskManager

class TestRiskManager(unittest.TestCase):
    """Test cases for the RiskManager class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.risk_manager = RiskManager(max_position_size=0.1)
    
    def test_initialization(self):
        """Test RiskManager initialization"""
        self.assertEqual(self.risk_manager.get_max_position_size(), 0.1)
    
    def test_calculate_position_size_positive_values(self):
        """Test position size calculation with positive values"""
        balance = 10000.0
        price = 50000.0
        expected_size = (balance * 0.1) / price  # 1000 / 50000 = 0.02
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertAlmostEqual(size, expected_size, places=10)
    
    def test_calculate_position_size_zero_balance(self):
        """Test position size calculation with zero balance"""
        balance = 0.0
        price = 50000.0
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertEqual(size, 0.0)
    
    def test_calculate_position_size_negative_balance(self):
        """Test position size calculation with negative balance"""
        balance = -1000.0
        price = 50000.0
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertEqual(size, 0.0)
    
    def test_calculate_position_size_zero_price(self):
        """Test position size calculation with zero price"""
        balance = 10000.0
        price = 0.0
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertEqual(size, 0.0)
    
    def test_calculate_position_size_negative_price(self):
        """Test position size calculation with negative price"""
        balance = 10000.0
        price = -50000.0
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertEqual(size, 0.0)
    
    def test_set_max_position_size_valid(self):
        """Test setting valid max position size"""
        new_size = 0.05
        self.risk_manager.set_max_position_size(new_size)
        self.assertEqual(self.risk_manager.get_max_position_size(), new_size)
    
    def test_set_max_position_size_invalid_too_high(self):
        """Test setting invalid max position size (too high)"""
        with self.assertRaises(ValueError):
            self.risk_manager.set_max_position_size(1.5)
    
    def test_set_max_position_size_invalid_too_low(self):
        """Test setting invalid max position size (too low)"""
        with self.assertRaises(ValueError):
            self.risk_manager.set_max_position_size(-0.1)
    
    def test_set_max_position_size_zero(self):
        """Test setting max position size to zero"""
        with self.assertRaises(ValueError):
            self.risk_manager.set_max_position_size(0.0)
    
    def test_different_max_position_sizes(self):
        """Test position calculation with different max position sizes"""
        balance = 10000.0
        price = 50000.0
        
        # Test with 5% max position size
        self.risk_manager.set_max_position_size(0.05)
        expected_size = (balance * 0.05) / price  # 500 / 50000 = 0.01
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertAlmostEqual(size, expected_size, places=10)
        
        # Test with 20% max position size
        self.risk_manager.set_max_position_size(0.2)
        expected_size = (balance * 0.2) / price  # 2000 / 50000 = 0.04
        size = self.risk_manager.calculate_position_size(balance, price)
        self.assertAlmostEqual(size, expected_size, places=10)

if __name__ == '__main__':
    unittest.main()
