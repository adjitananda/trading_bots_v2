#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

print("=" * 60)
print("🔍 ДИАГНОСТИКА АУТЕНТИФИКАЦИИ BYBIT")
print("=" * 60)

# Проверяем пути к .env
print("\n📁 ПРОВЕРКА ПУТЕЙ:")
project_root = Path(__file__).parent
print(f"Текущий файл: {__file__}")
print(f"project_root: {project_root}")

env_paths = [
    project_root / '.env',
    project_root.parent / '.env',
    Path('/home/trader/trading_bots_v2/.env'),
    Path.home() / 'trading_bots_v2/.env',
]

for i, path in enumerate(env_paths, 1):
    exists = path.exists()
    print(f"Путь {i}: {path} - {'✅' if exists else '❌'}")

# Загружаем .env
env_file = Path('/home/trader/trading_bots_v2/.env')
load_dotenv(env_file)

api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')

print("\n🔑 ПРОВЕРКА КЛЮЧЕЙ:")
print(f"API Key: {api_key[:8] if api_key else 'None'}...{api_key[-4:] if api_key and len(api_key) > 8 else ''}")
print(f"API Secret: {'*' * 8}...{api_secret[-4:] if api_secret and len(api_secret) > 8 else ''}")

if not api_key or not api_secret:
    print("❌ Ключи не найдены!")
    sys.exit(1)

print("\n🔬 ТЕСТ 1: Серверное время (без аутентификации)")
try:
    response = requests.get("https://api-testnet.bybit.com/v5/market/time")
    print(f"Статус: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Серверное время: {data}")
        server_time = int(data['result']['timeSecond'])
        print(f"✅ Сервер доступен")
    else:
        print(f"❌ Ошибка: {response.text}")
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")

print("\n🔬 ТЕСТ 2: Проверка формата ключей")
print(f"Длина API Key: {len(api_key)} символов")
print(f"Длина Secret: {len(api_secret)} символов")

# Проверяем, нет ли лишних пробелов или символов
print(f"API Key без пробелов: '{api_key.strip()}'")
print(f"Secret без пробелов: '{api_secret.strip()}'")

print("\n🔬 ТЕСТ 3: Прямой запрос с подписью (GET)")

timestamp = str(int(time.time() * 1000))
recv_window = "5000"

# Для GET запроса параметры идут в URL
params = {
    "accountType": "UNIFIED",
    "coin": "USDT"
}

# Сортируем параметры для консистентности
param_str = urlencode(sorted(params.items()))

# Создаем подпись (для GET запроса)
signature_payload = timestamp + api_key + recv_window + param_str
signature = hmac.new(
    bytes(api_secret.strip(), "utf-8"),
    bytes(signature_payload, "utf-8"),
    hashlib.sha256
).hexdigest()

headers = {
    "X-BAPI-API-KEY": api_key.strip(),
    "X-BAPI-TIMESTAMP": timestamp,
    "X-BAPI-SIGN": signature,
    "X-BAPI-RECV-WINDOW": recv_window
}

url = f"https://api-testnet.bybit.com/v5/account/wallet-balance?{param_str}"

print(f"URL: {url}")
print(f"Timestamp: {timestamp}")
print(f"Recv Window: {recv_window}")
print(f"Signature: {signature[:16]}...")

try:
    response = requests.get(url, headers=headers)
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('retCode') == 0:
            print("✅ УСПЕХ! Баланс получен")
        else:
            print(f"❌ Ошибка API: {data.get('retMsg')} (код: {data.get('retCode')})")
    else:
        print(f"❌ HTTP ошибка")
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")

print("\n🔬 ТЕСТ 4: POST запрос (информация о позициях)")

# Для POST запроса параметры в теле
params_post = {
    "category": "linear",
    "symbol": "BTCUSDT",
    "settleCoin": "USDT"
}

timestamp_post = str(int(time.time() * 1000))

# Для POST подпись строится иначе
param_str_post = urlencode(sorted(params_post.items()))
signature_payload_post = timestamp_post + api_key + recv_window + param_str_post
signature_post = hmac.new(
    bytes(api_secret.strip(), "utf-8"),
    bytes(signature_payload_post, "utf-8"),
    hashlib.sha256
).hexdigest()

headers_post = {
    "X-BAPI-API-KEY": api_key.strip(),
    "X-BAPI-TIMESTAMP": timestamp_post,
    "X-BAPI-SIGN": signature_post,
    "X-BAPI-RECV-WINDOW": recv_window,
    "Content-Type": "application/json"
}

url_post = "https://api-testnet.bybit.com/v5/position/list"

try:
    response = requests.post(url_post, headers=headers_post, json=params_post)
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text[:500]}")
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")

print("\n🔬 ТЕСТ 5: Проверка через pybit")
try:
    from pybit.unified_trading import HTTP
    
    session = HTTP(
        testnet=True,
        api_key=api_key.strip(),
        api_secret=api_secret.strip()
    )
    
    # Проверяем соединение через простой запрос
    time_response = session.get_server_time()
    print(f"Серверное время (pybit): {time_response}")
    
    # Пробуем получить информацию о кошельке
    balance_response = session.get_wallet_balance(
        accountType="UNIFIED",
        coin="USDT"
    )
    print(f"Баланс (pybit): {balance_response}")
    
except Exception as e:
    print(f"❌ Ошибка pybit: {e}")

print("\n" + "=" * 60)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 60)