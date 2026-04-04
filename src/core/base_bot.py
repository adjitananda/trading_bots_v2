#!/usr/bin/env python3
"""
Базовый класс для торговых ботов.
Поддерживает multi-coin режим (один бот → много символов).
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
        
        # Инициализация компонентов
        self.exchange = ExchangeClient()
        self.order_manager = OrderManager(self.bot_id, self.bot_name)
        self.position_tracker = PositionTracker(self.bot_id)
        
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
            for row in symbols_data:
                symbol = row['symbol']
                self.symbols.append(symbol)
                
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
                try:
                    self.strategies[symbol] = StrategyFactory.create_strategy(
                        strategy_name,
                        strategy_params
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка создания стратегии для {symbol}: {e}")
                    self.strategies[symbol] = None
            
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
        """
        Перезагрузить параметры из БД без перезапуска бота.
        Полезно при добавлении/удалении символов.
        """
        logger.info("🔄 Перезагрузка параметров...")
        
        # Сохраняем старые символы
        old_symbols = self.symbols.copy()
        
        # Очищаем текущие данные
        self.symbols = []
        self.symbol_params = {}
        self.strategies = {}
        
        # Загружаем заново
        self._load_symbols()
        
        # Логируем изменения
        added = set(self.symbols) - set(old_symbols)
        removed = set(old_symbols) - set(self.symbols)
        
        if added:
            logger.info(f"➕ Добавлены символы: {added}")
        if removed:
            logger.info(f"➖ Удалены символы: {removed}")
        
        logger.info(f"✅ Перезагрузка завершена. Теперь управляет: {self.symbols}")
    
    def get_signal(self, symbol: str) -> str:
        """
        Получить торговый сигнал для конкретного символа.
        
        Returns:
            'up' - сигнал на покупку
            'down' - сигнал на продажу
            'none' - нет сигнала
        """
        strategy = self.strategies.get(symbol)
        if not strategy:
            return 'none'
        
        try:
            # Получаем свечи
            interval = f"{self.config.get('timeframe', 5)}m"
            df = self.exchange.get_klines(symbol, interval, limit=100)
            
            if df is None or df.empty:
                return 'none'
            
            # Получаем сигнал от стратегии
            signal = strategy.get_signal(df)
            return signal
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сигнала для {symbol}: {e}")
            return 'none'
    
    def check_risk_limits(self, symbol: str) -> bool:
        """
        Проверить риск-лимиты для символа.
        
        Returns:
            True если можно торговать, False если лимиты превышены
        """
        risk_params = self.symbol_params.get(symbol, {}).get('risk_params', {})
        
        # Максимальное количество позиций
        max_positions = risk_params.get('max_positions', self.config.get('max_positions', 1))
        open_positions = len(self.position_tracker.get_open_positions(symbol))
        
        if open_positions >= max_positions:
            logger.debug(f"⚠️ {symbol}: достигнут лимит позиций ({open_positions}/{max_positions})")
            return False
        
        # Максимальный дневной убыток
        max_daily_loss = risk_params.get('max_daily_loss', self.config.get('max_daily_loss'))
        if max_daily_loss:
            today_pnl = self.position_tracker.get_today_pnl(symbol)
            if today_pnl <= -max_daily_loss:
                logger.warning(f"⚠️ {symbol}: превышен дневной лимит убытка ({today_pnl:.2f} <= -{max_daily_loss})")
                return False
        
        return True
    
    def execute_signal(self, symbol: str, signal: str):
        """
        Выполнить торговый сигнал.
        """
        if signal == 'up':
            # Проверяем риск-лимиты
            if not self.check_risk_limits(symbol):
                return
            
            # Получаем текущую цену
            current_price = self.exchange.get_current_price(symbol)
            if not current_price:
                logger.error(f"❌ Не удалось получить цену для {symbol}")
                return
            
            # Параметры сделки
            qty = self.config.get('qty', 10)
            tp_percent = self.config.get('tp', 0.05)
            sl_percent = self.config.get('sl', 0.02)
            
            tp_price = current_price * (1 + tp_percent)
            sl_price = current_price * (1 - sl_percent)
            
            # Размещаем ордер
            order = self.order_manager.place_order(
                symbol=symbol,
                side='BUY',
                quantity=qty,
                order_type='market',
                tp_price=tp_price,
                sl_price=sl_price,
                tp_percent=tp_percent,
                sl_percent=sl_percent
            )
            
            if order and order.get('success'):
                logger.info(f"✅ {symbol}: открыта позиция BUY по {current_price}")
                self.stats['total_trades'] += 1
            
        elif signal == 'down':
            # Проверяем, есть ли открытые позиции для закрытия
            open_positions = self.position_tracker.get_open_positions(symbol)
            if open_positions:
                for pos in open_positions:
                    self.order_manager.close_position(pos['trade_id'])
                    logger.info(f"🔒 {symbol}: закрыта позиция по сигналу SELL")
        
        self.stats['total_signals'] += 1
    
    def run_cycle(self):
        """Один цикл торговли"""
        for symbol in self.symbols:
            try:
                # Получаем сигнал
                signal = self.get_signal(symbol)
                
                # Выполняем сигнал
                if signal != 'none':
                    self.execute_signal(symbol, signal)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле для {symbol}: {e}")
                self.stats['last_error'] = str(e)
    
    def log_status(self):
        """Логирование статуса бота"""
        positions = self.position_tracker.get_all_open_positions()
        total_pnl = sum(p.get('pnl', 0) for p in positions)
        
        logger.info(f"📊 Статус {self.bot_name}:")
        logger.info(f"   Символы: {self.symbols}")
        logger.info(f"   Открытых позиций: {len(positions)}")
        logger.info(f"   Текущий PnL: {total_pnl:.2f} USDT")
        logger.info(f"   Всего сигналов: {self.stats['total_signals']}")
        logger.info(f"   Всего сделок: {self.stats['total_trades']}")
    
    def take_snapshot(self):
        """Сохранение снимка состояния в БД"""
        try:
            positions = self.position_tracker.get_all_open_positions()
            total_pnl = sum(p.get('pnl', 0) for p in positions)
            
            # Получаем баланс
            balance = self.exchange.get_balance()
            
            db.execute_update("""
                INSERT INTO snapshots (bot_id, exchange_id, timestamp, balance, total_pnl, open_positions_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                self.bot_id,
                1,  # exchange_id для Bybit
                now_local(),
                balance,
                total_pnl,
                len(positions)
            ))
            logger.debug(f"📸 Снимок сохранён: баланс={balance}, PnL={total_pnl}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения снимка: {e}")
    
    def run(self):
        """Основной цикл бота"""
        logger.info(f"🚀 Запуск бота {self.bot_name}")
        
        # Отправляем уведомление о запуске
        notifier.send_bot_startup(self.bot_name, self.config, self.config.get('strategy', 'unknown'))
        
        # Обновляем статус в БД
        db.execute_update(
            "UPDATE bots SET status = 'active', started_at = %s WHERE id = %s",
            (now_local(), self.bot_id)
        )
        
        try:
            while self.running:
                current_time = time.time()
                
                # Основной торговый цикл
                self.run_cycle()
                
                # Периодический лог статуса
                if current_time - self.last_status_log >= self.intervals['status_log']:
                    self.log_status()
                    self.last_status_log = current_time
                
                # Периодическая проверка рисков
                if current_time - self.last_risk_check >= self.intervals['risk_check']:
                    # Проверка рисков для всех символов
                    for symbol in self.symbols:
                        self.check_risk_limits(symbol)
                    self.last_risk_check = current_time
                
                # Периодический снимок состояния
                if current_time - self.last_snapshot >= self.intervals['snapshot']:
                    self.take_snapshot()
                    self.last_snapshot = current_time
                
                # Пауза
                time.sleep(self.intervals['main_loop'])
                
        except KeyboardInterrupt:
            logger.info(f"🛑 Получен сигнал остановки для {self.bot_name}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в {self.bot_name}: {e}")
            notifier.send_bot_error(self.bot_name, str(e))
        finally:
            self.stop()
    
    def stop(self):
        """Остановка бота"""
        self.running = False
        logger.info(f"🛑 Бот {self.bot_name} остановлен")
        
        # Обновляем статус в БД
        db.execute_update(
            "UPDATE bots SET status = 'stopped', stopped_at = %s WHERE id = %s",
            (now_local(), self.bot_id)
        )
        
        # Отправляем уведомление
        notifier.send_bot_stop(self.bot_name)

    # ==================== МЕТОДЫ ДЛЯ ПЕРЕЗАГРУЗКИ ПАРАМЕТРОВ ====================
    
    def check_reload_signal(self):
        """
        Проверить наличие сигнала на перезагрузку параметров.
        Сигнал: файл /tmp/reload_{bot_id}_{symbol}.signal
        """
        for symbol in self.symbols:
            signal_file = f"/tmp/reload_{self.bot_id}_{symbol}.signal"
            if os.path.exists(signal_file):
                try:
                    with open(signal_file, 'r') as f:
                        content = f.read()
                    logger.info(f"📡 Получен сигнал перезагрузки для {symbol}: {content}")
                    
                    # Удаляем файл сигнала
                    os.remove(signal_file)
                    
                    # Перезагружаем параметры
                    self.reload_params()
                    
                    # Отправляем уведомление
                    notifier.send_message(
                        f"🔄 Бот {self.bot_name} перезагрузил параметры для {symbol}\n"
                        f"Новые параметры применены."
                    )
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сигнала: {e}")
    
    def run(self):
        """Основной цикл бота (обновлённая версия с проверкой сигналов)"""
        logger.info(f"🚀 Запуск бота {self.bot_name}")
        
        notifier.send_bot_startup(self.bot_name, self.config, self.config.get('strategy', 'unknown'))
        
        db.execute_update(
            "UPDATE bots SET status = 'active', started_at = %s WHERE id = %s",
            (now_local(), self.bot_id)
        )
        
        try:
            while self.running:
                current_time = time.time()
                
                # Проверяем сигналы перезагрузки
                self.check_reload_signal()
                
                # Основной торговый цикл
                self.run_cycle()
                
                # Периодический лог статуса
                if current_time - self.last_status_log >= self.intervals['status_log']:
                    self.log_status()
                    self.last_status_log = current_time
                
                # Периодическая проверка рисков
                if current_time - self.last_risk_check >= self.intervals['risk_check']:
                    for symbol in self.symbols:
                        self.check_risk_limits(symbol)
                    self.last_risk_check = current_time
                
                # Периодический снимок состояния
                if current_time - self.last_snapshot >= self.intervals['snapshot']:
                    self.take_snapshot()
                    self.last_snapshot = current_time
                
                time.sleep(self.intervals['main_loop'])
                
        except KeyboardInterrupt:
            logger.info(f"🛑 Получен сигнал остановки для {self.bot_name}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в {self.bot_name}: {e}")
            notifier.send_bot_error(self.bot_name, str(e))
        finally:
            self.stop()
