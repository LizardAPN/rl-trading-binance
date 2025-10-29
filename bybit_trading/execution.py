import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
import math

from pybit.unified_trading import HTTP

from .config import TradingMode, BYBIT_CONFIG
from .risk import RiskManager

logger = logging.getLogger(__name__)

class BybitExecution:
    """
    Handles order execution on Bybit exchange with risk management
    """
    
    def __init__(self, mode: str, config: dict = None, max_retries: int = 3):
        """
        Initialize the execution module
        
        Args:
            mode: Trading mode (demo, paper, live)
            config: Configuration dictionary (optional, will use default if not provided)
            max_retries: Maximum number of retry attempts for API calls
        """
        self.mode = mode
        self.config = config or TradingMode.get_config(mode)
        self.max_retries = max_retries
        self.risk_manager = RiskManager()
        
        # Initialize Bybit HTTP session
        self.session = HTTP(
            testnet=TradingMode.is_testnet(mode),
            api_key=self.config["api_key"],
            api_secret=self.config["api_secret"]
        )
        
        logger.info(f"Initialized BybitExecution in {mode} mode")
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute a function with exponential backoff retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"All retry attempts failed: {str(e)}")
                    raise e
                
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + (0.1 * attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
    
    async def get_account_balance(self) -> float:
        """
        Get account balance in USDT
        
        Returns:
            float: Available balance in USDT
        """
        try:
            response = await self._retry_with_backoff(
                lambda: self.session.get_wallet_balance(accountType="UNIFIED")
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to get balance: {response.get('retMsg')}")
            
            balances = response.get("result", {}).get("list", [])
            if not balances:
                raise Exception("No balance information returned")
            
            # Find USDT balance
            for coin in balances[0].get("coin", []):
                if coin.get("coin") == "USDT":
                    return float(coin.get("walletBalance", 0))
            
            return 0.0
        except Exception as e:
            logger.error(f"Error getting account balance: {str(e)}")
            raise
    
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get symbol information including price and limits
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            dict: Symbol information
        """
        try:
            response = await self._retry_with_backoff(
                lambda: self.session.get_instruments_info(category="linear", symbol=symbol)
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to get symbol info: {response.get('retMsg')}")
            
            symbols = response.get("result", {}).get("list", [])
            if not symbols:
                raise Exception(f"Symbol {symbol} not found")
            
            return symbols[0]
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {str(e)}")
            raise
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            float: Current market price
        """
        try:
            response = await self._retry_with_backoff(
                lambda: self.session.get_tickers(category="linear", symbol=symbol)
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to get ticker: {response.get('retMsg')}")
            
            tickers = response.get("result", {}).get("list", [])
            if not tickers:
                raise Exception(f"No ticker data for {symbol}")
            
            return float(tickers[0].get("lastPrice", 0))
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {str(e)}")
            raise
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            dict: Position information or None if no position
        """
        try:
            response = await self._retry_with_backoff(
                lambda: self.session.get_positions(category="linear", symbol=symbol)
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to get position: {response.get('retMsg')}")
            
            positions = response.get("result", {}).get("list", [])
            if not positions:
                return None
            
            # Return first position (should be only one for isolated margin)
            return positions[0] if positions[0].get("size", "0") != "0" else None
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {str(e)}")
            raise
    
    async def place_order(self, action: int, symbol: str, qty: float = None) -> Dict[str, Any]:
        """
        Place an order based on agent action
        
        Args:
            action: Agent action (0: Hold, 1: Buy, 2: Sell, 3: Close)
            symbol: Trading pair symbol (e.g., BTCUSDT)
            qty: Order quantity (if None, will be calculated automatically)
            
        Returns:
            dict: Order result
        """
        action_map = {
            0: None,           # HOLD - без действия
            1: {"side": "Buy", "order_type": "Market"},
            2: {"side": "Sell", "order_type": "Market"}, 
            3: {"side": "Close"}  # Закрытие позиции
        }
        
        if action not in action_map:
            raise ValueError(f"Invalid action: {action}")
        
        if action == 0:  # HOLD
            logger.info("Hold action - no order placed")
            return {"status": "hold", "message": "No action taken"}
        
        try:
            # Get current price for position sizing if needed
            current_price = await self.get_current_price(symbol)
            
            # Calculate position size if not provided
            if qty is None:
                balance = await self.get_account_balance()
                qty = self.risk_manager.calculate_position_size(balance, current_price)
                logger.info(f"Calculated position size: {qty} for {symbol}")
            
            # Validate symbol
            symbol_info = await self.get_symbol_info(symbol)
            min_qty = float(symbol_info.get("lotSizeFilter", {}).get("minOrderQty", 0))
            
            # Round quantity to meet exchange requirements
            qty_precision = symbol_info.get("lotSizeFilter", {}).get("qtyStep", "0.0001")
            qty_step = float(qty_precision)
            qty = math.floor(qty / qty_step) * qty_step
            
            if qty < min_qty:
                logger.warning(f"Calculated quantity {qty} is below minimum {min_qty}")
                if action != 3:  # Don't place order if not closing
                    return {"status": "rejected", "message": f"Quantity {qty} below minimum {min_qty}"}
            
            # Prepare order parameters
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "qty": str(qty),
                "marketUnit": "coin" if symbol.endswith("USDT") else "baseCoin"
            }
            
            if action == 3:  # Close position
                position = await self.get_position(symbol)
                if not position:
                    logger.info("No position to close")
                    return {"status": "no_position", "message": "No open position to close"}
                
                order_params["side"] = "Sell" if position.get("side") == "Buy" else "Buy"
                order_params["orderType"] = "Market"
                order_params["reduceOnly"] = True
                logger.info(f"Closing position: {position.get('side')} {qty} {symbol}")
            else:
                order_details = action_map[action]
                order_params["side"] = order_details["side"]
                order_params["orderType"] = order_details["order_type"]
                logger.info(f"Placing {order_details['side']} order: {qty} {symbol}")
            
            # Place the order
            response = await self._retry_with_backoff(
                lambda: self.session.place_order(**order_params)
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Order placement failed: {response.get('retMsg')}")
            
            order_result = {
                "status": "success",
                "order_id": response.get("result", {}).get("orderId"),
                "action": action,
                "symbol": symbol,
                "quantity": qty,
                "price": current_price
            }
            
            logger.info(f"Order placed successfully: {order_result}")
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """
        Cancel all open orders for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            dict: Cancellation result
        """
        try:
            response = await self._retry_with_backoff(
                lambda: self.session.cancel_all_orders(category="linear", symbol=symbol)
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to cancel orders: {response.get('retMsg')}")
            
            result = {
                "status": "success",
                "message": f"Cancelled all orders for {symbol}"
            }
            
            logger.info(result["message"])
            return result
        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def get_all_symbols(self) -> List[str]:
        """
        Get all available USDT perpetual contract symbols from Bybit
        
        Returns:
            list: List of available symbol names
        """
        try:
            # Use a separate session without authentication for public endpoints
            public_session = HTTP(testnet=TradingMode.is_testnet(self.mode))
            
            response = await self._retry_with_backoff(
                lambda: public_session.get_instruments_info(category="linear")
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to get instruments info: {response.get('retMsg')}")
            
            symbols = response.get("result", {}).get("list", [])
            
            # Filter for USDT perpetual contracts that are currently trading
            usdt_contracts = [
                symbol.get("symbol") for symbol in symbols 
                if symbol.get("quoteCoin") == "USDT" and symbol.get("status") == "Trading"
            ]
            
            logger.info(f"Fetched {len(usdt_contracts)} USDT perpetual contracts")
            return usdt_contracts
            
        except Exception as e:
            logger.error(f"Error fetching all symbols: {str(e)}")
            raise
