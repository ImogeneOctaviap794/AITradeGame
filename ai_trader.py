import json
from typing import Dict
from openai import OpenAI, APIConnectionError, APIError

class AITrader:
    def __init__(self, api_key: str, api_url: str, model_name: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
    
    def make_decision(self, market_state: Dict, portfolio: Dict, 
                     account_info: Dict) -> Dict:
        prompt = self._build_prompt(market_state, portfolio, account_info)
        
        response_data = self._call_llm(prompt)
        
        decisions = self._parse_response(response_data['content'])
        
        # 返回决策和思考过程
        return {
            'decisions': decisions,
            'reasoning': response_data.get('reasoning', ''),
            'prompt': prompt  # 也返回完整提示词
        }
    
    def get_analysis_summary(self, market_state: Dict, decisions: Dict,
                           portfolio: Dict, account_info: Dict) -> str:
        """获取中文市场分析总结"""
        prompt = self._build_summary_prompt(market_state, decisions, portfolio, account_info)
        
        try:
            response_data = self._call_llm(prompt)
            summary = response_data['content']
            return summary.strip()
        except Exception as e:
            print(f"[WARN] Failed to get analysis summary: {e}")
            return "市场分析生成失败"
    
    def _build_prompt(self, market_state: Dict, portfolio: Dict, 
                     account_info: Dict) -> str:
        
        # 计算运行统计
        start_time = account_info.get('start_time', account_info.get('current_time', ''))
        current_time = account_info.get('current_time', '')
        invocation_count = account_info.get('invocation_count', 0)
        minutes_running = account_info.get('minutes_running', 0)
        
        prompt = f"""You are a professional cryptocurrency trader with real capital at risk. It has been {minutes_running} minutes since you started trading. The current time is {current_time} and you've been invoked {invocation_count} times.

Your goal: MAXIMIZE RETURNS while managing risk intelligently. Look for alpha opportunities across all coins.

ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST (最旧 → 最新)

Timeframes note: Intraday series are provided at 3-minute intervals (3分钟K线数据)

═══════════════════════════════════════════════════════════════
CURRENT MARKET STATE FOR ALL COINS (当前市场状态)
═══════════════════════════════════════════════════════════════

"""
        # 为每个币种提供详细的市场数据（时间序列格式）
        for coin, data in market_state.items():
            price = data.get('price', 0)
            indicators = data.get('indicators', {})
            
            # 当前值
            current_price = indicators.get('current_price', price)
            current_ema20 = indicators.get('current_ema20', current_price)
            current_macd = indicators.get('current_macd', 0)
            current_rsi_7 = indicators.get('current_rsi_7', 50)
            
            # 时间序列
            mid_prices = indicators.get('mid_prices', [current_price] * 10)
            ema_20_series = indicators.get('ema_20_series', [current_ema20] * 10)
            macd_series = indicators.get('macd_series', [0] * 10)
            rsi_7_series = indicators.get('rsi_7_series', [50] * 10)
            rsi_14_series = indicators.get('rsi_14_series', [50] * 10)
            
            # 格式化数组
            mid_prices_str = ', '.join([f'{p:.1f}' for p in mid_prices])
            ema_20_str = ', '.join([f'{p:.3f}' for p in ema_20_series])
            macd_str = ', '.join([f'{p:.3f}' for p in macd_series])
            rsi_7_str = ', '.join([f'{p:.3f}' for p in rsi_7_series])
            rsi_14_str = ', '.join([f'{p:.3f}' for p in rsi_14_series])
            
            # 4小时指标
            macd_4h_series = indicators.get('macd_4h_series', [0] * 10)
            rsi_14_4h_series = indicators.get('rsi_14_4h_series', [50] * 10)
            macd_4h_str = ', '.join([f'{p:.3f}' for p in macd_4h_series])
            rsi_14_4h_str = ', '.join([f'{p:.3f}' for p in rsi_14_4h_series])
            
            prompt += f"""ALL {coin} DATA
current_price = {current_price:.2f}, current_ema20 = {current_ema20:.3f}, current_macd = {current_macd:.3f}, current_rsi (7 period) = {current_rsi_7:.3f}

In addition, here is the latest {coin} open interest and funding rate for perps:
Open Interest: Latest: {data.get('open_interest', 0):.2f} Average: {data.get('open_interest', 0):.2f}
Funding Rate: {data.get('funding_rate', 0):.6e}

Intraday series (3-minute intervals, oldest → latest):
Mid prices: [{mid_prices_str}]
EMA indicators (20-period): [{ema_20_str}]
MACD indicators: [{macd_str}]
RSI indicators (7-Period): [{rsi_7_str}]
RSI indicators (14-Period): [{rsi_14_str}]

Longer-term context (4-hour timeframe):
20-Period EMA: {indicators.get('ema_20_4h', current_ema20):.3f} vs. 50-Period EMA: {indicators.get('ema_50_4h', current_ema20):.3f}
3-Period ATR: {indicators.get('atr_14', 0):.3f} vs. 14-Period ATR: {indicators.get('atr_14_4h', 0):.3f}
Current Volume: {indicators.get('current_volume', 0):.3f} vs. Average Volume: {indicators.get('volume_avg', 0):.3f}
MACD indicators: [{macd_4h_str}]
RSI indicators (14-Period): [{rsi_14_4h_str}]

"""
        
        # 账户信息
        prompt += f"""═══════════════════════════════════════════════════════════════
YOUR ACCOUNT INFORMATION & PERFORMANCE (账户信息与表现)
═══════════════════════════════════════════════════════════════

Initial Capital: ${account_info['initial_capital']:.2f} (初始资金)
Current Account Value: ${portfolio['total_value']:.2f} (当前账户总值)
Available Cash: ${portfolio['cash']:.2f} (可用现金)
Realized P&L: ${portfolio.get('realized_pnl', 0):.2f} (已实现盈亏)
Unrealized P&L: ${portfolio.get('unrealized_pnl', 0):.2f} (未实现盈亏)
Total Return: {account_info['total_return']:.2f}% (总收益率) {'📈 PROFIT!' if account_info['total_return'] > 0 else '📉 LOSS'}
Margin Used: ${portfolio.get('margin_used', 0):.2f} (已用保证金)

CURRENT LIVE POSITIONS (当前持仓):
"""
        if portfolio['positions']:
            for pos in portfolio['positions']:
                pnl = pos.get('pnl', 0)
                pnl_pct = (pnl / (pos['quantity'] * pos['avg_price'])) * 100 if pos['quantity'] > 0 else 0
                prompt += f"""
{pos['coin']} {pos['side'].upper()}:
  - Quantity: {pos['quantity']:.4f}
  - Entry Price: ${pos['avg_price']:.2f}
  - Current Price: ${pos.get('current_price', 0):.2f}
  - Leverage: {pos['leverage']}x
  - Notional Value: ${pos['quantity'] * pos['avg_price']:.2f}
  - Unrealized P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)
"""
        else:
            prompt += "No positions currently open.\n"
        
        prompt += f"""
═══════════════════════════════════════════════════════════════
TRADING INSTRUCTIONS
═══════════════════════════════════════════════════════════════

Your task is to analyze the market data and make trading decisions based on:
1. Technical indicators (SMA crossovers, RSI levels, trend direction)
2. Current positions and their performance
3. Risk management principles

DECISION RULES:

For EXISTING POSITIONS:
1. CHECK invalidation conditions first - if triggered, CLOSE immediately
2. EVALUATE technical signals - if showing clear reversal (MACD crossover against position, RSI extreme divergence), consider CLOSE
3. If position still looks good and invalidation not triggered - HOLD
4. Stop_loss and profit_target are automatically monitored by the system
5. For HOLD signals: output current quantity, keep existing exit_plan parameters

For NEW POSITIONS - ACTIVE TRADING STRATEGY:
- SEEK opportunities across all coins - look for setups even if you have existing positions
- Enter LONG when: RSI < 40 (oversold bounce), MACD turning positive, price above EMA20, uptrend confirmed
- Enter SHORT when: RSI > 60 (overbought), MACD turning negative, price below EMA20, downtrend confirmed
- Use 10-15x leverage for strong setups (confidence > 0.7), 5-10x for moderate setups
- Position sizing: Risk 3-5% of available cash per trade (higher for high-confidence setups)
- Aim for 2:1 or better risk/reward ratio (profit_target should be 2x the distance from stop_loss)

PORTFOLIO MANAGEMENT:
- Maintain 4-6 positions across different coins for diversification
- Keep at least 30% cash available for new opportunities
- Don't be afraid to take profits when targets are near
- Cut losses quickly if invalidation conditions are met

MARKET CONTEXT AWARENESS:
- 4-hour EMA20 > EMA50 = bullish bias (favor LONG positions)
- 4-hour EMA20 < EMA50 = bearish bias (favor SHORT positions or stay flat)
- MACD 4h trending up = momentum bullish
- High funding rates (> 0.01%) = overcrowded trade, be cautious

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

You MUST respond with ONLY a valid JSON object. No explanations, no markdown, just JSON.

For each coin you want to trade (or hold), provide this structure:

{{
  "COIN_SYMBOL": {{
    "signal": "buy_to_enter|sell_to_enter|close_position|hold",
    "quantity": 0.5,
    "leverage": 10,
    "profit_target": 45000.0,
    "stop_loss": 42000.0,
    "invalidation_condition": "Price closes below $42,000 on 3-minute candle",
    "confidence": 0.75,
    "risk_usd": 500.0,
    "justification": "RSI oversold at 28, price bounced off SMA14 support, strong buying volume"
  }}
}}

FIELD REQUIREMENTS:
- signal: Must be one of: buy_to_enter, sell_to_enter, close_position, hold
- quantity: Actual quantity of coins to trade (calculate based on risk and price)
- leverage: Integer between 1-20
- profit_target: Price level to take profit (not %)
- stop_loss: Price level to cut losses (not %)
- invalidation_condition: Clear price condition that negates your thesis
- confidence: Float between 0.0-1.0 (0.5=neutral, 0.75=high, 0.9=very high)
- risk_usd: Dollar amount at risk for this trade (quantity * price_distance_to_stop_loss)
- justification: Brief 1-sentence reason for the trade

CRITICAL: Output ONLY the JSON object. Do not include any text before or after the JSON.
Do not use markdown code blocks. Just raw JSON starting with {{ and ending with }}.

═══════════════════════════════════════════════════════════════
BEGIN ANALYSIS
═══════════════════════════════════════════════════════════════
"""
        
        return prompt
    
    def _build_summary_prompt(self, market_state: Dict, decisions: Dict, 
                             portfolio: Dict, account_info: Dict) -> str:
        """构建中文市场分析提示词"""
        prompt = """你是一位专业的加密货币交易分析师。请用中文提供一段详细的市场分析和交易总结。

要求格式如下：

第一段：总体账户表现
- 说明账户收益率、现金余额
- 总结当前持仓状况（几个币种，整体是盈利还是亏损）

第二段：各币种表现分析
- 逐个分析每个持仓币种的表现
- 说明哪些币种表现强劲，哪些表现疲软
- 提及是否达到止盈/止损/失效条件

第三段：本次决策说明
- 说明本次采取的行动（开仓/平仓/持有）
- 解释决策理由
- 说明下一步计划

示例格式：
"我的账户上涨了37.65%，有超过4900美元的现金，并且我持有目前所有的ETH、SOL、BTC、DOGE和BNB仓位，因为它们的失效条件尚未达到。XRP仓位略有下跌，但我暂时持有，因为损失很小，而且其失效点还很远。"

---

当前数据：

"""
        
        # 账户信息
        total_return = account_info.get('total_return', 0)
        cash = portfolio.get('cash', 0)
        total_value = portfolio.get('total_value', 0)
        
        prompt += f"""账户表现：
- 总收益率: {total_return:.2f}%
- 账户总值: ${total_value:.2f}
- 可用现金: ${cash:.2f}
- 未实现盈亏: ${portfolio.get('unrealized_pnl', 0):.2f}

"""
        
        # 持仓信息
        prompt += "当前持仓：\n"
        if portfolio.get('positions'):
            for pos in portfolio['positions']:
                pnl = pos.get('pnl', 0)
                pnl_pct = (pnl / (pos['quantity'] * pos['avg_price'])) * 100 if pos['quantity'] > 0 else 0
                prompt += f"- {pos['coin']} {pos['side']}: "
                prompt += f"数量 {pos['quantity']:.4f} @ ${pos['avg_price']:.2f} ({pos['leverage']}x), "
                prompt += f"盈亏 ${pnl:+.2f} ({pnl_pct:+.1f}%), "
                if pos.get('profit_target', 0) > 0:
                    prompt += f"止盈 ${pos['profit_target']:.2f}, "
                if pos.get('stop_loss', 0) > 0:
                    prompt += f"止损 ${pos['stop_loss']:.2f}"
                prompt += "\n"
        else:
            prompt += "- 暂无持仓\n"
        
        prompt += "\n市场数据：\n"
        for coin, data in market_state.items():
            price = data.get('price', 0)
            change = data.get('change_24h', 0)
            indicators = data.get('indicators', {})
            rsi = indicators.get('rsi_14', 50)
            prompt += f"- {coin}: ${price:.2f} ({change:+.2f}%), RSI: {rsi:.1f}\n"
        
        prompt += "\n本次决策：\n"
        for coin, decision in decisions.items():
            signal = decision.get('signal', 'unknown')
            if signal == 'buy_to_enter':
                prompt += f"- {coin}: 开多仓 {decision.get('quantity', 0)} (杠杆{decision.get('leverage', 1)}x)\n"
            elif signal == 'sell_to_enter':
                prompt += f"- {coin}: 开空仓 {decision.get('quantity', 0)} (杠杆{decision.get('leverage', 1)}x)\n"
            elif signal == 'close_position':
                prompt += f"- {coin}: 平仓\n"
            else:
                prompt += f"- {coin}: 持有\n"
        
        prompt += """
---

请基于以上信息，用中文写一段3-4句话的专业分析总结。要求：
1. 简洁明了，语言流畅
2. 包含账户表现、持仓状况、本次决策
3. 专业术语使用准确
4. 不要使用Markdown格式，纯文本即可
"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> Dict:
        try:
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                if '/v1' in base_url:
                    base_url = base_url.split('/v1')[0] + '/v1'
                else:
                    base_url = base_url + '/v1'
            
            client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                timeout=300.0  # 增加超时时间到300秒（5分钟，deepseek-reasoner需要更长时间）
            )
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional cryptocurrency trader. Output JSON format only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            message = response.choices[0].message
            content = message.content
            
            # 检测DeepSeek的reasoning字段
            reasoning = ""
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning = message.reasoning_content
            
            return {
                'content': content,
                'reasoning': reasoning
            }
            
        except APIConnectionError as e:
            error_msg = f"API connection failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except APIError as e:
            error_msg = f"API error ({e.status_code}): {e.message}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"LLM call failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            print(traceback.format_exc())
            raise Exception(error_msg)
    
    def _parse_response(self, response: str) -> Dict:
        response = response.strip()
        
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        
        try:
            decisions = json.loads(response.strip())
            return decisions
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse failed: {e}")
            print(f"[DATA] Response:\n{response}")
            return {}
