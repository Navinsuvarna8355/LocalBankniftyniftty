from flask import Flask, jsonify, request
from flask_cors import CORS
import requests  # optional use for API calls

app = Flask(__name__)
CORS(app)

# Health check endpoint
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "LocalBankInfinity backend running 🚀"
    })

# Example POST endpoint
@app.route("/api/signal", methods=["POST"])
def signal():
    data = request.get_json(force=True) or {}
    value = data.get("value", "no-data")
    # Example if you need to call an external API:
    # r = requests.get("https://api.example.com/data")
    # external_data = r.json()
    return jsonify({
        "input": value,
        "processed": f"Signal processed for {value}"
    })

if __name__ == "__main__":
    # Local dev server
    app.run(host="0.0.0.0", port=5000)
