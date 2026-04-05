"""
Smoke-тесты для Telegram команд
"""

import pytest
import os


class TestTelegramCommands:
    """Проверка регистрации Telegram команд"""
    
    @pytest.fixture
    def commander_content(self):
        """Читаем содержимое commander.py"""
        commander_path = 'src/telegram/commander.py'
        if not os.path.exists(commander_path):
            commander_path = 'trading_lib/telegram/commander.py'
        
        if os.path.exists(commander_path):
            with open(commander_path, 'r') as f:
                return f.read()
        return ""
    
    def test_commander_exists(self):
        """Проверка существования commander.py"""
        commander_path = 'src/telegram/commander.py'
        alt_path = 'trading_lib/telegram/commander.py'
        assert os.path.exists(commander_path) or os.path.exists(alt_path), \
            "commander.py not found"
    
    def test_crypto_commands_registered(self, commander_content):
        """Проверка команд крипто-бота"""
        crypto_commands = [
            'crypto_metrics',
            'crypto_status', 
            'crypto_optimize'
        ]
        
        for cmd in crypto_commands:
            # Проверяем наличие определения функции или декоратора
            has_func = f"def {cmd}" in commander_content
            has_decorator = f"commands=['{cmd}']" in commander_content
            assert has_func or has_decorator, f"Command '{cmd}' not found"
    
    def test_tinkoff_commands_registered(self, commander_content):
        """Проверка команд TINKOFF бота"""
        tinkoff_commands = [
            'tinkoff_metrics',
            'tinkoff_status',
            'tinkoff_optimize'
        ]
        
        for cmd in tinkoff_commands:
            has_func = f"def {cmd}" in commander_content
            has_decorator = f"commands=['{cmd}']" in commander_content
            assert has_func or has_decorator, f"Command '{cmd}' not found"
    
    def test_moex_commands_registered(self, commander_content):
        """Проверка команд MOEX бота"""
        moex_commands = [
            'moex_metrics',
            'moex_status',
            'moex_optimize'
        ]
        
        for cmd in moex_commands:
            has_func = f"def {cmd}" in commander_content
            has_decorator = f"commands=['{cmd}']" in commander_content
            assert has_func or has_decorator, f"Command '{cmd}' not found"
    
    def test_common_commands_registered(self, commander_content):
        """Проверка общих команд"""
        common_commands = [
            'params',
            'symbols',
            'optimize_status',
            'apply_params',
            'reject_params',
            'risk_status',
            'reset_risk',
            'regime'
        ]
        
        for cmd in common_commands:
            has_func = f"def {cmd}" in commander_content
            has_decorator = f"commands=['{cmd}']" in commander_content
            assert has_func or has_decorator, f"Command '{cmd}' not found"
    
    def test_compare_strategies_command(self, commander_content):
        """Проверка команды compare_strategies"""
        has_func = "def compare_strategies" in commander_content
        has_decorator = "commands=['compare_strategies']" in commander_content
        assert has_func or has_decorator, "Command 'compare_strategies' not found"
