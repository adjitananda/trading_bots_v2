#!/usr/bin/env python3
"""
ParamOptimizer - оптимизация параметров стратегии с помощью Optuna.
"""

import sys
import json
import logging
import optuna

# Подавляем вывод логов Optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.trading.exchange_client import ExchangeClient
from src.strategies.legacy import StrategyFactory
from src.core.database import db
from src.optimizer.param_spaces import get_param_space

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ParamOptimizer:
    
    def __init__(self, bot_id: int, symbol: str, strategy_name: str = None):
        self.bot_id = bot_id
        self.symbol = symbol
        self.exchange = ExchangeClient('bybit')
        self.strategy_name = strategy_name
        self.current_params = {}
        self._load_current_params()
    
    def _load_current_params(self):
        """Загрузить текущие параметры из bot_symbols"""
        query = """
            SELECT bs.strategy_params, b.strategy_type
            FROM bot_symbols bs
            JOIN bots b ON b.id = bs.bot_id
            WHERE bs.bot_id = %s AND bs.symbol = %s
        """
        result = db.execute_query(query, (self.bot_id, self.symbol), fetch_one=True)
        
        if result:
            params = result['strategy_params']
            if isinstance(params, str):
                params = json.loads(params)
            self.current_params = params or {}
            
            if not self.strategy_name:
                self.strategy_name = result.get('strategy_type', 'ma_crossover')
            logger.info(f"Загружены параметры для {self.symbol}: {self.current_params}")
        else:
            logger.warning(f"Не найдены параметры для {self.symbol}, используем дефолтные")
            self.current_params = {'short_ma': 12, 'long_ma': 36}
            self.strategy_name = self.strategy_name or 'ma_crossover'
        
        logger.info(f"Стратегия: {self.strategy_name}, параметры: {self.current_params}")
    
    def get_historical_data(self, days: int = 90) -> pd.DataFrame:
        """Загрузить исторические данные"""
        limit = days * 24 * 12
        interval = '5'
        logger.info(f"📥 Загрузка данных для {self.symbol} за {days} дней...")
        df = self.exchange.get_klines(self.symbol, interval, limit)
        if df is None or df.empty:
            logger.error("❌ Не удалось загрузить данные")
            return pd.DataFrame()
        logger.info(f"✅ Загружено {len(df)} свечей")
        return df
    
    def backtest(self, strategy, df: pd.DataFrame, tp_percent: float, sl_percent: float) -> Tuple[List[Dict], float]:
        trades = []
        position = None
        entry_price = 0
        entry_time = None
        
        for i in range(50, len(df)):
            window = df.iloc[:i+1]
            try:
                signal = strategy.get_signal(window)
            except Exception:
                continue
            
            current_price = df.iloc[i]['close']
            current_time = df.index[i]
            
            if position is None and signal == 'up':
                position = 'long'
                entry_price = current_price
                entry_time = current_time
            elif position is not None:
                if position == 'long':
                    tp_price = entry_price * (1 + tp_percent / 100)
                    sl_price = entry_price * (1 - sl_percent / 100)
                    if current_price >= tp_price:
                        pnl = (tp_price - entry_price) / entry_price * 100
                        trades.append({'entry_time': entry_time, 'exit_time': current_time, 'pnl': pnl})
                        position = None
                    elif current_price <= sl_price:
                        pnl = (sl_price - entry_price) / entry_price * 100
                        trades.append({'entry_time': entry_time, 'exit_time': current_time, 'pnl': pnl})
                        position = None
                    elif signal == 'down':
                        pnl = (current_price - entry_price) / entry_price * 100
                        trades.append({'entry_time': entry_time, 'exit_time': current_time, 'pnl': pnl})
                        position = None
        
        if not trades:
            return [], 0
        total_pnl = sum(t['pnl'] for t in trades)
        return trades, total_pnl
    
    def objective(self, trial: optuna.Trial, train_df: pd.DataFrame) -> float:
        param_space = get_param_space(self.strategy_name)
        params = {}
        for param_name, (min_val, max_val, param_type) in param_space.items():
            if param_type == "int":
                params[param_name] = trial.suggest_int(param_name, int(min_val), int(max_val))
            else:
                params[param_name] = trial.suggest_float(param_name, min_val, max_val)
        
        if self.strategy_name == 'ma_crossover':
            if params.get('short_ma', 0) >= params.get('long_ma', 0):
                return -1000.0
        
        try:
            strategy = StrategyFactory.create_strategy(self.strategy_name, params)
        except Exception as e:
            return -1000.0
        
        tp = params.get('take_profit', 2.0)
        sl = params.get('stop_loss', 1.0)
        trades, _ = self.backtest(strategy, train_df, tp, sl)
        
        if len(trades) < 5:
            return -1000.0
        
        returns = [t['pnl'] for t in trades]
        if len(returns) < 2 or np.std(returns) == 0:
            return -1000.0
        
        sharpe = np.mean(returns) / np.std(returns)
        if len(trades) > 100:
            sharpe *= 0.9
        return sharpe
    
    def optimize(self, days: int = 90, n_trials: int = 100, trigger_reason: str = None) -> Optional[Dict[str, Any]]:
        logger.info(f"🚀 Запуск оптимизации для {self.symbol} (стратегия: {self.strategy_name})")
        
        history_id = db.execute_insert("""
            INSERT INTO optimization_history (bot_id, symbol, trigger_reason, trials_count, optimization_start)
            VALUES (%s, %s, %s, %s, NOW())
        """, (self.bot_id, self.symbol, trigger_reason, n_trials))
        
        df = self.get_historical_data(days)
        if df.empty:
            return None
        
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        logger.info(f"📊 Train: {len(train_df)} свечей, Test: {len(test_df)} свечей")
        
        study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(lambda trial: self.objective(trial, train_df), n_trials=n_trials, show_progress_bar=True)
        
        best_trial = study.best_trial
        best_params = best_trial.params
        train_sharpe = best_trial.value
        logger.info(f"✅ Train Sharpe: {train_sharpe:.4f}, параметры: {best_params}")
        
        # Валидация на test
        try:
            test_strategy = StrategyFactory.create_strategy(self.strategy_name, best_params)
            tp = best_params.get('take_profit', 2.0)
            sl = best_params.get('stop_loss', 1.0)
            test_trades, _ = self.backtest(test_strategy, test_df, tp, sl)
            if len(test_trades) >= 5:
                test_returns = [t['pnl'] for t in test_trades]
                test_sharpe = np.mean(test_returns) / np.std(test_returns) if np.std(test_returns) > 0 else 0
            else:
                test_sharpe = None
            if test_sharpe is None or test_sharpe <= 0:
                overfit_ratio = None
            else:
                overfit_ratio = train_sharpe / test_sharpe
        except Exception as e:
            test_sharpe = -1.0
            overfit_ratio = 999.0
        
        db.execute_update("""
            UPDATE optimization_history 
            SET optimization_end = NOW(), best_sharpe = %s, test_sharpe = %s,
                overfit_ratio = %s, best_params = %s, old_params = %s
            WHERE id = %s
        """, (train_sharpe, test_sharpe, overfit_ratio, json.dumps(best_params), 
              json.dumps(self.current_params), history_id))
        
        return {
            'best_params': best_params,
            'train_sharpe': train_sharpe,
            'test_sharpe': test_sharpe,
            'overfit_ratio': overfit_ratio,
            'history_id': history_id,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bot_id', type=int, required=True)
    parser.add_argument('--symbol', type=str, required=True)
    parser.add_argument('--strategy', type=str, default=None)
    parser.add_argument('--days', type=int, default=90)
    parser.add_argument('--trials', type=int, default=100)
    parser.add_argument('--trigger', type=str, default=None)
    args = parser.parse_args()
    
    optimizer = ParamOptimizer(args.bot_id, args.symbol, args.strategy)
    result = optimizer.optimize(days=args.days, n_trials=args.trials, trigger_reason=args.trigger)
    if result:
        print(json.dumps(result, indent=2))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
