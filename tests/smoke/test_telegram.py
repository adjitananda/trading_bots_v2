"""
Smoke-тесты для TelegramNotifier.
"""

import pytest
from trading_lib.telegram_notifier import TelegramNotifier


def test_notify_without_token_logs_error():
    """Без токена и chat_id (пустые строки) нотификатор отключен"""
    notifier = TelegramNotifier(token="", chat_id="")
    assert notifier.enabled is False
    result = notifier.send_text("test")
    assert result is True  # молча пропускает


def test_notify_with_mock_token():
    """С фейковым токеном отправка падает, но не выбрасывает исключение наружу"""
    notifier = TelegramNotifier(token="FAKE_TOKEN", chat_id="12345")
    result = notifier.send_text("test message")
    assert result is False


def test_trade_notification_format():
    """Проверка формирования сообщения (без реальной отправки)"""
    notifier = TelegramNotifier(token="FAKE", chat_id="123")
    
    trade_result = {
        'broker': 'tinkoff',
        'symbol': 'BTCUSDT',
        'side': 'buy',
        'status': 'filled',
        'filled_qty': 0.001,
        'fill_price': 52340.50,
        'commission': 0.05234,
        'latency_ms': 237
    }
    
    result = notifier.send_trade_notification(trade_result)
    assert result is False
