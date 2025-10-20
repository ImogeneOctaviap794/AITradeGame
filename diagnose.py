#!/usr/bin/env python3
"""
诊断脚本 - 检查AI交易系统状态
"""

from database import Database
from datetime import datetime, timedelta

print("=" * 70)
print("AI交易系统诊断工具")
print("=" * 70)

db = Database('trading_bot.db')

# 1. 检查模型
print("\n1. 检查交易模型...")
models = db.get_all_models()
print(f"   找到 {len(models)} 个模型")

if not models:
    print("   ❌ 没有配置任何模型！")
    print("   → 解决方案：在Web界面添加模型")
    exit(1)

for model in models:
    print(f"\n   模型 {model['id']}: {model['name']}")
    print(f"   - API: {model['api_url']}")
    print(f"   - Model: {model['model_name']}")
    print(f"   - 初始资金: ${model['initial_capital']:,.2f}")

# 2. 检查对话记录
print("\n2. 检查AI对话记录...")
for model in models:
    conversations = db.get_conversations(model['id'], limit=5)
    print(f"\n   模型 {model['id']} ({model['name']}):")
    print(f"   - 总对话数: {len(conversations)}")
    
    if conversations:
        latest = conversations[0]
        latest_time = datetime.strptime(latest['timestamp'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        time_diff = (now - latest_time).total_seconds() / 60
        
        print(f"   - 最新对话: {latest['timestamp']}")
        print(f"   - 距今: {time_diff:.1f} 分钟")
        
        if time_diff > 5:
            print(f"   ⚠️ 超过5分钟没有新对话！")
            print(f"   → 后台线程可能未运行或出错")
        else:
            print(f"   ✓ 对话正常运行")
    else:
        print(f"   ❌ 没有任何对话记录！")
        print(f"   → 后台线程可能未启动或初始化失败")

# 3. 检查持仓
print("\n3. 检查当前持仓...")
for model in models:
    from market_data import MarketDataFetcher
    fetcher = MarketDataFetcher()
    prices = fetcher.get_current_prices(['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE'])
    current_prices = {coin: prices[coin]['price'] for coin in prices if coin in prices}
    
    portfolio = db.get_portfolio(model['id'], current_prices)
    
    print(f"\n   模型 {model['id']} ({model['name']}):")
    print(f"   - 账户总值: ${portfolio['total_value']:,.2f}")
    print(f"   - 可用资金: ${portfolio['cash']:,.2f}")
    print(f"   - 持仓数量: {len(portfolio['positions'])}")
    
    if portfolio['positions']:
        for pos in portfolio['positions']:
            pnl = pos.get('pnl', 0)
            print(f"     {pos['coin']} {pos['side']}: {pos['quantity']:.4f} @ ${pos['avg_price']:.2f} ({pos['leverage']}x)")
            print(f"       止盈: ${pos.get('profit_target', 0):.2f}, 止损: ${pos.get('stop_loss', 0):.2f}")
            print(f"       盈亏: ${pnl:+.2f}")

# 4. 检查最近交易
print("\n4. 检查最近交易...")
for model in models:
    trades = db.get_trades(model['id'], limit=5)
    print(f"\n   模型 {model['id']} ({model['name']}):")
    print(f"   - 总交易数: {len(trades)}")
    
    if trades:
        print(f"   - 最近5笔交易:")
        for trade in trades[:5]:
            pnl_sign = '+' if trade['pnl'] >= 0 else ''
            print(f"     [{trade['timestamp']}] {trade['coin']} {trade['signal']}: {pnl_sign}${trade['pnl']:.2f}")

# 5. 建议
print("\n" + "=" * 70)
print("诊断建议:")
print("=" * 70)

all_convs = []
for model in models:
    convs = db.get_conversations(model['id'], limit=1)
    all_convs.extend(convs)

if not all_convs:
    print("\n❌ 问题：没有任何AI对话记录")
    print("\n可能原因:")
    print("  1. 后台线程未启动")
    print("  2. trading_engines字典为空")
    print("  3. API连接失败")
    print("\n解决方案:")
    print("  → 停止服务器 (Ctrl+C)")
    print("  → 运行: python app.py (不要用 flask run)")
    print("  → 查看控制台是否显示 '[INFO] Auto-trading enabled'")
elif all_convs:
    latest = all_convs[0]
    latest_time = datetime.strptime(latest['timestamp'], '%Y-%m-%d %H:%M:%S')
    time_diff = (datetime.now() - latest_time).total_seconds() / 60
    
    if time_diff > 5:
        print(f"\n⚠️ 问题：AI对话已停止 {time_diff:.1f} 分钟")
        print("\n可能原因:")
        print("  1. 服务器重启后后台线程未启动")
        print("  2. trading_engines在初始化后被清空")
        print("  3. 循环中出现异常")
        print("\n解决方案:")
        print("  → 查看服务器控制台是否有 [DEBUG] 日志")
        print("  → 如果没有任何 [CYCLE] 日志，说明线程未运行")
        print("  → 重启服务器: python app.py")
    else:
        print("\n✓ 系统运行正常！")
        print(f"  最新对话: {time_diff:.1f} 分钟前")

print("\n" + "=" * 70)

