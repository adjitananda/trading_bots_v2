"""
Адаптер для Bybit.
Реализует ExchangeInterface используя существующий exchange_client.
"""

import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal

from trading_lib.trading.exchange_client import ExchangeClient
from trading_lib.exchanges.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class BybitAdapter(ExchangeInterface):
    """Адаптер для биржи Bybit"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация адаптера.
        
        Args:
            config: Конфигурация биржи (api_key, api_secret, testnet и т.д.)
        """
        self.config = config or {}
        self.exchange_name = "bybit"
        self.exchange_id = 1  # Bybit ID в БД
        self.client = ExchangeClient(self.exchange_name)
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """Получить баланс"""
        balance = self.client.get_balance()
        if currency:
            return {currency: balance.get(currency, 0)}
        return balance
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100):
        """Получить свечи"""
        return self.client.get_klines(symbol, interval, limit)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену"""
        return self.client.get_current_price(symbol)
    
    def place_order(self, symbol: str, side: str, quantity: float, 
                    order_type: str = 'market', price: Optional[float] = None):
        """Разместить ордер"""
        if order_type == 'market':
            return self.client.place_market_order(symbol, side, quantity)
        else:
            return self.client.place_limit_order(symbol, side, quantity, price)
    
    def get_positions(self, symbol: Optional[str] = None):
        """Получить позиции"""
        return self.client.get_positions(symbol)
    
    def cancel_order(self, order_id: str, symbol: str):
        """Отменить ордер"""
        return self.client.cancel_order(order_id, symbol)
    
    def test_connection(self) -> bool:
        """Проверить соединение"""
        return self.client.test_connection()
    
    def get_symbols(self) -> List[str]:
        """Получить список доступных символов"""
        # Получаем из кэша или через API
        return self.client.get_symbols() if hasattr(self.client, 'get_symbols') else []
    
    def get_trading_hours(self) -> Dict[str, Any]:
        """Вернуть торговые часы (для Bybit 24/7)"""
        return {
            'start': '00:00',
            'end': '23:59',
            'timezone': 'UTC',
            'weekends': [],  # Bybit торгуется 24/7
            'is_24_7': True
        }
