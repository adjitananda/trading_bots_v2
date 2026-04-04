#!/usr/bin/env python3
"""
Telegram Commander для управления торговыми ботами.
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
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        
        # Новые команды спринта 1
        self.app.add_handler(CommandHandler("metrics", self.cmd_metrics))
        self.app.add_handler(CommandHandler("symbols", self.cmd_symbols))
        self.app.add_handler(CommandHandler("add_symbol", self.cmd_add_symbol))
        self.app.add_handler(CommandHandler("remove_symbol", self.cmd_remove_symbol))
        self.app.add_handler(CommandHandler("reload", self.cmd_reload))
        self.app.add_handler(CommandHandler("status_ext", self.cmd_status_extended))
        self.app.add_handler(CommandHandler("help_ext", self.cmd_help_extended))
        
        # Команды оптимизации (спринт 2)
        self.app.add_handler(CommandHandler("optimize", self.cmd_optimize))
        self.app.add_handler(CommandHandler("optimize_status", self.cmd_optimize_status))
        self.app.add_handler(CommandHandler("apply_params", self.cmd_apply_params))
        self.app.add_handler(CommandHandler("reject_params", self.cmd_reject_params))
        
        # Команды Market Regime
        self.app.add_handler(CommandHandler("regime", self.cmd_regime))
        self.app.add_handler(CommandHandler("risk_status", self.cmd_risk_status))
        self.app.add_handler(CommandHandler("compare_strategies", self.cmd_compare_strategies))
        self.app.add_handler(CommandHandler("reset_risk", self.cmd_reset_risk))
        self.app.add_handler(CommandHandler("cancel_optimization", self.cmd_cancel_optimization))
        
        # Управляющие команды
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
            f"Я бот для управления торговыми ботами v2.\n\n"
            f"📊 /status - статус ботов\n"
            f"📈 /positions - открытые позиции\n"
            f"💰 /balance - баланс\n"
            f"📊 /metrics ETHUSDT - метрики\n"
            f"🔧 /optimize ETHUSDT SOLUSDT - запустить оптимизацию\n"
            f"❓ /help - подробная справка"
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        help_text = """
<b>🤖 УПРАВЛЕНИЕ БОТАМИ v2</b>

<b>📊 Информационные команды:</b>
/status - статус всех ботов
/positions - открытые позиции
/balance - текущий баланс
/metrics ETHUSDT - метрики бота

<b>🔧 Оптимизация (НОВОЕ!):</b>
/optimize ETHUSDT SOLUSDT - запустить оптимизацию
/optimize_status - статус оптимизаций
/apply_params 42 - применить параметры
/reject_params 42 - отклонить параметры

<b>📋 Управление символами:</b>
/symbols ETHUSDT - список символов
/add_symbol ETHUSDT SOLUSDT - добавить символ
/remove_symbol ETHUSDT SOLUSDT - удалить символ

<b>📈 Команды для позиций:</b>
/close ETHUSDT - закрыть позицию
/open ETHUSDT BUY 10 - открыть позицию

<b>🎮 Управление ботами:</b>
/stop ETHUSDT - остановить бота
/startbot ETHUSDT - запустить бота
        """
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    async def cmd_help_extended(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        help_text = """
<b>🤖 НОВЫЕ КОМАНДЫ ОПТИМИЗАЦИИ</b>

/optimize ETHUSDT SOLUSDT - ручной запуск оптимизации
/optimize_status - показать ожидающие оптимизации
/apply_params 42 - применить параметры
/reject_params 42 - отклонить предложение

