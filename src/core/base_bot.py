"""
Базовый класс для всех торговых ботов.
Объединяет все компоненты системы.
"""

import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
import signal
import sys

from src.trading.exchange_client import ExchangeClient, ExchangeFactory
from src.trading.order_manager import OrderManager
from src.trading.position_tracker import PositionTracker
from src.core.database import db, DatabaseError
from src.strategies.legacy import StrategyFactory
from src.messages.console_messages import ConsoleMessages
from src.messages.telegram_messages import TelegramMessages
from src.utils.time_utils import now_utc, now_local, utc_to_local


class BotError(Exception):
    """Базовое исключение для ошибок бота"""
    pass


class TradingBot:
    """
    Базовый класс торгового бота.
    
    Объединяет:
    - ExchangeClient - работа с биржей
    - OrderManager - управление ордерами
    - PositionTracker - отслеживание позиций
    - Strategy - торговую стратегию
    - Database - запись в БД
    """
    
    def __init__(self, bot_name: str, config: Dict[str, Any]):
        """
        Инициализация бота.
        
        Args:
            bot_name: Имя бота (должно совпадать с именем в БД)
            config: Конфигурация бота
        """
        self.bot_name = bot_name
        self.config = config
        self.running = True
        
        # Проверяем подключение к БД перед запуском
        self._check_database_connection()
        
        # Загружаем или создаем бота в БД
        self.bot_id = self._init_bot_in_db()
        
        # Инициализируем компоненты
        self._init_components()
        
        # Синхронизируем состояние с биржей при запуске
        self._sync_with_exchange()
        
        # Интервалы
        self.intervals = config.get('intervals', {
            'status_log': 300,
            'risk_check': 60,
            'closed_check': 30,
            'snapshot': 3600,
            'sync_check': 300  # Проверка синхронизации каждые 5 минут
        })
        
        # Времена последних действий
        self.last_actions = {
            'status_log': 0,
            'risk_check': 0,
            'closed_check': 0,
            'snapshot': 0,
            'sync_check': 0
        }
        
        # Статистика
        self.stats = {
            'signals_received': 0,
            'orders_placed': 0,
            'errors': 0,
            'sync_fixes': 0
        }
        
        # Обработчик сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print(ConsoleMessages.bot_startup(bot_name, config.get('symbol', bot_name)))
    
    def _check_database_connection(self):
        """Проверка подключения к БД"""
        try:
            result = db.execute_query("SELECT 1 as test", fetch_one=True)
            if result and result.get('test') == 1:
                print(f"✅ Подключение к БД успешно")
            else:
                raise DatabaseError("Не удалось выполнить тестовый запрос")
        except Exception as e:
            print(f"❌ Критическая ошибка: не удалось подключиться к БД")
            print(f"   Ошибка: {e}")
            raise BotError(f"Ошибка подключения к БД: {e}")
    
    def _init_bot_in_db(self) -> int:
        """Инициализировать запись о боте в БД"""
        try:
            existing = db.get_bot_by_name(self.bot_name, active_only=False)
            
            if existing:
                if existing['status'] != 'active':
                    db.update_bot_status(existing['id'], 'active', 'startup')
                print(f"✅ Бот {self.bot_name} (ID: {existing['id']}) найден в БД")
                return existing['id']
            
            exchange_id = db.get_exchange_id(self.config.get('exchange', 'bybit'))
            if not exchange_id:
                raise BotError(f"Биржа {self.config.get('exchange')} не найдена")
            
            bot_data = {
                'name': self.bot_name,
                'exchange_id': exchange_id,
                'strategy_type': self.config.get('strategy', 'ma_crossover'),
                'strategy_params': self.config.get('strategy_params', {}),
                'risk_params': self.config.get('risk_params', {}),
                'version': '1.0.0'
            }
            
            bot_id = db.create_bot(bot_data)
            print(f"✅ Создан новый бот {self.bot_name} (ID: {bot_id})")
            return bot_id
            
        except Exception as e:
            print(f"❌ Ошибка при работе с БД: {e}")
            raise BotError(f"Не удалось инициализировать бота в БД: {e}")
    
    def _init_components(self):
        """Инициализация всех компонентов"""
        try:
            self.exchange = ExchangeClient(self.config.get('exchange', 'bybit'))
            
            self.order_manager = OrderManager(
                self.exchange,
                self.bot_id,
                self.bot_name
            )
            
            self.position_tracker = PositionTracker(
                self.exchange,
                self.bot_id,
                self.bot_name
            )
            
            strategy_name = self.config.get('strategy', 'ma_crossover')
            strategy_params = self.config.get('strategy_params', {})
            self.strategy = StrategyFactory.create_strategy(strategy_name, strategy_params)
            
            print(ConsoleMessages.success(f"Стратегия: {self.strategy.name}"))
            
            self.symbol = self.config.get('symbol', self.bot_name)
            self.tp_percent = self.config.get('tp', 0.035) * 100
            self.sl_percent = self.config.get('sl', 0.030) * 100
            self.tp_decimal = self.config.get('tp', 0.035)
            self.sl_decimal = self.config.get('sl', 0.030)
            self.timeframe = self.config.get('timeframe', 5)
            self.qty_usdt = self.config.get('qty', 10)
            self.leverage = self.config.get('leverage', 1)
            self.max_positions = self.config.get('max_positions', 5)
            
            if not self.exchange.test_connection():
                raise BotError("Не удалось подключиться к бирже")
            
            if self.leverage > 1:
                self.exchange.set_leverage(self.symbol, self.leverage)
            
            self.exchange.set_position_mode(self.symbol)
            
            print(ConsoleMessages.bot_ready(
                self.bot_name,
                self.tp_decimal,
                self.sl_decimal,
                self.timeframe,
                self.qty_usdt,
                self.leverage,
                self.max_positions,
                self.strategy.name
            ))
            
        except Exception as e:
            raise BotError(f"Ошибка инициализации компонентов: {e}")
    
    def _sync_with_exchange(self):
        """
        Синхронизация состояния с биржей при запуске.
        Проверяет расхождения между БД и реальными позициями на бирже.
        """
        print(f"\n🔄 СИНХРОНИЗАЦИЯ С БИРЖЕЙ")
        print("-" * 40)
        
        try:
            # Получаем позиции с биржи
            exchange_positions = self.exchange.get_positions(self.symbol)
            print(f"📊 Позиций на бирже: {len(exchange_positions)}")
            
            # Получаем открытые сделки из БД
            db_trades = db.execute_query(
                'SELECT * FROM trades WHERE bot_id = %s AND status = "open" AND symbol = %s',
                (self.bot_id, self.symbol)
            )
            print(f"📊 Открытых сделок в БД: {len(db_trades)}")
            
            # Случай 1: В БД есть открытые сделки, но на бирже их нет
            if len(db_trades) > 0 and len(exchange_positions) == 0:
                print(f"⚠️ Найдены расхождения: в БД {len(db_trades)} сделок, на бирже 0")
                for trade in db_trades:
                    print(f"   Закрываю сделку #{trade['id']} в БД (ручное закрытие на бирже)")
                    
                    # Получаем текущую цену для расчета PnL
                    current_price = self.exchange.get_current_price(self.symbol)
                    
                    # Рассчитываем примерный PnL
                    if trade['side'] == 'BUY':
                        pnl = (current_price - float(trade['entry_price'])) * float(trade['quantity'])
                        pnl_percent = ((current_price - float(trade['entry_price'])) / float(trade['entry_price'])) * 100
                    else:  # SELL
                        pnl = (float(trade['entry_price']) - current_price) * float(trade['quantity'])
                        pnl_percent = ((float(trade['entry_price']) - current_price) / float(trade['entry_price'])) * 100
                    
                    # Закрываем сделку в БД
                    db.close_trade(trade['id'], {
                        'exit_time': now_utc(),
                        'exit_price': current_price,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent,
                        'exit_reason': 'MANUAL',
                        'exit_order_id': 'SYNC_CLOSE'
                    })
                    
                    self.stats['sync_fixes'] += 1
                    print(f"   ✅ Сделка #{trade['id']} закрыта с PnL: {pnl:+.2f} USDT")
            
            # Случай 2: На бирже есть позиции, но в БД их нет
            elif len(exchange_positions) > 0 and len(db_trades) == 0:
                print(f"⚠️ Найдены расхождения: на бирже {len(exchange_positions)} позиций, в БД 0")
                for pos in exchange_positions:
                    print(f"   Создаю запись о позиции {pos['side']} @ {pos['entry_price']}")
                    
                    # Создаем запись о сделке в БД
                    trade_id = db.create_trade({
                        'bot_id': self.bot_id,
                        'exchange_id': self.exchange_id,
                        'symbol': self.symbol,
                        'side': pos['side'],
                        'entry_time': now_utc(),  # приблизительно
                        'entry_price': pos['entry_price'],
                        'quantity': pos['size'],
                        'entry_order_id': 'SYNC_CREATE'
                    })
                    
                    self.stats['sync_fixes'] += 1
                    print(f"   ✅ Создана сделка #{trade_id}")
            
            # Случай 3: Количество совпадает, но могут быть несоответствия в деталях
            elif len(db_trades) == len(exchange_positions) and len(db_trades) > 0:
                print("🔍 Проверка деталей позиций...")
                # Здесь можно добавить более детальную проверку
                # Например, сравнение цен входа и количества
            
            else:
                print("✅ Состояние синхронизировано")
            
            print("-" * 40)
            
        except Exception as e:
            print(f"❌ Ошибка при синхронизации: {e}")
            traceback.print_exc()
    
    def _check_sync(self):
        """
        Периодическая проверка синхронизации.
        Вызывается с интервалом sync_check.
        """
        try:
            # Получаем позиции с биржи
            exchange_positions = self.exchange.get_positions(self.symbol)
            
            # Получаем открытые сделки из БД
            db_trades = db.execute_query(
                'SELECT * FROM trades WHERE bot_id = %s AND status = "open" AND symbol = %s',
                (self.bot_id, self.symbol)
            )
            
            # Если есть расхождение - синхронизируем
            if len(db_trades) != len(exchange_positions):
                print("⚠️ Обнаружено расхождение, запускаю синхронизацию...")
                self._sync_with_exchange()
            
        except Exception as e:
            print(f"⚠️ Ошибка при проверке синхронизации: {e}")
    
    def _signal_handler(self, signum, frame):
        """Обработка сигналов остановки"""
        print(ConsoleMessages.bot_stopped_by_user(self.bot_name))
        self.running = False
    
    def _should_run(self, action: str, current_time: float) -> bool:
        """Проверить, нужно ли выполнить действие"""
        interval = self.intervals.get(action, 0)
        last = self.last_actions.get(action, 0)
        return current_time - last >= interval
    
    def _update_last_action(self, action: str, current_time: float):
        """Обновить время последнего действия"""
        self.last_actions[action] = current_time
    
    def _get_current_price(self) -> Optional[float]:
        """Получить текущую цену"""
        return self.exchange.get_current_price(self.symbol)
    
    def _calculate_quantity(self, price: float) -> float:
        """Рассчитать количество для ордера"""
        return self.exchange.calculate_quantity(self.symbol, self.qty_usdt, price)
    
    def _calculate_tp_sl(self, price: float, side: str) -> tuple:
        """
        Рассчитать цены TP и SL.
        
        Returns:
            (tp_price, sl_price)
        """
        if side == 'buy':
            tp_price = price * (1 + self.tp_decimal)
            sl_price = price * (1 - self.sl_decimal)
        else:
            tp_price = price * (1 - self.tp_decimal)
            sl_price = price * (1 + self.sl_decimal)
        
        info = self.exchange.get_instrument_info(self.symbol)
        precision = info.get('price_precision', 2)
        
        return round(tp_price, precision), round(sl_price, precision)
    
    def _log_status(self):
        """Записать статус в БД"""
        try:
            balance = self.exchange.get_balance()
            positions = self.position_tracker.get_positions_summary()
            total_pnl = self.position_tracker.get_total_pnl()
            symbol_pnl = self.position_tracker.get_symbol_pnl()
            
            self.position_tracker.create_snapshot()
            
            local_time = now_local()
            print(ConsoleMessages.status_line(
                local_time,
                balance or 0,
                symbol_pnl,
                total_pnl,
                positions.get('symbol_positions', 0),
                positions.get('total_positions', 0),
                self.max_positions
            ))
            
            print(ConsoleMessages.status_logged(self.bot_name))
            
        except Exception as e:
            print(ConsoleMessages.error(f"Ошибка логирования статуса: {e}"))
    
    def _check_risk(self):
        """Проверить риск-параметры"""
        try:
            risk_params = self.config.get('risk_params', {})
            if not risk_params:
                return
            
            alerts = self.position_tracker.check_risk_limits(risk_params)
            
            for alert in alerts:
                db.create_alert({
                    'bot_id': self.bot_id,
                    'level': alert['level'],
                    'type': alert['type'],
                    'threshold_value': alert['threshold'],
                    'actual_value': alert['actual'],
                    'message': alert['message']
                })
                
                if alert['level'] == 'CRITICAL':
                    print(ConsoleMessages.error(alert['message']))
                    print(ConsoleMessages.error(f"Критическое нарушение: останавливаю бота"))
                    self.running = False
                    
                    db.create_stop_event({
                        'bot_id': self.bot_id,
                        'stop_type': 'soft',
                        'stop_reason': alert['type'],
                        'triggered_by': 'SYSTEM',
                        'auto_restart_scheduled': False
                    })
                    
                    db.update_bot_status(self.bot_id, 'stopped_soft', alert['type'])
                else:
                    print(ConsoleMessages.warning(alert['message']))
                
        except Exception as e:
            print(ConsoleMessages.error(f"Ошибка проверки рисков: {e}"))
    
    def _check_closed_positions(self):
        """Проверить закрытые позиции"""
        try:
            closed = self.order_manager.check_closed_positions(self.symbol)
            
            for trade in closed:
                print(ConsoleMessages.trade_updated(
                    self.bot_name,
                    trade['symbol'],
                    trade['pnl']
                ))
                
        except Exception as e:
            print(ConsoleMessages.error(f"Ошибка проверки закрытых позиций: {e}"))
    
    def _execute_strategy(self):
        """Выполнить торговую стратегию"""
        try:
            positions = self.position_tracker.get_current_positions()
            if len(positions) >= self.max_positions:
                print(ConsoleMessages.max_positions_reached(self.max_positions))
                return
            
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    print(ConsoleMessages.position_exists(self.symbol))
                    return
            
            df = self.exchange.get_klines(self.symbol, self.timeframe, limit=100)
            if df is None or df.empty:
                print(ConsoleMessages.no_data(self.symbol))
                return
            
            signal = self.strategy.get_signal(df)
            current_price = float(df['close'].iloc[-1])
            
            self.stats['signals_received'] += 1
            
            if signal == 'up':
                print(ConsoleMessages.buy_signal(self.symbol, current_price))
                self._open_position('buy', current_price)
                
            elif signal == 'down':
                print(ConsoleMessages.sell_signal(self.symbol, current_price))
                self._open_position('sell', current_price)
                
            else:
                print(ConsoleMessages.no_signal(self.symbol))
                
        except Exception as e:
            self.stats['errors'] += 1
            print(ConsoleMessages.error(f"Ошибка выполнения стратегии: {e}"))
            traceback.print_exc()
    
    def _open_position(self, side: str, price: float):
        """
        Открыть позицию.
        
        Args:
            side: 'buy' или 'sell'
            price: Текущая цена
        """
        try:
            quantity = self._calculate_quantity(price)
            tp_price, sl_price = self._calculate_tp_sl(price, side)
            
            result = self.order_manager.place_market_order(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                take_profit=tp_price,
                stop_loss=sl_price,
                tp_percent=self.tp_percent,
                sl_percent=self.sl_percent
            )
            
            if result['success']:
                self.stats['orders_placed'] += 1
            else:
                print(ConsoleMessages.error(f"Не удалось открыть позицию: {result.get('error')}"))
                
        except Exception as e:
            self.stats['errors'] += 1
            print(ConsoleMessages.error(f"Ошибка открытия позиции: {e}"))
    
    def run(self):
        """Основной цикл бота"""
        print(ConsoleMessages.info("Запуск основного цикла..."))
        
        time.sleep(2)
        
        while self.running:
            try:
                current_time = time.time()
                
                if self._should_run('closed_check', current_time):
                    self._check_closed_positions()
                    self._update_last_action('closed_check', current_time)
                
                if self._should_run('risk_check', current_time):
                    self._check_risk()
                    self._update_last_action('risk_check', current_time)
                
                if self._should_run('sync_check', current_time):
                    self._check_sync()
                    self._update_last_action('sync_check', current_time)
                
                if self._should_run('status_log', current_time):
                    self._log_status()
                    self._update_last_action('status_log', current_time)
                
                if self._should_run('snapshot', current_time):
                    self.position_tracker.create_snapshot()
                    self._update_last_action('snapshot', current_time)
                
                if self.running:
                    self._execute_strategy()
                
                time.sleep(10)
                
            except KeyboardInterrupt:
                print(ConsoleMessages.bot_stopped_by_user(self.bot_name))
                break
                
            except Exception as e:
                self.stats['errors'] += 1
                print(ConsoleMessages.error(f"Критическая ошибка в цикле: {e}"))
                traceback.print_exc()
                time.sleep(30)
        
        self._cleanup()
    
    def _cleanup(self):
        """Очистка при завершении"""
        print(ConsoleMessages.bot_finished(self.bot_name))
        
        try:
            self._log_status()
            db.update_bot_status(self.bot_id, 'stopped_soft', 'shutdown')
        except:
            pass
        
        print(f"\n📊 Статистика работы:")
        print(f"   Сигналов получено: {self.stats['signals_received']}")
        print(f"   Ордеров размещено: {self.stats['orders_placed']}")
        print(f"   Синхронизаций: {self.stats['sync_fixes']}")
        print(f"   Ошибок: {self.stats['errors']}")
