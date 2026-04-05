"""
Пространства параметров для различных стратегий.
Используется в ParamOptimizer для определения диапазонов оптимизации.
"""

STRATEGY_PARAM_SPACES = {
    "ma_crossover": {
        "short_ma": (5, 50, "int"),
        "long_ma": (20, 200, "int"),
        "take_profit": (1.0, 10.0, "float"),
        "stop_loss": (0.5, 5.0, "float"),
    },
    "bollinger": {
        "bb_period": (10, 50, "int"),
        "bb_std": (1.5, 3.0, "float"),
        "take_profit": (1.0, 10.0, "float"),
        "stop_loss": (0.5, 5.0, "float"),
    },
    "supertrend": {
        "atr_period": (7, 21, "int"),
        "atr_multiplier": (2.0, 4.0, "float"),
        "take_profit": (1.0, 10.0, "float"),
        "stop_loss": (0.5, 5.0, "float"),
    },
}


def get_param_space(strategy_name: str) -> dict:
    """Получить пространство параметров для стратегии"""
    if strategy_name not in STRATEGY_PARAM_SPACES:
        raise ValueError(f"Неизвестная стратегия: {strategy_name}. Доступны: {list(STRATEGY_PARAM_SPACES.keys())}")
    return STRATEGY_PARAM_SPACES[strategy_name]


def get_available_strategies() -> list:
    """Получить список доступных стратегий"""
    return list(STRATEGY_PARAM_SPACES.keys())


if __name__ == "__main__":
    print("Доступные стратегии:", get_available_strategies())
    for name, space in STRATEGY_PARAM_SPACES.items():
        print(f"\n{name}:")
        for param, (min_val, max_val, typ) in space.items():
            print(f"  {param}: {typ} от {min_val} до {max_val}")
