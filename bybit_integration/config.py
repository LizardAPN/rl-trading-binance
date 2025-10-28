# bybit_integration/config.py
"""
Конфигурация для интеграции с Bybit API
"""
import os
from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv 

load_dotenv()
class BybitAPIConfig(BaseModel):
    """
    Configuration for Bybit API connection
    """
    # API Keys - should be set via environment variables for security
    api_key: str = Field(default=os.getenv("BYBIT_API_KEY", ""))
    api_secret: str = Field(default=os.getenv("BYBIT_API_SECRET", ""))
    
    # Trading mode: 'demo' or 'real'
    mode: Literal["demo", "real"] = "demo"
    
    # Base URLs for different modes
    demo_url: str = "https://api-demo.bybit.com"
    real_url: str = "https://api.bybit.com"
    
    # Request timeout in seconds
    timeout: int = 10
    
    # Rate limiting (requests per second)
    rate_limit: int = 10
    
    @property
    def base_url(self) -> str:
        """Возвращает базовый URL в зависимости от режима"""
        return self.real_url if self.mode == "real" else self.demo_url
    
    @property
    def is_demo(self) -> bool:
        """Проверяет, используется ли демо режим"""
        return self.mode == "demo"


class DatabaseConfig(BaseModel):
    """
    Configuration for PostgreSQL/TimescaleDB connection
    """
    host: str = Field(default=os.getenv("DB_HOST", "localhost"))
    port: int = Field(default=int(os.getenv("DB_PORT", "5432")))
    database: str = Field(default=os.getenv("DB_NAME", "bybit_trading"))
    username: str = Field(default=os.getenv("DB_USER", "postgres"))
    password: str = Field(default=os.getenv("DB_PASSWORD", ""))
    timescaledb_enabled: bool = True


class TradingConfig(BaseModel):
    """
    Configuration for trading parameters
    """
    # Default symbol to trade
    symbol: str = "BTCUSDT"
    
    # Leverage settings
    leverage: int = 10
    
    # Position size as fraction of account balance (0.01 = 1%)
    position_size_fraction: float = 0.1
    
    # Risk management
    stop_loss_percent: float = 2.0  # 2%
    take_profit_percent: float = 4.0  # 4%
    trailing_stop_percent: float = 1.0  # 1%
    
    # Order settings
    slippage_tolerance: float = 0.005  # 0.5%
    
    # Enable/disable features
    enable_stop_loss: bool = True
    enable_take_profit: bool = True
    enable_trailing_stop: bool = True


class BybitIntegrationConfig(BaseModel):
    """
    Main configuration class for Bybit integration
    """
    api: BybitAPIConfig = BybitAPIConfig()
    database: DatabaseConfig = DatabaseConfig()
    trading: TradingConfig = TradingConfig()
    
    
    class Config:
        # Allow arbitrary attributes for nested configs
        arbitrary_types_allowed = True
