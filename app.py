# backend.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import math
import logging
import time
from datetime import datetime
import threading

# Set up logging to show debug information
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# State to store the fetched data
state = {
    'NIFTY': {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None, 'error': None},
    'BANKNIFTY': {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None, 'error': None},
    'last_update': None
}

POLL_INTERVAL = 60  # Poll every 60 seconds to avoid getting blocked

def fetch_option_chain_data(symbol):
    """Fetches option chain data from NSE."""
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    
    headers = {
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        session.get("https://www.nseindia.com", timeout=10)
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data for {symbol}: {e}")
        return None

def compute_oi_pcr_and_underlying(data):
    """Computes PCR and gets underlying price from the fetched data."""
    if not data or 'records' not in data or 'data' not in data['records']:
        return None

    expiry_dates = data['records']['expiryDates']
    if not expiry_dates:
        return None
        
    current_expiry = expiry_dates[0]
    
    pe_total_oi = 0
    ce_total_oi = 0
    pe_near_oi = 0
    ce_near_oi = 0

    underlying_price = data['records']['underlyingValue']
    
    for item in data['records']['data']:
        pe_total_oi += item.get('PE', {}).get('openInterest', 0)
        ce_total_oi += item.get('CE', {}).get('openInterest', 0)
        
        if item.get('expiryDate') == current_expiry:
            pe_near_oi += item.get('PE', {}).get('openInterest', 0)
            ce_near_oi += item.get('CE', {}).get('openInterest', 0)

    pcr_total = pe_total_oi / ce_total_oi if ce_total_oi != 0 else math.inf
    pcr_near = pe_near_oi / ce_near_oi if ce_near_oi != 0 else math.inf

    return {
        'underlying': underlying_price,
        'pcr_total': pcr_total,
        'pcr_near': pcr_near,
        'expiry': current_expiry
    }

def poller():
    """Background thread to periodically fetch data."""
    while True:
        for symbol in ['NIFTY', 'BANKNIFTY']:
            try:
                data = fetch_option_chain_data(symbol)
                if data:
                    info = compute_oi_pcr_and_underlying(data)
                    if info:
                        state[symbol]['underlying'] = info['underlying']
                        state[symbol]['pcr_total'] = info['pcr_total']
                        state[symbol]['pcr_near'] = info['pcr_near']
                        state[symbol]['expiry'] = info['expiry']
                        state[symbol]['error'] = None
            except Exception as e:
                state[symbol]['error'] = str(e)
                logging.error(f"Poller fetch error for {symbol}: {e}")
        state['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.info("Poller updated state.")
        time.sleep(POLL_INTERVAL)

def determine_signal(pcr, trend, ema_signal):
    """Determines the trading signal."""
    signal = "SIDEWAYS"
    suggested_side = None
    if trend == "BULLISH" and ema_signal == "BUY" and pcr >= 1:
        signal = "BUY"
        suggested_side = "CALL"
    elif trend == "BEARISH" and ema_signal == "SELL" and pcr <= 1:
        signal = "SELL"
        suggested_side = "PUT"
    return signal, suggested_side

@app.route('/api/strategy', methods=['GET'])
def api_strategy():
    """API endpoint for the strategy."""
    symbol = request.args.get('symbol', 'BANKNIFTY').upper()
    ema_signal = request.args.get('ema_signal', 'BUY').upper()
    use_near = request.args.get('use_near', 'true').lower() in ['1', 'true', 'yes']

    if symbol not in state:
        return jsonify({'error': 'unknown symbol'}), 400

    entry = state[symbol]
    if entry['underlying'] is None or entry['pcr_total'] is None:
        return jsonify({'error': 'data not ready', 'last_update': state.get('last_update', 'N/A')}), 503

    pcr = entry['pcr_near'] if use_near and entry['pcr_near'] is not None else entry['pcr_total']
    trend = 'BULLISH' if pcr is not None and pcr >= 1 else 'BEARISH'
    signal, suggested_side = determine_signal(pcr, trend, ema_signal)

    atm = round(entry['underlying'] / 100) * 100 if entry['underlying'] is not None else None
    suggested_option = f"{atm} {'CE' if suggested_side == 'CALL' else 'PE'}" if suggested_side else None

    return jsonify({
        'symbol': symbol,
        'signal': signal,
        'live_price': round(entry['underlying'], 2),
        'suggested_option': suggested_option,
        'trend': trend,
        'pcr': pcr,
        'last_updated': state.get('last_update', 'N/A')
    })

if __name__ == '__main__':
    # Start the background poller thread
    poller_thread = threading.Thread(target=poller, daemon=True)
    poller_thread.start()
    
    # Wait for initial data to be fetched
    print("Waiting for initial data fetch...")
    while state['NIFTY']['underlying'] is None or state['BANKNIFTY']['underlying'] is None:
        time.sleep(1)
    print("Initial data fetched. Starting Flask server...")
    
    app.run(port=5000, debug=True, use_reloader=False)
