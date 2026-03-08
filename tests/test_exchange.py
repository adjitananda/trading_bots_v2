#!/usr/bin/env python3
"""
Тесты для клиента биржи.
"""

import os
import sys
from pathlib import Path
import unittest
from datetime import datetime

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading.exchange_client import ExchangeClient, ExchangeFactory
from src.core.database import db


def test_connection():
    """Тест подключения к бирже"""
    print("\n🔌 Тест подключения...")
    
    try:
        # Создаем клиент (testnet больше не используется)
        client = ExchangeClient('bybit')
        print(f"  ✅ Клиент создан: {client.exchange_name}")
        
        # Проверяем подключение
        if client.test_connection():
            print("  ✅ Подключение успешно!")
            return client
        else:
            print("  ❌ Ошибка подключения")
            return None
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return None


def test_balance(client):
    """Тест получения баланса"""
    print("\n💰 Тест получения баланса...")
    
    balance = client.get_balance('USDT')
    if balance is not None:
        print(f"  ✅ Баланс USDT: ${balance:.2f}")
        return balance
    else:
        print("  ❌ Не удалось получить баланс")
        return None


def test_positions(client):
    """Тест получения позиций"""
    print("\n📊 Тест получения позиций...")
    
    positions = client.get_positions()
    print(f"  ✅ Найдено позиций: {len(positions)}")
    
    for pos in positions:
        print(f"     • {pos['symbol']}: {pos['side']} {pos['size']} @ ${pos['entry_price']}")
    
    return positions


def test_price(client, symbol='BTCUSDT'):
    """Тест получения текущей цены"""
    print(f"\n💵 Тест получения цены {symbol}...")
    
    price = client.get_current_price(symbol)
    if price:
        print(f"  ✅ Текущая цена: ${price:,.2f}")
        return price
    else:
        print(f"  ❌ Не удалось получить цену")
        return None


def test_instrument_info(client, symbol='BTCUSDT'):
    """Тест получения информации об инструменте"""
    print(f"\nℹ️ Тест получения информации об инструменте {symbol}...")
    
    info = client.get_instrument_info(symbol)
    if info:
        print(f"  ✅ Информация получена:")
        print(f"     • Шаг цены: {info.get('tick_size')}")
        print(f"     • Шаг количества: {info.get('qty_step')}")
        print(f"     • Мин. количество: {info.get('min_qty')}")
        print(f"     • Мин. сумма: ${info.get('min_notional')}")
        return info
    else:
        print(f"  ❌ Не удалось получить информацию")
        return None


def test_klines(client, symbol='BTCUSDT', interval='5'):
    """Тест получения свечей"""
    print(f"\n📈 Тест получения свечей {symbol} ({interval} мин)...")
    
    df = client.get_klines(symbol, interval, limit=10)
    if df is not None and not df.empty:
        print(f"  ✅ Получено {len(df)} свечей")
        print(f"     • Последняя цена: ${df['close'].iloc[-1]:.2f}")
        print(f"     • Объем: {df['volume'].iloc[-1]:.2f}")
        return df
    else:
        print(f"  ❌ Не удалось получить свечи")
        return None


def test_factory():
    """Тест фабрики клиентов"""
    print("\n🏭 Тест фабрики клиентов...")
    
    try:
        client = ExchangeFactory.create_client('bybit')
        print(f"  ✅ Фабрика создала клиент: {client.exchange_name}")
        
        if client.test_connection():
            print("  ✅ Подключение через фабрику работает")
        else:
            print("  ❌ Подключение через фабрику не работает")
    except Exception as e:
        print(f"  ❌ Ошибка фабрики: {e}")


def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ КЛИЕНТА БИРЖИ")
    print("=" * 60)
    
    # Тест подключения
    client = test_connection()
    if not client:
        print("\n❌ Ошибка подключения. Дальнейшие тесты невозможны.")
        return
    
    # Тесты
    test_balance(client)
    test_positions(client)
    test_price(client)
    test_instrument_info(client)
    test_klines(client)
    test_factory()
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    main()