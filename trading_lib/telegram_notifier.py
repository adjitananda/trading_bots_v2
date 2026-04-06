"""
Telegram notifier for demo trades.
Отправляет уведомления о сделках в Telegram-канал.
"""

import os
import logging
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Отправка уведомлений о сделках в Telegram.
    
    Если токен или chat_id не заданы — логирует ошибку и молча пропускает.
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Инициализация нотификатора.

        Args:
            token: Telegram Bot API token (если None — берёт из .env)
            chat_id: ID чата/канала для отправки (если None — берёт из .env)
        """
        # Если token явно передан (даже пустая строка) — используем его
        # Если token = None — только тогда берём из .env
        if token is None:
            self.token = os.getenv('TELEGRAM_TOKEN')
        else:
            self.token = token
        
        if chat_id is None:
            self.chat_id = os.getenv('TELEGRAM_CHANNEL_ID')
        else:
            self.chat_id = chat_id
        
        # Проверка: токен и chat_id должны быть не None и не пустые строки
        if not self.token or not self.chat_id or self.token == '' or self.chat_id == '':
            logger.error("TelegramNotifier: TELEGRAM_TOKEN или TELEGRAM_CHANNEL_ID не заданы")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("TelegramNotifier инициализирован")

    def send_trade_notification(self, trade_result: Dict[str, Any]) -> bool:
        """
        Отправляет уведомление о сделке.

        Args:
            trade_result: Словарь с результатом сделки (из place_order)
                - broker, symbol, side, status, filled_qty, fill_price, commission

        Returns:
            True если отправлено успешно или нотификатор отключен, False при ошибке
        """
        if not self.enabled:
            logger.debug("TelegramNotifier отключен, уведомление не отправлено")
            return True

        # Формируем сообщение
        status_emoji = "✅" if trade_result.get('status') == 'filled' else "❌"
        side_emoji = "🟢" if trade_result.get('side') == 'buy' else "🔴"
        
        message = (
            f"{status_emoji} *Демо-сделка*\n"
            f"{side_emoji} {trade_result.get('side', '?').upper()} {trade_result.get('symbol', '?')}\n"
            f"Брокер: {trade_result.get('broker', '?')}\n"
            f"Статус: {trade_result.get('status', '?')}\n"
            f"Кол-во: {trade_result.get('filled_qty', 0):.8f}\n"
            f"Цена: {trade_result.get('fill_price', 0):.2f}\n"
            f"Комиссия: {trade_result.get('commission', 0):.8f}\n"
            f"Задержка: {trade_result.get('latency_ms', 0)} мс"
        )

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }

        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("Telegram уведомление отправлено: %s %s", 
                        trade_result.get('symbol'), trade_result.get('status'))
            return True
        except requests.RequestException as e:
            logger.error("Ошибка отправки Telegram уведомления: %s", e)
            return False

    def send_text(self, text: str) -> bool:
        """
        Отправляет произвольный текст в Telegram.

        Args:
            text: Текст сообщения

        Returns:
            True если отправлено успешно
        """
        if not self.enabled:
            logger.debug("TelegramNotifier отключен, текст не отправлен")
            return True

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }

        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("Telegram текст отправлен")
            return True
        except requests.RequestException as e:
            logger.error("Ошибка отправки текста в Telegram: %s", e)
            return False
