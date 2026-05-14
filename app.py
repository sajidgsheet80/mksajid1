Here is the updated code with the **Place Order** functionality integrated.

**Using "Intelligence" (SDK vs Raw Requests):**
I noticed your snippet uses raw `requests.post` and manual access token handling. However, since we already have the `mconnect_obj` stored in the session (which handles authentication internally), it is much more robust and cleaner to use the SDK's built-in `place_order` method. This ensures tokens are managed correctly by the library.

I have added a **Place Order Tab** with a form pre-filled with the values from your snippet (NIFTY Option, AMO, etc.).

Save this as `app.py` and run.

```python
import logging
import uuid
from flask import Flask, render_template_string, request, session, jsonify, redirect, url_for
from tradingapi_a.mconnect import MConnect
import pandas as pd

# ==========================================
# CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = 'super_secret_key_change_this_in_production'

# Hardcoded API Key
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
    <title>m.Stock Trading Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; margin-bottom: 20px; }
        
        /* Form Styles */
        .login-box { max-width: 400px; margin: 50px auto; text-align: center; }
        input[type="text"], input[type="password"], input[type="number"], select { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button.btn-primary { width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button.btn-primary:hover { background-color: #0056b3; }
        button.btn-logout { background-color: #dc3545; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; float: right; }
        
        /* Place Order Form */
        .order-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .full-width { grid-column: span 2; }
        .btn-place { background-color: #28a745; color: white; width: 100%; padding: 15px; font-size: 18px; border: none; border-radius: 5px; cursor: pointer; margin-top: 20px; }
        .btn-place:hover { background-color: #218838; }
        
        /* Tab Styles */
        .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; }
        .tab-btn { padding: 10px 20px; background: none; border: none; font-size: 16px; cursor: pointer; color: #555; border-bottom: 3px solid transparent; transition: all 0.3s; }
        .tab-btn:hover { color: #007bff; }
        .tab-btn.active { color: #007bff; border-bottom: 3px solid #007bff; font-weight: bold; }

        /* Table Styles */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; color: #555; font-weight: 600; }
        tr:hover { background-color: #f1f1f1; }
        
        /* JSON Output Styles */
        pre { background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 13px; margin-top: 10px; }
        
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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="margin:0;">Trading Dashboard</h2>
            <form action="/logout" method="POST" style="margin:0;">
                <button type="submit" class="btn-logout">Logout</button>
            </form>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('positions')" id="btn-positions">Net Positions</button>
            <button class="tab-btn" onclick="switchTab('orders')" id="btn-orders">Order Book</button>
            <button class="tab-btn" onclick="switchTab('trades')" id="btn-trades">Trade Book</button>
            <button class="tab-btn" onclick="switchTab('place')" id="btn-place">Place Order</button>
        </div>

        <div id="loading" style="text-align: center; padding: 20px;">Loading data...</div>

        <!-- POSITIONS TABLE -->
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
            <tbody id="position-body"></tbody>
        </table>

        <!-- ORDER BOOK TABLE -->
        <div id="order-section" class="hidden">
            <div class="search-box">
                <input type="text" id="order-detail-id" placeholder="Enter Order ID">
                <button class="btn-search" onclick="fetchOrderDetails()">Get Order Details</button>
            </div>
            <div id="order-detail-result" class="hidden"></div>
            <table id="order-table">
                <thead>
                    <tr>
                        <th>Order ID</th>
                        <th>Symbol</th>
                        <th>Type</th>
                        <th>Qty</th>
                        <th>Price</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="order-body"></tbody>
            </table>
        </div>

        <!-- TRADE BOOK TABLE -->
        <table id="trade-table" class="hidden">
            <thead>
                <tr>
                    <th>Trade ID</th>
                    <th>Order ID</th>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody id="trade-body"></tbody>
        </table>

        <!-- PLACE ORDER FORM -->
        <div id="place-section" class="hidden" style="background: #f9f9f9; padding: 20px; border-radius: 8px;">
            <h3 style="margin-top:0;">Place New Order</h3>
            <div id="order-response-msg" style="text-align: center; margin-bottom: 15px; font-weight: bold;"></div>
            
            <div class="order-form-grid">
                <div>
                    <label>Trading Symbol</label>
                    <input type="text" id="po_symbol" value="NIFTY25N1124500CE">
                </div>
                <div>
                    <label>Exchange</label>
                    <select id="po_exchange">
                        <option value="NSE">NSE</option>
                        <option value="NFO" selected>NFO</option>
                        <option value="BSE">BSE</option>
                        <option value="MCX">MCX</option>
                    </select>
                </div>
                <div>
                    <label>Transaction Type</label>
                    <select id="po_ttype">
                        <option value="BUY" selected>BUY</option>
                        <option value="SELL">SELL</option>
                    </select>
                </div>
                <div>
                    <label>Order Type</label>
                    <select id="po_otype" onchange="togglePriceInput()">
                        <option value="MARKET" selected>MARKET</option>
                        <option value="LIMIT">LIMIT</option>
                        <option value="SL">STOP LOSS</option>
                    </select>
                </div>
                <div>
                    <label>Quantity</label>
                    <input type="number" id="po_qty" value="65">
                </div>
                <div>
                    <label>Product</label>
                    <select id="po_product">
                        <option value="MIS" selected>MIS (Intraday)</option>
                        <option value="NRML">NRML (Overnight)</option>
                        <option value="CNC">CNC (Delivery)</option>
                    </select>
                </div>
                <div>
                    <label>Validity</label>
                    <select id="po_validity">
                        <option value="DAY" selected>DAY</option>
                        <option value="IOC">IOC</option>
                    </select>
                </div>
                <div>
                    <label>Price</label>
                    <input type="number" id="po_price" value="0" placeholder="0 for Market">
                </div>
                <div class="full-width">
                    <label>Variety</label>
                    <select id="po_variety">
                        <option value="regular">Regular</option>
                        <option value="amo" selected>AMO (After Market)</option>
                        <option value="stoploss">Stoploss</option>
                    </select>
                </div>
            </div>
            <button class="btn-place" onclick="placeOrder()">PLACE ORDER</button>
        </div>

    </div>
    {% endif %}

    <script>
        let currentTab = 'positions';

        function switchTab(tabName) {
            currentTab = tabName;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('btn-' + tabName).classList.add('active');

            document.getElementById('position-table').classList.add('hidden');
            document.getElementById('order-section').classList.add('hidden');
            document.getElementById('trade-table').classList.add('hidden');
            document.getElementById('place-section').classList.add('hidden');
            
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('order-detail-result').classList.add('hidden');

            if(tabName === 'positions') fetchPositions();
            else if(tabName === 'orders') fetchOrderBook();
            else if(tabName === 'trades') fetchTradeBook();
            else if(tabName === 'place') {
                // No auto refresh for place order, just show form
                document.getElementById('place-section').classList.remove('hidden');
            }
        }

        function togglePriceInput() {
            const type = document.getElementById('po_otype').value;
            const priceInput = document.getElementById('po_price');
            if (type === 'MARKET') {
                priceInput.value = 0;
                priceInput.disabled = true;
            } else {
                priceInput.disabled = false;
                priceInput.placeholder = "Enter Limit Price";
            }
        }

        async function placeOrder() {
            const btn = document.querySelector('.btn-place');
            const msg = document.getElementById('order-response-msg');
            
            const payload = {
                tradingsymbol: document.getElementById('po_symbol').value,
                exchange: document.getElementById('po_exchange').value,
                transaction_type: document.getElementById('po_ttype').value,
                order_type: document.getElementById('po_otype').value,
                quantity: parseInt(document.getElementById('po_qty').value),
                product: document.getElementById('po_product').value,
                validity: document.getElementById('po_validity').value,
                price: parseFloat(document.getElementById('po_price').value),
                variety: document.getElementById('po_variety').value
            };

            msg.innerText = "Placing Order...";
            msg.style.color = "#333";
            btn.disabled = true;
            btn.innerText = "Processing...";

            try {
                const response = await fetch('/api/place_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();

                if (result.success || result.status === 'success') {
                    msg.innerText = "Order Placed Successfully! ID: " + (result.data?.order_id || "Check Logs");
                    msg.style.color = "green";
                } else {
                    msg.innerText = "Order Failed: " + (result.message || JSON.stringify(result));
                    msg.style.color = "red";
                }
            } catch (err) {
                msg.innerText = "Error: " + err.message;
                msg.style.color = "red";
            } finally {
                btn.disabled = false;
                btn.innerText = "PLACE ORDER";
            }
        }

        // ... (Keep existing fetch functions: fetchPositions, fetchOrderBook, fetchOrderDetails, fetchTradeBook) ...
        // Re-including them here for completeness

        async function fetchPositions() {
            if (currentTab !== 'positions') return;
            try {
                const response = await fetch('/api/positions');
                const data = await response.json();
                renderPositions(data);
            } catch (err) { document.getElementById('loading').innerText = "Failed to connect."; }
        }

        function renderPositions(data) {
            const tbody = document.getElementById('position-body');
            const table = document.getElementById('position-table');
            const loading = document.getElementById('loading');
            tbody.innerHTML = ''; 
            if (data.error) { loading.innerText = "Error: " + data.error; loading.classList.remove('hidden'); table.classList.add('hidden'); return; }
            if (!data || data.length === 0) { loading.innerText = "No open positions."; loading.classList.remove('hidden'); table.classList.add('hidden'); return; }
            loading.classList.add('hidden'); table.classList.remove('hidden');
            data.forEach(pos => {
                const qty = parseFloat(pos.quantity || 0); const ltp = parseFloat(pos.ltp || 0); const avg = parseFloat(pos.avg_price || 0);
                const pnl = qty * (ltp - avg); const pnlColor = pnl >= 0 ? 'green' : 'red';
                tbody.innerHTML += `<tr><td>${pos.trading_symbol || '-'}</td><td>${pos.product || '-'}</td><td>${pos.quantity || '0'}</td><td>${pos.avg_price || '0.00'}</td><td>${pos.ltp || '0.00'}</td><td style="color:${pnlColor}; font-weight:bold;">${pnl.toFixed(2)}</td></tr>`;
            });
        }

        async function fetchOrderBook() {
            if (currentTab !== 'orders') return;
            try {
                const response = await fetch('/api/order_book');
                const data = await response.json();
                renderOrderBook(data);
            } catch (err) { document.getElementById('loading').innerText = "Failed to connect."; }
        }

        function renderOrderBook(data) {
            const tbody = document.getElementById('order-body');
            const table = document.getElementById('order-table');
            const section = document.getElementById('order-section');
            const loading = document.getElementById('loading');
            tbody.innerHTML = '';
            if (data.error) { loading.innerText = "Error: " + data.error; loading.classList.remove('hidden'); section.classList.add('hidden'); return; }
            const orders = Array.isArray(data) ? data : (data.data || []);
            if (orders.length === 0) { loading.innerText = "No orders found."; loading.classList.remove('hidden'); section.classList.add('hidden'); return; }
            loading.classList.add('hidden'); section.classList.remove('hidden');
            orders.forEach(order => {
                const row = `<tr><td>${order.order_id || order.orderid || '-'}</td><td>${order.trading_symbol || order.symbol || '-'}</td><td>${order.transaction_type || order.side || '-'}</td><td>${order.quantity || order.filled_quantity || '0'}</td><td>${order.price || order.average_price || '0.00'}</td><td><span style="padding: 2px 6px; border-radius: 4px; background: #e9ecef; font-size: 0.9em;">${order.status || '-'}</span></td></tr>`;
                tbody.innerHTML += row;
            });
        }

        async function fetchOrderDetails() {
            const orderId = document.getElementById('order-detail-id').value.trim();
            if(!orderId) { alert("Please enter an Order ID"); return; }
            const resultDiv = document.getElementById('order-detail-result');
            resultDiv.innerHTML = "Loading..."; resultDiv.classList.remove('hidden');
            try {
                const response = await fetch(`/api/order_details/${orderId}`);
                const data = await response.json();
                resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            } catch (err) { resultDiv.innerHTML = "Error fetching details."; }
        }

        async function fetchTradeBook() {
            if (currentTab !== 'trades') return;
            try {
                const response = await fetch('/api/trade_book');
                const data = await response.json();
                renderTradeBook(data);
            } catch (err) { document.getElementById('loading').innerText = "Failed to connect."; }
        }

        function renderTradeBook(data) {
            const tbody = document.getElementById('trade-body');
            const table = document.getElementById('trade-table');
            const loading = document.getElementById('loading');
            tbody.innerHTML = '';
            if (data.error) { loading.innerText = "Error: " + data.error; loading.classList.remove('hidden'); table.classList.add('hidden'); return; }
            const trades = Array.isArray(data) ? data : (data.data || []);
            if (trades.length === 0) { loading.innerText = "No trades found."; loading.classList.remove('hidden'); table.classList.add('hidden'); return; }
            loading.classList.add('hidden'); table.classList.remove('hidden');
            trades.forEach(trade => {
                tbody.innerHTML += `<tr><td>${trade.trade_id || trade.tradeid || '-'}</td><td>${trade.order_id || trade.orderid || '-'}</td><td>${trade.trading_symbol || trade.symbol || '-'}</td><td>${trade.quantity || trade.traded_quantity || '0'}</td><td>${trade.price || trade.trade_price || '0.00'}</td><td>${trade.trade_time || trade.time || '-'}</td></tr>`;
            });
        }

        // Auto-refresh logic
        {% if session.get('logged_in') %}
        setInterval(() => {
            if(currentTab === 'positions') fetchPositions();
            else if(currentTab === 'orders') fetchOrderBook();
            else if(currentTab === 'trades') fetchTradeBook();
        }, 3000);
        fetchPositions();
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
    return render_template_string(HTML_TEMPLATE, api_key=API_KEY)

@app.route("/login", methods=["POST"])
def login():
    totp = request.form.get("totp", "").strip()
    if not totp:
        return render_template_string(HTML_TEMPLATE, api_key=API_KEY, error="OTP is required.")
    try:
        mconnect_obj = MConnect()
        logging.info(f"Attempting login with Key: {API_KEY}")
        res = mconnect_obj.verify_totp(API_KEY, totp)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                session['logged_in'] = True
                unique_sid = str(uuid.uuid4())
                session['sid'] = unique_sid 
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
    sid = session.get('sid')
    if sid and sid in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[sid]
    session.clear()
    return redirect(url_for('index'))

@app.route("/api/positions")
def get_positions():
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    sid = session['sid']; mconnect_obj = ACTIVE_SESSIONS.get(sid)
    if not mconnect_obj: return jsonify({"error": "Session expired"})
    try:
        res = mconnect_obj.get_net_position()
        if res.status_code == 200:
            data = res.json()
            return jsonify(data['data'] if isinstance(data, dict) and 'data' in data else data)
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/api/order_book")
def get_order_book():
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    sid = session['sid']; mconnect_obj = ACTIVE_SESSIONS.get(sid)
    if not mconnect_obj: return jsonify({"error": "Session expired"})
    try:
        res = mconnect_obj.get_order_book()
        if res.status_code == 200:
            data = res.json()
            return jsonify(data['data'] if isinstance(data, dict) and 'data' in data else data)
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/api/order_details/<order_id>")
def get_order_details(order_id):
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    sid = session['sid']; mconnect_obj = ACTIVE_SESSIONS.get(sid)
    if not mconnect_obj: return jsonify({"error": "Session expired"})
    try:
        res = mconnect_obj.get_order_details(order_id)
        if res.status_code == 200: return jsonify(res.json())
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/api/trade_book")
def get_trade_book():
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    sid = session['sid']; mconnect_obj = ACTIVE_SESSIONS.get(sid)
    if not mconnect_obj: return jsonify({"error": "Session expired"})
    try:
        res = mconnect_obj.get_trade_book()
        if res.status_code == 200:
            data = res.json()
            return jsonify(data['data'] if isinstance(data, dict) and 'data' in data else data)
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

# ==========================================
# NEW ROUTE: PLACE ORDER (SDK Implementation)
# ==========================================
@app.route("/api/place_order", methods=["POST"])
def place_order():
    if 'logged_in' not in session or 'sid' not in session:
        return jsonify({"error": "Not logged in"})

    sid = session['sid']
    mconnect_obj = ACTIVE_SESSIONS.get(sid)

    if not mconnect_obj:
        return jsonify({"error": "Session expired. Please login again."})

    try:
        # Get JSON data from frontend
        req_data = request.json
        
        # Using the SDK's place_order method instead of raw requests
        # The SDK handles the auth headers internally using the stored session
        res = mconnect_obj.place_order(
            tradingsymbol=req_data.get('tradingsymbol'),
            exchange=req_data.get('exchange'),
            transaction_type=req_data.get('transaction_type'),
            order_type=req_data.get('order_type'),
            quantity=req_data.get('quantity'),
            product=req_data.get('product'),
            validity=req_data.get('validity'),
            price=req_data.get('price'),
            variety=req_data.get('variety')
        )
        
        if res.status_code == 200:
            return jsonify(res.json())
        else:
            # Try to get error message from response
            try:
                err_data = res.json()
                return jsonify({"status": "error", "message": err_data})
            except:
                return jsonify({"status": "error", "message": f"HTTP {res.status_code}"})
            
    except Exception as e:
        logging.exception("Place Order Error")
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```
