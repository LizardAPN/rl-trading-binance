# bybit_integration/trader.py
"""
Модуль для автоматической торговли на Bybit на основе сигналов модели
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import numpy as np

from .api_client import BybitAPIClient, AsyncBybitAPIClient
from .config import BybitIntegrationConfig
from .database import DatabaseManager

# Настройка логирования
logger = logging.getLogger(__name__)


class BybitTrader:
    """
    Основной класс для автоматической торговли на Bybit
    """
    
    def __init__(self, config: BybitIntegrationConfig):
        """
        Инициализация трейдера Bybit
        
        Parameters
        ----------
        config : BybitIntegrationConfig
            Конфигурация для интеграции с Bybit
        """
        self.config = config
        self.api_client = BybitAPIClient(config.api)
        self.async_api_client = AsyncBybitAPIClient(config.api)
        self.db_manager = DatabaseManager(config.database)
        
        # Инициализация таблиц в базе данных
        self.db_manager.initialize_tables()
        
        # Состояние торговли
        self.is_running = False
        self.current_positions = {}
        self.open_orders = {}
        
        logger.info(f"BybitTrader initialized in {'DEMO' if config.api.is_demo else 'REAL'} mode")
    
    def get_market_data(self, symbol: str, interval: str = "1", limit: int = 200) -> List[Dict[str, Any]]:
        """
        Получение рыночных данных (свечей) для заданного символа
        
        Parameters
        ----------
        symbol : str
            Торговая пара (например, "BTCUSDT")
        interval : str, optional
            Интервал свечей (по умолчанию "1" - 1 минута)
        limit : int, optional
            Количество свечей (по умолчанию 200)
            
        Returns
        -------
        List[Dict[str, Any]]
            Список свечей с открытием, максимумом, минимумом, закрытием, объемом
        """
        try:
            response = self.api_client.get_kline(
                symbol=symbol,
                interval=interval,
                limit=limit,
                category="linear"
            )
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to fetch kline data: {response.get('retMsg')}")
            
            # Преобразование данных в удобный формат
            kline_data = response.get("result", {}).get("list", [])
            candles = []
            
            for candle in kline_data:
                candles.append({
                    "timestamp": datetime.fromtimestamp(int(candle[0]) / 1000),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                    "turnover": float(candle[6])
                })
            
            # Сохранение данных в базу
            self.db_manager.save_market_data([
                {"timestamp": c["timestamp"], "symbol": symbol, **c} for c in candles
            ])
            
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            raise
    
    def get_wallet_balance(self, coin: str = "USDT") -> Dict[str, Any]:
        """
        Получение баланса кошелька
        
        Parameters
        ----------
        coin : str, optional
            Валюта для получения баланса (по умолчанию "USDT")
            
        Returns
        -------
        Dict[str, Any]
            Информация о балансе кошелька
        """
        try:
            response = self.api_client.get_wallet_balance(coin=coin)
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to fetch wallet balance: {response.get('retMsg')}")
            
            balance_info = response.get("result", {}).get("list", [])
            if not balance_info:
                return {}
            
            # Возвращаем информацию о балансе для указанной монеты
            coins = balance_info[0].get("coin", [])
            for coin_info in coins:
                if coin_info.get("coin") == coin:
                    return {
                        "coin": coin_info.get("coin"),
                        "wallet_balance": float(coin_info.get("walletBalance", 0)),
                        "available_balance": float(coin_info.get("availableToWithdraw", 0)),
                        "equity": float(coin_info.get("equity", 0))
                    }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching wallet balance: {e}")
            raise
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение информации о текущих позициях
        
        Parameters
        ----------
        symbol : Optional[str], optional
            Торговая пара (если не указано, возвращает все позиции)
            
        Returns
        -------
        List[Dict[str, Any]]
            Список открытых позиций
        """
        try:
            response = self.api_client.get_positions(symbol=symbol, category="linear")
            
            if response.get("retCode") != 0:
                raise Exception(f"Failed to fetch positions: {response.get('retMsg')}")
            
            positions = response.get("result", {}).get("list", [])
            formatted_positions = []
            
            for pos in positions:
                # Пропускаем закрытые позиции
                if float(pos.get("size", 0)) == 0:
                    continue
                
                formatted_positions.append({
                    "symbol": pos.get("symbol"),
                    "side": pos.get("side"),
                    "size": float(pos.get("size", 0)),
                    "entry_price": float(pos.get("avgPrice", 0)),
                    "mark_price": float(pos.get("markPrice", 0)),
                    "pnl": float(pos.get("unrealisedPnl", 0)),
                    "leverage": int(pos.get("leverage", 1)),
                    "liquidation_price": float(pos.get("liqPrice", 0)),
                    "margin": float(pos.get("positionMM", 0))
                })
            
            # Обновление внутреннего состояния
            for pos in formatted_positions:
                self.current_positions[pos["symbol"]] = pos
            
            return formatted_positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise
    
    def calculate_position_size(self, symbol: str, signal_confidence: float = 1.0) -> float:
        """
        Расчет размера позиции на основе доступного баланса и конфиденциальности сигнала
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        signal_confidence : float, optional
            Уровень уверенности сигнала (0.0 - 1.0, по умолчанию 1.0)
            
        Returns
        -------
        float
            Размер позиции в базовой валюте
        """
        try:
            # Получение баланса кошелька
            balance = self.get_wallet_balance("USDT")
            available_balance = balance.get("available_balance", 0)
            
            if available_balance <= 0:
                logger.warning("No available balance for position sizing")
                return 0.0
            
            # Получение текущей цены символа
            tickers = self.api_client.get_tickers(category="linear")
            if tickers.get("retCode") != 0:
                raise Exception(f"Failed to fetch tickers: {tickers.get('retMsg')}")
            
            symbol_price = None
            for ticker in tickers.get("result", {}).get("list", []):
                if ticker.get("symbol") == symbol:
                    symbol_price = float(ticker.get("lastPrice", 0))
                    break
            
            if not symbol_price or symbol_price <= 0:
                logger.warning(f"Could not fetch price for {symbol}")
                return 0.0
            
            # Расчет размера позиции
            position_fraction = self.config.trading.position_size_fraction * signal_confidence
            position_value = available_balance * position_fraction
            position_size = position_value / symbol_price
            
            logger.info(f"Calculated position size for {symbol}: {position_size:.6f} ({position_value:.2f} USDT)")
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            return 0.0
    
    def place_order(self, symbol: str, side: str, order_type: str = "Market", 
                   qty: Optional[float] = None, signal_confidence: float = 1.0,
                   sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Размещение ордера на бирже
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        side : str
            Сторона ордера ("Buy" для LONG, "Sell" для SHORT)
        order_type : str, optional
            Тип ордера ("Market" или "Limit", по умолчанию "Market")
        qty : Optional[float], optional
            Количество (если не указано, рассчитывается автоматически)
        signal_confidence : float, optional
            Уровень уверенности сигнала (0.0 - 1.0, по умолчанию 1.0)
        sl_price : Optional[float], optional
            Цена стоп-лосса
        tp_price : Optional[float], optional
            Цена тейк-профита
            
        Returns
        -------
        Dict[str, Any]
            Результат размещения ордера
        """
        try:
            # Расчет размера позиции, если не указан
            if qty is None:
                qty = self.calculate_position_size(symbol, signal_confidence)
            
            if qty <= 0:
                raise Exception("Invalid position size")
            
            # Установка плеча
            self.api_client.set_leverage(
                symbol=symbol,
                buy_leverage=self.config.trading.leverage,
                sell_leverage=self.config.trading.leverage,
                category="linear"
            )
            
            # Размещение основного ордера
            order_response = self.api_client.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=qty,
                category="linear"
            )
            
            if order_response.get("retCode") != 0:
                raise Exception(f"Failed to place order: {order_response.get('retMsg')}")
            
            order_id = order_response.get("result", {}).get("orderId")
            logger.info(f"Placed {side} order for {symbol}: {order_id}")
            
            # Сохранение информации об ордере
            self.open_orders[order_id] = {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_id": order_id,
                "timestamp": datetime.now()
            }
            
            # Размещение стоп-лосса и тейк-профита, если включены
            if self.config.trading.enable_stop_loss and sl_price:
                sl_side = "Sell" if side == "Buy" else "Buy"
                sl_response = self.api_client.place_order(
                    symbol=symbol,
                    side=sl_side,
                    order_type="Stop",
                    qty=qty,
                    price=sl_price,
                    reduce_only=True,
                    category="linear"
                )
                if sl_response.get("retCode") == 0:
                    sl_order_id = sl_response.get("result", {}).get("orderId")
                    logger.info(f"Placed SL order for {symbol}: {sl_order_id}")
            
            if self.config.trading.enable_take_profit and tp_price:
                tp_side = "Sell" if side == "Buy" else "Buy"
                tp_response = self.api_client.place_order(
                    symbol=symbol,
                    side=tp_side,
                    order_type="Limit",
                    qty=qty,
                    price=tp_price,
                    reduce_only=True,
                    category="linear"
                )
                if tp_response.get("retCode") == 0:
                    tp_order_id = tp_response.get("result", {}).get("orderId")
                    logger.info(f"Placed TP order for {symbol}: {tp_order_id}")
            
            return order_response
            
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            raise
    
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Закрытие позиции по символу
        
        Parameters
        ----------
        symbol : str
            Торговая пара
            
        Returns
        -------
        Dict[str, Any]
            Результат закрытия позиции
        """
        try:
            # Получение текущей позиции
            positions = self.get_positions(symbol)
            if not positions:
                logger.info(f"No open position for {symbol}")
                return {}
            
            position = positions[0]
            position_side = position["side"]
            position_size = position["size"]
            
            # Определение стороны для закрытия
            close_side = "Sell" if position_side == "Buy" else "Buy"
            
            # Закрытие позиции
            close_response = self.api_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=position_size,
                reduce_only=True,
                category="linear"
            )
            
            if close_response.get("retCode") != 0:
                raise Exception(f"Failed to close position: {close_response.get('retMsg')}")
            
            # Удаление позиции из внутреннего состояния
            if symbol in self.current_positions:
                del self.current_positions[symbol]
            
            logger.info(f"Closed {position_side} position for {symbol}: {position_size}")
            return close_response
            
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            raise
    
    def calculate_stop_loss_take_profit(self, entry_price: float, side: str) -> tuple:
        """
        Расчет уровней стоп-лосса и тейк-профита
        
        Parameters
        ----------
        entry_price : float
            Цена входа
        side : str
            Сторона позиции ("Buy" или "Sell")
            
        Returns
        -------
        tuple
            Кортеж (stop_loss_price, take_profit_price)
        """
        if side == "Buy":
            sl_price = entry_price * (1 - self.config.trading.stop_loss_percent / 100)
            tp_price = entry_price * (1 + self.config.trading.take_profit_percent / 100)
        else:  # Sell
            sl_price = entry_price * (1 + self.config.trading.stop_loss_percent / 100)
            tp_price = entry_price * (1 - self.config.trading.take_profit_percent / 100)
        
        return sl_price, tp_price
    
    def process_model_signal(self, symbol: str, signal: int, confidence: float = 1.0) -> Dict[str, Any]:
        """
        Обработка сигнала от модели и выполнение торговых действий
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        signal : int
            Сигнал модели (0 - Hold, 1 - Long, 2 - Short, 3 - Close)
        confidence : float, optional
            Уровень уверенности сигнала (0.0 - 1.0, по умолчанию 1.0)
            
        Returns
        -------
        Dict[str, Any]
            Результат обработки сигнала
        """
        try:
            logger.info(f"Processing model signal for {symbol}: signal={signal}, confidence={confidence:.2f}")
            
            # Получение текущих позиций
            positions = self.get_positions(symbol)
            has_position = len(positions) > 0
            position_side = positions[0]["side"] if has_position else None
            
            result = {
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "action_taken": None,
                "order_id": None,
                "error": None
            }
            
            # Обработка сигнала в зависимости от текущего состояния
            if signal == 0:  # Hold
                result["action_taken"] = "hold"
                logger.info(f"Hold signal for {symbol} - no action taken")
                
            elif signal == 1:  # Long
                if not has_position:
                    # Открытие длинной позиции
                    market_data = self.get_market_data(symbol, limit=1)
                    if not market_data:
                        raise Exception("Failed to fetch market data for entry price")
                    
                    entry_price = market_data[0]["close"]
                    sl_price, tp_price = self.calculate_stop_loss_take_profit(entry_price, "Buy")
                    
                    order_response = self.place_order(
                        symbol=symbol,
                        side="Buy",
                        signal_confidence=confidence,
                        sl_price=sl_price,
                        tp_price=tp_price
                    )
                    
                    result["action_taken"] = "open_long"
                    result["order_id"] = order_response.get("result", {}).get("orderId")
                    logger.info(f"Opened LONG position for {symbol}")
                else:
                    result["action_taken"] = "hold_existing"
                    logger.info(f"Already have position for {symbol} - holding")
                    
            elif signal == 2:  # Short
                if not has_position:
                    # Открытие короткой позиции
                    market_data = self.get_market_data(symbol, limit=1)
                    if not market_data:
                        raise Exception("Failed to fetch market data for entry price")
                    
                    entry_price = market_data[0]["close"]
                    sl_price, tp_price = self.calculate_stop_loss_take_profit(entry_price, "Sell")
                    
                    order_response = self.place_order(
                        symbol=symbol,
                        side="Sell",
                        signal_confidence=confidence,
                        sl_price=sl_price,
                        tp_price=tp_price
                    )
                    
                    result["action_taken"] = "open_short"
                    result["order_id"] = order_response.get("result", {}).get("orderId")
                    logger.info(f"Opened SHORT position for {symbol}")
                else:
                    result["action_taken"] = "hold_existing"
                    logger.info(f"Already have position for {symbol} - holding")
                    
            elif signal == 3:  # Close
                if has_position:
                    # Закрытие позиции
                    close_response = self.close_position(symbol)
                    result["action_taken"] = "close_position"
                    result["order_id"] = close_response.get("result", {}).get("orderId")
                    logger.info(f"Closed position for {symbol}")
                else:
                    result["action_taken"] = "no_position"
                    logger.info(f"No position to close for {symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing model signal for {symbol}: {e}")
            return {
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "action_taken": None,
                "order_id": None,
                "error": str(e)
            }
    
    def auto_trade(self, symbol: str, model_signal_generator, polling_interval: int = 60):
        """
        Автоматическая торговля на основе сигналов модели
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        model_signal_generator : callable
            Функция или генератор, возвращающий сигналы от модели (signal, confidence)
        polling_interval : int, optional
            Интервал опроса сигнала в секундах (по умолчанию 60)
        """
        logger.info(f"Starting auto trading for {symbol} with polling interval {polling_interval}s")
        self.is_running = True
        
        try:
            while self.is_running:
                try:
                    # Получение сигнала от модели
                    signal, confidence = model_signal_generator()
                    
                    # Обработка сигнала
                    result = self.process_model_signal(symbol, signal, confidence)
                    
                    # Сохранение метрик в базу данных
                    if result["action_taken"] and result["action_taken"] not in ["hold", "hold_existing", "no_position"]:
                        self._save_trade_metrics(result)
                    
                    # Ожидание до следующего опроса
                    time.sleep(polling_interval)
                    
                except Exception as e:
                    logger.error(f"Error in auto trading loop for {symbol}: {e}")
                    time.sleep(polling_interval)  # Продолжаем даже при ошибке
                    
        except KeyboardInterrupt:
            logger.info("Auto trading stopped by user")
        finally:
            self.is_running = False
            logger.info("Auto trading finished")
    
    def _save_trade_metrics(self, trade_result: Dict[str, Any]):
        """
        Сохранение метрик торговли в базу данных
        
        Parameters
        ----------
        trade_result : Dict[str, Any]
            Результат обработки сигнала
        """
        try:
            metrics = {
                "timestamp": datetime.now(),
                "symbol": trade_result["symbol"],
                "strategy_name": "model_based",
                "position_side": trade_result.get("action_taken", "").replace("open_", "").replace("close_", ""),
                "entry_price": 0,  # Будет заполнено позже из данных ордера
                "exit_price": 0,   # Будет заполнено позже из данных ордера
                "position_size": 0,
                "pnl": 0,
                "pnl_percentage": 0,
                "commission": 0,
                "trade_duration": timedelta(seconds=0)
            }
            
            # Сохранение метрик в базу данных
            self.db_manager.save_trading_metrics(metrics)
            logger.info(f"Saved trade metrics for {trade_result['symbol']}")
            
        except Exception as e:
            logger.error(f"Error saving trade metrics: {e}")
    
    async def async_place_order(self, symbol: str, side: str, order_type: str = "Market", 
                               qty: Optional[float] = None, signal_confidence: float = 1.0,
                               sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Асинхронное размещение ордера на бирже
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        side : str
            Сторона ордера ("Buy" для LONG, "Sell" для SHORT)
        order_type : str, optional
            Тип ордера ("Market" или "Limit", по умолчанию "Market")
        qty : Optional[float], optional
            Количество (если не указано, рассчитывается автоматически)
        signal_confidence : float, optional
            Уровень уверенности сигнала (0.0 - 1.0, по умолчанию 1.0)
        sl_price : Optional[float], optional
            Цена стоп-лосса
        tp_price : Optional[float], optional
            Цена тейк-профита
            
        Returns
        -------
        Dict[str, Any]
            Результат размещения ордера
        """
        try:
            async with self.async_api_client as client:
                # Расчет размера позиции, если не указан
                if qty is None:
                    qty = await self.async_calculate_position_size(symbol, signal_confidence)
                
                if qty <= 0:
                    raise Exception("Invalid position size")
                
                # Установка плеча
                await client.set_leverage(
                    symbol=symbol,
                    buy_leverage=self.config.trading.leverage,
                    sell_leverage=self.config.trading.leverage,
                    category="linear"
                )
                
                # Размещение основного ордера
                order_response = await client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    qty=qty,
                    category="linear"
                )
                
                if order_response.get("retCode") != 0:
                    raise Exception(f"Failed to place order: {order_response.get('retMsg')}")
                
                order_id = order_response.get("result", {}).get("orderId")
                logger.info(f"Placed {side} order for {symbol}: {order_id}")
                
                # Сохранение информации об ордере
                self.open_orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "order_id": order_id,
                    "timestamp": datetime.now()
                }
                
                # Размещение стоп-лосса и тейк-профита, если включены
                if self.config.trading.enable_stop_loss and sl_price:
                    sl_side = "Sell" if side == "Buy" else "Buy"
                    sl_response = await client.place_order(
                        symbol=symbol,
                        side=sl_side,
                        order_type="Stop",
                        qty=qty,
                        price=sl_price,
                        reduce_only=True,
                        category="linear"
                    )
                    if sl_response.get("retCode") == 0:
                        sl_order_id = sl_response.get("result", {}).get("orderId")
                        logger.info(f"Placed SL order for {symbol}: {sl_order_id}")
                
                if self.config.trading.enable_take_profit and tp_price:
                    tp_side = "Sell" if side == "Buy" else "Buy"
                    tp_response = await client.place_order(
                        symbol=symbol,
                        side=tp_side,
                        order_type="Limit",
                        qty=qty,
                        price=tp_price,
                        reduce_only=True,
                        category="linear"
                    )
                    if tp_response.get("retCode") == 0:
                        tp_order_id = tp_response.get("result", {}).get("orderId")
                        logger.info(f"Placed TP order for {symbol}: {tp_order_id}")
                
                return order_response
                
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            raise
    
    async def async_calculate_position_size(self, symbol: str, signal_confidence: float = 1.0) -> float:
        """
        Асинхронный расчет размера позиции на основе доступного баланса и конфиденциальности сигнала
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        signal_confidence : float, optional
            Уровень уверенности сигнала (0.0 - 1.0, по умолчанию 1.0)
            
        Returns
        -------
        float
            Размер позиции в базовой валюте
        """
        try:
            async with self.async_api_client as client:
                # Получение баланса кошелька
                balance_response = await client.get_wallet_balance(coin="USDT")
                
                if balance_response.get("retCode") != 0:
                    raise Exception(f"Failed to fetch wallet balance: {balance_response.get('retMsg')}")
                
                balance_info = balance_response.get("result", {}).get("list", [])
                if not balance_info:
                    available_balance = 0
                else:
                    coins = balance_info[0].get("coin", [])
                    available_balance = 0
                    for coin_info in coins:
                        if coin_info.get("coin") == "USDT":
                            available_balance = float(coin_info.get("availableToWithdraw", 0))
                            break
                
                if available_balance <= 0:
                    logger.warning("No available balance for position sizing")
                    return 0.0
                
                # Получение текущей цены символа
                tickers_response = await client.get_tickers(category="linear")
                if tickers_response.get("retCode") != 0:
                    raise Exception(f"Failed to fetch tickers: {tickers_response.get('retMsg')}")
                
                symbol_price = None
                for ticker in tickers_response.get("result", {}).get("list", []):
                    if ticker.get("symbol") == symbol:
                        symbol_price = float(ticker.get("lastPrice", 0))
                        break
                
                if not symbol_price or symbol_price <= 0:
                    logger.warning(f"Could not fetch price for {symbol}")
                    return 0.0
                
                # Расчет размера позиции
                position_fraction = self.config.trading.position_size_fraction * signal_confidence
                position_value = available_balance * position_fraction
                position_size = position_value / symbol_price
                
                logger.info(f"Calculated position size for {symbol}: {position_size:.6f} ({position_value:.2f} USDT)")
                return position_size
                
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            return 0.0
    
    def get_system_metrics(self) -> List[Dict[str, Any]]:
        """
        Получение системных метрик для мониторинга
        
        Returns
        -------
        List[Dict[str, Any]]
            Список системных метрик
        """
        metrics = []
        timestamp = datetime.now()
        
        try:
            # Получение баланса кошелька
            balance = self.get_wallet_balance("USDT")
            if balance:
                metrics.append({
                    "timestamp": timestamp,
                    "name": "wallet_balance",
                    "value": balance.get("wallet_balance", 0),
                    "tags": {"coin": "USDT"}
                })
                
                metrics.append({
                    "timestamp": timestamp,
                    "name": "available_balance",
                    "value": balance.get("available_balance", 0),
                    "tags": {"coin": "USDT"}
                })
            
            # Получение открытых позиций
            positions = self.get_positions()
            metrics.append({
                "timestamp": timestamp,
                "name": "open_positions_count",
                "value": len(positions),
                "tags": {}
            })
            
            # Общая прибыль/убыток по открытым позициям
            total_pnl = sum(pos.get("pnl", 0) for pos in positions)
            metrics.append({
                "timestamp": timestamp,
                "name": "total_unrealized_pnl",
                "value": total_pnl,
                "tags": {}
            })
            
            # Сохранение метрик в базу данных
            self.db_manager.save_system_metrics(metrics)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def stop_trading(self):
        """
        Остановка автоматической торговли
        """
        self.is_running = False
        logger.info("Trading stopped")
