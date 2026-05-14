import logging
import uuid  # <--- Added import to generate unique session IDs
from flask import Flask, render_template_string, request, session, jsonify, redirect, url_for
from tradingapi_a.mconnect import MConnect
import pandas as pd

# ==========================================
# CONFIGURATION
# ==========================================
app = Flask(__name__)
# Secret key for Flask session encryption
app.secret_key = 'super_secret_key_change_this_in_production'

# Hardcoded API Key as requested
API_KEY = "CJOHJvQ/lUBtRZSXIVAtd3wkLRaSDpVGbO92K+FAIo8="

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# ==========================================
# SESSION MANAGEMENT (MEMORY STORE)
# ==========================================
ACTIVE_SESSIONS = {}

# ==========================================
# HTML TEMPLATE
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>m.Stock Live Positions</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; margin-bottom: 30px; }
        
        /* Form Styles */
        .login-box { max-width: 400px; margin: 50px auto; text-align: center; }
        input[type="text"], input[type="password"] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button.btn-primary { width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button.btn-primary:hover { background-color: #0056b3; }
        button.btn-logout { background-color: #dc3545; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; float: right; }
        
        /* Table Styles */
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; color: #555; font-weight: 600; }
        tr:hover { background-color: #f1f1f1; }
        
        /* Utility */
        .hidden { display: none; }
        .error { color: red; text-align: center; margin-top: 10px; }
        .success { color: green; text-align: center; margin-top: 10px; }
        .api-key-display { font-size: 12px; color: #888; text-align: center; margin-top: 5px; word-break: break-all;}
    </style>
</head>
<body>

    {% if not session.get('logged_in') %}
    <!-- LOGIN SECTION -->
    <div class="container login-box">
        <h2>m.Stock Login</h2>
        <div class="api-key-display">API Key: {{ api_key }}</div>
        
        <form method="POST" action="/login">
            <div class="form-group">
                <input type="text" name="totp" placeholder="Enter OTP" required autocomplete="off">
            </div>
            <button type="submit" class="btn-primary">Verify OTP & Login</button>
        </form>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
    </div>

    {% else %}
    <!-- DASHBOARD SECTION -->
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Live Net Positions</h2>
            <form action="/logout" method="POST">
                <button type="submit" class="btn-logout">Logout</button>
            </form>
        </div>

        <div id="loading" style="text-align: center; padding: 20px;">Loading positions...</div>

        <table id="position-table" class="hidden">
            <thead>
                <tr>
                    <th>Trading Symbol</th>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Avg Price</th>
                    <th>LTP</th>
                    <th>P&L</th>
                </tr>
            </thead>
            <tbody id="position-body">
                <!-- Rows will be injected here -->
            </tbody>
        </table>
    </div>
    {% endif %}

    <script>
        // Auto-refresh logic if logged in
        {% if session.get('logged_in') %}
        async function fetchPositions() {
            try {
                const response = await fetch('/api/positions');
                const data = await response.json();
                
                const tbody = document.getElementById('position-body');
                const table = document.getElementById('position-table');
                const loading = document.getElementById('loading');
                
                tbody.innerHTML = ''; // Clear existing rows

                if (data.error) {
                    loading.innerText = "Error: " + data.error;
                    loading.classList.remove('hidden');
                    table.classList.add('hidden');
                    return;
                }

                if (data.length === 0) {
                    loading.innerText = "No open positions found.";
                    loading.classList.remove('hidden');
                    table.classList.add('hidden');
                    return;
                }

                loading.classList.add('hidden');
                table.classList.remove('hidden');

                data.forEach(pos => {
                    const row = document.createElement('tr');
                    
                    // Calculate P&L for display
                    const qty = parseFloat(pos.quantity);
                    const ltp = parseFloat(pos.ltp);
                    const avg = parseFloat(pos.avg_price);
                    const pnl = qty * (ltp - avg);
                    const pnlColor = pnl >= 0 ? 'green' : 'red';

                    row.innerHTML = `
                        <td>${pos.trading_symbol || '-'}</td>
                        <td>${pos.product || '-'}</td>
                        <td>${pos.quantity || '0'}</td>
                        <td>${pos.avg_price || '0.00'}</td>
                        <td>${pos.ltp || '0.00'}</td>
                        <td style="color:${pnlColor}; font-weight:bold;">${pnl.toFixed(2)}</td>
                    `;
                    tbody.appendChild(row);
                });

            } catch (err) {
                console.error("Fetch error:", err);
                document.getElementById('loading').innerText = "Failed to connect to server.";
            }
        }

        // Fetch immediately and then every 3 seconds
        fetchPositions();
        setInterval(fetchPositions, 3000);
        {% endif %}
    </script>
</body>
</html>
"""

# ==========================================
# ROUTES
# ==========================================

@app.route("/", methods=["GET"])
def index():
    """Render the main page."""
    return render_template_string(HTML_TEMPLATE, api_key=API_KEY)

@app.route("/login", methods=["POST"])
def login():
    """Handle OTP Login using SDK."""
    totp = request.form.get("totp", "").strip()
    
    if not totp:
        return render_template_string(HTML_TEMPLATE, api_key=API_KEY, error="OTP is required.")

    try:
        # Create a new MConnect instance
        mconnect_obj = MConnect()
        
        # Verify TOTP using the Hardcoded API Key
        logging.info(f"Attempting login with Key: {API_KEY}")
        res = mconnect_obj.verify_totp(API_KEY, totp)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                # 1. Mark Flask session as logged in
                session['logged_in'] = True
                
                # 2. FIX: Generate a unique ID manually because Flask session doesn't have .sid
                unique_sid = str(uuid.uuid4())
                session['sid'] = unique_sid 
                
                # 3. Store the mconnect_obj in our global memory dictionary using this unique ID
                ACTIVE_SESSIONS[unique_sid] = mconnect_obj
                
                return redirect(url_for('index'))
            else:
                return render_template_string(HTML_TEMPLATE, api_key=API_KEY, error=data.get("message", "Login Failed"))
        else:
            return render_template_string(HTML_TEMPLATE, api_key=API_KEY, error=f"HTTP Error: {res.status_code}")

    except Exception as e:
        logging.exception("Login Error")
        return render_template_string(HTML_TEMPLATE, api_key=API_KEY, error=str(e))

@app.route("/logout", methods=["POST"])
def logout():
    """Logout and clear session."""
    # Retrieve the ID we stored in session
    sid = session.get('sid')
    if sid and sid in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[sid]
    
    session.clear()
    return redirect(url_for('index'))

@app.route("/api/positions")
def get_positions():
    """API Endpoint to fetch live positions using the stored SDK object."""
    if 'logged_in' not in session or 'sid' not in session:
        return jsonify({"error": "Not logged in"})

    # Retrieve the ID from session
    sid = session['sid']
    mconnect_obj = ACTIVE_SESSIONS.get(sid)

    if not mconnect_obj:
        return jsonify({"error": "Session expired. Please login again."})

    try:
        # Use the stored object to call the SDK method
        res = mconnect_obj.get_net_position()
        
        if res.status_code == 200:
            data = res.json()
            # Handle different response structures from the API
            if isinstance(data, dict) and 'data' in data:
                return jsonify(data['data'])
            elif isinstance(data, list):
                return jsonify(data)
            else:
                return jsonify(data)
        else:
            return jsonify({"error": f"API Error: {res.status_code}"})
            
    except Exception as e:
        logging.exception("Fetch Position Error")
        return jsonify({"error": str(e)})

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
