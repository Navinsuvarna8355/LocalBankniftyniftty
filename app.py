from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import threading, time
import random

app = Flask(__name__)
CORS(app)

# Simulated option chain fetcher (replace with real NSE API logic)
def fetch_option_chain(symbol):
    return {
        'underlying': random.uniform(24000, 55000),
        'pcr_total': round(random.uniform(0.7, 1.2), 2),
        'pcr_near': round(random.uniform(0.7, 1.2), 2),
        'expiry': '28-Aug-2025'
    }

# Strategy logic
def determine_signal(pcr, trend, ema_signal):
    if ema_signal == 'BUY' and trend == 'BULLISH':
        return 'BUY', 'CALL'
    elif ema_signal == 'SELL' and trend == 'BEARISH':
        return 'SELL', 'PUT'
    else:
        return 'SIDEWAYS', None

state = {
    'NIFTY': {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None, 'error': None},
    'BANKNIFTY': {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None, 'error': None},
    'last_update': None
}

POLL_INTERVAL = 5  # seconds

def poller():
    while True:
        for symbol in ['NIFTY', 'BANKNIFTY']:
            try:
                data = fetch_option_chain(symbol)
                state[symbol]['underlying'] = data['underlying']
                state[symbol]['pcr_total'] = data['pcr_total']
                state[symbol]['pcr_near'] = data['pcr_near']
                state[symbol]['expiry'] = data['expiry']
                state[symbol]['error'] = None
            except Exception as e:
                state[symbol]['error'] = str(e)
        state['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        time.sleep(POLL_INTERVAL)

threading.Thread(target=poller, daemon=True).start()

@app.route('/')
def home():
    return jsonify({'message': 'StrategySignal backend running'})

@app.route('/api/summary')
def summary():
    return jsonify({'state': state})

@app.route('/api/strategy')
def strategy():
    symbol = request.args.get('symbol', 'BANKNIFTY').upper()
    if symbol not in state:
        return jsonify({'error': 'Unknown symbol'}), 400

    entry = state[symbol]
    if entry['underlying'] is None or entry['pcr_total'] is None:
        return jsonify({'error': 'Data not ready'}), 503

    use_near = request.args.get('use_near', 'true').lower() in ['1', 'true', 'yes']
    ema_signal = request.args.get('ema_signal', 'BUY').upper()

    pcr = entry['pcr_near'] if use_near and entry['pcr_near'] is not None else entry['pcr_total']

    if pcr >= 1.05:
        trend = 'BULLISH'
    elif pcr <= 0.95:
        trend = 'BEARISH'
    else:
        trend = 'SIDEWAYS'

    signal, suggested_side = determine_signal(pcr, trend, ema_signal)
    atm = round(entry['underlying'] / 100) * 100
    suggested_option = f"{atm} {'CE' if suggested_side == 'CALL' else 'PE'}" if suggested_side else None
    confidence = min(100, int(abs(pcr - 1) * 100))

    return jsonify({
        'symbol': symbol,
        'signal': signal,
        'live_price': round(entry['underlying'], 2),
        'suggested_option': suggested_option,
        'trend': trend,
        'strategy': '3 EMA Crossover + PCR (option-chain)',
        'confidence': confidence,
        'pcr': pcr,
        'pcr_total': entry['pcr_total'],
        'pcr_near': entry['pcr_near'],
        'expiry': entry['expiry'],
        'timestamp': state['last_update']
    })

if __name__ == '__main__':
    print('✅ StrategySignal backend starting...')
    app.run(host='0.0.0.0', port=5000, debug=True)

