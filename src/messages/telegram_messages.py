# messages/telegram_messages.py
from datetime import datetime
from typing import Optional, Dict, Any

class TelegramMessages:
    """Класс для генерации сообщений Telegram"""
    
    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Форматирование даты и времени"""
        return dt.strftime('%d.%m.%Y %H:%M:%S')
    
    @staticmethod
    def new_trade(bot_name: str, symbol: str, side: str, price: float, 
                  quantity: float, tp_price: float, sl_price: float, 
                  tp_percent: float, sl_percent: float, order_id: str,
                  balance: float, symbol_pnl: float, total_pnl: float,
                  current_positions: int, total_positions: int, max_positions: int,
                  strategy_name: str, local_time: datetime) -> str:
        """Сообщение о новой сделке"""
        # Определяем эмодзи и направление
        if side == 'BUY':
            side_emoji = "🟢"
            direction = "LONG"
        else:
            side_emoji = "🔴"
            direction = "SHORT"
        
        # Форматируем P&L
        symbol_pnl_formatted = f"+{symbol_pnl:.2f}" if symbol_pnl >= 0 else f"{symbol_pnl:.2f}"
        total_pnl_formatted = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"
        
        # Позиции с учетом новой сделки
        positions_display = f"{current_positions}/{total_positions}/{max_positions}"
        
        return f"""{side_emoji} *НОВАЯ СДЕЛКА* ({order_id}) {side_emoji}
            
🤖 Бот: {bot_name}
📊 Пара: {symbol}
📈 Направление: {direction}
💰 Цена входа: {price:.6f}
🔢 Количество: {quantity:.4f}
🎯 Take Profit: {tp_price:.6f} ({tp_percent:.1f}%)
🛑 Stop Loss: {sl_price:.6f} ({sl_percent:.1f}%)
💰 Баланс: ${balance:.2f} USDT
💰 P&L: {symbol_pnl_formatted}/{total_pnl_formatted}
📊 Позиций: {positions_display} (с учетом этой новой сделки)
📈 Стратегия: {strategy_name}
⏰ Дата и Время: {TelegramMessages.format_datetime(local_time)} (UTC+3)"""

    @staticmethod
    def trade_closed(bot_name: str, symbol: str, side: str, 
                     entry_price: float, exit_price: float, 
                     quantity: float, pnl: float, pnl_percent: float,
                     reason: str, balance: float, symbol_pnl: float, total_pnl: float,
                     strategy_name: str, entry_time: datetime, exit_time: datetime,
                     order_id: str) -> str:
        """Сообщение о закрытии сделки"""
        # Определяем эмодзи и направление
        if side == 'Buy':  # Закрыли Long
            direction = "LONG"
            close_side = "SELL"
        else:  # Закрыли Short
            direction = "SHORT"
            close_side = "BUY"
        
        # Определяем результат
        if pnl > 0:
            result_emoji = "✅"
            result_text = "ПРИБЫЛЬ"
            pnl_sign = "+"
        else:
            result_emoji = "🔴"
            result_text = "УБЫТОК"
            pnl_sign = ""
        
        # Форматируем P&L
        symbol_pnl_formatted = f"+{symbol_pnl:.2f}" if symbol_pnl >= 0 else f"{symbol_pnl:.2f}"
        total_pnl_formatted = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"
        
        # Форматируем PnL сделки
        pnl_formatted = f"{pnl_sign}{pnl:.4f}"
        pnl_percent_formatted = f"{pnl_sign}{pnl_percent:.2f}"
        
        # Определяем причину закрытия на русском
        reason_text = {
            'TP': 'Сработал Take Profit',
            'SL': 'Сработал Stop Loss',
            'MANUAL': 'Ручное закрытие',
            'LIQUIDATION': 'Ликвидация',
            'UNKNOWN': 'Неизвестно'
        }.get(reason, reason)
        
        return f"""❌ *СДЕЛКА ЗАКРЫТА* ({order_id}) ❌

