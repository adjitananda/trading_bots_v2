├── init.py # Инициализация пакета
├── conftest.py # Общие фикстуры для pytest
├── README.md # Этот файл
├── smoke/ # L1: Smoke-тесты (2-3 минуты)
│ ├── test_diagnose.py # Проверка diagnose.py
│ ├── test_database.py # Проверка БД
│ └── test_telegram_commands.py # Проверка Telegram команд
├── regression/ # L2: Регрессионные тесты (30-60 минут)
│ ├── test_crypto_bot.py # Тесты крипто-бота
│ ├── test_tinkoff_bot.py # Тесты TINKOFF бота
│ ├── test_moex_bot.py # Тесты MOEX бота
│ ├── test_optimizer.py # Тесты оптимизатора
│ └── test_regime_filter.py # Тесты режимов рынка
├── fixtures/ # Тестовые данные
│ ├── sample_klines_eth.csv # Пример свечей ETH
│ └── sample_trades.json # Пример сделок
└── manual/ # L3: Ручные чек-листы
└── regression_checklist.md # Чек-лист для тестировщика