
from flask import Flask, request, render_template_string, jsonify
import requests
import hashlib
import os
import time

app = Flask(__name__)
app.secret_key = "single_user_terminal_key"

# ===== Hardcoded Configuration =====
MSTOCK_API_KEY = CJOHJvQ/lUBtRZSXIVAtd3wkLRaSDpVGbO92K+FAIo8='  # Replace with your actual mStock API Key
MSTOCK_API_SECRET = 'CJOHJvQ/lUBtRZSXIVAtd3wkLRaSDpVGbO92K+FAIo8='

# Global mStock session for single user
mstock_session = {
    'access_token': None,
    'access_token_expiry': None,
    'refresh_token': None,
    'refresh_token_expiry': None
}

# Server-side deduplication cache
order_request_cache = {}

# ===== mStock Authentication Routes =====

@app.route("/mstock/login", methods=["POST"])
def login_mstock():
    if not MSTOCK_API_KEY or MSTOCK_API_KEY == '<PASTE_YOUR_API_KEY_HERE>':
        return jsonify({"status": "error", "message": "API Key not configured in script."}), 400
    
    totp = request.json.get("totp", "").strip()
    if not totp:
        return jsonify({"status": "error", "message": "OTP is required"}), 400
    
    checksum = hashlib.sha256(f"{MSTOCK_API_KEY}{totp}{MSTOCK_API_SECRET}".encode()).hexdigest()
    headers = {'X-Mirae-Version': '1', 'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'api_key': MSTOCK_API_KEY, 'totp': totp, 'checksum': checksum}
    
    try:
        response = requests.post(
            'https://api.mstock.trade/openapi/typea/session/verifytotp',
            headers=headers,
            data=data
        )
        resp_json = response.json()
        
        if resp_json.get("status") == "success":
            mstock_session['access_token'] = resp_json["data"]["access_token"]
            mstock_session['access_token_expiry'] = time.time() + resp_json["data"].get("expires_in", 3600)
            
            if "refresh_token" in resp_json["data"]:
                mstock_session['refresh_token'] = resp_json["data"]["refresh_token"]
                mstock_session['refresh_token_expiry'] = time.time() + resp_json["data"].get("refresh_token_expires_in", 86400)
                
            return jsonify({
                "status": "success",
                "message": "mStock Authentication successful",
                "access_token": mstock_session['access_token']
            })
        else:
            return jsonify({
                "status": "error",
                "message": resp_json.get("message", "Failed to generate session")
            }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error verifying OTP: {str(e)}"
        }), 500

@app.route("/mstock/status", methods=["GET"])
def mstock_status():
    access_token = mstock_session.get('access_token')
    
    if access_token and mstock_session.get('access_token_expiry', 0) > time.time():
        return jsonify({"status": "authenticated"})
    else:
        return jsonify({"status": "not_authenticated"})

@app.route("/mstock/logout", methods=["POST"])
def logout_mstock():
    mstock_session['access_token'] = None
    mstock_session['access_token_expiry'] = None
    mstock_session['refresh_token'] = None
    mstock_session['refresh_token_expiry'] = None
    return jsonify({"status": "success", "message": "Logged out"})

# ===== Manual Order Placement with Deduplication =====

