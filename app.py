from flask import Flask, request, render_template_string, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import requests
import hashlib
import os
import time

app = Flask(__name__)
app.secret_key = "sajid_secret_key_change_this"

# ===== Configuration =====
MSTOCK_API_SECRET = '<your_api_secret_here>'

USERS_FILE = "users.txt"
CREDENTIALS_FILE = "user_credentials.txt"

def init_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            f.write("")
    if not os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'w') as f:
            f.write("")

init_files()

def save_user(username, password, email):
    with open(USERS_FILE, 'a') as f:
        hashed_pw = generate_password_hash(password)
        f.write(f"{username}|{hashed_pw}|{email}\n")

def get_user(username):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('|')
                if len(parts) >= 3 and parts[0] == username:
                    return {'username': parts[0], 'password': parts[1], 'email': parts[2]}
    return None

def verify_user(username, password):
    user = get_user(username)
    if user and check_password_hash(user['password'], password):
        return user
    return None

def save_user_credentials(username, mstock_api_key=None):
    credentials = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split('|')
                    if len(parts) >= 2:
                        credentials[parts[0]] = {'mstock_api_key': parts[1]}
    if username not in credentials:
        credentials[username] = {'mstock_api_key': ''}
    if mstock_api_key:
        credentials[username]['mstock_api_key'] = mstock_api_key
    with open(CREDENTIALS_FILE, 'w') as f:
        for user, creds in credentials.items():
            f.write(f"{user}|{creds['mstock_api_key']}\n")

def get_user_credentials(username):
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    with open(CREDENTIALS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('|')
                if len(parts) >= 2 and parts[0] == username:
                    return {'mstock_api_key': parts[1]}
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

user_sessions = {}

def get_user_session(username):
    if username not in user_sessions:
        user_sessions[username] = {
            'mstock_access_token': None,
            'mstock_access_token_expiry': None,
            'mstock_refresh_token': None,
            'mstock_refresh_token_expiry': None
        }
    return user_sessions[username]

@app.route("/mstock/login", methods=["POST"])
@login_required
def login_mstock():
    username = session['username']
    user_sess = get_user_session(username)
    creds = get_user_credentials(username)
    
    if not creds or not creds['mstock_api_key']:
        return jsonify({"status": "error", "message": "mStock API key not configured."}), 400
    
    totp = request.json.get("totp", "").strip()
    if not totp:
        return jsonify({"status": "error", "message": "OTP is required"}), 400
    
    checksum = hashlib.sha256(f"{creds['mstock_api_key']}{totp}{MSTOCK_API_SECRET}".encode()).hexdigest()
    headers = {'X-Mirae-Version': '1', 'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'api_key': creds['mstock_api_key'], 'totp': totp, 'checksum': checksum}
    
    try:
        response = requests.post(
            'https://api.mstock.trade/openapi/typea/session/verifytotp',
            headers=headers,
            data=data
        )
        resp_json = response.json()
        
        if resp_json.get("status") == "success":
            access_token = resp_json["data"]["access_token"]
            access_token_expiry = time.time() + resp_json["data"].get("expires_in", 3600)
            user_sess['mstock_access_token'] = access_token
            user_sess['mstock_access_token_expiry'] = access_token_expiry
            
            if "refresh_token" in resp_json["data"]:
                refresh_token = resp_json["data"]["refresh_token"]
                refresh_token_expiry = time.time() + resp_json["data"].get("refresh_token_expires_in", 86400)
                user_sess['mstock_refresh_token'] = refresh_token
                user_sess['mstock_refresh_token_expiry'] = refresh_token_expiry
                
            return jsonify({
                "status": "success",
                "message": "mStock Authentication successful",
                "access_token": access_token
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
@login_required
def mstock_status():
    username = session['username']
    user_sess = get_user_session(username)
    access_token = user_sess.get('mstock_access_token')
    
    if access_token and user_sess.get('mstock_access_token_expiry', 0) > time.time():
        return jsonify({"status": "authenticated"})
    else:
        return jsonify({"status": "not_authenticated"})

@app.route("/mstock/logout", methods=["POST"])
@login_required
def logout_mstock():
    username = session['username']
    user_sess = get_user_session(username)
    user_sess['mstock_access_token'] = None
    user_sess['mstock_access_token_expiry'] = None
    user_sess['mstock_refresh_token'] = None
    user_sess['mstock_refresh_token_expiry'] = None
    return jsonify({"status": "success", "message": "Logged out"})

# ✅ FIXED: Added request deduplication with unique request ID
order_request_cache = {}

@app.route("/place_order", methods=["POST"])
@login_required
def place_manual_order():
    """Handles Manual Order Placement via mStock with deduplication"""
    username = session['username']
    user_sess = get_user_session(username)
    creds = get_user_credentials(username)
    access_token = user_sess.get('mstock_access_token')
    
    if not access_token:
        return jsonify({
            "status": "error",
            "message": "mStock not authenticated. Please login with OTP."
        }), 403

    # ✅ DEDUPLICATION CHECK: Prevent duplicate requests
    request_id = request.headers.get('X-Request-ID', '')
    if request_id:
        current_time = time.time()
        if request_id in order_request_cache:
            cached_time = order_request_cache[request_id]
            if current_time - cached_time < 5:  # 5 second window
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
            'Authorization': f'token {creds["mstock_api_key"]}:{access_token}',
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
                "broker_response": resp_json,
                "side": transaction_type,
                "symbol": symbol
            }), 400
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Connection Error: {str(e)}"
        }), 500

