#!/usr/bin/env python3
"""
CRYPTO_BOT - торговля криптовалютами на Bybit
Поддерживает multi-coin через таблицу bot_symbols
"""

import sys
import time
import signal
import logging
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from trading_lib.utils.database import Database
from trading_lib.exchanges import BybitAdapter
from trading_lib.strategies import get_strategy
from trading_lib.telegram.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CryptoBot:
    """Крипто-бот для торговли на Bybit"""
    
    def __init__(self):
        self.bot_id = 7  # CRYPTO_BOT
        self.bot_name = "CRYPTO_BOT"
        self.db = Database()
        self.exchange = BybitAdapter()
        self.notifier = TelegramNotifier()
        self.running = True
        self.symbols = []
        self.strategies = {}
        self.config = {
            'strategy': 'ma_crossover',
            'timeframe': 5,
            'intervals': {'main_loop': 5}
        }
        self.load_symbols()
        
        logger.info(f"🤖 {self.bot_name} инициализирован")
        logger.info(f"📊 Управляет символами: {self.symbols}")
    
    def load_symbols(self):
        """Загрузить активные символы из bot_symbols"""
        result = self.db.execute_query("""
            SELECT symbol, strategy_params, risk_params
            FROM bot_symbols
            WHERE bot_id = %s AND is_active = 1
        """, (self.bot_id,))
        
        self.symbols = []
        self.strategies = {}
        
        for row in result:
            symbol = row['symbol']
            self.symbols.append(symbol)
            
            params = row['strategy_params']
            if isinstance(params, str):
                params = json.loads(params)
            
            strategy_name = params.get('strategy', 'ma_crossover')
            try:
                self.strategies[symbol] = get_strategy(strategy_name, params)
                logger.info(f"  ✅ {symbol}: стратегия {strategy_name} загружена")
            except Exception as e:
                logger.error(f"  ❌ {symbol}: ошибка загрузки стратегии - {e}")
                self.strategies[symbol] = None
    
    def get_signal(self, symbol: str) -> str:
        """Получить торговый сигнал"""
        strategy = self.strategies.get(symbol)
        if not strategy:
            return 'none'
        
        try:
            interval = f"{self.config.get('timeframe', 5)}m"
            df = self.exchange.get_klines(symbol, interval, limit=100)
            if df is None or df.empty:
                return 'none'
            return strategy.get_signal(df)
        except Exception as e:
            logger.error(f"Ошибка получения сигнала для {symbol}: {e}")
            return 'none'
    
    def run_cycle(self):
        """Один цикл торговли"""
        for symbol in self.symbols:
            try:
                signal = self.get_signal(symbol)
                if signal != 'none':
                    logger.info(f"📡 {symbol}: сигнал {signal}")
            except Exception as e:
                logger.error(f"Ошибка в цикле для {symbol}: {e}")
    
    def run(self):
        """Основной цикл бота"""
        logger.info(f"🚀 Запуск {self.bot_name}")
        self.notifier.send_bot_startup(self.bot_name, self.config, self.config.get('strategy', 'ma_crossover'))
        
        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())
        
        while self.running:
            try:
                self.run_cycle()
                time.sleep(5)
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
                time.sleep(10)
        
        logger.info(f"🛑 {self.bot_name} остановлен")
        self.notifier.send_bot_stop(self.bot_name)
    
    def stop(self):
        """Остановка бота"""
        self.running = False


if __name__ == "__main__":
    bot = CryptoBot()
    bot.run()
