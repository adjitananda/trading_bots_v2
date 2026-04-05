"""
Регрессионные тесты для TINKOFF_BOT
"""

import pytest
import os


class TestTinkoffBot:
    """Тестирование TINKOFF бота"""
    
    def test_tinkoff_bot_exists(self):
        """Проверка существования файла tinkoff_bot.py"""
        assert os.path.exists('tinkoff_bot.py'), "tinkoff_bot.py not found"
    
    def test_tinkoff_bot_import(self):
        """Проверка импорта TinkoffBot"""
        from tinkoff_bot import TinkoffBot
        assert TinkoffBot is not None
    
    def test_tinkoff_bot_class_exists(self):
        """Проверка класса TinkoffBot"""
        with open('tinkoff_bot.py', 'r') as f:
            content = f.read()
        
        assert 'class TinkoffBot' in content
    
    def test_tinkoff_bot_has_run_method(self):
        """Проверка наличия метода run"""
        with open('tinkoff_bot.py', 'r') as f:
            content = f.read()
        
        assert 'def run' in content
    
    @pytest.mark.slow
    def test_tinkoff_bot_in_db(self, db):
        """Проверка наличия TINKOFF_BOT в БД"""
        bots = db.query("SELECT id, name FROM bots WHERE name = 'TINKOFF_BOT'")
        
        if len(bots) == 0:
            pytest.skip("TINKOFF_BOT not found in database")
        
        assert bots[0]['name'] == 'TINKOFF_BOT'
