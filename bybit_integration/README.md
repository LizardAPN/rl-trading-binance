# Bybit Integration Module

Модуль интеграции с биржей Bybit для автоматической торговли на основе сигналов RL-модели.

## Описание

Этот модуль предоставляет полный набор инструментов для автоматической торговли на бирже Bybit с использованием сигналов от RL-модели. Он включает в себя:

- Клиент API для взаимодействия с Bybit (поддержка демо и реального режимов)
- Систему сохранения рыночных данных и метрик в PostgreSQL/TimescaleDB
- Автоматическую торговлю с управлением рисками
- Поддержку как синхронной, так и асинхронной работы

## Структура модуля

```
bybit_integration/
├── config.py          # Конфигурация модуля
├── api_client.py      # Клиент Bybit API (синхронный и асинхронный)
├── database.py        # Работа с базой данных PostgreSQL/TimescaleDB
├── trader.py          # Основной класс для автоматической торговли
├── example_usage.py   # Примеры использования
└── README.md          # Документация
```

## Компоненты

### 1. Конфигурация (config.py)

Центральный файл конфигурации, содержащий настройки для:
- Подключения к Bybit API (ключи, режимы работы)
- Подключения к базе данных PostgreSQL/TimescaleDB
- Параметров торговли (плечо, размер позиции, стоп-лосс/тейк-профит)

### 2. Клиент API (api_client.py)

Реализация клиентов для работы с Bybit API:
- `BybitAPIClient` - синхронный клиент
- `AsyncBybitAPIClient` - асинхронный клиент

Поддерживаемые функции:
- Получение рыночных данных (свечи, цены, объемы)
- Получение информации о балансе и позициях
- Размещение, отмена и управление ордерами
- Установка плеча

### 3. База данных (database.py)

Менеджер для работы с PostgreSQL/TimescaleDB:
- Инициализация таблиц для хранения данных
- Сохранение рыночных данных
- Сохранение метрик торговли
- Сохранение системных метрик
- Получение сводной статистики

### 4. Трейдер (trader.py)

Основной класс для автоматической торговли:
- Расчет размера позиции на основе баланса и уверенности сигнала
- Открытие/закрытие позиций
- Управление рисками (стоп-лосс, тейк-профит, трейлинг стоп)
- Обработка сигналов от RL-модели
- Автоматическая торговля по расписанию
- Сохранение метрик в базу данных

### 5. Примеры использования (example_usage.py)

Демонстрационные примеры:
- Синхронное использование трейдера
- Асинхронное использование трейдера
- Автоматическая торговля на основе сигналов модели

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Установите переменные окружения:
```bash
export BYBIT_API_KEY="your_api_key"
export BYBIT_API_SECRET="your_api_secret"
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="bybit_trading"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
```

3. Убедитесь, что PostgreSQL/TimescaleDB запущена и доступна

## Настройка

Конфигурация осуществляется через класс `BybitIntegrationConfig`:

```python
from bybit_integration.config import BybitIntegrationConfig

config = BybitIntegrationConfig()
# Настройка режима (demo/real)
config.api.mode = "demo"  # или "real"
# Настройка торговых параметров
config.trading.symbol = "BTCUSDT"
config.trading.leverage = 10
config.trading.position_size_fraction = 0.1
```

## Использование

### Базовый пример

```python
from bybit_integration.config import BybitIntegrationConfig
from bybit_integration.trader import BybitTrader

# Создание конфигурации
config = BybitIntegrationConfig()
config.api.mode = "demo"  # Демо режим для тестирования

# Создание трейдера
trader = BybitTrader(config)

# Получение баланса
balance = trader.get_wallet_balance("USDT")
print(f"Баланс: {balance}")

# Получение рыночных данных
market_data = trader.get_market_data("BTCUSDT", interval="1", limit=100)

# Обработка сигнала от модели
signal = 1  # LONG сигнал
confidence = 0.8  # Уверенность 80%
result = trader.process_model_signal("BTCUSDT", signal, confidence)
```

### Автоматическая торговля

```python
def model_signal_generator():
    """Функция, возвращающая сигналы от вашей RL-модели"""
    # Здесь интеграция с вашей RL-моделью
    return signal, confidence

# Запуск автоматической торговли
trader.auto_trade("BTCUSDT", model_signal_generator, polling_interval=60)
```

### Асинхронное использование

```python
import asyncio

async def async_example():
    config = BybitIntegrationConfig()
    trader = BybitTrader(config)
    
    # Асинхронный расчет размера позиции
    position_size = await trader.async_calculate_position_size("BTCUSDT", 0.9)
    
    # Асинхронное размещение ордера
    order_result = await trader.async_place_order(
        symbol="BTCUSDT",
        side="Buy",
        signal_confidence=0.9
    )

# Запуск
asyncio.run(async_example())
```

## Основные возможности

### 1. Автоматическая торговля
- Обработка сигналов от RL-модели
- Автоматическое открытие/закрытие позиций
- Управление размером позиции на основе баланса и уверенности сигнала

### 2. Управление рисками
- Стоп-лосс (фиксированный процент)
- Тейк-профит (фиксированный процент)
- Трейлинг стоп
- Управление плечом

### 3. Хранение данных
- Сохранение рыночных данных в TimescaleDB
- Сохранение метрик торговли
- Сохранение системных метрик
- Получение сводной статистики

### 4. Мониторинг
- Получение баланса кошелька
- Получение открытых позиций
- Системные метрики (баланс, количество позиций, PnL)

## Безопасность

- API ключи передаются через переменные окружения
- Поддержка демо режима для тестирования
- Проверка состояния перед размещением ордеров
- Логирование всех операций

## Лицензия

MIT License

## Автор

Разработано для интеграции RL-моделей с биржей Bybit.
