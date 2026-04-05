#!/usr/bin/env python3
"""
Тест метода get_bot
"""
import sys
from pathlib import Path
import pprint

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.core.database import db

print("=== ПРОВЕРКА get_bot_by_name ===")
bot = db.get_bot_by_name('ETHUSDT')
print(f"Тип: {type(bot)}")
print(f"Содержимое:")
pprint.pprint(bot)

print("\n=== ПРОВЕРКА get_bot ===")
if bot and 'id' in bot:
    bot_by_id = db.get_bot(bot['id'])
    print(f"Тип: {type(bot_by_id)}")
    print(f"Содержимое:")
    pprint.pprint(bot_by_id)