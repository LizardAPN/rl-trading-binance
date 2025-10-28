# bybit_integration/api_client.py
"""
Клиент для работы с Bybit API
"""
import asyncio
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import aiohttp
import requests

from config import BybitAPIConfig


class BybitAPIClient:
    """
    Клиент для взаимодействия с Bybit API
    
    Поддерживает как демо, так и реальный режимы торговли
    """
    
    def __init__(self, config: BybitAPIConfig):
        """
        Инициализация клиента Bybit API
        
        Parameters
        ----------
        config : BybitAPIConfig
            Конфигурация для подключения к API
        """
        self.config = config
        self.session = requests.Session()
        
        # Установка заголовков по умолчанию
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        
        if self.config.api_key and self.config.api_secret:
            self.session.headers.update({
                'X-BAPI-API-KEY': self.config.api_key,
            })
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Генерация подписи для приватных запросов
        
        Parameters
        ----------
        params : Dict[str, Any]
            Параметры запроса
            
        Returns
        -------
        str
            Подпись для запроса
        """
        param_str = urlencode(sorted(params.items()))
        timestamp = str(int(time.time() * 1000))
        signature_data = timestamp + self.config.api_key + param_str
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None, is_private: bool = False) -> Dict[str, Any]:
        """
        Выполнение HTTP запроса к API
        
        Parameters
        ----------
        method : str
            HTTP метод (GET, POST, PUT, DELETE)
        endpoint : str
            Эндпоинт API
        params : Optional[Dict], optional
            Параметры запроса для GET запросов
        data : Optional[Dict], optional
            Данные для тела запроса для POST/PUT запросов
        is_private : bool, optional
            Флаг приватного запроса (требует подписи)
            
        Returns
        -------
        Dict[str, Any]
            Ответ от API
        """
        url = self.config.base_url + endpoint
        headers = self.session.headers.copy()
        
        # Для приватных запросов добавляем подпись и таймстамп
        if is_private and self.config.api_key and self.config.api_secret:
            timestamp = str(int(time.time() * 1000))
            signature, _ = self._generate_signature(params or {})
            
            headers.update({
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-SIGN': signature,
            })
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers, timeout=self.config.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=self.config.timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, headers=headers, timeout=self.config.timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params, headers=headers, timeout=self.config.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Получение информации о аккаунте
        
        Returns
        -------
        Dict[str, Any]
            Информация о аккаунте
        """
        return self._make_request('GET', '/v5/account/info', is_private=True)
    
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
            Баланс кошелька
        """
        params = {'coin': coin} if coin else {}
        return self._make_request('GET', '/v5/account/wallet-balance', params=params, is_private=True)
    
    def get_tickers(self, category: str = "linear") -> Dict[str, Any]:
        """
        Получение информации о ценах тикеров
        
        Parameters
        ----------
        category : str, optional
            Категория рынка (spot, linear, inverse) (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Информация о ценах тикеров
        """
        params = {'category': category}
        return self._make_request('GET', '/v5/market/tickers', params=params)
    
    def get_kline(self, symbol: str, interval: str, limit: int = 200, 
                  category: str = "linear") -> Dict[str, Any]:
        """
        Получение исторических свечей (kline)
        
        Parameters
        ----------
        symbol : str
            Торговая пара (например, "BTCUSDT")
        interval : str
            Интервал свечей (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
        limit : int, optional
            Количество свечей (по умолчанию 200, максимум 1000)
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Исторические свечи
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit,
            'category': category
        }
        return self._make_request('GET', '/v5/market/kline', params=params)
    
    def place_order(self, symbol: str, side: str, order_type: str, qty: float,
                   price: Optional[float] = None, time_in_force: str = "GTC",
                   reduce_only: bool = False, close_on_trigger: bool = False,
                   category: str = "linear") -> Dict[str, Any]:
        """
        Размещение ордера
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        side : str
            Сторона ордера ("Buy" или "Sell")
        order_type : str
            Тип ордера ("Market", "Limit")
        qty : float
            Количество
        price : Optional[float], optional
            Цена для лимитного ордера
        time_in_force : str, optional
            Время действия ордера (по умолчанию "GTC")
        reduce_only : bool, optional
            Флаг закрытия позиции (по умолчанию False)
        close_on_trigger : bool, optional
            Закрывать ли позицию при срабатывании (по умолчанию False)
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Результат размещения ордера
        """
        data = {
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': str(qty),
            'timeInForce': time_in_force,
            'reduceOnly': reduce_only,
            'closeOnTrigger': close_on_trigger,
            'category': category
        }
        
        if price is not None:
            data['price'] = str(price)
        
        return self._make_request('POST', '/v5/order/create', data=data, is_private=True)
    
    def get_open_orders(self, symbol: Optional[str] = None, category: str = "linear") -> Dict[str, Any]:
        """
        Получение списка открытых ордеров
        
        Parameters
        ----------
        symbol : Optional[str], optional
            Торговая пара (если не указано, возвращает все открытые ордера)
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Список открытых ордеров
        """
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request('GET', '/v5/order/realtime', params=params, is_private=True)
    
    def cancel_order(self, symbol: str, order_id: str, category: str = "linear") -> Dict[str, Any]:
        """
        Отмена ордера
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        order_id : str
            ID ордера
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Результат отмены ордера
        """
        data = {
            'symbol': symbol,
            'orderId': order_id,
            'category': category
        }
        return self._make_request('POST', '/v5/order/cancel', data=data, is_private=True)
    
    def get_positions(self, symbol: Optional[str] = None, category: str = "linear") -> Dict[str, Any]:
        """
        Получение информации о позициях
        
        Parameters
        ----------
        symbol : Optional[str], optional
            Торговая пара (если не указано, возвращает все позиции)
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Информация о позициях
        """
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request('GET', '/v5/position/list', params=params, is_private=True)
    
    def set_leverage(self, symbol: str, buy_leverage: int, sell_leverage: int, 
                     category: str = "linear") -> Dict[str, Any]:
        """
        Установка плеча для торговой пары
        
        Parameters
        ----------
        symbol : str
            Торговая пара
        buy_leverage : int
            Плечо для покупок
        sell_leverage : int
            Плечо для продаж
        category : str, optional
            Категория рынка (по умолчанию "linear")
            
        Returns
        -------
        Dict[str, Any]
            Результат установки плеча
        """
        data = {
            'symbol': symbol,
            'buyLeverage': str(buy_leverage),
            'sellLeverage': str(sell_leverage),
            'category': category
        }
        return self._make_request('POST', '/v5/position/set-leverage', data=data, is_private=True)


class AsyncBybitAPIClient(BybitAPIClient):
    """
    Асинхронный клиент для взаимодействия с Bybit API
    """
    
    def __init__(self, config: BybitAPIConfig):
        """
        Инициализация асинхронного клиента Bybit API
        
        Parameters
        ----------
        config : BybitAPIConfig
            Конфигурация для подключения к API
        """
        self.config = config
        self.session = None
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер для создания сессии"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер для закрытия сессии"""
        if self.session:
            await self.session.close()
    
    async def _make_async_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                                 data: Optional[Dict] = None, is_private: bool = False) -> Dict[str, Any]:
        """
        Асинхронное выполнение HTTP запроса к API
        
        Parameters
        ----------
        method : str
            HTTP метод (GET, POST, PUT, DELETE)
        endpoint : str
            Эндпоинт API
        params : Optional[Dict], optional
            Параметры запроса для GET запросов
        data : Optional[Dict], optional
            Данные для тела запроса для POST/PUT запросов
        is_private : bool, optional
            Флаг приватного запроса (требует подписи)
            
        Returns
        -------
        Dict[str, Any]
            Ответ от API
        """
        if not self.session:
            raise RuntimeError("Async client must be used within async context manager")
        
        url = self.config.base_url + endpoint
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        # Для приватных запросов добавляем API ключ
        if is_private and self.config.api_key:
            headers['X-BAPI-API-KEY'] = self.config.api_key
        
        # Для приватных запросов добавляем подпись и таймстамп
        if is_private and self.config.api_key and self.config.api_secret:
            timestamp = str(int(time.time() * 1000))
            signature, _ = self._generate_signature(params or {})
            
            headers.update({
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-SIGN': signature,
            })
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url, params=params, headers=headers, 
                                          timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == 'PUT':
                async with self.session.put(url, json=data, headers=headers,
                                          timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == 'DELETE':
                async with self.session.delete(url, params=params, headers=headers,
                                             timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            raise Exception(f"API request failed: {str(e)}")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Асинхронное получение информации о аккаунте"""
        return await self._make_async_request('GET', '/v5/account/info', is_private=True)
    
    async def get_wallet_balance(self, coin: str = "USDT") -> Dict[str, Any]:
        """Асинхронное получение баланса кошелька"""
        params = {'coin': coin} if coin else {}
        return await self._make_async_request('GET', '/v5/account/wallet-balance', params=params, is_private=True)
    
    async def get_tickers(self, category: str = "linear") -> Dict[str, Any]:
        """Асинхронное получение информации о ценах тикеров"""
        params = {'category': category}
        return await self._make_async_request('GET', '/v5/market/tickers', params=params)
    
    async def get_kline(self, symbol: str, interval: str, limit: int = 200,
                       category: str = "linear") -> Dict[str, Any]:
        """Асинхронное получение исторических свечей"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit,
            'category': category
        }
        return await self._make_async_request('GET', '/v5/market/kline', params=params)
    
    async def place_order(self, symbol: str, side: str, order_type: str, qty: float,
                         price: Optional[float] = None, time_in_force: str = "GTC",
                         reduce_only: bool = False, close_on_trigger: bool = False,
                         category: str = "linear") -> Dict[str, Any]:
        """Асинхронное размещение ордера"""
        data = {
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': str(qty),
            'timeInForce': time_in_force,
            'reduceOnly': reduce_only,
            'closeOnTrigger': close_on_trigger,
            'category': category
        }
        
        if price is not None:
            data['price'] = str(price)
        
        return await self._make_async_request('POST', '/v5/order/create', data=data, is_private=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None, category: str = "linear") -> Dict[str, Any]:
        """Асинхронное получение списка открытых ордеров"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
            
        return await self._make_async_request('GET', '/v5/order/realtime', params=params, is_private=True)
    
    async def cancel_order(self, symbol: str, order_id: str, category: str = "linear") -> Dict[str, Any]:
        """Асинхронная отмена ордера"""
        data = {
            'symbol': symbol,
            'orderId': order_id,
            'category': category
        }
        return await self._make_async_request('POST', '/v5/order/cancel', data=data, is_private=True)
    
    async def get_positions(self, symbol: Optional[str] = None, category: str = "linear") -> Dict[str, Any]:
        """Асинхронное получение информации о позициях"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
            
        return await self._make_async_request('GET', '/v5/position/list', params=params, is_private=True)
    
    async def set_leverage(self, symbol: str, buy_leverage: int, sell_leverage: int, 
                          category: str = "linear") -> Dict[str, Any]:
        """Асинхронная установка плеча для торговой пары"""
        data = {
            'symbol': symbol,
            'buyLeverage': str(buy_leverage),
            'sellLeverage': str(sell_leverage),
            'category': category
        }
        return await self._make_async_request('POST', '/v5/position/set-leverage', data=data, is_private=True)
