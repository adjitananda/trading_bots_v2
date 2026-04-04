#!/usr/bin/env python3
"""
ParamOptimizer - оптимизация параметров стратегии с помощью Optuna.
"""

import sys
import json
import logging
import optuna
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from optuna.samplers import TPESampler

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.trading.exchange_client import ExchangeClient
from src.strategies.legacy import StrategyFactory
from src.core.database import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ParamOptimizer:
    """Оптимизатор параметров стратегии"""
    
    def __init__(self, bot_id: int, symbol: str):
        self.bot_id = bot_id
        self.symbol = symbol
        self.exchange = ExchangeClient('bybit')
        self.strategy_name = None
        self.current_params = {}
        
        # Загружаем текущие параметры
        self._load_current_params()
    
    def _load_current_params(self):
        """Загрузить текущие параметры из bot_symbols"""
        query = """
            SELECT strategy_params, strategy_type
            FROM bot_symbols bs
            JOIN bots b ON b.id = bs.bot_id
            WHERE bs.bot_id = %s AND bs.symbol = %s
        """
        result = db.execute_query(query, (self.bot_id, self.symbol))
        
        if result:
            params = result[0]['strategy_params']
            if isinstance(params, str):
                params = json.loads(params)
            self.current_params = params or {}
            
            # Определяем стратегию (пока только ma_crossover)
            self.strategy_name = 'ma_crossover'
        else:
            logger.warning(f"Не найдены параметры для {self.symbol}")
            self.current_params = {'short_ma': 12, 'long_ma': 36}
    
    def get_historical_data(self, days: int = 90) -> pd.DataFrame:
        """
        Загрузить исторические данные для оптимизации.
        
        Args:
            days: Количество дней истории
        
        Returns:
            DataFrame с колонками ['open', 'high', 'low', 'close', 'volume']
        """
        limit = days * 24 * 12  # 5-минутные свечи: 12 в час * 24 часа * дни
        interval = '5m'
        
        logger.info(f"📥 Загрузка исторических данных для {self.symbol} за {days} дней...")
        
        df = self.exchange.get_klines(self.symbol, interval, limit)
        
        if df is None or df.empty:
            logger.error("❌ Не удалось загрузить данные")
            return pd.DataFrame()
        
        logger.info(f"✅ Загружено {len(df)} свечей")
        return df
    
    def objective(self, trial: optuna.Trial, df: pd.DataFrame) -> float:
        """
        Целевая функция для Optuna.
        
        Args:
            trial: Текущее испытание Optuna
            df: DataFrame с историческими данными
        
        Returns:
            Sharpe Ratio (цель максимизации)
        """
        # Параметры для оптимизации (MA Crossover)
        short_ma = trial.suggest_int('short_ma', 5, 50)
        long_ma = trial.suggest_int('long_ma', 20, 200)
        take_profit = trial.suggest_float('take_profit', 1.0, 10.0)
        stop_loss = trial.suggest_float('stop_loss', 0.5, 5.0)
        
        # Валидация: short_ma должен быть меньше long_ma
        if short_ma >= long_ma:
            return -1000.0
        
        # Создаём стратегию с параметрами
        strategy_params = {
            'short_ma': short_ma,
            'long_ma': long_ma
        }
        
        try:
            strategy = StrategyFactory.create_strategy('ma_crossover', strategy_params)
        except Exception as e:
            logger.error(f"Ошибка создания стратегии: {e}")
            return -1000.0
        
        # Бэктестинг
        trades = self.backtest(strategy, df, take_profit / 100, stop_loss / 100)
        
        if len(trades) < 5:
            return -1000.0
        
        # Рассчитываем метрики
        returns = [t['pnl'] for t in trades if t['pnl'] is not None]
        
        if len(returns) < 2:
            return -1000.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return -1000.0
        
        sharpe = mean_return / std_return
        
        # Штраф за слишком частые сделки
        if len(trades) > 100:
            sharpe *= 0.9
        
        # Бонус за положительный PnL
        total_pnl = sum(returns)
        if total_pnl > 0:
            sharpe *= (1 + total_pnl / 1000)
        
        return sharpe
    
    def backtest(self, strategy, df: pd.DataFrame, tp_percent: float, sl_percent: float) -> List[Dict]:
        """
        Простой бэктест стратегии.
        
        Returns:
            Список сделок с полями: entry_time, exit_time, pnl
        """
        trades = []
        position = None
        entry_price = 0
        entry_time = None
        
        for i in range(50, len(df)):
            # Берём окно данных
            window = df.iloc[:i+1]
            
            try:
                signal = strategy.get_signal(window)
            except Exception:
                continue
            
            current_price = df.iloc[i]['close']
            current_time = df.index[i]
            
            # Открытие позиции
            if position is None and signal == 'up':
                position = 'long'
                entry_price = current_price
                entry_time = current_time
            
            # Закрытие позиции
            elif position is not None:
                # Проверка TP/SL
                if position == 'long':
                    tp_price = entry_price * (1 + tp_percent)
                    sl_price = entry_price * (1 - sl_percent)
                    
                    if current_price >= tp_price:
                        # TP сработал
                        pnl = (tp_price - entry_price) / entry_price * 100
                        trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'pnl': pnl,
                            'type': 'tp'
                        })
                        position = None
                    elif current_price <= sl_price:
                        # SL сработал
                        pnl = (sl_price - entry_price) / entry_price * 100
                        trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'pnl': pnl,
                            'type': 'sl'
                        })
                        position = None
                    elif signal == 'down':
                        # Сигнал на закрытие
                        pnl = (current_price - entry_price) / entry_price * 100
                        trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'pnl': pnl,
                            'type': 'signal'
                        })
                        position = None
        
        return trades
    
    def optimize(self, days: int = 90, n_trials: int = 100, trigger_reason: str = None) -> Dict[str, Any]:
        """
        Запустить оптимизацию параметров.
        
        Args:
            days: Количество дней истории для бэктеста
            n_trials: Количество испытаний Optuna
            trigger_reason: Причина запуска (для записи в историю)
        
        Returns:
            Словарь с лучшими параметрами и метриками
        """
        logger.info(f"🚀 Запуск оптимизации для {self.symbol} (бот {self.bot_id})")
        logger.info(f"   Испытаний: {n_trials}, дней истории: {days}")
        
        # Создаём запись в optimization_history
        history_id = db.execute_update("""
            INSERT INTO optimization_history (bot_id, symbol, trigger_reason, trials_count, optimization_start)
            VALUES (%s, %s, %s, %s, NOW())
        """, (self.bot_id, self.symbol, trigger_reason, n_trials))
        
        # Загружаем данные
        df = self.get_historical_data(days)
        if df.empty:
            logger.error("❌ Нет данных для оптимизации")
            return None
        
        # Создаём исследование Optuna
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=42)
        )
        
        # Запускаем оптимизацию
        study.optimize(
            lambda trial: self.objective(trial, df),
            n_trials=n_trials,
            show_progress_bar=True
        )
        
        # Получаем лучшие параметры
        best_trial = study.best_trial
        best_params = best_trial.params
        best_sharpe = best_trial.value
        
        logger.info(f"✅ Оптимизация завершена!")
        logger.info(f"   Лучший Sharpe: {best_sharpe:.4f}")
        logger.info(f"   Параметры: {best_params}")
        
        # Формируем результат
        result = {
            'best_params': best_params,
            'best_sharpe': best_sharpe,
            'n_trials': n_trials,
            'current_params': self.current_params,
            'history_id': history_id
        }
        
        # Обновляем запись в БД
        db.execute_update("""
            UPDATE optimization_history 
            SET optimization_end = NOW(), best_sharpe = %s, best_params = %s, old_params = %s
            WHERE id = %s
        """, (best_sharpe, json.dumps(best_params), json.dumps(self.current_params), history_id))
        
        return result


def main():
    """CLI для запуска оптимизации"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Оптимизация параметров стратегии')
    parser.add_argument('--bot_id', type=int, required=True, help='ID бота')
    parser.add_argument('--symbol', type=str, required=True, help='Торговый символ')
    parser.add_argument('--days', type=int, default=90, help='Дней истории (по умолчанию 90)')
    parser.add_argument('--trials', type=int, default=100, help='Испытаний Optuna (по умолчанию 100)')
    parser.add_argument('--trigger', type=str, help='Причина запуска')
    
    args = parser.parse_args()
    
    optimizer = ParamOptimizer(args.bot_id, args.symbol)
    result = optimizer.optimize(days=args.days, n_trials=args.trials, trigger_reason=args.trigger)
    
    if result:
        print(json.dumps(result, indent=2))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
