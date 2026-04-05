"""
Адаптер для Московской биржи (MOEX)
Реализует ExchangeInterface через ISS REST API.
"""

import os
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, time as dt_time, timedelta

from trading_lib.exchanges.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class MoexAdapter(ExchangeInterface):
    """Адаптер для Московской биржи"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация адаптера.
        
        Args:
            config: Конфигурация (токен не требуется для публичного API)
        """
        self.config = config or {}
        self.exchange_name = "moex"
        self.exchange_id = 3  # ID после вставки в БД
        self.base_url = "https://iss.moex.com/iss"
        self.session = requests.Session()
        
        logger.info("📈 Мосбиржа адаптер инициализирован")
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Получить баланс.
        Внимание: Требуется брокерский API для реальных данных.
        """
        # Заглушка
        balance = {"RUB": 100000.0}
        if currency:
            return {currency: balance.get(currency, 0)}
        return balance
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Получить свечи через ISS API.
        
        Args:
            symbol: Тикер фьючерса (например 'SiH6')
            interval: Интервал ('1m', '5m', '15m', '1h', '1d')
            limit: Количество свечей
        """
        # Маппинг интервалов MOEX
        interval_map = {
            '1m': 1,
            '5m': 5,
            '10m': 10,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '1d': 24
        }
        
        interval_minutes = interval_map.get(interval, 60)
        
        # Формируем URL для свечей фьючерса
        url = f"{self.base_url}/engines/futures/markets/forts/securities/{symbol}/candles"
        
        try:
            response = self.session.get(url, params={
                'interval': interval_minutes,
                'limit': limit
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Парсим данные (заглушка)
                return []
            else:
                logger.warning(f"Ошибка получения свечей {symbol}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Ошибка запроса к MOEX: {e}")
            return []
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Отменить ордер (требуется брокерский API)"""
        logger.info(f"❌ Отмена ордера {order_id} (заглушка)")
        return True
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получить открытые ордера"""
        return []
    
    def get_symbols(self) -> List[str]:
        """Получить список фьючерсов"""
        url = f"{self.base_url}/engines/futures/markets/forts/securities"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Парсим список фьючерсов
                return ['SiH6', 'RIH6', 'BRH6', 'EDH6']  # Заглушка
            return []
        except Exception as e:
            logger.error(f"Ошибка получения символов: {e}")
            return []
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """Получить информацию о бирже"""
        return {
            'name': self.exchange_name,
            'id': self.exchange_id,
            'type': 'futures',
            'timezone': 'Europe/Moscow',
            'is_24_7': False
        }
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Получить тикер"""
        url = f"{self.base_url}/engines/futures/markets/forts/securities/{symbol}"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                # Заглушка
                return {
                    'symbol': symbol,
                    'last_price': 100000.0,
                    'bid': 99950.0,
                    'ask': 100050.0,
                    'volume': 10000,
                    'high': 101000.0,
                    'low': 99000.0
                }
            return {'symbol': symbol, 'last_price': 0}
        except Exception as e:
            logger.error(f"Ошибка получения тикера: {e}")
            return {'symbol': symbol, 'last_price': 0}
    
    def test_connection(self) -> bool:
        """Проверить соединение с MOEX ISS API"""
        try:
            response = self.session.get(f"{self.base_url}/engines", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ошибка подключения к MOEX: {e}")
            return False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену"""
        ticker = self.get_ticker(symbol)
        return ticker.get('last_price')
    
    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = 'market', price: Optional[float] = None):
        """
        Разместить ордер.
        Внимание: Требуется брокерский API.
        """
        logger.info(f"📈 Размещение ордера {side} {quantity} {symbol} (заглушка)")
        return {'success': True, 'order_id': f'moex_{symbol}_{int(datetime.now().timestamp())}'}
    
    def get_positions(self, symbol: Optional[str] = None):
        """Получить позиции"""
        return []
    
    def get_trading_hours(self) -> Dict[str, Any]:
        """Вернуть торговые часы"""
        return {
            'start': '10:00',
            'end': '23:50',
            'timezone': 'Europe/Moscow',
            'weekends': [5, 6],
            'is_24_7': False
        }
    
    def is_trading_time(self) -> bool:
        """Проверить, идёт ли торговая сессия"""
        now = datetime.now()
        
        if now.weekday() >= 5:
            return False
        
        start = dt_time(10, 0)
        end = dt_time(23, 50)
        current = now.time()
        
        return start <= current <= end
