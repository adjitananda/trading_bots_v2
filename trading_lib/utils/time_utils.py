# /home/trader/trading_bots_logs/utils/time_utils.py
"""
Утилиты для работы с временем.
Все функции работают с UTC как с эталоном и преобразуют в UTC+3 для отображения.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

def utc_to_local(utc_dt: Optional[datetime]) -> Optional[datetime]:
    """
    Преобразование UTC времени в UTC+3.
    
    Args:
        utc_dt: Время в UTC или None
        
    Returns:
        Время в UTC+3 или None
    """
    if utc_dt is None:
        return None
    if hasattr(utc_dt, 'tzinfo') and utc_dt.tzinfo is not None:
        utc_dt = utc_dt.replace(tzinfo=None)
    return utc_dt + timedelta(hours=3)

def now_utc() -> datetime:
    """
    Текущее время в UTC (без часового пояса).
    
    Returns:
        datetime: Текущее UTC время
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

def now_local() -> datetime:
    """
    Текущее время в UTC+3 (без часового пояса).
    
    Returns:
        datetime: Текущее время в UTC+3
    """
    return now_utc() + timedelta(hours=3)

def format_datetime(dt: Optional[datetime], format_str: str = '%d.%m.%Y %H:%M:%S') -> str:
    """
    Форматирование даты и времени.
    
    Args:
        dt: Дата и время или None
        format_str: Строка форматирования
        
    Returns:
        str: Отформатированная дата или пустая строка
    """
    if dt is None:
        return ''
    return dt.strftime(format_str)

def format_date(dt: Optional[datetime]) -> str:
    """Форматирование только даты."""
    return format_datetime(dt, '%d.%m.%Y')

def format_time(dt: Optional[datetime]) -> str:
    """Форматирование только времени."""
    return format_datetime(dt, '%H:%M:%S')

def seconds_to_duration(seconds: Optional[int]) -> str:
    """
    Преобразование секунд в читаемый формат (ЧЧ:ММ:СС).
    
    Args:
        seconds: Количество секунд или None
        
    Returns:
        str: Длительность в формате ЧЧ:ММ:СС
    """
    if seconds is None:
        return ''
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"