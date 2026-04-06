"""
Smoke-тесты для эмулятора OrderSimulator.
"""

import pytest
import asyncio
from decimal import Decimal
from trading_lib.simulator import OrderSimulator, DEFAULT_SLIPPAGE_PERCENT


@pytest.mark.asyncio
async def test_full_fill():
    """Полное исполнение при fill_probability=1.0"""
    sim = OrderSimulator(fill_probability=Decimal("1.0"))
    order = {'side': 'buy', 'qty': Decimal('0.01')}
    market_price = Decimal('50000.0')
    
    result = await sim.simulate_fill(order, market_price)
    
    assert result['filled'] is True
    assert result['filled_qty'] == Decimal('0.01')
    assert result['fill_price'] > market_price  # buy slippage up
    assert result['commission'] > 0
    assert 100 <= result['latency_ms'] <= 300


@pytest.mark.asyncio
async def test_reject_probability():
    """Отказ при fill_probability=0.0"""
    sim = OrderSimulator(fill_probability=Decimal("0.0"))
    order = {'side': 'sell', 'qty': Decimal('0.01')}
    market_price = Decimal('50000.0')
    
    result = await sim.simulate_fill(order, market_price)
    
    assert result['filled'] is False
    assert result['reason'] == 'fill_probability_reject'


@pytest.mark.asyncio
async def test_slippage_calculation():
    """Проверка направления проскальзывания"""
    sim = OrderSimulator(slippage_percent=Decimal("0.1"))  # 0.1%
    market_price = Decimal('100.0')
    
    # buy
    buy_order = {'side': 'buy', 'qty': Decimal('1')}
    buy_result = await sim.simulate_fill(buy_order, market_price)
    assert buy_result['fill_price'] > market_price
    
    # sell
    sell_order = {'side': 'sell', 'qty': Decimal('1')}
    sell_result = await sim.simulate_fill(sell_order, market_price)
    assert sell_result['fill_price'] < market_price


@pytest.mark.asyncio
async def test_latency_range():
    """Задержка в заданном диапазоне"""
    sim = OrderSimulator(latency_ms_min=150, latency_ms_max=250)
    order = {'side': 'buy', 'qty': Decimal('0.01')}
    market_price = Decimal('50000.0')
    
    results = []
    for _ in range(10):
        res = await sim.simulate_fill(order, market_price)
        results.append(res['latency_ms'])
    
    assert all(150 <= ms <= 250 for ms in results)


def test_invalid_probability():
    """Некорректная вероятность вызывает ValueError"""
    with pytest.raises(ValueError):
        OrderSimulator(fill_probability=Decimal("1.5"))
    
    with pytest.raises(ValueError):
        OrderSimulator(fill_probability=Decimal("-0.1"))


def test_invalid_latency():
    """Некорректная задержка вызывает ValueError"""
    with pytest.raises(ValueError):
        OrderSimulator(latency_ms_min=-10, latency_ms_max=100)
    
    with pytest.raises(ValueError):
        OrderSimulator(latency_ms_min=200, latency_ms_max=100)


@pytest.mark.asyncio
async def test_order_without_side_raises():
    """Ордер без side вызывает ValueError"""
    sim = OrderSimulator()
    order = {'qty': Decimal('0.01')}
    
    with pytest.raises(ValueError, match="must have 'side'"):
        await sim.simulate_fill(order, Decimal('100'))
