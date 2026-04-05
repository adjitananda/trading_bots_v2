"""
Smoke-тесты для базы данных
"""

import pytest


class TestDatabaseSmoke:
    """Быстрая проверка работоспособности БД"""
    
    def test_database_import(self):
        """Проверка импорта Database"""
        from trading_lib.utils.database import Database
        assert Database is not None
    
    def test_database_connection(self, db):
        """Проверка подключения к БД"""
        result = db.query("SELECT 1 as test")
        assert result is not None
        assert len(result) > 0
        assert result[0].get('test') == 1
    
    def test_required_tables_exist(self, db):
        """Проверка наличия всех обязательных таблиц"""
        # Получаем список таблиц
        tables_result = db.query("SHOW TABLES")
        existing_tables = [list(row.values())[0] for row in tables_result]
        
        required_tables = [
            'bots',
            'bot_symbols', 
            'trades',
            'orders',
            'alerts',
            'exchanges'
        ]
        
        missing_tables = [t for t in required_tables if t not in existing_tables]
        assert len(missing_tables) == 0, f"Missing tables: {missing_tables}"
    
    def test_bots_table_structure(self, db):
        """Проверка структуры таблицы bots"""
        columns = db.query("DESCRIBE bots")
        column_names = [col['Field'] for col in columns]
        
        required_columns = ['id', 'name', 'exchange_id', 'status', 'is_active']
        for col in required_columns:
            assert col in column_names, f"Column '{col}' missing in bots table"
    
    def test_bot_symbols_table_structure(self, db):
        """Проверка структуры таблицы bot_symbols"""
        columns = db.query("DESCRIBE bot_symbols")
        column_names = [col['Field'] for col in columns]
        
        required_columns = ['id', 'bot_id', 'symbol', 'strategy_params', 'is_active', 'reload_flag']
        for col in required_columns:
            assert col in column_names, f"Column '{col}' missing in bot_symbols table"
    
    def test_trades_table_structure(self, db):
        """Проверка структуры таблицы trades"""
        columns = db.query("DESCRIBE trades")
        column_names = [col['Field'] for col in columns]
        
        required_columns = ['id', 'bot_id', 'symbol', 'side', 'entry_time', 'entry_price', 'quantity', 'status']
        for col in required_columns:
            assert col in column_names, f"Column '{col}' missing in trades table"
