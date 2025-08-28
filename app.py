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

def display_dashboard(symbol, info):
    """
    Displays the dashboard for a given symbol.
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
            }
            .blue-card {
                background-color: #dbeafe; /* Corresponds to blue-100 */
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
    
    st.header(f"{symbol} Live Analysis")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="card blue-card">Live Price<div style="font-size:1.5rem; font-weight: bold;">₹ {info["underlying"]:.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card">Total PCR<div style="font-size:1.5rem; font-weight: bold;">{info["pcr_total"]:.2f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card">Near PCR<div style="font-size:1.5rem; font-weight: bold;">{info["pcr_near"]:.2f}</div></div>', unsafe_allow_html=True)

    st.subheader("Strategy Signal")
    
    ema_signal_choice = st.radio(
        "Select EMA Signal",
        ["BUY", "SELL"],
        index=0,
        horizontal=True,
        help="Select 'BUY' for bullish EMA crossover or 'SELL' for bearish."
    )
    
    use_near_pcr = st.checkbox("Use Near Expiry PCR?", value=True)
    
    pcr_used = info['pcr_near'] if use_near_pcr else info['pcr_total']
    trend = "BULLISH" if pcr_used >= 1 else "BEARISH"
    
    signal, suggested_side = determine_signal(pcr_used, trend, ema_signal_choice)
    
    st.write(f"**Used PCR**: {pcr_used:.2f} ({'Near Expiry' if use_near_pcr else 'Total OI'})")
    st.write(f"**Trend**: {trend}")

    if signal == "BUY":
        st.success(f"Signal: {signal} ({suggested_side}) - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} CE")
    elif signal == "SELL":
        st.error(f"Signal: {signal} ({suggested_side}) - At-The-Money option suggested: ₹{round(info['underlying']/100)*100} PE")
    else:
        st.info("Signal: SIDEWAYS - No strong signal found.")
        
    st.divider()
    
    st.write(f"Last updated: {info['last_update']}")
    st.write("Data source: NSE India")
    st.warning("Disclaimer: This is for educational purposes only. Do not use for live trading.")

    st.markdown('</div>', unsafe_allow_html=True)

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

    dashboard_placeholder = st.empty()

    symbol_choice = st.sidebar.radio(
        "Select Symbol",
        ["NIFTY", "BANKNIFTY"],
        index=0
    )

    if st.sidebar.button("Refresh Data"):
        st.session_state.force_refresh = True
        
    if "force_refresh" not in st.session_state or st.session_state.force_refresh:
        try:
            with st.spinner(f"Fetching live data for {symbol_choice}... Please wait."):
                data = fetch_option_chain_from_api(symbol_choice)
                info = compute_oi_pcr_and_underlying(data)
            
            info['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with dashboard_placeholder.container():
                display_dashboard(symbol_choice, info)
            
            st.session_state.force_refresh = False

        except Exception as e:
            st.error(f"Error fetching data for {symbol_choice}: {e}")
            st.info("Please click 'Refresh Data' to try again.")
            st.session_state.force_refresh = False

if __name__ == "__main__":
    main()
