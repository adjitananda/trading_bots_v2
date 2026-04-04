#!/usr/bin/env python3
"""
Telegram Commander для управления торговыми ботами v2.
"""

import os
import logging
import asyncio
import subprocess
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db
from src.trading.exchange_client import ExchangeClient
from src.utils.time_utils import now_local

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
        self.app.add_handler(CommandHandler("metrics", self.cmd_metrics))
        self.app.add_handler(CommandHandler("symbols", self.cmd_symbols))
        
        # Команды Market Regime
        self.app.add_handler(CommandHandler("regime", self.cmd_regime))
        self.app.add_handler(CommandHandler("risk_status", self.cmd_risk_status))
        self.app.add_handler(CommandHandler("compare_strategies", self.cmd_compare_strategies))
        self.app.add_handler(CommandHandler("reset_risk", self.cmd_reset_risk))
        
        # Команды оптимизации
        self.app.add_handler(CommandHandler("optimize", self.cmd_optimize))
        self.app.add_handler(CommandHandler("optimize_status", self.cmd_optimize_status))
        self.app.add_handler(CommandHandler("apply_params", self.cmd_apply_params))
        self.app.add_handler(CommandHandler("reject_params", self.cmd_reject_params))
        self.app.add_handler(CommandHandler("cancel_optimization", self.cmd_cancel_optimization))
        
        # Управление символами
        self.app.add_handler(CommandHandler("add_symbol", self.cmd_add_symbol))
        self.app.add_handler(CommandHandler("remove_symbol", self.cmd_remove_symbol))
        self.app.add_handler(CommandHandler("reload", self.cmd_reload))
        
        # Заглушки
        self.app.add_handler(CommandHandler("close", self.cmd_close))
        self.app.add_handler(CommandHandler("closeall", self.cmd_close_all))
        self.app.add_handler(CommandHandler("open", self.cmd_open))
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
    
    def _format_params(self, params: Dict) -> str:
        if not params:
            return "не указаны"
        parts = []
        for k, v in params.items():
            if isinstance(v, float):
                parts.append(f"{k}={v:.2f}")
            else:
                parts.append(f"{k}={v}")
        return ", ".join(parts)
    
    # ==================== БАЗОВЫЕ КОМАНДЫ ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            f"🤖 Trading Bots V2 - автоматическая торговля на Bybit\n\n"
            f"📊 Информация:\n"
            f"/status - статус ботов\n"
            f"/positions - открытые позиции\n"
            f"/balance - баланс\n"
            f"/metrics ETHUSDT - метрики бота\n"
            f"/regime ETHUSDT - режим рынка\n"
            f"/risk_status ETHUSDT - статус риска\n\n"
            f"🔧 Управление:\n"
            f"/optimize ETHUSDT ETHUSDT - оптимизация параметров\n"
            f"/optimize_status - статус оптимизаций\n"
            f"/apply_params 42 - применить параметры\n"
            f"/reset_risk ETHUSDT - сбросить риск\n\n"
            f"❓ /help - полная справка"
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        help_text = """🤖 TRADING BOTS V2 - ПОЛНАЯ СПРАВКА

==================================================

📊 ИНФОРМАЦИОННЫЕ КОМАНДЫ
--------------------------------------------------
/status - статус всех ботов
/positions - все открытые позиции
/balance - текущий баланс USDT
/metrics ETHUSDT - метрики бота (Win Rate, Sharpe, Max DD)
/regime ETHUSDT - режим рынка (тренд/флэт/высокая волатильность)
/risk_status ETHUSDT - текущий множитель риска

==================================================

🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ
--------------------------------------------------
/optimize ETHUSDT ETHUSDT - запустить оптимизацию
/optimize_status - показать ожидающие оптимизации
/apply_params 42 - применить найденные параметры
/reject_params 42 - отклонить предложение
/cancel_optimization 42 - отменить оптимизацию

==================================================

📈 СРАВНЕНИЕ СТРАТЕГИЙ
--------------------------------------------------
/compare_strategies ETHUSDT - сравнить 3 стратегии

==================================================

🛡️ УПРАВЛЕНИЕ РИСКАМИ
--------------------------------------------------
/reset_risk ETHUSDT - сбросить risk_multiplier в 1.0

==================================================

📋 УПРАВЛЕНИЕ СИМВОЛАМИ
--------------------------------------------------
/symbols ETHUSDT - список символов бота
/add_symbol ETHUSDT SOLUSDT - добавить символ
/remove_symbol ETHUSDT SOLUSDT - удалить символ
/reload ETHUSDT - перезагрузить параметры

==================================================

⚠️ ВАЖНО
--------------------------------------------------
• HIGH_VOLATILITY режим (ATR ratio > 2.0) — торговля запрещена
• /open и /close в разработке, используйте ручные ордера на бирже"""
        await update.message.reply_text(help_text)
    
    # ==================== ИНФОРМАЦИОННЫЕ КОМАНДЫ ====================
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("✅ Бот работает. Используйте /help")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        open_trades = db.get_open_trades()
        if not open_trades:
            await update.message.reply_text("📭 Нет открытых позиций")
            return
        message = "📈 ОТКРЫТЫЕ ПОЗИЦИИ\n\n"
        for trade in open_trades:
            message += f"{trade['symbol']}: {trade['side']} @ {float(trade['entry_price']):.4f}\n"
        await update.message.reply_text(message)
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        try:
            exchange = ExchangeClient('bybit')
            balance = exchange.get_balance()
            await update.message.reply_text(f"💰 Баланс: ${balance:.2f} USDT")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите бота. Пример: /metrics ETHUSDT")
            return
        bot_name = args[0].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        result = db.execute_query("""
            SELECT * FROM bot_performance_metrics 
            WHERE bot_id = %s ORDER BY metric_date DESC LIMIT 1
        """, (bot['id'],))
        if not result:
            await update.message.reply_text(f"📊 Нет данных по метрикам для {bot_name}")
            return
        m = result[0]
        await update.message.reply_text(
            f"📊 Метрики {bot_name}:\n"
            f"Win Rate: {m['win_rate']:.1f}%\n"
            f"Max Drawdown: {m['max_drawdown']:.2f}%\n"
            f"Sharpe: {m['sharpe_ratio']:.2f}\n"
            f"Profit Factor: {m['profit_factor']:.2f}\n"
            f"Сделок: {m['total_trades']}"
        )
    
    async def cmd_symbols(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите бота. Пример: /symbols ETHUSDT")
            return
        bot_name = args[0].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        symbols = db.execute_query(
            "SELECT symbol FROM bot_symbols WHERE bot_id = %s AND is_active = 1",
            (bot['id'],)
        )
        if not symbols:
            await update.message.reply_text(f"❌ У бота {bot_name} нет символов")
            return
        await update.message.reply_text(f"📋 Символы {bot_name}: {', '.join([s['symbol'] for s in symbols])}")
    
    # ==================== КОМАНДЫ MARKET REGIME ====================
    
    async def cmd_regime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /regime ETHUSDT")
            return
        symbol = args[0].upper()
        try:
            from src.regime.detector import MarketRegimeDetector
            exchange = ExchangeClient('bybit')
            detector = MarketRegimeDetector(exchange)
            regime, metadata = detector.detect(symbol)
            await update.message.reply_text(
                f"🌊 Режим рынка: {symbol}\n"
                f"Текущий режим: {regime.value}\n"
                f"ADX: {metadata.get('adx', 'N/A')}\n"
                f"ATR ratio: {metadata.get('atr_ratio', 'N/A')}\n"
                f"EMA200: {metadata.get('ema200_direction', 'N/A')}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_risk_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /risk_status ETHUSDT")
            return
        symbol = args[0].upper()
        bot = db.get_bot_by_name(symbol)
        if not bot:
            await update.message.reply_text(f"❌ Бот {symbol} не найден")
            return
        from src.optimizer.parameter_updater import get_risk_multiplier, is_halted
        multiplier = get_risk_multiplier(bot['id'], symbol)
        halted = is_halted(bot['id'], symbol)
        await update.message.reply_text(
            f"📊 Risk Status: {symbol}\n\n"
            f"Risk Multiplier: {multiplier:.2f}\n"
            f"Halted: {'Да' if halted else 'Нет'}"
        )
    
    async def cmd_compare_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /compare_strategies ETHUSDT")
            return
        symbol = args[0].upper()
        await update.message.reply_text(f"🔄 Сравнение стратегий для {symbol}...\nЭто может занять 1-2 минуты.")
        try:
            from src.optimizer.param_optimizer import ParamOptimizer
            bot = db.get_bot_by_name(symbol)
            if not bot:
                await update.message.reply_text(f"❌ Бот {symbol} не найден")
                return
            strategies = ['ma_crossover', 'bollinger', 'supertrend']
            results = {}
            for strategy in strategies:
                optimizer = ParamOptimizer(bot['id'], symbol, strategy)
                result = optimizer.optimize(days=60, n_trials=30, trigger_reason="compare_strategies")
                if result:
                    results[strategy] = {
                        'train_sharpe': result.get('train_sharpe', 0),
                        'test_sharpe': result.get('test_sharpe', 0),
                        'overfit_ratio': result.get('overfit_ratio', 999),
                    }
            message = f"📊 Сравнение стратегий для {symbol}\n\n"
            for strategy, data in results.items():
                emoji = "✅" if data['overfit_ratio'] <= 1.5 else "❌"
                message += f"{emoji} {strategy.upper()}\n"
                message += f"   Train Sharpe: {data['train_sharpe']:.3f}\n"
                message += f"   Test Sharpe: {data['test_sharpe']:.3f}\n"
                message += f"   Overfit: {data['overfit_ratio']:.2f}\n\n"
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_reset_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /reset_risk ETHUSDT")
            return
        symbol = args[0].upper()
        bot = db.get_bot_by_name(symbol)
        if not bot:
            await update.message.reply_text(f"❌ Бот {symbol} не найден")
            return
        from src.optimizer.parameter_updater import set_risk_multiplier, set_halted
        set_risk_multiplier(bot['id'], symbol, 1.0, "Ручной сброс пользователем")
        set_halted(bot['id'], symbol, False)
        await update.message.reply_text(f"✅ Risk multiplier для {symbol} сброшен в 1.0")
    
    # ==================== КОМАНДЫ ОПТИМИЗАЦИИ ====================
    
    async def cmd_optimize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Формат: /optimize BOT_NAME SYMBOL\nПример: /optimize ETHUSDT ETHUSDT")
            return
        bot_name = args[0].upper()
        symbol = args[1].upper()
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        await update.message.reply_text(f"🚀 Запущена оптимизация для {symbol}\nЭто может занять 1-2 минуты...")
        script_path = "/home/trader/trading_bots_v2/src/optimizer/param_optimizer.py"
        try:
            result = subprocess.run(
                ["python", script_path, "--bot_id", str(bot['id']), "--symbol", symbol, "--trials", "20", "--days", "30"],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    opt_result = json.loads(result.stdout)
                    best_params = opt_result.get('best_params', {})
                    best_sharpe = opt_result.get('train_sharpe', 0)
                    history_id = opt_result.get('history_id')
                    message = f"✅ Оптимизация для {symbol} завершена!\n\n"
                    message += f"Лучшие параметры: {self._format_params(best_params)}\n"
                    message += f"Ожидаемый Sharpe: {best_sharpe:.4f}\n"
                    if history_id:
                        message += f"Для применения: /apply_params {history_id}"
                    await update.message.reply_text(message)
                except json.JSONDecodeError as e:
                    await update.message.reply_text(f"❌ Ошибка парсинга: {e}\nВывод: {result.stdout[:200]}")
            else:
                error_msg = result.stderr[:300] if result.stderr else "Неизвестная ошибка"
                await update.message.reply_text(f"❌ Ошибка оптимизации: {error_msg}")
        except subprocess.TimeoutExpired:
            await update.message.reply_text("❌ Таймаут оптимизации (более 3 минут)")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_optimize_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        from src.optimizer.parameter_updater import get_pending_optimizations
        pending = get_pending_optimizations()
        if not pending:
            await update.message.reply_text("📭 Нет ожидающих оптимизаций")
            return
        message = "📊 ОЖИДАЮЩИЕ ОПТИМИЗАЦИИ\n\n"
        for p in pending[:5]:
            message += f"🆔 #{p['id']} - {p['bot_name']} {p['symbol']}\n"
            message += f"   Sharpe: {p['best_sharpe']:.4f}\n"
            message += f"   /apply_params {p['id']}\n\n"
        await update.message.reply_text(message)
    
    async def cmd_apply_params(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите ID: /apply_params 42")
            return
        try:
            history_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом")
            return
        from src.optimizer.parameter_updater import update_params, get_pending_optimizations
        pending = get_pending_optimizations()
        target = None
        for p in pending:
            if p['id'] == history_id:
                target = p
                break
        if not target:
            await update.message.reply_text(f"❌ Оптимизация #{history_id} не найдена")
            return
        success = update_params(target['bot_id'], target['symbol'], target['best_params'], history_id)
        if success:
            await update.message.reply_text(f"✅ Параметры для {target['symbol']} обновлены!")
        else:
            await update.message.reply_text(f"❌ Ошибка применения параметров")
    
    async def cmd_reject_params(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите ID: /reject_params 42")
            return
        try:
            history_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом")
            return
        from src.optimizer.parameter_updater import reject_params
        reason = " ".join(args[1:]) if len(args) > 1 else "Отклонено пользователем"
        success = reject_params(history_id, reason)
        if success:
            await update.message.reply_text(f"✅ Оптимизация #{history_id} отклонена")
        else:
            await update.message.reply_text(f"❌ Ошибка")
    
    async def cmd_cancel_optimization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите ID: /cancel_optimization 42")
            return
        try:
            history_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом")
            return
        opt = db.execute_query("SELECT id FROM optimization_history WHERE id = %s AND applied = 0 AND rejected = 0", (history_id,))
        if not opt:
            await update.message.reply_text(f"❌ Оптимизация #{history_id} не найдена")
            return
        from src.optimizer.parameter_updater import reject_params
        reject_params(history_id, "Отменено пользователем")
        await update.message.reply_text(f"✅ Оптимизация #{history_id} отменена")
    
    # ==================== УПРАВЛЕНИЕ СИМВОЛАМИ ====================
    
    async def cmd_add_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_remove_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("🔄 Перезагрузка параметров...")
    
    # ==================== ЗАГЛУШКИ ====================
    
    async def cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_stop_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def cmd_start_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ В разработке")
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("✅ Выполнено")
    
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
