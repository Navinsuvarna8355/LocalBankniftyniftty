# app.py
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime, timezone

APP_VERSION = "1.0.0"

app = Flask(__name__)
CORS(app)

# -------------------------
# Strategy core
# -------------------------

def determine_swing_signal(pcr: float, trend: str, ema_signal: str):
    """
    Original, stricter logic (Swing mode).
    Returns (signal, option, reason).
    """
    t = (trend or "").strip().upper()
    e = (ema_signal or "").strip().upper()

    if t == "BULLISH" and e == "BUY" and pcr >= 1:
        return "BUY", "CALL", "Trend+EMA aligned and PCR >= 1"
    elif t == "BEARISH" and e == "SELL" and pcr <= 1:
        return "SELL", "PUT", "Trend+EMA aligned and PCR <= 1"
    return "SIDEWAYS", None, "Conditions not aligned (Swing)"


def determine_scalp_signal(
    pcr: float,
    trend: str,
    ema_signal: str,
    ema_fast: float,
    ema_mid: float,
    ema_slow: float,
    disparity: float,
    prev_disparity: float,
    volume: float,
    avg_volume: float,
    vol_mult: float = 1.2,
):
    """
    Scalping logic with:
    - PCR tolerance bands
    - Triple-EMA stack
    - Disparity slope
    - Volume spike
    Returns (signal, option, reason).
    """
    t = (trend or "").strip().upper()
    e = (ema_signal or "").strip().upper()

    # Validations
    missing = []
    for name, val in [
        ("ema_fast", ema_fast), ("ema_mid", ema_mid), ("ema_slow", ema_slow),
        ("disparity", disparity), ("prev_disparity", prev_disparity),
        ("volume", volume), ("avg_volume", avg_volume)
    ]:
        if val is None:
            missing.append(name)
    if missing:
        return "SIDEWAYS", None, f"Missing fields for scalp: {', '.join(missing)}"

    bull_stack = (ema_fast > ema_mid > ema_slow)
    bear_stack = (ema_fast < ema_mid < ema_slow)
    disp_slope = disparity - prev_disparity
    vol_spike = (avg_volume > 0) and (volume >= avg_volume * vol_mult)

    # PCR tolerance
    bull_pcr_ok = 0.95 <= pcr <= 1.30
    bear_pcr_ok = 0.70 <= pcr <= 1.05

    # Bullish scalp
    if t == "BULLISH" and e == "BUY" and bull_stack and disp_slope > 0 and vol_spike and bull_pcr_ok:
        reason = "Bull stack + Disparity rising + Vol spike + PCR in [0.95,1.30]"
        return "BUY", "CALL", reason

    # Bearish scalp
    if t == "BEARISH" and e == "SELL" and bear_stack and disp_slope < 0 and vol_spike and bear_pcr_ok:
        reason = "Bear stack + Disparity falling + Vol spike + PCR in [0.70,1.05]"
        return "SELL", "PUT", reason

    # Near miss diagnostics
    diagnostics = []
    if not ((t == "BULLISH" and e == "BUY") or (t == "BEARISH" and e == "SELL")):
        diagnostics.append("Trend/EMA mismatch")
    if t == "BULLISH" and not bull_stack:
        diagnostics.append("EMA not bull-stacked")
    if t == "BEARISH" and not bear_stack:
        diagnostics.append("EMA not bear-stacked")
    if (t == "BULLISH" and disp_slope <= 0) or (t == "BEARISH" and disp_slope >= 0):
        diagnostics.append("Disparity slope not supportive")
    if not vol_spike:
        diagnostics.append("No volume spike")
    if (t == "BULLISH" and not bull_pcr_ok) or (t == "BEARISH" and not bear_pcr_ok):
        diagnostics.append("PCR outside tolerance")

    reason = " | ".join(diagnostics) if diagnostics else "No confluence"
    return "SIDEWAYS", None, reason


def build_response(
    mode: str,
    signal: str,
    option: str | None,
    reason: str,
    risk_target_pct: float = 0.30,
    risk_stop_pct: float = 0.20,
):
    return {
        "version": APP_VERSION,
        "mode": mode,
        "signal": signal,
        "suggested_option": option,
        "reason": reason,
        "risk": {
            "target_pct": risk_target_pct,
            "stop_pct": risk_stop_pct
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

# -------------------------
# API
# -------------------------

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "version": APP_VERSION})

