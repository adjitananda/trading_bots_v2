#!/usr/bin/env python3
"""
Telegram Commander для управления торговыми ботами.
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db
from src.trading.exchange_client import ExchangeClient
from src.trading.order_manager import OrderManager
from src.utils.time_utils import now_local, utc_to_local, format_datetime

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ALLOWED_USER_IDS = [int(id) for id in os.getenv("YOUR_TELEGRAM_ID", "").split(",") if id]
logger.info(f"✅ Разрешенные пользователи: {ALLOWED_USER_IDS}")


class TelegramCommander:
    
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        self.pending_actions = {}
    
    def _register_handlers(self):
        # Базовые команды
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Информационные команды
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        
        # Новые команды спринта
        self.app.add_handler(CommandHandler("metrics", self.cmd_metrics))
        self.app.add_handler(CommandHandler("symbols", self.cmd_symbols))
        self.app.add_handler(CommandHandler("add_symbol", self.cmd_add_symbol))
        self.app.add_handler(CommandHandler("remove_symbol", self.cmd_remove_symbol))
        self.app.add_handler(CommandHandler("reload", self.cmd_reload))
        self.app.add_handler(CommandHandler("status_ext", self.cmd_status_extended))
        self.app.add_handler(CommandHandler("help_ext", self.cmd_help_extended))
        
        # Управляющие команды для позиций
        self.app.add_handler(CommandHandler("close", self.cmd_close))
        self.app.add_handler(CommandHandler("closeall", self.cmd_close_all))
        self.app.add_handler(CommandHandler("open", self.cmd_open))
        
        # Управляющие команды для ботов
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("stopall", self.cmd_stop_all))
        self.app.add_handler(CommandHandler("startbot", self.cmd_start_bot))
        self.app.add_handler(CommandHandler("startall", self.cmd_start_all))
        
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_error_handler(self.error_handler)
    
    async def _check_auth(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            await update.message.reply_text("⛔️ Доступ запрещен.")
            return False
        return True
    
    async def _send_typing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    def _format_number_html(self, value: float) -> str:
        if value >= 0:
            return f"+{value:.2f}"
        return f"{value:.2f}"
    
    # ==================== БАЗОВЫЕ КОМАНДЫ ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я бот для управления торговыми ботами v2.\n"
            f"Вот что я умею:\n\n"
            f"📊 /status - общий статус всех ботов\n"
            f"📈 /positions - все открытые позиции\n"
            f"💰 /balance - текущий баланс\n"
            f"📉 /pnl [дни] - PnL за период\n"
            f"📊 /metrics ETHUSDT - метрики бота (НОВОЕ!)\n"
            f"📋 /symbols ETHUSDT - список символов (НОВОЕ!)\n"
            f"➕ /add_symbol ETHUSDT SOLUSDT - добавить символ (НОВОЕ!)\n"
            f"🟢 /open - открыть позицию\n"
            f"❌ /close - закрыть позицию\n"
            f"▶️ /startbot - запустить бота\n"
            f"🛑 /stop - остановить бота\n"
            f"❓ /help - подробная справка\n"
            f"❓ /help_ext - новые команды"
        )
        db.log_command(str(user.id), user.username, "start", {}, True)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        help_text = """
<b>🤖 УПРАВЛЕНИЕ БОТАМИ v2</b>

<b>📊 Информационные команды:</b>
/status - статус всех ботов
/positions - открытые позиции
/balance - текущий баланс
/pnl 7 - PnL за 7 дней
/metrics ETHUSDT - метрики бота (Win Rate, Max DD, Sharpe)
/symbols ETHUSDT - список символов бота

<b>➕ Управление символами (НОВОЕ!):</b>
/add_symbol ETHUSDT SOLUSDT - добавить символ
/remove_symbol ETHUSDT SOLUSDT - удалить символ
/reload ETHUSDT - перезагрузить параметры

<b>📈 Команды для позиций:</b>
/close ETHUSDT - закрыть позицию
/closeall - закрыть все позиции
/open ETHUSDT BUY 10 - открыть LONG на 10 USDT
/open ETHUSDT SELL 10 2 1 - SHORT с TP=2%, SL=1%

