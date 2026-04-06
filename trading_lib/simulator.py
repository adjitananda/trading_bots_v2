"""
Эмулятор исполнения ордеров для демо-торговли.

Детерминированный, логируемый, с явными константами.
"""

import asyncio
import logging
import random
from decimal import Decimal
from typing import Dict, Any, Optional

# Константы (никаких магических чисел)
DEFAULT_SLIPPAGE_PERCENT = Decimal("0.05")  # 0.05%
DEFAULT_LATENCY_MS_MIN = 100
DEFAULT_LATENCY_MS_MAX = 300
DEFAULT_FILL_PROBABILITY = Decimal("0.95")  # 95%
DEFAULT_LIQUIDITY_LIMIT_PERCENT = Decimal("10.0")  # 10% от стакана

# Комиссии по умолчанию (заглушка, реальные из brokers_commissions.json)
DEFAULT_TAKER_FEE = Decimal("0.001")  # 0.1%
DEFAULT_MAKER_FEE = Decimal("0.0005")  # 0.05%


logger = logging.getLogger(__name__)


class OrderSimulator:
    """
    Эмулятор исполнения ордера с проскальзыванием, задержкой и вероятностью отказа.
    
    Не поддерживает частичное заполнение от ликвидности (см. known_issues.md).
    """

    def __init__(
        self,
        slippage_percent: Decimal = DEFAULT_SLIPPAGE_PERCENT,
        latency_ms_min: int = DEFAULT_LATENCY_MS_MIN,
        latency_ms_max: int = DEFAULT_LATENCY_MS_MAX,
        fill_probability: Decimal = DEFAULT_FILL_PROBABILITY,
        liquidity_limit_percent: Decimal = DEFAULT_LIQUIDITY_LIMIT_PERCENT,
    ):
        """
        Инициализация эмулятора.

        Args:
            slippage_percent: Проскальзывание в процентах (например, 0.05 = 0.05%)
            latency_ms_min: Минимальная задержка в мс
            latency_ms_max: Максимальная задержка в мс
            fill_probability: Вероятность полного исполнения (0..1)
            liquidity_limit_percent: Лимит ликвидности в процентах от стакана (заглушка)
        """
        if not (0 <= fill_probability <= 1):
            raise ValueError("fill_probability must be between 0 and 1")
        if latency_ms_min <= 0 or latency_ms_max <= 0:
            raise ValueError("latency must be positive")
        if latency_ms_min > latency_ms_max:
            raise ValueError("latency_ms_min must be <= latency_ms_max")

        self.slippage_percent = slippage_percent
        self.latency_ms_min = latency_ms_min
        self.latency_ms_max = latency_ms_max
        self.fill_probability = fill_probability
        self.liquidity_limit_percent = liquidity_limit_percent

    async def simulate_fill(
        self,
        order: Dict[str, Any],
        market_price: Decimal,
        order_book: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Эмулирует исполнение ордера.

        Args:
            order: Словарь ордера с ключами 'side' (buy/sell), 'qty' (Decimal)
            market_price: Текущая рыночная цена
            order_book: Опционально стакан (не используется в V1, только для лога)

        Returns:
            Словарь с результатом исполнения:
            {
                'filled': bool,
                'fill_price': Decimal,
                'filled_qty': Decimal,
                'commission': Decimal,
                'latency_ms': int,
                'reason': str
            }

        Raises:
            ValueError: Если ордер некорректен
        """
        # Валидация входа
        if 'side' not in order or order['side'] not in ('buy', 'sell'):
            raise ValueError("order must have 'side' = 'buy' or 'sell'")
        
        qty = order.get('qty')
        if not isinstance(qty, Decimal) or qty <= 0:
            raise ValueError("order['qty'] must be positive Decimal")

        # 1. Проверка ликвидности (заглушка — логируем, но не отклоняем в V1)
        if order_book:
            logger.debug("Order book received but liquidity check is stub in V1")
        else:
            logger.debug("No order book provided, skipping liquidity check")

        # 2. Вероятность отказа
        fill_roll = random.random()
        if fill_roll > float(self.fill_probability):
            logger.info("Order rejected: fill_probability=%.2f, roll=%.2f", 
                        self.fill_probability, fill_roll)
            return {
                'filled': False,
                'fill_price': Decimal('0'),
                'filled_qty': Decimal('0'),
                'commission': Decimal('0'),
                'latency_ms': random.randint(self.latency_ms_min, self.latency_ms_max),
                'reason': 'fill_probability_reject'
            }

        # 3. Проскальзывание
        slippage_multiplier = Decimal('1') + (self.slippage_percent / Decimal('100'))
        if order['side'] == 'buy':
            # Покупаем дороже
            fill_price = market_price * slippage_multiplier
        else:
            # Продаем дешевле
            fill_price = market_price / slippage_multiplier

        # Округление до 8 знаков (стандарт для крипты)
        fill_price = fill_price.quantize(Decimal('0.00000001'))

        # 4. Полное исполнение (частичное не поддерживается, см. known_issues.md)
        filled_qty = qty

        # 5. Комиссия (заглушка, реальная из brokers_commissions.json будет в адаптере)
        commission = filled_qty * fill_price * DEFAULT_TAKER_FEE
        commission = commission.quantize(Decimal('0.00000001'))

        # 6. Задержка
        latency_ms = random.randint(self.latency_ms_min, self.latency_ms_max)
        await asyncio.sleep(latency_ms / 1000.0)

        logger.info(
            "Order filled: side=%s, qty=%s, price=%s, latency=%dms, commission=%s",
            order['side'], filled_qty, fill_price, latency_ms, commission
        )

        return {
            'filled': True,
            'fill_price': fill_price,
            'filled_qty': filled_qty,
            'commission': commission,
            'latency_ms': latency_ms,
            'reason': 'full_fill'
        }