@app.route('/sp', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        if not username or not password or not email:
            return render_template_string(SIGNUP_TEMPLATE, error="All fields are required!")
        if get_user(username):
            return render_template_string(SIGNUP_TEMPLATE, error="Username already exists!")
        save_user(username, password, email)
        return redirect(url_for('login_page'))
    return render_template_string(SIGNUP_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        user = verify_user(username, password)
        if user:
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials!")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    username = session.get('username')
    if username:
        user_sessions[username]['mstock_access_token'] = None
    session.clear()
    return redirect(url_for('login_page'))

@app.route("/setup_credentials", methods=["GET", "POST"])
@login_required
def setup_credentials():
    username = session['username']
    creds = get_user_credentials(username)
    if request.method == "POST":
        mstock_api_key = request.form.get("mstock_api_key")
        if mstock_api_key:
            save_user_credentials(username, mstock_api_key=mstock_api_key)
            return redirect(url_for('index'))
    return render_template_string(CREDENTIALS_TEMPLATE,
                                   mstock_api_key=creds['mstock_api_key'] if creds else "")

@app.route("/", methods=["GET"])
@login_required
def index():
    username = session['username']
    creds = get_user_credentials(username)
    return render_template_string(DASHBOARD_TEMPLATE, username=username, has_api_key=bool(creds and creds.get('mstock_api_key')))

# ===== HTML Templates =====

SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sign Up</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 350px; }
        h2 { text-align: center; color: #333; margin-bottom: 20px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0056b3; }
        .error { color: red; text-align: center; margin-bottom: 15px; font-size: 14px; }
        .link { text-align: center; margin-top: 20px; font-size: 14px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Create Account</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" minlength="6" required>
            <button type="submit">Sign Up</button>
        </form>
        <div class="link">Already have an account? <a href="/login">Login</a></div>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 350px; }
        h2 { text-align: center; color: #333; margin-bottom: 20px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0056b3; }
        .error { color: red; text-align: center; margin-bottom: 15px; font-size: 14px; }
        .link { text-align: center; margin-top: 20px; font-size: 14px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Login</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        <div class="link">Don't have an account? Contact Admin.</div>
    </div>
</body>
</html>
"""

CREDENTIALS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Setup mStock</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; padding: 40px; display: flex; justify-content: center; }
        .card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 500px; }
        h2 { color: #333; margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input { width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #218838; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Setup mStock Credentials</h2>
        <p style="color:#666; font-size:14px; margin-bottom:20px;">Enter your mStock API Key. The API Secret is hardcoded in the server configuration.</p>
        <form method="POST">
            <label>mStock API Key</label>
            <input type="text" name="mstock_api_key" value="{{ mstock_api_key }}" placeholder="e.g. 7x9..." required>
            <button type="submit">Save & Continue</button>
        </form>
    </div>
</body>
</html>
"""

# ✅ FIXED DASHBOARD TEMPLATE
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
        .nav-links a { color: var(--text-muted); text-decoration: none; margin-left: 20px; font-size: 0.9rem; transition: color 0.2s; }
        .nav-links a:hover { color: var(--text-main); }
        .user-badge { background: #333; padding: 5px 12px; border-radius: 20px; font-size: 0.85rem; }
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
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-muted); margin-top: 10px; }
        .btn-outline:hover { border-color: var(--text-main); color: var(--text-main); }
        
        /* ✅ CRITICAL FIX: Block clicks at CSS level when disabled */
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
        <div class="nav-links">
            <span class="user-badge">{{ username }}</span>
            <a href="/setup_credentials">Settings</a>
            <a href="/logout">Logout</a>
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
                    {% if not has_api_key %}
                        <a href="/setup_credentials" style="color: var(--danger); font-size: 0.8rem; text-decoration: none;">⚠️ API Key Missing</a>
                    {% endif %}
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

            <!-- ✅ FIX 1: Added onsubmit="return false;" to completely prevent form submission -->
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

                <!-- ✅ FIX 2: Removed onclick, will use addEventListener -->
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
                    <li>Ensure mStock API Key is set in <a href="/setup_credentials" style="color: var(--primary);">Settings</a>.</li>
                    <li>Authenticate using the OTP sent to your registered mobile/email.</li>
                    <li>Enter the correct Trading Symbol (e.g., RELIANCE, INFY, NIFTY25JAN24500CE).</li>
                    <li>Select Intraday (MIS) or Delivery (NRML).</li>
                </ul>
            </div>
        </section>
    </main>

    <div id="toast">Message here</div>

    <script>
        // ✅ FIX 3: Multiple layers of protection against double submission
        
        let currentSide = 'BUY';
        let isSubmitting = false;
        let lastClickTime = 0;
        const MIN_CLICK_INTERVAL = 2000; // 2 seconds minimum between clicks
        
        // ✅ FIX 4: Generate unique request ID for deduplication
        function generateRequestId() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
        }

        // --- Authentication Logic ---
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

        // --- UI Logic ---
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

        // --- Order Logic with Triple Protection ---
        async function placeOrder() {
            // ✅ PROTECTION LAYER 1: Timestamp-based throttle
            const now = Date.now();
            if (now - lastClickTime < MIN_CLICK_INTERVAL) {
                console.log("Click throttled. Too fast.");
                showToast('Please wait before clicking again', 'error');
                return;
            }
            lastClickTime = now;

            // ✅ PROTECTION LAYER 2: State lock check
            if (isSubmitting) {
                console.log("Request already in progress. Ignoring.");
                return;
            }

            // ✅ PROTECTION LAYER 3: Immediate button disable + CSS block
            isSubmitting = true;
            const btn = document.getElementById('submit-btn');
            const originalText = btn.innerText;
            
            btn.disabled = true;
            btn.classList.add('disabled'); // This adds pointer-events: none via CSS
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
                        'X-Request-ID': requestId  // ✅ Send unique ID for server-side dedup
                    },
                    body: JSON.stringify(formData)
                });
                const data = await res.json();

                if (data.status === 'success') {
                    addLog('ORDER', `${data.side} ${data.symbol} Qty: ${data.quantity} - ID: ${data.order_id}`, 'success');
                    showToast('Order Placed Successfully!', 'success');
                } else {
                    addLog('ERROR', `${data.side || formData.side} ${formData.symbol} - ${data.message}`, 'error');
                    showToast('Order Failed: ' + data.message, 'error');
                }
            } catch (err) {
                addLog('ERROR', 'Network Error: ' + err.message, 'error');
                showToast('Network Error', 'error');
            } finally {
                // ✅ Add delay before re-enabling to prevent rapid re-clicks
                setTimeout(() => {
                    isSubmitting = false;
                    btn.disabled = false;
                    btn.classList.remove('disabled');
                    btn.innerText = originalText;
                }, 1500); // 1.5 second cooldown
            }
        }

        // --- Logger ---
        function addLog(tag, message, type) {
            const container = document.getElementById('log-container');
            const time = new Date().toLocaleTimeString();
            
            const div = document.createElement('div');
            div.className = 'log-entry';
            
            let colorClass = 'log-info';
            if (type === 'success') colorClass = 'log-success';
            if (type === 'error') colorClass = 'log-error';

            div.innerHTML = `
                <span class="log-time">[${time}]</span>
                <strong>${tag}:</strong>
                <span class="${colorClass}">${message}</span>
            `;
            
            container.insertBefore(div, container.firstChild);
        }

        // --- Toast Notification ---
        function showToast(message, type) {
            const toast = document.getElementById("toast");
            toast.innerText = message;
            toast.className = "show " + type;
            setTimeout(function(){ toast.className = toast.className.replace("show", ""); }, 3000);
        }

        // ✅ FIX 5: Use addEventListener instead of inline onclick
        // This ensures only ONE event handler is attached
        document.addEventListener('DOMContentLoaded', function() {
            
            // Order button - with all event prevention
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                placeOrder();
            });
            
            // Prevent any other click handlers on the button
            submitBtn.addEventListener('click', function(e) {
                e.stopImmediatePropagation();
            }, true); // Capture phase

            // Side toggle buttons
            document.getElementById('opt-buy').addEventListener('click', function(e) {
                e.preventDefault();
                setSide('BUY');
            });
            
            document.getElementById('opt-sell').addEventListener('click', function(e) {
                e.preventDefault();
                setSide('SELL');
            });

            // Order type change
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

            // OTP button
            document.getElementById('otp-btn').addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                authenticate();
            });

            // Prevent form submission by any means
            document.getElementById('order-form').addEventListener('submit', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            }, true);

            // Initialize
            checkAuthStatus();
            setInterval(checkAuthStatus, 60000);
            
            addLog('System', 'Terminal initialized with double-click protection.', 'info');
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*60)
    print("🚀 mStock Manual Trading Terminal")
    print("="*60)
    print(f"📍 Server: http://127.0.0.1:{port}")
    print("📝 Users stored in: users.txt")
    print("🔑 Credentials stored in: user_credentials.txt")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
