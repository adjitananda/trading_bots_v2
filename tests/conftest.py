"""
Pytest конфигурация и общие фикстуры для тестирования UTOS
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Добавляем пути к модулям проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'trading_lib'))

# Флаг использования тестовой БД (не трогаем production)
USE_TEST_DB = os.environ.get('UTOS_TEST_DB', 'false').lower() == 'true'


@pytest.fixture(scope="session")
def project_root():
    """Путь к корню проекта"""
    return PROJECT_ROOT


@pytest.fixture
def db():
    """Фикстура для подключения к БД (только чтение для тестов)"""
    from trading_lib.utils.database import Database
    
    db = Database()
    
    # Для тестов используем транзакцию с откатом, чтобы не менять данные
    # Или отдельную тестовую БД
    
    yield db
    
    # Не закрываем connection, Database сам управляет


@pytest.fixture
def mock_exchange():
    """Фикстура с мок-биржей (без реальных запросов)"""
    mock = Mock()
    mock.get_klines = Mock(return_value=[])
    mock.get_ticker = Mock(return_value={'bid': 100, 'ask': 101})
    mock.create_order = Mock(return_value={'order_id': 'test_123'})
    return mock


@pytest.fixture
def crypto_exchange(mock_exchange):
    """Фикстура для крипто-биржи (использует мок)"""
    return mock_exchange


@pytest.fixture(scope="session")
def sample_klines_eth():
    """Фикстура с тестовыми свечами ETH"""
    import pandas as pd
    import os
    
    file_path = os.path.join(
        os.path.dirname(__file__), 
        'fixtures', 
        'sample_klines_eth.csv'
    )
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        # Преобразуем timestamp в datetime если нужно
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    else:
        # Возвращаем пустой DataFrame если файла нет
        return pd.DataFrame()


@pytest.fixture(scope="session")
def sample_trades():
    """Фикстура с тестовыми сделками"""
    import json
    import os
    
    file_path = os.path.join(
        os.path.dirname(__file__), 
        'fixtures', 
        'sample_trades.json'
    )
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    else:
        return {"trades": []}


@pytest.fixture
def temp_db_cursor():
    """Фикстура для временной таблицы в тестах (с откатом)"""
    from trading_lib.utils.database import Database
    
    db = Database()
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        yield cursor
    finally:
        connection.rollback()
        cursor.close()


# Маркеры для различных типов тестов
def pytest_configure(config):
    config.addinivalue_line(
        "markers", 
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", 
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", 
        "regression: marks tests as regression tests"
    )
