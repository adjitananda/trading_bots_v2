"""
Определение текущего режима рынка.
"""

import logging
import pandas as pd
import pandas_ta as ta
from typing import Tuple, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.regime.regimes import MarketRegime

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """Детектор режима рынка"""
    
    def __init__(self, exchange_client):
        self.exchange = exchange_client
    
    def detect(self, symbol: str, lookback_days: int = 100) -> Tuple[MarketRegime, Dict[str, Any]]:
        """Определить текущий режим рынка"""
        metadata = {'adx': None, 'atr_ratio': None, 'ema200_direction': None, 'price': None}
        
        try:
            df = self.exchange.get_klines(symbol, '1d', lookback_days + 100)
            if df is None or df.empty or len(df) < 50:
                return MarketRegime.RANGING, metadata
            
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            
            # ADX
            adx_series = ta.adx(high=pd.Series(high), low=pd.Series(low), 
                                close=pd.Series(close), length=14)
            if adx_series is not None and 'ADX_14' in adx_series.columns:
                adx = float(adx_series['ADX_14'].iloc[-1])
                metadata['adx'] = round(adx, 2)
            else:
                adx = 20
            
            # ATR ratio
            atr_series = ta.atr(high=pd.Series(high), low=pd.Series(low), 
                                close=pd.Series(close), length=14)
            if atr_series is not None and not atr_series.empty:
                current_atr = float(atr_series.iloc[-1])
                avg_atr = float(atr_series.iloc[-50:].mean()) if len(atr_series) >= 50 else current_atr
                atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
                metadata['atr_ratio'] = round(atr_ratio, 2)
            else:
                atr_ratio = 1.0
            
            # EMA200
            ema200 = ta.ema(pd.Series(close), length=200)
            if ema200 is not None and not ema200.empty:
                ema200_value = float(ema200.iloc[-1])
            else:
                ema200_value = close[-1]
            
            current_price = float(close[-1])
            metadata['price'] = round(current_price, 2)
            metadata['ema200_direction'] = 'above' if current_price > ema200_value else 'below'
            
            # Приоритет 1: Высокая волатильность
            if atr_ratio > 2.0:
                return MarketRegime.HIGH_VOLATILITY, metadata
            
            # Приоритет 2: Трендовые режимы
            if adx > 25:
                if current_price > ema200_value:
                    return MarketRegime.STRONG_UPTREND, metadata
                else:
                    return MarketRegime.STRONG_DOWNTREND, metadata
            
            # Приоритет 3: Флэт
            return MarketRegime.RANGING, metadata
            
        except Exception as e:
            logger.error(f"Ошибка определения режима для {symbol}: {e}")
            return MarketRegime.RANGING, metadata
    
    def is_trading_allowed(self, symbol: str) -> bool:
        """Проверить, разрешена ли торговля"""
        regime, _ = self.detect(symbol)
        return regime != MarketRegime.HIGH_VOLATILITY
