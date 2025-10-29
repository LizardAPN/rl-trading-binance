# Bybit Trading Module

A comprehensive trading module for Bybit exchange integration with support for live trading, risk management, real-time data streaming, and performance monitoring.

## Features

- **Multiple Trading Modes**: Demo, Paper, and Live trading
- **Risk Management**: Automatic position sizing and risk controls
- **Real-time Data Streaming**: WebSocket integration for market data
- **Performance Monitoring**: Real-time metrics, PnL tracking, and Sharpe ratio calculation
- **Telegram Notifications**: Trade alerts and error notifications
- **Comprehensive Logging**: JSON-formatted trade and error logs
- **Automatic Reconnection**: Robust error handling and retry mechanisms
- **Unified Margin Trading**: Support for USDT perpetual contracts

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Install additional dependencies for Bybit trading:
```bash
pip install pybit python-dotenv
```

## Configuration

### Environment Variables

Create a `.env` file in the project root with your API keys:

```bash
# Bybit API Keys
BYBIT_MAINNET_API_KEY=your_mainnet_api_key_here
BYBIT_MAINNET_SECRET=your_mainnet_secret_here
BYBIT_TESTNET_API_KEY=your_testnet_api_key_here
BYBIT_TESTNET_SECRET=your_testnet_secret_here

# Telegram Bot Configuration (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

### Trading Configuration

Configure trading parameters in `configs/live_trading.py`:

```python
cfg.live_trading = type('LiveTradingConfig', (), {
    'enabled': True,
    'mode': "demo",  # demo/paper/live
    'symbols': ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    'check_interval': 60,  # seconds
    'max_position_pct': 0.1,
    'telegram_alerts': True
})()
```

## Usage

### Command Line Interface

Start live trading with the command line interface:

```bash
# Demo mode (testnet)
python live_trading.py configs/live_trading.py --mode demo

# Paper trading mode (testnet with real balance)
python live_trading.py configs/live_trading.py --mode paper

# Live trading mode (mainnet)
python live_trading.py configs/live_trading.py --mode live

# Specify custom symbols
python live_trading.py configs/live_trading.py --mode live --symbols BTCUSDT,ETHUSDT
```

### Programmatic Usage

```python
from bybit_trading.engine import BybitTradingEngine
from bybit_trading.config import TradingMode

# Initialize trading engine
engine = BybitTradingEngine(
    mode=TradingMode.LIVE,
    symbols=["BTCUSDT", "ETHUSDT"],
    config={
        "check_interval": 60,
        "max_position_pct": 0.1
    }
)

# Start trading
import asyncio
asyncio.run(engine.start())

# Execute trades
result = asyncio.run(engine.execute_trade(action=1, symbol="BTCUSDT"))  # Buy
result = asyncio.run(engine.execute_trade(action=2, symbol="BTCUSDT"))  # Sell
result = asyncio.run(engine.execute_trade(action=3, symbol="BTCUSDT"))  # Close position
```

## Trading Modes

| Mode | Network | Balance | Description |
|------|---------|---------|-------------|
| `demo` | Testnet | Virtual | Testing with virtual funds |
| `paper` | Testnet | Real | Testing with real balance on testnet |
| `live` | Mainnet | Real | Live trading with real funds |

## Risk Management

The risk management system automatically calculates position sizes based on your account balance and risk parameters:

```python
from bybit_trading.risk import RiskManager

# Initialize with 10% max position size
risk_manager = RiskManager(max_position_size=0.1)

# Calculate position size
position_size = risk_manager.calculate_position_size(balance=10000, current_price=40000)
```

## Monitoring and Metrics

The system tracks real-time performance metrics:

- **Total PnL**: Cumulative profit and loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **ROI**: Return on investment

## Testing

Run unit tests:

```bash
python -m unittest tests/test_config.py
python -m unittest tests/test_risk.py
python -m unittest tests/test_execution.py
python -m unittest tests/test_streaming.py
python -m unittest tests/test_monitoring.py
python -m unittest tests/test_engine.py
```

Or run all tests:

```bash
python -m unittest discover tests
```

## Security

- Never commit API keys to version control
- Use `.env` files for sensitive configuration
- Enable two-factor authentication on your Bybit account
- Use read-only API keys for monitoring applications

## License

This project is licensed under the MIT License.
