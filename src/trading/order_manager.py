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
    
    def _create_order_record(self, order_data: Dict, source: str = "auto") -> int:
        """
        Создать запись об ордере в БД.
        
        Args:
            order_data: Данные ордера
            source: Источник ордера ("auto" или "manual")
            
        Returns:
            ID записи в БД
        """
        return db.create_order({
            "bot_id": self.bot_id,
            "exchange_id": self.exchange_id,
            "exchange_order_id": order_data["exchange_order_id"],
            "symbol": order_data["symbol"],
            "side": order_data["side"].upper(),
            "order_type": order_data.get("order_type", "market"),
            "quantity": order_data["quantity"],
            "price": order_data.get("price"),
            "status": "new",
            "source": source  # НОВОЕ ПОЛЕ
        })
    
    def _create_trade_record(self, trade_data: Dict, source: str = "auto") -> int:
        """
        Создать запись о сделке в БД.
        
        Args:
            trade_data: Данные сделки
            source: Источник сделки ("auto" или "manual")
            
        Returns:
            ID сделки в БД
        """
        return db.create_trade({
            "bot_id": self.bot_id,
            "exchange_id": self.exchange_id,
            "symbol": trade_data["symbol"],
            "side": trade_data["side"].upper(),
            "entry_time": now_utc(),
            "entry_price": trade_data["price"],
            "quantity": trade_data["quantity"],
            "entry_order_id": trade_data.get("order_id"),
            "source_entry": source  # НОВОЕ ПОЛЕ
        })
    
    def _update_order_status(self, exchange_order_id: str, status_data: Dict):
        """Обновить статус ордера в БД"""
        db.update_order(exchange_order_id, status_data)
    
    def place_market_order(self, symbol: str, side: str, quantity: float,
                          take_profit: float = None, stop_loss: float = None,
                          tp_percent: float = None, sl_percent: float = None,
                          source: str = "auto") -> Dict:  # НОВЫЙ ПАРАМЕТР
        """
        Разместить рыночный ордер с полным логированием.
        
        Args:
            symbol: Торговая пара
            side: "buy" или "sell"
            quantity: Количество
            take_profit: Цена take profit
            stop_loss: Цена stop loss
            tp_percent: Процент TP (для отчета)
            sl_percent: Процент SL (для отчета)
            source: Источник ордера ("auto" или "manual")
            
        Returns:
            Dict с результатом:
            {
                "success": bool,
                "order_id": str,
                "trade_id": int,
                "error": str (если ошибка)
            }
        """
        print(ConsoleMessages.analyzing_symbol(symbol))
        print(f"  Размещение {side.upper()} ордера, количество: {quantity} (источник: {source})")
        
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
            
            exchange_order_id = result["order_id"]
            print(f"  ✅ Ордер размещен, ID: {exchange_order_id}")
            
            # 2. Создаем запись в таблице orders
            order_data = {
                "exchange_order_id": exchange_order_id,
                "symbol": symbol,
                "side": side,
                "order_type": "market",
                "quantity": quantity,
                "price": None  # для market ордера цена неизвестна заранее
            }
            order_db_id = self._create_order_record(order_data, source)
            
            # 3. Получаем текущую цену для записи сделки
            current_price = self.exchange.get_current_price(symbol)
            
            # 4. Создаем запись в таблице trades
            trade_data = {
                "symbol": symbol,
                "side": side,
                "price": current_price,
                "quantity": quantity,
                "order_id": exchange_order_id
            }
            trade_id = self._create_trade_record(trade_data, source)
            
            # 5. Обновляем ордер с ссылкой на сделку
            self._update_order_status(exchange_order_id, {
                "trade_id": trade_id,
                "status": "filled",
                "filled_quantity": quantity,
                "average_fill_price": current_price,
                "finished_at": now_utc()
            })
            
            # 6. Сохраняем в кэш недавних ордеров
            self._recent_orders[exchange_order_id] = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": current_price,
                "open_balance": open_balance,
                "tp_price": take_profit,
                "sl_price": stop_loss,
                "tp_percent": tp_percent,
                "sl_percent": sl_percent,
                "source": source,  # НОВОЕ ПОЛЕ
                "timestamp": now_utc()
            }
            
            print(ConsoleMessages.order_placed(symbol, side))
            print(f"  💰 Цена входа: {current_price}")
            if take_profit:
                print(f"  🎯 TP: {take_profit} ({tp_percent}%)")
            if stop_loss:
                print(f"  🛑 SL: {stop_loss} ({sl_percent}%)")
            
            return {
                "success": True,
                "order_id": exchange_order_id,
                "trade_id": trade_id,
                "entry_price": current_price
            }
            
        except InsufficientBalanceError as e:
            error_msg = f"Недостаточно средств: {e}"
            print(ConsoleMessages.error(error_msg))
            return {"success": False, "error": error_msg}
            
        except OrderError as e:
            error_msg = f"Ошибка ордера: {e}"
            print(ConsoleMessages.error(error_msg))
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e}"
            print(ConsoleMessages.error(error_msg))
            traceback.print_exc()
            return {"success": False, "error": error_msg}
    
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float,
                         source: str = "auto") -> Dict:  # НОВЫЙ ПАРАМЕТР
        """
        Разместить лимитный ордер.
        """
        try:
            result = self.exchange.place_limit_order(symbol, side, price, quantity)
            exchange_order_id = result["order_id"]
            
            # Создаем запись в БД
            order_data = {
                "exchange_order_id": exchange_order_id,
                "symbol": symbol,
                "side": side,
                "order_type": "limit",
                "quantity": quantity,
                "price": price
            }
            self._create_order_record(order_data, source)
            
            return {
                "success": True,
                "order_id": exchange_order_id
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
                    return {"error": "Ордер не найден"}
                symbol = order["symbol"]
            else:
                symbol = cached["symbol"]
            
            # Запрашиваем статус с биржи
            status = self.exchange.get_order_status(symbol, exchange_order_id)
            
            if status:
                # Обновляем в БД
                self._update_order_status(exchange_order_id, {
                    "status": status["status"].lower(),
                    "filled_quantity": status.get("executed_qty"),
                    "average_fill_price": status.get("avg_price"),
                    "finished_at": status.get("updated_time")
                })
                
                return status
            
            return {"error": "Не удалось получить статус"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def cancel_order(self, symbol: str, exchange_order_id: str) -> bool:
        """
        Отменить ордер.
        """
        try:
            success = self.exchange.cancel_order(symbol, exchange_order_id)
            
            if success:
                self._update_order_status(exchange_order_id, {
                    "status": "cancelled",
                    "cancel_reason": "USER_CANCELLED",
                    "finished_at": now_utc()
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
        Теперь использует поле source для точного определения причины закрытия.
        
        Args:
            symbol: Если указан, только по этому символу
            
        Returns:
            Список закрытых сделок
        """
        print(f"\n🔍🔍🔍 OrderManager.check_closed_positions() вызван для symbol={symbol}")
        print(f"🔍 Текущее время: {now_utc()}")

        try:
            # Получаем закрытые сделки с биржи
            closed = self.exchange.get_closed_pnl(symbol=symbol, limit=50)
            
            updated_trades = []
            current_time = now_utc()
            
            # Для логирования (чтобы не спамить)
            skipped_old = 0
            skipped_processed = 0
            
            for item in closed:
                order_id = item.get("order_id")

                print(f"\n  --- Проверка ордера {order_id} ---")
                print(f"  Данные с биржи: side={item.get('side')}, pnl={item.get('pnl')}")

                if not order_id:
                    continue
                
                # ✅ ФИЛЬТР 1: Пропускаем очень старые ордера (> 24 часов)
                created_time = item.get("created_time")
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
                    if order_in_db["status"] in ["filled", "cancelled", "rejected"]:
                        skipped_processed += 1
                        continue
                
                # Проверяем, не обработана ли уже эта сделка
                existing = db.get_trades_by_order_id(order_id)
                if existing:
                    trade = existing[0]
                    if trade["status"] == "closed":
                        skipped_processed += 1
                        continue
                    else:
                        # Нашли открытую сделку - будем закрывать
                        pass
                
                # Ищем информацию в кэше
                cached = self._recent_orders.get(order_id)
                
                # ===== УЛУЧШЕННОЕ ОПРЕДЕЛЕНИЕ ПРИЧИНЫ ЗАКРЫТИЯ =====
                # Получаем источник ордера входа
                source_entry = "auto"
                if cached and cached.get("source"):
                    source_entry = cached["source"]
                else:
                    # Пробуем найти в БД
                    entry_orders = db.get_orders_by_exchange_id(order_id)
                    if entry_orders and entry_orders[0].get("source"):
                        source_entry = entry_orders[0]["source"]
                
                # Определяем причину закрытия с учётом источника
                exit_reason, source_exit = self._determine_close_reason_enhanced(
                    item, cached, source_entry
                )
                
                # Рассчитываем PnL процент
                pnl_percent = 0
                if item["entry_price"] > 0:
                    if item["side"] == "BUY":
                        pnl_percent = ((item["exit_price"] - item["entry_price"]) / item["entry_price"]) * 100
                    else:
                        pnl_percent = ((item["entry_price"] - item["exit_price"]) / item["entry_price"]) * 100
                
                # Получаем trade_id
                trade_id = None
                if cached and cached.get("trade_id"):
                    trade_id = cached["trade_id"]
                else:
                    trades = db.get_trades_by_order_id(order_id)
                    if trades:
                        trade_id = trades[0]["id"]
                
                if not trade_id:
                    # Если не нашли trade_id, создаем запись в логах, но не кричим
                    import logging
                    logging.debug(f"Order {order_id} has no associated trade - skipping")
                    continue
                
                # Подготавливаем данные для закрытия
                exit_time = datetime.fromtimestamp(int(item["created_time"]) / 1000) if item["created_time"] else now_utc()
                
                close_data = {
                    "exit_time": exit_time,
                    "exit_price": item["exit_price"],
                    "pnl": item["pnl"],
                    "pnl_percent": pnl_percent,
                    "exit_reason": exit_reason,
                    "exit_order_id": order_id,
                    "source_exit": source_exit  # НОВОЕ ПОЛЕ
                }
                
                success = db.close_trade(trade_id, close_data)
                if success:
                    # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ =====
                    try:
                        from src.telegram.notifier import notifier
                        trade_details = db.get_trade(trade_id)
                        if trade_details:
                            # Получаем бота для strategy_name
                            bot = db.get_bot(trade_details['bot_id'])
                            
                            notifier.send_close_notification({
                                "bot_name": trade_details['bot_name'],
                                "symbol": item["symbol"],
                                "side": trade_details["side"],
                                "entry_price": float(trade_details["entry_price"]),
                                "exit_price": item["exit_price"],
                                "quantity": float(trade_details["quantity"]),
                                "pnl": item["pnl"],
                                "pnl_percent": pnl_percent,
                                "reason": exit_reason,
                                "balance": 0,  # можно добавить получение баланса
                                "symbol_pnl": 0,
                                "total_pnl": 0,
                                "strategy_name": bot.get("strategy_type", "unknown") if bot else "unknown",
                                "entry_time": trade_details["entry_time"],
                                "order_id": order_id,
                                "source_entry": source_entry,
                                "source_exit": source_exit
                            })
                            print(f"  ✅ Уведомление о закрытии отправлено для сделки {trade_id}")
                    except Exception as e:
                        print(f"  ⚠️ Ошибка отправки уведомления о закрытии: {e}")
                    updated_trades.append({
                        "trade_id": trade_id,
                        "symbol": item["symbol"],
                        "pnl": item["pnl"],
                        "pnl_percent": pnl_percent,
                        "reason": exit_reason,
                        "source_entry": source_entry,
                        "source_exit": source_exit
                    })
                    
                    # Только для действительно новых закрытий выводим в консоль
                    source_info = f"[{source_entry}→{source_exit}]"
                    print(f"  ✅ Сделка {trade_id} по {item["symbol"]} закрыта: {item["pnl"]:.2f} USDT ({pnl_percent:.2f}%) {source_info}")
                    
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
    
    # ===== НОВЫЙ УЛУЧШЕННЫЙ МЕТОД ОПРЕДЕЛЕНИЯ ПРИЧИНЫ =====
    def _determine_close_reason_enhanced(self, closed_item: Dict, cached: Optional[Dict], 
                                         source_entry: str) -> tuple:
        """
        Определить причину и источник закрытия сделки.
        
        Args:
            closed_item: Данные закрытой сделки с биржи
            cached: Кэшированная информация об ордере входа
            source_entry: Источник входа ("auto" или "manual")
            
        Returns:
            tuple: (exit_reason, source_exit)
        """
        exit_price = closed_item["exit_price"]
        
        # Если есть кэшированная информация
        if cached:
            entry_price = cached.get("entry_price")
            side = cached.get("side", "").upper()
            tp_price = cached.get("tp_price")
            sl_price = cached.get("sl_price")
            
            # Проверяем TP/SL с допуском 0.1%
            if tp_price is not None and tp_price > 0:
                if abs(exit_price - tp_price) / tp_price < 0.001:
                    return ("TP", "auto" if source_entry == "auto" else "manual")
            
            if sl_price is not None and sl_price > 0:
                if abs(exit_price - sl_price) / sl_price < 0.001:
                    return ("SL", "auto" if source_entry == "auto" else "manual")
            
            # Если не TP/SL, но есть cached, значит это ручное закрытие
            return ("MANUAL", "manual")
        
        # Если нет кэша, смотрим в БД
        order_id = closed_item.get("order_id")
        if order_id:
            entry_orders = db.get_orders_by_exchange_id(order_id)
            if entry_orders and entry_orders[0].get("source") == "auto":
                # Автоматическая сделка, но не TP/SL (вероятно ручное закрытие)
                return ("MANUAL", "manual")
        
        # По умолчанию
        return ("UNKNOWN", "manual")
    
    # Оставляем старый метод для совместимости
    def _determine_close_reason_short(self, closed_item: Dict, cached: Optional[Dict]) -> str:
        """
        Устаревший метод. Используйте _determine_close_reason_enhanced.
        """
        reason, _ = self._determine_close_reason_enhanced(closed_item, cached, "auto")
        return reason
    
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
                "trade_id": trade["id"],
                "symbol": trade["symbol"],
                "side": trade["side"],
                "entry_price": float(trade["entry_price"]),
                "quantity": float(trade["quantity"]),
                "open_balance": trade.get("open_balance"),
                "source_entry": trade.get("source_entry"),  # НОВОЕ ПОЛЕ
                "timestamp": trade["entry_time"]
            }
        
        return None