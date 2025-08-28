from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)
APP_VERSION = "1.0.0"

# ---------------------
# STRATEGY LOGIC
# ---------------------
def determine_swing_signal(pcr: float, trend: str, ema_signal: str):
    t = (trend or "").strip().upper()
    e = (ema_signal or "").strip().upper()
    if t == "BULLISH" and e == "BUY" and pcr >= 1:
        return "BUY", "CALL", "Trend+EMA aligned and PCR >= 1"
    elif t == "BEARISH" and e == "SELL" and pcr <= 1:
        return "SELL", "PUT", "Trend+EMA aligned and PCR <= 1"
    return "SIDEWAYS", None, "Conditions not aligned (Swing)"

def determine_scalp_signal(
    pcr: float, trend: str, ema_signal: str,
    ema_fast: float, ema_mid: float, ema_slow: float,
    disparity: float, prev_disparity: float,
    volume: float, avg_volume: float, vol_mult: float = 1.2
):
    t = (trend or "").strip().upper()
    e = (ema_signal or "").strip().upper()

    bull_stack = ema_fast > ema_mid > ema_slow
    bear_stack = ema_fast < ema_mid < ema_slow
    disp_slope = disparity - prev_disparity
    vol_spike = avg_volume > 0 and volume >= avg_volume * vol_mult
    bull_pcr_ok = 0.95 <= pcr <= 1.30
    bear_pcr_ok = 0.70 <= pcr <= 1.05

    if t == "BULLISH" and e == "BUY" and bull_stack and disp_slope > 0 and vol_spike and bull_pcr_ok:
        return "BUY", "CALL", "Bull stack + Disparity rising + Vol spike + PCR in [0.95,1.30]"
    if t == "BEARISH" and e == "SELL" and bear_stack and disp_slope < 0 and vol_spike and bear_pcr_ok:
        return "SELL", "PUT", "Bear stack + Disparity falling + Vol spike + PCR in [0.70,1.05]"
    return "SIDEWAYS", None, "No confluence for scalp"

def build_response(mode, signal, option, reason, target=0.30, stop=0.20):
    return {
        "version": APP_VERSION,
        "mode": mode,
        "signal": signal,
        "suggested_option": option,
        "reason": reason,
        "risk": {"target_pct": target, "stop_pct": stop},
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

# ---------------------
# ROUTES
# ---------------------
@app.route("/api/signal", methods=["POST"])
def api_signal():
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "scalp").lower()

    pcr = float(data.get("pcr", 1.0))
    trend = data.get("trend", "")
    ema_signal = data.get("ema_signal", "")

    if mode == "swing":
        sig, opt, why = determine_swing_signal(pcr, trend, ema_signal)
        return jsonify(build_response("swing", sig, opt, why))

    ema_fast = float(data.get("ema_fast", 0) or 0)
    ema_mid = float(data.get("ema_mid", 0) or 0)
    ema_slow = float(data.get("ema_slow", 0) or 0)
    disparity = float(data.get("disparity", 0) or 0)
    prev_disparity = float(data.get("prev_disparity", 0) or 0)
    volume = float(data.get("volume", 0) or 0)
    avg_volume = float(data.get("avg_volume", 0) or 0)
    vol_mult = float(data.get("vol_mult", 1.2) or 1.2)

    sig, opt, why = determine_scalp_signal(
        pcr, trend, ema_signal,
        ema_fast, ema_mid, ema_slow,
        disparity, prev_disparity,
        volume, avg_volume, vol_mult
    )
    return jsonify(build_response("scalp", sig, opt, why))

# Minimal embedded UI
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Signal Strategy</title>
  <style>
    body { font:14px system-ui; margin:2rem; }
    input, select { margin:4px; }
    pre { background:#f5f5f5; padding:1rem; }
  </style>
</head>
<body>
  <h1>Signal Strategy Test</h1>
  <form id="f">
    Mode: <select name="mode"><option value="scalp">scalp</option><option value="swing">swing</option></select><br>
    PCR: <input name="pcr" value="1.06"/><br>
    Trend: <select name="trend"><option>BULLISH</option><option>BEARISH</option></select><br>
    EMA Signal: <select name="ema_signal"><option>BUY</option><option>SELL</option></select><br>
    EMA Fast: <input name="ema_fast" value="9"/><br>
    EMA Mid: <input name="ema_mid" value="21"/><br>
    EMA Slow: <input name="ema_slow" value="50"/><br>
    Disparity: <input name="disparity" value="0.8"/><br>
    Prev Disparity: <input name="prev_disparity" value="0.6"/><br>
    Volume: <input name="volume" value="120000"/><br>
    Avg Volume: <input name="avg_volume" value="90000"/><br>
    Vol Multiplier: <input name="vol_mult" value="1.2"/><br>
    <button type="submit">Get Signal</button>
  </form>
  <pre id="out">{}</pre>
  <script>
    document.getElementById('f').addEventListener('submit', async e=>{
      e.preventDefault();
      const fd = new FormData(e.target);
      const payload = {};
      fd.forEach((v,k)=>payload[k] = isNaN(v) ? v : parseFloat(v));
      const res = await fetch('/api/signal',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      document.getElementById('out').textContent = JSON.stringify(json, null, 2);
    });
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/healthz")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