🤖 Бот: {bot_name}
📊 Пара: {symbol}
📈 Направление: {direction}
❗️ Причина: {reason_text}
💰 Цена входа: {entry_price:.6f}
💸 Цена выхода: {exit_price:.6f}
🔢 Количество: {quantity:.4f}
💲 Баланс: ${balance:.2f} USDT
💰 P&L: {symbol_pnl_formatted}/{total_pnl_formatted} (по этой монете / общий)
📈 Стратегия: {strategy_name}
⏰ Время входа: {TelegramMessages.format_datetime(entry_time)} (UTC+3)
⏰ Время выхода: {TelegramMessages.format_datetime(exit_time)} (UTC+3)
{result_emoji} Результат: {result_text} ({pnl_formatted} USDT)"""

    @staticmethod
    def startup(bot_name: str, bot_symbol: str, config: Dict[str, Any], 
                strategy_name: str, local_time: datetime) -> str:
        """Сообщение о запуске бота"""
        return f"""🚀 *БОТ ЗАПУЩЕН* 🚀

🤖 Бот: {bot_name}
📊 Пара: {bot_symbol}
⏰ Время: {TelegramMessages.format_datetime(local_time)} (UTC+3)

⚙️ *Настройки:*
• TP: {config.get('tp', 0)*100:.1f}%
• SL: {config.get('sl', 0)*100:.1f}%
• Таймфрейм: {config.get('timeframe', 5)} мин
• Размер ордера: ${config.get('qty', 10)} USDT
• Плечо: {config.get('leverage', 1)}x
• Макс. позиций: {config.get('max_positions', 5)}
📈 Стратегия: {strategy_name}

✅ Бот готов к работе!"""

    @staticmethod
    def bot_log(bot_name: str, balance: float, symbol_pnl: float, total_pnl: float,
                symbol_positions: int, total_positions: int, max_positions: int,
                strategy_name: str, local_time: datetime) -> str:
        """Лог-сообщение о состоянии бота"""
        # Форматируем P&L
        symbol_pnl_formatted = f"+{symbol_pnl:.2f}" if symbol_pnl >= 0 else f"{symbol_pnl:.2f}"
        total_pnl_formatted = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"
        pnl_display = f"{symbol_pnl_formatted}/{total_pnl_formatted}"
        
        # Форматируем позиции
        positions_display = f"{symbol_positions}/{total_positions}/{max_positions}"
        
        return f"""*ЛОГ БОТА* 📊

🤖 Бот: {bot_name}
💰 Баланс: ${balance:.2f} USDT
💰 P&L: {pnl_display}
📊 Позиций: {positions_display}
📈 Стратегия: {strategy_name}
⏰ Дата и Время: {TelegramMessages.format_datetime(local_time)} (UTC+3)

✅ Бот работает нормально"""

    @staticmethod
    def dashboard_startup(hostname: str, url: str, local_time: datetime) -> str:
        """Сообщение о запуске дашборда"""
        return f"""📊 *ДАШБОРД ЗАПУЩЕН* 📊

⏰ Время: {TelegramMessages.format_datetime(local_time)} (UTC+3)
💻 Сервер: {hostname}
🔗 URL: {url}

✅ Дашборд готов к работе!"""

    @staticmethod
    def bot_stopped(bot_name: str, local_time: datetime) -> str:
        """Сообщение об остановке бота"""
        return f"""🛑 *БОТ ОСТАНОВЛЕН*
🤖 {bot_name}
⏰ {TelegramMessages.format_datetime(local_time)} (UTC+3)"""

    @staticmethod
    def bot_error(bot_name: str, error: str, local_time: datetime) -> str:
        """Сообщение об ошибке бота"""
        return f"""💥 *КРИТИЧЕСКАЯ ОШИБКА*
🤖 {bot_name}
⏰ {TelegramMessages.format_datetime(local_time)} (UTC+3)
❌ {str(error)[:200]}"""