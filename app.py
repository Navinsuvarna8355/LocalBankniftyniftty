from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# Health check
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "LocalBankInfinity backend running 🚀"
    })

# Example POST endpoint
@app.route("/api/signal", methods=["POST"])
def signal():
    data = request.get_json(force=True)
    input_value = data.get("value", "no-data")

    # Example external call (replace with your logic)
    # r = requests.get("https://api.example.com/data")
    # external_data = r.json()

    return jsonify({
        "input": input_value,
        "processed": f"Signal processed for {input_value}"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
