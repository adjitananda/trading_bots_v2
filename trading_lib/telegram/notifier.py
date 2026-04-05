"""
Модуль для отправки уведомлений в Telegram.
Интегрируется с существующими ботами.
"""

import os
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


from trading_lib.utils.database import db
from trading_lib.utils.time_utils import now_local, format_datetime
from src.messages.telegram_messages import TelegramMessages

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Отправка уведомлений в Telegram.
    Используется торговыми ботами для оповещений.
    """
    
    def __init__(self):
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.events_channel = os.getenv('TELEGRAM_CHANNEL_ID')
        self.logs_channel = os.getenv('TELEGRAM_CHANNEL_ID_LOG')
        
        # Логируем загруженные значения
        logger.info("📨 Инициализация TelegramNotifier:")
        logger.info(f"  Token загружен: {bool(self.token)}")
        if self.token:
            logger.info(f"  Token (первые 10 символов): {self.token[:10]}...")
        logger.info(f"  Events channel: {self.events_channel}")
        logger.info(f"  Logs channel: {self.logs_channel}")
        
        if not self.token:
            logger.error("❌ TELEGRAM_TOKEN не настроен, уведомления не будут отправляться")
        if not self.events_channel:
            logger.error("❌ TELEGRAM_CHANNEL_ID не настроен, уведомления о событиях не будут отправляться")
        if not self.logs_channel:
            logger.error("❌ TELEGRAM_CHANNEL_ID_LOG не настроен, логи не будут отправляться")
    
    def _send(self, message: str, channel_id: str, parse_mode: str = 'HTML') -> bool:
        """Отправить сообщение в канал"""
        logger.info(f"📨 Попытка отправки сообщения в канал: {channel_id}")
        logger.debug(f"Сообщение: {message[:100]}...")
        
        if not self.token:
            logger.error("❌ Нет токена Telegram")
            return False
        
        if not channel_id:
            logger.error("❌ Нет channel_id")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": channel_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            logger.info(f"🔄 Отправка запроса к Telegram API")
            response = requests.post(url, data=payload, timeout=10)
            
            logger.info(f"📨 Ответ от Telegram API: статус {response.status_code}")
            if response.status_code != 200:
                logger.error(f"❌ Ошибка Telegram API: {response.text}")
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}", exc_info=True)
            return False
    
    def send_trade_notification(self, trade_data: Dict) -> bool:
        """
        Отправить уведомление о новой сделке.
        
        Args:
            trade_data: Данные сделки (из order_manager)
        """
        if not self.events_channel:
            logger.warning("⚠️ Нет events_channel, уведомление не отправлено")
            return False
        
        # Получаем дополнительную информацию
        bot = db.get_bot(trade_data['bot_id'])
        
        # Добавим отладку
        logger.info(f"🔍 ДЕБАГ: bot_id = {trade_data['bot_id']}")
        logger.info(f"🔍 ДЕБАГ: тип bot = {type(bot)}")
        logger.info(f"🔍 ДЕБАГ: bot = {bot}")
        
        if not bot:
            logger.error(f"❌ Бот с ID {trade_data['bot_id']} не найден")
            return False
        
        # Безопасно извлекаем данные
        try:
            # Если bot - это словарь
            if isinstance(bot, dict):
                strategy_name = bot.get('strategy_type', 'unknown')
                risk_params = bot.get('risk_params', {})
                if isinstance(risk_params, str):
                    import json
                    try:
                        risk_params = json.loads(risk_params)
                    except:
                        risk_params = {}
                max_positions = risk_params.get('max_positions', 5)
            else:
                # Если bot - это что-то другое
                logger.warning(f"⚠️ bot не является словарем: {type(bot)}")
                strategy_name = 'unknown'
                max_positions = 5
            
            # Получаем текущие позиции для отображения
            open_trades = db.get_open_trades(trade_data['bot_id'])
            total_positions = len(open_trades)
            
            # Формируем сообщение
            message = TelegramMessages.new_trade(
                bot_name=trade_data['bot_name'],
                symbol=trade_data['symbol'],
                side=trade_data['side'].upper(),
                price=trade_data['entry_price'],
                quantity=trade_data['quantity'],
                tp_price=trade_data.get('tp_price', 0),
                sl_price=trade_data.get('sl_price', 0),
                tp_percent=trade_data.get('tp_percent', 0),
                sl_percent=trade_data.get('sl_percent', 0),
                order_id=trade_data['order_id'],
                balance=trade_data.get('balance', 0),
                symbol_pnl=trade_data.get('symbol_pnl', 0),
                total_pnl=trade_data.get('total_pnl', 0),
                current_positions=total_positions,
                total_positions=total_positions,
                max_positions=max_positions,
                strategy_name=strategy_name,
                local_time=now_local()
            )
            
            logger.info(f"📨 Отправка уведомления о новой сделке: {trade_data['symbol']} {trade_data['side']}")
            return self._send(message, self.events_channel)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при формировании уведомления: {e}", exc_info=True)
            return False
    
    def send_close_notification(self, close_data: Dict) -> bool:
        """
        Отправить уведомление о закрытии сделки.
        
        Args:
            close_data: Данные о закрытии (из order_manager)
        """
        if not self.events_channel:
            logger.warning("⚠️ Нет events_channel, уведомление не отправлено")
            return False
        
        message = TelegramMessages.trade_closed(
            bot_name=close_data['bot_name'],
            symbol=close_data['symbol'],
            side=close_data['side'],
            entry_price=close_data['entry_price'],
            exit_price=close_data['exit_price'],
            quantity=close_data['quantity'],
            pnl=close_data['pnl'],
            pnl_percent=close_data['pnl_percent'],
            reason=close_data['reason'],
            balance=close_data.get('balance', 0),
            symbol_pnl=close_data.get('symbol_pnl', 0),
            total_pnl=close_data.get('total_pnl', 0),
            strategy_name=close_data['strategy_name'],
            entry_time=close_data['entry_time'],
            exit_time=now_local(),
            order_id=close_data['order_id']
        )
        
        logger.info(f"📨 Отправка уведомления о закрытии сделки: {close_data['symbol']} PnL: {close_data['pnl']:.2f}")
        return self._send(message, self.events_channel)
    
    def send_bot_startup(self, bot_name: str, config: Dict, strategy_name: str) -> bool:
        """
        Отправить уведомление о запуске бота.
        """
        if not self.events_channel:
            return False
        
        message = TelegramMessages.startup(
            bot_name=bot_name,
            bot_symbol=config.get('symbol', bot_name),
            config=config,
            strategy_name=strategy_name,
            local_time=now_local()
        )
        
        logger.info(f"📨 Отправка уведомления о запуске бота: {bot_name}")
        return self._send(message, self.events_channel)
    
    def send_bot_stop(self, bot_name: str) -> bool:
        """Отправить уведомление об остановке бота"""
        if not self.events_channel:
            return False
        
        message = TelegramMessages.bot_stopped(
            bot_name=bot_name,
            local_time=now_local()
        )
        
        logger.info(f"📨 Отправка уведомления об остановке бота: {bot_name}")
        return self._send(message, self.events_channel)
    
    def send_bot_error(self, bot_name: str, error: str) -> bool:
        """Отправить уведомление об ошибке"""
        if not self.events_channel:
            return False
        
        message = TelegramMessages.bot_error(
            bot_name=bot_name,
            error=error,
            local_time=now_local()
        )
        
        logger.info(f"📨 Отправка уведомления об ошибке бота: {bot_name}")
        return self._send(message, self.events_channel)
    
    def send_daily_log(self, stats: Dict) -> bool:
        """
        Отправить ежедневный лог в канал логов.
        
        Args:
            stats: Статистика (из master_logger)
        """
        if not self.logs_channel:
            return False
        
        time_str = format_datetime(now_local())
        
        message = f"""📊 *ЕЖЕДНЕВНЫЙ ЛОГ* 📊
⏰ {time_str}

💰 *ОБЩАЯ СТАТИСТИКА*
• Баланс: ${stats.get('balance', 0):.2f}
• Общий PnL: {stats.get('total_pnl', 0):+.2f}
• Позиций: {stats.get('positions_count', 0)}

📈 *БОТЫ*\n"""
        
        for bot in stats.get('bots', []):
            pnl = bot.get('pnl', 0)
            pnl_sign = "🟢" if pnl >= 0 else "🔴"
            message += f"• {bot['name']}: {pnl_sign} {pnl:+.2f} | {bot['trades']} сделок\n"
        
        logger.info(f"📨 Отправка ежедневного лога")
        return self._send(message, self.logs_channel, parse_mode='Markdown')


# Глобальный экземпляр для использования в ботах
notifier = TelegramNotifier()