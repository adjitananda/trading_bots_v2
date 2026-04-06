"""
Tinkoff Adapter с поддержкой демо-режима через OrderSimulator.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from trading_lib.simulator import OrderSimulator

logger = logging.getLogger(__name__)


class TinkoffAdapter:
    """
    Адаптер для Tinkoff API.
    
    В демо-режиме использует OrderSimulator вместо реального API.
    """

    def __init__(self, demo_mode: bool = False, api_token: Optional[str] = None):
        """
        Инициализация адаптера.

        Args:
            demo_mode: Если True, используется эмулятор (не отправляет реальные ордера)
            api_token: Токен API Tinkoff (обязателен, если demo_mode=False)
        """
        self.demo_mode = demo_mode
        self.api_token = api_token
        
        if not demo_mode and not api_token:
            raise ValueError("api_token обязателен при demo_mode=False")
        
        if demo_mode:
            self.simulator = OrderSimulator()
            logger.info("TinkoffAdapter запущен в ДЕМО-режиме (эмулятор)")
        else:
            logger.info("TinkoffAdapter запущен в РЕАЛЬНОМ режиме")
            # Здесь будет реальный клиент Tinkoff API

    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        order_type: str = "market"
    ) -> Dict[str, Any]:
        """
        Размещение ордера (реальное или эмуляция).

        Args:
            symbol: Торговый символ (например, 'BTCUSDT')
            side: 'buy' или 'sell'
            qty: Количество
            order_type: Тип ордера (только 'market' в V1)

        Returns:
            Словарь с результатом ордера в едином формате
        """
        if order_type != "market":
            raise ValueError("TinkoffAdapter V1 поддерживает только market-ордера")

        # Получение рыночной цены (заглушка, реальная будет через API)
        market_price = await self._get_market_price(symbol)

        if self.demo_mode:
            logger.info("DEMO MODE: ордер %s %s %s эмулируется", side, qty, symbol)
            
            order = {'side': side, 'qty': qty}
            result = await self.simulator.simulate_fill(order, market_price)
            
            return {
                'broker': 'tinkoff',
                'symbol': symbol,
                'order_id': f"DEMO_{id(result)}",
                'status': 'filled' if result['filled'] else 'rejected',
                'filled_qty': result['filled_qty'],
                'fill_price': result['fill_price'],
                'commission': result['commission'],
                'latency_ms': result['latency_ms'],
                'reason': result['reason']
            }
        else:
            # Реальный вызов API Tinkoff
            logger.info("REAL MODE: отправка ордера %s %s %s", side, qty, symbol)
            # Здесь будет реальный код
            raise NotImplementedError("Реальный режим Tinkoff будет в следующем спринте")

    async def _get_market_price(self, symbol: str) -> Decimal:
        """
        Получение текущей рыночной цены.
        
        В демо-режиме возвращает тестовую цену.
        В реальном — запрос к API.
        """
        if self.demo_mode:
            # Заглушка для демо-режима
            return Decimal("50000.0")
        else:
            # Здесь будет реальный запрос к Tinkoff API
            raise NotImplementedError("Реальное получение цены будет позже")
