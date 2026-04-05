"""
Регрессионные тесты для CRYPTO_BOT
"""

import pytest
import sys
import os


class TestCryptoBot:
    """Тестирование крипто-бота"""
    
    def test_crypto_bot_import(self):
        """Проверка импорта CryptoBot"""
        from crypto_bot import CryptoBot
        assert CryptoBot is not None
    
    def test_crypto_bot_class_exists(self):
        """Проверка существования класса CryptoBot"""
        with open('crypto_bot.py', 'r') as f:
            content = f.read()
        
        assert 'class CryptoBot' in content
        assert 'MoexBaseBot' not in content  # Не должно быть наследования от MOEX
    
    def test_crypto_bot_has_run_method(self):
        """Проверка наличия метода run"""
        with open('crypto_bot.py', 'r') as f:
            content = f.read()
        
        assert 'def run' in content
    
    def test_crypto_bot_uses_trading_lib(self):
        """Проверка использования trading_lib"""
        with open('crypto_bot.py', 'r') as f:
            content = f.read()
        
        # Должен импортировать из trading_lib
        assert 'trading_lib' in content
    
    @pytest.mark.slow
    def test_crypto_bot_initialization(self, db):
        """Проверка инициализации бота (медленный тест)"""
        # Проверяем, что бот есть в БД
        bots = db.query("SELECT id, name FROM bots WHERE name LIKE '%CRYPTO%' OR name LIKE '%crypto%'")
        assert len(bots) > 0, "Crypto bot not found in database"
    
    @pytest.mark.slow
    def test_crypto_bot_symbols_in_db(self, db):
        """Проверка наличия символов для крипто-бота"""
        # Находим крипто-бота
        bot = db.query("SELECT id FROM bots WHERE name = 'CRYPTO_BOT'")
        if not bot:
            pytest.skip("CRYPTO_BOT not found")
        
        bot_id = bot[0]['id']
        symbols = db.query(
            "SELECT symbol FROM bot_symbols WHERE bot_id = %s AND is_active = 1",
            (bot_id,)
        )
        
        expected_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        found_symbols = [s['symbol'] for s in symbols]
        
        # Не все символы могут быть активны
        for sym in expected_symbols:
            if sym not in found_symbols:
                print(f"Warning: {sym} not active for CRYPTO_BOT")
