#!/bin/bash
# Скрипт для запуска Telegram Commander

cd /home/trader/trading_bots_v2
source /home/trader/.venv/bin/activate

echo "=========================================="
echo "🚀 ЗАПУСК TELEGRAM COMMANDER"
echo "=========================================="

# Проверяем наличие токена
if ! grep -q "TELEGRAM_TOKEN" .env; then
    echo "❌ TELEGRAM_TOKEN не найден в .env"
    exit 1
fi

# Создаем директорию для логов
mkdir -p logs

# Запускаем бота
python -m src.telegram.commander 2>&1 | tee -a logs/telegram.log