<b>Пример:</b>
1. /optimize ETHUSDT ETHUSDT
2. Ждёте результат (1-2 минуты)
3. /apply_params 123
        """
        await update.message.reply_text(help_text, parse_mode="HTML")
    
    # ==================== ИНФОРМАЦИОННЫЕ КОМАНДЫ ====================
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("✅ Бот работает. Используйте /help")
    
    async def cmd_status_extended(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("📊 Расширенный статус в разработке")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        await update.message.reply_text("📈 Список позиций в разработке")
    
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
    
    # ==================== КОМАНДЫ МЕТРИК ====================
    
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
            await update.message.reply_text("❌ Укажите бота")
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
    
    # ==================== КОМАНДЫ ОПТИМИЗАЦИИ ====================
    
    async def cmd_optimize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update):
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Формат: /optimize ETHUSDT SOLUSDT")
            return
        
        bot_name = args[0].upper()
        symbol = args[1].upper()
        
        bot = db.get_bot_by_name(bot_name)
        if not bot:
            await update.message.reply_text(f"❌ Бот {bot_name} не найден")
            return
        
        await update.message.reply_text(
            f"🚀 Запущена оптимизация для {symbol}\n"
            f"Это может занять 1-2 минуты..."
        )
        
        script_path = "/home/trader/trading_bots_v2/src/optimizer/param_optimizer.py"
        
        try:
            result = subprocess.run(
                ["python", script_path, "--bot_id", str(bot['id']), "--symbol", symbol, "--trials", "20"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                opt_result = json.loads(result.stdout)
                best_params = opt_result.get('best_params', {})
                best_sharpe = opt_result.get('best_sharpe', 0)
                
                message = f"""✅ Оптимизация для {symbol} завершена!

<b>Лучшие параметры:</b>
{self._format_params(best_params)}

<b>Ожидаемый Sharpe:</b> {best_sharpe:.4f}

