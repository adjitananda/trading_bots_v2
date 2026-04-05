"""
Регистр стратегий.
"""

from typing import Dict, Any, Type, Optional
from trading_lib.strategies.base import BaseStrategy

# Регистр стратегий
_strategies: Dict[str, Type[BaseStrategy]] = {}


class StrategyRegistry:
    """Регистр стратегий (синглтон)"""
    
    _instance = None
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]):
        """Зарегистрировать стратегию"""
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get(cls, name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        """Получить экземпляр стратегии"""
        if name not in cls._strategies:
            raise ValueError(f"Стратегия '{name}' не найдена")
        return cls._strategies[name](params or {})
    
    @classmethod
    def list_strategies(cls) -> list:
        """Список доступных стратегий"""
        return list(cls._strategies.keys())


def register_strategy(name: str, strategy_class: Type[BaseStrategy]):
    """Зарегистрировать стратегию (функция-хелпер)"""
    StrategyRegistry.register(name, strategy_class)


def get_strategy(name: str, params: Dict[str, Any] = None) -> BaseStrategy:
    """Получить экземпляр стратегии по имени (функция-хелпер)"""
    return StrategyRegistry.get(name, params)


def get_available_strategies() -> list:
    """Получить список доступных стратегий"""
    return StrategyRegistry.list_strategies()


def list_strategies() -> list:
    """Алиас для get_available_strategies"""
    return get_available_strategies()