@app.route("/place_order", methods=["POST"])
def place_manual_order():
    access_token = mstock_session.get('access_token')
    
    if not access_token:
        return jsonify({
            "status": "error",
            "message": "mStock not authenticated. Please login with OTP."
        }), 403

    # DEDUPLICATION CHECK: Prevent duplicate requests
    request_id = request.headers.get('X-Request-ID', '')
    if request_id:
        current_time = time.time()
        if request_id in order_request_cache:
            if current_time - order_request_cache[request_id] < 5: 
                return jsonify({
                    "status": "error",
                    "message": "Duplicate request detected. Please wait.",
                    "duplicate": True
                }), 429
        order_request_cache[request_id] = current_time
        
        # Clean old entries
        expired = [k for k, v in order_request_cache.items() if current_time - v > 10]
        for k in expired:
            del order_request_cache[k]

    data = request.json
    symbol = data.get('symbol', '').strip().upper()
    transaction_type = data.get('side', 'BUY').upper()
    quantity = int(data.get('quantity', 1))
    order_type = data.get('order_type', 'MARKET').upper()
    price = float(data.get('price', 0))
    exchange = data.get('exchange', 'NSE').upper()
    product = data.get('product', 'MIS').upper()

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol is required"}), 400

    payload = {
        'tradingsymbol': symbol,
        'exchange': exchange,
        'transaction_type': transaction_type,
        'order_type': order_type,
        'quantity': quantity,
        'product': product,
        'validity': 'DAY',
        'price': price if order_type == 'LIMIT' else 0,
        'variety': 'regular'
    }

    try:
        headers = {
            'X-Mirae-Version': '1',
            'Authorization': f'token {MSTOCK_API_KEY}:{access_token}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        response = requests.post(
            f'https://api.mstock.trade/openapi/typea/orders/regular',
            headers=headers,
            data=payload
        )
        
        resp_json = response.json()
        
        if resp_json.get("status") == "success":
            order_id = resp_json.get("data", {}).get("orderid")
            return jsonify({
                "status": "success",
                "message": f"Order Placed Successfully! ID: {order_id}",
                "order_id": order_id,
                "side": transaction_type,
                "symbol": symbol,
                "quantity": quantity
            })
        else:
            error_msg = resp_json.get("message", "Unknown error from broker")
            if "data" in resp_json and isinstance(resp_json["data"], list):
                error_msg = resp_json["data"][0].get("message", error_msg)
                
            return jsonify({
                "status": "error",
                "message": f"Order Failed: {error_msg}",
                "side": transaction_type,
                "symbol": symbol
            }), 400
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Connection Error: {str(e)}"
        }), 500

# ---- General Routes ----

@app.route("/", methods=["GET"])
def index():
    return render_template_string(DASHBOARD_TEMPLATE)

