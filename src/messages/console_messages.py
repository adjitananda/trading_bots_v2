# messages/console_messages.py
from datetime import datetime
from typing import Optional, Dict, Any, List

class ConsoleMessages:
    """Класс для генерации сообщений консоли"""
    
    SEPARATOR = "=" * 70
    SHORT_SEPARATOR = "-" * 50
    
    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Форматирование даты и времени"""
        return dt.strftime('%d.%m.%Y %H:%M:%S')
    
    @staticmethod
    def bot_startup(bot_name: str, bot_symbol: str) -> str:
        """Заголовок запуска бота"""
        return f"""{ConsoleMessages.SEPARATOR}
🤖 ЗАПУСК БОТА: {bot_name}
📊 Торговая пара: {bot_symbol}
{ConsoleMessages.SEPARATOR}"""
    
    @staticmethod
    def api_keys_check(api_key: Optional[str], api_secret: Optional[str]) -> str:
        """Проверка API ключей"""
        lines = [
            "\n🔐 ПРОВЕРКА API КЛЮЧЕЙ:",
            f"📎 API Key получен: {'ДА' if api_key else 'НЕТ'}",
            f"📎 API Secret получен: {'ДА' if api_secret else 'НЕТ'}"
        ]
        
        if api_key:
            masked_api = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
            lines.append(f"   -> {masked_api}")
        else:
            lines.append("   -> API Key НЕ НАЙДЕН")
        
        if api_secret:
            masked_secret = f"{api_secret[:4]}...{api_secret[-4:]}" if len(api_secret) > 8 else "***"
            lines.append(f"   -> {masked_secret}")
        else:
            lines.append("   -> API Secret НЕ НАЙДЕН")
        
        lines.append(ConsoleMessages.SHORT_SEPARATOR)
        
        return "\n".join(lines)
    
    @staticmethod
    def bot_ready(bot_name: str, tp: float, sl: float, timeframe: int, 
                  qty: float, leverage: int, max_positions: int, strategy_name: str) -> str:
        """Сообщение о готовности бота"""
        return f"""
🎯 Бот {bot_name} готов к работе
⚙️  Настройки: TP={tp*100:.1f}%, SL={sl*100:.1f}%, TF={timeframe}min
💵 Размер ордера: ${qty} USDT, Плечо: {leverage}x
📊 Макс. позиций: {max_positions}
📈 Стратегия: {strategy_name}
{ConsoleMessages.SEPARATOR}"""
    
    @staticmethod
    def status_line(local_time: datetime, balance: float, symbol_pnl: float, 
                    total_pnl: float, symbol_positions: int, total_positions: int, 
                    max_positions: int) -> str:
        """Строка статуса в консоли"""
        symbol_pnl_formatted = f"+{symbol_pnl:.2f}" if symbol_pnl >= 0 else f"{symbol_pnl:.2f}"
        total_pnl_formatted = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"
        positions_display = f"{symbol_positions}/{total_positions}/{max_positions}"
        
        time_str = ConsoleMessages.format_datetime(local_time)
        
        return f"\n⏰ {time_str} (UTC+3)\n💰 Баланс: ${balance:.2f} USDT | P&L: {symbol_pnl_formatted}/{total_pnl_formatted} | 📊 Позиций: {positions_display}"
    
    @staticmethod
    def analyzing_symbol(symbol: str) -> str:
        """Анализ символа"""
        return f"\n🔍 Анализ {symbol}"
    
    @staticmethod
    def no_data(symbol: str) -> str:
        """Нет данных"""
        return f"❌ Нет данных для {symbol}"
    
    @staticmethod
    def position_exists(symbol: str) -> str:
        """Позиция уже открыта"""
        return f"⏭️ Позиция по {symbol} уже открыта"
    
    @staticmethod
    def buy_signal(symbol: str, price: float) -> str:
        """Сигнал на покупку"""
        return f"🎯 BUY сигнал для {symbol}, цена: {price:.6f}"
    
    @staticmethod
    def sell_signal(symbol: str, price: float) -> str:
        """Сигнал на продажу"""
        return f"🎯 SELL сигнал для {symbol}, цена: {price:.6f}"
    
    @staticmethod
    def no_signal(symbol: str) -> str:
        """Нет сигнала"""
        return f"⏳ Нет сигналов для {symbol}"
    
    @staticmethod
    def max_positions_reached(max_positions: int) -> str:
        """Достигнут лимит позиций"""
        return f"⚠️ Достигнут лимит позиций ({max_positions})"
    
    @staticmethod
    def sleep_pause(seconds: int) -> str:
        """Пауза"""
        return f"\n💤 Пауза {seconds} секунд..."
    
    @staticmethod
    def order_placed(symbol: str, side: str) -> str:
        """Ордер размещен"""
        side_text = "LONG" if side == 'buy' else "SHORT"
        return f"{side_text} ордер размещен для {symbol}"
    
    @staticmethod
    def position_mode_set(symbol: str) -> str:
        """Режим позиции установлен"""
        return f"✅ {symbol}: Режим позиции установлен в One-Way"
    
    @staticmethod
    def sending_telegram_log() -> str:
        """Отправка лога в Telegram"""
        return f"\n📨 Отправляю лог бота в Telegram..."
    
    @staticmethod
    def telegram_log_sent() -> str:
        """Лог отправлен в Telegram"""
        return f"✅ Лог отправлен в Telegram канал"
    
    @staticmethod
    def status_logged(bot_name: str) -> str:
        """Статус записан в БД"""
        return f"📊 Статус бота {bot_name} записан в базу данных"
    
    @staticmethod
    def trade_logged(bot_name: str, side: str) -> str:
        """Сделка записана"""
        return f"📝 {bot_name}: Сделка {side} записана"
    
    @staticmethod
    def trade_updated(bot_name: str, symbol: str, pnl: float) -> str:
        """Сделка обновлена"""
        return f"📝 {bot_name}: Сделка по {symbol} помечена как закрытая с PnL {pnl:.2f}"
    
    @staticmethod
    def trade_not_found(bot_name: str, symbol: str) -> str:
        """Сделка не найдена"""
        return f"⚠️ {bot_name}: Не найдена открытая сделка для {symbol}, создаем новую запись"
    
    @staticmethod
    def db_connected() -> str:
        """Подключение к БД успешно"""
        return f"✅ Подключение к базе данных успешно"
    
    @staticmethod
    def db_connection_error(error: str) -> str:
        """Ошибка подключения к БД"""
        return f"❌ Ошибка подключения к базе: {error}"
    
    @staticmethod
    def bot_stopped_by_user(bot_name: str) -> str:
        """Бот остановлен пользователем"""
        return f"\n🛑 Бот {bot_name} остановлен пользователем"
    
    @staticmethod
    def bot_finished(bot_name: str) -> str:
        """Бот завершил работу"""
        return f"""{ConsoleMessages.SEPARATOR}
👋 Бот {bot_name} завершил работу
📊 Логи сохранены в базу данных
{ConsoleMessages.SEPARATOR}"""
    
    @staticmethod
    def error(message: str, error_type: str = "ERROR") -> str:
        """Сообщение об ошибке"""
        return f"❌ {error_type}: {message}"
    
    @staticmethod
    def warning(message: str) -> str:
        """Предупреждение"""
        return f"⚠️ {message}"
    
    @staticmethod
    def success(message: str) -> str:
        """Успех"""
        return f"✅ {message}"
    
    @staticmethod
    def info(message: str) -> str:
        """Информация"""
        return f"ℹ️ {message}"