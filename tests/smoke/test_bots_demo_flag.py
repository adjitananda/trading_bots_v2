"""
Проверка, что боты принимают флаг demo_mode.
"""

import pytest
from bots.crypto_bot import CryptoBot  # предполагаемое имя класса
from bots.tinkoff_bot import TinkoffBot
from bots.moex_bot import MoexBot


def test_crypto_bot_demo_flag():
    """CryptoBot должен принимать demo_mode"""
    bot = CryptoBot(demo_mode=True)
    assert bot.demo_mode is True


def test_tinkoff_bot_demo_flag():
    """TinkoffBot должен принимать demo_mode"""
    bot = TinkoffBot(demo_mode=True)
    assert bot.demo_mode is True


def test_moex_bot_demo_flag():
    """MoexBot должен принимать demo_mode"""
    bot = MoexBot(demo_mode=True)
    assert bot.demo_mode is True
