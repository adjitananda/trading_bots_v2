#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')

print(f"API Key: {api_key[:8]}...{api_key[-4:] if api_key and len(api_key) > 12 else 'не найден'}")
print(f"API Secret: {'*' * 8}...{api_secret[-4:] if api_secret and len(api_secret) > 8 else 'не найден'}")

if not api_key or not api_secret:
    print("❌ API ключи не найдены в .env")
    exit(1)

try:
    # Пробуем подключиться к testnet
    session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
    
    # Пробуем получить информацию о кошельке
    response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    
    if response['retCode'] == 0:
        print("✅ Подключение успешно!")
        print(f"Ответ API: {response}")
    else:
        print(f"❌ Ошибка API: {response}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")