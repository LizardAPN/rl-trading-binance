import asyncio
import json
import logging
import time
from typing import List, Dict, Any, Callable
from collections import deque

import websockets
from pybit.unified_trading import WebSocket

logger = logging.getLogger(__name__)

class BybitDataStream:
    """
    Handles real-time data streaming from Bybit WebSocket API
    """
    
    def __init__(self, symbols: List[str], max_buffer_size: int = 1000):
        """
        Initialize the data stream
        
        Args:
            symbols: List of trading symbols to subscribe to
            max_buffer_size: Maximum size of the data buffer
        """
        self.symbols = symbols
        self.max_buffer_size = max_buffer_size
        self.buffer = deque(maxlen=max_buffer_size)
        self.ws = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        # Callbacks
        self.on_message_callback = None
        self.on_error_callback = None
        self.on_disconnect_callback = None
        
        logger.info(f"Initialized BybitDataStream for symbols: {symbols}")
    
    def set_on_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback function for handling incoming messages
        
        Args:
            callback: Function to call when a message is received
        """
        self.on_message_callback = callback
    
    def set_on_error_callback(self, callback: Callable[[Exception], None]):
        """
        Set callback function for handling errors
        
        Args:
            callback: Function to call when an error occurs
        """
        self.on_error_callback = callback
    
    def set_on_disconnect_callback(self, callback: Callable[[], None]):
        """
        Set callback function for handling disconnections
        
        Args:
            callback: Function to call when disconnected
        """
        self.on_disconnect_callback = callback
    
    async def connect(self, testnet: bool = True):
        """
        Connect to Bybit WebSocket
        
        Args:
            testnet: Whether to use testnet (True) or mainnet (False)
        """
        try:
            # Close existing connection if any
            if self.ws:
                await self.disconnect()
            
            # Determine URL based on network
            if testnet:
                url = "wss://stream-testnet.bybit.com/v5/public/linear"
            else:
                url = "wss://stream.bybit.com/v5/public/linear"
            
            logger.info(f"Connecting to Bybit WebSocket at {url}")
            
            # Initialize WebSocket
            self.ws = WebSocket(
                testnet=testnet,
                channel_type="linear"
            )
            
            # Store reference to the event loop
            self._loop = asyncio.get_running_loop()
            
            # Define callback function for handling messages
            def ws_callback(message):
                # This callback will be called when messages arrive
                # We need to handle the message appropriately
                if self.on_message_callback:
                    # Use the stored event loop to schedule the async callback
                    asyncio.run_coroutine_threadsafe(
                        self._handle_message(message), 
                        self._loop
                    )
            
            # Subscribe to kline topics for all symbols
            for symbol in self.symbols:
                # Subscribe to 1-minute klines
                self.ws.kline_stream(interval=1, symbol=symbol, callback=ws_callback)
                # Subscribe to 5-minute klines
                self.ws.kline_stream(interval=5, symbol=symbol, callback=ws_callback)
            
            self.running = True
            self.reconnect_attempts = 0
            
            logger.info(f"Subscribed to kline topics for symbols: {self.symbols}")
            
            # Keep the connection alive
            while self.running and self.ws:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {str(e)}")
            if self.on_error_callback:
                # Call the error callback directly
                self.on_error_callback(e)
            raise
    
    async def _listen(self):
        """
        Listen for incoming WebSocket messages
        """
        try:
            while self.running and self.ws:
                try:
                    # Get message from WebSocket
                    message = self.ws.recv()
                    if message:
                        await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error receiving message: {str(e)}")
                    if self.on_error_callback:
                        self.on_error_callback(e)
                    break
                    
        except Exception as e:
            logger.error(f"Error in listen loop: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(e)
        finally:
            await self._on_disconnect()
    
    async def _handle_message(self, message: Dict[str, Any]):
        """
        Handle incoming WebSocket message
        
        Args:
            message: Incoming message data
        """
        try:
            # Parse message
            if isinstance(message, str):
                message = json.loads(message)
            
            # Debug: Log the type and content of the message
            logger.debug(f"Received message type: {type(message)}, content: {message}")
            
            # Handle list messages (multiple klines in one message)
            if isinstance(message, list):
                # Process each item in the list
                for item in message:
                    await self._process_single_message(item)
                return
            
            # Handle single message
            await self._process_single_message(message)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    async def _process_single_message(self, message: Dict[str, Any]):
        """
        Process a single WebSocket message
        
        Args:
            message: Single message data
        """
        try:
            topic = message.get('topic', '') if isinstance(message, dict) else ''
            
            # Handle kline data
            if topic.startswith('kline'):
                parsed_data = self._parse_kline(message)
                if parsed_data:
                    # Add to buffer
                    self.buffer.append(parsed_data)
                    
                    # Call callback if set
                    if self.on_message_callback:
                        await self.on_message_callback(parsed_data)
                        
                    logger.debug(f"Received kline data for {parsed_data.get('symbol')}")
            
            # Handle other message types if needed
            else:
                logger.debug(f"Received non-kline message: {topic}")
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    def _parse_kline(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse kline data from WebSocket message
        
        Args:
            message: Raw WebSocket message
            
        Returns:
            dict: Parsed kline data
        """
        try:
            # Debug: Log the type and content of the message
            logger.debug(f"Parsing kline message type: {type(message)}, content: {message}")
            
            # Check if message is a dictionary
            if not isinstance(message, dict):
                logger.error(f"Expected dict message but got {type(message)}: {message}")
                return None
                
            topic = message.get('topic', '')
            data = message.get('data', {})
            
            # Extract symbol and timeframe from topic
            # Format: kline.{interval}.{symbol}
            parts = topic.split('.')
            if len(parts) >= 3:
                interval = parts[1]
                symbol = parts[2]
            else:
                symbol = "UNKNOWN"
                interval = "1"
            
            # Parse kline data
            kline_data = {
                'timestamp': int(time.time() * 1000),  # Current timestamp in ms
                'symbol': symbol,
                'interval': interval,
                'open_time': data.get('start', 0),
                'open': float(data.get('open', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'close': float(data.get('close', 0)),
                'volume': float(data.get('volume', 0)),
                'turnover': float(data.get('turnover', 0)),
                'confirm': data.get('confirm', False)
            }
            
            return kline_data
            
        except Exception as e:
            logger.error(f"Error parsing kline data: {str(e)}")
            return None
    
    async def disconnect(self):
        """
        Disconnect from WebSocket
        """
        self.running = False
        if self.ws:
            try:
                self.ws.exit()
                logger.info("Disconnected from WebSocket")
            except Exception as e:
                logger.error(f"Error disconnecting from WebSocket: {str(e)}")
            finally:
                self.ws = None
        
        await self._on_disconnect()
    
    async def _on_disconnect(self):
        """
        Handle disconnection event
        """
        logger.info("WebSocket disconnected")
        if self.on_disconnect_callback:
            self.on_disconnect_callback()
        
        # Attempt to reconnect if still running
        if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"Attempting to reconnect... ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
            await asyncio.sleep(self.reconnect_delay)
            # Reconnection would need to be handled by the caller
    
    def get_buffer_data(self) -> List[Dict[str, Any]]:
        """
        Get current buffer data
        
        Returns:
            list: Copy of current buffer data
        """
        return list(self.buffer)
    
    def clear_buffer(self):
        """
        Clear the data buffer
        """
        self.buffer.clear()
        logger.info("Data buffer cleared")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the data stream
        
        Returns:
            dict: Health check results
        """
        return {
            'connected': self.ws is not None,
            'running': self.running,
            'buffer_size': len(self.buffer),
            'max_buffer_size': self.buffer.maxlen,
            'symbols': self.symbols,
            'reconnect_attempts': self.reconnect_attempts
        }
