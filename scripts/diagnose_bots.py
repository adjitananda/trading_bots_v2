#!/usr/bin/env python3
"""
Диагностика проблемы с ботами
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

def check_environment():
    """Проверка окружения"""
    print("\n" + "=" * 60)
    print("🔍 ДИАГНОСТИКА БОТОВ")
    print("=" * 60)
    
    # Текущая директория
    print(f"\n📁 Текущая директория: {os.getcwd()}")
    print(f"📁 Проект: {project_root}")
    
    # Python path
    print(f"\n🐍 Python path:")
    for p in sys.path:
        if 'trading_bots_v2' in p:
            print(f"   ✅ {p}")
    
    # Проверка .env
    env_path = project_root / '.env'
    if env_path.exists():
        print(f"\n✅ .env файл найден: {env_path}")
        # Проверяем права
        import stat
        mode = os.stat(env_path).st_mode
        print(f"   Права: {oct(mode)[-3:]}")
    else:
        print(f"\n❌ .env НЕ НАЙДЕН: {env_path}")

def check_database():
    """Проверка подключения к БД"""
    print("\n" + "=" * 60)
    print("🗄️  ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    try:
        from src.core.database import db
        
        # Тестовый запрос
        result = db.execute_query("SELECT 1 as test", fetch_one=True)
        if result and result.get('test') == 1:
            print("✅ Подключение к БД работает")
        else:
            print("❌ Не удалось выполнить запрос")
        
        # Проверяем ботов в БД
        bots = db.execute_query("SELECT id, name, status FROM bots ORDER BY id")
        print(f"\n📊 Боты в БД ({len(bots)}):")
        for bot in bots:
            print(f"   • ID:{bot['id']} | {bot['name']} | {bot['status']}")
        
        # Проверяем наличие записей
        trades = db.execute_query("SELECT COUNT(*) as cnt FROM trades")
        orders = db.execute_query("SELECT COUNT(*) as cnt FROM orders")
        snapshots = db.execute_query("SELECT COUNT(*) as cnt FROM snapshots")
        
        print(f"\n📈 Статистика:")
        print(f"   • trades: {trades[0]['cnt'] if trades else 0}")
        print(f"   • orders: {orders[0]['cnt'] if orders else 0}")
        print(f"   • snapshots: {snapshots[0]['cnt'] if snapshots else 0}")
        
        # Проверяем открытые сделки
        open_trades = db.execute_query(
            "SELECT t.*, b.name as bot_name FROM trades t "
            "JOIN bots b ON t.bot_id = b.id "
            "WHERE t.status = 'open'"
        )
        if open_trades:
            print(f"\n🔓 Открытые сделки ({len(open_trades)}):")
            for t in open_trades:
                print(f"   • {t['bot_name']}: {t['symbol']} {t['side']} @ {t['entry_price']}")
        
    except Exception as e:
        print(f"❌ Ошибка при работе с БД: {e}")
        import traceback
        traceback.print_exc()

def check_bot_files():
    """Проверка файлов ботов"""
    print("\n" + "=" * 60)
    print("🤖 ПРОВЕРКА ФАЙЛОВ БОТОВ")
    print("=" * 60)
    
    bots_dir = project_root / 'bots'
    if not bots_dir.exists():
        print(f"❌ Директория bots не найдена: {bots_dir}")
        return
    
    bot_files = list(bots_dir.glob('*_bot.py'))
    print(f"\nНайдено {len(bot_files)} файлов ботов:")
    
    for bot_file in bot_files:
        print(f"\n📄 {bot_file.name}:")
        
        # Проверяем права
        mode = os.stat(bot_file).st_mode
        print(f"   Права: {oct(mode)[-3:]}")
        
        # Проверяем shebang
        with open(bot_file, 'r') as f:
            first_line = f.readline().strip()
            if first_line.startswith('#!'):
                print(f"   Shebang: {first_line}")
            else:
                print(f"   ⚠️  Нет shebang!")
        
        # Проверяем импорты
        try:
            # Пробуем импортировать бота
            import importlib.util
            spec = importlib.util.spec_from_file_location(bot_file.stem, bot_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                print(f"   ✅ Импорт работает")
        except Exception as e:
            print(f"   ❌ Ошибка импорта: {e}")

def check_processes():
    """Проверка запущенных процессов"""
    print("\n" + "=" * 60)
    print("🔄 ЗАПУЩЕННЫЕ ПРОЦЕССЫ")
    print("=" * 60)
    
    import subprocess
    
    # Ищем процессы ботов
    result = subprocess.run(
        ["ps", "aux", "|", "grep", "python.*_bot.py", "|", "grep", "-v", "grep"],
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip():
        print("\nНайденные процессы:")
        print(result.stdout)
    else:
        print("\n❌ Нет запущенных ботов")

def main():
    check_environment()
    check_database()
    check_bot_files()
    check_processes()
    
    print("\n" + "=" * 60)
    print("\n📋 РЕКОМЕНДАЦИИ:")
    print("   1. Запустите скрипт очистки тестовых данных")
    print("   2. Перезапустите всех ботов:")
    print("      cd /home/trader/trading_bots_v2")
    print("      pkill -f bots/")
    print("      ./scripts/run_all_bots.sh")
    print("   3. Проверьте логи:")
    print("      tail -f /home/trader/trading_bots_v2/logs/*.log")
    print("=" * 60)

if __name__ == "__main__":
    main()
