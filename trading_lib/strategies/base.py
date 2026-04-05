"""
Базовый класс для всех торговых стратегий.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseStrategy(ABC):
    """Абстрактный базовый класс стратегии"""
    
    def __init__(self, params: Dict[str, Any]):
        self.params = params
    
    @abstractmethod
    def get_signal(self, df):
        """
        Получить торговый сигнал.
        
        Returns:
            'up' - сигнал на покупку
            'down' - сигнал на продажу
            'none' - нет сигнала
        """
        pass
    
    def update_params(self, params: Dict[str, Any]):
        """Обновить параметры стратегии"""
        self.params.update(params)
