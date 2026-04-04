#!/usr/bin/env python3
"""
Валидатор торговых символов на бирже.
"""

import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


def validate_symbol(exchange_client, symbol: str) -> Tuple[bool, str]:
    """
    Проверяет, торгуется ли символ на бирже.
    Делает это через попытку получить текущую цену.
    
    Returns:
        (валидный, сообщение)
    """
    try:
        price = exchange_client.get_current_price(symbol)
        if price and price > 0:
            return True, "OK"
        else:
            return False, f"Символ {symbol} не торгуется или цена = 0"
    except Exception as e:
        error_msg = str(e)
        if "Invalid symbol" in error_msg or "not found" in error_msg.lower():
            return False, f"Символ {symbol} не найден на бирже"
        return False, f"Ошибка проверки: {error_msg[:100]}"


def validate_symbols_batch(exchange_client, symbols: List[str]) -> dict:
    """Проверяет список символов."""
    return {sym: validate_symbol(exchange_client, sym) for sym in symbols}


def get_valid_symbols(exchange_client, symbols: List[str]) -> List[str]:
    """Возвращает только валидные символы."""
    valid = []
    for sym in symbols:
        is_valid, _ = validate_symbol(exchange_client, sym)
        if is_valid:
            valid.append(sym)
        else:
            logger.warning(f"⚠️ Символ {sym} пропущен (не валиден)")
    return valid
