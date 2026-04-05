"""
Адаптер для Тинькофф Инвестиции (tinkoff.ru)
Реализует ExchangeInterface через gRPC API.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, time as dt_time
from decimal import Decimal

from trading_lib.exchanges.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class TinkoffAdapter(ExchangeInterface):
    """Адаптер для Тинькофф Инвестиции"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация адаптера.
        
        Args:
            config: Конфигурация с token
        """
        self.config = config or {}
        self.token = self.config.get('token') or os.getenv('TINKOFF_TOKEN')
        self.exchange_name = "tinkoff"
        self.exchange_id = 2  # ID после вставки в БД
        
        if not self.token:
            logger.warning("⚠️ TINKOFF_TOKEN не установлен")
        
        self._init_client()
    
    def _init_client(self):
        """Инициализация клиента (заглушка, реальный gRPC позже)"""
        logger.info("📈 Тинькофф адаптер инициализирован (режим заглушки)")
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """Получить баланс в рублях"""
        # Заглушка: возвращаем тестовый баланс
        balance = {"RUB": 100000.0}
        if currency:
            return {currency: balance.get(currency, 0)}
        return balance
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Получить свечи.
        
        Args:
            symbol: Тикер (например 'SBER')
            interval: Интервал ('1m', '5m', '15m', '1h', '1d')
            limit: Количество свечей
        """
        # Заглушка: возвращаем пустой список
        logger.warning(f"⚠️ get_klines для {symbol} - заглушка")
        return []
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Отменить ордер"""
        logger.info(f"❌ Отмена ордера {order_id} (заглушка)")
        return True
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получить открытые ордера"""
        return []
    
    def get_symbols(self) -> List[str]:
        """Получить список доступных тикеров"""
        # Основные акции Московской биржи
        return [
            'SBER', 'YNDX', 'ROSN', 'GAZP', 'LKOH',
            'VTBR', 'TATN', 'NVTK', 'MGNT', 'MTSS'
        ]
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """Получить информацию о бирже"""
        return {
            'name': self.exchange_name,
            'id': self.exchange_id,
            'type': 'spot',
            'timezone': 'Europe/Moscow',
            'is_24_7': False
        }
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Получить тикер"""
        # Заглушка
        return {
            'symbol': symbol,
            'last_price': 100.0,
            'bid': 99.5,
            'ask': 100.5,
            'volume': 1000000,
            'high': 105.0,
            'low': 95.0
        }
    
    def test_connection(self) -> bool:
        """Проверить соединение с API"""
        if self.token:
            logger.info("✅ Тинькофф API: токен установлен")
            return True
        logger.warning("⚠️ Тинькофф API: токен отсутствует")
        return False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену"""
        # Заглушка
        return 100.0
    
    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = 'market', price: Optional[float] = None):
        """
        Разместить ордер.
        
        Внимание: Тинькофф поддерживает только длинные позиции (BUY).
        """
        if side.upper() != 'BUY':
            logger.warning(f"⚠️ Тинькофф не поддерживает шорты (side={side})")
            return {'success': False, 'error': 'Only BUY orders supported'}
        
        logger.info(f"📈 Размещение ордера {side} {quantity} {symbol} (заглушка)")
        return {'success': True, 'order_id': f'tinkoff_{symbol}_{int(datetime.now().timestamp())}'}
    
    def get_positions(self, symbol: Optional[str] = None):
        """Получить позиции"""
        return []
    
    def get_trading_hours(self) -> Dict[str, Any]:
        """Вернуть торговые часы"""
        return {
            'start': '10:00',
            'end': '18:50',
            'timezone': 'Europe/Moscow',
            'weekends': [5, 6],  # Суббота, Воскресенье
            'is_24_7': False
        }
    
    def is_trading_time(self) -> bool:
        """Проверить, идёт ли торговая сессия"""
        now = datetime.now()
        
        # Выходные
        if now.weekday() >= 5:
            return False
        
        # Время
        start = dt_time(10, 0)
        end = dt_time(18, 50)
        current = now.time()
        
        return start <= current <= end