@app.route("/api/signal", methods=["POST"])
def api_signal():
    """
    Request JSON:
    {
      "mode": "swing" | "scalp",
      "pcr": 1.06,
      "trend": "BULLISH" | "BEARISH",
      "ema_signal": "BUY" | "SELL",
      "ema_fast": 9.0, "ema_mid": 21.0, "ema_slow": 50.0,           # scalp mode
      "disparity": 0.8, "prev_disparity": 0.6,                      # scalp mode
      "volume": 120000, "avg_volume": 90000, "vol_mult": 1.2        # scalp mode (vol_mult optional)
    }
    """
    data = request.get_json(silent=True) or {}

    mode = (data.get("mode") or "scalp").strip().lower()
    pcr = float(data.get("pcr", 1.0))
    trend = data.get("trend", "")
    ema_signal = data.get("ema_signal", "")

    if mode == "swing":
        sig, opt, why = determine_swing_signal(pcr, trend, ema_signal)
        return jsonify(build_response("swing", sig, opt, why))

    # scalp (default)
    def _f(key):
        v = data.get(key, None)
        return float(v) if v is not None else None

    ema_fast = _f("ema_fast")
    ema_mid = _f("ema_mid")
    ema_slow = _f("ema_slow")
    disparity = _f("disparity")
    prev_disparity = _f("prev_disparity")
    volume = _f("volume")
    avg_volume = _f("avg_volume")
    vol_mult = float(data.get("vol_mult", 1.2))

    sig, opt, why = determine_scalp_signal(
        pcr, trend, ema_signal,
        ema_fast, ema_mid, ema_slow,
        disparity, prev_disparity,
        volume, avg_volume, vol_mult
    )
    return jsonify(build_response("scalp", sig, opt, why))

# -------------------------
# Minimal UI
# -------------------------

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Scalping Signal — Single-file</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font: 14px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #222; }
    h1 { font-size: 20px; margin-bottom: 12px; }
    fieldset { border: 1px solid #ddd; padding: 12px; margin-bottom: 16px; }
    label { display: block; margin: 6px 0 2px; }
    input, select { width: 220px; padding: 6px; }
    .row { display: flex; gap: 24px; flex-wrap: wrap; }
    button { padding: 8px 14px; cursor: pointer; }
    pre { background: #f7f7f7; padding: 12px; overflow: auto; }
    .signal { font-weight: 600; }
  </style>
</head>
<body>
  <h1>Scalping/Swing Signal</h1>
  <form id="f">
    <fieldset>
      <legend>Mode & core</legend>
      <label>Mode</label>
      <select name="mode">
        <option value="scalp" selected>scalp</option>
        <option value="swing">swing</option>
      </select>

      <label>PCR</label>
      <input name="pcr" type="number" step="0.01" value="1.06" />

      <label>Trend</label>
      <select name="trend">
        <option>BULLISH</option>
        <option>BEARISH</option>
      </select>

      <label>EMA signal</label>
      <select name="ema_signal">
        <option>BUY</option>
        <option>SELL</option>
      </select>
    </fieldset>

    <fieldset>
      <legend>Scalp-only inputs</legend>
      <div class="row">
        <div>
          <label>EMA fast</label>
          <input name="ema_fast" type="number" step="0.001" />
          <label>EMA mid</label>
          <input name="ema_mid" type="number" step="0.001" />
          <label>EMA slow</label>
          <input name="ema_slow" type="number" step="0.001" />
        </div>
        <div>
          <label>Disparity</label>
          <input name="disparity" type="number" step="0.001" />
          <label>Prev disparity</label>
          <input name="prev_disparity" type="number" step="0.001" />
          <label>Vol multiplier</label>
          <input name="vol_mult" type="number" step="0.01" value="1.2" />
        </div>
        <div>
          <label>Volume</label>
          <input name="volume" type="number" step="1" />
          <label>Avg volume</label>
          <input name="avg_volume" type="number" step="1" />
        </div>
      </div>
    </fieldset>

    <button type="submit">Get signal</button>
  </form>

  <h3>Response</h3>
  <pre id="out">{}</pre>

  <script>
    const form = document.getElementById('f');
    const out = document.getElementById('out');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const mode = fd.get('mode');

      const payload = {
        mode: mode,
        pcr: parseFloat(fd.get('pcr')),
        trend: fd.get('trend'),
        ema_signal: fd.get('ema_signal'),
      };

      if (mode === 'scalp') {
        const num = k => {
          const v = fd.get(k);
          return v ? parseFloat(v) : null;
        };
        payload.ema_fast = num('ema_fast');
        payload.ema_mid = num('ema_mid');
        payload.ema_slow = num('ema_slow');
        payload.disparity = num('disparity');
        payload.prev_disparity = num('prev_disparity');
        payload.volume = num('volume');
        payload.avg_volume = num('avg_volume');
        payload.vol_mult = num('vol_mult') ?? 1.2;
      }

      const res = await fetch('/api/signal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      out.textContent = JSON.stringify(json, null, 2);
    });
  </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

# -------------------------
# Local run (dev)
# -------------------------
if __name__ == "__main__":
    # For local testing; in cloud use gunicorn via Procfile
    app.run(host="0.0.0.0", port=8000, debug=False)
