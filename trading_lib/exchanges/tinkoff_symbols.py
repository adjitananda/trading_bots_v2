"""
Маппинг тикеров Тинькофф к Figi-идентификаторам.
Figi требуется для API Тинькофф.
"""

# Маппинг человеческих тикеров → Figi
SYMBOL_TO_FIGI = {
    'SBER': 'BBG004730ZJ9',   # Сбербанк
    'SBERP': 'BBG004730ZG2',  # Сбербанк-преф
    'YNDX': 'BBG00L7B9SY6',   # Яндекс
    'ROSN': 'BBG004731032',   # Роснефть
    'GAZP': 'BBG0047316V2',   # Газпром
    'LKOH': 'BBG0047316Y9',   # Лукойл
    'VTBR': 'BBG004730YV7',   # ВТБ
    'TATN': 'BBG0047316W0',   # Татнефть
    'NVTK': 'BBG0047316X9',   # Новатэк
    'MGNT': 'BBG004730V91',   # Магнит
    'MTSS': 'BBG004730VT2',   # МТС
    'SNGS': 'BBG004730Z77',   # Сургутнефтегаз
    'GMKN': 'BBG004731029',   # Норильский никель
    'CHMF': 'BBG004730Z50',   # Северсталь
    'PLZL': 'BBG004730ZG3',   # Полюс Золото
}

FIGI_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_FIGI.items()}


def get_figi(symbol: str) -> str:
    """Получить Figi по тикеру"""
    return SYMBOL_TO_FIGI.get(symbol.upper())


def get_symbol_from_figi(figi: str) -> str:
    """Получить тикер по Figi"""
    return FIGI_TO_SYMBOL.get(figi)


def get_all_symbols() -> list:
    """Получить все поддерживаемые тикеры"""
    return list(SYMBOL_TO_FIGI.keys())


def is_supported(symbol: str) -> bool:
    """Проверить, поддерживается ли тикер"""
    return symbol.upper() in SYMBOL_TO_FIGI
