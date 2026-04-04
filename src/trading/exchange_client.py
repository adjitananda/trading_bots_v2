"""
Клиент для работы с биржами.
Абстрагирует API конкретной биржи за единым интерфейсом.
"""

import os
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import requests
from decimal import Decimal, ROUND_DOWN
import json
from functools import lru_cache
import threading

from pybit.unified_trading import HTTP as BybitHTTP
from src.core.database import db
from src.utils.time_utils import now_utc


class ExchangeError(Exception):
    """Базовое исключение для ошибок биржи"""
    pass


class RateLimitError(ExchangeError):
    """Превышение лимитов API"""
    pass


class InsufficientBalanceError(ExchangeError):
    """Недостаточно средств"""
    pass


class OrderError(ExchangeError):
    """Ошибка при размещении ордера"""
    pass


class ExchangeClient:
    """
    Единый клиент для работы с биржами.
    Поддерживает несколько бирж через фабричный метод.
    Все подключения идут к основной сети (mainnet).
    """
    
    def __init__(self, exchange_name: str, api_key: str = None, api_secret: str = None):
        """
        Инициализация клиента для конкретной биржи (всегда mainnet).
        
        Args:
            exchange_name: 'bybit', 'binance' и т.д.
            api_key: API ключ (если None, берется из .env)
            api_secret: Секретный ключ (если None, берется из .env)
        """
        self.exchange_name = exchange_name.lower()
        
        # Получаем ID биржи из БД (только основная сеть)
        self.exchange_id = db.get_exchange_id(exchange_name)
        if not self.exchange_id:
            raise ExchangeError(f"Биржа {exchange_name} не найдена в БД")
        
        # Загружаем API ключи
        self.api_key = api_key or os.getenv(f'{exchange_name.upper()}_API_KEY')
        self.api_secret = api_secret or os.getenv(f'{exchange_name.upper()}_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ExchangeError(f"API ключи для {exchange_name} не найдены в .env")
        
        # Инициализируем конкретного клиента (всегда mainnet)
        self._client = self._create_client()
        
        # Кэш для часто запрашиваемых данных
        self._cache = {}
        self._cache_lock = threading.Lock()
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100 мс между запросами
        
        pass
    
    def _create_client(self):
        """Создание клиента для конкретной биржи (всегда mainnet)"""
        if self.exchange_name == 'bybit':
            return BybitHTTP(
                testnet=False,  # Всегда mainnet
                api_key=self.api_key,
                api_secret=self.api_secret
            )
        elif self.exchange_name == 'binance':
            # TODO: добавить Binance клиент
            raise NotImplementedError("Binance пока не поддерживается")
        else:
            raise ExchangeError(f"Неподдерживаемая биржа: {self.exchange_name}")
    
    def _rate_limit(self):
        """Примитивный rate limiting"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _handle_response(self, response: Dict) -> Dict:
        """
        Обработка ответа от биржи.
        
        Args:
            response: Ответ от API биржи
            
        Returns:
            Нормализованный ответ
            
        Raises:
            ExchangeError: в случае ошибки
        """
        if self.exchange_name == 'bybit':
            if response.get('retCode') != 0:
                error_code = response.get('retCode')
                error_msg = response.get('retMsg', 'Unknown error')
                
                if error_code == 10002:  # Rate limit
                    raise RateLimitError(f"Rate limit: {error_msg}")
                elif error_code == 10020:  # Insufficient balance
                    raise InsufficientBalanceError(f"Недостаточно средств: {error_msg}")
                else:
                    raise ExchangeError(f"API Error {error_code}: {error_msg}")
            
            return response.get('result', {})
        
        return response
    
    # ==================== БАЛАНС ====================
    
    def get_balance(self, asset: str = 'USDT') -> Optional[float]:
        """
        Получение баланса по активу.
        
        Args:
            asset: Актив (USDT, BTC и т.д.)
            
        Returns:
            Баланс или None при ошибке
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.get_wallet_balance(
                    accountType="UNIFIED",
                    coin=asset
                )
                result = self._handle_response(response)
                
                # Парсим ответ ByBit
                if result and 'list' in result and len(result['list']) > 0:
                    for coin in result['list'][0].get('coin', []):
                        if coin.get('coin') == asset:
                            return float(coin.get('walletBalance', 0))
            
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка получения баланса: {e}")
            return None
    
    @lru_cache(maxsize=1)
    def get_balance_cached(self, asset: str = 'USDT', cache_seconds: int = 10) -> Optional[float]:
        """
        Получение баланса с кэшированием.
        
        Args:
            asset: Актив
            cache_seconds: Время жизни кэша в секундах
            
        Returns:
            Баланс
        """
        return self.get_balance(asset)
    
    # ==================== ПОЗИЦИИ ====================
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """
        Получение открытых позиций.
        
        Args:
            symbol: Если указан, только по этому символу
            
        Returns:
            Список позиций в нормализованном формате
        """
        self._rate_limit()

        # Для тестового бота возвращаем пустой список
        if symbol == 'TEST_BOT':
            return []
        
        try:
            if self.exchange_name == 'bybit':
                params = {'category': 'linear', 'settleCoin': 'USDT'}
                if symbol:
                    params['symbol'] = symbol
                
                response = self._client.get_positions(**params)
                result = self._handle_response(response)
                
                positions = []
                for pos in result.get('list', []):
                    size = float(pos.get('size', 0))
                    if size > 0:  # Только позиции с размером > 0
                        positions.append({
                            'symbol': pos['symbol'],
                            'side': 'LONG' if pos['side'] == 'Buy' else 'SHORT',
                            'size': size,
                            'entry_price': float(pos.get('avgPrice', 0)),
                            'leverage': float(pos.get('leverage', 1)),
                            'mark_price': float(pos.get('markPrice', 0)),
                            'unrealised_pnl': float(pos.get('unrealisedPnl', 0)),
                            'position_value': float(pos.get('positionValue', 0)),
                            'liq_price': float(pos.get('liqPrice', 0)) if pos.get('liqPrice') else None,
                            'take_profit': float(pos.get('takeProfit', 0)) if pos.get('takeProfit') else None,
                            'stop_loss': float(pos.get('stopLoss', 0)) if pos.get('stopLoss') else None
                        })
                
                return positions
            
            return []
            
        except Exception as e:
            print(f"⚠️ Ошибка получения позиций: {e}")
            return []
    
    def get_position_pnl(self, symbol: str) -> Optional[float]:
        """
        Получить нереализованный PnL по позиции.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Нереализованный PnL или None
        """
        positions = self.get_positions(symbol)
        if positions:
            return positions[0].get('unrealised_pnl')
        return None
    
    # ==================== СВЕЧИ ====================
    
    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Получение исторических свечей.
        
        Args:
            symbol: Торговая пара
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Количество свечей
            
        Returns:
            DataFrame с колонками: timestamp, open, high, low, close, volume
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.get_kline(
                    category='linear',
                    symbol=symbol,
                    interval=str(interval),
                    limit=limit
                )
                result = self._handle_response(response)
                
                if not result or 'list' not in result:
                    return None
                
                # Преобразуем в DataFrame
                data = result['list']
                if not data:
                    return None
                
                # Создаём DataFrame
                df = pd.DataFrame(data)
                # В Bybit ответ содержит: timestamp, open, high, low, close, volume, turnover
                if len(df.columns) >= 6:
                    df = df.iloc[:, :6]  # Берём первые 6 колонок
                    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                else:
                    return None
                
                # Конвертируем типы
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df = df.set_index('timestamp')
                df = df[::-1]  # Переворачиваем (от старых к новым)
                
                return df
            
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка получения свечей для {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получить текущую цену (mark price).
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Текущая цена
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.get_tickers(
                    category='linear',
                    symbol=symbol
                )
                result = self._handle_response(response)
                
                if result and 'list' in result and len(result['list']) > 0:
                    return float(result['list'][0]['markPrice'])
            
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка получения цены для {symbol}: {e}")
            return None
    
    # ==================== ИНСТРУМЕНТЫ ====================
    
    def get_instrument_info(self, symbol: str) -> Dict:
        """
        Получить информацию о торговом инструменте.
        
        Returns:
            Словарь с параметрами: price_precision, qty_step, min_qty, min_notional и т.д.
        """
        cache_key = f"instrument_{symbol}"
        
        # Проверяем кэш
        with self._cache_lock:
            if cache_key in self._cache:
                cache_time, data = self._cache[cache_key]
                if (datetime.now() - cache_time).seconds < 3600:  # 1 час кэш
                    return data
        
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.get_instruments_info(
                    category='linear',
                    symbol=symbol
                )
                result = self._handle_response(response)
                
                if not result or 'list' not in result or len(result['list']) == 0:
                    raise ExchangeError(f"Инструмент {symbol} не найден")
                
                info = result['list'][0]
                
                # Парсим параметры
                price_filter = info['priceFilter']
                lot_filter = info['lotSizeFilter']
                
                # Вычисляем точность цены
                tick_size = price_filter['tickSize']
                price_precision = len(tick_size.split('.')[1]) if '.' in tick_size else 0
                
                instrument_data = {
                    'symbol': symbol,
                    'price_precision': price_precision,
                    'qty_step': float(lot_filter['qtyStep']),
                    'min_qty': float(lot_filter['minOrderQty']),
                    'max_qty': float(lot_filter['maxOrderQty']),
                    'min_notional': float(lot_filter['minNotionalValue']),
                    'max_leverage': float(info['leverageFilter']['maxLeverage']),
                    'tick_size': float(tick_size)
                }
                
                # Сохраняем в кэш
                with self._cache_lock:
                    self._cache[cache_key] = (datetime.now(), instrument_data)
                
                return instrument_data
            
            return {}
            
        except Exception as e:
            print(f"⚠️ Ошибка получения информации об инструменте {symbol}: {e}")
            return {}
    
    def calculate_quantity(self, symbol: str, usdt_amount: float, price: float = None) -> float:
        """
        Рассчитать количество для ордера с учетом ограничений.
        
        Args:
            symbol: Торговая пара
            usdt_amount: Сумма в USDT
            price: Цена (если None, будет получена текущая)
            
        Returns:
            Корректное количество
        """
        if price is None:
            price = self.get_current_price(symbol)
            if price is None:
                raise ExchangeError(f"Не удалось получить цену для {symbol}")
        
        # Получаем параметры инструмента
        info = self.get_instrument_info(symbol)
        
        # Рассчитываем сырое количество
        raw_qty = usdt_amount / price
        
        # Округляем до шага
        qty_step = info.get('qty_step', 0.001)
        qty_calc = float(Decimal(str(raw_qty)).quantize(
            Decimal(str(qty_step)), rounding=ROUND_DOWN
        ))
        
        # Проверяем минимальное количество
        min_qty = info.get('min_qty', 0.001)
        if qty_calc < min_qty:
            qty_calc = min_qty
        
        # Проверяем минимальную стоимость
        min_notional = info.get('min_notional', 5)
        notional = qty_calc * price
        if notional < min_notional:
            qty_calc = (min_notional / price) // qty_step * qty_step + qty_step
        
        # Финальное округление
        if qty_step < 1:
            precision = len(str(qty_step).split('.')[1])
            qty_calc = round(qty_calc, precision)
        else:
            qty_calc = int(qty_calc)
        
        return qty_calc
    
    # ==================== ОРДЕРА ====================
    
    def place_market_order(self, symbol: str, side: str, quantity: float,
                           take_profit: float = None, stop_loss: float = None) -> Dict:
        """
        Разместить рыночный ордер.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            quantity: Количество
            take_profit: Цена take profit (опционально)
            stop_loss: Цена stop loss (опционально)
            
        Returns:
            Информация об ордере
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                params = {
                    'category': 'linear',
                    'symbol': symbol,
                    'side': 'Buy' if side.lower() == 'buy' else 'Sell',
                    'orderType': 'Market',
                    'qty': str(quantity),
                    'positionIdx': 0  # One-way mode
                }
                
                if take_profit:
                    params['takeProfit'] = str(take_profit)
                    params['tpTriggerBy'] = 'MarkPrice'
                
                if stop_loss:
                    params['stopLoss'] = str(stop_loss)
                    params['slTriggerBy'] = 'MarkPrice'
                
                response = self._client.place_order(**params)
                result = self._handle_response(response)
                
                return {
                    'order_id': result.get('orderId'),
                    'symbol': symbol,
                    'side': side,
                    'type': 'market',
                    'quantity': quantity,
                    'status': 'placed',
                    'raw_response': result
                }
            
            return {}
            
        except Exception as e:
            raise OrderError(f"Ошибка размещения ордера: {e}")
    
    def place_limit_order(self, symbol: str, side: str, price: float, 
                          quantity: float) -> Dict:
        """
        Разместить лимитный ордер.
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.place_order(
                    category='linear',
                    symbol=symbol,
                    side='Buy' if side.lower() == 'buy' else 'Sell',
                    orderType='Limit',
                    qty=str(quantity),
                    price=str(price),
                    positionIdx=0
                )
                result = self._handle_response(response)
                
                return {
                    'order_id': result.get('orderId'),
                    'symbol': symbol,
                    'side': side,
                    'type': 'limit',
                    'price': price,
                    'quantity': quantity,
                    'status': 'placed'
                }
            
            return {}
            
        except Exception as e:
            raise OrderError(f"Ошибка размещения лимитного ордера: {e}")
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Отменить ордер.
        
        Returns:
            True если успешно
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.cancel_order(
                    category='linear',
                    symbol=symbol,
                    orderId=order_id
                )
                self._handle_response(response)
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Ошибка отмены ордера: {e}")
            return False
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Получить статус ордера.
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.get_order_history(
                    category='linear',
                    symbol=symbol,
                    orderId=order_id
                )
                result = self._handle_response(response)
                
                if result and 'list' in result and len(result['list']) > 0:
                    order = result['list'][0]
                    return {
                        'order_id': order['orderId'],
                        'status': order['orderStatus'],
                        'executed_qty': float(order.get('cumExecQty', 0)),
                        'executed_value': float(order.get('cumExecValue', 0)),
                        'avg_price': float(order.get('avgPrice', 0)) if order.get('avgPrice') else None,
                        'created_time': order.get('createdTime'),
                        'updated_time': order.get('updatedTime')
                    }
            
            return {}
            
        except Exception as e:
            print(f"⚠️ Ошибка получения статуса ордера: {e}")
            return {}
    
    # ==================== ЗАКРЫТЫЕ СДЕЛКИ ====================
    
    def get_closed_pnl(self, symbol: str = None, limit: int = 50) -> List[Dict]:
        """
        Получить историю закрытых сделок с PnL.
        
        Args:
            symbol: Фильтр по символу
            limit: Количество записей
            
        Returns:
            Список закрытых сделок
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                params = {'category': 'linear', 'limit': limit}
                if symbol:
                    params['symbol'] = symbol
                
                response = self._client.get_closed_pnl(**params)
                result = self._handle_response(response)
                
                trades = []
                for item in result.get('list', []):
                    trades.append({
                        'symbol': item['symbol'],
                        'order_id': item.get('orderId'),
                        'side': 'BUY' if item['side'] == 'Buy' else 'SELL',
                        'entry_price': float(item.get('avgEntryPrice', 0)),
                        'exit_price': float(item.get('avgExitPrice', 0)),
                        'quantity': float(item.get('qty', 0)),
                        'pnl': float(item.get('closedPnl', 0)),
                        'fee': float(item.get('fee', 0)),
                        'created_time': item.get('createdTime'),
                        'updated_time': item.get('updatedTime')
                    })
                
                return trades
            
            return []
            
        except Exception as e:
            print(f"⚠️ Ошибка получения истории закрытых сделок: {e}")
            return []
    
    # ==================== НАСТРОЙКИ ====================
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Установить плечо.
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                response = self._client.set_leverage(
                    category='linear',
                    symbol=symbol,
                    buyLeverage=str(leverage),
                    sellLeverage=str(leverage)
                )
                self._handle_response(response)
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Ошибка установки плеча: {e}")
            return False
    
    def set_position_mode(self, symbol: str, mode: int = 0) -> bool:
        """
        Установить режим позиции (0 - one-way, 3 - hedge).
        """
        self._rate_limit()
        
        try:
            if self.exchange_name == 'bybit':
                # Проверяем текущий режим
                response = self._client.switch_position_mode(
                    category='linear',
                    symbol=symbol,
                    mode=str(mode)
                )
                self._handle_response(response)
                return True
            
            return False
            
        except Exception as e:
            if "110025" not in str(e) and "No need to change" not in str(e):
                print(f"⚠️ Ошибка установки режима позиции: {e}")
            return False
    
    # ==================== ТЕСТОВЫЕ МЕТОДЫ ====================
    
    def test_connection(self) -> bool:
        """
        Проверить подключение к бирже.
        
        Returns:
            True если подключение работает
        """
        try:
            balance = self.get_balance()
            return balance is not None
        except:
            return False


# Фабрика для создания клиентов
class ExchangeFactory:
    """Фабрика для создания клиентов бирж (только mainnet)"""
    
    @staticmethod
    def create_client(exchange_name: str) -> ExchangeClient:
        """
        Создать клиент для биржи (всегда mainnet).
        
        Args:
            exchange_name: 'bybit', 'binance'
            
        Returns:
            Экземпляр ExchangeClient
        """
        return ExchangeClient(exchange_name)
    
    @staticmethod
    def create_client_for_bot(bot_name: str) -> ExchangeClient:
        """
        Создать клиент для конкретного бота (по его настройкам из БД).
        Всегда использует основную сеть (mainnet).
        
        Args:
            bot_name: Имя бота
            
        Returns:
            Экземпляр ExchangeClient
        """
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            raise ExchangeError(f"Бот {bot_name} не найден")
        
        exchange = db.get_exchange(bot['exchange_id'])
        if not exchange:
            raise ExchangeError(f"Биржа для бота {bot_name} не найдена")
        
        # Извлекаем имя биржи без суффиксов _demo, _test
        exchange_name = exchange['name'].replace('_demo', '').replace('_test', '')
        
        # Всегда используем mainnet
        return ExchangeClient(exchange_name)