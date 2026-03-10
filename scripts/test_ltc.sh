#!/bin/bash
# Тест LTCUSDT

cd /home/trader/trading_bots_v2
source /home/trader/.venv/bin/activate

echo "=========================================="
echo "🧪 ТЕСТ LTCUSDT"
echo "=========================================="

# Показать текущий статус
echo -e "\n📊 Текущий статус:"
python scripts/manual_trade.py status

# Открыть LONG позицию
echo -e "\n🟢 Открываем LONG LTCUSDT (10 USDT, TP=2%, SL=1%)"
python scripts/manual_trade.py buy LTCUSDT --amount 10 --tp 2 --sl 1

# Подождать немного
echo -e "\n⏳ Ожидание 10 секунд..."
sleep 10

# Показать статус
echo -e "\n📊 Статус после открытия:"
python scripts/manual_trade.py status

echo -e "\n✅ Тест завершен. Для закрытия выполните:"
echo "  python scripts/manual_trade.py close --symbol LTCUSDT"