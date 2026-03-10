#!/bin/bash
# Скрипт для запуска всех ботов

echo "🚀 Запуск всех торговых ботов"
echo "================================"

# Активируем окружение
source /home/trader/.venv/bin/activate

# Функция для запуска бота в отдельном терминале
run_bot() {
    echo "Запуск $1..."
    cd /home/trader/trading_bots_v2
    python3 bots/${1}.py &
    echo "✅ $1 запущен (PID: $!)"
    sleep 2
}

# Запускаем ботов
run_bot "ada_bot"
run_bot "btc_bot"
run_bot "doge_bot"
run_bot "eth_bot"
run_bot "ltc_bot"
run_bot "sol_bot"
run_bot "xrp_bot"

echo "================================"
echo "✅ Все боты запущены"
echo "📊 Для мониторинга используйте:"
echo "   python scripts/monitor_db_working.py --bot ETHUSDT"
echo "   python scripts/monitor_db_working.py --bot BTCUSDT"
echo ""
echo "❌ Для остановки: pkill -f bots/"