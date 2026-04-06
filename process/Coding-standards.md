# Стандарты кодирования UTOS

**Версия:** 1.0
**Дата обновления:** 2026-04-06
**Ответственный:** ИИ-Проектировщик
**Для кого:** ИИ-Разработчик

---

## 1. Общие правила

| Правило | Описание |
|---------|----------|
| **Язык** | Python 3.8+ |
| **Имена переменных и функций** | snake_case (пример: `get_balance`, `short_ma`) |
| **Имена классов** | PascalCase (пример: `BybitAdapter`, `RiskManager`) |
| **Имена констант** | UPPER_SNAKE_CASE (пример: `MAX_DRAWDOWN_THRESHOLD`) |
| **Отступы** | 4 пробела (не табуляция) |
| **Кодировка** | UTF-8 |

---

## 2. Структура проекта
trading_bots_v2/
├── trading_lib/ # Общая библиотека (не зависит от конкретного бота)
│ ├── exchanges/ # Адаптеры бирж
│ ├── strategies/ # Торговые стратегии
│ ├── optimizer/ # Оптимизатор и метрики
│ ├── regime/ # Фильтр режимов рынка
│ ├── utils/ # Утилиты (БД, валидация, время)
│ └── telegram/ # Уведомления (без команд)
├── tests/ # Тесты (L1, L2, L3)
├── scripts/ # Скрипты для обслуживания
├── bots/ # Старые single-coin боты (до миграции)
├── crypto_bot.py # CRYPTO_BOT
├── tinkoff_bot.py # TINKOFF_BOT
├── moex_bot.py # MOEX_BOT
├── config/ # Конфигурационные файлы
├── prompts/ # Регламенты ролей
├── process/ # Процессные документы
└── reports/ # Еженедельные отчёты

text

---

## 3. Стандарты кода

### 3.1. Документирование

Каждый модуль, класс и публичная функция должны иметь docstring.

```python
def calculate_sharpe_ratio(trades, risk_free_rate=0.0):
    """
    Рассчитывает Sharpe Ratio по списку сделок.

    Параметры:
    - trades: list of dict — сделки с полями pnl, entry_time, exit_time
    - risk_free_rate: float — безрисковая ставка (по умолчанию 0)

    Возвращает:
    - float: Sharpe Ratio или None, если недостаточно данных
    """
3.2. Импорты
Группировать в порядке:

Стандартные библиотеки Python

Сторонние библиотеки

Внутренние модули trading_lib

python
import os
import json
from datetime import datetime

import pandas as pd
import pytest

from trading_lib.exchanges.interface import ExchangeInterface
from trading_lib.utils.database import Database
3.3. Обработка ошибок
Использовать конкретные исключения, не подавлять ошибки.

python
# Хорошо
try:
    data = exchange.get_klines(symbol)
except ConnectionError as e:
    logger.error(f"Ошибка подключения к {symbol}: {e}")
    return None

# Плохо
try:
    data = exchange.get_klines(symbol)
except:
    pass
3.4. Логирование
Использовать модуль logging, не print().

python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Бот запущен для символа {symbol}")
logger.error(f"Ошибка при размещении ордера: {e}")
4. Стандарты тестирования
Правило	Описание
Покрытие	Каждый новый модуль сопровождается pytest-тестами
Изоляция	Тесты не должны изменять production-БД. Использовать тестовую БД или транзакции с откатом.
Запуск L1	Перед коммитом обязательно запустить pytest tests/smoke/ -v
Имена тестов	test_<название_функции>_<сценарий> (пример: test_calculate_sharpe_empty_trades)
5. Стандарты коммитов
Формат сообщения коммита:

text
Спринт <N>: <Краткое описание>

<Детальное описание (опционально)>
Примеры:

text
Спринт 6: Добавлен каркас tests/ и pytest

- Создана структура tests/ (smoke, regression, fixtures, manual)
- Добавлены L1-тесты для diagnose, database, telegram_commands
- Обновлён requirements.txt (pytest, pytest-cov)
6. Запрещённые практики
Что запрещено	Почему
print() вместо логирования	Не контролируется уровень, не пишется в файл
Голые except:	Скрывает ошибки, затрудняет отладку
Магические числа	Непонятно, откуда взялось значение. Выносить в константы.
Слишком длинные функции (>50 строк)	Трудно читать и тестировать. Разбивать на меньшие.
Изменение production-БД в тестах	Может уничтожить данные реальной торговли
История изменений
Версия	Дата	Изменение	Автор
1.0	2026-04-06	Создание документа	ИИ-Проектировщик
text

---

## Инструкция по размещению

**Создать файлы в репозитории:**

```bash
cd /home/trader/trading_bots_v2

# Создать Glossary.md
cat > process/Glossary.md << 'EOF'
[вставить содержимое Документа 1]
EOF

# Создать Coding-standards.md
cat > process/Coding-standards.md << 'EOF'
[вставить содержимое Документа 2]
EOF

# Отправить в репозиторий
git add process/Glossary.md process/Coding-standards.md
git commit -m "Документация: добавлены Глоссарий и Стандарты кодирования UTOS"
git push
Полный комплект документов process/ (итог)
Файл	Статус
Project-passport.md	✅ Утверждён
Roadmap.md	✅ Утверждён
Project-meeting.md	✅ Существует
Glossary.md	✅ Готов к созданию
Coding-standards.md	✅ Готов к созданию