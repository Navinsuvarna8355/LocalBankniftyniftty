from flask import Flask, jsonify
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app)

# Helper to get current IST timestamp string
def ist_now():
    return datetime.datetime.utcnow().astimezone(
        datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ).strftime("%Y-%m-%d %H:%M:%S")

# Root health check
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "LocalBankInfinity backend running 🚀",
        "timestamp": ist_now()
    })

# Strategy signal endpoints
@app.route("/strategy/signal/NIFTY", methods=["GET"])
def signal_nifty():
    return jsonify({
        "index": "NIFTY",
        "signal": "SIDEWAYS",
        "live_price": 19412.2,
        "trend": "BEARISH",
        "strategy": "EMA Crossover + PCR (option chain)",
        "pcr_spot": 1.06,
        "max_pain": 19400,
        "pcr_oi": 1.04,
        "expiry": "24-Aug-2023",
        "timestamp": ist_now()
    })

@app.route("/strategy/signal/BANKNIFTY", methods=["GET"])
def signal_banknifty():
    return jsonify({
        "index": "BANKNIFTY",
        "signal": "SIDEWAYS",
        "live_price": 44502.1,
        "trend": "BEARISH",
        "strategy": "EMA Crossover + PCR (option chain)",
        "pcr_spot": 1.08,
        "max_pain": 44500,
        "pcr_oi": 1.06,
        "expiry": "24-Aug-2023",
        "timestamp": ist_now()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
