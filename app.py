
import logging
import uuid
import io
import pandas as pd
from flask import Flask, render_template_string, request, session, jsonify, redirect, url_for
from tradingapi_a.mconnect import MConnect

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
        input[type="text"], input[type="password"], input[type="number"], input[type="date"], select { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button.btn-primary { width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button.btn-primary:hover { background-color: #0056b3; }
        button.btn-logout { background-color: #dc3545; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; float: right; }
        
        /* Place Order Form */
        .order-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .full-width { grid-column: span 2; }
        .btn-place { background-color: #28a745; color: white; width: 100%; padding: 15px; font-size: 18px; border: none; border-radius: 5px; cursor: pointer; margin-top: 20px; }
        .btn-place:hover { background-color: #218838; }
        
        /* Tab Styles */
        .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; overflow-x: auto; }
        .tab-btn { padding: 10px 20px; background: none; border: none; font-size: 16px; cursor: pointer; color: #555; border-bottom: 3px solid transparent; transition: all 0.3s; white-space: nowrap; }
        .tab-btn:hover { color: #007bff; }
        .tab-btn.active { color: #007bff; border-bottom: 3px solid #007bff; font-weight: bold; }

        /* Table Styles */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
        th, td { padding: 10px; text-align: center; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; color: #555; font-weight: 600; }
        tr:hover { background-color: #f1f1f1; }
        
        /* Option Chain Specifics */
        .oc-ce-ltp { color: green; font-weight: bold; }
        .oc-pe-ltp { color: red; font-weight: bold; }
        .oc-controls { display: flex; gap: 10px; margin-bottom: 15px; align-items: flex-end; }
        .oc-controls > div { flex: 1; }
        
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
            <button class="tab-btn" onclick="switchTab('optionchain')" id="btn-optionchain">Option Chain</button>
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
                <input type="text" id="order-detail-id" placeholder="Enter Order ID" style="width:auto; margin-right:10px;">
                <button class="btn-search" onclick="fetchOrderDetails()" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; cursor:pointer;">Get Order Details</button>
            </div>
            <div id="order-detail-result" class="hidden"></div>
            <table id="order-table" style="margin-top:20px;">
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

        <!-- OPTION CHAIN SECTION -->
        <div id="oc-section" class="hidden">
            <div class="oc-controls">
                <div>
                    <label>Index Symbol</label>
                    <select id="oc_symbol">
                        <option value="NIFTY">NIFTY</option>
                        <option value="BANKNIFTY">BANKNIFTY</option>
                        <option value="FINNIFTY">FINNIFTY</option>
                        <option value="MIDCPNIFTY">MIDCPNIFTY</option>
                    </select>
                </div>
                <div>
                    <label>Strikes Range (±)</label>
                    <input type="number" id="oc_strike_range" value="10" min="5" max="50">
                </div>
                <div>
                    <label>&nbsp;</label>
                    <button class="btn-primary" style="padding: 12px;" onclick="fetchOptionChain(true)">Refresh</button>
                </div>
            </div>
            
            <table id="oc-table">
                <thead>
                    <tr>
                        <th colspan="3" style="color: green; border-bottom: 2px solid #ddd;">CALLS</th>
                        <th style="background-color: #e9ecef;">Strike</th>
                        <th colspan="3" style="color: red; border-bottom: 2px solid #ddd;">PUTS</th>
                    </tr>
                    <tr>
                        <th>OI Chg</th>
                        <th>OI</th>
                        <th>LTP</th>
                        <th style="background-color: #f8f9fa;">Price</th>
                        <th>LTP</th>
                        <th>OI</th>
                        <th>OI Chg</th>
                    </tr>
                </thead>
                <tbody id="oc-body"></tbody>
            </table>
        </div>

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
            document.getElementById('oc-section').classList.add('hidden');
            document.getElementById('place-section').classList.add('hidden');
            
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('order-detail-result').classList.add('hidden');

            if(tabName === 'positions') fetchPositions();
            else if(tabName === 'orders') fetchOrderBook();
            else if(tabName === 'trades') fetchTradeBook();
            else if(tabName === 'optionchain') fetchOptionChain(true);
            else if(tabName === 'place') {
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
                    msg.innerText = "Order Placed Successfully! ID: " + (result.data ? (result.data.order_id || "Check Logs") : "Check Logs");
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
                const qty = parseFloat(pos.quantity || 0); 
                const ltp = parseFloat(pos.ltp || 0); 
                const avg = parseFloat(pos.avg_price || 0);
                const pnl = qty * (ltp - avg); 
                const pnlColor = pnl >= 0 ? 'green' : 'red';
                const row = document.createElement('tr');
                row.innerHTML = `<td>${pos.trading_symbol || '-'}</td><td>${pos.product || '-'}</td><td>${pos.quantity || '0'}</td><td>${pos.avg_price || '0.00'}</td><td>${pos.ltp || '0.00'}</td><td style="color:${pnlColor}; font-weight:bold;">${pnl.toFixed(2)}</td>`;
                tbody.appendChild(row);
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
                const row = document.createElement('tr');
                row.innerHTML = `<td>${order.order_id || order.orderid || '-'}</td><td>${order.trading_symbol || order.symbol || '-'}</td><td>${order.transaction_type || order.side || '-'}</td><td>${order.quantity || order.filled_quantity || '0'}</td><td>${order.price || order.average_price || '0.00'}</td><td><span style="padding: 2px 6px; border-radius: 4px; background: #e9ecef; font-size: 0.9em;">${order.status || '-'}</span></td></tr>`;
                tbody.appendChild(row);
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
                const row = document.createElement('tr');
                row.innerHTML = `<td>${trade.trade_id || trade.tradeid || '-'}</td><td>${trade.order_id || trade.orderid || '-'}</td><td>${trade.trading_symbol || trade.symbol || '-'}</td><td>${trade.quantity || trade.traded_quantity || '0'}</td><td>${trade.price || trade.trade_price || '0.00'}</td><td>${trade.trade_time || trade.time || '-'}</td></td>`;
                tbody.appendChild(row);
            });
        }

        async function fetchOptionChain(showLoading = false) {
            if (currentTab !== 'optionchain') return;

            const symbol = document.getElementById('oc_symbol').value;
            const range = document.getElementById('oc_strike_range').value;
            const loading = document.getElementById('loading');
            const section = document.getElementById('oc-section');
            
            if(showLoading) { loading.innerText = "Loading Option Chain..."; loading.classList.remove('hidden'); }

            try {
                const url = `/api/option_chain?symbol=${symbol}&strike_range=${range}`;
                const response = await fetch(url);
                const data = await response.json();
                renderOptionChain(data);
            } catch (err) { 
                loading.innerText = "Error connecting to Option Chain API."; 
                loading.classList.remove('hidden');
                section.classList.add('hidden');
            }
        }

        function renderOptionChain(data) {
            const tbody = document.getElementById('oc-body');
            const table = document.getElementById('oc-table');
            const loading = document.getElementById('loading');
            const section = document.getElementById('oc-section');

            tbody.innerHTML = '';
            
            if (data.error) { 
                loading.innerText = "Error: " + data.error; 
                loading.classList.remove('hidden'); 
                section.classList.add('hidden'); 
                return; 
            }
            
            const chainData = Array.isArray(data) ? data : (data.data || []);

            if (chainData.length === 0) { 
                loading.innerText = "No option chain data found."; 
                loading.classList.remove('hidden'); 
                section.classList.add('hidden'); 
                return; 
            }

            loading.classList.add('hidden'); 
            section.classList.remove('hidden');

            chainData.forEach(row => {
                // Data is expected in format { strike, ce_ltp, pe_ltp, ... }
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${row.ce_oi_chng || '-'}</td>
                    <td>${row.ce_oi || '-'}</td>
                    <td class="oc-ce-ltp">${row.ce_ltp}</td>
                    <td style="background-color: #f8f9fa; font-weight:bold;">${row.strike}</td>
                    <td class="oc-pe-ltp">${row.pe_ltp}</td>
                    <td>${row.pe_oi || '-'}</td>
                    <td>${row.pe_oi_chng || '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        {% if session.get('logged_in') %}
        setInterval(() => {
            if(currentTab === 'positions') fetchPositions();
            else if(currentTab === 'orders') fetchOrderBook();
            else if(currentTab === 'trades') fetchTradeBook();
            else if(currentTab === 'optionchain') fetchOptionChain(false);
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
                
                # DOWNLOAD INSTRUMENTS ON LOGIN
                try:
                    logging.info("Downloading instruments...")
                    inst_res = mconnect_obj.get_instruments()
                    csv = io.BytesIO(inst_res)
                    df_instruments = pd.read_csv(csv)
                    ACTIVE_SESSIONS[unique_sid] = {
                        "mconnect": mconnect_obj,
                        "instruments": df_instruments
                    }
                    logging.info("Instruments downloaded and cached.")
                except Exception as e:
                    logging.error(f"Failed to download instruments: {e}")
                    ACTIVE_SESSIONS[unique_sid] = {
                        "mconnect": mconnect_obj,
                        "instruments": None
                    }

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
    sid = session['sid']; session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    mconnect_obj = session_data['mconnect']
    
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
    sid = session['sid']; session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    mconnect_obj = session_data['mconnect']
    
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
    sid = session['sid']; session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    mconnect_obj = session_data['mconnect']
    
    try:
        res = mconnect_obj.get_order_details(order_id)
        if res.status_code == 200: return jsonify(res.json())
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/api/trade_book")
def get_trade_book():
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    sid = session['sid']; session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    mconnect_obj = session_data['mconnect']
    
    try:
        res = mconnect_obj.get_trade_book()
        if res.status_code == 200:
            data = res.json()
            return jsonify(data['data'] if isinstance(data, dict) and 'data' in data else data)
        return jsonify({"error": f"API Error: {res.status_code}"})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/api/option_chain")
def get_option_chain_api():
    if 'logged_in' not in session or 'sid' not in session: return jsonify({"error": "Not logged in"})
    
    sid = session['sid']
    session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    
    mconnect_obj = session_data['mconnect']
    df = session_data.get('instruments')
    
    if df is None:
        return jsonify({"error": "Instruments not loaded. Please logout and login again."})

    try:
        symbol = request.args.get('symbol', 'NIFTY')
        strike_range_count = int(request.args.get('strike_range', 10))
        
        # 1. Filter for Index Options
        # Based on user's reference code logic
        nifty = df[
            (df["segment"] == "OPTIDX") &
            (df["exchange"] == "NFO") &
            (df["tradingsymbol"].str.startswith(symbol))
        ]

        if nifty.empty:
            return jsonify({"error": f"No options found for {symbol}"})

        # 2. Find Nearest Expiry
        exp_list = nifty["expiry"].dropna().unique().tolist()
        exp_list.sort()
        nearest_exp = exp_list[0]
        
        nifty_exp = nifty[nifty["expiry"] == nearest_exp]

        # 3. Find ATM Strike
        # To find ATM, we need the current spot price of the Index.
        # We try to find the Index token from the master list
        index_data = df[
            (df["segment"] == "INDEX") & 
            (df["exchange"] == "NSE") & 
            (df["tradingsymbol"].str.startswith(symbol))
        ]
        
        spot_price = 0
        if not index_data.empty:
            index_token = index_data.iloc[0]['symboltoken'] # Assuming column name symboltoken
            try:
                # Try to get quote for spot
                # Note: Method might be get_quote or get_quotes depending on version
                quote_res = mconnect_obj.get_quotes([index_token]) 
                if quote_res.status_code == 200:
                    quote_json = quote_res.json()
                    # Handling potential nested structure
                    if isinstance(quote_json, dict) and 'data' in quote_json:
                        spot_price = float(quote_json['data'][0].get('ltp', 0))
                    elif isinstance(quote_json, list):
                        spot_price = float(quote_json[0].get('ltp', 0))
            except Exception as e:
                logging.warning(f"Could not fetch spot price: {e}")
        
        # Fallback if spot price is 0 (e.g. market closed or API fail): Use center of strikes
        if spot_price == 0:
            all_strikes = nifty_exp["strike"].unique()
            spot_price = (min(all_strikes) + max(all_strikes)) / 2

        # 4. Calculate Strike Range
        strike_interval = 50 # Standard for NIFTY/BANKNIFTY
        if symbol == "BANKNIFTY": strike_interval = 100
        
        atm_strike = round(spot_price / strike_interval) * strike_interval
        
        lower_strike = atm_strike - (strike_range_count * strike_interval)
        upper_strike = atm_strike + (strike_range_count * strike_interval)

        strike_range = nifty_exp[
            (nifty_exp["strike"] >= lower_strike) &
            (nifty_exp["strike"] <= upper_strike)
        ]

        # 5. Separate CE and PE
        if "option_type" in strike_range.columns:
            ce_options = strike_range[strike_range["option_type"] == "CE"]
            pe_options = strike_range[strike_range["option_type"] == "PE"]
        else:
            ce_options = strike_range[strike_range["tradingsymbol"].str.endswith("CE")]
            pe_options = strike_range[strike_range["tradingsymbol"].str.endswith("PE")]

        # 6. Get Tokens for Live Data
        # Assuming 'symboltoken' is the column name based on typical API structures
        all_tokens = ce_options['symboltoken'].tolist() + pe_options['symboltoken'].tolist()
        
        price_map = {}
        
        # 7. Fetch Live Prices (Batch)
        try:
            if all_tokens:
                # Attempt to fetch quotes. Note: Some SDKs limit batch size.
                # If API fails, prices will be 0.
                quote_res = mconnect_obj.get_quotes(all_tokens)
                if quote_res.status_code == 200:
                    q_data = quote_res.json()
                    q_list = q_data.get('data', q_data) if isinstance(q_data, dict) else q_data
                    
                    for item in q_list:
                        tk = item.get('symboltoken')
                        ltp = item.get('ltp', 0)
                        oi = item.get('oi', 0)
                        oi_chng = item.get('change_oi', 0) # Or 'oi_chng' depending on API version
                        price_map[tk] = {'ltp': ltp, 'oi': oi, 'oi_chng': oi_chng}
        except Exception as e:
            logging.error(f"Error fetching option quotes: {e}")

        # 8. Merge Data
        response_data = []
        
        # Sort by strike
        ce_options = ce_options.sort_values('strike')
        pe_options = pe_options.sort_values('strike')

        # Iterate through unique strikes to build rows
        for strike in sorted(strike_range['strike'].unique()):
            row = {'strike': strike}
            
            # Get CE Data
            ce_row = ce_options[ce_options['strike'] == strike]
            if not ce_row.empty:
                ce_token = str(ce_row.iloc[0]['symboltoken'])
                ce_info = price_map.get(ce_token, {})
                row['ce_ltp'] = ce_info.get('ltp', 0)
                row['ce_oi'] = ce_info.get('oi', 0)
                row['ce_oi_chng'] = ce_info.get('oi_chng', 0)
            else:
                row['ce_ltp'] = 0
                row['ce_oi'] = 0
                row['ce_oi_chng'] = 0

            # Get PE Data
            pe_row = pe_options[pe_options['strike'] == strike]
            if not pe_row.empty:
                pe_token = str(pe_row.iloc[0]['symboltoken'])
                pe_info = price_map.get(pe_token, {})
                row['pe_ltp'] = pe_info.get('ltp', 0)
                row['pe_oi'] = pe_info.get('oi', 0)
                row['pe_oi_chng'] = pe_info.get('oi_chng', 0)
            else:
                row['pe_ltp'] = 0
                row['pe_oi'] = 0
                row['pe_oi_chng'] = 0
            
            response_data.append(row)

        return jsonify(response_data)

    except Exception as e:
        logging.exception("Option Chain Error")
        return jsonify({"error": str(e)})

@app.route("/api/place_order", methods=["POST"])
def place_order():
    if 'logged_in' not in session or 'sid' not in session:
        return jsonify({"error": "Not logged in"})

    sid = session['sid']
    session_data = ACTIVE_SESSIONS.get(sid)
    if not session_data: return jsonify({"error": "Session expired"})
    
    mconnect_obj = session_data['mconnect']

    try:
        req_data = request.json
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
