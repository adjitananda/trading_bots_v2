"""
Адаптер для Bybit.
Реализует ExchangeInterface используя существующий exchange_client.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.trading.exchange_client import ExchangeClient
from src.exchanges.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class BybitAdapter(ExchangeInterface):
    """Адаптер для биржи Bybit"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация адаптера.
        
        Args:
            config: Конфигурация биржи (api_key, api_secret, testnet и т.д.)
        """
        self.config = config or {}
        # Используем существующий ExchangeClient (требует exchange_name)
        self.client = ExchangeClient('bybit')
        self.name = "bybit"
        self.exchange_type = "futures"  # Bybit futures
        self.trading_hours = None  # 24/7
        
        logger.info(f"✅ BybitAdapter инициализирован (testnet={self.config.get('testnet', False)})")
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Получить баланс.
        """
        try:
            # ExchangeClient.get_balance() возвращает баланс в USDT
            balance = self.client.get_balance()
            
            if currency:
                # Если запрошена конкретная валюта
                if currency.upper() == 'USDT':
                    return {'USDT': balance}
                else:
                    # Для других валют нужно будет расширить
                    return {currency: 0.0}
            
            # Возвращаем USDT баланс (основная валюта для фьючерсов)
            return {'USDT': balance}
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return {'USDT': 0.0}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Получить историю свечей.
        
        Args:
            symbol: Торговая пара (например 'ETHUSDT')
            interval: Таймфрейм ('5m', '1h', '1d' и т.д.)
            limit: Количество свечей
        """
        try:
            # ExchangeClient.get_klines возвращает DataFrame
            df = self.client.get_klines(symbol, interval, limit)
            
            if df is None or df.empty:
                return []
            
            # Конвертируем DataFrame в список словарей
            klines = []
            for idx, row in df.iterrows():
                klines.append({
                    'timestamp': int(idx.timestamp()) if hasattr(idx, 'timestamp') else 0,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            
            return klines
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей для {symbol}: {e}")
            return []
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'market',
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Разместить ордер.
        
        Использует существующий ExchangeClient.place_order()
        """
        try:
            # ExchangeClient.place_order ожидает side в нижнем регистре
            side_lower = side.lower()
            
            # Для маркет ордеров price не нужен
            if order_type == 'market':
                order = self.client.place_order(
                    symbol=symbol,
                    side=side_lower,
                    quantity=quantity,
                    order_type='market'
                )
            else:
                order = self.client.place_order(
                    symbol=symbol,
                    side=side_lower,
                    quantity=quantity,
                    order_type=order_type,
                    price=price
                )
            
            # Приводим к единому формату
            return {
                'order_id': order.get('order_id', ''),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'filled_quantity': order.get('filled_quantity', 0),
                'price': price,
                'average_fill_price': order.get('avg_price', 0),
                'status': order.get('status', 'new'),
                'order_type': order_type,
                'raw_response': order
            }
        except Exception as e:
            logger.error(f"❌ Ошибка размещения ордера {side} {quantity} {symbol}: {e}")
            return {
                'order_id': '',
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'filled_quantity': 0,
                'price': price,
                'average_fill_price': 0,
                'status': 'rejected',
                'error': str(e)
            }
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Отменить ордер.
        """
        try:
            if not symbol:
                logger.warning("⚠️ Для отмены ордера нужен symbol")
                return False
            
            result = self.client.cancel_order(symbol, order_id)
            return result.get('success', False)
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордера {order_id}: {e}")
            return False
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Получить список открытых ордеров.
        """
        try:
            # ExchangeClient.get_open_orders требует symbol
            if not symbol:
                return []
            
            orders = self.client.get_open_orders(symbol)
            
            # Приводим к единому формату
            result = []
            for order in orders:
                result.append({
                    'order_id': order.get('order_id', ''),
                    'symbol': order.get('symbol', symbol),
                    'side': order.get('side', ''),
                    'quantity': float(order.get('qty', 0)),
                    'filled_quantity': float(order.get('filled_qty', 0)),
                    'price': float(order.get('price', 0)) if order.get('price') else None,
                    'status': order.get('status', ''),
                    'order_type': order.get('order_type', '')
                })
            
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения открытых ордеров: {e}")
            return []
    
    def get_symbols(self) -> List[str]:
        """
        Получить список всех доступных торговых пар.
        """
        try:
            # Возвращаем основные пары с USDT
            return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOGEUSDT', 
                    'LTCUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка символов: {e}")
            return []
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Получить информацию о бирже.
        """
        return {
            'name': self.name,
            'display_name': 'Bybit',
            'type': self.exchange_type,
            'trading_hours': self.trading_hours,  # 24/7
            'fees': {
                'maker': 0.0002,  # 0.02%
                'taker': 0.00055  # 0.055%
            },
            'is_testnet': self.config.get('testnet', False)
        }
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """
        Получить текущую цену и статистику по символу.
        """
        try:
            # Используем ExchangeClient.get_current_price
            price = self.client.get_current_price(symbol)
            
            return {
                'last': price,
                'bid': price,  # Bybit не даёт просто bid/ask без отдельного запроса
                'ask': price,
                'volume': 0,
                'high': 0,
                'low': 0
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера для {symbol}: {e}")
            return {
                'last': 0,
                'bid': 0,
                'ask': 0,
                'volume': 0,
                'high': 0,
                'low': 0
            }
    
    def test_connection(self) -> bool:
        """
        Проверить подключение к бирже.
        """
        try:
            # Пробуем получить баланс (простой тест)
            balance = self.get_balance()
            return balance.get('USDT', 0) >= 0
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Bybit: {e}")
            return False
