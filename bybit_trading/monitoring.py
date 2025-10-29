import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
import numpy as np

logger = logging.getLogger(__name__)

class TradeLogger:
    """
    Handles detailed logging of trades and system events in JSON format
    """
    
    def __init__(self, log_file: str = "trading_log.json"):
        """
        Initialize trade logger
        
        Args:
            log_file: Path to the log file
        """
        self.log_file = log_file
        self.session_start_time = time.time()
        
        # Initialize log file with session info
        self._initialize_log()
        
        logger.info(f"Initialized TradeLogger with log file: {log_file}")
    
    def _initialize_log(self):
        """
        Initialize log file with session information
        """
        session_info = {
            "session_start": datetime.utcnow().isoformat(),
            "session_id": f"session_{int(time.time())}",
            "events": []
        }
        
        try:
            with open(self.log_file, 'w') as f:
                json.dump(session_info, f, indent=2)
        except Exception as e:
            logger.error(f"Error initializing log file: {str(e)}")
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log an event to the JSON log file
        
        Args:
            event_type: Type of event (e.g., 'trade', 'error', 'order')
            data: Event data
        """
        try:
            # Read existing log
            with open(self.log_file, 'r') as f:
                log_data = json.load(f)
            
            # Create event entry
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "data": data
            }
            
            # Append event
            log_data["events"].append(event_entry)
            
            # Write back to file
            with open(self.log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
                
            logger.debug(f"Logged event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}")

class TelegramNotifier:
    """
    Sends notifications via Telegram bot
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot token (from @BotFather)
            chat_id: Chat ID to send messages to
        """
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            logger.info("TelegramNotifier initialized and enabled")
        else:
            logger.info("TelegramNotifier disabled (missing credentials)")
    
    async def send_message(self, message: str, parse_mode: str = "Markdown"):
        """
        Send a message via Telegram
        
        Args:
            message: Message to send
            parse_mode: Parse mode (Markdown, HTML, etc.)
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            # Send message asynchronously
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug("Telegram message sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")

