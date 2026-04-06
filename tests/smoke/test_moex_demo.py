"""
Smoke-тесты для MoexAdapter в демо-режиме.
"""

import pytest
from decimal import Decimal
from trading_lib.exchanges.MoexAdapter import MoexAdapter


@pytest.mark.asyncio
async def test_demo_mode_no_real_api():
    """Демо-режим не вызывает реальное API (просто не падает)"""
    adapter = MoexAdapter(demo_mode=True)
    
    result = await adapter.place_order(
        symbol="SBER",
        side="buy",
        qty=Decimal("10")
    )
    
    assert result['broker'] == 'moex'
    assert result['status'] in ('filled', 'rejected')
    assert 'order_id' in result
    assert result['symbol'] == 'SBER'


@pytest.mark.asyncio
async def test_demo_mode_returns_order_format():
    """Проверка формата возвращаемого ордера"""
    adapter = MoexAdapter(demo_mode=True)
    
    result = await adapter.place_order(
        symbol="SiH6",
        side="sell",
        qty=Decimal("1")
    )
    
    expected_keys = {'broker', 'symbol', 'order_id', 'status', 
                     'filled_qty', 'fill_price', 'commission', 
                     'latency_ms', 'reason'}
    
    assert expected_keys.issubset(result.keys())
    assert isinstance(result['filled_qty'], Decimal)
    assert isinstance(result['fill_price'], Decimal)
    assert isinstance(result['commission'], Decimal)
    assert isinstance(result['latency_ms'], int)
    assert 100 <= result['latency_ms'] <= 300


def test_real_mode_without_key_raises():
    """Реальный режим без api_key вызывает ValueError"""
    with pytest.raises(ValueError, match="api_key обязателен"):
        MoexAdapter(demo_mode=False, api_key=None)
