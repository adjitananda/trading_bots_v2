"""
Функции для расчёта метрик эффективности торговли.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


def to_float(value):
    """Конвертирует Decimal в float для математических операций"""
    if value is None:
        return 0.0
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    return float(value) if value is not None else 0.0


def calculate_sharpe_ratio(trades: List[Dict], risk_free_rate: float = 0) -> Optional[float]:
    """
    Рассчитать коэффициент Шарпа.
    
    Args:
        trades: Список сделок (каждая с ключом 'pnl')
        risk_free_rate: Безрисковая ставка (по умолчанию 0)
    
    Returns:
        Sharpe ratio или None (если недостаточно данных)
    """
    if not trades or len(trades) < 2:
        return None
    
    # Извлекаем PnL из сделок (конвертируем Decimal в float)
    returns = [to_float(t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
    
    if len(returns) < 2:
        return None
    
    returns = np.array(returns)
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    
    if std_return == 0:
        return None
    
    sharpe = (mean_return - risk_free_rate) / std_return
    return float(sharpe)


def calculate_max_drawdown(trades: List[Dict]) -> Optional[float]:
    """
    Рассчитать максимальную просадку (Max Drawdown).
    
    Важнейшая метрика риска.
    
    Args:
        trades: Список сделок (каждая с ключами 'pnl' и опционально 'entry_time')
    
    Returns:
        Max drawdown в процентах (например 15.5 для 15.5%) или None
    """
    if not trades:
        return None
    
    # Извлекаем PnL (конвертируем Decimal в float)
    pnls = [to_float(t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
    
    if not pnls:
        return None
    
    # Рассчитываем equity curve (кумулятивная сумма PnL)
    equity = np.cumsum(pnls)
    
    # Добавляем начальный капитал (условно 10000 для расчёта процентов)
    initial_capital = 10000
    equity_values = initial_capital + equity
    
    # Находим максимальную просадку
    peak = equity_values[0]
    max_drawdown = 0
    
    for value in equity_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    return float(max_drawdown) if max_drawdown > 0 else 0.0


def calculate_win_rate(trades: List[Dict]) -> Optional[float]:
    """
    Рассчитать процент прибыльных сделок.
    
    Args:
        trades: Список сделок (каждая с ключом 'pnl')
    
    Returns:
        Win rate в процентах (например 65.5 для 65.5%) или None
    """
    if not trades:
        return None
    
    total = len(trades)
    if total == 0:
        return None
    
    wins = sum(1 for t in trades if to_float(t.get('pnl', 0)) > 0)
    
    return float(wins / total * 100)


def calculate_profit_factor(trades: List[Dict]) -> Optional[float]:
    """
    Рассчитать Profit Factor = Gross Profit / Gross Loss.
    
    Args:
        trades: Список сделок (каждая с ключом 'pnl')
    
    Returns:
        Profit factor (например 1.85) или None
    """
    if not trades:
        return None
    
    gross_profit = sum(to_float(t.get('pnl', 0)) for t in trades if to_float(t.get('pnl', 0)) > 0)
    gross_loss = abs(sum(to_float(t.get('pnl', 0)) for t in trades if to_float(t.get('pnl', 0)) < 0))
    
    if gross_loss == 0:
        return None if gross_profit == 0 else float('inf')
    
    return float(gross_profit / gross_loss)


def calculate_sortino_ratio(trades: List[Dict], risk_free_rate: float = 0) -> Optional[float]:
    """
    Рассчитать коэффициент Сортино (учитывает только негативную волатильность).
    
    Args:
        trades: Список сделок (каждая с ключом 'pnl')
        risk_free_rate: Безрисковая ставка
    
    Returns:
        Sortino ratio или None
    """
    if not trades or len(trades) < 2:
        return None
    
    returns = [to_float(t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
    
    if len(returns) < 2:
        return None
    
    returns = np.array(returns)
    mean_return = np.mean(returns)
    
    # Рассчитываем только отрицательные отклонения
    negative_returns = returns[returns < 0]
    if len(negative_returns) == 0:
        return float('inf')
    
    downside_std = np.std(negative_returns)
    
    if downside_std == 0:
        return None
    
    sortino = (mean_return - risk_free_rate) / downside_std
    return float(sortino)


def calculate_calmar_ratio(trades: List[Dict], period_years: float = None) -> Optional[float]:
    """
    Рассчитать коэффициент Кальмара = Годовая доходность / Max Drawdown.
    
    Args:
        trades: Список сделок (каждая с ключами 'pnl', 'entry_time', 'exit_time')
        period_years: Период в годах (если None - вычисляется автоматически)
    
    Returns:
        Calmar ratio или None
    """
    if not trades or len(trades) < 2:
        return None
    
    # Суммарный PnL (конвертируем Decimal)
    total_pnl = sum(to_float(t.get('pnl', 0)) for t in trades)
    
    # Начальный капитал (условно)
    initial_capital = 10000.0
    total_return = total_pnl / initial_capital
    
    # Определяем период в годах
    if period_years is None:
        # Пытаемся определить по времени сделок
        entry_times = []
        for t in trades:
            et = t.get('entry_time')
            if et:
                # Если это строка, пробуем распарсить
                if isinstance(et, str):
                    try:
                        # Пробуем разные форматы
                        if ' ' in et:
                            dt = datetime.strptime(et, '%Y-%m-%d %H:%M:%S')
                        else:
                            dt = datetime.strptime(et, '%Y-%m-%d')
                        entry_times.append(dt)
                    except:
                        pass
                elif isinstance(et, datetime):
                    entry_times.append(et)
        
        if len(entry_times) < 2:
            # Не можем определить период, используем 30 дней по умолчанию
            period_years = 30 / 365.25
        else:
            min_time = min(entry_times)
            max_time = max(entry_times)
            days = (max_time - min_time).days
            period_years = max(days / 365.25, 1/365)  # Минимум 1 день
    
    # Годовая доходность
    if period_years > 0:
        # Используем float для возведения в степень
        total_return_float = float(total_return)
        annual_return = (1 + total_return_float) ** (1 / period_years) - 1
    else:
        annual_return = 0
    
    # Max Drawdown
    max_dd = calculate_max_drawdown(trades)
    
    if max_dd is None or max_dd == 0:
        return None
    
    calmar = annual_return / (max_dd / 100)
    return float(calmar)


def calculate_all_metrics(trades: List[Dict]) -> Dict[str, Optional[float]]:
    """
    Рассчитать все метрики для списка сделок.
    
    Args:
        trades: Список сделок
    
    Returns:
        Словарь со всеми метриками
    """
    total_pnl = sum(to_float(t.get('pnl', 0)) for t in trades) if trades else 0
    
    return {
        'total_pnl': total_pnl,
        'total_trades': len(trades),
        'win_rate': calculate_win_rate(trades),
        'sharpe_ratio': calculate_sharpe_ratio(trades),
        'max_drawdown': calculate_max_drawdown(trades),
        'profit_factor': calculate_profit_factor(trades),
        'sortino_ratio': calculate_sortino_ratio(trades),
        'calmar_ratio': calculate_calmar_ratio(trades)
    }


# Функция для тестирования на случайных данных
if __name__ == "__main__":
    # Тестовые данные
    test_trades = [
        {'pnl': 100, 'entry_time': '2025-01-01', 'exit_time': '2025-01-02'},
        {'pnl': -50, 'entry_time': '2025-01-03', 'exit_time': '2025-01-04'},
        {'pnl': 200, 'entry_time': '2025-01-05', 'exit_time': '2025-01-06'},
        {'pnl': -30, 'entry_time': '2025-01-07', 'exit_time': '2025-01-08'},
        {'pnl': 150, 'entry_time': '2025-01-09', 'exit_time': '2025-01-10'},
    ]
    
    print("Тестирование метрик:")
    metrics = calculate_all_metrics(test_trades)
    for key, value in metrics.items():
        if value is not None:
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        else:
            print(f"  {key}: None")