<b>🎮 Управление ботами:</b>
/stop ETHUSDT - остановить бота
/stopall - остановить всех
/startbot ETHUSDT - запустить бота
/startall - запустить всех
/status_ext - расширенный статус (символы + позиции)

<b>📝 Примеры:</b>
<code>/metrics ETHUSDT</code> - метрики ETH бота
<code>/symbols ETHUSDT</code> - список символов
<code>/add_symbol ETHUSDT SOLUSDT</code> - добавить SOL
<code>/pnl 7</code> - прибыль за неделю
<code>/open ETHUSDT BUY 10 2 1</code> - LONG с TP/SL

<i>Новые команды: /metrics, /symbols, /add_symbol, /remove_symbol, /reload, /status_ext</i>
        """
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    # ==================== НОВЫЕ КОМАНДЫ СПРИНТА ====================
    
    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await self._send_typing(update, context)
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите бота. Пример: /metrics ETHUSDT", parse_mode="HTML")
            return
        bot_name = args[0].upper()
        symbol = args[1].upper() if len(args) > 1 else None
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        if symbol:
            query = "SELECT * FROM bot_performance_metrics WHERE bot_id = %s AND symbol = %s ORDER BY metric_date DESC LIMIT 1"
            result = db.execute_query(query, (bot['id'], symbol))
        else:
            symbols_data = db.execute_query("SELECT symbol FROM bot_symbols WHERE bot_id = %s AND is_active = 1", (bot['id'],))
            if not symbols_data:
                await update.message.reply_text(f"❌ У бота {bot_name} нет активных символов")
                return
            symbol = symbols_data[0]['symbol']
            query = "SELECT * FROM bot_performance_metrics WHERE bot_id = %s AND symbol = %s ORDER BY metric_date DESC LIMIT 1"
            result = db.execute_query(query, (bot['id'], symbol))
        if not result:
            await update.message.reply_text(f"📊 Нет данных по метрикам для {symbol}\nЗапустите: python scripts/calculate_bot_metrics.py --bot_id {bot['id']}", parse_mode="HTML")
            return
        metrics = result[0]
        message = f"""<b>📊 Метрики {symbol}</b>
