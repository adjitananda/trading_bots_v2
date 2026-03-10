#!/bin/bash
# Скрипт для запуска всех ботов с правильным Python из виртуального окружения

echo "=========================================="
echo "🚀 Запуск всех торговых ботов"
echo "=========================================="

# Активируем виртуальное окружение
source /home/trader/.venv/bin/activate

# Проверяем, что используем правильный Python
PYTHON_PATH=$(which python3)
echo "✅ Используется Python: $PYTHON_PATH"

# Функция для запуска бота
run_bot() {
    echo "------------------------------------------"
    echo "Запуск $1..."
    
    # Создаем директорию для логов
    mkdir -p /home/trader/trading_bots_v2/logs
    
    # Запускаем бота с правильным Python
    cd /home/trader/trading_bots_v2
    $PYTHON_PATH bots/${1}.py >> /home/trader/trading_bots_v2/logs/${1}.log 2>&1 &
    
    PID=$!
    sleep 2
    
    if kill -0 $PID 2>/dev/null; then
        echo "✅ $1 запущен (PID: $PID)"
    else
        echo "❌ $1 НЕ запустился!"
        echo "   Лог:"
        tail -5 /home/trader/trading_bots_v2/logs/${1}.log
    fi
}

# Очищаем старые логи
echo "🧹 Очистка старых логов..."
rm -f /home/trader/trading_bots_v2/logs/*.log

# Запускаем ботов
run_bot "ada_bot"
run_bot "btc_bot"
run_bot "doge_bot"
run_bot "eth_bot"
run_bot "ltc_bot"
run_bot "sol_bot"
run_bot "xrp_bot"

echo "=========================================="
echo "✅ Все боты запущены"
echo "=========================================="
echo "📊 Для мониторинга используйте:"
echo "   python3 scripts/monitor_db_working.py --bot ADAUSDT"
echo "=========================================="
