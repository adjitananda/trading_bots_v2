"""
Утилиты для работы с фьючерсами Московской биржи.
"""

from datetime import datetime, timedelta
from typing import Optional


def parse_futures_code(code: str) -> dict:
    """
    Разобрать код фьючерса.
    
    Примеры:
    - SiH6 → Si, H, 2026
    - RIZ6 → RI, Z, 2026
    
    Месяцы: F(Jan) G(Feb) H(Mar) J(Apr) K(May) M(Jun) N(Jul) Q(Aug) U(Sep) V(Oct) X(Nov) Z(Dec)
    """
    import re
    
    # Ищем букву месяца в конце
    month_codes = {
        'F': 1, 'G': 2, 'H': 3, 'J': 4, 'K': 5, 'M': 6,
        'N': 7, 'Q': 8, 'U': 9, 'V': 10, 'X': 11, 'Z': 12
    }
    
    match = re.search(r'([A-Z]+)([FGHJKMNQUVXZ])(\d+)$', code.upper())
    if not match:
        return None
    
    base = match.group(1)
    month_code = match.group(2)
    year = 2000 + int(match.group(3))
    
    return {
        'base': base,
        'month': month_codes.get(month_code, 3),
        'year': year,
        'code': code
    }


def get_expiry_date(code: str) -> Optional[datetime]:
    """
    Получить дату экспирации фьючерса.
    Для фьючерсов MOEX: 3-й четверг месяца.
    """
    parsed = parse_futures_code(code)
    if not parsed:
        return None
    
    year = parsed['year']
    month = parsed['month']
    
    # Находим 3-й четверг месяца
    first_day = datetime(year, month, 1)
    # Первый четверг
    days_to_thursday = (3 - first_day.weekday() + 7) % 7
    first_thursday = first_day + timedelta(days=days_to_thursday)
    # Третий четверг
    third_thursday = first_thursday + timedelta(days=14)
    
    return third_thursday


def is_expiring_soon(code: str, days: int = 3) -> bool:
    """Проверить, не истекает ли фьючерс скоро"""
    expiry = get_expiry_date(code)
    if not expiry:
        return False
    
    days_left = (expiry - datetime.now()).days
    return 0 < days_left <= days


def get_next_contract(base: str) -> Optional[str]:
    """Получить следующий контракт для базы"""
    # Простая логика: возвращаем следующий месяц
    # Реальная логика сложнее
    month_codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
    current_month = datetime.now().month
    
    for code in month_codes:
        month_num = {'F':1, 'G':2, 'H':3, 'J':4, 'K':5, 'M':6,
                     'N':7, 'Q':8, 'U':9, 'V':10, 'X':11, 'Z':12}[code]
        if month_num > current_month:
            year = datetime.now().year
            return f"{base}{code}{str(year)[-2:]}"
    
    # Следующий год
    year = datetime.now().year + 1
    return f"{base}F{str(year)[-2:]}"
