"""
Risk Manager - управление множителем риска и восстановлением после Halt.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db
from src.optimizer.triggers import check_triggers
from src.optimizer.parameter_updater import set_risk_multiplier, set_halted, is_halted, get_risk_multiplier
from src.regime.detector import MarketRegimeDetector

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Управление риском:
    - Получение множителя риска на основе trigger_level
    - Условия возобновления торговли после Halt
    - Снижение риска при срабатывании триггеров
    """
    
    def __init__(self, bot_id: int, symbol: str, exchange_client):
        self.bot_id = bot_id
        self.symbol = symbol
        self.exchange = exchange_client
        self.regime_detector = MarketRegimeDetector(exchange_client)
    
    def get_risk_multiplier(self) -> float:
        """
        Возвращает текущий множитель риска (0.0 - 1.0).
        
        Returns:
            multiplier: 1.0 = норма, 0.5 = половинный риск, 0.0 = остановка
        """
        # Получаем уровень триггера
        level, reasons, metadata = check_triggers(self.bot_id, self.symbol, self.exchange)
        
        multiplier = 1.0
        
        if level == 1:
            # Warning: снижаем риск до 50%
            multiplier = 0.5
            logger.info(f"⚠️ {self.symbol}: уровень 1 (Warning), риск снижен до {multiplier}")
            
            # Обновляем в БД
            set_risk_multiplier(self.bot_id, self.symbol, multiplier, f"Warning: {', '.join(reasons[:2])}")
            
        elif level >= 2:
            # Halt: полная остановка
            multiplier = 0.0
            logger.error(f"🔴 {self.symbol}: уровень 2 (Halt), торговля остановлена")
            
            set_risk_multiplier(self.bot_id, self.symbol, multiplier, f"Halt: {', '.join(reasons[:2])}")
            set_halted(self.bot_id, self.symbol, True)
        
        else:
            # Нормальный режим, проверяем не было ли остановки
            if is_halted(self.bot_id, self.symbol):
                # Проверяем условия возобновления
                if self.resume_conditions_met():
                    logger.info(f"🟢 {self.symbol}: условия возобновления выполнены")
                    multiplier = 0.5  # Начинаем с половинного риска
                    set_risk_multiplier(self.bot_id, self.symbol, multiplier, "Восстановление после Halt")
                    set_halted(self.bot_id, self.symbol, False)
                else:
                    multiplier = 0.0
            else:
                # Нормальный режим, убеждаемся что множитель = 1.0
                current = get_risk_multiplier(self.bot_id, self.symbol)
                if current != 1.0:
                    set_risk_multiplier(self.bot_id, self.symbol, 1.0, "Нормальный режим")
        
        return multiplier
    
    def resume_conditions_met(self) -> bool:
        """
        Условия возобновления торговли после Halt:
        1. Прошло не менее 24 часов с момента Halt
        2. Текущая просадка < 5% (восстановление от пика)
        3. Текущий режим рынка не HIGH_VOLATILITY
        4. Sharpe за последние 7 дней > 0.5
        """
        # 1. Проверяем время с момента остановки
        halted_info = db.execute_query("""
            SELECT halted_at FROM bot_symbols
            WHERE bot_id = %s AND symbol = %s
        """, (self.bot_id, self.symbol))
        
        if not halted_info or not halted_info[0].get('halted_at'):
            return True
        
        halted_at = halted_info[0]['halted_at']
        if isinstance(halted_at, str):
            halted_at = datetime.fromisoformat(halted_at.replace(' ', 'T'))
        
        hours_since_halt = (datetime.now() - halted_at).total_seconds() / 3600
        
        if hours_since_halt < 24:
            logger.info(f"⏳ {self.symbol}: прошло только {hours_since_halt:.1f}ч с момента Halt (нужно 24ч)")
            return False
        
        # 2. Проверяем текущую просадку
        from src.optimizer.metrics import calculate_current_drawdown
        current_dd = calculate_current_drawdown(self.bot_id, self.symbol, self.exchange)
        
        if current_dd is not None and current_dd >= 5.0:
            logger.info(f"📉 {self.symbol}: текущая просадка {current_dd:.2f}% >= 5%")
            return False
        
        # 3. Проверяем режим рынка
        regime, _ = self.regime_detector.detect(self.symbol)
        if regime.value == 'high_volatility':
            logger.info(f"🌊 {self.symbol}: режим HIGH_VOLATILITY, торговля запрещена")
            return False
        
        # 4. Проверяем Sharpe за последние 7 дней
        metrics = db.execute_query("""
            SELECT sharpe_ratio FROM bot_performance_metrics
            WHERE bot_id = %s AND symbol = %s
            ORDER BY metric_date DESC
            LIMIT 1
        """, (self.bot_id, self.symbol))
        
        if metrics and metrics[0].get('sharpe_ratio'):
            sharpe = float(metrics[0]['sharpe_ratio'])
            if sharpe <= 0.5:
                logger.info(f"📊 {self.symbol}: Sharpe {sharpe:.2f} <= 0.5")
                return False
        
        logger.info(f"✅ {self.symbol}: все условия возобновления выполнены")
        return True
    
    def should_trade(self) -> Tuple[bool, str]:
        """
        Проверить, можно ли торговать.
        
        Returns:
            (can_trade, reason)
        """
        multiplier = self.get_risk_multiplier()
        
        if multiplier <= 0:
            return False, "Торговля остановлена (risk_multiplier = 0)"
        
        # Проверяем режим рынка
        regime, meta = self.regime_detector.detect(self.symbol)
        
        if regime.value == 'high_volatility':
            return False, f"Высокая волатильность (ATR ratio = {meta.get('atr_ratio', '?')})"
        
        return True, "OK"


