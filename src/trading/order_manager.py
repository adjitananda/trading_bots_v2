"""
Менеджер ордеров.
Отвечает за размещение, отслеживание и запись ордеров в БД.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import traceback
import time

from src.trading.exchange_client import ExchangeClient, OrderError, InsufficientBalanceError
from src.core.database import db
from src.utils.time_utils import now_utc
from src.messages.console_messages import ConsoleMessages
from src.messages.telegram_messages import TelegramMessages


class OrderManagerError(Exception):
    """Базовое исключение для OrderManager"""
    pass


class OrderManager:
    """
    Управление ордерами с автоматической записью в БД.
    
    Отвечает за:
    - Размещение ордеров
    - Отслеживание статуса
    - Запись в таблицы orders и trades
    - Обработку ошибок
    """
    
    def __init__(self, exchange_client: ExchangeClient, bot_id: int, bot_name: str):
        """
        Инициализация менеджера ордеров.
        
        Args:
            exchange_client: Клиент биржи
            bot_id: ID бота в БД
            bot_name: Имя бота (для сообщений)
        """
        self.exchange = exchange_client
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.exchange_id = exchange_client.exchange_id
        
        # Для отслеживания недавних ордеров
        self._recent_orders = {}  # exchange_order_id -> информация
        
    def _get_balance_before_trade(self) -> Optional[float]:
        """Получить баланс перед сделкой"""
        try:
            return self.exchange.get_balance()
        except:
            return None
    
    def _create_order_record(self, order_data: Dict) -> int:
        """
        Создать запись об ордере в БД.
        
        Args:
            order_data: Данные ордера
            
        Returns:
            ID записи в БД
        """
        return db.create_order({
            'bot_id': self.bot_id,
            'exchange_id': self.exchange_id,
            'exchange_order_id': order_data['exchange_order_id'],
            'symbol': order_data['symbol'],
            'side': order_data['side'].upper(),
            'order_type': order_data.get('order_type', 'market'),
            'quantity': order_data['quantity'],
            'price': order_data.get('price'),
            'status': 'new'
        })
    
    def _create_trade_record(self, trade_data: Dict) -> int:
        """
        Создать запись о сделке в БД.
        
        Args:
            trade_data: Данные сделки
            
        Returns:
            ID сделки в БД
        """
        return db.create_trade({
            'bot_id': self.bot_id,
            'exchange_id': self.exchange_id,
            'symbol': trade_data['symbol'],
            'side': trade_data['side'].upper(),
            'entry_time': now_utc(),
            'entry_price': trade_data['price'],
            'quantity': trade_data['quantity'],
            'entry_order_id': trade_data.get('order_id')
        })
    
    def _update_order_status(self, exchange_order_id: str, status_data: Dict):
        """Обновить статус ордера в БД"""
        db.update_order(exchange_order_id, status_data)
    
    def place_market_order(self, symbol: str, side: str, quantity: float,
                          take_profit: float = None, stop_loss: float = None,
                          tp_percent: float = None, sl_percent: float = None) -> Dict:
        """
        Разместить рыночный ордер с полным логированием.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            quantity: Количество
            take_profit: Цена take profit
            stop_loss: Цена stop loss
            tp_percent: Процент TP (для отчета)
            sl_percent: Процент SL (для отчета)
            
        Returns:
            Dict с результатом:
            {
                'success': bool,
                'order_id': str,
                'trade_id': int,
                'error': str (если ошибка)
            }
        """
        print(ConsoleMessages.analyzing_symbol(symbol))
        print(f"  Размещение {side.upper()} ордера, количество: {quantity}")
        
        # Получаем баланс до сделки
        open_balance = self._get_balance_before_trade()
        
        try:
            # 1. Размещаем ордер на бирже
            result = self.exchange.place_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                take_profit=take_profit,
                stop_loss=stop_loss
            )
            
            exchange_order_id = result['order_id']
            print(f"  ✅ Ордер размещен, ID: {exchange_order_id}")
            
            # 2. Создаем запись в таблице orders
            order_data = {
                'exchange_order_id': exchange_order_id,
                'symbol': symbol,
                'side': side,
                'order_type': 'market',
                'quantity': quantity,
                'price': None  # для market ордера цена неизвестна заранее
            }
            order_db_id = self._create_order_record(order_data)
            
            # 3. Получаем текущую цену для записи сделки
            current_price = self.exchange.get_current_price(symbol)
            
            # 4. Создаем запись в таблице trades
            trade_data = {
                'symbol': symbol,
                'side': side,
                'price': current_price,
                'quantity': quantity,
                'order_id': exchange_order_id
            }
            trade_id = self._create_trade_record(trade_data)
            
            # 5. Обновляем ордер с ссылкой на сделку
            self._update_order_status(exchange_order_id, {
                'trade_id': trade_id,
                'status': 'filled',
                'filled_quantity': quantity,
                'average_fill_price': current_price,
                'finished_at': now_utc()
            })
            
            # 6. Сохраняем в кэш недавних ордеров
            self._recent_orders[exchange_order_id] = {
                'trade_id': trade_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': current_price,
                'open_balance': open_balance,
                'tp_price': take_profit,
                'sl_price': stop_loss,
                'tp_percent': tp_percent,
                'sl_percent': sl_percent,
                'timestamp': now_utc()
            }
            
            print(ConsoleMessages.order_placed(symbol, side))
            print(f"  💰 Цена входа: {current_price}")
            if take_profit:
                print(f"  🎯 TP: {take_profit} ({tp_percent}%)")
            if stop_loss:
                print(f"  🛑 SL: {stop_loss} ({sl_percent}%)")
            
            return {
                'success': True,
                'order_id': exchange_order_id,
                'trade_id': trade_id,
                'entry_price': current_price
            }
            
        except InsufficientBalanceError as e:
            error_msg = f"Недостаточно средств: {e}"
            print(ConsoleMessages.error(error_msg))
            return {'success': False, 'error': error_msg}
            
        except OrderError as e:
            error_msg = f"Ошибка ордера: {e}"
            print(ConsoleMessages.error(error_msg))
            return {'success': False, 'error': error_msg}
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e}"
            print(ConsoleMessages.error(error_msg))
            traceback.print_exc()
            return {'success': False, 'error': error_msg}
    
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> Dict:
        """
        Разместить лимитный ордер.
        """
        try:
            result = self.exchange.place_limit_order(symbol, side, price, quantity)
            exchange_order_id = result['order_id']
            
            # Создаем запись в БД
            order_data = {
                'exchange_order_id': exchange_order_id,
                'symbol': symbol,
                'side': side,
                'order_type': 'limit',
                'quantity': quantity,
                'price': price
            }
            self._create_order_record(order_data)
            
            return {
                'success': True,
                'order_id': exchange_order_id
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_order_status(self, exchange_order_id: str) -> Dict:
        """
        Проверить статус ордера и обновить в БД.
        
        Returns:
            Dict со статусом ордера
        """
        try:
            # Получаем информацию из кэша
            cached = self._recent_orders.get(exchange_order_id)
            if not cached:
                # Если нет в кэше, ищем в БД
                order = db.get_order(exchange_order_id)
                if not order:
                    return {'error': 'Ордер не найден'}
                symbol = order['symbol']
            else:
                symbol = cached['symbol']
            
            # Запрашиваем статус с биржи
            status = self.exchange.get_order_status(symbol, exchange_order_id)
            
            if status:
                # Обновляем в БД
                self._update_order_status(exchange_order_id, {
                    'status': status['status'].lower(),
                    'filled_quantity': status.get('executed_qty'),
                    'average_fill_price': status.get('avg_price'),
                    'finished_at': status.get('updated_time')
                })
                
                return status
            
            return {'error': 'Не удалось получить статус'}
            
        except Exception as e:
            return {'error': str(e)}
    
    def cancel_order(self, symbol: str, exchange_order_id: str) -> bool:
        """
        Отменить ордер.
        """
        try:
            success = self.exchange.cancel_order(symbol, exchange_order_id)
            
            if success:
                self._update_order_status(exchange_order_id, {
                    'status': 'cancelled',
                    'cancel_reason': 'USER_CANCELLED',
                    'finished_at': now_utc()
                })
                
                # Удаляем из кэша, если был
                self._recent_orders.pop(exchange_order_id, None)
                
                print(f"  ✅ Ордер {exchange_order_id} отменен")
            
            return success
            
        except Exception as e:
            print(f"  ❌ Ошибка отмены ордера: {e}")
            return False
    
    def check_closed_positions(self, symbol: str = None) -> List[Dict]:
        """
        Проверить закрытые позиции и обновить сделки в БД.
        Теперь игнорирует ордера старше 24 часов и уже обработанные.
        
        Args:
            symbol: Если указан, только по этому символу
            
        Returns:
            Список закрытых сделок
        """
        try:
            # Получаем закрытые сделки с биржи
            closed = self.exchange.get_closed_pnl(symbol=symbol, limit=50)
            
            updated_trades = []
            current_time = now_utc()
            
            # Для логирования (чтобы не спамить)
            skipped_old = 0
            skipped_processed = 0
            
            for item in closed:
                order_id = item.get('order_id')
                if not order_id:
                    continue
                
                # ✅ ФИЛЬТР 1: Пропускаем очень старые ордера (> 24 часов)
                created_time = item.get('created_time')
                if created_time:
                    try:
                        # Конвертируем timestamp с биржи (в миллисекундах)
                        order_time = datetime.fromtimestamp(int(created_time) / 1000)
                        age_hours = (current_time - order_time).total_seconds() / 3600
                        
                        if age_hours > 24:
                            skipped_old += 1
                            continue  # игнорируем старые ордера
                    except (ValueError, TypeError):
                        pass  # если не можем распарсить время, пропускаем проверку
                
                # ✅ ФИЛЬТР 2: Проверяем, есть ли уже этот ордер в нашей БД
                existing_orders = db.get_orders_by_exchange_id(order_id)
                if existing_orders:
                    order_in_db = existing_orders[0]
                    
                    # Если ордер уже есть и он финальный (filled/cancelled) - пропускаем
                    if order_in_db['status'] in ['filled', 'cancelled', 'rejected']:
                        skipped_processed += 1
                        continue
                
                # Проверяем, не обработана ли уже эта сделка
                existing = db.get_trades_by_order_id(order_id)
                if existing:
                    trade = existing[0]
                    if trade['status'] == 'closed':
                        skipped_processed += 1
                        continue
                    else:
                        # Нашли открытую сделку - будем закрывать
                        pass
                
                # Ищем информацию в кэше
                cached = self._recent_orders.get(order_id)
                
                # Определяем причину закрытия
                exit_reason = self._determine_close_reason_short(item, cached)
                
                # Рассчитываем PnL процент
                pnl_percent = 0
                if item['entry_price'] > 0:
                    if item['side'] == 'BUY':
                        pnl_percent = ((item['exit_price'] - item['entry_price']) / item['entry_price']) * 100
                    else:
                        pnl_percent = ((item['entry_price'] - item['exit_price']) / item['entry_price']) * 100
                
                # Получаем trade_id
                trade_id = None
                if cached and cached.get('trade_id'):
                    trade_id = cached['trade_id']
                else:
                    trades = db.get_trades_by_order_id(order_id)
                    if trades:
                        trade_id = trades[0]['id']
                
                if not trade_id:
                    # Если не нашли trade_id, создаем запись в логах, но не кричим
                    # Просто логируем в файл, а не в консоль
                    import logging
                    logging.debug(f"Order {order_id} has no associated trade - skipping")
                    continue
                
                # Подготавливаем данные для закрытия
                exit_time = datetime.fromtimestamp(int(item['created_time']) / 1000) if item['created_time'] else now_utc()
                
                close_data = {
                    'exit_time': exit_time,
                    'exit_price': item['exit_price'],
                    'pnl': item['pnl'],
                    'pnl_percent': pnl_percent,
                    'exit_reason': exit_reason,
                    'exit_order_id': order_id
                }
                
                success = db.close_trade(trade_id, close_data)
                if success:
                    updated_trades.append({
                        'trade_id': trade_id,
                        'symbol': item['symbol'],
                        'pnl': item['pnl'],
                        'pnl_percent': pnl_percent,
                        'reason': exit_reason
                    })
                    
                    # Только для действительно новых закрытий выводим в консоль
                    print(f"  ✅ Сделка {trade_id} по {item['symbol']} закрыта: {item['pnl']:.2f} USDT ({pnl_percent:.2f}%)")
                    
                    # Удаляем из кэша
                    self._recent_orders.pop(order_id, None)
            
            # Если много пропущенных, покажем одну строку вместо кучи
            if skipped_old > 0 or skipped_processed > 0:
                total_skipped = skipped_old + skipped_processed
                if total_skipped > 5:  # только если действительно много
                    print(f"  📊 Пропущено старых/обработанных ордеров: {skipped_old}/{skipped_processed}")
            
            return updated_trades
            
        except Exception as e:
            print(f"  ❌ Ошибка проверки закрытых позиций: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _determine_close_reason_short(self, closed_item: Dict, cached: Optional[Dict]) -> str:
        """
        Определить причину закрытия сделки (короткий код для БД).
        
        Returns:
            'TP', 'SL', 'MANUAL' или 'UNKNOWN' - короткие коды для БД
        """
        if not cached:
            # Если нет кэша, пытаемся определить по данным с биржи
            # Проверяем, есть ли в closed_item информация о причине
            # По умолчанию возвращаем UNKNOWN
            return 'UNKNOWN'
        
        entry_price = cached.get('entry_price')
        exit_price = closed_item['exit_price']
        side = cached.get('side', '').upper()
        
        # Проверяем TP/SL
        tp_price = cached.get('tp_price')
        sl_price = cached.get('sl_price')
        
        # Если TP/SL установлены, проверяем совпадение
        if tp_price is not None and tp_price > 0:
            if abs(exit_price - tp_price) / tp_price < 0.001:  # 0.1% допуск
                return 'TP'
        
        if sl_price is not None and sl_price > 0:
            if abs(exit_price - sl_price) / sl_price < 0.001:
                return 'SL'
        
        # Если не TP и не SL, но цена сильно отличается от входа
        if side == 'BUY':
            if exit_price > entry_price * 1.001:  # >0.1% profit
                return 'TP'
            elif exit_price < entry_price * 0.999:  # >0.1% loss
                return 'SL'
        else:  # SELL
            if exit_price < entry_price * 0.999:
                return 'TP'
            elif exit_price > entry_price * 1.001:
                return 'SL'
        
        return 'MANUAL'  # предположительно ручное закрытие
    
    # Оставляем старый метод для совместимости, но не используем его
    def _determine_close_reason(self, closed_item: Dict, cached: Optional[Dict]) -> str:
        """
        Устаревший метод. Используйте _determine_close_reason_short.
        """
        return self._determine_close_reason_short(closed_item, cached)
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """Получить недавние ордера из БД"""
        return db.get_orders_by_bot(self.bot_id, limit)
    
    def get_open_trades(self) -> List[Dict]:
        """Получить открытые сделки бота"""
        return db.get_open_trades(self.bot_id)
    
    def get_trade_info(self, order_id: str) -> Optional[Dict]:
        """
        Получить информацию о сделке по ID ордера.
        
        Returns:
            Dict с информацией или None
        """
        # Сначала проверяем кэш
        if order_id in self._recent_orders:
            return self._recent_orders[order_id]
        
        # Ищем в БД
        trades = db.get_trades_by_order_id(order_id)
        if trades:
            trade = trades[0]
            return {
                'trade_id': trade['id'],
                'symbol': trade['symbol'],
                'side': trade['side'],
                'entry_price': float(trade['entry_price']),
                'quantity': float(trade['quantity']),
                'open_balance': trade.get('open_balance'),
                'timestamp': trade['entry_time']
            }
        
        return None