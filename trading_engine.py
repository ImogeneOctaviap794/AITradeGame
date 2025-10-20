from datetime import datetime
from typing import Dict
import json

class TradingEngine:
    def __init__(self, model_id: int, db, market_fetcher, ai_trader):
        self.model_id = model_id
        self.db = db
        self.market_fetcher = market_fetcher
        self.ai_trader = ai_trader
        self.coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE']
    
    def execute_trading_cycle(self) -> Dict:
        try:
            market_state = self._get_market_state()
            
            current_prices = {coin: market_state[coin]['price'] for coin in market_state}
            
            portfolio = self.db.get_portfolio(self.model_id, current_prices)
            
            # 首先检查现有持仓的止损止盈条件
            exit_results = self._check_exit_conditions(portfolio, current_prices)
            
            account_info = self._build_account_info(portfolio)
            
            decision_result = self.ai_trader.make_decision(
                market_state, portfolio, account_info
            )
            
            # 提取决策、思考过程和提示词
            decisions = decision_result['decisions']
            reasoning = decision_result.get('reasoning', '')
            user_prompt = decision_result.get('prompt', '')
            
            execution_results = self._execute_decisions(decisions, market_state, portfolio)
            
            # 合并退出和执行结果
            all_results = exit_results + execution_results
            
            # 第二个请求：获取中文市场分析总结（传入完整账户信息）
            updated_portfolio_for_summary = self.db.get_portfolio(self.model_id, current_prices)
            analysis_summary = self.ai_trader.get_analysis_summary(
                market_state, decisions, updated_portfolio_for_summary, account_info
            )
            
            self.db.add_conversation(
                self.model_id,
                user_prompt=user_prompt,
                ai_response=json.dumps(decisions, ensure_ascii=False),
                cot_trace=reasoning,  # 存储AI思考过程
                summary=analysis_summary  # 存储中文总结
            )
            
            updated_portfolio = self.db.get_portfolio(self.model_id, current_prices)
            self.db.record_account_value(
                self.model_id,
                updated_portfolio['total_value'],
                updated_portfolio['cash'],
                updated_portfolio['positions_value']
            )
            
            return {
                'success': True,
                'decisions': decisions,
                'executions': all_results,
                'portfolio': updated_portfolio
            }
            
        except Exception as e:
            print(f"[ERROR] Trading cycle failed (Model {self.model_id}): {e}")
            import traceback
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_exit_conditions(self, portfolio: Dict, current_prices: Dict) -> list:
        """
        检查所有持仓的止损止盈条件
        自动平仓触及以下条件的仓位：
        1. profit_target - 达到目标价
        2. stop_loss - 触及止损价
        3. invalidation_condition - 失效条件（简单版本：检查价格）
        """
        results = []
        
        for position in portfolio.get('positions', []):
            coin = position['coin']
            current_price = current_prices.get(coin, 0)
            
            if current_price == 0:
                continue
            
            profit_target = position.get('profit_target', 0)
            stop_loss = position.get('stop_loss', 0)
            side = position['side']
            should_close = False
            reason = ""
            
            # 检查止盈
            if profit_target > 0:
                if side == 'long' and current_price >= profit_target:
                    should_close = True
                    reason = f"Profit target hit: ${current_price:.2f} >= ${profit_target:.2f}"
                elif side == 'short' and current_price <= profit_target:
                    should_close = True
                    reason = f"Profit target hit: ${current_price:.2f} <= ${profit_target:.2f}"
            
            # 检查止损
            if not should_close and stop_loss > 0:
                if side == 'long' and current_price <= stop_loss:
                    should_close = True
                    reason = f"Stop loss hit: ${current_price:.2f} <= ${stop_loss:.2f}"
                elif side == 'short' and current_price >= stop_loss:
                    should_close = True
                    reason = f"Stop loss hit: ${current_price:.2f} >= ${stop_loss:.2f}"
            
            # 如果需要平仓，执行
            if should_close:
                try:
                    # 计算盈亏
                    entry_price = position['avg_price']
                    quantity = position['quantity']
                    
                    if side == 'long':
                        pnl = (current_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - current_price) * quantity
                    
                    # 平仓
                    self.db.close_position(self.model_id, coin, side)
                    
                    # 记录交易
                    self.db.add_trade(
                        self.model_id, coin, 'auto_close', quantity,
                        current_price, position['leverage'], side, pnl=pnl
                    )
                    
                    print(f"[AUTO-EXIT] {coin} {side}: {reason}, P&L: ${pnl:.2f}")
                    
                    results.append({
                        'coin': coin,
                        'signal': 'auto_close',
                        'reason': reason,
                        'quantity': quantity,
                        'price': current_price,
                        'pnl': pnl,
                        'message': f'Auto-closed {coin} {side}: {reason}'
                    })
                    
                except Exception as e:
                    print(f"[ERROR] Auto-exit failed for {coin}: {e}")
                    results.append({'coin': coin, 'error': str(e)})
        
        return results
    
    def _get_market_state(self) -> Dict:
        """Get comprehensive market state with all technical indicators"""
        # Use the new complete market data method
        market_state = self.market_fetcher.get_complete_market_data(self.coins)
        return market_state
    
    def _build_account_info(self, portfolio: Dict) -> Dict:
        model = self.db.get_model(self.model_id)
        initial_capital = model['initial_capital']
        total_value = portfolio['total_value']
        total_return = ((total_value - initial_capital) / initial_capital) * 100
        
        # 获取运行统计
        stats = self.db.get_trading_statistics(self.model_id)
        
        return {
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            'total_return': total_return,
            'initial_capital': initial_capital,
            'start_time': stats['start_time'],
            'minutes_running': stats['minutes_running'],
            'invocation_count': stats['invocation_count']
        }
    
    def _format_prompt(self, market_state: Dict, portfolio: Dict, 
                      account_info: Dict) -> str:
        return f"Market State: {len(market_state)} coins, Portfolio: {len(portfolio['positions'])} positions"
    
    def _execute_decisions(self, decisions: Dict, market_state: Dict, 
                          portfolio: Dict) -> list:
        results = []
        
        for coin, decision in decisions.items():
            if coin not in self.coins:
                continue
            
            signal = decision.get('signal', '').lower()
            
            try:
                if signal == 'buy_to_enter':
                    result = self._execute_buy(coin, decision, market_state, portfolio)
                elif signal == 'sell_to_enter':
                    result = self._execute_sell(coin, decision, market_state, portfolio)
                elif signal == 'close_position':
                    result = self._execute_close(coin, decision, market_state, portfolio)
                elif signal == 'hold':
                    result = {'coin': coin, 'signal': 'hold', 'message': 'Hold position'}
                else:
                    result = {'coin': coin, 'error': f'Unknown signal: {signal}'}
                
                results.append(result)
                
            except Exception as e:
                results.append({'coin': coin, 'error': str(e)})
        
        return results
    
    def _execute_buy(self, coin: str, decision: Dict, market_state: Dict, 
                    portfolio: Dict) -> Dict:
        quantity = float(decision.get('quantity', 0))
        leverage = int(decision.get('leverage', 1))
        price = market_state[coin]['price']
        profit_target = float(decision.get('profit_target', 0))
        stop_loss = float(decision.get('stop_loss', 0))
        invalidation_condition = decision.get('invalidation_condition', '')
        
        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}
        
        required_margin = (quantity * price) / leverage
        if required_margin > portfolio['cash']:
            return {'coin': coin, 'error': 'Insufficient cash'}
        
        # 保存持仓，包括止损止盈信息
        self.db.update_position(
            self.model_id, coin, quantity, price, leverage, 'long',
            profit_target, stop_loss, invalidation_condition
        )
        
        self.db.add_trade(
            self.model_id, coin, 'buy_to_enter', quantity, 
            price, leverage, 'long', pnl=0
        )
        
        return {
            'coin': coin,
            'signal': 'buy_to_enter',
            'quantity': quantity,
            'price': price,
            'leverage': leverage,
            'profit_target': profit_target,
            'stop_loss': stop_loss,
            'message': f'Long {quantity:.4f} {coin} @ ${price:.2f} (TP: ${profit_target:.2f}, SL: ${stop_loss:.2f})'
        }
    
    def _execute_sell(self, coin: str, decision: Dict, market_state: Dict, 
                     portfolio: Dict) -> Dict:
        quantity = float(decision.get('quantity', 0))
        leverage = int(decision.get('leverage', 1))
        price = market_state[coin]['price']
        profit_target = float(decision.get('profit_target', 0))
        stop_loss = float(decision.get('stop_loss', 0))
        invalidation_condition = decision.get('invalidation_condition', '')
        
        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}
        
        required_margin = (quantity * price) / leverage
        if required_margin > portfolio['cash']:
            return {'coin': coin, 'error': 'Insufficient cash'}
        
        # 保存持仓，包括止损止盈信息
        self.db.update_position(
            self.model_id, coin, quantity, price, leverage, 'short',
            profit_target, stop_loss, invalidation_condition
        )
        
        self.db.add_trade(
            self.model_id, coin, 'sell_to_enter', quantity, 
            price, leverage, 'short', pnl=0
        )
        
        return {
            'coin': coin,
            'signal': 'sell_to_enter',
            'quantity': quantity,
            'price': price,
            'leverage': leverage,
            'profit_target': profit_target,
            'stop_loss': stop_loss,
            'message': f'Short {quantity:.4f} {coin} @ ${price:.2f} (TP: ${profit_target:.2f}, SL: ${stop_loss:.2f})'
        }
    
    def _execute_close(self, coin: str, decision: Dict, market_state: Dict, 
                      portfolio: Dict) -> Dict:
        position = None
        for pos in portfolio['positions']:
            if pos['coin'] == coin:
                position = pos
                break
        
        if not position:
            return {'coin': coin, 'error': 'Position not found'}
        
        current_price = market_state[coin]['price']
        entry_price = position['avg_price']
        quantity = position['quantity']
        side = position['side']
        
        if side == 'long':
            pnl = (current_price - entry_price) * quantity
        else:
            pnl = (entry_price - current_price) * quantity
        
        self.db.close_position(self.model_id, coin, side)
        
        self.db.add_trade(
            self.model_id, coin, 'close_position', quantity,
            current_price, position['leverage'], side, pnl=pnl
        )
        
        return {
            'coin': coin,
            'signal': 'close_position',
            'quantity': quantity,
            'price': current_price,
            'pnl': pnl,
            'message': f'Close {coin}, P&L: ${pnl:.2f}'
        }