Для применения: /apply_params {opt_result.get('history_id')}
Для отклонения: /reject_params {opt_result.get('history_id')}
"""
                await update.message.reply_text(message, parse_mode="HTML")
            else:
                await update.message.reply_text(f"❌ Ошибка: {result.stderr[:200]}")
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
        
        message = "<b>📊 ОЖИДАЮЩИЕ ОПТИМИЗАЦИИ</b>\n\n"
        for p in pending[:5]:
            message += f"🆔 #{p['id']} - {p['bot_name']} {p['symbol']}\n"
            message += f"   Sharpe: {p['best_sharpe']:.4f}\n"
            message += f"   /apply_params {p['id']}\n\n"
        
        await update.message.reply_text(message, parse_mode="HTML")
    
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
        
        success = update_params(
            target['bot_id'],
            target['symbol'],
            target['best_params'],
            history_id
        )
        
        if success:
            await update.message.reply_text(
                f"✅ Параметры для {target['symbol']} обновлены!\n"
                f"Для применения перезапустите бота: sudo systemctl restart bot-{target['bot_name'].lower()}"
            )
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
    
    # ==================== ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ КОМАНД ====================
    
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

    # ==================== КОМАНДЫ MARKET REGIME ====================
    
    async def cmd_regime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущий режим рынка."""
        if not await self._check_auth(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /regime ETHUSDT")
            return
        
        symbol = args[0].upper()
        
        try:
            from src.regime.detector import MarketRegimeDetector
            from src.trading.exchange_client import ExchangeClient
            
            exchange = ExchangeClient('bybit')
            detector = MarketRegimeDetector(exchange)
            
            regime, metadata = detector.detect(symbol)
            
            # Эмодзи для режима
            regime_emojis = {
                'high_volatility': '🌊🔴',
                'strong_uptrend': '📈🟢',
                'strong_downtrend': '📉🔴',
                'ranging': '🟡📊'
            }
            emoji = regime_emojis.get(regime.value, '❓')
            
            message = f"""
<b>{emoji} Режим рынка: {symbol}</b>

<b>Текущий режим:</b> {regime.value.replace('_', ' ').upper()}

<b>Метрики:</b>
• ADX: {metadata.get('adx', 'N/A')}
• ATR ratio: {metadata.get('atr_ratio', 'N/A')}
• EMA200: {metadata.get('ema200_direction', 'N/A')}
• Текущая цена: ${metadata.get('price', 'N/A')}

<b>Интерпретация:</b>
"""
            
            if regime.value == 'high_volatility':
                message += "⚠️ Высокая волатильность! Торговля запрещена."
            elif regime.value in ['strong_uptrend', 'strong_downtrend']:
                message += "✅ Сильный тренд. Стратегии MA Crossover и SuperTrend могут работать."
            else:
                message += "🟡 Флэтовый рынок. Стратегия Bollinger Bands наиболее подходит."
            
            await update.message.reply_text(message, parse_mode="HTML")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_risk_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать risk_multiplier и причину снижения."""
        if not await self._check_auth(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите символ. Пример: /risk_status ETHUSDT")
            return
        
        symbol = args[0].upper()
        
        # Находим бота
        bot = db.get_bot_by_name(symbol)
        if not bot:
            await update.message.reply_text(f"❌ Бот {symbol} не найден")
            return
        
        from src.optimizer.parameter_updater import get_risk_multiplier, is_halted
        
        multiplier = get_risk_multiplier(bot['id'], symbol)
        halted = is_halted(bot['id'], symbol)
        
        # Получаем последний триггер
        trigger = db.execute_query("""
            SELECT trigger_level, reasons, action_taken, timestamp
            FROM trigger_log
            WHERE bot_id = %s AND symbol = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (bot['id'], symbol))
        
        message = f"""
<b>📊 Risk Status: {symbol}</b>

<b>Risk Multiplier:</b> {multiplier:.2f}
<b>Halted:</b> {'✅ Да' if halted else '❌ Нет'}

<b>Последний триггер:</b>
"""
        
        if trigger:
            t = trigger[0]
            level_str = "⚠️ WARNING" if t['trigger_level'] == 1 else "🔴 HALT" if t['trigger_level'] == 2 else "🟢 OK"
            message += f"""
Уровень: {level_str}
Действие: {t.get('action_taken', 'N/A')}
Время: {t['timestamp']}
"""
        else:
            message += "Нет срабатываний"
        
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def cmd_compare_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сравнить 3 стратегии на out-of-sample данных."""
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
            
            # Находим бота
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
                        'params': result.get('best_params', {})
                    }
            
            # Формируем сообщение
            message = f"<b>📊 Сравнение стратегий для {symbol}</b>\n\n"
            
            for strategy, data in results.items():
                emoji = "🟢" if data['overfit_ratio'] <= 1.5 else "🔴"
                message += f"{emoji} <b>{strategy.upper()}</b>\n"
                message += f"   Train Sharpe: {data['train_sharpe']:.3f}\n"
                message += f"   Test Sharpe: {data['test_sharpe']:.3f}\n"
                message += f"   Overfit: {data['overfit_ratio']:.2f}\n"
                message += f"   Параметры: {self._format_params(data['params'])}\n\n"
            
            message += "\n<i>Overfit ratio < 1.5 — хорошо, > 1.5 — переобучение</i>"
            
            await update.message.reply_text(message, parse_mode="HTML")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_reset_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сбросить risk_multiplier в 1.0."""
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
        
        await update.message.reply_text(f"✅ Risk multiplier для {symbol} сброшен в 1.0\nТорговля возобновлена.")
    
    async def cmd_cancel_optimization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменить запущенную оптимизацию."""
        if not await self._check_auth(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ Укажите ID оптимизации. Пример: /cancel_optimization 42")
            return
        
        try:
            history_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом")
            return
        
        # Проверяем, существует ли оптимизация
        opt = db.execute_query(
            "SELECT id FROM optimization_history WHERE id = %s AND applied = 0 AND rejected = 0",
            (history_id,)
        )
        
        if not opt:
            await update.message.reply_text(f"❌ Оптимизация #{history_id} не найдена или уже обработана")
            return
        
        from src.optimizer.parameter_updater import reject_params
        reject_params(history_id, "Отменено пользователем")
        
        await update.message.reply_text(f"✅ Оптимизация #{history_id} отменена")