Бот: {bot_name}
Период: {metrics['metric_date']}
━━━━━━━━━━━━━━━━━━━━━━━
📈 Win Rate: {metrics['win_rate']:.1f}%
💰 Profit Factor: {metrics['profit_factor']:.2f}
📉 Max Drawdown: {metrics['max_drawdown']:.2f}%
⚡ Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
🎯 Sortino Ratio: {metrics['sortino_ratio']:.2f}
━━━━━━━━━━━━━━━━━━━━━━━
📊 Всего сделок: {metrics['total_trades']}
💰 Общий PnL: {self._format_number_html(float(metrics['total_pnl']))} USDT"""
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def cmd_symbols(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите бота. Пример: /symbols ETHUSDT", parse_mode="HTML")
            return
        bot_name = args[0].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        symbols = db.execute_query("""
            SELECT s.symbol, s.is_active, COUNT(t.id) as open_positions
            FROM bot_symbols s
            LEFT JOIN trades t ON t.bot_id = s.bot_id AND t.symbol = s.symbol AND t.status = 'open'
            WHERE s.bot_id = %s
            GROUP BY s.id
        """, (bot['id'],))
        if not symbols:
            await update.message.reply_text(f"❌ У бота {bot_name} нет активных символов")
            return
        message = f"<b>📋 Символы бота {bot_name}</b>\n\n"
        for s in symbols:
            status_emoji = "🟢" if s['is_active'] else "🔴"
            message += f"{status_emoji} <b>{s['symbol']}</b> - позиций: {s['open_positions'] or 0}\n"
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def cmd_add_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Формат: /add_symbol ETHUSDT SOLUSDT", parse_mode="HTML")
            return
        bot_name = args[0].upper()
        new_symbol = args[1].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        existing = db.execute_query("SELECT id FROM bot_symbols WHERE bot_id = %s AND symbol = %s", (bot['id'], new_symbol))
        if existing:
            await update.message.reply_text(f"⚠️ Символ {new_symbol} уже есть")
            return
        default = db.execute_query("SELECT strategy_params, risk_params FROM bot_symbols WHERE bot_id = %s LIMIT 1", (bot['id'],))
        if default:
            strategy_params = default[0]['strategy_params']
            risk_params = default[0]['risk_params']
        else:
            strategy_params = json.dumps({'short_ma': 6, 'long_ma': 49})
            risk_params = json.dumps({'max_positions': 1})
        db.execute_update("INSERT INTO bot_symbols (bot_id, symbol, strategy_params, risk_params, is_active) VALUES (%s, %s, %s, %s, 1)", (bot['id'], new_symbol, strategy_params, risk_params))
        await update.message.reply_text(f"✅ Символ {new_symbol} добавлен. Выполните /reload {bot_name}")
    
    async def cmd_remove_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Формат: /remove_symbol ETHUSDT SOLUSDT", parse_mode="HTML")
            return
        bot_name = args[0].upper()
        symbol = args[1].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        open_positions = db.execute_query("SELECT id FROM trades WHERE bot_id = %s AND symbol = %s AND status = 'open'", (bot['id'], symbol))
        if open_positions:
            await update.message.reply_text(f"⚠️ Нельзя удалить {symbol}: есть открытые позиции")
            return
        db.execute_update("UPDATE bot_symbols SET is_active = 0 WHERE bot_id = %s AND symbol = %s", (bot['id'], symbol))
        await update.message.reply_text(f"✅ Символ {symbol} деактивирован. Выполните /reload {bot_name}")
    
    async def cmd_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите бота. Пример: /reload ETHUSDT", parse_mode="HTML")
            return
        bot_name = args[0].upper()
        await update.message.reply_text(f"🔄 Запрос на перезагрузку {bot_name} отправлен. Для применения перезапустите процесс: sudo systemctl restart bot-{bot_name.lower()}")
    
    async def cmd_status_extended(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await self._send_typing(update, context)
        bots = db.get_all_active_bots()
        if not bots:
            await update.message.reply_text("❌ Нет активных ботов")
            return
        message = "<b>📊 СТАТУС БОТОВ (расширенный)</b>\n\n"
        for bot in bots:
            symbols = db.execute_query("SELECT symbol FROM bot_symbols WHERE bot_id = %s AND is_active = 1", (bot['id'],))
            if not symbols:
                symbols = [{'symbol': bot['name']}]
            open_trades = db.get_open_trades(bot['id'])
            status_emoji = "🟢" if bot['status'] == 'active' else "🔴"
            message += f"{status_emoji} <b>{bot['name']}</b>\n"
            message += f"   Символы: {', '.join([s['symbol'] for s in symbols])}\n"
            message += f"   Позиций: {len(open_trades)}\n\n"
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def cmd_help_extended(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        help_text = """
<b>🤖 НОВЫЕ КОМАНДЫ (СПРИНТ 1)</b>

/metrics ETHUSDT - метрики бота
/symbols ETHUSDT - список символов
/add_symbol ETHUSDT SOLUSDT - добавить символ
/remove_symbol ETHUSDT SOLUSDT - удалить символ
/reload ETHUSDT - перезагрузить параметры
/status_ext - расширенный статус

<b>Примеры:</b>
<code>/metrics ETHUSDT</code>
<code>/symbols ETHUSDT</code>
<code>/add_symbol ETHUSDT SOLUSDT</code>
        """
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    # ==================== ОСТАЛЬНЫЕ КОМАНДЫ ====================
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("✅ Бот работает. Используйте /help_ext для новых команд.")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        open_trades = db.get_open_trades()
        if not open_trades:
            await update.message.reply_text("📭 Нет открытых позиций")
            return
        message = "<b>📈 ОТКРЫТЫЕ ПОЗИЦИИ</b>\n\n"
        for trade in open_trades:
            message += f"{trade['symbol']}: {trade['side']} @ {float(trade['entry_price']):.4f}\n"
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        try:
            exchange = ExchangeClient('bybit')
            balance = exchange.get_balance()
            await update.message.reply_text(f"💰 Баланс: ${balance:.2f} USDT")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("📊 Используйте /metrics для детальной статистики")
    
    async def cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_stop_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def cmd_start_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("❌ Команда в разработке")
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("✅ Операция выполнена")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Ошибка: {context.error}")
    
    def run(self):
        logger.info("🚀 Telegram Commander запущен")
        self.app.run_polling()


if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN не найден")
        sys.exit(1)
    commander = TelegramCommander(token)
    commander.run()
