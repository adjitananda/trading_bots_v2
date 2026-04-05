#!/usr/bin/env python3
"""
Очистка тестовых данных из БД.
Оставляет структуру, удаляет только тестовые записи.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db
from src.utils.time_utils import now_utc

def confirm(prompt):
    """Запрос подтверждения"""
    response = input(f"\n{prompt} (y/N): ").lower()
    return response == 'y'

def cleanup_test_data():
    """Очистка тестовых данных"""
    print("\n" + "=" * 60)
    print("🧹 ОЧИСТКА ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)
    
    # Получаем статистику до очистки
    print("\n📊 Статистика до очистки:")
    
    counts = {}
    for table in ['trades', 'orders', 'snapshots', 'alerts', 'bot_stop_events', 'command_logs']:
        result = db.execute_query(f"SELECT COUNT(*) as cnt FROM {table}", fetch_one=True)
        counts[table] = result['cnt'] if result else 0
        print(f"   • {table}: {counts[table]}")
    
    if not confirm("\n⚠️  Удалить все данные? Операция необратима!"):
        print("❌ Операция отменена")
        return
    
    # Очищаем в правильном порядке (с учетом foreign keys)
    print("\n🔄 Очистка...")
    
    tables_in_order = [
        'orders',        # зависит от trades
        'trades',        # зависит от bots
        'snapshots',     # зависит от bots
        'alerts',        # зависит от bots
        'bot_stop_events', # зависит от bots и alerts
        'command_logs'   # независимая
    ]
    
    for table in tables_in_order:
        try:
            db.execute_update(f"DELETE FROM {table}")
            print(f"   ✅ {table} очищена")
        except Exception as e:
            print(f"   ⚠️  {table}: {e}")
    
    # Сбрасываем AUTO_INCREMENT
    print("\n🔄 Сброс AUTO_INCREMENT...")
    for table in ['trades', 'orders', 'snapshots', 'alerts', 'bot_stop_events', 'command_logs']:
        try:
            db.execute_update(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
            print(f"   ✅ {table} AUTO_INCREMENT сброшен")
        except Exception as e:
            print(f"   ⚠️  {table}: {e}")
    
    # Проверяем результат
    print("\n📊 Статистика после очистки:")
    total_cleared = 0
    for table in ['trades', 'orders', 'snapshots', 'alerts', 'bot_stop_events', 'command_logs']:
        result = db.execute_query(f"SELECT COUNT(*) as cnt FROM {table}", fetch_one=True)
        cnt = result['cnt'] if result else 0
        cleared = counts[table] - cnt
        total_cleared += cleared
        print(f"   • {table}: {cnt} (удалено: {cleared})")
    
    print(f"\n✅ Всего удалено записей: {total_cleared}")
    
    # Обновляем статус ботов
    print("\n🤖 Обновление статуса ботов...")
    db.execute_update("UPDATE bots SET status = 'active', status_reason = NULL, status_changed_at = NOW()")
    print("   ✅ Статус ботов сброшен")
    
    print("\n" + "=" * 60)
    print("✅ Очистка завершена!")
    print("=" * 60)
    
    # Показываем текущее состояние ботов
    bots = db.execute_query("SELECT id, name, status, created_at FROM bots ORDER BY id")
    if bots:
        print("\n📋 Текущие боты в БД:")
        for bot in bots:
            created = bot['created_at'].strftime('%Y-%m-%d %H:%M') if bot['created_at'] else 'unknown'
            print(f"   • ID:{bot['id']} | {bot['name']} | {bot['status']} | создан: {created}")

if __name__ == "__main__":
    cleanup_test_data()
