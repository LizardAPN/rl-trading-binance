from pydantic import BaseModel
from typing import List, Optional


class LiveTradingConfig(BaseModel):
    enabled: bool = True
    mode: str = "demo"  # demo/paper/live
    symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    check_interval: int = 60  # seconds
    max_position_pct: float = 0.1
    telegram_alerts: bool = True
    telegram_bot_token: str = ""  # Set in .env file
    telegram_chat_id: str = ""    # Set in .env file
