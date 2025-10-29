import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Manages risk for trading operations
    """
    
    def __init__(self, max_position_size: float = 0.1):
        """
        Initialize risk manager
        
        Args:
            max_position_size: Maximum position size as fraction of balance (default: 0.1 = 10%)
        """
        self.max_position_size = max_position_size
        logger.info(f"Initialized RiskManager with max position size: {max_position_size*100}%")
    
    def calculate_position_size(self, balance: float, current_price: float) -> float:
        """
        Calculate safe position size based on account balance and current price
        
        Args:
            balance: Account balance in USDT
            current_price: Current market price of the asset
            
        Returns:
            float: Position size in asset units
        """
        if balance <= 0:
            logger.warning("Account balance is zero or negative")
            return 0.0
            
        if current_price <= 0:
            logger.warning("Current price is zero or negative")
            return 0.0
        
        # Calculate maximum risk amount
        max_risk_amount = balance * self.max_position_size
        
        # Calculate position size
        position_size = max_risk_amount / current_price
        
        logger.debug(f"Position size calculation - Balance: {balance}, "
                    f"Price: {current_price}, Max risk: {max_risk_amount}, "
                    f"Position size: {position_size}")
        
        return position_size
    
    def set_max_position_size(self, max_position_size: float) -> None:
        """
        Update maximum position size
        
        Args:
            max_position_size: New maximum position size as fraction of balance
        """
        if not 0 < max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")
        
        self.max_position_size = max_position_size
        logger.info(f"Updated max position size to: {max_position_size*100}%")
    
    def get_max_position_size(self) -> float:
        """
        Get current maximum position size setting
        
        Returns:
            float: Maximum position size as fraction of balance
        """
        return self.max_position_size
