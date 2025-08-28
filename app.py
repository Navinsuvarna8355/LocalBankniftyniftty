# app.py
import streamlit as st
import pandas as pd
import math
import requests
import logging
from datetime import datetime
import time

# Logging setup for debugging
logging.basicConfig(level=logging.INFO)

# --- Data Fetching Functions ---
def fetch_option_chain_from_api(symbol):
    """
    Fetches live option chain data from a third-party API.
    Uses a fresh requests.Session for each request to avoid stale sessions.
    """
    api_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        logging.info(f"Attempting to fetch data for {symbol}...")
        session = requests.Session()
        homepage_url = "https://www.nseindia.com/"
        session.get(homepage_url, headers=headers, timeout=10)
        response = session.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info("Data fetched successfully.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from API for {symbol}: {e}")
        raise Exception(f"Failed to fetch data. Error: {e}")

def fetch_vix_data():
    """
    Fetches the India VIX value from a public NSE API.
    """
    vix_api_url = "https://www.nseindia.com/api/all-indices"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        logging.info("Fetching India VIX data...")
        response = requests.get(vix_api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for index in data.get('data', []):
            if index.get('index') == 'India VIX':
                return index.get('lastPrice')
        
        logging.warning("India VIX data not found in the response.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching India VIX data: {e}")
        return None

def compute_oi_pcr_and_underlying(data):
    """
    Computes PCR and gets underlying price from the fetched data.
    """
    if not data or 'records' not in data or 'data' not in data['records']:
        return {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None}

    expiry_dates = data['records']['expiryDates']
    if not expiry_dates:
        raise ValueError("No expiry dates found in the data.")
        
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

# --- Strategy and UI Functions ---
def determine_signal(pcr, trend, ema_signal):
    """
    Based on PCR, trend and EMA signal, determines the final trading signal.
    """
    signal = "SIDEWAYS"
    suggested_option = None

    if trend == "BULLISH" and ema_signal == "BUY" and pcr >= 1:
        signal = "BUY"
        suggested_option = "CALL"
    elif trend == "BEARISH" and ema_signal == "SELL" and pcr <= 1:
        signal = "SELL"
        suggested_option = "PUT"
    else:
        signal = "SIDEWAYS"
        suggested_option = None
    return signal, suggested_option

def get_vix_label(vix_value):
    """
    Returns a volatility label and advice based on the VIX value.
    """
    if vix_value is None:
        return {"value": 0, "label": "Not Available", "advice": "Volatility data is not available."}
    if vix_value < 15:
        return {"value": vix_value, "label": "Low Volatility", "advice": "The market has low volatility. Large price swings are not expected."}
    elif 15 <= vix_value <= 25:
        return {"value": vix_value, "label": "Medium Volatility", "advice": "The market has medium volatility. You can trade according to your strategy."}
    else:
        return {"value": vix_value, "label": "High Volatility", "advice": "The market has very high volatility. Trade with great caution or avoid trading."}

def display_dashboard(symbol, info):
    """
    Displays the dashboard for a given symbol.
    """
    st.subheader(f"{symbol} Dashboard")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Live Price", f"₹ {info['underlying']:.2f}")
    with col2:
        st.metric("PCR", f"{info['pcr_total']:.2f}")
    with col3:
        st.metric("Trend", info["trend"])

    st.markdown("---")
    st.subheader("Strategy Signal")
    
    if info['signal'] == "BUY":
        st.success(f"Signal: BUY CE - ATM Option: ₹{round(info['underlying']/100)*100} CE")
    elif info['signal'] == "SELL":
        st.error(f"Signal: SELL PE - ATM Option: ₹{round(info['underlying']/100)*100} PE")
    else:
        st.info("Signal: SIDEWAYS - No strong signal found.")
        
    st.divider()
    
    st.write(f"Last Updated: {info['last_update']}")
    
def display_simulated_sms(phone_number, message_type, trade_details):
    """
    Displays a simulated SMS message in the Streamlit app.
    """
    if not phone_number:
        return

    full_message = f"Number: {phone_number}\n"
    if message_type == "entry":
        full_message += f"New Trade: {trade_details['Symbol']} with a {trade_details['Signal']} signal. Entry Price: ₹{trade_details['Entry Price']:.2f}"
    elif message_type == "exit":
        full_message += f"Trade Closed: {trade_details['Symbol']} trade has been closed. Exit Price: ₹{trade_details['Current Price']:.2f}. P&L: ₹{trade_details['Final P&L']:.2f}"
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("SMS Notification")
    st.sidebar.info(full_message)

def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(
        page_title="NSE Auto Paper Trading App",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    st.title("NSE Auto Paper Trading Dashboard")
    st.markdown("Yeh dashboard ek custom trading strategy ke aadhar par NIFTY aur BANKNIFTY ke liye **automatic paper trades** chalata hai.")
    st.warning("Disclaimer: Yeh sirf shaikshik uddeshyon ke liye hai. Live trading ke liye iska upyog na karein.")

    # Trade log aur data ke liye session state ko initialize karein
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {
            'NIFTY': None,
            'BANKNIFTY': None,
        }
    if 'last_update_time' not in st.session_state:
        st.session_state.last_update_time = 0
    if 'last_logged_signal' not in st.session_state:
        st.session_state.last_logged_signal = {}
    
    # --- Sidebar mein user inputs ke liye UI ---
    st.sidebar.header("Settings")
    phone_number = st.sidebar.text_input("Apna Phone Number Dalein", help="Yeh sirf ek simulation hai. Koi asli SMS nahi bheja jayega.")

    ema_signal_choice = st.sidebar.radio(
        "EMA Signal Chunein",
        ["BUY", "SELL"],
        index=0,
        horizontal=True,
        help="Bullish EMA crossover ke liye 'BUY' ya bearish ke liye 'SELL' chunein."
    )
    
    use_near_pcr = st.sidebar.checkbox("Near Expiry PCR ka upyog karein?", value=True)
    
    lot_size = st.sidebar.number_input("Lot Size", min_value=1, value=1, step=1)
    
    # --- Data Fetching aur Display Logic (Auto-Refresh) ---
    if time.time() - st.session_state.last_update_time > 60:
        try:
            with st.spinner("NIFTY aur BANKNIFTY ke liye live data fetch kar rahe hain..."):
                # Dono symbols ke liye data ek saath fetch karein
                nifty_raw_data = fetch_option_chain_from_api('NIFTY')
                banknifty_raw_data = fetch_option_chain_from_api('BANKNIFTY')
                
                vix_value = fetch_vix_data()
                vix_data = get_vix_label(vix_value)
                
                # NIFTY data ko process karein
                nifty_info = compute_oi_pcr_and_underlying(nifty_raw_data)
                pcr_used_nifty = nifty_info['pcr_near'] if use_near_pcr else nifty_info['pcr_total']
                trend_nifty = "BULLISH" if pcr_used_nifty >= 1 else "BEARISH"
                signal_nifty, suggested_side_nifty = determine_signal(pcr_used_nifty, trend_nifty, ema_signal_choice)
                
                st.session_state.data_cache['NIFTY'] = {
                    'underlying': nifty_info['underlying'],
                    'pcr_total': nifty_info['pcr_total'],
                    'pcr_near': nifty_info['pcr_near'],
                    'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'trend': trend_nifty,
                    'signal': signal_nifty,
                    'suggested_side': suggested_side_nifty,
                    'vix_data': vix_data
                }
                
                # BANKNIFTY data ko process karein
                banknifty_info = compute_oi_pcr_and_underlying(banknifty_raw_data)
                pcr_used_banknifty = banknifty_info['pcr_near'] if use_near_pcr else banknifty_info['pcr_total']
                trend_banknifty = "BULLISH" if pcr_used_banknifty >= 1 else "BEARISH"
                signal_banknifty, suggested_side_banknifty = determine_signal(pcr_used_banknifty, trend_banknifty, ema_signal_choice)
                
                st.session_state.data_cache['BANKNIFTY'] = {
                    'underlying': banknifty_info['underlying'],
                    'pcr_total': banknifty_info['pcr_total'],
                    'pcr_near': banknifty_info['pcr_near'],
                    'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'trend': trend_banknifty,
                    'signal': signal_banknifty,
                    'suggested_side': suggested_side_banknifty,
                    'vix_data': vix_data
                }

                st.session_state.last_update_time = time.time()
                st.rerun()
            
        except Exception as e:
            st.error(f"Data fetch karne mein galti: {e}")
            st.session_state.data_cache['NIFTY'] = None
            st.session_state.data_cache['BANKNIFTY'] = None
    
    # --- Auto-Trading Logic (Entry and Exit) ---
    for symbol_choice in ['NIFTY', 'BANKNIFTY']:
        current_info = st.session_state.data_cache.get(symbol_choice)
        
        if current_info and current_info['signal'] != "SIDEWAYS":
            # Check for an active trade for this symbol
            active_trade = next((trade for trade in st.session_state.trade_log if trade['Symbol'] == symbol_choice and trade['Status'] == 'Active'), None)
            
            if not active_trade:
                # No active trade, so enter a new one based on the current signal
                log_key = f"{symbol_choice}_{current_info['signal']}"
                if st.session_state.last_logged_signal.get(log_key) != current_info['last_update']:
                    
                    log_entry = {
                        "Timestamp": current_info['last_update'],
                        "Symbol": symbol_choice,
                        "Signal": current_info['signal'],
                        "Suggested Option": f"₹{round(current_info['underlying']/100)*100} {current_info['suggested_side']}",
                        "Entry Price": current_info['underlying'],
                        "Exit Time": "-",
                        "Current Price": current_info['underlying'],
                        "P&L": 0.0,
                        "Final P&L": "-",
                        "Used PCR": f"{current_info['pcr_total']:.2f}" if not use_near_pcr else f"{current_info['pcr_near']:.2f}",
                        "Lot Size": lot_size,
                        "Status": "Active"
                    }
                    st.session_state.trade_log.append(log_entry)
                    st.session_state.last_logged_signal[log_key] = current_info['last_update']
                    
                    display_simulated_sms(phone_number, "entry", log_entry)

    # Check for trade exits based on signal changes
    for entry in st.session_state.trade_log:
        if entry['Status'] == "Active":
            current_symbol = entry['Symbol']
            current_info = st.session_state.data_cache.get(current_symbol)
            
            if not current_info:
                continue

            current_signal = current_info['signal']
            entry_signal = entry['Signal']
            
            # Exit conditions
            is_exit_signal = (current_signal == "SIDEWAYS") or \
                             (current_signal == "SELL" and entry_signal == "BUY") or \
                             (current_signal == "BUY" and entry_signal == "SELL")
            
            if is_exit_signal:
                current_price = current_info['underlying']
                entry['Status'] = "Closed"
                entry['Exit Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry['Current Price'] = current_price
                
                if entry_signal == "BUY":
                    pnl_calc = (current_price - entry['Entry Price']) * entry['Lot Size']
                else: # entry_signal == "SELL"
                    pnl_calc = (entry['Entry Price'] - current_price) * entry['Lot Size']
                
                entry['P&L'] = 0.0 # Live P&L is now 0
                entry['Final P&L'] = pnl_calc
                st.success(f"{entry['Symbol']} ke liye trade auto-exit ho gaya hai. Final P&L: ₹{pnl_calc:.2f}")
                display_simulated_sms(phone_number, "exit", entry)
            else:
                # Update live P&L for active trades
                current_price = current_info['underlying']
                if entry_signal == "BUY":
                    pnl_live = (current_price - entry['Entry Price']) * entry['Lot Size']
                else:
                    pnl_live = (entry['Entry Price'] - current_price) * entry['Lot Size']
                entry['Current Price'] = current_price
                entry['P&L'] = pnl_live
    
    # --- Dashboards side-by-side display karein ---
    col_nifty, col_banknifty = st.columns(2)
    
    with col_nifty:
        if st.session_state.data_cache['NIFTY']:
            info = st.session_state.data_cache['NIFTY']
            display_dashboard('NIFTY', info)
        else:
            st.info("NIFTY data uplabdh nahi hai. Thodi der mein automatic refresh hoga.")
    
    with col_banknifty:
        if st.session_state.data_cache['BANKNIFTY']:
            info = st.session_state.data_cache['BANKNIFTY']
            display_dashboard('BANKNIFTY', info)
        else:
            st.info("BANKNIFTY data uplabdh nahi hai. Thodi der mein automatic refresh hoga.")
    
    st.subheader("India VIX")
    vix_data = get_vix_label(st.session_state.data_cache['NIFTY']['vix_data']['value'] if st.session_state.data_cache['NIFTY'] else None)
    st.info(f"India VIX: **{vix_data['value']:.2f}** ({vix_data['label']}). {vix_data['advice']}")
    
    st.subheader("Trade Log")
    if st.session_state.trade_log:
        display_log = []
        for entry in st.session_state.trade_log:
            display_entry = entry.copy()
            display_entry['P&L (Live/Final)'] = f"₹{display_entry['P&L']:.2f}" if display_entry['Status'] == 'Active' else f"₹{display_entry['Final P&L']:.2f}"
            display_log.append(display_entry)
        
        df_log = pd.DataFrame(display_log)
        df_log = df_log.drop(columns=['P&L', 'Final P&L'])
        
        st.dataframe(df_log.style.apply(lambda x: ['background: #d4edda' if float(str(x['P&L (Live/Final)']).replace('₹', '')) > 0 else 'background: #f8d7da' if float(str(x['P&L (Live/Final)']).replace('₹', '')) < 0 else '' for i in x], axis=1))
    else:
        st.info("Trade log khaali hai. App automatic trades record karega.")
    
if __name__ == "__main__":
    main()
