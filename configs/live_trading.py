from config import cfg

# Live trading configuration
cfg.live_trading.enabled = True
cfg.live_trading.mode = "demo"  # demo/paper/live
cfg.live_trading.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
cfg.live_trading.use_all_symbols = True  # Use all available symbols instead of hardcoded list
cfg.live_trading.check_interval = 3600  # seconds
cfg.live_trading.max_position_pct = 0.1
cfg.live_trading.telegram_alerts = True
cfg.live_trading.telegram_bot_token = ""  # Set in .env file
cfg.live_trading.telegram_chat_id = ""    # Set in .env file
