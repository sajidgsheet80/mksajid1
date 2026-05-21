
import logging
import uuid
import io
import os
import secrets
import pandas as pd

from flask import (
    Flask,
    render_template_string,
    request,
    session,
    jsonify,
    redirect,
    url_for
)

from tradingapi_a.mconnect import MConnect

# =========================================================
# CONFIGURATION
# =========================================================

app = Flask(__name__)

# Better Secret Key
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Hardcoded API Key
API_KEY = "CJOHJvQ/lUBtRZSXIVAtd3wkLRaSDpVGbO92K+FAIo8="

logging.basicConfig(level=logging.DEBUG)

# =========================================================
# SESSION STORE
# =========================================================

ACTIVE_SESSIONS = {}

# =========================================================
# HTML TEMPLATE
# =========================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>m.Stock Trading Dashboard</title>

    <style>
        body {
            font-family: Arial;
            background: #f0f2f5;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
        }

        h2 {
            text-align: center;
        }

        input, select {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            margin-bottom: 10px;
        }

        button {
            padding: 12px;
            border: none;
            cursor: pointer;
            border-radius: 5px;
        }

        .btn-primary {
            background: #007bff;
            color: white;
        }

        .btn-place {
            background: green;
            color: white;
            width: 100%;
            font-size: 18px;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        .tab-btn {
            background: #eee;
        }

        .tab-btn.active {
            background: #007bff;
            color: white;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: center;
        }

        .hidden {
            display: none;
        }

        .error {
            color: red;
        }

        .success {
            color: green;
        }

        .order-form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
    </style>
</head>

<body>

{% if not session.get('logged_in') %}

<div class="container" style="max-width:400px;">

    <h2>m.Stock Login</h2>

    <form method="POST" action="/login">

        <input type="text" name="totp" placeholder="Enter OTP" required>

        <button class="btn-primary" type="submit">
            Login
        </button>

    </form>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

</div>

{% else %}

<div class="container">

    <div style="display:flex;justify-content:space-between;align-items:center;">

        <h2>Trading Dashboard</h2>

        <form action="/logout" method="POST">
            <button type="submit">
                Logout
            </button>
        </form>

    </div>

    <div class="tabs">

        <button class="tab-btn active" id="btn-positions"
            onclick="switchTab('positions')">
            Positions
        </button>

        <button class="tab-btn" id="btn-orders"
            onclick="switchTab('orders')">
            Orders
        </button>

        <button class="tab-btn" id="btn-trades"
            onclick="switchTab('trades')">
            Trades
        </button>

        <button class="tab-btn" id="btn-place"
            onclick="switchTab('place')">
            Place Order
        </button>

    </div>

    <div id="loading">
        Loading...
    </div>

    <!-- POSITIONS -->

    <table id="position-table" class="hidden">

        <thead>
            <tr>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Avg</th>
                <th>LTP</th>
                <th>P&L</th>
            </tr>
        </thead>

        <tbody id="position-body"></tbody>

    </table>

    <!-- ORDERS -->

    <table id="order-table" class="hidden">

        <thead>
            <tr>
                <th>Order ID</th>
                <th>Symbol</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Status</th>
            </tr>
        </thead>

        <tbody id="order-body"></tbody>

    </table>

    <!-- TRADES -->

    <table id="trade-table" class="hidden">

        <thead>
            <tr>
                <th>Trade ID</th>
                <th>Order ID</th>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Price</th>
            </tr>
        </thead>

        <tbody id="trade-body"></tbody>

    </table>

    <!-- PLACE ORDER -->

    <div id="place-section" class="hidden">

        <h3>Place Order</h3>

        <div id="order-msg"></div>

        <div class="order-form-grid">

            <div>
                <label>Symbol</label>
                <input type="text" id="po_symbol"
                    value="NIFTY25N1124500CE">
            </div>

            <div>
                <label>Exchange</label>

                <select id="po_exchange">
                    <option value="NFO">NFO</option>
                    <option value="NSE">NSE</option>
                </select>
            </div>

            <div>
                <label>Transaction</label>

                <select id="po_ttype">
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                </select>
            </div>

            <div>
                <label>Order Type</label>

                <select id="po_otype">
                    <option value="MARKET">MARKET</option>
                    <option value="LIMIT">LIMIT</option>
                </select>
            </div>

            <div>
                <label>Qty</label>

                <input type="number" id="po_qty" value="50">
            </div>

            <div>
                <label>Price</label>

                <input type="number" id="po_price" value="0">
            </div>

            <div>
                <label>Product</label>

                <select id="po_product">
                    <option value="MIS">MIS</option>
                    <option value="NRML">NRML</option>
                </select>
            </div>

            <div>
                <label>Validity</label>

                <select id="po_validity">
                    <option value="DAY">DAY</option>
                    <option value="IOC">IOC</option>
                </select>
            </div>

        </div>

        <button class="btn-place"
            onclick="placeOrder()">
            PLACE ORDER
        </button>

    </div>

</div>

{% endif %}

<script>

let currentTab = 'positions';

function switchTab(tab) {

    currentTab = tab;

    document.querySelectorAll('.tab-btn').forEach(
        x => x.classList.remove('active')
    );

    document.getElementById('btn-' + tab)
        .classList.add('active');

    document.getElementById('position-table')
        .classList.add('hidden');

    document.getElementById('order-table')
        .classList.add('hidden');

    document.getElementById('trade-table')
        .classList.add('hidden');

    document.getElementById('place-section')
        .classList.add('hidden');

    if(tab === 'positions')
        fetchPositions();

    else if(tab === 'orders')
        fetchOrders();

    else if(tab === 'trades')
        fetchTrades();

    else if(tab === 'place')
        document.getElementById('place-section')
            .classList.remove('hidden');
}

async function fetchPositions() {

    const res = await fetch('/api/positions');
    const data = await res.json();

    const body = document.getElementById('position-body');

    body.innerHTML = '';

    document.getElementById('loading')
        .classList.add('hidden');

    document.getElementById('position-table')
        .classList.remove('hidden');

    data.forEach(pos => {

        const qty = parseFloat(pos.quantity || 0);
        const avg = parseFloat(pos.avg_price || 0);
        const ltp = parseFloat(pos.ltp || 0);

        const pnl = qty * (ltp - avg);

        body.innerHTML += `
        <tr>
            <td>${pos.trading_symbol || '-'}</td>
            <td>${qty}</td>
            <td>${avg}</td>
            <td>${ltp}</td>
            <td>${pnl.toFixed(2)}</td>
        </tr>
        `;
    });
}

async function fetchOrders() {

    const res = await fetch('/api/order_book');
    const data = await res.json();

    const body = document.getElementById('order-body');

    body.innerHTML = '';

    document.getElementById('loading')
        .classList.add('hidden');

    document.getElementById('order-table')
        .classList.remove('hidden');

    data.forEach(o => {

        body.innerHTML += `
        <tr>
            <td>${o.order_id || '-'}</td>
            <td>${o.trading_symbol || '-'}</td>
            <td>${o.transaction_type || '-'}</td>
            <td>${o.quantity || 0}</td>
            <td>${o.status || '-'}</td>
        </tr>
        `;
    });
}

async function fetchTrades() {

    const res = await fetch('/api/trade_book');
    const data = await res.json();

    const body = document.getElementById('trade-body');

    body.innerHTML = '';

    document.getElementById('loading')
        .classList.add('hidden');

    document.getElementById('trade-table')
        .classList.remove('hidden');

    data.forEach(t => {

        body.innerHTML += `
        <tr>
            <td>${t.trade_id || '-'}</td>
            <td>${t.order_id || '-'}</td>
            <td>${t.trading_symbol || '-'}</td>
            <td>${t.quantity || 0}</td>
            <td>${t.price || 0}</td>
        </tr>
        `;
    });
}

async function placeOrder() {

    const payload = {

        tradingsymbol:
            document.getElementById('po_symbol').value,

        exchange:
            document.getElementById('po_exchange').value,

        transaction_type:
            document.getElementById('po_ttype').value,

        order_type:
            document.getElementById('po_otype').value,

        quantity:
            parseInt(document.getElementById('po_qty').value),

        product:
            document.getElementById('po_product').value,

        validity:
            document.getElementById('po_validity').value,

        price:
            parseFloat(document.getElementById('po_price').value)
    };

    const res = await fetch('/api/place_order', {

        method: 'POST',

        headers: {
            'Content-Type': 'application/json'
        },

        body: JSON.stringify(payload)
    });

    const data = await res.json();

    const msg = document.getElementById('order-msg');

    if(data.status === 'success') {

        msg.innerHTML =
            "<span class='success'>Order Placed</span>";

    } else {

        msg.innerHTML =
            "<span class='error'>" +
            JSON.stringify(data) +
            "</span>";
    }
}

{% if session.get('logged_in') %}

fetchPositions();

setInterval(() => {

    if(currentTab === 'positions')
        fetchPositions();

    else if(currentTab === 'orders')
        fetchOrders();

    else if(currentTab === 'trades')
        fetchTrades();

}, 3000);

{% endif %}

</script>

</body>
</html>
"""

# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        api_key=API_KEY
    )

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["POST"])
def login():

    totp = request.form.get("totp", "").strip()

    if not totp:

        return render_template_string(
            HTML_TEMPLATE,
            error="OTP Required",
            api_key=API_KEY
        )

    try:

        mconnect_obj = MConnect()

        res = mconnect_obj.verify_totp(
            API_KEY,
            totp
        )

        if res.status_code != 200:

            return render_template_string(
                HTML_TEMPLATE,
                error=f"HTTP {res.status_code}",
                api_key=API_KEY
            )

        data = res.json()

        if data.get("status") != "success":

            return render_template_string(
                HTML_TEMPLATE,
                error=data.get("message"),
                api_key=API_KEY
            )

        session['logged_in'] = True

        sid = str(uuid.uuid4())

        session['sid'] = sid

        logging.info("Downloading instruments...")

        inst_res = mconnect_obj.get_instruments()

        csv_data = io.BytesIO(inst_res)

        df = pd.read_csv(csv_data)

        # DETECT TOKEN COLUMN

        token_col = None

        for col in [
            "token",
            "symboltoken",
            "instrument_token",
            "instrumenttoken"
        ]:

            if col in df.columns:
                token_col = col
                break

        # DETECT SYMBOL COLUMN

        symbol_col = None

        for col in [
            "tradingsymbol",
            "trading_symbol",
            "symbol",
            "tsym"
        ]:

            if col in df.columns:
                symbol_col = col
                break

        if not token_col:

            return render_template_string(
                HTML_TEMPLATE,
                error="Token column not found",
                api_key=API_KEY
            )

        if not symbol_col:

            return render_template_string(
                HTML_TEMPLATE,
                error="Symbol column not found",
                api_key=API_KEY
            )

        logging.info(f"Token Column: {token_col}")
        logging.info(f"Symbol Column: {symbol_col}")

        ACTIVE_SESSIONS[sid] = {

            "mconnect": mconnect_obj,
            "instruments": df,
            "token_col": token_col,
            "symbol_col": symbol_col
        }

        return redirect(url_for("index"))

    except Exception as e:

        logging.exception("Login Error")

        return render_template_string(
            HTML_TEMPLATE,
            error=str(e),
            api_key=API_KEY
        )

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout", methods=["POST"])
def logout():

    sid = session.get("sid")

    if sid in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[sid]

    session.clear()

    return redirect(url_for("index"))

# =========================================================
# POSITIONS
# =========================================================

@app.route("/api/positions")
def positions():

    if 'sid' not in session:
        return jsonify([])

    m = ACTIVE_SESSIONS[session['sid']]['mconnect']

    try:

        res = m.get_net_position()

        return jsonify(res.json().get('data', []))

    except Exception as e:

        return jsonify({"error": str(e)})

# =========================================================
# ORDER BOOK
# =========================================================

@app.route("/api/order_book")
def order_book():

    if 'sid' not in session:
        return jsonify([])

    m = ACTIVE_SESSIONS[session['sid']]['mconnect']

    try:

        res = m.get_order_book()

        return jsonify(res.json().get('data', []))

    except Exception as e:

        return jsonify({"error": str(e)})

# =========================================================
# TRADE BOOK
# =========================================================

@app.route("/api/trade_book")
def trade_book():

    if 'sid' not in session:
        return jsonify([])

    m = ACTIVE_SESSIONS[session['sid']]['mconnect']

    try:

        res = m.get_trade_book()

        return jsonify(res.json().get('data', []))

    except Exception as e:

        return jsonify({"error": str(e)})

# =========================================================
# PLACE ORDER
# =========================================================

@app.route("/api/place_order", methods=["POST"])
def place_order():

    if 'sid' not in session:

        return jsonify({
            "status": "error",
            "message": "Not logged in"
        })

    try:

        session_data = ACTIVE_SESSIONS[session['sid']]

        m = session_data['mconnect']

        df = session_data['instruments']

        token_col = session_data['token_col']

        symbol_col = session_data['symbol_col']

        req_data = request.json

        symbol = req_data.get('tradingsymbol')

        # FIND TOKEN

        row = df[
            df[symbol_col].astype(str) == str(symbol)
        ]

        if row.empty:

            return jsonify({
                "status": "error",
                "message": "Symbol not found"
            })

        symbol_token = str(
            row.iloc[0][token_col]
        )

        logging.info(f"Found token: {symbol_token}")

        # SDK PARAMS

        res = m.place_order(

            _tradingsymbol=symbol,

            _symboltoken=symbol_token,

            _exchange=req_data.get('exchange'),

            _transaction_type=req_data.get(
                'transaction_type'
            ),

            _order_type=req_data.get('order_type'),

            _quantity=str(req_data.get('quantity')),

            _product=req_data.get('product'),

            _validity=req_data.get('validity'),

            _price=str(req_data.get('price'))
        )

        logging.info(f"Order Response: {res}")

        # HANDLE RESPONSE

        if isinstance(res, dict):

            return jsonify(res)

        if hasattr(res, 'json'):

            try:
                return jsonify(res.json())

            except:
                return jsonify({
                    "status": "success",
                    "data": str(res)
                })

        return jsonify({
            "status": "success",
            "data": str(res)
        })

    except Exception as e:

        logging.exception("Place Order Error")

        return jsonify({
            "status": "error",
            "message": str(e)
        })

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

