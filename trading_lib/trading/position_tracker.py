"""
Отслеживание позиций бота.
Агрегирует информацию из биржи и БД.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from trading_lib.trading.exchange_client import ExchangeClient
from trading_lib.utils.database import db
from trading_lib.utils.time_utils import now_utc


class PositionTracker:
    """
    Отслеживание позиций бота.
    
    Отвечает за:
    - Получение текущих позиций с биржи
    - Агрегацию статистики
    - Создание снимков состояния
    """
    
    def __init__(self, exchange_client: ExchangeClient, bot_id: int, bot_name: str):
        self.exchange = exchange_client
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.exchange_id = exchange_client.exchange_id
    
    def get_current_positions(self, symbol: str = None) -> List[Dict]:
        """
        Получить текущие позиции с биржи.
        
        Args:
            symbol: Если указан, только по этому символу
            
        Returns:
            Список позиций
        """
        return self.exchange.get_positions(symbol)
    
    def get_positions_summary(self) -> Dict:
        """
        Получить сводку по позициям.
        
        Returns:
            {
                'total_positions': int,
                'symbol_positions': int (позиции по символу бота),
                'long_positions': int,
                'short_positions': int,
                'total_pnl': float (нереализованный),
                'position_value': float
            }
        """
        positions = self.get_current_positions()
        
        summary = {
            'total_positions': len(positions),
            'symbol_positions': 0,
            'long_positions': 0,
            'short_positions': 0,
            'total_pnl': 0.0,
            'total_position_value': 0.0,
            'positions': []
        }
        
        for pos in positions:
            # Подсчет по типам
            if pos['symbol'] == self.bot_name:  # предполагаем, что имя бота = символ
                summary['symbol_positions'] += 1
            
            if pos['side'] == 'LONG':
                summary['long_positions'] += 1
            else:
                summary['short_positions'] += 1
            
            summary['total_pnl'] += pos.get('unrealised_pnl', 0)
            summary['total_position_value'] += pos.get('position_value', 0)
            
            # Сохраняем детали
            summary['positions'].append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'entry_price': pos['entry_price'],
                'current_price': pos.get('mark_price', pos['entry_price']),
                'pnl': pos.get('unrealised_pnl', 0),
                'pnl_percent': ((pos.get('mark_price', pos['entry_price']) - pos['entry_price']) / pos['entry_price']) * 100
                if pos['side'] == 'LONG' else ((pos['entry_price'] - pos.get('mark_price', pos['entry_price'])) / pos['entry_price']) * 100
            })
        
        return summary
    
    def get_total_pnl(self) -> float:
        """
        Получить общий PnL бота (реализованный + нереализованный).
        
        Returns:
            Общий PnL в USDT (float)
        """
        # Реализованный PnL из БД (может быть Decimal)
        summary = db.get_bot_summary(self.bot_id, days=365*10)  # за всё время
        realized_pnl = summary.get('total_pnl', 0)
        
        # Конвертируем Decimal в float если нужно
        if hasattr(realized_pnl, 'to_decimal'):
            realized_pnl = float(realized_pnl)
        
        # Нереализованный PnL с биржи (уже float)
        positions = self.get_current_positions()
        unrealized_pnl = sum(float(p.get('unrealised_pnl', 0)) for p in positions)
        
        return float(realized_pnl) + unrealized_pnl
    
    def get_symbol_pnl(self, symbol: str = None) -> float:
        """
        Получить PnL по конкретному символу.
        
        Args:
            symbol: Если None, использует имя бота
            
        Returns:
            PnL по символу (float)
        """
        if symbol is None:
            symbol = self.bot_name
        
        # Нереализованный PnL по символу с биржи
        positions = self.get_current_positions(symbol)
        unrealized = 0.0
        for p in positions:
            try:
                unrealized += float(p.get('unrealised_pnl', 0))
            except (TypeError, ValueError):
                pass
        
        # Реализованный PnL по символу из БД
        query = """
            SELECT COALESCE(SUM(pnl), 0) as total_pnl
            FROM trades
            WHERE bot_id = %s AND symbol = %s AND status = 'closed'
        """
        result = db.execute_query(query, (self.bot_id, symbol), fetch_one=True)
        realized = result['total_pnl'] if result else 0
        
        # Конвертируем Decimal в float если нужно
        if not isinstance(realized, float):
            try:
                realized = float(realized)
            except (TypeError, ValueError):
                realized = 0.0
        
        return realized + unrealized
    
    def create_snapshot(self) -> int:
        """
        Создать снимок текущего состояния бота.
        
        Returns:
            ID созданного снимка
        """
        # Получаем текущие данные
        balance = self.exchange.get_balance()
        positions = self.get_current_positions()
        summary = self.get_positions_summary()
        total_pnl = self.get_total_pnl()
        symbol_pnl = self.get_symbol_pnl()
        
        # Получаем открытые сделки из БД для деталей
        open_trades = db.get_open_trades(self.bot_id)
        
        # Рассчитываем просадку (упрощенно)
        drawdown = self._calculate_drawdown()
        
        # Получаем сегодняшний PnL
        today_summary = db.get_bot_summary(self.bot_id, days=1)
        daily_pnl = today_summary.get('total_pnl', 0)
        
        # Получаем количество убыточных сделок подряд
        consecutive_losses = self._get_consecutive_losses()
        
        # Создаем снимок
        snapshot_data = {
            'bot_id': self.bot_id,
            'exchange_id': self.exchange_id,
            'balance': balance or 0,
            'total_pnl': total_pnl,
            'daily_pnl': daily_pnl,
            'open_positions_count': summary['total_positions'],
            'open_positions_json': [
                {
                    'symbol': p['symbol'],
                    'side': p['side'],
                    'size': p['size'],
                    'entry_price': p['entry_price'],
                    'current_price': p.get('current_price'),
                    'pnl': p.get('pnl'),
                    'pnl_percent': p.get('pnl_percent')
                }
                for p in summary['positions']
            ],
            'drawdown_current': drawdown['current'],
            'drawdown_max': drawdown['max'],
            'consecutive_losses': consecutive_losses
        }
        
        return db.create_snapshot(snapshot_data)
    
    def _calculate_drawdown(self) -> Dict[str, float]:
        """
        Рассчитать текущую и максимальную просадку.
        
        Returns:
            {'current': float, 'max': float} в процентах
        """
        # Получаем историю баланса из снимков
        query = """
            SELECT balance, timestamp
            FROM snapshots
            WHERE bot_id = %s
            ORDER BY timestamp DESC
            LIMIT 100
        """
        snapshots = db.execute_query(query, (self.bot_id,))
        
        if len(snapshots) < 2:
            return {'current': 0, 'max': 0}
        
        # Находим максимум за период
        max_balance = max(s['balance'] for s in snapshots)
        current_balance = snapshots[0]['balance']
        
        # Текущая просадка
        current_drawdown = ((max_balance - current_balance) / max_balance * 100) if max_balance > 0 else 0
        
        # Максимальная просадка
        max_drawdown = 0
        running_max = snapshots[0]['balance']
        
        for s in snapshots:
            if s['balance'] > running_max:
                running_max = s['balance']
            drawdown = ((running_max - s['balance']) / running_max * 100) if running_max > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            'current': current_drawdown,
            'max': max_drawdown
        }
    
    def _get_consecutive_losses(self) -> int:
        """
        Получить количество убыточных сделок подряд.
        """
        query = """
            SELECT pnl
            FROM trades
            WHERE bot_id = %s AND status = 'closed'
            ORDER BY exit_time DESC
            LIMIT 10
        """
        recent = db.execute_query(query, (self.bot_id,))
        
        count = 0
        for trade in recent:
            if trade['pnl'] and trade['pnl'] < 0:
                count += 1
            else:
                break
        
        return count
    
    def check_risk_limits(self, risk_params: Dict) -> List[Dict]:
        """
        Проверить соблюдение риск-параметров.
        
        Args:
            risk_params: {
                'max_drawdown': 5.0,
                'max_consecutive_losses': 3,
                'max_daily_loss': 50.0,
                'max_position_size': 100.0
            }
            
        Returns:
            Список нарушений (алертов)
        """
        alerts = []
        
        # Получаем текущие метрики
        drawdown = self._calculate_drawdown()
        consecutive_losses = self._get_consecutive_losses()
        
        # Баланс и позиции
        balance = self.exchange.get_balance() or 0
        positions = self.get_current_positions()
        total_position_value = sum(p.get('position_value', 0) for p in positions)
        
        # Дневной PnL
        today_summary = db.get_bot_summary(self.bot_id, days=1)
        daily_pnl = today_summary.get('total_pnl', 0)
        
        # Проверка просадки
        if 'max_drawdown' in risk_params and drawdown['current'] > risk_params['max_drawdown']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'DRAWDOWN_EXCEEDED',
                'threshold': risk_params['max_drawdown'],
                'actual': drawdown['current'],
                'message': f"Просадка {drawdown['current']:.1f}% превышает лимит {risk_params['max_drawdown']}%"
            })
        
        # Проверка последовательных убытков
        if 'max_consecutive_losses' in risk_params and consecutive_losses >= risk_params['max_consecutive_losses']:
            alerts.append({
                'level': 'WARNING',
                'type': 'CONSECUTIVE_LOSSES_EXCEEDED',
                'threshold': risk_params['max_consecutive_losses'],
                'actual': consecutive_losses,
                'message': f"{consecutive_losses} убыточных сделок подряд (лимит: {risk_params['max_consecutive_losses']})"
            })
        
        # Проверка дневного убытка
        if 'max_daily_loss' in risk_params and abs(daily_pnl) > risk_params['max_daily_loss'] and daily_pnl < 0:
            alerts.append({
                'level': 'WARNING',
                'type': 'DAILY_LOSS_EXCEEDED',
                'threshold': risk_params['max_daily_loss'],
                'actual': abs(daily_pnl),
                'message': f"Дневной убыток {abs(daily_pnl):.2f} USDT превышает лимит {risk_params['max_daily_loss']}"
            })
        
        # Проверка размера позиции
        if 'max_position_size' in risk_params and total_position_value > risk_params['max_position_size']:
            alerts.append({
                'level': 'WARNING',
                'type': 'POSITION_SIZE_EXCEEDED',
                'threshold': risk_params['max_position_size'],
                'actual': total_position_value,
                'message': f"Общий размер позиций {total_position_value:.2f} USDT превышает лимит {risk_params['max_position_size']}"
            })
        
        return alerts