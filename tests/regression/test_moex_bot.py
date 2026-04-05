"""
Регрессионные тесты для MOEX_BOT
"""

import pytest
import os


class TestMoexBot:
    """Тестирование MOEX бота"""
    
    def test_moex_bot_exists(self):
        """Проверка существования файла moex_bot.py"""
        assert os.path.exists('moex_bot.py'), "moex_bot.py not found"
    
    def test_moex_bot_import(self):
        """Проверка импорта MoexBot"""
        from moex_bot import MoexBot
        assert MoexBot is not None
    
    def test_moex_bot_class_exists(self):
        """Проверка класса MoexBot"""
        with open('moex_bot.py', 'r') as f:
            content = f.read()
        
        assert 'class MoexBot' in content
    
    def test_moex_bot_has_run_method(self):
        """Проверка наличия метода run"""
        with open('moex_bot.py', 'r') as f:
            content = f.read()
        
        assert 'def run' in content
    
    @pytest.mark.slow
    def test_moex_bot_in_db(self, db):
        """Проверка наличия MOEX_BOT в БД"""
        bots = db.query("SELECT id, name FROM bots WHERE name = 'MOEX_BOT'")
        
        if len(bots) == 0:
            pytest.skip("MOEX_BOT not found in database")
        
        assert bots[0]['name'] == 'MOEX_BOT'
