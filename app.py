# app.py
import streamlit as st
import pandas as pd
import math
import requests
import logging
from datetime import datetime

# Set up logging to show debug information
logging.basicConfig(level=logging.INFO)

# --- Updated Data Fetching Function using a Public API ---
def fetch_option_chain_from_api(symbol='BANKNIFTY'):
    """
    Fetches live option chain data from a third-party API.
    """
    api_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        logging.info(f"Fetching data from third-party API for {symbol}...")
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info("Data fetched successfully.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from API for {symbol}: {e}")
        raise Exception(f"Failed to fetch data. Error: {e}")

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
        
        # Check for near expiry data
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

def display_dashboard(symbol, info, signal, suggested_side):
    """
    Displays the dashboard for a given symbol, including the trade log feature.
    """
    # Use HTML to replicate the local UI design
    st.markdown("""
        <style>
            .main-container {
                padding: 2rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .card {
                background-color: #e5e7eb; /* Corresponds to gray-200 */
                padding: 1rem;
                border-radius: 0.5rem;
                text-align: center;
                color: #1f2937; /* Add this line for dark text color */
            }
            .blue-card {
                background-color: #dbeafe; /* Corresponds to blue-100 */
                color: #1f2937; /* Add this line for dark text color */
            }
            .signal-card {
                background-color: #f9fafb; /* Corresponds to gray-50 */
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
    
    st.subheader(f"{symbol} Option Chain Dashboard", help="Live analysis based on PCR strategy.")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="card blue-card">Live Price<div style="font-size:1.5rem; font-weight: bold;">₹ {info["underlying"]:.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card">PCR<div style="font-size:1.5rem; font-weight: bold;">{info["pcr_total"]:.2f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card">Trend<div style="font-size:1.5rem; font-weight: bold;">{info["trend"]}</div></div>', unsafe_allow_html=True)

    st.subheader("Strategy Signal")
    
    # Show explicit buy/sell action on CE/PE
    if signal == "BUY":
        st.success(f"Signal: BUY CE - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} CE")
    elif signal == "SELL":
        st.error(f"Signal: SELL PE - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} PE")
    else:
        st.info("Signal: SIDEWAYS - No strong signal found.")
        
    st.divider()
    
    st.write(f"Data source: NSE India | Last Updated: {info['last_update']}")
    st.warning("Disclaimer: This is for educational purposes only. Do not use for live trading.")

    st.markdown('</div>', unsafe_allow_html=True)
    
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
        page_title="NSE Option Chain Strategy",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    st.title("NSE Option Chain Analysis Dashboard")
    st.markdown("This dashboard provides live analysis of NIFTY and BANKNIFTY based on a custom trading strategy.")

    # Initialize session state for the trade log and data
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    if 'nifty_data' not in st.session_state:
        st.session_state.nifty_data = None
    if 'banknifty_data' not in st.session_state:
        st.session_state.banknifty_data = None
    # Add a flag to prevent multiple logs for the same signal
    if 'last_logged_signal' not in st.session_state:
        st.session_state.last_logged_signal = {}
    
    # --- UI for user inputs in the sidebar ---
    st.sidebar.header("Settings")
    phone_number = st.sidebar.text_input("Enter Your Phone Number", help="This is a simulation only. No actual SMS will be sent.")

    ema_signal_choice = st.sidebar.radio(
        "Select EMA Signal",
        ["BUY", "SELL"],
        index=0,
        horizontal=True,
        help="Select 'BUY' for bullish EMA crossover or 'SELL' for bearish."
    )
    
    use_near_pcr = st.sidebar.checkbox("Use Near Expiry PCR?", value=True)
    
    # Add a new input for Lot Size
    lot_size = st.sidebar.number_input("Lot Size", min_value=1, value=1, step=1)

    # Refresh button
    refresh_button = st.sidebar.button("Refresh Data")
    
    # UI for symbol selection on the main page
    symbol_choice = st.radio(
        "Select Symbol",
        ["NIFTY", "BANKNIFTY"],
        index=0,
        horizontal=True
    )

    # --- Data Fetching and Display Logic ---
    
    # Fetch data only if refresh button is clicked or if data is not yet available
    if refresh_button or (symbol_choice == 'NIFTY' and st.session_state.nifty_data is None) or \
       (symbol_choice == 'BANKNIFTY' and st.session_state.banknifty_data is None):
        try:
            with st.spinner(f"Fetching live data for {symbol_choice}... Please wait."):
                data = fetch_option_chain_from_api(symbol_choice)
                info = compute_oi_pcr_and_underlying(data)
            
            pcr_used = info['pcr_near'] if use_near_pcr else info['pcr_total']
            trend = "BULLISH" if pcr_used >= 1 else "BEARISH"
            signal, suggested_side = determine_signal(pcr_used, trend, ema_signal_choice)
            
            # Store calculated info in session state
            current_data = {
                'underlying': info['underlying'],
                'pcr_total': info['pcr_total'],
                'pcr_near': info['pcr_near'],
                'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'use_near_pcr': use_near_pcr,
                'pcr_used': pcr_used,
                'trend': trend,
                'ema_signal': ema_signal_choice,
                'signal': signal,
                'suggested_side': suggested_side,
                'lot_size': lot_size # Store the current lot size for the dashboard
            }

            if symbol_choice == 'NIFTY':
                st.session_state.nifty_data = current_data
            elif symbol_choice == 'BANKNIFTY':
                st.session_state.banknifty_data = current_data
            
        except Exception as e:
            st.error(f"Error fetching data for {symbol_choice}: {e}")
            st.info("Please click 'Refresh Data' to try again.")

    # --- Auto-Log and P&L Update Logic ---
    current_info = None
    if symbol_choice == 'NIFTY' and st.session_state.nifty_data:
        current_info = st.session_state.nifty_data
    elif symbol_choice == 'BANKNIFTY' and st.session_state.banknifty_data:
        current_info = st.session_state.banknifty_data

    if current_info and current_info['signal'] != "SIDEWAYS":
        # Check if the signal has changed since the last log
        log_key = f"{symbol_choice}_{current_info['signal']}"
        if st.session_state.last_logged_signal.get(log_key) != current_info['last_update']:
            
            # Log the new trade
            log_entry = {
                "Timestamp": current_info['last_update'],
                "Symbol": symbol_choice,
                "Signal": current_info['signal'],
                "Suggested Option": f"₹{round(current_info['underlying']/100)*100} {current_info['suggested_side']}",
                "Entry Price": current_info['underlying'],
                "Exit Time": "-",
                "Current Price": current_info['underlying'], # Initial current price is the entry price
                "P&L": 0.0,
                "Final P&L": "-",
                "Used PCR": f"{current_info['pcr_used']:.2f}",
                "Lot Size": lot_size, # Log the lot size
                "Status": "Active" # To track active trades
            }
            st.session_state.trade_log.append(log_entry)
            st.session_state.last_logged_signal[log_key] = current_info['last_update']
            
            # Display simulated SMS for trade entry
            display_simulated_sms(phone_number, "entry", log_entry)

    # Auto-exit logic for active trades
    current_nifty_price = st.session_state.nifty_data['underlying'] if st.session_state.nifty_data else None
    current_banknifty_price = st.session_state.banknifty_data['underlying'] if st.session_state.banknifty_data else None
    
    # Get the latest signal for the selected symbol to check for exit conditions
    current_signal_for_exit = current_info['signal'] if current_info else None

    # Iterate over a copy to avoid issues with modifying the list while iterating
    for entry in list(st.session_state.trade_log):
        if entry['Status'] == "Active" and entry['Symbol'] == symbol_choice:
            # Check for exit conditions
            # Exit if the current signal is opposite of the entry signal or is 'SIDEWAYS'
            if (current_signal_for_exit == "SELL" and entry['Signal'] == "BUY") or \
               (current_signal_for_exit == "BUY" and entry['Signal'] == "SELL") or \
               (current_signal_for_exit == "SIDEWAYS"):
                
                current_price = None
                if entry['Symbol'] == 'NIFTY' and current_nifty_price:
                    current_price = current_nifty_price
                elif entry['Symbol'] == 'BANKNIFTY' and current_banknifty_price:
                    current_price = current_banknifty_price
                
                if current_price:
                    # Find the original entry in the session state to modify it
                    for original_entry in st.session_state.trade_log:
                        if original_entry['Timestamp'] == entry['Timestamp'] and original_entry['Symbol'] == entry['Symbol']:
                            original_entry['Status'] = "Closed"
                            original_entry['Exit Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            original_entry['Current Price'] = current_price
                            # Calculate final P&L
                            pnl_calc = (current_price - original_entry['Entry Price']) * original_entry['Lot Size'] if original_entry['Signal'] == "BUY" else (original_entry['Entry Price'] - current_price) * original_entry['Lot Size']
                            original_entry['P&L'] = 0.0 # Reset live P&L for closed trade
                            original_entry['Final P&L'] = pnl_calc
                            st.success(f"Trade for {original_entry['Symbol']} has been auto-exited. Final P&L: ₹{pnl_calc:.2f}")
                            
                            # Display simulated SMS for trade exit
                            display_simulated_sms(phone_number, "exit", original_entry)
                            break
    
    # Update P&L for all active trades
    for entry in st.session_state.trade_log:
        if entry['Status'] == "Active":
            current_symbol = entry['Symbol']
            current_signal = entry['Signal']
            current_entry_price = entry['Entry Price']
            
            if current_symbol == 'NIFTY' and current_nifty_price:
                current_price = current_nifty_price
            elif current_symbol == 'BANKNIFTY' and current_banknifty_price:
                current_price = current_banknifty_price
            else:
                continue

            # Calculate live P&L based on signal and lot size
            if current_signal == "BUY":
                pnl = (current_price - current_entry_price) * entry['Lot Size']
            else: # SELL
                pnl = (current_entry_price - current_price) * entry['Lot Size']

            entry['Current Price'] = current_price
            entry['P&L'] = pnl

    # Display the dashboard based on the selected symbol
    if symbol_choice == 'NIFTY' and st.session_state.nifty_data:
        info = st.session_state.nifty_data
        display_dashboard(symbol_choice, info, info['signal'], info['suggested_side'])
    elif symbol_choice == 'BANKNIFTY' and st.session_state.banknifty_data:
        info = st.session_state.banknifty_data
        display_dashboard(symbol_choice, info, info['signal'], info['suggested_side'])
    else:
        st.info("Please select a symbol and click 'Refresh Data' to view the dashboard.")
    
    # Display the trade log
    st.subheader("Trade Log")
    if st.session_state.trade_log:
        # Create a new list of entries to display
        display_log = []
        for entry in st.session_state.trade_log:
            # Create a copy to avoid modifying the original session state dicts
            display_entry = entry.copy()
            # Format P&L based on status
            display_entry['P&L (Live/Final)'] = f"₹{display_entry['P&L']:.2f}" if display_entry['Status'] == 'Active' else f"₹{display_entry['Final P&L']:.2f}"
            display_log.append(display_entry)
        
        df_log = pd.DataFrame(display_log)
        
        # Drop the intermediate P&L and Final P&L columns
        df_log = df_log.drop(columns=['P&L', 'Final P&L'])
        
        # Apply color styling
        st.dataframe(df_log.style.apply(lambda x: ['background: #d4edda' if '₹' in str(x['P&L (Live/Final)']) and float(str(x['P&L (Live/Final)']).replace('₹', '')) > 0 else 'background: #f8d7da' if '₹' in str(x['P&L (Live/Final)']) and float(str(x['P&L (Live/Final)']).replace('₹', '')) < 0 else '' for i in x], axis=1))
    else:
        st.info("Trade log is empty. Log a trade above.")
    
if __name__ == "__main__":
    main()
