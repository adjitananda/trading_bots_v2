"""
Абстрактный слой для биржевых адаптеров.
Все биржи должны реализовывать этот интерфейс.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from decimal import Decimal


class ExchangeInterface(ABC):
    """Базовый интерфейс для всех бирж"""
    
    @abstractmethod
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Получить баланс.
        
        Args:
            currency: Опционально - конкретная валюта (USDT, BTC и т.д.)
            
        Returns:
            Словарь {currency: available_balance}
        """
        pass
    
    @abstractmethod
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Получить историю свечей.
        
        Args:
            symbol: Торговая пара (например 'BTCUSDT')
            interval: Таймфрейм ('1m', '5m', '1h', '1d' и т.д.)
            limit: Количество свечей
            
        Returns:
            Список словарей с полями:
            timestamp, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'market',
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Разместить ордер.
        
        Args:
            symbol: Торговая пара
            side: 'BUY' или 'SELL'
            quantity: Количество в базовой валюте (например BTC)
            order_type: 'market', 'limit', 'stop', 'take_profit', 'stop_loss'
            price: Цена для лимитных ордеров
            stop_loss: Цена стоп-лосса
            take_profit: Цена тейк-профита
            
        Returns:
            Словарь с информацией об ордере (order_id, status, filled_quantity и т.д.)
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Отменить ордер.
        
        Args:
            order_id: ID ордера на бирже
            symbol: Торговая пара (для некоторых бирж обязателен)
            
        Returns:
            True если успешно, иначе False
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Получить список открытых ордеров.
        
        Args:
            symbol: Опционально - фильтр по торговой паре
            
        Returns:
            Список ордеров
        """
        pass
    
    @abstractmethod
    def get_symbols(self) -> List[str]:
        """
        Получить список всех доступных торговых пар.
        
        Returns:
            Список символов (например ['BTCUSDT', 'ETHUSDT', ...])
        """
        pass
    
    @abstractmethod
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Получить информацию о бирже.
        
        Returns:
            Словарь с полями:
            name - название биржи
            type - 'spot', 'futures' или 'both'
            trading_hours - None для 24/7 или строка с расписанием
            fees - {maker: float, taker: float}
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """
        Получить текущую цену и статистику по символу.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Словарь с полями: last, bid, ask, volume, high, low
        """
        pass
    
    def test_connection(self) -> bool:
        """
        Проверить подключение к бирже.
        По умолчанию пробуем получить список символов.
        """
        try:
            self.get_symbols()
            return True
        except Exception:
            return False
