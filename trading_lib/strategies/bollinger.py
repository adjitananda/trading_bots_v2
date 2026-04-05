"""
Bollinger Bands стратегия.
Сигнал BUY когда цена касается нижней полосы и отскакивает.
Сигнал SELL когда цена касается верхней полосы и отскакивает.
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional

from trading_lib.strategies.base import BaseStrategy


class BollingerStrategy(BaseStrategy):
    """Стратегия на основе полос Боллинджера"""
    
    def __init__(self, params: dict = None):
        super().__init__(params)
        self.period = self.params.get('bb_period', 20)
        self.std = self.params.get('bb_std', 2.0)
        self.tp_percent = self.params.get('take_profit', 3.0)
        self.sl_percent = self.params.get('stop_loss', 1.5)
    
    def get_signal(self, df: pd.DataFrame) -> str:
        """
        Возвращает торговый сигнал.
        
        Args:
            df: DataFrame с колонками ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            'up' - сигнал на покупку (цена отскочила от нижней полосы)
            'down' - сигнал на продажу (цена отскочила от верхней полосы)
            'none' - нет сигнала
        """
        if df is None or df.empty or len(df) < self.period:
            return 'none'
        
        df_copy = df.copy()
        
        # Рассчитываем Bollinger Bands
        bbands = ta.bbands(df_copy['close'], length=self.period, std=self.std)
        
        if bbands is None or bbands.empty:
            return 'none'
        
        df_copy['BB_LOWER'] = bbands[f'BBL_{self.period}_{self.std}.0']
        df_copy['BB_UPPER'] = bbands[f'BBU_{self.period}_{self.std}.0']
        df_copy['BB_MIDDLE'] = bbands[f'BBM_{self.period}_{self.std}.0']
        
        if len(df_copy) < 2:
            return 'none'
        
        price_current = float(df_copy['close'].iloc[-1])
        price_prev = float(df_copy['close'].iloc[-2])
        bb_lower_current = float(df_copy['BB_LOWER'].iloc[-1])
        bb_upper_current = float(df_copy['BB_UPPER'].iloc[-1])
        
        # Сигнал на покупку: цена касается нижней полосы и отскакивает
        if price_prev <= bb_lower_current and price_current > bb_lower_current:
            return 'up'
        
        # Сигнал на продажу: цена касается верхней полосы и отскакивает
        if price_prev >= bb_upper_current and price_current < bb_upper_current:
            return 'down'
        
        return 'none'
    
    def get_tp_sl(self, entry_price: float, side: str) -> tuple:
        """
        Рассчитать цены тейк-профита и стоп-лосса.
        
        Args:
            entry_price: Цена входа
            side: 'BUY' или 'SELL'
        
        Returns:
            (take_profit_price, stop_loss_price)
        """
        if side.upper() == 'BUY':
            tp = entry_price * (1 + self.tp_percent / 100)
            sl = entry_price * (1 - self.sl_percent / 100)
        else:
            tp = entry_price * (1 - self.tp_percent / 100)
            sl = entry_price * (1 + self.sl_percent / 100)
        
        return tp, sl
    
    def get_info(self) -> dict:
        """Информация о стратегии"""
        return {
            'name': 'bollinger',
            'params': {
                'bb_period': self.period,
                'bb_std': self.std,
                'take_profit': self.tp_percent,
                'stop_loss': self.sl_percent
            }
        }
