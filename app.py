from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import time
import threading
from datetime import datetime

from trading_engine import TradingEngine
from market_data import MarketDataFetcher
from ai_trader import AITrader
from database import Database

app = Flask(__name__)
CORS(app)

db = Database('trading_bot.db')
market_fetcher = MarketDataFetcher()
trading_engines = {}
auto_trading = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/models', methods=['GET'])
def get_models():
    models = db.get_all_models()
    return jsonify(models)

@app.route('/api/models', methods=['POST'])
def add_model():
    data = request.json
    model_id = db.add_model(
        name=data['name'],
        api_key=data['api_key'],
        api_url=data['api_url'],
        model_name=data['model_name'],
        initial_capital=float(data.get('initial_capital', 100000))
    )
    
    try:
        model = db.get_model(model_id)
        trading_engines[model_id] = TradingEngine(
            model_id=model_id,
            db=db,
            market_fetcher=market_fetcher,
            ai_trader=AITrader(
                api_key=model['api_key'],
                api_url=model['api_url'],
                model_name=model['model_name']
            )
        )
        print(f"[INFO] Model {model_id} ({data['name']}) initialized")
    except Exception as e:
        print(f"[ERROR] Model {model_id} initialization failed: {e}")
    
    return jsonify({'id': model_id, 'message': 'Model added successfully'})

