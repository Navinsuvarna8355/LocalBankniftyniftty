# streamlit_app.py
import streamlit as st
import time
import pandas as pd
from nse_option_chain import fetch_option_chain, compute_oi_pcr_and_underlying

# Function to determine the signal
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
    st.header(f"{symbol} Live Analysis")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Live Price", f"₹ {info['underlying']:.2f}")
    with col2:
        st.metric("Total PCR", f"{info['pcr_total']:.2f}")
    with col3:
        st.metric("Near PCR", f"{info['pcr_near']:.2f}")

    st.subheader("Strategy Signal")
    
    # User inputs for EMA signal and PCR type
    ema_signal_choice = st.radio(
        "Select EMA Signal",
        ["BUY", "SELL"],
        index=0,
        horizontal=True,
        help="Select 'BUY' for bullish EMA crossover or 'SELL' for bearish."
    )
    
    use_near_pcr = st.checkbox("Use Near Expiry PCR?", value=True)
    
    # Determine the PCR and Trend
    pcr_used = info['pcr_near'] if use_near_pcr else info['pcr_total']
    trend = "BULLISH" if pcr_used >= 1 else "BEARISH"
    
    # Determine the final signal
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

    # Select the symbol
    symbol_choice = st.sidebar.radio(
        "Select Symbol",
        ["NIFTY", "BANKNIFTY"],
        index=0
    )
    
    # A placeholder for the dashboard
    dashboard_placeholder = st.empty()

    # Create a simple polling loop
    while True:
        try:
            # Use a spinner to show that the app is loading
            with st.spinner(f"Fetching live data for {symbol_choice}... Please wait."):
                data = fetch_option_chain(symbol_choice)
                info = compute_oi_pcr_and_underlying(data)
            
            # Add timestamp to info
            info['last_update'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

            # Update the dashboard
            with dashboard_placeholder.container():
                display_dashboard(symbol_choice, info)

        except Exception as e:
            st.error(f"Error fetching data for {symbol_choice}: {e}")
            st.info("Retrying in 5 seconds...")

        time.sleep(5)  # Poll every 5 seconds

if __name__ == "__main__":
    main()
