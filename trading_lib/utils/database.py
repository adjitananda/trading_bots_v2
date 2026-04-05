import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class Database:
    """Простой и надёжный класс для работы с БД"""
    
    def __init__(self):
        self.config = {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT", 3306)),
            "user": os.getenv("MYSQL_USER", "trader"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": os.getenv("MYSQL_DATABASE", "trading_bots_v2"),
            "charset": "utf8mb4",
            "use_unicode": True,
            "autocommit": True,
        }
        self._test_connection()
    
    def _test_connection(self):
        try:
            conn = self._get_connection()
            conn.close()
            pass
        except Exception as e:
            print(f"❌ Database: ошибка подключения: {e}")
    
    def _get_connection(self):
        """Получить новое соединение"""
        return mysql.connector.connect(**self.config)
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """Выполнить SELECT запрос"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch_one:
                result = cursor.fetchone()
            else:
                result = cursor.fetchall()
            
            return result
        except Error as e:
            print(f"❌ Ошибка запроса: {e}\nQuery: {query}")
            return None if fetch_one else []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Выполнить INSERT/UPDATE/DELETE запрос"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount
        except Error as e:
            print(f"❌ Ошибка выполнения: {e}\nQuery: {query}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """Выполнить INSERT и вернуть lastrowid"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"❌ Ошибка INSERT: {e}\nQuery: {query}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # ==================== ОСНОВНЫЕ МЕТОДЫ ====================
    
    def get_exchange_id(self, exchange_name: str) -> Optional[int]:
        query = "SELECT id FROM exchanges WHERE name = %s AND is_active = 1"
        result = self.execute_query(query, (exchange_name,), fetch_one=True)
        return result['id'] if result else None
    
    def get_bot(self, bot_id: int) -> Optional[Dict]:
        query = "SELECT * FROM bots WHERE id = %s"
        return self.execute_query(query, (bot_id,), fetch_one=True)
    
    def get_bot_by_name(self, bot_name: str, active_only: bool = True) -> Optional[Dict]:
        query = "SELECT * FROM bots WHERE name = %s"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY id DESC LIMIT 1"
        return self.execute_query(query, (bot_name,), fetch_one=True)
    
    def get_all_active_bots(self) -> List[Dict]:
        query = "SELECT * FROM bots WHERE is_active = 1 ORDER BY name"
        return self.execute_query(query) or []
    
    def update_bot_status(self, bot_id: int, status: str, reason: str = None) -> bool:
        query = "UPDATE bots SET status = %s, status_reason = %s, status_changed_at = NOW() WHERE id = %s"
        rows = self.execute_update(query, (status, reason, bot_id))
        return rows > 0
    
    def get_open_trades(self, bot_id: int = None) -> List[Dict]:
        query = "SELECT * FROM trades WHERE status = 'open'"
        params = []
        if bot_id:
            query += " AND bot_id = %s"
            params.append(bot_id)
        query += " ORDER BY entry_time DESC"
        return self.execute_query(query, tuple(params) if params else None) or []
    
    def get_trade(self, trade_id: int) -> Optional[Dict]:
        query = "SELECT * FROM trades WHERE id = %s"
        return self.execute_query(query, (trade_id,), fetch_one=True)
    
    def log_command(self, user_id: str, username: str, command: str, args: Dict, success: bool, result: Any = None, error: str = None) -> int:
        query = """INSERT INTO command_logs (user_id, username, command, args, success, result, error_message, executed_at) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())"""
        params = (user_id, username, command, json.dumps(args) if args else None, success, json.dumps(result) if result else None, error)
        return self.execute_insert(query, params)
    
    def get_last_snapshot(self, bot_id: int) -> Optional[Dict]:
        query = "SELECT * FROM snapshots WHERE bot_id = %s ORDER BY timestamp DESC LIMIT 1"
        return self.execute_query(query, (bot_id,), fetch_one=True)
    
    def get_bot_summary(self, bot_id: int, days: int = 30) -> Dict:
        query = """SELECT COUNT(*) as total_trades, 
                          SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                          SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as loss_trades,
                          COALESCE(SUM(pnl), 0) as total_pnl,
                          COALESCE(AVG(pnl), 0) as avg_pnl
                   FROM trades WHERE bot_id = %s AND status = 'closed' AND exit_time >= NOW() - INTERVAL %s DAY"""
        result = self.execute_query(query, (bot_id, days), fetch_one=True)
        if result and result.get('total_trades', 0) > 0:
            result['win_rate'] = (result.get('profitable_trades', 0) / result['total_trades']) * 100
        else:
            result = result or {}
            result['win_rate'] = 0
        return result
    
    def get_daily_pnl(self, bot_id: int = None, days: int = 30) -> List[Dict]:
        query = "SELECT DATE(exit_time) as date, COUNT(*) as trades, SUM(pnl) as total_pnl FROM trades WHERE status = 'closed'"
        params = []
        if bot_id:
            query += " AND bot_id = %s"
            params.append(bot_id)
        query += " AND exit_time >= NOW() - INTERVAL %s DAY GROUP BY DATE(exit_time) ORDER BY date"
        params.append(days)
        return self.execute_query(query, tuple(params)) or []
    
    def execute_query_with_cache(self, query: str, params: tuple = None, cache_key: str = None, ttl: int = 60):
        return self.execute_query(query, params)


db = Database()
