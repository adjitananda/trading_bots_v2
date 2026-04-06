"""
Smoke-тесты для TinkoffAdapter в демо-режиме.
"""

import pytest
from decimal import Decimal
from trading_lib.exchanges.TinkoffAdapter import TinkoffAdapter


@pytest.mark.asyncio
async def test_demo_mode_no_real_api():
    """Демо-режим не вызывает реальное API (просто не падает)"""
    adapter = TinkoffAdapter(demo_mode=True)
    
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side="buy",
        qty=Decimal("0.001")
    )
    
    assert result['broker'] == 'tinkoff'
    assert result['status'] in ('filled', 'rejected')
    assert 'order_id' in result
    assert result['symbol'] == 'BTCUSDT'


@pytest.mark.asyncio
async def test_demo_mode_returns_order_format():
    """Проверка формата возвращаемого ордера"""
    adapter = TinkoffAdapter(demo_mode=True)
    
    result = await adapter.place_order(
        symbol="ETHUSDT",
        side="sell",
        qty=Decimal("0.01")
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


def test_real_mode_without_token_raises():
    """Реальный режим без токена вызывает ValueError"""
    with pytest.raises(ValueError, match="api_token обязателен"):
        TinkoffAdapter(demo_mode=False, api_token=None)
