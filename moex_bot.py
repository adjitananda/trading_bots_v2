#!/usr/bin/env python3
"""
MOEX_BOT - торговля фьючерсами на Московской бирже
Поддерживает multi-coin через таблицу bot_symbols
"""

import sys
import time
import signal
import logging
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from trading_lib.utils.database import Database
from trading_lib.exchanges import MoexAdapter
from trading_lib.exchanges.moex_utils import is_expiring_soon, get_next_contract
from trading_lib.strategies import get_strategy
from trading_lib.telegram.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MoexBot:
    """Бот для торговли фьючерсами на Мосбирже"""
    
    def __init__(self):
        self.bot_id = None
        self.bot_name = "MOEX_BOT"
        self.db = Database()
        
        # Получаем bot_id
        result = self.db.execute_query("SELECT id FROM bots WHERE name = %s", (self.bot_name,))
        if result:
            self.bot_id = result[0]['id']
        else:
            exchange_id = self.db.execute_query("SELECT id FROM exchanges WHERE name = 'moex'")[0]['id']
            self.db.execute_update("""
                INSERT INTO bots (name, exchange_id, strategy_type, is_active, status)
                VALUES (%s, %s, 'ma_crossover', 1, 'active')
            """, (self.bot_name, exchange_id))
            self.bot_id = self.db.execute_query("SELECT LAST_INSERT_ID() as id")[0]['id']
            logger.info(f"✅ Создана запись для {self.bot_name} (id={self.bot_id})")
        
        self.exchange = MoexAdapter()
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
    
    def is_trading_time(self) -> bool:
        """Проверить, можно ли торговать"""
        return self.exchange.is_trading_time()
    
    def check_expiry(self, symbol: str) -> bool:
        """Проверить экспирацию фьючерса"""
        if is_expiring_soon(symbol, days=3):
            next_contract = get_next_contract(symbol[:-3] if len(symbol) > 3 else symbol)
            logger.warning(f"⚠️ {symbol} истекает через 3 дня! Рекомендуется перейти на {next_contract}")
            return True
        return False
    
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
        if not self.is_trading_time():
            return
        
        for symbol in self.symbols:
            try:
                self.check_expiry(symbol)
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
    bot = MoexBot()
    bot.run()
