# bybit_integration/example_usage.py
"""
Пример использования системы автоматической торговли Bybit
"""
import asyncio
import logging
import os
import time
from datetime import datetime
import numpy as np

from config import BybitIntegrationConfig
from trader import BybitTrader


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def example_model_signal_generator():
    """
    Пример генератора сигналов от модели RL.
    В реальной системе здесь будет интеграция с обученной моделью.
    
    Returns
    -------
    tuple
        Кортеж (сигнал, уверенность), где:
        - сигнал: 0 (Hold), 1 (Long), 2 (Short), 3 (Close)
        - уверенность: уровень уверенности от 0.0 до 1.0
    """
    # В примере случайным образом генерируем сигналы
    # В реальной системе здесь будет вызов обученной RL-модели
    signals = [0, 1, 2, 3]
    signal = np.random.choice(signals, p=[0.7, 0.1, 0.1, 0.1])  # Чаще держим позиции
    confidence = np.random.uniform(0.5, 1.0)  # Уверенность от 0.5 до 1.0
    
    return signal, confidence


def main_sync_example():
    """
    Пример синхронного использования трейдера
    """
    logger.info("Starting synchronous Bybit trading example")
    
    # Создание конфигурации
    config = BybitIntegrationConfig()
    
    # Для демонстрации используем демо режим
    config.api.mode = "demo"
    
    # Создание трейдера
    trader = BybitTrader(config)
    
    # Получение баланса кошелька
    try:
        balance = trader.get_wallet_balance("USDT")
        logger.info(f"Wallet balance: {balance}")
    except Exception as e:
        logger.error(f"Failed to get wallet balance: {e}")
    
    # Получение рыночных данных
    try:
        market_data = trader.get_market_data("BTCUSDT", interval="1", limit=10)
        logger.info(f"Retrieved {len(market_data)} candles for BTCUSDT")
        if market_data:
            logger.info(f"Latest price: {market_data[0]['close']}")
    except Exception as e:
        logger.error(f"Failed to get market data: {e}")
    
    # Получение текущих позиций
    try:
        positions = trader.get_positions("BTCUSDT")
        logger.info(f"Open positions: {len(positions)}")
        for pos in positions:
            logger.info(f"Position: {pos['symbol']} {pos['side']} {pos['size']} @ {pos['entry_price']}")
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
    
    # Обработка одного сигнала от модели
    try:
        signal, confidence = example_model_signal_generator()
        result = trader.process_model_signal("BTCUSDT", signal, confidence)
        logger.info(f"Processed signal: {result}")
    except Exception as e:
        logger.error(f"Failed to process model signal: {e}")
    
    # Получение системных метрик
    try:
        metrics = trader.get_system_metrics()
        logger.info(f"Collected {len(metrics)} system metrics")
        for metric in metrics:
            logger.info(f"Metric: {metric['name']} = {metric['value']}")
    except Exception as e:
        logger.error(f"Failed to collect system metrics: {e}")


async def main_async_example():
    """
    Пример асинхронного использования трейдера
    """
    logger.info("Starting asynchronous Bybit trading example")
    
    # Создание конфигурации
    config = BybitIntegrationConfig()
    
    # Для демонстрации используем демо режим
    config.api.mode = "demo"
    
    # Создание трейдера
    trader = BybitTrader(config)
    
    # Асинхронное получение рыночных данных
    try:
        market_data = trader.get_market_data("ETHUSDT", interval="5", limit=20)
        logger.info(f"Retrieved {len(market_data)} candles for ETHUSDT")
        if market_data:
            logger.info(f"Latest price: {market_data[0]['close']}")
    except Exception as e:
        logger.error(f"Failed to get market data: {e}")
    
    # Асинхронный расчет размера позиции
    try:
        position_size = await trader.async_calculate_position_size("ETHUSDT", signal_confidence=0.8)
        logger.info(f"Calculated position size for ETHUSDT: {position_size}")
    except Exception as e:
        logger.error(f"Failed to calculate position size: {e}")
    
    # Асинхронное размещение ордера (в демо режиме не будет выполнено реальных сделок)
    try:
        # Только для демонстрации - в реальной системе используйте осторожно!
        if not config.api.is_demo:
            order_result = await trader.async_place_order(
                symbol="ETHUSDT",
                side="Buy",
                signal_confidence=0.9,
                qty=0.1  # Для демонстрации фиксированное количество
            )
            logger.info(f"Placed order: {order_result}")
        else:
            logger.info("Skipping order placement in demo mode")
    except Exception as e:
        logger.error(f"Failed to place order: {e}")


def auto_trading_example():
    """
    Пример автоматической торговли на основе сигналов модели
    """
    logger.info("Starting auto trading example")
    
    # Создание конфигурации
    config = BybitIntegrationConfig()
    
    # Для демонстрации используем демо режим
    config.api.mode = "demo"
    
    # Создание трейдера
    trader = BybitTrader(config)
    
    # Запуск автоматической торговли (в демо режиме)
    # В реальной системе используйте меньший интервал (например, 60 секунд)
    logger.info("Starting auto trading loop (will run for 5 minutes in demo mode)")
    
    # Для демонстрации запустим только на 5 минут
    start_time = time.time()
    duration = 300  # 5 минут
    
    try:
        while time.time() - start_time < duration:
            # Получение сигнала от модели
            signal, confidence = example_model_signal_generator()
            
            # Обработка сигнала
            result = trader.process_model_signal("BTCUSDT", signal, confidence)
            logger.info(f"Auto trade result: {result['action_taken']}")
            
            # Получение системных метрик
            metrics = trader.get_system_metrics()
            logger.info(f"System metrics collected: {len(metrics)} items")
            
            # Пауза между итерациями (в реальной системе может быть 60 секунд)
            time.sleep(30)  # 30 секунд для демонстрации
            
    except KeyboardInterrupt:
        logger.info("Auto trading interrupted by user")
    except Exception as e:
        logger.error(f"Error in auto trading: {e}")
    finally:
        trader.stop_trading()
        logger.info("Auto trading finished")


if __name__ == "__main__":
    logger.info("Bybit Integration Examples")
    
    # Пример синхронного использования
    main_sync_example()
    
    # Пример асинхронного использования
    asyncio.run(main_async_example())
    
    # Пример автоматической торговли
    auto_trading_example()
    
    logger.info("All examples completed")
