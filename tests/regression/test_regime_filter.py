"""
Регрессионные тесты для фильтра режимов рынка
"""

import pytest


class TestMarketRegime:
    """Тестирование определения режимов рынка"""
    
    def test_regime_enum_import(self):
        """Проверка импорта MarketRegime"""
        from trading_lib.regime.regimes import MarketRegime
        assert MarketRegime is not None
    
    def test_regime_enum_values(self):
        """Проверка значений Enum MarketRegime"""
        from trading_lib.regime.regimes import MarketRegime
        
        # Ожидаемые режимы
        expected_regimes = [
            'HIGH_VOLATILITY',
            'STRONG_UPTREND',
            'STRONG_DOWNTREND',
            'RANGING'
        ]
        
        for regime in expected_regimes:
            assert hasattr(MarketRegime, regime), f"Regime {regime} not found"
    
    def test_detector_import(self):
        """Проверка импорта детектора"""
        from trading_lib.regime.detector import MarketRegimeDetector
        assert MarketRegimeDetector is not None
    
    def test_detector_has_detect_method(self):
        """Проверка наличия метода detect"""
        from trading_lib.regime.detector import MarketRegimeDetector
        
        # Проверяем, что класс имеет метод detect
        assert hasattr(MarketRegimeDetector, 'detect') or hasattr(MarketRegimeDetector, 'detect_regime')
    
    def test_restrictions_import(self):
        """Проверка импорта ограничений"""
        from trading_lib.regime.restrictions import RegimeRestrictions
        assert RegimeRestrictions is not None
    
    @pytest.mark.slow
    def test_regime_log_table_exists(self, db):
        """Проверка наличия таблицы market_regime_log"""
        tables = db.query("SHOW TABLES LIKE 'market_regime_log'")
        assert len(tables) > 0, "market_regime_log table not found"
        
        # Проверяем структуру
        columns = db.query("DESCRIBE market_regime_log")
        column_names = [col['Field'] for col in columns]
        
        required_columns = ['id', 'bot_id', 'symbol', 'regime', 'timestamp']
        for col in required_columns:
            assert col in column_names
