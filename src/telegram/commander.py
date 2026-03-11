#!/usr/bin/env python3
"""
Telegram Commander для управления торговыми ботами.
Позволяет:
- Просматривать открытые позиции
- Открывать и закрывать позиции
- Смотреть баланс и статистику
- Запускать и останавливать ботов
- Получать уведомления о сделках
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
from tabulate import tabulate

# Добавляем путь к проекту
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db
from src.trading.exchange_client import ExchangeFactory
from src.trading.order_manager import OrderManager
from src.utils.time_utils import now_local, utc_to_local, format_datetime
from src.messages.telegram_messages import TelegramMessages

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
ALLOWED_USER_IDS = [int(id) for id in os.getenv("YOUR_TELEGRAM_ID", "").split(",") if id]
logger.info(f"✅ Разрешенные пользователи: {ALLOWED_USER_IDS}")


class TelegramCommander:
    """
    Telegram бот для управления торговлей.
    
    Команды:
    /start - приветствие
    /status - общий статус всех ботов
    /positions - все открытые позиции
    /balance - текущий баланс
    /pnl [days] - PnL за период
    /close [symbol] - закрыть позицию
    /closeall - закрыть все позиции
    /stop [bot] - остановить бота
    /stopall - остановить всех ботов
    /open [symbol] [BUY/SELL] [amount] [tp] [sl] - открыть позицию
    /startbot [bot] - запустить бота
    /startall - запустить всех ботов
    /help - справка
    """
    
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        
        # Кэш для активных действий
        self.pending_actions = {}
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        
        # Базовые команды
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Информационные команды
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        
        # Управляющие команды для позиций
        self.app.add_handler(CommandHandler("close", self.cmd_close))
        self.app.add_handler(CommandHandler("closeall", self.cmd_close_all))
        self.app.add_handler(CommandHandler("open", self.cmd_open))
        
        # Управляющие команды для ботов
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("stopall", self.cmd_stop_all))
        self.app.add_handler(CommandHandler("startbot", self.cmd_start_bot))
        self.app.add_handler(CommandHandler("startall", self.cmd_start_all))
        
        # Обработчик кнопок
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик ошибок
        self.app.add_error_handler(self.error_handler)
    
    async def _check_auth(self, update: Update) -> bool:
        """Проверка авторизации пользователя"""
        user_id = update.effective_user.id
        
        if user_id not in ALLOWED_USER_IDS:
            await update.message.reply_text(
                "⛔️ Доступ запрещен. Вы не авторизованы для использования этого бота."
            )
            logger.warning(f"Неавторизованный доступ: user_id={user_id}")
            return False
        
        logger.info(f"✅ Авторизован доступ: user_id={user_id}")
        return True
    
    async def _send_typing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка индикатора печатания"""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
    
    def _format_number_html(self, value: float) -> str:
        """Форматирование числа для HTML"""
        if value >= 0:
            return f"+{value:.2f}"
        else:
            return f"{value:.2f}"
    
    # ==================== БАЗОВЫЕ КОМАНДЫ ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        if not await self._check_auth(update):
            return
        
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я бот для управления торговыми ботами. Вот что я умею:\n\n"
            f"📊 /status - общий статус всех ботов\n"
            f"📈 /positions - все открытые позиции\n"
            f"💰 /balance - текущий баланс\n"
            f"📉 /pnl [дни] - PnL за период\n"
            f"🟢 /open - открыть позицию\n"
            f"❌ /close - закрыть позицию\n"
            f"▶️ /startbot - запустить бота\n"
            f"🛑 /stop - остановить бота\n"
            f"❓ /help - подробная справка"
        )
        
        # Логируем команду
        db.log_command(
            user_id=str(user.id),
            username=user.username,
            command="start",
            args={},
            success=True
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help"""
        if not await self._check_auth(update):
            return
        
        help_text = """
<b>🤖 УПРАВЛЕНИЕ БОТАМИ</b>

<b>Информационные команды:</b>
/status - статус всех ботов
/positions - открытые позиции
/balance - текущий баланс
/pnl 7 - PnL за 7 дней

<b>Команды для позиций:</b>
/close ETHUSDT - закрыть позицию
/closeall - закрыть все позиции
/open ETHUSDT BUY 10 - открыть LONG на 10 USDT
/open ETHUSDT SELL 10 2 1 - SHORT с TP=2%, SL=1%

<b>Управление ботами:</b>
/stop ETHUSDT - остановить бота
/stopall - остановить всех
/startbot ETHUSDT - запустить бота
/startall - запустить всех

<b>Примеры:</b>
<code>/pnl 7</code> - прибыль за неделю
<code>/open ETHUSDT BUY 10 2 1</code> - LONG с TP/SL
<code>/close ETHUSDT</code> - закрыть ETH
<code>/startbot ETHUSDT</code> - запустить ETH бота

⚠️ <b>Важно:</b> 
- Команды с подтверждением требуют нажатия кнопки
- Запуск/остановка меняет статус в БД, процесс нужно запускать вручную
- Доступ ограничен вашим Telegram ID
        """
        
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    # ==================== ИНФОРМАЦИОННЫЕ КОМАНДЫ ====================
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус всех ботов"""
        if not await self._check_auth(update):
            return
        
        await self._send_typing(update, context)
        
        try:
            bots = db.get_all_active_bots()
            
            if not bots:
                await update.message.reply_text("❌ Нет активных ботов")
                return
            
            message = "<b>📊 СТАТУС БОТОВ</b>\n\n"
            
            for bot in bots:
                # Получаем последний снимок
                snapshot = db.get_last_snapshot(bot["id"])
                
                # Получаем открытые позиции
                open_trades = db.get_open_trades(bot["id"])
                
                # Формируем строку статуса
                status_emoji = "🟢" if bot["status"] == "active" else "🔴"
                message += f"{status_emoji} <b>{bot['name']}</b>\n"
                
                if snapshot:
                    pnl = float(snapshot["total_pnl"])
                    pnl_sign = "🟢" if pnl >= 0 else "🔴"
                    message += f"   Баланс: ${float(snapshot['balance']):.2f}\n"
                    message += f"   PnL: {pnl_sign} ${abs(pnl):.2f}\n"
                
                message += f"   Позиций: {len(open_trades)}\n\n"
            
            await update.message.reply_text(message, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка в status: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все открытые позиции"""
        if not await self._check_auth(update):
            return
        
        await self._send_typing(update, context)
        
        try:
            # Получаем все открытые сделки
            open_trades = db.get_open_trades()
            
            if not open_trades:
                await update.message.reply_text("📭 Нет открытых позиций")
                return
            
            # Группируем по ботам
            message = "<b>📈 ОТКРЫТЫЕ ПОЗИЦИИ</b>\n\n"
            
            # Создаем клавиатуру для каждой позиции
            keyboard = []
            
            for trade in open_trades:
                entry_time = utc_to_local(trade["entry_time"])
                side_emoji = "🟢" if trade["side"] == "BUY" else "🔴"
                
                # Добавляем информацию об источнике сделки
                source_info = "🤖" if trade.get("source_entry") == "auto" else "👤"
                
                # Добавляем в сообщение
                message += f"{side_emoji} {source_info} <b>{trade['bot_name']}</b> - {trade['symbol']}\n"
                message += f"   Вход: {entry_time.strftime('%d.%m %H:%M')}\n"
                message += f"   Цена: ${float(trade['entry_price']):.4f}\n"
                message += f"   Количество: {float(trade['quantity']):.4f}\n\n"
                
                # Добавляем кнопку для закрытия
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Закрыть {trade['symbol']}",
                        callback_data=f"close_{trade['id']}"
                    )
                ])
            
            # Добавляем кнопку "Закрыть все"
            if len(open_trades) > 1:
                keyboard.append([
                    InlineKeyboardButton(
                        "⚠️ Закрыть ВСЕ",
                        callback_data="close_all"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка в positions: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущий баланс"""
        if not await self._check_auth(update):
            return
        
        await self._send_typing(update, context)
        
        try:
            # Создаем клиент биржи
            exchange = ExchangeFactory.create_client("bybit")
            balance = exchange.get_balance()
            
            if balance is None:
                await update.message.reply_text("❌ Не удалось получить баланс")
                return
            
            # Получаем общий PnL
            total_pnl = 0
            bots = db.get_all_active_bots()
            for bot in bots:
                summary = db.get_bot_summary(bot["id"], days=365*10)
                total_pnl += summary.get("total_pnl", 0)
            
            # Получаем открытые позиции
            open_trades = db.get_open_trades()
            
            message = f"""<b>💰 ТЕКУЩИЙ БАЛАНС</b>

Баланс: <b>${balance:.2f}</b> USDT
Общий PnL: <b>{self._format_number_html(total_pnl)}</b> USDT
Открытых позиций: <b>{len(open_trades)}</b>

<i>Последнее обновление: {format_datetime(now_local())}</i>"""
            
            await update.message.reply_text(message, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка в balance: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать PnL за период"""
        if not await self._check_auth(update):
            return
        
        await self._send_typing(update, context)
        
        try:
            # Парсим аргументы: /pnl [bot] [days]
            args = context.args
            bot_name = None
            days = 30  # по умолчанию 30 дней
            
            if args:
                if args[0].upper() in ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT"]:
                    bot_name = args[0].upper()
                    if len(args) > 1:
                        try:
                            days = int(args[1])
                        except:
                            pass
                else:
                    try:
                        days = int(args[0])
                    except:
                        pass
            
            if bot_name:
                # PnL по конкретному боту
                bot = db.get_bot_by_name(bot_name)
                if not bot:
                    await update.message.reply_text(f"❌ Бот {bot_name} не найден")
                    return
                
                # Получаем отдельно статистику по авто и ручным сделкам
                auto_stats = db.get_strategy_performance(bot["id"], days)
                manual_trades = db.get_manual_trades(bot["id"], days)
                manual_pnl = sum(float(t.get("pnl", 0)) for t in manual_trades)
                
                summary = db.get_bot_summary(bot["id"], days=days)
                daily = db.get_daily_pnl(bot["id"], days=days)
                
                total_pnl = summary.get("total_pnl", 0)
                avg_pnl = summary.get("avg_pnl", 0)
                
                # Собираем сообщение
                lines = []
                lines.append(f"<b>📊 P&L {bot_name} за {days} дней</b>")
                lines.append("")
                lines.append(f"Всего сделок: {summary.get('total_trades', 0)}")
                lines.append(f"  🤖 Авто: {auto_stats.get('total_trades', 0)} (Win Rate: {auto_stats.get('win_rate', 0):.1f}%)")
                lines.append(f"  👤 Ручных: {len(manual_trades)}")
                lines.append(f"Прибыльных: {summary.get('profitable_trades', 0)}")
                lines.append(f"Убыточных: {summary.get('loss_trades', 0)}")
                lines.append(f"Общий Win Rate: {summary.get('win_rate', 0):.1f}%")
                lines.append(f"")
                lines.append(f"Общий PnL: <b>{self._format_number_html(total_pnl)}</b> USDT")
                lines.append(f"  🤖 Авто: {self._format_number_html(auto_stats.get('total_pnl', 0))} USDT")
                lines.append(f"  👤 Ручные: {self._format_number_html(manual_pnl)} USDT")
                lines.append(f"Средний PnL: {self._format_number_html(avg_pnl)} USDT")
                lines.append("")
                
                # Последние дни
                if daily:
                    lines.append("<b>Последние дни:</b>")
                    for d in daily[-5:]:
                        date_str = d["date"].strftime("%d.%m")
                        pnl_value = float(d["total_pnl"])
                        lines.append(f"{date_str}: {self._format_number_html(pnl_value)} ({d['trades']} сделок)")
                
                message = "\n".join(lines)
                
            else:
                # Общий PnL по всем ботам
                lines = []
                lines.append(f"<b>📊 ОБЩИЙ P&L за {days} дней</b>")
                lines.append("")
                
                total_pnl = 0
                total_trades = 0
                
                bots = db.get_all_active_bots()
                for bot in bots:
                    summary = db.get_bot_summary(bot["id"], days=days)
                    bot_pnl = summary.get("total_pnl", 0)
                    total_pnl += bot_pnl
                    total_trades += summary.get("total_trades", 0)
                    
                    pnl_sign = "🟢" if bot_pnl >= 0 else "🔴"
                    lines.append(f"{pnl_sign} {bot['name']}: {self._format_number_html(bot_pnl)} USDT")
                
                lines.append("")
                lines.append(f"<b>ИТОГО:</b> {self._format_number_html(total_pnl)} USDT")
                lines.append(f"Всего сделок: {total_trades}")
                
                message = "\n".join(lines)
            
            await update.message.reply_text(message, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка в pnl: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка при формировании отчета")
    
    # ==================== УПРАВЛЯЮЩИЕ КОМАНДЫ ДЛЯ ПОЗИЦИЙ ====================
    
    async def cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Закрыть позицию"""
        if not await self._check_auth(update):
            return
        
        args = context.args
        
        if not args:
            # Если нет аргументов, показываем список позиций для закрытия
            await self.cmd_positions(update, context)
            return
        
        symbol = args[0].upper()
        
        # Ищем открытую позицию по символу
        open_trades = db.get_open_trades()
        trade_to_close = None
        
        for trade in open_trades:
            if trade["symbol"] == symbol:
                trade_to_close = trade
                break
        
        if not trade_to_close:
            await update.message.reply_text(f"❌ Нет открытой позиции по {symbol}")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, закрыть", callback_data=f"confirm_close_{trade_to_close['id']}"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Закрыть позицию <b>{symbol}</b>?\n\n"
            f"Бот: {trade_to_close['bot_name']}\n"
            f"Цена входа: ${float(trade_to_close['entry_price']):.4f}",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    async def cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Закрыть все позиции"""
        if not await self._check_auth(update):
            return
        
        open_trades = db.get_open_trades()
        
        if not open_trades:
            await update.message.reply_text("📭 Нет открытых позиций")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, закрыть все", callback_data="close_all"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Закрыть ВСЕ позиции ({len(open_trades)} шт.)?",
            reply_markup=reply_markup
        )
    
    async def cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открыть новую позицию
        Форматы:
        /open ETHUSDT BUY 10
        /open ETHUSDT SELL 10
        /open ETHUSDT BUY 10 2 1  (с TP=2%, SL=1%)
        """
        if not await self._check_auth(update):
            return
        
        args = context.args
        
        if len(args) < 3:
            await update.message.reply_text(
                "❌ Неправильный формат. Используйте:\n"
                "<code>/open ETHUSDT BUY 10</code> - LONG на 10 USDT\n"
                "<code>/open ETHUSDT SELL 10</code> - SHORT на 10 USDT\n"
                "<code>/open ETHUSDT BUY 10 2 1</code> - с TP=2%, SL=1%",
                parse_mode="HTML"
            )
            return
        
        symbol = args[0].upper()
        side = args[1].upper()
        amount = float(args[2])
        
        # Параметры TP/SL (опционально)
        tp_percent = 2.0  # по умолчанию 2%
        sl_percent = 1.0  # по умолчанию 1%
        
        if len(args) >= 4:
            tp_percent = float(args[3])
        if len(args) >= 5:
            sl_percent = float(args[4])
        
        if side not in ["BUY", "SELL"]:
            await update.message.reply_text("❌ Сторона должна быть BUY или SELL")
            return
        
        # Находим бота для этого символа
        bot = db.get_bot_by_name(symbol)
        if not bot:
            await update.message.reply_text(f"❌ Бот для {symbol} не найден")
            return
        
        # 🟢 УБРАЛИ ПРОВЕРКУ СТАТУСА - ручная торговля работает всегда
        # if bot["status"] != "active":
        #     await update.message.reply_text(f"❌ Бот {symbol} не активен (статус: {bot['status']})")
        #     return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Подтвердить",
                    callback_data=f"confirm_open_{symbol}_{side}_{amount}_{tp_percent}_{sl_percent}"
                ),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Открыть позицию?\n\n"
            f"Символ: <b>{symbol}</b>\n"
            f"Сторона: <b>{side}</b>\n"
            f"Сумма: <b>{amount} USDT</b>\n"
            f"TP: <b>{tp_percent}%</b>\n"
            f"SL: <b>{sl_percent}%</b>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    # ==================== УПРАВЛЯЮЩИЕ КОМАНДЫ ДЛЯ БОТОВ ====================
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Остановить бота"""
        if not await self._check_auth(update):
            return
        
        args = context.args
        
        if not args:
            # Показываем список активных ботов
            bots = db.get_all_active_bots()
            keyboard = []
            
            for bot in bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🛑 {bot['name']}",
                        callback_data=f"stop_{bot['id']}"
                    )
                ])
            
            if len(bots) > 1:
                keyboard.append([
                    InlineKeyboardButton(
                        "⚠️ Остановить ВСЕХ",
                        callback_data="stop_all"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🛑 Выберите бота для остановки:",
                reply_markup=reply_markup
            )
            return
        
        bot_name = args[0].upper()
        bot = db.get_bot_by_name(bot_name)
        
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, остановить", callback_data=f"confirm_stop_{bot['id']}"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Остановить бота <b>{bot_name}</b>?",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    async def cmd_stop_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Остановить всех ботов"""
        if not await self._check_auth(update):
            return
        
        active_bots = db.get_all_active_bots()
        
        if not active_bots:
            await update.message.reply_text("✅ Нет активных ботов")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, остановить всех", callback_data="stop_all"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Остановить ВСЕХ ботов ({len(active_bots)} шт.)?",
            reply_markup=reply_markup
        )
    
    async def cmd_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запустить остановленного бота"""
        if not await self._check_auth(update):
            return
        
        args = context.args
        
        if not args:
            # Показываем список остановленных ботов
            # ИСПРАВЛЕНО: используем одинарные кавычки внутри строки
            bots = db.execute_query(
                "SELECT * FROM bots WHERE status != 'active' AND is_active = TRUE"
            )
            
            if not bots:
                await update.message.reply_text("✅ Нет остановленных ботов")
                return
            
            keyboard = []
            for bot in bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"▶️ {bot['name']} ({bot['status']})",
                        callback_data=f"startbot_{bot['id']}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "▶️ Выберите бота для запуска:",
                reply_markup=reply_markup
            )
            return
        
        bot_name = args[0].upper()
        bot = db.get_bot_by_name(bot_name, active_only=False)
        
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        
        if bot["status"] == "active":
            await update.message.reply_text(f"✅ Бот {bot_name} уже активен")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, запустить", callback_data=f"confirm_startbot_{bot['id']}"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Запустить бота <b>{bot_name}</b>?",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    async def cmd_start_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запустить всех остановленных ботов"""
        if not await self._check_auth(update):
            return
        
        # ИСПРАВЛЕНО: используем одинарные кавычки внутри строки
        stopped_bots = db.execute_query(
            "SELECT * FROM bots WHERE status != 'active' AND is_active = TRUE"
        )
        
        if not stopped_bots:
            await update.message.reply_text("✅ Нет остановленных ботов")
            return
        
        # Запрашиваем подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, запустить всех", callback_data="confirm_startall"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Запустить всех остановленных ботов ({len(stopped_bots)} шт.)?",
            reply_markup=reply_markup
        )
    
    # ==================== ОБРАБОТЧИК КНОПОК ====================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Обработка отмены
        if data == "cancel":
            await query.edit_message_text("❌ Операция отменена")
            return
        
        # Закрытие конкретной сделки
        if data.startswith("confirm_close_"):
            trade_id = int(data.replace("confirm_close_", ""))
            await self._execute_close_trade(query, trade_id)
            return
        
        # Закрытие всех сделок
        if data == "close_all":
            await self._execute_close_all(query)
            return
        
        # Открытие позиции
        if data.startswith("confirm_open_"):
            # Формат: confirm_open_ETHUSDT_BUY_10_2_1
            parts = data.replace("confirm_open_", "").split("_")
            symbol = parts[0]
            side = parts[1]
            amount = float(parts[2])
            tp = float(parts[3])
            sl = float(parts[4])
            await self._execute_open_position(query, symbol, side, amount, tp, sl)
            return
        
        # Запуск конкретного бота
        if data.startswith("confirm_startbot_"):
            bot_id = int(data.replace("confirm_startbot_", ""))
            await self._execute_start_bot(query, bot_id)
            return
        
        # Запуск всех ботов
        if data == "confirm_startall":
            await self._execute_start_all(query)
            return
        
        # Остановка конкретного бота
        if data.startswith("confirm_stop_"):
            bot_id = int(data.replace("confirm_stop_", ""))
            await self._execute_stop_bot(query, bot_id)
            return
        
        # Остановка всех ботов
        if data == "stop_all":
            await self._execute_stop_all(query)
            return
        
        # Если просто закрыть (без подтверждения) - показываем детали
        if data.startswith("close_"):
            trade_id = int(data.replace("close_", ""))
            trade = db.get_trade(trade_id)
            
            if trade:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_close_{trade_id}"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"⚠️ Закрыть сделку?\n\n"
                    f"Бот: {trade['bot_name']}\n"
                    f"Символ: {trade['symbol']}\n"
                    f"Сторона: {trade['side']}\n"
                    f"Цена входа: ${float(trade['entry_price']):.4f}",
                    reply_markup=reply_markup
                )
        
        # Остановка бота (выбор)
        if data.startswith("stop_"):
            bot_id = int(data.replace("stop_", ""))
            bot = db.get_bot(bot_id)
            
            if bot:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_stop_{bot_id}"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"⚠️ Остановить бота <b>{bot['name']}</b>?",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        
        # Запуск бота (выбор)
        if data.startswith("startbot_"):
            bot_id = int(data.replace("startbot_", ""))
            bot = db.get_bot(bot_id)
            
            if bot:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_startbot_{bot_id}"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"⚠️ Запустить бота <b>{bot['name']}</b>?",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
    
    # ==================== МЕТОДЫ ВЫПОЛНЕНИЯ ====================
    
    async def _execute_close_trade(self, query, trade_id: int):
        """Исполнить закрытие сделки"""
        try:
            await query.edit_message_text("🔄 Закрываю позицию...")
            
            trade = db.get_trade(trade_id)
            if not trade:
                await query.edit_message_text("❌ Сделка не найдена")
                return
            
            # Создаем клиент биржи
            exchange = ExchangeFactory.create_client_for_bot(trade["bot_name"])
            order_manager = OrderManager(exchange, trade["bot_id"], trade["bot_name"])
            
            # Определяем сторону для закрытия
            close_side = "sell" if trade["side"] == "BUY" else "buy"
            
            # Закрываем позицию (ручное закрытие - source="manual")
            result = order_manager.place_market_order(
                symbol=trade["symbol"],
                side=close_side,
                quantity=float(trade["quantity"]),
                source="manual"  # Явно указываем, что это ручное закрытие
            )
            
            if result["success"]:
                # Ждем немного и проверяем закрытие
                await asyncio.sleep(2)
                closed = order_manager.check_closed_positions(trade["symbol"])
                
                if closed:
                    pnl = closed[0]["pnl"]
                    source_info = f"[{closed[0].get('source_entry', '?')}→manual]"
                    
                    # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ О ЗАКРЫТИИ =====
                    try:
                        from src.telegram.notifier import notifier
                        
                        # Получаем детали сделки для уведомления
                        trade_details = db.get_trade(trade_id)
                        if trade_details:
                            notifier.send_close_notification({
                                "bot_name": trade["bot_name"],
                                "symbol": trade["symbol"],
                                "side": trade_details["side"],
                                "entry_price": float(trade_details["entry_price"]),
                                "exit_price": float(closed[0].get("exit_price", 0)),
                                "quantity": float(trade_details["quantity"]),
                                "pnl": pnl,
                                "pnl_percent": closed[0].get("pnl_percent", 0),
                                "reason": "MANUAL",
                                "balance": exchange.get_balance() or 0,
                                "symbol_pnl": 0,  # TODO: добавить расчет
                                "total_pnl": 0,   # TODO: добавить расчет
                                "strategy_name": trade["bot_name"],  # или получить из БД
                                "entry_time": trade_details["entry_time"],
                                "order_id": result["order_id"]
                            })
                            print(f"✅ Уведомление о закрытии отправлено для {trade['symbol']}")
                    except Exception as e:
                        print(f"❌ Ошибка отправки уведомления о закрытии: {e}")
                    
                    await query.edit_message_text(
                        f"✅ Позиция <b>{trade['symbol']}</b> закрыта {source_info}\n"
                        f"PnL: <b>{self._format_number_html(pnl)}</b> USDT",
                        parse_mode="HTML"
                    )
                else:
                    await query.edit_message_text(
                        f"✅ Ордер на закрытие отправлен, но PnL пока не получен"
                    )
            else:
                await query.edit_message_text(f"❌ Ошибка: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_close_all(self, query):
        """Закрыть все позиции"""
        try:
            await query.edit_message_text("🔄 Закрываю все позиции...")
            
            open_trades = db.get_open_trades()
            results = []
            
            for trade in open_trades:
                try:
                    exchange = ExchangeFactory.create_client_for_bot(trade["bot_name"])
                    order_manager = OrderManager(exchange, trade["bot_id"], trade["bot_name"])
                    
                    close_side = "sell" if trade["side"] == "BUY" else "buy"
                    
                    result = order_manager.place_market_order(
                        symbol=trade["symbol"],
                        side=close_side,
                        quantity=float(trade["quantity"]),
                        source="manual"  # Явно указываем, что это ручное закрытие
                    )
                    
                    if result["success"]:
                        results.append(f"✅ {trade['symbol']}")
                    else:
                        results.append(f"❌ {trade['symbol']}: {result.get('error')}")
                    
                    await asyncio.sleep(0.5)  # Пауза между ордерами
                    
                except Exception as e:
                    results.append(f"❌ {trade['symbol']}: {e}")
            
            message = "<b>РЕЗУЛЬТАТЫ ЗАКРЫТИЯ</b>\n\n" + "\n".join(results)
            await query.edit_message_text(message, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии всех: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_open_position(self, query, symbol: str, side: str, amount: float, tp_percent: float, sl_percent: float):
        """Исполнить открытие позиции"""
        try:
            await query.edit_message_text("🔄 Открываю позицию...")
            
            # Находим бота
            bot = db.get_bot_by_name(symbol)
            if not bot:
                await query.edit_message_text(f"❌ Бот {symbol} не найден")
                return
            
            # Создаем клиент биржи
            exchange = ExchangeFactory.create_client_for_bot(symbol)
            order_manager = OrderManager(exchange, bot["id"], symbol)
            
            # Получаем текущую цену
            price = exchange.get_current_price(symbol)
            if not price:
                await query.edit_message_text(f"❌ Не удалось получить цену для {symbol}")
                return
            
            # Рассчитываем количество
            quantity = exchange.calculate_quantity(symbol, amount, price)
            
            # Рассчитываем TP/SL цены
            if side == "BUY":
                tp_price = price * (1 + tp_percent / 100)
                sl_price = price * (1 - sl_percent / 100)
            else:
                tp_price = price * (1 - tp_percent / 100)
                sl_price = price * (1 + sl_percent / 100)
            
            # Открываем позицию (ручная - source="manual")
            result = order_manager.place_market_order(
                symbol=symbol,
                side=side.lower(),
                quantity=quantity,
                take_profit=tp_price,
                stop_loss=sl_price,
                tp_percent=tp_percent,
                sl_percent=sl_percent,
                source="manual"  # Явно указываем, что это ручная сделка
            )
            
            if result["success"]:
                # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ =====
                try:
                    from src.telegram.notifier import notifier
                    
                    # Получаем баланс и PnL (опционально)
                    balance = exchange.get_balance() or 0
                    
                    # Отправляем уведомление
                    notifier.send_trade_notification({
                        "bot_id": bot["id"],
                        "bot_name": symbol,
                        "symbol": symbol,
                        "side": side.lower(),
                        "entry_price": result["entry_price"],
                        "quantity": quantity,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                        "tp_percent": tp_percent,
                        "sl_percent": sl_percent,
                        "order_id": result["order_id"],
                        "balance": balance,
                        "symbol_pnl": 0,  # TODO: можно добавить расчет
                        "total_pnl": 0,   # TODO: можно добавить расчет
                        "source": "manual"
                    })
                    print(f"✅ Уведомление отправлено для ручной сделки {symbol}")
                except Exception as e:
                    print(f"❌ Ошибка отправки уведомления: {e}")
                
                await query.edit_message_text(
                    f"✅ Позиция открыта (ручная)!\n\n"
                    f"Символ: <b>{symbol}</b>\n"
                    f"Сторона: <b>{side}</b>\n"
                    f"Цена входа: <b>${result['entry_price']:.4f}</b>\n"
                    f"Количество: <b>{quantity:.4f}</b>\n"
                    f"Order ID: <code>{result['order_id']}</code>",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text(f"❌ Ошибка: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Ошибка при открытии позиции: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_stop_bot(self, query, bot_id: int):
        """Остановить бота"""
        try:
            bot = db.get_bot(bot_id)
            if not bot:
                await query.edit_message_text("❌ Бот не найден")
                return
            
            # Обновляем статус в БД
            db.update_bot_status(bot_id, "stopped", "telegram_command")
            
            await query.edit_message_text(
                f"🛑 Бот <b>{bot['name']}</b> остановлен\n"
                f"(автоматическая торговля отключена, ручные сделки доступны)",
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_stop_all(self, query):
        """Остановить всех ботов"""
        try:
            bots = db.get_all_active_bots()
            
            for bot in bots:
                db.update_bot_status(bot["id"], "stopped", "telegram_command")
            
            await query.edit_message_text(
                f"🛑 Все боты остановлены\n"
                f"(автоматическая торговля отключена, ручные сделки доступны)"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при остановке всех: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_start_bot(self, query, bot_id: int):
        """Запустить бота (обновить статус в БД)"""
        try:
            bot = db.get_bot(bot_id)
            if not bot:
                await query.edit_message_text("❌ Бот не найден")
                return
            
            # Обновляем статус в БД
            db.update_bot_status(bot_id, "active", "telegram_command")
            
            await query.edit_message_text(
                f"✅ Бот <b>{bot['name']}</b> отмечен как активный\n"
                f"(автоматическая торговля включена)",
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    async def _execute_start_all(self, query):
        """Запустить всех ботов"""
        try:
            # ИСПРАВЛЕНО: используем одинарные кавычки внутри строки
            stopped_bots = db.execute_query(
                "SELECT * FROM bots WHERE status != 'active' AND is_active = TRUE"
            )
            
            for bot in stopped_bots:
                db.update_bot_status(bot["id"], "active", "telegram_command")
            
            await query.edit_message_text(
                f"✅ {len(stopped_bots)} ботов отмечены как активные\n"
                f"(автоматическая торговля включена)"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при запуске всех: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
    
    # ==================== ОБРАБОТЧИК ОШИБОК ====================
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ошибок"""
        logger.error(f"Ошибка: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла внутренняя ошибка. Попробуйте позже."
            )
    
    # ==================== ЗАПУСК ====================
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Telegram Commander запущен")
        self.app.run_polling()


# Точка входа
if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN не найден в .env")
        sys.exit(1)
    
    commander = TelegramCommander(token)
    commander.run()