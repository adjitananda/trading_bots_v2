#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных.
Запускать один раз при создании новой системы.
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту в sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print(f"📁 Project root: {project_root}")
print(f"📁 Python path: {sys.path[0]}")

try:
    import mysql.connector
    from mysql.connector import Error
    print("✅ mysql.connector загружен")
except ImportError as e:
    print(f"❌ Ошибка загрузки mysql.connector: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print("✅ dotenv загружен")
except ImportError as e:
    print(f"❌ Ошибка загрузки dotenv: {e}")
    print("\nПроверьте установку:")
    print("pip list | grep dotenv")
    sys.exit(1)

# Загружаем .env если есть
env_path = project_root / '.env'
if env_path.exists():
    print(f"📁 Найден .env файл: {env_path}")
    load_dotenv(env_path)
else:
    print("⚠️ .env файл не найден. Создаю шаблон...")
    with open(env_path, 'w') as f:
        f.write("""# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=trader
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=trading_bots_v2
""")
    print("✅ Создан шаблон .env. Отредактируйте его с вашим паролем MySQL.")
    print(f"   Файл: {env_path}")
    sys.exit(1)

def init_database():
    """Инициализация базы данных"""
    
    # Параметры подключения (без базы данных)
    config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'trader'),
        'password': os.getenv('MYSQL_PASSWORD'),
    }
    
    db_name = os.getenv('MYSQL_DATABASE', 'trading_bots_v2')
    
    print(f"\n🔧 Конфигурация:")
    print(f"  • Хост: {config['host']}")
    print(f"  • Порт: {config['port']}")
    print(f"  • Пользователь: {config['user']}")
    print(f"  • База данных: {db_name}")
    
    if not config['password'] or config['password'] == 'your_password_here':
        print("\n❌ MYSQL_PASSWORD не задан или используется значение по умолчанию в .env файле")
        print("   Отредактируйте файл .env и укажите правильный пароль MySQL")
        print(f"   nano {env_path}")
        return False
    
    try:
        print(f"\n🔌 Подключаюсь к MySQL...")
        
        # Подключаемся к MySQL (без конкретной БД)
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        print("✅ Подключение успешно!")
        
        # Проверяем, существует ли база данных
        cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
        if cursor.fetchone():
            print(f"📊 База данных '{db_name}' уже существует")
        else:
            print(f"📊 Создаю базу данных '{db_name}'...")
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"✅ База данных '{db_name}' создана")
        
        # Переключаемся на нашу базу данных
        cursor.execute(f"USE {db_name}")
        
        # Читаем SQL файл
        sql_file = Path(__file__).parent / 'create_tables.sql'
        if not sql_file.exists():
            print(f"❌ SQL файл не найден: {sql_file}")
            return False
            
        print(f"\n📝 Читаю SQL файл: {sql_file}")
        with open(sql_file, 'r') as f:
            sql_script = f.read()
        
        # Разделяем на отдельные запросы
        statements = sql_script.split(';')
        valid_statements = [s.strip() for s in statements if s.strip()]
        
        print(f"\n📝 Создаю таблицы ({len(valid_statements)} запросов)...")
        
        for i, statement in enumerate(valid_statements, 1):
            try:
                cursor.execute(statement)
                print(f"  ✅ [{i}/{len(valid_statements)}] Выполнен")
            except Error as e:
                if "already exists" in str(e).lower():
                    print(f"  ⚠️  [{i}] Таблица уже существует")
                else:
                    print(f"  ❌ [{i}] Ошибка: {e}")
                    print(f"     Запрос: {statement[:100]}...")
        
        conn.commit()
        
        # Проверяем, что таблицы создались
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\n📊 Таблицы в базе данных '{db_name}':")
        if tables:
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  • {table_name}: {count} записей")
        else:
            print("  • Таблицы не найдены")
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ База данных успешно инициализирована!")
        return True
        
    except Error as e:
        print(f"\n❌ Ошибка подключения к MySQL: {e}")
        print("\nВозможные решения:")
        print("  1. Проверьте, запущен ли MySQL:")
        print("     sudo systemctl status mysql")
        print("  2. Проверьте пароль в .env файле")
        print("  3. Проверьте права пользователя:")
        print("     sudo mysql -e \"GRANT ALL PRIVILEGES ON *.* TO 'trader'@'localhost' IDENTIFIED BY 'ваш_пароль';\"")
        print("     sudo mysql -e \"FLUSH PRIVILEGES;\"")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Инициализация базы данных trading_bots_v2")
    print("=" * 60)
    
    success = init_database()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Готово! База данных инициализирована.")
        print("\nСледующий шаг: создать класс Database для работы с БД")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Ошибка инициализации.")
        print("=" * 60)