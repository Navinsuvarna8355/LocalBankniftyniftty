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

# A public, free third-party API for NSE data. This bypasses direct NSE security.
# (NSE data ke liye ek public, free third-party API. Yeh direct NSE security ko bypass karta hai.)
THIRD_PARTY_API = "https://www.nseoptionchain.com/api/option-chain/?symbol={}"

def fetch_option_chain_from_api(symbol, retries=5, backoff_factor=1):
    """
    Fetches live option chain data from a third-party API with retry logic.
    (Retry logic ke saath ek third-party API se live option chain data fetch karta hai.)
    """
    api_url = THIRD_PARTY_API.format(symbol)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    }
    
    for i in range(retries):
        try:
            logging.info(f"Attempting to fetch data for {symbol} from third-party API, attempt {i+1} of {retries}...")
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info("Data fetched successfully.")
            
            # This API has a different structure, so we need to process it.
            # (Is API ka structure alag hai, isliye isko process karna padega.)
            if data and 'data' in data:
                return data
            else:
                logging.error("Invalid data format from API.")
                return None
                
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error fetching data from API for {symbol}: {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
            else:
                raise Exception(f"Failed to fetch data after multiple retries. Error: {e}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data from API for {symbol}: {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
            else:
                raise Exception(f"Failed to fetch data after multiple retries. Error: {e}")
    
    return None

def fetch_vix_data():
    """
    Fetches the India VIX value from a public source. (Placeholder for a reliable source)
    (Public source se India VIX ki value fetch karta hai. (Ek vishwasniya source ke liye placeholder))
    """
    # NOTE: The previous NSE API for VIX also had security issues.
    # We will use a mock value for now as a reliable public API for VIX is hard to find.
    # For a real application, you would need a paid API for this.
    # (Pichle VIX ke liye NSE API mein bhi security samasya thi. Abhi hum ek mock value ka upyog karenge.)
    # (Ek asli application ke liye, iske liye aapko ek paid API ki zaroorat hogi.)
    logging.info("Using mock VIX data.")
    return 18.50 # A hardcoded, representative value (Ek hardcoded, pratinidhi value)


def compute_oi_pcr_and_underlying(data):
    """
    Computes PCR and gets underlying price from the fetched data (Third-party API).
    (Fetched data se PCR aur underlying price compute karta hai (Third-party API).)
    """
    if not data or 'data' not in data:
        return {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None}

    # This third-party API has a different structure
    pe_total_oi = 0
    ce_total_oi = 0
    pe_near_oi = 0
    ce_near_oi = 0

    # The API might not always provide an underlying price directly in the main response.
    # We'll try to extract it from the first entry.
    underlying_price = data['data'][0]['underlyingValue'] if data['data'] else None
    expiry_dates = list(set([item['expiryDate'] for item in data['data']]))
    expiry_dates.sort()
    current_expiry = expiry_dates[0] if expiry_dates else None

    if not current_expiry:
        return {'underlying': underlying_price, 'pcr_total': None, 'pcr_near': None, 'expiry': None}

    for item in data['data']:
        pe_total_oi += item.get('PE_openInterest', 0)
        ce_total_oi += item.get('CE_openInterest', 0)
        
        if item.get('expiryDate') == current_expiry:
            pe_near_oi += item.get('PE_openInterest', 0)
            ce_near_oi += item.get('CE_openInterest', 0)

    pcr_total = pe_total_oi / ce_total_oi if ce_total_oi != 0 else math.inf
    pcr_near = pe_near_oi / ce_near_oi if ce_near_oi != 0 else math.inf

    return {
        'underlying': underlying_price,
        'pcr_total': pcr_total,
        'pcr_near': pcr_near,
        'expiry': current_expiry
    }


def find_oi_based_sr_levels(data):
    """
    Finds Support and Resistance levels based on highest Open Interest in the near expiry.
    (Near expiry mein sabse zyada Open Interest ke aadhar par Support aur Resistance levels dhoondhta hai.)
    """
    if not data or 'data' not in data:
        return {'resistance': None, 'support': None}
        
    expiry_dates = list(set([item['expiryDate'] for item in data['data']]))
    expiry_dates.sort()
    if not expiry_dates:
        return {'resistance': None, 'support': None}
        
    current_expiry = expiry_dates[0]
    
    max_ce_oi = 0
    resistance_level = None
    
    max_pe_oi = 0
    support_level = None
    
    for item in data['data']:
        if item.get('expiryDate') == current_expiry:
            # Check for Resistance (highest Call OI)
            ce_oi = item.get('CE_openInterest', 0)
            if ce_oi > max_ce_oi:
                max_ce_oi = ce_oi
                resistance_level = item.get('strikePrice')
            
            # Check for Support (highest Put OI)
            pe_oi = item.get('PE_openInterest', 0)
            if pe_oi > max_pe_oi:
                max_pe_oi = pe_oi
                support_level = item.get('strikePrice')
                
    return {'resistance': resistance_level, 'support': support_level}

# --- Strategy and UI Functions ---
def determine_signal(pcr, trend, ema_signal):
    """
    Based on PCR, trend and EMA signal, determines the final trading signal.
    (PCR, trend aur EMA signal ke aadhar par final trading signal nirdharit karta hai.)
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
    (VIX value ke aadhar par volatility label aur salah deta hai.)
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
    Displays the dashboard for a given symbol, including OI-based S&R levels.
    (Diye gaye symbol ke liye dashboard display karta hai, jismein OI-based S&R levels shamil hain.)
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
    elif info['signal'] == "BREACH_UP":
        st.success(f"Signal: RESISTANCE BREACH - Market is likely to move higher.")
    elif info['signal'] == "BREACH_DOWN":
        st.error(f"Signal: SUPPORT BREACH - Market is likely to move lower.")
    else:
        st.info("Signal: SIDEWAYS - No strong signal found.")
        
    st.markdown("---")

    st.subheader("OI-Based Support & Resistance")
    oi_levels = info.get('oi_levels')
    if oi_levels and oi_levels['resistance'] and oi_levels['support']:
        sr_cols = st.columns(2)
        with sr_cols[0]:
            st.metric("Resistance", f"₹ {oi_levels['resistance']:.2f}")
        with sr_cols[1]:
            st.metric("Support", f"₹ {oi_levels['support']:.2f}")
    else:
        st.info("S&R levels not available. Please wait for the next data fetch.")
    
    st.divider()
    
    st.write(f"Last Updated: {info['last_update']}")
    
def display_simulated_sms(phone_number, message_type, trade_details):
    """
    Displays a simulated SMS message in the Streamlit app.
    (Streamlit app mein ek simulated SMS message display karta hai.)
    """
    if not phone_number:
        return

    full_message = f"Number: {phone_number}\n"
    if message_type == "entry":
        full_message += f"New Trade: {trade_details['Symbol']} with a {trade_details['Signal']} signal. Trigger: {trade_details['Trigger']}. Entry Price: ₹{trade_details['Entry Price']:.2f}"
    elif message_type == "exit":
        full_message += f"Trade Closed: {trade_details['Symbol']} trade has been closed. Exit Price: ₹{trade_details['Current Price']:.2f}. P&L: ₹{trade_details['Final P&L']:.2f}"
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("SMS Notification")
    st.sidebar.info(full_message)

def main():
    """
    Main function to run the Streamlit app.
    (Streamlit app chalane ke liye main function.)
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

    # ON/OFF toggle button
    paper_trading_on = st.toggle("Paper Trading ON/OFF", value=False, help="Toggle on to start automatic data refresh and paper trading.")
    
    # Session state
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
    
    # --- Sidebar
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
    
    # --- Data Fetching and Display Logic
    if (time.time() - st.session_state.last_update_time > 60):
        try:
            with st.spinner("NIFTY aur BANKNIFTY ke liye live data fetch kar rahe hain..."):
                nifty_raw_data = fetch_option_chain_from_api('NIFTY')
                banknifty_raw_data = fetch_option_chain_from_api('BANKNIFTY')
                
                vix_value = fetch_vix_data()
                vix_data = get_vix_label(vix_value)
                
                # Process NIFTY data
                nifty_info = compute_oi_pcr_and_underlying(nifty_raw_data)
                if nifty_info['underlying']:
                    pcr_used_nifty = nifty_info['pcr_near'] if use_near_pcr else nifty_info['pcr_total']
                    trend_nifty = "BULLISH" if pcr_used_nifty >= 1 else "BEARISH"
                    signal_nifty, suggested_side_nifty = determine_signal(pcr_used_nifty, trend_nifty, ema_signal_choice)
                    oi_levels_nifty = find_oi_based_sr_levels(nifty_raw_data)
                    st.session_state.data_cache['NIFTY'] = {
                        'underlying': nifty_info['underlying'],
                        'pcr_total': nifty_info['pcr_total'],
                        'pcr_near': nifty_info['pcr_near'],
                        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'trend': trend_nifty,
                        'signal': signal_nifty,
                        'suggested_side': suggested_side_nifty,
                        'vix_data': vix_data,
                        'oi_levels': oi_levels_nifty
                    }
                
                # Process BANKNIFTY data
                banknifty_info = compute_oi_pcr_and_underlying(banknifty_raw_data)
                if banknifty_info['underlying']:
                    pcr_used_banknifty = banknifty_info['pcr_near'] if use_near_pcr else banknifty_info['pcr_total']
                    trend_banknifty = "BULLISH" if pcr_used_banknifty >= 1 else "BEARISH"
                    signal_banknifty, suggested_side_banknifty = determine_signal(pcr_used_banknifty, trend_banknifty, ema_signal_choice)
                    oi_levels_banknifty = find_oi_based_sr_levels(banknifty_raw_data)
                    st.session_state.data_cache['BANKNIFTY'] = {
                        'underlying': banknifty_info['underlying'],
                        'pcr_total': banknifty_info['pcr_total'],
                        'pcr_near': banknifty_info['pcr_near'],
                        'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'trend': trend_banknifty,
                        'signal': signal_banknifty,
                        'suggested_side': suggested_side_banknifty,
                        'vix_data': vix_data,
                        'oi_levels': oi_levels_banknifty
                    }

                st.session_state.last_update_time = time.time()
            
        except Exception as e:
            st.error(f"Data fetch karne mein galti: {e}")
            st.session_state.data_cache['NIFTY'] = None
            st.session_state.data_cache['BANKNIFTY'] = None
    
    # --- Auto-Trading Logic (Entry and Exit) ---
    if paper_trading_on:
        for symbol_choice in ['NIFTY', 'BANKNIFTY']:
            current_info = st.session_state.data_cache.get(symbol_choice)
            
            if not current_info or not current_info['underlying']:
                continue

            current_price = current_info['underlying']
            
            # Check for S&R breach
            breach_signal = "SIDEWAYS"
            if current_info['oi_levels'] and current_info['oi_levels']['resistance'] and current_info['oi_levels']['support']:
                if current_price > current_info['oi_levels']['resistance']:
                    breach_signal = "BREACH_UP"
                elif current_price < current_info['oi_levels']['support']:
                    breach_signal = "BREACH_DOWN"

            # Primary signal is from the strategy
            primary_signal = current_info['signal']
            
            # Combine signals to decide entry/exit
            final_signal = primary_signal
            trade_trigger = "Strategy"
            if primary_signal == "SIDEWAYS" and breach_signal != "SIDEWAYS":
                final_signal = breach_signal
                trade_trigger = "Breach"

            # Check for an active trade for this symbol
            active_trade = next((trade for trade in st.session_state.trade_log if trade['Symbol'] == symbol_choice and trade['Status'] == 'Active'), None)
            
            # Enter a new trade if there's no active one and a valid signal
            if not active_trade and final_signal != "SIDEWAYS":
                log_key = f"{symbol_choice}_{final_signal}_{current_info['last_update']}"
                if st.session_state.last_logged_signal.get(log_key) != current_info['last_update']:
                    
                    log_entry = {
                        "Timestamp": current_info['last_update'],
                        "Symbol": symbol_choice,
                        "Signal": final_signal,
                        "Suggested Option": f"₹{round(current_price/100)*100} {'CE' if final_signal == 'BUY' or final_signal == 'BREACH_UP' else 'PE'}",
                        "Entry Price": current_price,
                        "Exit Time": "-",
                        "Current Price": current_price,
                        "P&L": 0.0,
                        "Final P&L": "-",
                        "Used PCR": f"{current_info['pcr_total']:.2f}" if not use_near_pcr else f"{current_info['pcr_near']:.2f}",
                        "Lot Size": lot_size,
                        "Status": "Active",
                        "Trigger": trade_trigger
                    }
                    st.session_state.trade_log.append(log_entry)
                    st.session_state.last_logged_signal[log_key] = current_info['last_update']
                    
                    display_simulated_sms(phone_number, "entry", log_entry)

        # Check for trade exits based on signal changes
        for entry in list(st.session_state.trade_log):
            if entry['Status'] == "Active":
                current_symbol = entry['Symbol']
                current_info = st.session_state.data_cache.get(current_symbol)
                
                if not current_info or not current_info['underlying']:
                    continue

                current_signal = current_info['signal']
                entry_signal = entry['Signal']
                
                # Exit conditions
                is_exit_signal = (current_signal == "SIDEWAYS") or \
                                 (current_signal == "SELL" and entry_signal == "BUY") or \
                                 (current_signal == "BUY" and entry_signal == "SELL") or \
                                 (current_signal == "BREACH_UP" and entry_signal in ["BREACH_DOWN", "SELL"]) or \
                                 (current_signal == "BREACH_DOWN" and entry_signal in ["BREACH_UP", "BUY"])

                if is_exit_signal:
                    current_price = current_info['underlying']
                    entry['Status'] = "Closed"
                    entry['Exit Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    entry['Current Price'] = current_price
                    
                    if entry_signal in ["BUY", "BREACH_UP"]:
                        pnl_calc = (current_price - entry['Entry Price']) * entry['Lot Size']
                    else: # entry_signal in ["SELL", "BREACH_DOWN"]
                        pnl_calc = (entry['Entry Price'] - current_price) * entry['Lot Size']
                    
                    entry['P&L'] = 0.0
                    entry['Final P&L'] = pnl_calc
                    st.success(f"{entry['Symbol']} ke liye trade auto-exit ho gaya hai. Final P&L: ₹{pnl_calc:.2f}")
                    display_simulated_sms(phone_number, "exit", entry)
                else:
                    # Update live P&L for active trades
                    current_price = current_info['underlying']
                    if entry_signal in ["BUY", "BREACH_UP"]:
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
            st.info("NIFTY data uplabdh nahi hai. Kripya app chalne dein.")
    
    with col_banknifty:
        if st.session_state.data_cache['BANKNIFTY']:
            info = st.session_state.data_cache['BANKNIFTY']
            display_dashboard('BANKNIFTY', info)
        else:
            st.info("BANKNIFTY data uplabdh nahi hai. Kripya app chalne dein.")
    
    st.subheader("India VIX")
    vix_data = get_vix_label(st.session_state.data_cache['NIFTY']['vix_data']['value'] if st.session_state.data_cache['NIFTY'] else None)
    st.info(f"India VIX: **{vix_data['value']:.2f}** ({vix_data['label']}). {vix_data['advice']}")
    
    st.subheader("Trade Log")
    if st.session_state.trade_log:
        display_log = []
        for entry in st.session_state.trade_log:
            display_entry = entry.copy()
            display_entry['P&L (Live/Final)'] = f"₹{display_entry['P&L']:.2f}" if entry['Status'] == 'Active' else f"₹{entry['Final P&L']:.2f}"
            display_log.append(display_entry)
        
        df_log = pd.DataFrame(display_log)
        df_log = df_log.drop(columns=['P&L', 'Final P&L'])
        
        st.dataframe(df_log.style.apply(lambda x: ['background: #d4edda' if float(str(x['P&L (Live/Final)']).replace('₹', '')) > 0 else 'background: #f8d7da' if float(str(x['P&L (Live/Final)']).replace('₹', '')) < 0 else '' for i in x], axis=1))
    else:
        st.info("Trade log khaali hai. App automatic trades record karega.")
    
if __name__ == "__main__":
    main()