@app.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    try:
        model = db.get_model(model_id)
        model_name = model['name'] if model else f"ID-{model_id}"
        
        db.delete_model(model_id)
        if model_id in trading_engines:
            del trading_engines[model_id]
        
        print(f"[INFO] Model {model_id} ({model_name}) deleted")
        return jsonify({'message': 'Model deleted successfully'})
    except Exception as e:
        print(f"[ERROR] Delete model {model_id} failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/reset', methods=['POST'])
def reset_model(model_id):
    try:
        model = db.get_model(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        model_name = model['name']
        db.reset_model(model_id)
        
        print(f"[INFO] Model {model_id} ({model_name}) reset")
        return jsonify({'message': 'Model reset successfully'})
    except Exception as e:
        print(f"[ERROR] Reset model {model_id} failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/capital', methods=['PUT'])
def update_capital(model_id):
    try:
        model = db.get_model(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        data = request.json
        new_capital = float(data.get('initial_capital', 0))
        
        if new_capital <= 0:
            return jsonify({'error': 'Initial capital must be positive'}), 400
        
        db.update_initial_capital(model_id, new_capital)
        
        model_name = model['name']
        print(f"[INFO] Model {model_id} ({model_name}) capital updated to ${new_capital:.2f}")
        return jsonify({'message': 'Capital updated successfully', 'initial_capital': new_capital})
    except Exception as e:
        print(f"[ERROR] Update capital for model {model_id} failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/portfolio', methods=['GET'])
def get_portfolio(model_id):
    prices_data = market_fetcher.get_current_prices(['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE'])
    current_prices = {coin: prices_data[coin]['price'] for coin in prices_data}
    
    portfolio = db.get_portfolio(model_id, current_prices)
    account_value = db.get_account_value_history(model_id, limit=100)
    
    return jsonify({
        'portfolio': portfolio,
        'account_value_history': account_value
    })

@app.route('/api/models/<int:model_id>/trades', methods=['GET'])
def get_trades(model_id):
    limit = request.args.get('limit', 50, type=int)
    trades = db.get_trades(model_id, limit=limit)
    return jsonify(trades)

@app.route('/api/models/<int:model_id>/conversations', methods=['GET'])
def get_conversations(model_id):
    limit = request.args.get('limit', 20, type=int)
    conversations = db.get_conversations(model_id, limit=limit)
    return jsonify(conversations)

@app.route('/api/market/prices', methods=['GET'])
def get_market_prices():
    coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE']
    prices = market_fetcher.get_current_prices(coins)
    return jsonify(prices)

@app.route('/api/models/<int:model_id>/execute', methods=['POST'])
def execute_trading(model_id):
    if model_id not in trading_engines:
        model = db.get_model(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        trading_engines[model_id] = TradingEngine(
            model_id=model_id,
            db=db,
            market_fetcher=market_fetcher,
            ai_trader=AITrader(
                api_key=model['api_key'],
                api_url=model['api_url'],
                model_name=model['model_name']
            )
        )
    
    try:
        result = trading_engines[model_id].execute_trading_cycle()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def trading_loop():
    print("[INFO] Trading loop started")
    
    # 启动后立即执行一次（如果有模型）
    first_run = True
    
    while auto_trading:
        try:
            if not trading_engines:
                if first_run:
                    print("[INFO] Waiting for models to be added...")
                    first_run = False
                print(f"[DEBUG] No trading engines, sleeping 30s... (time: {datetime.now().strftime('%H:%M:%S')})")
                time.sleep(30)
                continue
            
            # 如果不是第一次运行，先等待3分钟
            if not first_run:
                print(f"\n{'='*60}")
                print(f"[SLEEP] Waiting 3 minutes for next cycle")
                print(f"{'='*60}\n")
                time.sleep(180)
            else:
                print(f"[DEBUG] First run, executing immediately...")
            
            first_run = False
            
            print(f"\n{'='*60}")
            print(f"[CYCLE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"[INFO] Active models: {len(trading_engines)}")
            print(f"[DEBUG] Trading engines IDs: {list(trading_engines.keys())}")
            print(f"{'='*60}")
            
            for model_id, engine in list(trading_engines.items()):
                try:
                    print(f"\n[EXEC] Model {model_id}")
                    result = engine.execute_trading_cycle()
                    
                    if result.get('success'):
                        print(f"[OK] Model {model_id} completed")
                        if result.get('executions'):
                            for exec_result in result['executions']:
                                signal = exec_result.get('signal', 'unknown')
                                coin = exec_result.get('coin', 'unknown')
                                msg = exec_result.get('message', '')
                                if signal != 'hold':
                                    print(f"  [TRADE] {coin}: {msg}")
                    else:
                        error = result.get('error', 'Unknown error')
                        print(f"[WARN] Model {model_id} failed: {error}")
                        
                except Exception as e:
                    print(f"[ERROR] Model {model_id} exception: {e}")
                    import traceback
                    print(traceback.format_exc())
                    continue
            
        except Exception as e:
            print(f"\n[CRITICAL] Trading loop error: {e}")
            import traceback
            print(traceback.format_exc())
            print("[RETRY] Retrying in 60 seconds\n")
            time.sleep(60)
    
    print("[INFO] Trading loop stopped")

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    models = db.get_all_models()
    leaderboard = []
    
    prices_data = market_fetcher.get_current_prices(['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE'])
    current_prices = {coin: prices_data[coin]['price'] for coin in prices_data}
    
    for model in models:
        portfolio = db.get_portfolio(model['id'], current_prices)
        account_value = portfolio.get('total_value', model['initial_capital'])
        returns = ((account_value - model['initial_capital']) / model['initial_capital']) * 100
        
        leaderboard.append({
            'model_id': model['id'],
            'model_name': model['name'],
            'account_value': account_value,
            'returns': returns,
            'initial_capital': model['initial_capital']
        })
    
    leaderboard.sort(key=lambda x: x['returns'], reverse=True)
    return jsonify(leaderboard)

def init_trading_engines():
    try:
        models = db.get_all_models()
        
        if not models:
            print("[WARN] No trading models found")
            return
        
        print(f"\n[INIT] Initializing trading engines...")
        for model in models:
            model_id = model['id']
            model_name = model['name']
            
            try:
                trading_engines[model_id] = TradingEngine(
                    model_id=model_id,
                    db=db,
                    market_fetcher=market_fetcher,
                    ai_trader=AITrader(
                        api_key=model['api_key'],
                        api_url=model['api_url'],
                        model_name=model['model_name']
                    )
                )
                print(f"  [OK] Model {model_id} ({model_name})")
            except Exception as e:
                print(f"  [ERROR] Model {model_id} ({model_name}): {e}")
                continue
        
        print(f"[INFO] Initialized {len(trading_engines)} engine(s)\n")
        
    except Exception as e:
        print(f"[ERROR] Init engines failed: {e}\n")

# 初始化标志，避免重复初始化
_initialized = False

def initialize_app():
    """Initialize database and trading engines"""
    global _initialized
    if _initialized:
        return
    _initialized = True
    
    print("\n" + "=" * 60)
    print("AI Trading Platform - Initializing...")
    print("=" * 60)
    
    db.init_db()
    print("[OK] Database initialized")
    
    init_trading_engines()
    print(f"[OK] Trading engines ready: {len(trading_engines)} model(s)")
    
    if auto_trading:
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
        print("[INFO] Auto-trading enabled (background thread started)")
    else:
        print("[INFO] Auto-trading disabled")
    
    print("\n" + "=" * 60)
    print("Server: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")

# 使用 before_request 确保初始化（适配 flask run）
@app.before_request
def ensure_initialized():
    initialize_app()

if __name__ == '__main__':
    # 如果用 python app.py 启动，立即初始化
    initialize_app()
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
