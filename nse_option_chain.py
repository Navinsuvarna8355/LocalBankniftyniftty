import requests, time, random
from requests.exceptions import RequestException

NSE_BASE = "https://www.nseindia.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
]

def new_session():
    s = requests.Session()
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.nseindia.com/option-chain",
        "Connection": "keep-alive",
    }
    s.headers.update(headers)
    return s

def fetch_option_chain(symbol):
    session = new_session()
    try:
        session.get(NSE_BASE + "/option-chain", timeout=5)
    except Exception:
        pass
    url = f"{NSE_BASE}/api/option-chain-indices?symbol={symbol}"
    resp = None
    for i in range(3):
        try:
            resp = session.get(url, timeout=6)
            resp.raise_for_status()
            break
        except RequestException as e:
            time.sleep(0.6 + i*0.5)
    if resp is None:
        raise RequestException(f"Failed to GET {url} after retries")
    data = resp.json()
    return data

def compute_oi_pcr_and_underlying(data):
    records = data.get("records", {})
    expiry_dates = records.get("expiryDates", [])
    if not expiry_dates:
        raise ValueError("No expiry dates found in option chain")
    current_expiry = expiry_dates[0]
    total_ce_oi = 0
    total_pe_oi = 0
    total_ce_oi_near = 0
    total_pe_oi_near = 0
    underlying = records.get("underlyingValue")
    for item in records.get("data", []):
        if item.get("expiryDate") != current_expiry:
            continue
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        total_ce_oi += ce.get("openInterest", 0)
        total_pe_oi += pe.get("openInterest", 0)
        strike = item.get("strikePrice", 0)
        if underlying is not None and abs(strike - underlying) <= 200:
            total_ce_oi_near += ce.get("openInterest", 0)
            total_pe_oi_near += pe.get("openInterest", 0)
    pcr_total = round((total_pe_oi / total_ce_oi), 2) if total_ce_oi else None
    pcr_near = round((total_pe_oi_near / total_ce_oi_near), 2) if total_ce_oi_near else None
    return {
        "expiry": current_expiry,
        "underlying": underlying,
        "total_CE_OI": total_ce_oi,
        "total_PE_OI": total_pe_oi,
        "pcr_total": pcr_total,
        "pcr_near": pcr_near
    }
