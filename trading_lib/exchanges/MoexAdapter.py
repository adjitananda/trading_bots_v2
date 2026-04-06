"""
MOEX Adapter с поддержкой демо-режима через OrderSimulator.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from trading_lib.simulator import OrderSimulator

logger = logging.getLogger(__name__)


class MoexAdapter:
    """
    Адаптер для MOEX API.
    
    В демо-режиме использует OrderSimulator вместо реального API.
    """

    def __init__(self, demo_mode: bool = False, api_key: Optional[str] = None):
        """
        Инициализация адаптера.

        Args:
            demo_mode: Если True, используется эмулятор (не отправляет реальные ордера)
            api_key: API ключ MOEX (обязателен, если demo_mode=False)
        """
        self.demo_mode = demo_mode
        self.api_key = api_key
        
        if not demo_mode and not api_key:
            raise ValueError("api_key обязателен при demo_mode=False")
        
        if demo_mode:
            self.simulator = OrderSimulator()
            logger.info("MoexAdapter запущен в ДЕМО-режиме (эмулятор)")
        else:
            logger.info("MoexAdapter запущен в РЕАЛЬНОМ режиме")
            # Здесь будет реальный клиент MOEX API

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
            symbol: Торговый символ (например, 'SBER', 'SiH6')
            side: 'buy' или 'sell'
            qty: Количество
            order_type: Тип ордера (только 'market' в V1)

        Returns:
            Словарь с результатом ордера в едином формате
        """
        if order_type != "market":
            raise ValueError("MoexAdapter V1 поддерживает только market-ордера")

        # Получение рыночной цены (заглушка, реальная будет через API)
        market_price = await self._get_market_price(symbol)

        if self.demo_mode:
            logger.info("DEMO MODE: ордер %s %s %s эмулируется", side, qty, symbol)
            
            order = {'side': side, 'qty': qty}
            result = await self.simulator.simulate_fill(order, market_price)
            
            return {
                'broker': 'moex',
                'symbol': symbol,
                'order_id': f"DEMO_MOEX_{id(result)}",
                'status': 'filled' if result['filled'] else 'rejected',
                'filled_qty': result['filled_qty'],
                'fill_price': result['fill_price'],
                'commission': result['commission'],
                'latency_ms': result['latency_ms'],
                'reason': result['reason']
            }
        else:
            # Реальный вызов API MOEX
            logger.info("REAL MODE: отправка ордера %s %s %s", side, qty, symbol)
            # Здесь будет реальный код
            raise NotImplementedError("Реальный режим MOEX будет в следующем спринте")

    async def _get_market_price(self, symbol: str) -> Decimal:
        """
        Получение текущей рыночной цены.
        
        В демо-режиме возвращает тестовую цену.
        В реальном — запрос к API.
        """
        if self.demo_mode:
            # Заглушка для демо-режима
            if symbol.startswith("Si"):
                return Decimal("75.5")  # Фьючерс на доллар
            elif symbol.startswith("SBER"):
                return Decimal("250.0")  # Акции Сбера
            else:
                return Decimal("100.0")
        else:
            # Здесь будет реальный запрос к MOEX API
            raise NotImplementedError("Реальное получение цены будет позже")
