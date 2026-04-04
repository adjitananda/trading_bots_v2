#!/usr/bin/env python3
"""
Базовый класс для торговых ботов.
Поддерживает multi-coin режим (один бот → много символов).
С поддержкой reload_flag для динамического обновления параметров.
"""

import time
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import db
from src.trading.exchange_client import ExchangeClient
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.strategies.legacy import StrategyFactory
from src.telegram.notifier import notifier
from src.utils.time_utils import now_local, format_datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Базовый класс для всех торговых ботов"""
    
    def __init__(self, bot_name: str, config: Dict[str, Any]):
        """
        Инициализация бота.
        
        Args:
            bot_name: Имя бота (например 'ETHUSDT' или 'eth_bot')
            config: Конфигурация бота
        """
        self.bot_name = bot_name
        self.config = config
        
        # Определяем bot_id из БД
        self.bot_id = self._get_bot_id()
        if not self.bot_id:
            raise ValueError(f"Бот {bot_name} не найден в БД")
        
        # Инициализация биржи
        exchange_name = config.get('exchange', 'bybit')
        self.exchange = ExchangeClient(exchange_name)
        
        # Менеджеры с передачей exchange_client
        self.order_manager = OrderManager(self.exchange, self.bot_id, self.bot_name)
        self.position_tracker = PositionTracker(self.exchange, self.bot_id, self.bot_name)
        
        # Multi-coin: список символов и их параметров
        self.symbols: List[str] = []
        self.symbol_params: Dict[str, Dict] = {}
        self.strategies: Dict[str, Any] = {}
        
        # Загружаем символы из БД
        self._load_symbols()
        
        # Интервалы (в секундах)
        self.intervals = config.get('intervals', {
            'main_loop': 5,      # 5 секунд
            'status_log': 300,    # 5 минут
            'risk_check': 60,     # 1 минута
            'snapshot': 3600      # 1 час
        })
        
        # Состояние бота
        self.running = True
        self.last_status_log = 0
        self.last_risk_check = 0
        self.last_snapshot = 0
        
        # Статистика
        self.stats = {
            'start_time': now_local(),
            'total_signals': 0,
            'total_trades': 0,
            'last_error': None
        }
        
        logger.info(f"🤖 Бот {bot_name} (id={self.bot_id}) инициализирован")
        logger.info(f"📊 Управляет символами: {self.symbols}")
    
    def _get_bot_id(self) -> Optional[int]:
        """Получить bot_id из БД по имени"""
        result = db.execute_query(
            "SELECT id FROM bots WHERE name = %s",
            (self.bot_name,)
        )
        if result:
            return result[0]['id']
        return None
    
    def _load_symbols(self):
        """
        Загрузить список символов из таблицы bot_symbols.
        Для обратной совместимости: если в bot_symbols нет записей,
        используем символ из конфига (старый режим).
        """
        # Пытаемся загрузить из bot_symbols
        symbols_data = db.execute_query("""
            SELECT symbol, strategy_params, risk_params, is_active
            FROM bot_symbols
            WHERE bot_id = %s AND is_active = 1
        """, (self.bot_id,))
        
        if symbols_data:
            # Multi-coin режим
            new_symbols = []
            for row in symbols_data:
                symbol = row['symbol']
                new_symbols.append(symbol)
                
                # Параметры стратегии
                strategy_params = row['strategy_params']
                if isinstance(strategy_params, str):
                    import json
                    strategy_params = json.loads(strategy_params)
                
                # Риск-параметры
                risk_params = row['risk_params']
                if isinstance(risk_params, str):
                    import json
                    risk_params = json.loads(risk_params)
                elif risk_params is None:
                    risk_params = {}
                
                self.symbol_params[symbol] = {
                    'strategy_params': strategy_params,
                    'risk_params': risk_params
                }
                
                # Создаём стратегию
                strategy_name = self.config.get('strategy', 'ma_crossover')
                if symbol not in self.strategies:
                    try:
                        self.strategies[symbol] = StrategyFactory.create_strategy(
                            strategy_name,
                            strategy_params
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка создания стратегии для {symbol}: {e}")
                        self.strategies[symbol] = None
            
            self.symbols = new_symbols
            logger.info(f"📊 Загружено {len(self.symbols)} символов из bot_symbols")
        else:
            # Старый режим: один символ из конфига
            symbol = self.config.get('symbol')
            if symbol:
                self.symbols = [symbol]
                
                # Параметры из конфига
                strategy_params = self.config.get('strategy_params', {})
                risk_params = self.config.get('risk_params', {})
                
                self.symbol_params[symbol] = {
                    'strategy_params': strategy_params,
                    'risk_params': risk_params
                }
                
                strategy_name = self.config.get('strategy', 'ma_crossover')
                try:
                    self.strategies[symbol] = StrategyFactory.create_strategy(
                        strategy_name,
                        strategy_params
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка создания стратегии для {symbol}: {e}")
                    self.strategies[symbol] = None
                
                logger.info(f"📊 Legacy режим: один символ {symbol}")
            else:
                logger.error("❌ Нет символов для торговли")
                self.symbols = []
    
    def reload_params(self):
        """Перезагрузить параметры из БД без перезапуска бота."""
        logger.info("🔄 Перезагрузка параметров...")
        old_symbols = self.symbols.copy()
        self.symbols = []
        self.symbol_params = {}
        self._load_symbols()
        
        added = set(self.symbols) - set(old_symbols)
        removed = set(old_symbols) - set(self.symbols)
        if added:
            logger.info(f"➕ Добавлены символы: {added}")
        if removed:
            logger.info(f"➖ Удалены символы: {removed}")
        logger.info(f"✅ Перезагрузка завершена. Теперь управляет: {self.symbols}")
    
    def get_signal(self, symbol: str) -> str:
        """Получить торговый сигнал для конкретного символа."""
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
            logger.error(f"❌ Ошибка получения сигнала для {symbol}: {e}")
            return 'none'
    
    def check_risk_limits(self, symbol: str) -> bool:
        """Проверить риск-лимиты для символа."""
        risk_params = self.symbol_params.get(symbol, {}).get('risk_params', {})
        max_positions = risk_params.get('max_positions', self.config.get('max_positions', 1))
        open_positions = len(self.position_tracker.get_current_positions(symbol))
        if open_positions >= max_positions:
            logger.debug(f"⚠️ {symbol}: лимит позиций ({open_positions}/{max_positions})")
            return False
        
        max_daily_loss = risk_params.get('max_daily_loss', self.config.get('max_daily_loss'))
        if max_daily_loss:
            today_pnl = self.position_tracker.get_daily_pnl(symbol) if hasattr(self.position_tracker, 'get_daily_pnl') else 0
            if today_pnl <= -max_daily_loss:
                logger.warning(f"⚠️ {symbol}: дневной лимит убытка ({today_pnl:.2f})")
                return False
        return True
    
    def execute_signal(self, symbol: str, signal: str):
        """Выполнить торговый сигнал."""
        if signal == 'up':
            if not self.check_risk_limits(symbol):
                return
            current_price = self.exchange.get_current_price(symbol)
            if not current_price:
                logger.error(f"❌ Не удалось получить цену для {symbol}")
                return
            
            qty = self.config.get('qty', 10)
            tp_percent = self.config.get('tp', 0.05)
            sl_percent = self.config.get('sl', 0.02)
            
            order = self.order_manager.place_order(
                symbol=symbol, side='BUY', quantity=qty, order_type='market',
                tp_price=current_price * (1 + tp_percent),
                sl_price=current_price * (1 - sl_percent)
            )
            if order and order.get('success'):
                logger.info(f"✅ {symbol}: открыта позиция BUY по {current_price}")
                self.stats['total_trades'] += 1
        elif signal == 'down':
            positions = self.position_tracker.get_current_positions(symbol)
            for pos in positions:
                self.order_manager.close_position(pos['trade_id'])
                logger.info(f"🔒 {symbol}: закрыта позиция")
        self.stats['total_signals'] += 1
    
    def run_cycle(self):
        """Один цикл торговли"""
        for symbol in self.symbols:
            try:
                signal = self.get_signal(symbol)
                if signal != 'none':
                    self.execute_signal(symbol, signal)
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле для {symbol}: {e}")
                self.stats['last_error'] = str(e)
    
    def log_status(self):
        """Логирование статуса бота"""
        positions = self.position_tracker.get_current_positions()
        total_pnl = sum(p.get('unrealised_pnl', 0) for p in positions)
        logger.info(f"📊 Статус {self.bot_name}: символов={len(self.symbols)}, позиций={len(positions)}, PnL={total_pnl:.2f}")
    
    def take_snapshot(self):
        """Сохранение снимка состояния в БД"""
        try:
            positions = self.position_tracker.get_current_positions()
            total_pnl = sum(p.get('unrealised_pnl', 0) for p in positions)
            balance = self.exchange.get_balance()
            db.execute_update("""
                INSERT INTO snapshots (bot_id, exchange_id, timestamp, balance, total_pnl, open_positions_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (self.bot_id, self.exchange.exchange_id, now_local(), balance, total_pnl, len(positions)))
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения снимка: {e}")
    
    # ==================== RELOAD_FLAG ПРОВЕРКА ====================
    
    def check_reload_flag(self, symbol: str) -> bool:
        """Проверить, нужно ли перезагрузить параметры для символа."""
        result = db.execute_query(
            "SELECT reload_flag FROM bot_symbols WHERE bot_id = %s AND symbol = %s",
            (self.bot_id, symbol)
        )
        return result and result[0].get('reload_flag', 0) == 1
    
    def reload_symbol_params(self, symbol: str):
        """Перезагрузить параметры для конкретного символа из БД."""
        result = db.execute_query(
            "SELECT strategy_params, risk_params FROM bot_symbols WHERE bot_id = %s AND symbol = %s",
            (self.bot_id, symbol)
        )
        if result:
            row = result[0]
            strategy_params = row['strategy_params']
            if isinstance(strategy_params, str):
                import json
                strategy_params = json.loads(strategy_params)
            
            risk_params = row['risk_params']
            if isinstance(risk_params, str):
                import json
                risk_params = json.loads(risk_params)
            elif risk_params is None:
                risk_params = {}
            
            self.symbol_params[symbol] = {'strategy_params': strategy_params, 'risk_params': risk_params}
            
            if symbol in self.strategies and self.strategies[symbol]:
                try:
                    self.strategies[symbol].params = strategy_params
                    logger.info(f"✅ Стратегия для {symbol} обновлена")
                except Exception as e:
                    logger.error(f"❌ Ошибка обновления стратегии: {e}")
            
            db.execute_update(
                "UPDATE bot_symbols SET reload_flag = 0 WHERE bot_id = %s AND symbol = %s",
                (self.bot_id, symbol)
            )
            logger.info(f"✅ Параметры для {symbol} перезагружены")
            try:
                notifier.send_message(f"🔄 Параметры {symbol} обновлены: {strategy_params}")
            except:
                pass
    
    def get_risk_multiplier(self, symbol: str) -> float:
        """Получить текущий множитель риска для символа."""
        result = db.execute_query(
            "SELECT risk_multiplier FROM bot_symbols WHERE bot_id = %s AND symbol = %s",
            (self.bot_id, symbol)
        )
        if result:
            return float(result[0].get('risk_multiplier', 1.0))
        return 1.0
    
    # ==================== ОСНОВНОЙ ЦИКЛ ====================
    
    def run(self):
        """Основной цикл бота с поддержкой reload_flag и risk_multiplier"""
        logger.info(f"🚀 Запуск бота {self.bot_name}")
        notifier.send_bot_startup(self.bot_name, self.config, self.config.get('strategy', 'unknown'))
        db.execute_update("UPDATE bots SET status = 'active', started_at = %s WHERE id = %s", (now_local(), self.bot_id))
        
        try:
            while self.running:
                current_time = time.time()
                
                for symbol in self.symbols:
                    try:
                        # 1. Проверка reload_flag
                        if self.check_reload_flag(symbol):
                            self.reload_symbol_params(symbol)
                        
                        # 2. Проверка risk_multiplier
                        if self.get_risk_multiplier(symbol) <= 0:
                            logger.debug(f"⏸️ Торговля для {symbol} остановлена (risk_multiplier=0)")
                            continue
                        
                        # 3. Сигнал и исполнение
                        signal = self.get_signal(symbol)
                        if signal != 'none':
                            self.execute_signal(symbol, signal)
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка для {symbol}: {e}")
                
                if current_time - self.last_status_log >= self.intervals.get('status_log', 300):
                    self.log_status()
                    self.last_status_log = current_time
                if current_time - self.last_risk_check >= self.intervals.get('risk_check', 60):
                    for symbol in self.symbols:
                        self.check_risk_limits(symbol)
                    self.last_risk_check = current_time
                if current_time - self.last_snapshot >= self.intervals.get('snapshot', 3600):
                    self.take_snapshot()
                    self.last_snapshot = current_time
                
                time.sleep(self.intervals.get('main_loop', 5))
                
        except KeyboardInterrupt:
            logger.info(f"🛑 Остановка {self.bot_name}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            notifier.send_bot_error(self.bot_name, str(e))
        finally:
            self.stop()
    
    def stop(self):
        """Остановка бота"""
        self.running = False
        logger.info(f"🛑 Бот {self.bot_name} остановлен")
        db.execute_update("UPDATE bots SET status = 'stopped', stopped_at = %s WHERE id = %s", (now_local(), self.bot_id))
        notifier.send_bot_stop(self.bot_name)
