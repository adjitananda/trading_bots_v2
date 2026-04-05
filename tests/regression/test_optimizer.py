"""
Регрессионные тесты для оптимизатора параметров
"""

import pytest


class TestParamOptimizer:
    """Тестирование оптимизатора параметров"""
    
    def test_param_optimizer_import(self):
        """Проверка импорта ParamOptimizer"""
        from trading_lib.optimizer.param_optimizer import ParamOptimizer
        assert ParamOptimizer is not None
    
    def test_param_spaces_import(self):
        """Проверка импорта пространств параметров"""
        from trading_lib.optimizer.param_spaces import STRATEGY_PARAM_SPACES
        assert STRATEGY_PARAM_SPACES is not None
        assert isinstance(STRATEGY_PARAM_SPACES, dict)
    
    def test_strategy_param_spaces_have_required_keys(self):
        """Проверка наличия обязательных стратегий в параметрах"""
        from trading_lib.optimizer.param_spaces import STRATEGY_PARAM_SPACES
        
        # Ожидаемые стратегии
        expected_strategies = ['ma_crossover', 'bollinger', 'supertrend']
        
        for strategy in expected_strategies:
            assert strategy in STRATEGY_PARAM_SPACES, f"Strategy {strategy} not found"
    
    def test_ma_crossover_params(self):
        """Проверка параметров MA Crossover"""
        from trading_lib.optimizer.param_spaces import STRATEGY_PARAM_SPACES
        
        params = STRATEGY_PARAM_SPACES.get('ma_crossover', {})
        assert 'short_ma' in params
        assert 'long_ma' in params
        assert params['short_ma']['type'] == 'int'
        assert params['long_ma']['type'] == 'int'
    
    def test_bollinger_params(self):
        """Проверка параметров Bollinger Bands"""
        from trading_lib.optimizer.param_spaces import STRATEGY_PARAM_SPACES
        
        params = STRATEGY_PARAM_SPACES.get('bollinger', {})
        assert 'bb_period' in params
        assert 'bb_std' in params
        assert params['bb_period']['type'] == 'int'
        assert params['bb_std']['type'] == 'float'
    
    def test_supertrend_params(self):
        """Проверка параметров Supertrend"""
        from trading_lib.optimizer.param_spaces import STRATEGY_PARAM_SPACES
        
        params = STRATEGY_PARAM_SPACES.get('supertrend', {})
        assert 'atr_period' in params
        assert 'multiplier' in params
        assert params['atr_period']['type'] == 'int'
        assert params['multiplier']['type'] == 'float'
    
    def test_metrics_import(self):
        """Проверка импорта метрик"""
        from trading_lib.optimizer.metrics import calculate_metrics
        assert calculate_metrics is not None
    
    def test_risk_manager_import(self):
        """Проверка импорта RiskManager"""
        from trading_lib.optimizer.risk_manager import RiskManager
        assert RiskManager is not None
    
    def test_triggers_import(self):
        """Проверка импорта триггеров"""
        from trading_lib.optimizer.triggers import OptimizationTriggers
        assert OptimizationTriggers is not None
    
    def test_parameter_updater_import(self):
        """Проверка импорта ParameterUpdater"""
        from trading_lib.optimizer.parameter_updater import ParameterUpdater
        assert ParameterUpdater is not None
    
    @pytest.mark.slow
    def test_optimizer_db_integration(self, db):
        """Проверка интеграции оптимизатора с БД (медленный)"""
        # Проверяем наличие таблицы optimization_history
        tables = db.query("SHOW TABLES LIKE 'optimization_history'")
        assert len(tables) > 0, "optimization_history table not found"
        
        # Проверяем структуру
        columns = db.query("DESCRIBE optimization_history")
        column_names = [col['Field'] for col in columns]
        
        required_columns = ['id', 'bot_id', 'symbol', 'best_params', 'applied']
        for col in required_columns:
            assert col in column_names