# ===== HTML Template =====

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mStock Manual Terminal</title>
    <style>
        :root {
            --bg-dark: #121212;
            --bg-card: #1e1e1e;
            --bg-input: #2c2c2c;
            --text-main: #e0e0e0;
            --text-muted: #a0a0a0;
            --accent: #00e676;
            --danger: #ff5252;
            --primary: #2979ff;
            --border: #333;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: var(--bg-dark); color: var(--text-main); display: flex; flex-direction: column; min-height: 100vh; }
        header { background-color: var(--bg-card); padding: 15px 30px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .brand { font-size: 1.2rem; font-weight: bold; display: flex; align-items: center; gap: 10px; }
        .brand span { color: var(--accent); }
        main { flex: 1; padding: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 30px; max-width: 1400px; margin: 0 auto; width: 100%; }
        @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
        .card { background-color: var(--bg-card); border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; flex-direction: column; }
        .card h2 { margin-bottom: 20px; font-weight: 600; font-size: 1.2rem; border-left: 4px solid var(--accent); padding-left: 10px; }
        #auth-section { margin-bottom: 20px; }
        .status-indicator { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #555; margin-right: 8px; }
        .status-indicator.active { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
        .status-text { font-size: 0.9rem; color: var(--text-muted); }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-size: 0.85rem; color: var(--text-muted); }
        input, select { width: 100%; padding: 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; color: white; font-size: 1rem; outline: none; transition: border 0.2s; }
        input:focus, select:focus { border-color: var(--primary); }
        .row { display: flex; gap: 15px; }
        .col { flex: 1; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 1rem; transition: opacity 0.2s; width: 100%; }
        .btn:hover { opacity: 0.9; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-buy { background: var(--accent); color: #000; }
        .btn-sell { background: var(--danger); color: white; }
        .btn.disabled, .btn:disabled {
            opacity: 0.5 !important;
            cursor: not-allowed !important;
            pointer-events: none !important;
        }
        .toggle-container { display: flex; background: var(--bg-input); border-radius: 6px; padding: 4px; margin-bottom: 15px; }
        .toggle-option { flex: 1; text-align: center; padding: 10px; cursor: pointer; border-radius: 4px; transition: 0.3s; font-weight: 600; font-size: 0.9rem; }
        .toggle-option.active-buy { background: var(--accent); color: black; }
        .toggle-option.active-sell { background: var(--danger); color: white; }
        .log-container { flex: 1; overflow-y: auto; max-height: 400px; background: #000; border-radius: 6px; padding: 15px; font-family: 'Courier New', monospace; font-size: 0.85rem; border: 1px solid var(--border); }
        .log-entry { margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #222; }
        .log-time { color: #666; font-size: 0.75rem; margin-right: 10px; }
        .log-success { color: var(--accent); }
        .log-error { color: var(--danger); }
        .log-info { color: var(--primary); }
        .otp-form { background: #252525; padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid var(--primary); }
        #toast { visibility: hidden; min-width: 250px; background-color: #333; color: #fff; text-align: center; border-radius: 4px; padding: 16px; position: fixed; z-index: 1; left: 50%; bottom: 30px; transform: translateX(-50%); box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        #toast.show { visibility: visible; animation: fadein 0.5s, fadeout 0.5s 2.5s; }
        #toast.success { border-left: 5px solid var(--accent); }
        #toast.error { border-left: 5px solid var(--danger); }
        @keyframes fadein { from {bottom: 0; opacity: 0;} to {bottom: 30px; opacity: 1;} }
        @keyframes fadeout { from {bottom: 30px; opacity: 1;} to {bottom: 0; opacity: 0;} }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            mStock <span>Manual Terminal</span>
        </div>
    </header>

    <main>
        <section class="card">
            <h2>Order Entry</h2>
            
            <div id="auth-section">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="status-indicator" id="auth-dot"></span>
                        <span class="status-text" id="auth-text">Checking...</span>
                    </div>
                </div>
                <div id="otp-area" class="otp-form" style="display: none;">
                    <label>Enter OTP (mStock)</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="totp-input" placeholder="6-digit OTP" maxlength="6" style="text-align: center; letter-spacing: 5px; font-weight: bold;">
                        <button class="btn btn-primary" style="width: auto;" id="otp-btn">Login</button>
                    </div>
                    <div id="otp-msg" style="font-size: 0.8rem; margin-top: 5px; color: #aaa;"></div>
                </div>
            </div>

            <hr style="border: 0; border-top: 1px solid var(--border); margin: 20px 0;">

            <form id="order-form" onsubmit="return false;">
                <div class="form-group">
                    <label>Symbol (Trading Symbol)</label>
                    <input type="text" id="symbol" name="symbol" placeholder="e.g. NIFTY25JAN24500CE" required value="NIFTY25JAN24500CE">
                    <small style="color: #666; font-size: 0.75rem;">Use exact exchange symbol format</small>
                </div>

                <div class="row">
                    <div class="col">
                        <div class="form-group">
                            <label>Exchange</label>
                            <select id="exchange" name="exchange">
                                <option value="NSE">NSE</option>
                                <option value="NFO" selected>NFO</option>
                                <option value="BSE">BSE</option>
                                <option value="MCX">MCX</option>
                            </select>
                        </div>
                    </div>
                    <div class="col">
                        <div class="form-group">
                            <label>Product</label>
                            <select id="product" name="product">
                                <option value="MIS" selected>Intraday (MIS)</option>
                                <option value="NRML">Delivery (NRML)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div class="form-group">
                    <label>Side</label>
                    <div class="toggle-container">
                        <div class="toggle-option active-buy" id="opt-buy">BUY</div>
                        <div class="toggle-option" id="opt-sell">SELL</div>
                    </div>
                    <input type="hidden" id="side" name="side" value="BUY">
                </div>

                <div class="row">
                    <div class="col">
                        <div class="form-group">
                            <label>Order Type</label>
                            <select id="order_type" name="order_type">
                                <option value="MARKET">MARKET</option>
                                <option value="LIMIT">LIMIT</option>
                            </select>
                        </div>
                    </div>
                    <div class="col">
                        <div class="form-group">
                            <label>Quantity</label>
                            <input type="number" id="quantity" name="quantity" value="50" min="1" required>
                        </div>
                    </div>
                </div>

                <div class="form-group" id="price-group" style="display: none;">
                    <label>Price</label>
                    <input type="number" id="price" name="price" step="0.05" value="0">
                </div>

                <button type="button" id="submit-btn" class="btn btn-buy">PLACE BUY ORDER</button>
            </form>
        </section>

        <section class="card">
            <h2>Activity Log</h2>
            <div class="log-container" id="log-container">
                <div class="log-entry">
                    <span class="log-time">System</span>
                    <span class="log-info">Terminal initialized. Waiting for connection...</span>
                </div>
            </div>
            <div style="margin-top: 20px; font-size: 0.85rem; color: #666; line-height: 1.5;">
                <strong>Instructions:</strong>
                <ul style="margin-left: 20px; margin-top: 5px;">
                    <li>Authenticate using the OTP sent to your registered mobile/email.</li>
                    <li>Enter the correct Trading Symbol (e.g., RELIANCE, INFY, NIFTY25JAN24500CE).</li>
                    <li>Select Intraday (MIS) or Delivery (NRML).</li>
                </ul>
            </div>
        </section>
    </main>

    <div id="toast">Message here</div>

    <script>
        let currentSide = 'BUY';
        let isSubmitting = false;
        let lastClickTime = 0;
        const MIN_CLICK_INTERVAL = 2000;
        
        function generateRequestId() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
        }

        async function checkAuthStatus() {
            try {
                const res = await fetch('/mstock/status');
                const data = await res.json();
                
                const dot = document.getElementById('auth-dot');
                const text = document.getElementById('auth-text');
                const otpArea = document.getElementById('otp-area');

                if (data.status === 'authenticated') {
                    dot.classList.add('active');
                    text.innerText = 'Connected to mStock';
                    text.style.color = 'var(--accent)';
                    otpArea.style.display = 'none';
                } else {
                    dot.classList.remove('active');
                    text.innerText = 'Not Authenticated';
                    text.style.color = 'var(--danger)';
                    otpArea.style.display = 'block';
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function authenticate() {
            const totp = document.getElementById('totp-input').value;
            const msg = document.getElementById('otp-msg');
            const btn = document.getElementById('otp-btn');
            
            if (!totp || totp.length !== 6) {
                msg.innerText = "Please enter a valid 6-digit OTP.";
                msg.style.color = "var(--danger)";
                return;
            }

            msg.innerText = "Verifying...";
            msg.style.color = "#aaa";
            btn.disabled = true;
            btn.classList.add('disabled');

            try {
                const res = await fetch('/mstock/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ totp: totp })
                });
                const data = await res.json();

                if (data.status === 'success') {
                    msg.innerText = "Success!";
                    msg.style.color = "var(--accent)";
                    showToast('Logged in successfully!', 'success');
                    checkAuthStatus();
                } else {
                    msg.innerText = "Failed: " + data.message;
                    msg.style.color = "var(--danger)";
                    showToast('Login Failed', 'error');
                }
            } catch (e) {
                msg.innerText = "Error connecting to server.";
                msg.style.color = "var(--danger)";
            } finally {
                btn.disabled = false;
                btn.classList.remove('disabled');
            }
        }

        function setSide(side) {
            currentSide = side;
            document.getElementById('side').value = side;
            const btn = document.getElementById('submit-btn');
            const optBuy = document.getElementById('opt-buy');
            const optSell = document.getElementById('opt-sell');

            if (side === 'BUY') {
                btn.className = 'btn btn-buy';
                btn.innerText = 'PLACE BUY ORDER';
                optBuy.classList.add('active-buy');
                optSell.classList.remove('active-sell');
            } else {
                btn.className = 'btn btn-sell';
                btn.innerText = 'PLACE SELL ORDER';
                optBuy.classList.remove('active-buy');
                optSell.classList.add('active-sell');
            }
        }

        async function placeOrder() {
            const now = Date.now();
            if (now - lastClickTime < MIN_CLICK_INTERVAL) {
                showToast('Please wait before clicking again', 'error');
                return;
            }
            lastClickTime = now;

            if (isSubmitting) {
                return;
            }

            isSubmitting = true;
            const btn = document.getElementById('submit-btn');
            const originalText = btn.innerText;
            
            btn.disabled = true;
            btn.classList.add('disabled');
            btn.innerText = "PROCESSING...";

            const requestId = generateRequestId();

            const formData = {
                symbol: document.getElementById('symbol').value,
                exchange: document.getElementById('exchange').value,
                product: document.getElementById('product').value,
                side: currentSide,
                order_type: document.getElementById('order_type').value,
                quantity: parseInt(document.getElementById('quantity').value),
                price: parseFloat(document.getElementById('price').value)
            };

            try {
                const res = await fetch('/place_order', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Request-ID': requestId
                    },
                    body: JSON.stringify(formData)
                });
                const data = await res.json();

                if (data.status === 'success') {
                    addLog('ORDER', `${data.side} ${data.symbol} Qty: ${data.quantity} - ID: ${data.order_id}`, 'success');
                    showToast('Order Placed Successfully!', 'success');
                } else {
                    addLog('ERROR', `${formData.side} ${formData.symbol} - ${data.message}`, 'error');
                    showToast('Order Failed: ' + data.message, 'error');
                }
            } catch (err) {
                addLog('ERROR', 'Network Error: ' + err.message, 'error');
                showToast('Network Error', 'error');
            } finally {
                setTimeout(() => {
                    isSubmitting = false;
                    btn.disabled = false;
                    btn.classList.remove('disabled');
                    btn.innerText = originalText;
                }, 1500);
            }
        }

        function addLog(tag, message, type) {
            const container = document.getElementById('log-container');
            const time = new Date().toLocaleTimeString();
            const div = document.createElement('div');
            div.className = 'log-entry';
            let colorClass = 'log-info';
            if (type === 'success') colorClass = 'log-success';
            if (type === 'error') colorClass = 'log-error';
            div.innerHTML = `<span class="log-time">[${time}]</span><strong>${tag}:</strong> <span class="${colorClass}">${message}</span>`;
            container.insertBefore(div, container.firstChild);
        }

        function showToast(message, type) {
            const toast = document.getElementById("toast");
            toast.innerText = message;
            toast.className = "show " + type;
            setTimeout(function(){ toast.className = toast.className.replace("show", ""); }, 3000);
        }

        document.addEventListener('DOMContentLoaded', function() {
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                placeOrder();
            });
            
            submitBtn.addEventListener('click', function(e) {
                e.stopImmediatePropagation();
            }, true);

            document.getElementById('opt-buy').addEventListener('click', function(e) {
                e.preventDefault();
                setSide('BUY');
            });
            
            document.getElementById('opt-sell').addEventListener('click', function(e) {
                e.preventDefault();
                setSide('SELL');
            });

            document.getElementById('order_type').addEventListener('change', function() {
                const type = this.value;
                const priceGroup = document.getElementById('price-group');
                const priceInput = document.getElementById('price');
                if (type === 'LIMIT') {
                    priceGroup.style.display = 'block';
                    priceInput.required = true;
                    priceInput.value = '';
                    priceInput.focus();
                } else {
                    priceGroup.style.display = 'none';
                    priceInput.required = false;
                    priceInput.value = 0;
                }
            });

            document.getElementById('otp-btn').addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                authenticate();
            });

            document.getElementById('order-form').addEventListener('submit', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            }, true);

            checkAuthStatus();
            setInterval(checkAuthStatus, 60000);
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*60)
    print("mStock Manual Trading Terminal (Hardcoded)")
    print("="*60)
    print(f"Server: http://127.0.0.1:{port}")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
