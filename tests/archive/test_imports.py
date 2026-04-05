#!/usr/bin/env python3
"""Тест импортов"""

import sys
print(f"Python path: {sys.path}")

try:
    import pandas as pd
    print(f"✅ pandas {pd.__version__}")
except ImportError as e:
    print(f"❌ pandas: {e}")

try:
    from src.trading.exchange_client import ExchangeClient
    print("✅ exchange_client")
except ImportError as e:
    print(f"❌ exchange_client: {e}")

try:
    from src.trading.order_manager import OrderManager
    print("✅ order_manager")
except ImportError as e:
    print(f"❌ order_manager: {e}")

try:
    from src.core.database import db
    print("✅ database")
except ImportError as e:
    print(f"❌ database: {e}")