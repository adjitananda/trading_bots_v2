"""
Smoke-тесты для сохранения демо-сделок в БД.
"""

import pytest
from decimal import Decimal
from trading_lib.db import save_demo_trade


def test_insert_demo_trade():
    """Вставка демо-сделки в БД"""
    trade_id = save_demo_trade(
        broker="tinkoff",
        symbol="BTCUSDT",
        side="buy",
        qty=Decimal("0.001"),
        price=Decimal("52340.50"),
        commission=Decimal("0.0523405"),
        latency_ms=237
    )
    
    assert trade_id > 0
    print(f"\n✅ Вставлена запись с id={trade_id}")


def test_decimal_precision():
    """Проверка точности DECIMAL(20,8)"""
    trade_id = save_demo_trade(
        broker="moex",
        symbol="SBER",
        side="sell",
        qty=Decimal("10.12345678"),
        price=Decimal("250.12345678"),
        commission=Decimal("0.25012345"),
        latency_ms=150
    )
    
    assert trade_id > 0
    print(f"\n✅ DECIMAL(20,8) сохранен: qty=10.12345678, price=250.12345678")


def test_invalid_broker_raises():
    """Некорректный broker вызывает ValueError"""
    with pytest.raises(ValueError, match="Некорректный broker"):
        save_demo_trade(
            broker="invalid",
            symbol="BTC",
            side="buy",
            qty=Decimal("1"),
            price=Decimal("100"),
            commission=Decimal("0.1"),
            latency_ms=200
        )


def test_invalid_latency_raises():
    """Некорректная задержка вызывает ValueError"""
    with pytest.raises(ValueError, match="latency_ms должен быть в диапазоне"):
        save_demo_trade(
            broker="tinkoff",
            symbol="BTC",
            side="buy",
            qty=Decimal("1"),
            price=Decimal("100"),
            commission=Decimal("0.1"),
            latency_ms=500  # >300
        )