class PerformanceMetrics:
    """
    Tracks and calculates real-time performance metrics
    """
    
    def __init__(self):
        """
        Initialize performance metrics tracker
        """
        self.trades = []
        self.balance_history = []
        self.start_balance = 0.0
        self.current_balance = 0.0
        
        logger.info("Initialized PerformanceMetrics")
    
    def update_balance(self, balance: float, timestamp: float = None):
        """
        Update account balance
        
        Args:
            balance: Current account balance
            timestamp: Timestamp of balance update (default: current time)
        """
        if timestamp is None:
            timestamp = time.time()
            
        self.current_balance = balance
        self.balance_history.append({
            "timestamp": timestamp,
            "balance": balance
        })
        
        # Set start balance if not set
        if self.start_balance == 0.0 and len(self.balance_history) == 1:
            self.start_balance = balance
    
    def record_trade(self, trade: Dict[str, Any]):
        """
        Record a trade for performance calculations
        
        Args:
            trade: Trade information
        """
        trade_entry = {
            "timestamp": time.time(),
            "pnl": trade.get("pnl", 0.0),
            "commission": trade.get("commission", 0.0),
            **trade
        }
        
        self.trades.append(trade_entry)
        logger.debug(f"Recorded trade: {trade.get('symbol', 'N/A')}")
    
    def calculate_pnl(self) -> float:
        """
        Calculate total PnL
        
        Returns:
            float: Total profit/loss
        """
        if not self.trades:
            return 0.0
            
        return sum(trade.get("pnl", 0.0) for trade in self.trades)
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sharpe ratio based on trade returns
        
        Args:
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            float: Sharpe ratio
        """
        if len(self.trades) < 2:
            return 0.0
        
        # Calculate returns
        returns = [trade.get("pnl", 0.0) / self.start_balance for trade in self.trades if self.start_balance > 0]
        
        if not returns:
            return 0.0
            
        # Calculate Sharpe ratio
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
            
        # Annualize (assuming daily returns, 252 trading days)
        sharpe = (mean_return - risk_free_rate) / std_return
        annualized_sharpe = sharpe * np.sqrt(252)
        
        return annualized_sharpe
    
    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown
        
        Returns:
            float: Maximum drawdown as percentage
        """
        if len(self.balance_history) < 2:
            return 0.0
        
        balances = [entry["balance"] for entry in self.balance_history]
        peak = balances[0]
        max_dd = 0.0
        
        for balance in balances:
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all performance metrics
        
        Returns:
            dict: Performance metrics
        """
        return {
            "total_pnl": self.calculate_pnl(),
            "sharpe_ratio": self.calculate_sharpe_ratio(),
            "max_drawdown": self.calculate_max_drawdown(),
            "total_trades": len(self.trades),
            "win_rate": self._calculate_win_rate(),
            "current_balance": self.current_balance,
            "start_balance": self.start_balance,
            "roi": ((self.current_balance - self.start_balance) / self.start_balance 
                   if self.start_balance > 0 else 0.0)
        }
    
    def _calculate_win_rate(self) -> float:
        """
        Calculate win rate of trades
        
        Returns:
            float: Win rate as percentage
        """
        if not self.trades:
            return 0.0
        
        winning_trades = sum(1 for trade in self.trades if trade.get("pnl", 0.0) > 0)
        return winning_trades / len(self.trades)

class SystemMonitor:
    """
    Monitors system health and performance
    """
    
    def __init__(self, telegram_notifier: TelegramNotifier = None):
        """
        Initialize system monitor
        
        Args:
            telegram_notifier: Telegram notifier instance
        """
        self.telegram_notifier = telegram_notifier or TelegramNotifier()
        self.trade_logger = TradeLogger()
        self.metrics = PerformanceMetrics()
        self.health_checks = []
        
        logger.info("Initialized SystemMonitor")
    
    async def log_trade(self, trade_data: Dict[str, Any]):
        """
        Log a trade event
        
        Args:
            trade_data: Trade information
        """
        self.trade_logger.log_event("trade", trade_data)
        self.metrics.record_trade(trade_data)
        
        # Send Telegram notification for significant trades
        if self.telegram_notifier.enabled:
            pnl = trade_data.get("pnl", 0.0)
            if abs(pnl) > 10:  # Notify for trades with PnL > $10
                symbol = trade_data.get("symbol", "N/A")
                message = f"-trade: {symbol}\nPnL: ${pnl:.2f}"
                await self.telegram_notifier.send_message(message)
    
    async def log_error(self, error_data: Dict[str, Any]):
        """
        Log an error event
        
        Args:
            error_data: Error information
        """
        self.trade_logger.log_event("error", error_data)
        
        # Send Telegram notification for errors
        if self.telegram_notifier.enabled:
            error_msg = error_data.get("message", "Unknown error")
            message = f"🚨 Error occurred:\n{error_msg}"
            await self.telegram_notifier.send_message(message)
    
    async def log_order(self, order_data: Dict[str, Any]):
        """
        Log an order event
        
        Args:
            order_data: Order information
        """
        self.trade_logger.log_event("order", order_data)
    
    def update_balance(self, balance: float):
        """
        Update account balance for metrics calculation
        
        Args:
            balance: Current account balance
        """
        self.metrics.update_balance(balance)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics
        
        Returns:
            dict: Performance metrics
        """
        return self.metrics.get_metrics()
    
    def add_health_check(self, name: str, check_function):
        """
        Add a health check function
        
        Args:
            name: Name of the health check
            check_function: Function that returns health status
        """
        self.health_checks.append({
            "name": name,
            "function": check_function
        })
    
    def run_health_checks(self) -> Dict[str, Any]:
        """
        Run all registered health checks
        
        Returns:
            dict: Health check results
        """
        results = {}
        for check in self.health_checks:
            try:
                results[check["name"]] = check["function"]()
            except Exception as e:
                results[check["name"]] = {
                    "status": "error",
                    "message": str(e)
                }
                logger.error(f"Health check {check['name']} failed: {str(e)}")
        
        return results
