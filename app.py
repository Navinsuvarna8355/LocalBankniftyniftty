# app.py
import streamlit as st
import pandas as pd
import math
import requests
import logging
from datetime import datetime

# Logging setup takay debugging mein madad mile
logging.basicConfig(level=logging.INFO)

# --- Data Fetching Functions ---
def fetch_option_chain_from_api(symbol):
    """
    Ek third-party API se live option chain data fetch karta hai.
    Yeh function har request ke liye ek naya requests.Session istemal karta hai taake session ya cookies expire na hon.
    """
    api_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        logging.info(f"{symbol} ke liye data fetch karne ki koshish kar rahe hain...")
        
        # Har request ke liye ek naya requests session
        session = requests.Session()
        
        # Pehli request homepage par takay session cookie mil jaye
        homepage_url = "https://www.nseindia.com/"
        session.get(homepage_url, headers=headers, timeout=10)
        
        # Dusri request asli API par, jo session cookie ka istemal karegi
        response = session.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info("Data safalta purvak fetch ho gaya.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"{symbol} ke liye API se data fetch karne mein galti: {e}")
        raise Exception(f"Data fetch karne mein nakam rahe. Galti: {e}")

def fetch_vix_data():
    """
    NSE public API se India VIX ki value fetch karta hai.
    """
    vix_api_url = "https://www.nseindia.com/api/all-indices"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        logging.info("India VIX data fetch kar rahe hain...")
        response = requests.get(vix_api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for index in data.get('data', []):
            if index.get('index') == 'India VIX':
                return index.get('lastPrice')
        
        logging.warning("India VIX data response mein nahi mila.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"India VIX data fetch karne mein galti: {e}")
        return None

def compute_oi_pcr_and_underlying(data):
    """
    Fetched data se PCR aur underlying price compute karta hai.
    """
    if not data or 'records' not in data or 'data' not in data['records']:
        return {'underlying': None, 'pcr_total': None, 'pcr_near': None, 'expiry': None}

    expiry_dates = data['records']['expiryDates']
    if not expiry_dates:
        raise ValueError("Data mein koi expiry dates nahi mili.")
        
    current_expiry = expiry_dates[0]
    
    pe_total_oi = 0
    ce_total_oi = 0
    pe_near_oi = 0
    ce_near_oi = 0

    underlying_price = data['records']['underlyingValue']
    
    for item in data['records']['data']:
        pe_total_oi += item.get('PE', {}).get('openInterest', 0)
        ce_total_oi += item.get('CE', {}).get('openInterest', 0)
        
        # Near expiry data ke liye check karein
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
    PCR, trend aur EMA signal ke aadhar par final trading signal nirdharit karta hai.
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
    VIX value ke aadhar par volatility label aur salah deta hai.
    """
    if vix_value is None:
        return {"value": 0, "label": "Uplabdh nahi", "advice": "Volatility data uplabdh nahi hai."}
    if vix_value < 15:
        return {"value": vix_value, "label": "Kam Volatility", "advice": "Market mein kam volatility hai. Bade price swings ki ummeed nahi hai."}
    elif 15 <= vix_value <= 25:
        return {"value": vix_value, "label": "Madhyam Volatility", "advice": "Market mein madhyam volatility hai. Aap apni strategy ke hisab se trade kar sakte hain."}
    else:
        return {"value": vix_value, "label": "High Volatility", "advice": "Market mein bahut zyada volatility hai. Savdhani se trade karein ya avoid karein."}

def display_dashboard(symbol, info, vix_data):
    """
    Diye gaye symbol ke liye dashboard display karta hai, jismein trade log aur VIX shamil hain.
    """
    # Local UI design ko replicate karne ke liye HTML ka upyog karein
    st.markdown("""
        <style>
            .main-container {
                padding: 2rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .card {
                background-color: #e5e7eb; /* gray-200 ke barabar */
                padding: 1rem;
                border-radius: 0.5rem;
                text-align: center;
                color: #1f2937; /* dark text color ke liye */
            }
            .blue-card {
                background-color: #dbeafe; /* blue-100 ke barabar */
                color: #1f2937; /* dark text color ke liye */
            }
            .signal-card {
                background-color: #f9fafb; /* gray-50 ke barabar */
                padding: 1.5rem;
                border-radius: 0.5rem;
                text-align: center;
            }
            .signal-text {
                font-size: 1.5rem;
                font-weight: bold;
            }
            .green-text { color: #22c55e; } /* green-500 */
            .red-text { color: #ef4444; } /* red-500 */
            .yellow-text { color: #eab308; } /* yellow-500 */
        </style>
    """, unsafe_allow_html=True)

    # Main container
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    st.subheader(f"{symbol} Option Chain Dashboard", help="PCR strategy ke aadhar par live analysis.")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="card blue-card">Live Price<div style="font-size:1.5rem; font-weight: bold;">₹ {info["underlying"]:.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card">PCR<div style="font-size:1.5rem; font-weight: bold;">{info["pcr_total"]:.2f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card">Trend<div style="font-size:1.5rem; font-weight: bold;">{info["trend"]}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="card">India VIX<div style="font-size:1.5rem; font-weight: bold;">{vix_data["value"]:.2f}</div><div style="font-size:0.8rem;">{vix_data["label"]}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Market Volatility Advice")
    st.info(vix_data["advice"])
    st.markdown("---")

    st.subheader("Strategy Signal")
    
    # CE/PE par explicit buy/sell action dikhayein
    if info['signal'] == "BUY":
        st.success(f"Signal: BUY CE - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} CE")
    elif info['signal'] == "SELL":
        st.error(f"Signal: SELL PE - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} PE")
    else:
        st.info("Signal: SIDEWAYS - Koi strong signal nahi mila.")
        
    st.divider()
    
    st.write(f"Data source: NSE India | Last Updated: {info['last_update']}")
    st.warning("Disclaimer: Yeh sirf shaikshik uddeshyon ke liye hai. Live trading ke liye iska upyog na karein.")

    st.markdown('</div>', unsafe_allow_html=True)
    
def display_simulated_sms(phone_number, message_type, trade_details):
    """
    Streamlit app mein ek simulated SMS message display karta hai.
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
    Streamlit app chalane ke liye main function.
    """
    st.set_page_config(
        page_title="NSE Option Chain Strategy",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    st.title("NSE Option Chain Analysis Dashboard")
    st.markdown("Yeh dashboard ek custom trading strategy ke aadhar par NIFTY aur BANKNIFTY ka live analysis pradan karta hai.")

    # Trade log aur data ke liye session state ko initialize karein
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {
            'NIFTY': None,
            'BANKNIFTY': None,
        }
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
    
    # Main page par symbol selection ke liye UI
    symbol_choice = st.radio(
        "Symbol Chunein",
        ["NIFTY", "BANKNIFTY"],
        index=0,
        horizontal=True
    )
    
    # Dono symbols ke liye data fetch aur refresh karne ke liye ek button
    refresh_button = st.sidebar.button("Data Refresh Karein")
    
    # --- Data Fetching aur Display Logic ---
    
    # Button click par ya agar cache mein data nahi hai toh data fetch karein
    if refresh_button or (st.session_state.data_cache['NIFTY'] is None and st.session_state.data_cache['BANKNIFTY'] is None):
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
            
        except Exception as e:
            st.error(f"Data fetch karne mein galti: {e}")
            st.session_state.data_cache['NIFTY'] = None
            st.session_state.data_cache['BANKNIFTY'] = None
    
    # --- Auto-Log aur P&L Update Logic ---
    current_info = st.session_state.data_cache[symbol_choice]
    
    if current_info and current_info['signal'] != "SIDEWAYS":
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

    for entry in list(st.session_state.trade_log):
        if entry['Status'] == "Active" and entry['Symbol'] == symbol_choice:
            if (current_info and current_info['signal'] == "SELL" and entry['Signal'] == "BUY") or \
               (current_info and current_info['signal'] == "BUY" and entry['Signal'] == "SELL") or \
               (current_info and current_info['signal'] == "SIDEWAYS"):
                
                if current_info and current_info['underlying']:
                    current_price = current_info['underlying']
                    for original_entry in st.session_state.trade_log:
                        if original_entry['Timestamp'] == entry['Timestamp'] and original_entry['Symbol'] == entry['Symbol']:
                            original_entry['Status'] = "Closed"
                            original_entry['Exit Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            original_entry['Current Price'] = current_price
                            pnl_calc = (current_price - original_entry['Entry Price']) * original_entry['Lot Size'] if original_entry['Signal'] == "BUY" else (original_entry['Entry Price'] - current_price) * original_entry['Lot Size']
                            original_entry['P&L'] = 0.0
                            original_entry['Final P&L'] = pnl_calc
                            st.success(f"{original_entry['Symbol']} ke liye trade auto-exit ho gaya hai. Final P&L: ₹{pnl_calc:.2f}")
                            display_simulated_sms(phone_number, "exit", original_entry)
                            break
    
    for entry in st.session_state.trade_log:
        if entry['Status'] == "Active":
            current_symbol = entry['Symbol']
            current_signal = entry['Signal']
            current_entry_price = entry['Entry Price']
            
            current_price = st.session_state.data_cache[current_symbol]['underlying'] if st.session_state.data_cache[current_symbol] else None
            if not current_price:
                continue

            if current_signal == "BUY":
                pnl = (current_price - current_entry_price) * entry['Lot Size']
            else:
                pnl = (current_entry_price - current_price) * entry['Lot Size']

            entry['Current Price'] = current_price
            entry['P&L'] = pnl

    # --- Dashboards display karein ---
    if st.session_state.data_cache[symbol_choice]:
        info = st.session_state.data_cache[symbol_choice]
        vix_data = info.get('vix_data', get_vix_label(fetch_vix_data()))
        display_dashboard(symbol_choice, info, vix_data)
    else:
        st.info("Kripya ek symbol chunein aur dashboard dekhne ke liye 'Data Refresh Karein' button par click karein.")
    
    st.subheader("Trade Log")
    if st.session_state.trade_log:
        display_log = []
        for entry in st.session_state.trade_log:
            display_entry = entry.copy()
            display_entry['P&L (Live/Final)'] = f"₹{display_entry['P&L']:.2f}" if display_entry['Status'] == 'Active' else f"₹{display_entry['Final P&L']:.2f}"
            display_log.append(display_entry)
        
        df_log = pd.DataFrame(display_log)
        
        df_log = df_log.drop(columns=['P&L', 'Final P&L'])
        
        st.dataframe(df_log.style.apply(lambda x: ['background: #d4edda' if '₹' in str(x['P&L (Live/Final)']) and float(str(x['P&L (Live/Final)']).replace('₹', '')) > 0 else 'background: #f8d7da' if '₹' in str(x['P&L (Live/Final)']) and float(str(x['P&L (Live/Final)']).replace('₹', '')) < 0 else '' for i in x], axis=1))
    else:
        st.info("Trade log khaali hai. Upar ek trade log karein.")
    
if __name__ == "__main__":
    main()
