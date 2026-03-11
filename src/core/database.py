import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime, date
import json
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
import threading
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class DatabaseError(Exception):
    """Специфичное исключение для ошибок БД"""
    pass


class Database:
    """
    Класс для работы с базой данных.
    Реализует паттерн Singleton для единого подключения.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Инициализация подключения"""
        self.config = {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT", 3306)),
            "user": os.getenv("MYSQL_USER", "trader"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": os.getenv("MYSQL_DATABASE", "trading_bots_v2"),
            "charset": "utf8mb4",
            "use_unicode": True,
            "autocommit": False,
            "pool_name": "trading_pool",
            "pool_size": 5,
            "buffered": True
        }
        
        # Кэши для часто используемых данных
        self._cache = {}
        self._cache_timeout = {}
        
        # Проверяем подключение при инициализации
        self._test_connection()
    
    def get_orders_by_exchange_id(self, exchange_order_id: str) -> List[Dict]:
        """
        Получить ордера по ID на бирже.
        
        Args:
            exchange_order_id: ID ордера на бирже
            
        Returns:
            Список ордеров (обычно 0 или 1)
        """
        query = "SELECT * FROM orders WHERE exchange_order_id = %s ORDER BY id DESC"
        return self.execute_query(query, (exchange_order_id,))


    def _test_connection(self):
        """Тест подключения к БД"""
        try:
            # Используем execute_query вместо прямого курсора
            result = self.execute_query("SELECT 1 as test", fetch_one=True)
            print("✅ Database: успешное подключение")
        except Exception as e:
            print(f"❌ Database: ошибка подключения: {e}")
            raise DatabaseError(f"Не удалось подключиться к БД: {e}")
    
    @contextmanager
    def get_connection(self):
        """
        Контекстный менеджер для получения подключения.
        Автоматически закрывает соединение.
        """
        conn = None
        try:
            conn = mysql.connector.connect(**self.config)
            yield conn
        except Error as e:
            raise DatabaseError(f"Ошибка подключения: {e}")
        finally:
            if conn and conn.is_connected():
                # Перед закрытием убеждаемся, что все результаты прочитаны
                try:
                    if conn.unread_result:
                        cursor = conn.cursor()
                        cursor.fetchall()
                        cursor.close()
                except:
                    pass
                conn.close()
    
    @contextmanager
    def transaction(self):
        """
        Контекстный менеджер для транзакций.
        Автоматически делает commit при успехе или rollback при ошибке.
        """
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise DatabaseError(f"Ошибка транзакции: {e}")
    
    # ==================== БАЗОВЫЕ МЕТОДЫ ====================
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """
        Выполнение SQL запроса с возвратом результатов.
        
        Args:
            query: SQL запрос
            params: параметры запроса
            fetch_one: вернуть только одну запись
            
        Returns:
            Список словарей или один словарь
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True, buffered=True)
            cursor.execute(query, params or ())
            
            if fetch_one:
                result = cursor.fetchone()
                # Важно: потребляем оставшиеся результаты
                if cursor.with_rows:
                    cursor.fetchall()
                return result
            else:
                results = cursor.fetchall()
                return results
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """
        Выполнение INSERT запроса.
        
        Returns:
            ID вставленной записи
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(buffered=True)
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        Выполнение UPDATE/DELETE запроса.
        
        Returns:
            Количество затронутых строк
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(buffered=True)
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount
    
    # ==================== РАБОТА С БИРЖАМИ ====================
    
    def get_exchange_id(self, exchange_name: str) -> Optional[int]:
        """Получить ID биржи по имени"""
        cache_key = f"exchange_{exchange_name}"
        
        # Проверяем кэш
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        query = "SELECT id FROM exchanges WHERE name = %s AND is_active = TRUE"
        result = self.execute_query(query, (exchange_name,), fetch_one=True)
        
        if result:
            self._cache[cache_key] = result["id"]
            return result["id"]
        
        return None
    
    def get_all_exchanges(self) -> List[Dict]:
        """Получить список всех активных бирж"""
        query = "SELECT * FROM exchanges WHERE is_active = TRUE ORDER BY name"
        return self.execute_query(query)

    def get_exchange(self, exchange_id: int) -> Optional[Dict]:
        """
        Получить информацию о бирже по ID.
        
        Args:
            exchange_id: ID биржи
            
        Returns:
            Словарь с данными биржи или None
        """
        query = "SELECT * FROM exchanges WHERE id = %s"
        return self.execute_query(query, (exchange_id,), fetch_one=True)

    
    # ==================== РАБОТА С БОТАМИ ====================
    
    def create_bot(self, bot_data: Dict) -> int:
        """
        Создать новую версию бота.
        
        Args:
            bot_data: {
                "name": "ETHUSDT",
                "exchange_id": 1,
                "strategy_type": "ma_crossover",
                "strategy_params": {...},
                "risk_params": {...},
                "version": "1.0.0",
                "parent_bot_id": None
            }
        """
        query = """
            INSERT INTO bots (
                name, exchange_id, strategy_type, strategy_params,
                risk_params, version, parent_bot_id, created_at, started_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        
        params = (
            bot_data["name"],
            bot_data["exchange_id"],
            bot_data["strategy_type"],
            json.dumps(bot_data.get("strategy_params", {})),
            json.dumps(bot_data.get("risk_params", {})),
            bot_data.get("version", "1.0.0"),
            bot_data.get("parent_bot_id")
        )
        
        return self.execute_insert(query, params)
    
    def get_bot(self, bot_id: int) -> Optional[Dict]:
        """Получить информацию о боте по ID"""
        query = """
            SELECT b.*, e.name as exchange_name 
            FROM bots b
            JOIN exchanges e ON b.exchange_id = e.id
            WHERE b.id = %s
        """
        return self.execute_query(query, (bot_id,), fetch_one=True)
    
    def get_bot_by_name(self, bot_name: str, active_only: bool = True) -> Optional[Dict]:
        """Получить активного бота по имени"""
        query = """
            SELECT b.*, e.name as exchange_name 
            FROM bots b
            JOIN exchanges e ON b.exchange_id = e.id
            WHERE b.name = %s
        """
        if active_only:
            # ИСПРАВЛЕНО: используем одинарные кавычки внутри строки
            query += " AND b.is_active = TRUE AND b.status = 'active'"
        
        query += " ORDER BY b.created_at DESC LIMIT 1"
        
        return self.execute_query(query, (bot_name,), fetch_one=True)
    
    def get_all_active_bots(self) -> List[Dict]:
        """Получить всех активных ботов"""
        query = """
            SELECT b.*, e.name as exchange_name 
            FROM bots b
            JOIN exchanges e ON b.exchange_id = e.id
            WHERE b.is_active = TRUE AND b.status = 'active'
            ORDER BY b.name
        """
        return self.execute_query(query)
    
    def update_bot_status(self, bot_id: int, status: str, reason: str = None) -> bool:
        """Обновить статус бота"""
        query = """
            UPDATE bots 
            SET status = %s, status_reason = %s, status_changed_at = NOW()
            WHERE id = %s
        """
        rows = self.execute_update(query, (status, reason, bot_id))
        return rows > 0
    
    def deactivate_bot(self, bot_id: int) -> bool:
        """Деактивировать бота (при создании новой версии)"""
        query = "UPDATE bots SET is_active = FALSE, stopped_at = NOW() WHERE id = %s"
        rows = self.execute_update(query, (bot_id,))
        return rows > 0
    
    # ==================== РАБОТА СО СДЕЛКАМИ ====================
    
    def create_trade(self, trade_data: Dict) -> int:
        """
        Создать новую сделку (при открытии позиции).
        
        Args:
            trade_data: {
                "bot_id": 1,
                "exchange_id": 1,
                "symbol": "ETHUSDT",
                "side": "BUY",
                "entry_time": datetime,
                "entry_price": 1500.5,
                "quantity": 0.1,
                "entry_order_id": "abc123",
                "source_entry": "auto" или "manual"  # НОВОЕ ПОЛЕ
            }
        """
        query = """
            INSERT INTO trades (
                bot_id, exchange_id, symbol, side,
                entry_time, entry_price, quantity,
                entry_order_id, status, source_entry
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s)
        """
        
        params = (
            trade_data["bot_id"],
            trade_data["exchange_id"],
            trade_data["symbol"],
            trade_data["side"],
            trade_data["entry_time"],
            trade_data["entry_price"],
            trade_data["quantity"],
            trade_data.get("entry_order_id"),
            trade_data.get("source_entry", "auto")  # По умолчанию auto
        )
        
        return self.execute_insert(query, params)
    
    def close_trade(self, trade_id: int, close_data: Dict) -> bool:
        """
        Закрыть сделку.
        
        Args:
            trade_id: ID сделки
            close_data: {
                "exit_time": datetime,
                "exit_price": 1600.0,
                "pnl": 100.0,
                "pnl_percent": 6.67,
                "exit_reason": "TP",
                "exit_order_id": "def456",
                "source_exit": "auto" или "manual"  # НОВОЕ ПОЛЕ
            }
        """
        # Сначала получаем сделку для расчета pnl_percent если не передан
        if "pnl_percent" not in close_data:
            trade = self.get_trade(trade_id)
            if trade:
                entry_price = float(trade["entry_price"])
                exit_price = float(close_data["exit_price"])
                
                if trade["side"] == "BUY":
                    pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl_percent = ((entry_price - exit_price) / entry_price) * 100
                
                close_data["pnl_percent"] = pnl_percent
        
        # Динамически строим запрос с учетом новых полей
        set_parts = [
            "exit_time = %s",
            "exit_price = %s",
            "pnl = %s",
            "pnl_percent = %s",
            "exit_reason = %s",
            "exit_order_id = %s",
            "status = 'closed'",
            "updated_at = NOW()"
        ]
        params = [
            close_data["exit_time"],
            close_data["exit_price"],
            close_data.get("pnl"),
            close_data.get("pnl_percent"),
            close_data.get("exit_reason"),
            close_data.get("exit_order_id")
        ]
        
        # Добавляем source_exit если передан
        if "source_exit" in close_data:
            set_parts.append("source_exit = %s")
            params.append(close_data["source_exit"])
        
        params.append(trade_id)
        
        query = f"UPDATE trades SET {', '.join(set_parts)} WHERE id = %s AND status = 'open'"
        
        rows = self.execute_update(query, tuple(params))
        return rows > 0
    
    def get_trade(self, trade_id: int) -> Optional[Dict]:
        """Получить сделку по ID"""
        query = """
            SELECT t.*, b.name as bot_name, e.name as exchange_name
            FROM trades t
            JOIN bots b ON t.bot_id = b.id
            JOIN exchanges e ON t.exchange_id = e.id
            WHERE t.id = %s
        """
        return self.execute_query(query, (trade_id,), fetch_one=True)
    
    def get_open_trades(self, bot_id: int = None) -> List[Dict]:
        """Получить все открытые сделки (опционально для конкретного бота)"""
        query = """
            SELECT t.*, b.name as bot_name, e.name as exchange_name
            FROM trades t
            JOIN bots b ON t.bot_id = b.id
            JOIN exchanges e ON t.exchange_id = e.id
            WHERE t.status = 'open'
        """
        params = []
        
        if bot_id:
            query += " AND t.bot_id = %s"
            params.append(bot_id)
        
        query += " ORDER BY t.entry_time DESC"
        
        return self.execute_query(query, tuple(params) if params else None)
    
    def get_trades_by_order_id(self, order_id: str) -> List[Dict]:
        """Получить сделки по ID ордера на бирже"""
        query = """
            SELECT t.*, b.name as bot_name
            FROM trades t
            JOIN bots b ON t.bot_id = b.id
            WHERE t.entry_order_id = %s OR t.exit_order_id = %s
        """
        return self.execute_query(query, (order_id, order_id))
    
    # ==================== РАБОТА С ОРДЕРАМИ ====================
    
    def create_order(self, order_data: Dict) -> int:
        """
        Создать запись об ордере.
        
        Args:
            order_data: {
                "trade_id": None или ID сделки,
                "bot_id": 1,
                "exchange_id": 1,
                "exchange_order_id": "abc123",
                "symbol": "ETHUSDT",
                "side": "BUY",
                "order_type": "market",
                "quantity": 0.1,
                "price": 1500.5,
                "status": "new",
                "source": "auto" или "manual"  # НОВОЕ ПОЛЕ
            }
        """
        query = """
            INSERT INTO orders (
                trade_id, bot_id, exchange_id, exchange_order_id,
                symbol, side, order_type, quantity, price, status,
                source, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        params = (
            order_data.get("trade_id"),
            order_data["bot_id"],
            order_data["exchange_id"],
            order_data["exchange_order_id"],
            order_data["symbol"],
            order_data["side"],
            order_data["order_type"],
            order_data["quantity"],
            order_data.get("price"),
            order_data["status"],
            order_data.get("source", "auto")  # По умолчанию auto
        )
        
        return self.execute_insert(query, params)
    
    def update_order(self, exchange_order_id: str, update_data: Dict) -> bool:
        """
        Обновить статус ордера.
        
        Args:
            exchange_order_id: ID ордера на бирже
            update_data: {
                "status": "filled",
                "filled_quantity": 0.1,
                "average_fill_price": 1500.5,
                "finished_at": datetime,
                "cancel_reason": "...",
                "failure_reason": "..."
            }
        """
        # Динамически строим запрос
        set_parts = []
        params = []
        
        for field in ["status", "filled_quantity", "average_fill_price", 
                      "finished_at", "cancel_reason", "failure_reason", "metadata"]:
            if field in update_data:
                if field in ["metadata"]:
                    set_parts.append(f"{field} = %s")
                    params.append(json.dumps(update_data[field]))
                else:
                    set_parts.append(f"{field} = %s")
                    params.append(update_data[field])
        
        if not set_parts:
            return False
        
        set_parts.append("updated_at = NOW()")
        query = f"UPDATE orders SET {', '.join(set_parts)} WHERE exchange_order_id = %s"
        params.append(exchange_order_id)
        
        rows = self.execute_update(query, tuple(params))
        return rows > 0
    
    def get_order(self, exchange_order_id: str) -> Optional[Dict]:
        """Получить ордер по ID на бирже"""
        query = "SELECT * FROM orders WHERE exchange_order_id = %s"
        return self.execute_query(query, (exchange_order_id,), fetch_one=True)
    
    def get_orders_by_bot(self, bot_id: int, limit: int = 100) -> List[Dict]:
        """Получить последние ордера бота"""
        query = """
            SELECT * FROM orders 
            WHERE bot_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """
        return self.execute_query(query, (bot_id, limit))
    
    # ==================== СНИМКИ СОСТОЯНИЯ ====================
    
    def create_snapshot(self, snapshot_data: Dict) -> int:
        """
        Создать снимок состояния бота.
        
        Args:
            snapshot_data: {
                "bot_id": 1,
                "exchange_id": 1,
                "balance": 1000.5,
                "total_pnl": 150.2,
                "daily_pnl": 25.3,
                "open_positions_count": 2,
                "open_positions_json": [...],
                "drawdown_current": 2.5,
                "drawdown_max": 5.0,
                "consecutive_losses": 0
            }
        """
        query = """
            INSERT INTO snapshots (
                bot_id, exchange_id, timestamp, balance, total_pnl,
                daily_pnl, open_positions_count, open_positions_json,
                drawdown_current, drawdown_max, consecutive_losses
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            snapshot_data["bot_id"],
            snapshot_data["exchange_id"],
            snapshot_data["balance"],
            snapshot_data["total_pnl"],
            snapshot_data.get("daily_pnl"),
            snapshot_data["open_positions_count"],
            json.dumps(snapshot_data.get("open_positions_json", [])),
            snapshot_data.get("drawdown_current", 0),
            snapshot_data.get("drawdown_max", 0),
            snapshot_data.get("consecutive_losses", 0)
        )
        
        return self.execute_insert(query, params)
    
    def get_last_snapshot(self, bot_id: int) -> Optional[Dict]:
        """Получить последний снимок бота"""
        query = """
            SELECT * FROM snapshots 
            WHERE bot_id = %s 
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        return self.execute_query(query, (bot_id,), fetch_one=True)
    
    # ==================== АЛЕРТЫ ====================
    
    def create_alert(self, alert_data: Dict) -> int:
        """
        Создать алерт.
        
        Args:
            alert_data: {
                "bot_id": 1,
                "level": "WARNING",
                "type": "DRAWDOWN_EXCEEDED",
                "threshold_value": 5.0,
                "actual_value": 7.2,
                "message": "Просадка превышена"
            }
        """
        query = """
            INSERT INTO alerts (
                bot_id, level, type, threshold_value,
                actual_value, message, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        
        params = (
            alert_data["bot_id"],
            alert_data["level"],
            alert_data["type"],
            alert_data.get("threshold_value"),
            alert_data.get("actual_value"),
            alert_data["message"]
        )
        
        return self.execute_insert(query, params)
    
    def get_unresolved_alerts(self, bot_id: int = None) -> List[Dict]:
        """Получить неподтвержденные алерты"""
        query = """
            SELECT a.*, b.name as bot_name
            FROM alerts a
            JOIN bots b ON a.bot_id = b.id
            WHERE a.acknowledged = FALSE
        """
        params = []
        
        if bot_id:
            query += " AND a.bot_id = %s"
            params.append(bot_id)
        
        query += " ORDER BY a.created_at DESC"
        
        return self.execute_query(query, tuple(params) if params else None)
    
    def acknowledge_alert(self, alert_id: int, action_taken: str = None) -> bool:
        """Подтвердить алерт"""
        query = """
            UPDATE alerts 
            SET acknowledged = TRUE, acknowledged_at = NOW(), action_taken = %s
            WHERE id = %s
        """
        rows = self.execute_update(query, (action_taken, alert_id))
        return rows > 0
    
    # ==================== ИСТОРИЯ ОСТАНОВОК ====================
    
    def create_stop_event(self, stop_data: Dict) -> int:
        """
        Создать событие остановки бота.
        
        Args:
            stop_data: {
                "bot_id": 1,
                "alert_id": None,
                "stop_type": "soft",
                "stop_reason": "max_drawdown",
                "triggered_by": "SYSTEM",
                "triggered_by_user_id": None,
                "positions_before_stop": [...],
                "auto_restart_scheduled": True,
                "auto_restart_at": datetime
            }
        """
        query = """
            INSERT INTO bot_stop_events (
                bot_id, alert_id, stop_type, stop_reason,
                triggered_by, triggered_by_user_id, positions_before_stop,
                auto_restart_scheduled, auto_restart_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        params = (
            stop_data["bot_id"],
            stop_data.get("alert_id"),
            stop_data["stop_type"],
            stop_data["stop_reason"],
            stop_data["triggered_by"],
            stop_data.get("triggered_by_user_id"),
            json.dumps(stop_data.get("positions_before_stop", [])),
            stop_data.get("auto_restart_scheduled", False),
            stop_data.get("auto_restart_at")
        )
        
        return self.execute_insert(query, params)
    
    def get_bot_stop_history(self, bot_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю остановок бота"""
        query = """
            SELECT * FROM bot_stop_events 
            WHERE bot_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """
        return self.execute_query(query, (bot_id, limit))
    
    # ==================== КОМАНДЫ ====================
    
    def log_command(self, user_id: str, username: str, command: str, 
                    args: Dict, success: bool, result: Any = None, 
                    error: str = None) -> int:
        """Записать выполненную команду"""
        query = """
            INSERT INTO command_logs (
                user_id, username, command, args, 
                success, result, error_message, executed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        params = (
            user_id,
            username,
            command,
            json.dumps(args) if args else None,
            success,
            json.dumps(result) if result else None,
            error
        )
        
        return self.execute_insert(query, params)
    
    # ==================== ОТЧЕТЫ ====================
    
    def get_bot_summary(self, bot_id: int, days: int = 30) -> Dict:
        """Получить сводку по боту за период"""
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as loss_trades,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(AVG(pnl), 0) as avg_pnl,
                COALESCE(MAX(pnl), 0) as max_profit,
                COALESCE(MIN(pnl), 0) as max_loss,
                COALESCE(SUM(ABS(pnl)), 0) as total_volume
            FROM trades 
            WHERE bot_id = %s 
                AND status = 'closed'
                AND exit_time >= NOW() - INTERVAL %s DAY
        """
        result = self.execute_query(query, (bot_id, days), fetch_one=True)
        
        if result:
            # Конвертируем все числовые значения в float
            for key in ["total_pnl", "avg_pnl", "max_profit", "max_loss", "total_volume"]:
                if key in result:
                    result[key] = self._to_float(result[key])
            
            # Добавляем процент прибыльных
            total = result.get("total_trades", 0) or 0
            profitable = result.get("profitable_trades", 0) or 0
            
            if total > 0:
                result["win_rate"] = (float(profitable) / float(total)) * 100
            else:
                result["win_rate"] = 0.0
        
        return result or {}
    
    def get_daily_pnl(self, bot_id: int = None, days: int = 30) -> List[Dict]:
        """Получить дневной PnL"""
        query = """
            SELECT 
                DATE(exit_time) as date,
                COUNT(*) as trades,
                SUM(pnl) as total_pnl
            FROM trades 
            WHERE status = 'closed'
        """
        params = []
        
        if bot_id:
            query += " AND bot_id = %s"
            params.append(bot_id)
        
        query += """
            AND exit_time >= NOW() - INTERVAL %s DAY
            GROUP BY DATE(exit_time)
            ORDER BY date
        """
        params.append(days)
        
        results = self.execute_query(query, tuple(params))
        
        # Конвертируем total_pnl в float для каждого результата
        for row in results:
            if "total_pnl" in row:
                row["total_pnl"] = self._to_float(row["total_pnl"])
        
        return results
    
    def get_open_positions_view(self) -> List[Dict]:
        """Получить открытые позиции через view"""
        try:
            return self.execute_query("SELECT * FROM v_open_positions")
        except:
            return []
    
    def get_today_summary(self) -> Dict:
        """Получить итоги за сегодня"""
        try:
            return self.execute_query("SELECT * FROM v_today_summary", fetch_one=True) or {}
        except:
            return {}
    
    # ==================== НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С SOURCE ====================
    
    def get_auto_trades(self, bot_id: int = None, days: int = 30) -> List[Dict]:
        """
        Получить автоматические сделки (source_entry = 'auto')
        """
        query = """
            SELECT t.*, b.name as bot_name
            FROM trades t
            JOIN bots b ON t.bot_id = b.id
            WHERE t.source_entry = 'auto'
        """
        params = []
        
        if bot_id:
            query += " AND t.bot_id = %s"
            params.append(bot_id)
        
        if days:
            query += " AND t.entry_time >= NOW() - INTERVAL %s DAY"
            params.append(days)
        
        query += " ORDER BY t.entry_time DESC"
        
        return self.execute_query(query, tuple(params) if params else None)
    
    def get_manual_trades(self, bot_id: int = None, days: int = 30) -> List[Dict]:
        """
        Получить ручные сделки (source_entry = 'manual')
        """
        query = """
            SELECT t.*, b.name as bot_name
            FROM trades t
            JOIN bots b ON t.bot_id = b.id
            WHERE t.source_entry = 'manual'
        """
        params = []
        
        if bot_id:
            query += " AND t.bot_id = %s"
            params.append(bot_id)
        
        if days:
            query += " AND t.entry_time >= NOW() - INTERVAL %s DAY"
            params.append(days)
        
        query += " ORDER BY t.entry_time DESC"
        
        return self.execute_query(query, tuple(params) if params else None)
    
    def get_strategy_performance(self, bot_id: int, days: int = 30) -> Dict:
        """
        Получить эффективность стратегии (только авто-сделки)
        """
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as loss_trades,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(AVG(pnl), 0) as avg_pnl
            FROM trades 
            WHERE bot_id = %s 
                AND status = 'closed'
                AND source_entry = 'auto'
                AND exit_time >= NOW() - INTERVAL %s DAY
        """
        result = self.execute_query(query, (bot_id, days), fetch_one=True)
        
        if result:
            total = result.get("total_trades", 0) or 0
            profitable = result.get("profitable_trades", 0) or 0
            
            if total > 0:
                result["win_rate"] = (float(profitable) / float(total)) * 100
            else:
                result["win_rate"] = 0.0
        
        return result or {}
    
    # ==================== КЭШИРОВАНИЕ ====================
    
    def cache_get(self, key: str, max_age_seconds: int = 60):
        """Получить значение из кэша"""
        if key in self._cache:
            timestamp = self._cache_timeout.get(key, 0)
            age = (datetime.now() - timestamp).total_seconds()
            if age < max_age_seconds:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_timeout[key]
        return None
    
    def cache_set(self, key: str, value):
        """Сохранить значение в кэш"""
        self._cache[key] = value
        self._cache_timeout[key] = datetime.now()
    
    def _to_float(self, value):
        """Безопасное преобразование в float"""
        if value is None:
            return 0.0
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def cache_clear(self):
        """Очистить кэш"""
        self._cache.clear()
        self._cache_timeout.clear()


# Глобальный экземпляр для удобства
db = Database()