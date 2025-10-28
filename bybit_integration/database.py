# bybit_integration/database.py
"""
Модуль для работы с базой данных PostgreSQL/TimescaleDB
"""
import logging
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

from config import DatabaseConfig


class DatabaseManager:
    """
    Менеджер для работы с базой данных PostgreSQL/TimescaleDB
    """
    
    def __init__(self, config: DatabaseConfig):
        """
        Инициализация менеджера базы данных
        
        Parameters
        ----------
        config : DatabaseConfig
            Конфигурация подключения к базе данных
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Проверяем подключение при инициализации
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()
                    self.logger.info(f"Connected to PostgreSQL: {version[0]}")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Контекстный менеджер для получения соединения с базой данных
        """
        print(f"Database config: host={self.config.host}, db={self.config.database}, user={self.config.username}, password_provided={bool(self.config.password)}")
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password
            )
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def initialize_tables(self):
        """
        Инициализация таблиц в базе данных
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Создание таблицы для рыночных данных
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS market_data (
                            timestamp TIMESTAMPTZ NOT NULL,
                            symbol VARCHAR(20) NOT NULL,
                            open_price DECIMAL(20, 8),
                            high_price DECIMAL(20, 8),
                            low_price DECIMAL(20, 8),
                            close_price DECIMAL(20, 8),
                            volume DECIMAL(20, 8),
                            trades_count INTEGER,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            PRIMARY KEY (timestamp, symbol)  
                        );
                    """)
                    
                    # Создание hypertable для TimescaleDB
                    if self.config.timescaledb_enabled:
                        cur.execute("""
                            SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);
                        """)
                    
                    # Создание индексов
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp 
                        ON market_data (symbol, timestamp DESC);
                    """)
                    
                    # Создание таблицы для метрик торговли
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS trading_metrics (
                            timestamp TIMESTAMPTZ NOT NULL,
                            symbol VARCHAR(20) NOT NULL,
                            strategy_name VARCHAR(100),
                            position_side VARCHAR(10),
                            entry_price DECIMAL(20, 8),
                            exit_price DECIMAL(20, 8),
                            position_size DECIMAL(20, 8),
                            pnl DECIMAL(20, 8),
                            pnl_percentage DECIMAL(10, 4),
                            commission DECIMAL(20, 8),
                            trade_duration INTERVAL,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            PRIMARY KEY (timestamp, symbol)
                        );
                    """)
                    
                    # Создание hypertable для TimescaleDB
                    if self.config.timescaledb_enabled:
                        cur.execute("""
                            SELECT create_hypertable('trading_metrics', 'timestamp', if_not_exists => TRUE);
                        """)
                    
                    # Создание индексов
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trading_metrics_symbol_timestamp 
                        ON trading_metrics (symbol, timestamp DESC);
                    """)
                    
                    # Создание таблицы для системных метрик
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS system_metrics (
                            timestamp TIMESTAMPTZ NOT NULL,
                            metric_name VARCHAR(100) NOT NULL,
                            metric_value DECIMAL(20, 8),
                            tags JSONB,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            PRIMARY KEY (timestamp, metric_name) 
                        );
                    """)
                    
                    # Создание hypertable для TimescaleDB
                    if self.config.timescaledb_enabled:
                        cur.execute("""
                            SELECT create_hypertable('system_metrics', 'timestamp', if_not_exists => TRUE);
                        """)
                    
                    # Создание индексов
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_system_metrics_name_timestamp 
                        ON system_metrics (metric_name, timestamp DESC);
                    """)
                    
                    conn.commit()
                    self.logger.info("Database tables initialized successfully")
                    
        except Exception as e:
            self.logger.error(f"Failed to initialize database tables: {e}")
            raise
    
    def save_market_data(self, data: List[Dict[str, Any]]) -> int:
        """
        Сохранение рыночных данных в базу данных
        
        Parameters
        ----------
        data : List[Dict[str, Any]]
            Список словарей с рыночными данными
            
        Returns
        -------
        int
            Количество успешно вставленных записей
        """
        if not data:
            return 0
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    inserted_count = 0
                    
                    for record in data:
                        cur.execute("""
                            INSERT INTO market_data (
                                timestamp, symbol, open_price, high_price, 
                                low_price, close_price, volume, trades_count
                            ) VALUES (%(timestamp)s, %(symbol)s, %(open)s, %(high)s, 
                                     %(low)s, %(close)s, %(volume)s, %(trades)s)
                            ON CONFLICT DO NOTHING;
                        """, {
                            'timestamp': record['timestamp'],
                            'symbol': record['symbol'],
                            'open': record['open'],
                            'high': record['high'],
                            'low': record['low'],
                            'close': record['close'],
                            'volume': record['volume'],
                            'trades': record.get('trades', 0)
                        })
                        inserted_count += cur.rowcount
                    
                    conn.commit()
                    self.logger.info(f"Saved {inserted_count} market data records")
                    return inserted_count
                    
        except Exception as e:
            self.logger.error(f"Failed to save market data: {e}")
            raise
    
    def save_trading_metrics(self, metrics: Dict[str, Any]) -> int:
        """
        Сохранение метрик торговли в базу данных
        
        Parameters
        ----------
        metrics : Dict[str, Any]
            Словарь с метриками торговли
            
        Returns
        -------
        int
            Количество успешно вставленных записей
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trading_metrics (
                            timestamp, symbol, strategy_name, position_side,
                            entry_price, exit_price, position_size, pnl,
                            pnl_percentage, commission, trade_duration
                        ) VALUES (
                            %(timestamp)s, %(symbol)s, %(strategy_name)s, %(position_side)s,
                            %(entry_price)s, %(exit_price)s, %(position_size)s, %(pnl)s,
                            %(pnl_percentage)s, %(commission)s, %(trade_duration)s
                        );
                    """, metrics)
                    
                    conn.commit()
                    self.logger.info("Saved trading metrics")
                    return cur.rowcount
                    
        except Exception as e:
            self.logger.error(f"Failed to save trading metrics: {e}")
            raise
    
    def save_system_metrics(self, metrics: List[Dict[str, Any]]) -> int:
        """
        Сохранение системных метрик в базу данных
        
        Parameters
        ----------
        metrics : List[Dict[str, Any]]
            Список словарей с системными метриками
            
        Returns
        -------
        int
            Количество успешно вставленных записей
        """
        if not metrics:
            return 0
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    inserted_count = 0
                    
                    for metric in metrics:
                        cur.execute("""
                            INSERT INTO system_metrics (
                                timestamp, metric_name, metric_value, tags
                            ) VALUES (%(timestamp)s, %(name)s, %(value)s, %(tags)s);
                        """, {
                            'timestamp': metric['timestamp'],
                            'name': metric['name'],
                            'value': metric['value'],
                            'tags': metric.get('tags', {})
                        })
                        inserted_count += cur.rowcount
                    
                    conn.commit()
                    self.logger.info(f"Saved {inserted_count} system metrics")
                    return inserted_count
                    
        except Exception as e:
            self.logger.error(f"Failed to save system metrics: {e}")
            raise
    
    def get_latest_market_data(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """
        Получение последних рыночных данных для символа
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        limit : int, optional
            Количество записей (по умолчанию 100)
            
        Returns
        -------
        pd.DataFrame
            DataFrame с рыночными данными
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT timestamp, open_price, high_price, low_price, 
                           close_price, volume, trades_count
                    FROM market_data
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    LIMIT %s;
                """
                df = pd.read_sql_query(query, conn, params=[symbol, limit])
                return df
                
        except Exception as e:
            self.logger.error(f"Failed to fetch market data: {e}")
            raise
    
    def get_trading_metrics_summary(self, symbol: Optional[str] = None, 
                                   days: int = 30) -> Dict[str, Any]:
        """
        Получение сводки метрик торговли
        
        Parameters
        ----------
        symbol : Optional[str], optional
            Торговая пара (если не указано, для всех пар)
        days : int, optional
            Количество дней для анализа (по умолчанию 30)
            
        Returns
        -------
        Dict[str, Any]
            Сводка метрик торговли
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    where_clause = "WHERE timestamp >= NOW() - INTERVAL '%s days'" % days
                    if symbol:
                        where_clause += f" AND symbol = '{symbol}'"
                    
                    query = f"""
                        SELECT 
                            COUNT(*) as total_trades,
                            SUM(pnl) as total_pnl,
                            AVG(pnl) as avg_pnl,
                            AVG(pnl_percentage) as avg_pnl_percentage,
                            SUM(commission) as total_commission,
                            COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                            COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
                            AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_winning_trade,
                            AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_losing_trade
                        FROM trading_metrics
                        {where_clause};
                    """
                    
                    cur.execute(query)
                    result = cur.fetchone()
                    
                    # Вычисление дополнительных метрик
                    if result and result['total_trades'] > 0:
                        win_rate = result['winning_trades'] / result['total_trades'] if result['total_trades'] > 0 else 0
                        profit_factor = (
                            abs(result['avg_winning_trade'] * result['winning_trades']) / 
                            abs(result['avg_losing_trade'] * result['losing_trades'])
                        ) if result['losing_trades'] > 0 and result['avg_losing_trade'] is not None else 0
                        
                        result['win_rate'] = win_rate
                        result['profit_factor'] = profit_factor
                    
                    return dict(result) if result else {}
                    
        except Exception as e:
            self.logger.error(f"Failed to fetch trading metrics summary: {e}")
            raise
