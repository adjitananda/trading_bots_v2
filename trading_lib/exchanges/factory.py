"""
Фабрика для создания адаптеров бирж.
Возвращает нужный адаптер на основе exchange_id или имени.
"""

import logging
from typing import Dict, Any, Optional

from .interface import ExchangeInterface
from .bybit_adapter import BybitAdapter

logger = logging.getLogger(__name__)


class ExchangeFactory:
    """Фабрика для создания биржевых адаптеров"""
    
    # Регистр адаптеров
    _adapters = {
        'bybit': BybitAdapter,
    }
    
    @classmethod
    def get_exchange(cls, exchange_id: int, config: Optional[Dict[str, Any]] = None) -> ExchangeInterface:
        """
        Получить адаптер биржи по ID.
        
        Args:
            exchange_id: ID биржи из таблицы exchanges
            config: Дополнительная конфигурация (api_key, api_secret и т.д.)
            
        Returns:
            Экземпляр адаптера биржи
        """
        from trading_lib.utils.database import db
        
        # Загружаем информацию о бирже из БД
        exchange_info = cls._get_exchange_by_id(exchange_id)
        
        if not exchange_info:
            raise ValueError(f"Биржа с ID {exchange_id} не найдена")
        
        exchange_name = exchange_info.get('name', '').lower()
        
        return cls.get_exchange_by_name(exchange_name, config)
    
    @classmethod
    def get_exchange_by_name(cls, name: str, config: Optional[Dict[str, Any]] = None) -> ExchangeInterface:
        """
        Получить адаптер биржи по имени.
        
        Args:
            name: Имя биржи ('bybit', 'binance' и т.д.)
            config: Дополнительная конфигурация
            
        Returns:
            Экземпляр адаптера биржи
        """
        if name not in cls._adapters:
            available = ', '.join(cls._adapters.keys())
            raise ValueError(f"Неизвестная биржа: {name}. Доступны: {available}")
        
        adapter_class = cls._adapters[name]
        logger.info(f"🏭 Создан адаптер для биржи: {name}")
        
        return adapter_class(config or {})
    
    @classmethod
    def _get_exchange_by_id(cls, exchange_id: int) -> Optional[Dict[str, Any]]:
        """Загрузить информацию о бирже из БД"""
        try:
            from trading_lib.utils.database import db
            
            query = "SELECT id, name, type, is_active, api_config FROM exchanges WHERE id = %s"
            result = db.execute_query(query, (exchange_id,))
            
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки биржи ID {exchange_id}: {e}")
            return None
    
    @classmethod
    def register_adapter(cls, name: str, adapter_class):
        """
        Зарегистрировать новый адаптер.
        Используется для расширения новыми биржами.
        
        Args:
            name: Имя биржи (ключ)
            adapter_class: Класс адаптера (наследник ExchangeInterface)
        """
        cls._adapters[name.lower()] = adapter_class
        logger.info(f"📝 Зарегистрирован адаптер для биржи: {name}")
    
    @classmethod
    def get_available_exchanges(cls) -> list:
        """Получить список доступных бирж"""
        return list(cls._adapters.keys())


# Утилитарная функция для быстрого доступа
def get_exchange(exchange_id: int, config: Optional[Dict[str, Any]] = None) -> ExchangeInterface:
    """
    Быстрый доступ к фабрике.
    
    Args:
        exchange_id: ID биржи из таблицы exchanges
        config: Конфигурация
        
    Returns:
        Адаптер биржи
    """
    return ExchangeFactory.get_exchange(exchange_id, config)


def get_exchange_by_name(name: str, config: Optional[Dict[str, Any]] = None) -> ExchangeInterface:
    """
    Быстрый доступ к фабрике по имени.
    
    Args:
        name: Имя биржи
        config: Конфигурация
        
    Returns:
        Адаптер биржи
    """
    return ExchangeFactory.get_exchange_by_name(name, config)
