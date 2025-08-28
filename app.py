from flask import Flask, request, jsonify, render_template_string
import random
from datetime import datetime

# ---------------------------------
# Flask App Init
# ---------------------------------
app = Flask(__name__)

# ---------------------------------
# Inline Frontend HTML + JS
# ---------------------------------
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Strategy Signal Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f7f7f7; padding: 20px; }
        h1 { color: #333; }
        #result { margin-top: 20px; padding: 10px; background: #fff; border-radius: 4px; min-height: 30px; }
        button { padding: 8px 16px; cursor: pointer; margin-top: 10px; }
        footer { margin-top: 30px; font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <h1>Strategy Signal Dashboard</h1>
    <button onclick="fetchSignal()">Get Signal</button>
    <div id="result">Click the button to fetch a signal...</div>

    <footer>
        Powered by Flask | Last updated: <span id="time"></span>
    </footer>

    <script>
        document.getElementById("time").innerText = new Date().toLocaleString();

        async function fetchSignal() {
            document.getElementById("result").innerText = "Loading...";
            try {
                let res = await fetch("/signal", { method: "POST" });
                let data = await res.json();
                document.getElementById("result").innerText =
                    "Signal: " + data.signal + " | Time: " + data.time;
            } catch (err) {
                document.getElementById("result").innerText = "Error fetching signal";
            }
        }
    </script>
</body>
</html>
"""

# ---------------------------------
# Routes
# ---------------------------------
@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/signal", methods=["POST"])
def get_signal():
    """
    This is the backend logic route.
    Replace the random.choice() with your actual trading strategy logic.
    """
    signal = random.choice(["BUY", "SELL", "HOLD"])
    return jsonify({
        "signal": signal,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ---------------------------------
# Entry Point for Local Run
# ---------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
