"""
Базовый класс для всех стратегий.
Адаптирован для новой архитектуры.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional


class BaseStrategy(ABC):
    """Базовый класс стратегии"""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> str:
        """
        Возвращает торговый сигнал.
        
        Args:
            df: DataFrame с колонками ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            'up' - сигнал на покупку
            'down' - сигнал на продажу
            'none' - нет сигнала
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Информация о стратегии"""
        return {
            'name': self.name,
            'params': self.params
        }
