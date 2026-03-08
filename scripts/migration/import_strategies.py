# scripts/migration/import_strategies.py
#!/usr/bin/env python3
"""
Импорт стратегий из старой системы в новую.
Адаптация под новую архитектуру.
"""

import os
import shutil
from pathlib import Path
import re

def import_strategies():
    """Копируем и адаптируем strategies.py"""
    
    old_path = "/home/trader/trading_bots_logs/strategies.py"
    new_dir = "/home/trader/trading_bots_v2/src/strategies"
    
    # Создаем папку если нет
    os.makedirs(new_dir, exist_ok=True)
    
    # Создаем базовый класс для стратегий в новой системе
    base_strategy = '''"""
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
'''
    
    with open(f"{new_dir}/base.py", 'w') as f:
        f.write(base_strategy)
    
    print("✅ base.py создан")
    
    # Читаем старый файл
    with open(old_path, 'r') as f:
        content = f.read()
    
    # Создаем файл с импортированными стратегиями
    imported_content = '''"""
Импортированные стратегии из старой системы.
Дата импорта: 2026-03-06
Оригинал: /home/trader/trading_bots_logs/strategies.py

Адаптировано для новой архитектуры.
"""

import pandas as pd
import pandas_ta as ta

from src.strategies.base import BaseStrategy


# ==================== СТРАТЕГИИ НА ОСНОВЕ СКОЛЬЗЯЩИХ СРЕДНИХ ====================
'''
    
    # Находим и адаптируем классы стратегий
    # Простой парсинг (для начала скопируем как есть, потом адаптируем)
    
    # Находим все классы стратегий
    strategy_classes = re.findall(r'class (\w+Strategy).*?:\n(.*?)(?=\nclass|\Z)', content, re.DOTALL)
    
    for class_name, class_body in strategy_classes:
        if class_name == 'BaseStrategy':
            continue  # пропускаем, у нас свой базовый
        
        # Добавляем импорт pandas_ta если нужно
        if 'ta.' in class_body:
            imported_content += f"\n\nclass {class_name}(BaseStrategy):"
            imported_content += class_body
            print(f"  → Импортирован {class_name}")
    
    # Добавляем фабрику стратегий
    factory = '''

# ==================== ФАБРИКА СТРАТЕГИЙ ====================

class StrategyFactory:
    """Фабрика для создания стратегий"""
    
    _strategies = {
'''
    
    # Добавляем все найденные стратегии в фабрику
    for class_name, _ in strategy_classes:
        if class_name != 'BaseStrategy':
            # Преобразуем имя в ключ (MACrossoverStrategy -> ma_crossover)
            key = re.sub(r'Strategy$', '', class_name)
            key = re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
            factory += f"        '{key}': {class_name},\n"
    
    factory += '''    }
    
    @classmethod
    def create_strategy(cls, name: str, params: dict = None):
        """Создать стратегию по имени"""
        if name not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(f"Unknown strategy: {name}. Available: {available}")
        
        strategy_class = cls._strategies[name]
        return strategy_class(params)
    
    @classmethod
    def get_all_strategies(cls):
        """Список всех доступных стратегий"""
        return list(cls._strategies.keys())
'''
    
    imported_content += factory
    
    # Сохраняем
    with open(f"{new_dir}/legacy.py", 'w') as f:
        f.write(imported_content)
    
    print(f"\n✅ Стратегии импортированы в {new_dir}/legacy.py")
    print(f"   Найдено классов: {len(strategy_classes)}")

def import_messages():
    """Импорт сообщений"""
    
    old_messages = "/home/trader/trading_bots_logs/messages"
    new_messages = "/home/trader/trading_bots_v2/src/messages"
    
    os.makedirs(new_messages, exist_ok=True)
    
    for file in ['console_messages.py', 'telegram_messages.py']:
        old_file = f"{old_messages}/{file}"
        new_file = f"{new_messages}/{file}"
        
        if os.path.exists(old_file):
            shutil.copy2(old_file, new_file)
            print(f"✅ {file} импортирован")
    
    # Импортируем time_utils
    old_time = "/home/trader/trading_bots_logs/utils/time_utils.py"
    new_utils = "/home/trader/trading_bots_v2/src/utils"
    os.makedirs(new_utils, exist_ok=True)
    
    if os.path.exists(old_time):
        shutil.copy2(old_time, f"{new_utils}/time_utils.py")
        print(f"✅ time_utils.py импортирован")

if __name__ == "__main__":
    print("🚀 Начинаем импорт из старой системы...")
    print("=" * 50)
    
    import_strategies()
    print("-" * 50)
    import_messages()
    
    print("=" * 50)
    print("✅ Импорт завершен!")
    print("📁 Новая структура: /home/trader/trading_bots_v2/")