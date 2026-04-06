"""
Database utilities for trading_bots_v2.
Поддержка MySQL и демо-сделок.
"""

import os
import logging
import mysql.connector
from decimal import Decimal
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Конфигурация БД из переменных окружения
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'database': os.getenv('MYSQL_DATABASE', 'trading_bots_v2'),
    'user': os.getenv('MYSQL_USER', 'trader'),
    'password': os.getenv('MYSQL_PASSWORD'),
}

logger = logging.getLogger(__name__)


def save_demo_trade(
    broker: str,
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
    commission: Decimal,
    latency_ms: int
) -> int:
    """
    Сохраняет информацию о демо-сделке в таблицу demo_trades.
    
    Args:
        broker: 'tinkoff', 'moex', 'bybit'
        symbol: Торговый символ
        side: 'buy' или 'sell'
        qty: Количество
        price: Цена исполнения
        commission: Комиссия в деньгах
        latency_ms: Задержка в миллисекундах
    
    Returns:
        id вставленной записи
    
    Raises:
        ValueError: Если параметры некорректны
        mysql.connector.Error: При ошибке БД
    """
    if broker not in ('tinkoff', 'moex', 'bybit'):
        raise ValueError(f"Некорректный broker: {broker}")
    
    if side not in ('buy', 'sell'):
        raise ValueError(f"Некорректный side: {side}")
    
    if qty <= 0:
        raise ValueError(f"qty должен быть положительным: {qty}")
    
    if price <= 0:
        raise ValueError(f"price должен быть положительным: {price}")
    
    if commission < 0:
        raise ValueError(f"commission не может быть отрицательной: {commission}")
    
    if not (100 <= latency_ms <= 300):
        raise ValueError(f"latency_ms должен быть в диапазоне 100-300: {latency_ms}")
    
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        query = """
            INSERT INTO demo_trades 
            (broker, symbol, side, qty, price, commission, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (broker, symbol, side, qty, price, commission, latency_ms))
        connection.commit()
        
        inserted_id = cursor.lastrowid
        logger.info("Демо-сделка сохранена: id=%d, broker=%s, symbol=%s", 
                    inserted_id, broker, symbol)
        
        return inserted_id
        
    except mysql.connector.Error as e:
        logger.error("Ошибка БД при сохранении демо-сделки: %s", e)
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
