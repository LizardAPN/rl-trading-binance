from config import cfg

# Live trading configuration
cfg.live_trading = type('LiveTradingConfig', (), {
    'enabled': True,
    'mode': "demo",  # demo/paper/live
    'symbols': ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    'check_interval': 60,  # seconds
    'max_position_pct': 0.1,
    'telegram_alerts': True,
    'telegram_bot_token': "",  # Set in .env file
    'telegram_chat_id': ""     # Set in .env file
})()
