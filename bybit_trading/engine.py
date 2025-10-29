import asyncio
import logging
import signal
import sys
from typing import List, Dict, Any, Optional
import time

from .config import TradingMode, BYBIT_CONFIG
from .execution import BybitExecution
from .risk import RiskManager
from .streaming import BybitDataStream
from .monitoring import SystemMonitor, TelegramNotifier

logger = logging.getLogger(__name__)

class BybitTradingEngine:
    """
    Main trading engine that coordinates all components for live trading
    """
    
    def __init__(self, mode: str, symbols: List[str], config: dict = None):
        """
        Initialize the trading engine
        
        Args:
            mode: Trading mode (demo, paper, live)
            symbols: List of trading symbols
            config: Additional configuration parameters
        """
        self.mode = mode
        self.symbols = symbols
        self.config = config or {}
        
        # Initialize components
        self.execution = None
        self.data_stream = None
        self.monitor = None
        self.risk_manager = None
        
        # Runtime state
        self.running = False
        self.last_balance_update = 0
        self.check_interval = self.config.get("check_interval", 60)  # seconds
        self.max_position_pct = self.config.get("max_position_pct", 0.1)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initialized BybitTradingEngine in {mode} mode for symbols: {symbols}")
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully
        """
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    async def initialize(self):
        """
        Initialize all components of the trading engine
        """
        try:
            # Get configuration based on mode
            bybit_config = TradingMode.get_config(self.mode)
            
            # Initialize risk manager
            self.risk_manager = RiskManager(max_position_size=self.max_position_pct)
            
            # Initialize execution module
            self.execution = BybitExecution(
                mode=self.mode,
                config=bybit_config
            )
            
            # Determine symbols to use
            final_symbols = self.symbols
            if self.config.get("use_all_symbols", False):
                logger.info("Fetching all available symbols...")
                all_symbols = await self.execution.get_all_symbols()
                final_symbols = all_symbols
                logger.info(f"Using all {len(final_symbols)} available symbols")
            else:
                logger.info(f"Using configured symbols: {final_symbols}")
            
            # Initialize data stream
            self.data_stream = BybitDataStream(symbols=final_symbols)
            
            # Initialize monitoring
            telegram_notifier = TelegramNotifier(
                bot_token=self.config.get("telegram_bot_token"),
                chat_id=self.config.get("telegram_chat_id")
            )
            self.monitor = SystemMonitor(telegram_notifier=telegram_notifier)
            
            # Add health checks
            self._setup_health_checks()
            
            # Set up data stream callbacks
            self._setup_data_callbacks()
            
            logger.info("Trading engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing trading engine: {str(e)}")
            await self.monitor.log_error({"message": f"Initialization error: {str(e)}"})
            return False
    
    def _setup_health_checks(self):
        """
        Set up health checks for various components
        """
        if not self.monitor:
            return
            
        # WebSocket connection health check
        if self.data_stream:
            self.monitor.add_health_check("websocket", self.data_stream.health_check)
        
        # Execution module health check
        if self.execution:
            self.monitor.add_health_check("execution", lambda: {
                "mode": self.execution.mode,
                "configured": bool(self.execution.session),
                "max_retries": self.execution.max_retries
            })
    
    def _setup_data_callbacks(self):
        """
        Set up callbacks for data stream events
        """
        if not self.data_stream:
            return
            
        # Set message callback
        self.data_stream.set_on_message_callback(self._on_data_message)
        
        # Set error callback
        self.data_stream.set_on_error_callback(self._on_data_error)
        
        # Set disconnect callback
        self.data_stream.set_on_disconnect_callback(self._on_data_disconnect)
    
    async def _on_data_message(self, data: Dict[str, Any]):
        """
        Handle incoming data messages
        
        Args:
            data: Incoming data message
        """
        logger.debug(f"Received data message: {data.get('symbol', 'N/A')}")
        # Process incoming data here if needed for strategy
    
    async def _on_data_error(self, error: Exception):
        """
        Handle data stream errors
        
        Args:
            error: Error that occurred
        """
        logger.error(f"Data stream error: {str(error)}")
        await self.monitor.log_error({"message": f"Data stream error: {str(error)}"})
    
    async def _on_data_disconnect(self):
        """
        Handle data stream disconnection
        """
        logger.warning("Data stream disconnected")
        await self.monitor.log_error({"message": "Data stream disconnected"})
        
        # Attempt to reconnect if still running
        if self.running:
            logger.info("Attempting to reconnect data stream...")
            await self._reconnect_data_stream()
    
    async def _reconnect_data_stream(self):
        """
        Reconnect data stream
        """
        try:
            if self.data_stream:
                testnet = TradingMode.is_testnet(self.mode)
                await self.data_stream.connect(testnet=testnet)
                logger.info("Data stream reconnected successfully")
        except Exception as e:
            logger.error(f"Error reconnecting data stream: {str(e)}")
            await self.monitor.log_error({"message": f"Reconnection error: {str(e)}"})
    
    async def start(self):
        """
        Start the trading engine
        """
        logger.info("Starting Bybit trading engine...")
        
        # Initialize components
        if not await self.initialize():
            logger.error("Failed to initialize trading engine")
            return False
        
        # Connect to data stream
        try:
            testnet = TradingMode.is_testnet(self.mode)
            await self.data_stream.connect(testnet=testnet)
        except Exception as e:
            logger.error(f"Failed to connect to data stream: {str(e)}")
            await self.monitor.log_error({"message": f"Data stream connection error: {str(e)}"})
            return False
        
        # Mark as running
        self.running = True
        logger.info("Trading engine started successfully")
        
        # Send startup notification
        if self.monitor and self.monitor.telegram_notifier.enabled:
            message = f"🚀 Trading engine started\nMode: {self.mode}\nSymbols: {', '.join(self.symbols)}"
            await self.monitor.telegram_notifier.send_message(message)
        
        # Start main trading loop
        await self._trading_loop()
        
        return True
    
    async def _trading_loop(self):
        """
        Main trading loop
        """
        logger.info("Entering trading loop")
        
        while self.running:
            try:
                # Update balance periodically
                if time.time() - self.last_balance_update > self.check_interval:
                    await self._update_balance()
                    self.last_balance_update = time.time()
                
                # Run health checks
                health_status = self.monitor.run_health_checks()
                logger.debug(f"Health check status: {health_status}")
                
                # Get performance metrics
                metrics = self.monitor.get_performance_metrics()
                logger.info(f"Performance metrics: PnL=${metrics['total_pnl']:.2f}, "
                           f"ROI={metrics['roi']*100:.2f}%, Trades={metrics['total_trades']}")
                
                # Sleep before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}")
                await self.monitor.log_error({"message": f"Trading loop error: {str(e)}"})
                await asyncio.sleep(5)  # Brief pause before continuing
    
    async def _update_balance(self):
        """
        Update account balance for monitoring
        """
        try:
            if self.execution:
                balance = await self.execution.get_account_balance()
                self.monitor.update_balance(balance)
                logger.debug(f"Updated account balance: ${balance:.2f}")
        except Exception as e:
            logger.error(f"Error updating balance: {str(e)}")
    
    async def execute_trade(self, action: int, symbol: str, qty: float = None) -> Dict[str, Any]:
        """
        Execute a trade based on agent action
        
        Args:
            action: Agent action (0: Hold, 1: Buy, 2: Sell, 3: Close)
            symbol: Trading symbol
            qty: Order quantity (optional, will be calculated if not provided)
            
        Returns:
            dict: Trade execution result
        """
        if not self.execution:
            return {"status": "error", "message": "Execution module not initialized"}
        
        try:
            # Place order
            result = await self.execution.place_order(action, symbol, qty)
            
            # Log the order
            if self.monitor:
                await self.monitor.log_order({
                    "action": action,
                    "symbol": symbol,
                    "quantity": qty,
                    "result": result
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            error_result = {"status": "error", "message": str(e)}
            
            # Log the error
            if self.monitor:
                await self.monitor.log_error({
                    "message": f"Trade execution error: {str(e)}",
                    "action": action,
                    "symbol": symbol
                })
            
            return error_result
    
    def stop(self):
        """
        Stop the trading engine gracefully
        """
        logger.info("Stopping trading engine...")
        self.running = False
        
        # Disconnect data stream
        if self.data_stream:
            asyncio.create_task(self.data_stream.disconnect())
        
        # Send shutdown notification
        if self.monitor and self.monitor.telegram_notifier.enabled:
            message = f"🛑 Trading engine stopped\nMode: {self.mode}"
            asyncio.create_task(self.monitor.telegram_notifier.send_message(message))
        
        logger.info("Trading engine stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current engine status
        
        Returns:
            dict: Engine status information
        """
        return {
            "mode": self.mode,
            "symbols": self.symbols,
            "running": self.running,
            "performance_metrics": self.monitor.get_performance_metrics() if self.monitor else {},
            "health_checks": self.monitor.run_health_checks() if self.monitor else {}
        }
