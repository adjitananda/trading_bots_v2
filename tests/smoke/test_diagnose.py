"""
Smoke-тесты для diagnose.py
"""

import pytest
import subprocess
import sys
import os


def test_diagnose_script_exists():
    """Проверка, что diagnose.py существует"""
    diagnose_path = 'scripts/diagnose.py'
    assert os.path.exists(diagnose_path), f"{diagnose_path} не найден"


def test_diagnose_script_runs():
    """Проверка, что diagnose.py запускается без ошибок"""
    result = subprocess.run(
        [sys.executable, 'scripts/diagnose.py'],
        capture_output=True,
        text=True,
        timeout=30
    )
    # diagnose.py может возвращать 0 или 1 в зависимости от проверок
    # Главное — чтобы не было критической ошибки импорта
    assert "Traceback" not in result.stderr
    assert "Error" not in result.stderr or "No handlers could be found" in result.stderr


def test_diagnose_has_required_sections():
    """Проверка наличия обязательных секций в diagnose.py"""
    with open('scripts/diagnose.py', 'r') as f:
        content = f.read()
    
    # Ожидаемые ключевые слова
    required_keywords = [
        'def diagnose',
        'check_',
        'database',
        'bots'
    ]
    
    for kw in required_keywords:
        assert kw in content, f"Keyword '{kw}' not found in diagnose.py"