class VolatilityGuard:
    """
    Volatility Guard - снижение риска при высокой волатильности.
    """
    
    def __init__(self, exchange_client):
        self.exchange = exchange_client
    
    def check(self, symbol: str) -> Tuple[bool, float]:
        """
        Проверить волатильность и вернуть множитель снижения риска.
        
        Args:
            symbol: Торговая пара
        
        Returns:
            (activated, reduction_factor)
            reduction_factor: 1.0 (норма), 0.5 (средняя), 0.0 (экстремальная)
        """
        try:
            # Загружаем свечи для расчёта ATR
            df = self.exchange.get_klines(symbol, '1h', 100)
            
            if df is None or df.empty or len(df) < 50:
                return False, 1.0
            
            import pandas_ta as ta
            import pandas as pd
            
            # Рассчитываем ATR
            atr = ta.atr(
                high=pd.Series(df['high'].values),
                low=pd.Series(df['low'].values),
                close=pd.Series(df['close'].values),
                length=14
            )
            
            if atr is None or atr.empty:
                return False, 1.0
            
            current_atr = float(atr.iloc[-1])
            avg_atr = float(atr.iloc[-50:].mean()) if len(atr) >= 50 else current_atr
            
            if avg_atr <= 0:
                return False, 1.0
            
            atr_ratio = current_atr / avg_atr
            
            # Определяем множитель
            if atr_ratio > 3.0:
                logger.warning(f"⚠️ {symbol}: экстремальная волатильность (ATR ratio = {atr_ratio:.2f})")
                return True, 0.0  # Остановка
            elif atr_ratio > 2.0:
                logger.info(f"📊 {symbol}: высокая волатильность (ATR ratio = {atr_ratio:.2f})")
                return True, 0.5  # Снижение на 50%
            
            return False, 1.0
            
        except Exception as e:
            logger.error(f"Ошибка в VolatilityGuard для {symbol}: {e}")
            return False, 1.0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.trading.exchange_client import ExchangeClient
    
    exchange = ExchangeClient('bybit')
    
    # Тест RiskManager
    for symbol in ['ETHUSDT', 'BTCUSDT']:
        bot = db.execute_query("SELECT id FROM bots WHERE name = %s", (symbol,))
        if bot:
            rm = RiskManager(bot[0]['id'], symbol, exchange)
            mult = rm.get_risk_multiplier()
            can, reason = rm.should_trade()
            print(f"\n{symbol}: multiplier={mult}, can_trade={can}, reason={reason}")
    
    # Тест VolatilityGuard
    vg = VolatilityGuard(exchange)
    for symbol in ['ETHUSDT', 'BTCUSDT']:
        activated, factor = vg.check(symbol)
        print(f"{symbol}: volatility_guard={activated}, factor={factor}")
