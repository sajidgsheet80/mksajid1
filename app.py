from fyers_apiv3 import fyersModel
from flask import Flask, redirect, request, render_template_string, jsonify
import webbrowser
import pandas as pd
import os
import json
from datetime import datetime

# ---- Credentials ----
client_id = "VMS68P9EK0-100"
secret_key = "ZJ0CFWZEL1"
redirect_uri = "http://127.0.0.1:5000/callback"

# ---- Session ----
appSession = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type="code",
    grant_type="authorization_code",
    state="sample"
)

# ---- Flask ----
app = Flask(__name__)
app.secret_key = "sajid_secret"
fyers = None

# ---- NIFTY 50 Stock Symbols ----
nifty50_stocks = {
    "RELIANCE": "NSE:RELIANCE-EQ",
    "TCS": "NSE:TCS-EQ",
    "HDFCBANK": "NSE:HDFCBANK-EQ",
    "INFY": "NSE:INFY-EQ",
    "ICICIBANK": "NSE:ICICIBANK-EQ",
    "HINDUNILVR": "NSE:HINDUNILVR-EQ",
    "ITC": "NSE:ITC-EQ",
    "SBIN": "NSE:SBIN-EQ",
    "BHARTIARTL": "NSE:BHARTIARTL-EQ",
    "KOTAKBANK": "NSE:KOTAKBANK-EQ",
    "LT": "NSE:LT-EQ",
    "AXISBANK": "NSE:AXISBANK-EQ",
    "BAJFINANCE": "NSE:BAJFINANCE-EQ",
    "ASIANPAINT": "NSE:ASIANPAINT-EQ",
    "MARUTI": "NSE:MARUTI-EQ",
    "M&M": "NSE:M&M-EQ",
    "TITAN": "NSE:TITAN-EQ",
    "SUNPHARMA": "NSE:SUNPHARMA-EQ",
    "ULTRACEMCO": "NSE:ULTRACEMCO-EQ",
    "NESTLEIND": "NSE:NESTLEIND-EQ",
    "WIPRO": "NSE:WIPRO-EQ",
    "HCLTECH": "NSE:HCLTECH-EQ",
    "NTPC": "NSE:NTPC-EQ",
    "TATAMOTORS": "NSE:TATAMOTORS-EQ",
    "POWERGRID": "NSE:POWERGRID-EQ",
    "BAJAJFINSV": "NSE:BAJAJFINSV-EQ",
    "ADANIENT": "NSE:ADANIENT-EQ",
    "ONGC": "NSE:ONGC-EQ",
    "TECHM": "NSE:TECHM-EQ",
    "TATASTEEL": "NSE:TATASTEEL-EQ",
    "DIVISLAB": "NSE:DIVISLAB-EQ",
    "COALINDIA": "NSE:COALINDIA-EQ",
    "INDUSINDBK": "NSE:INDUSINDBK-EQ",
    "JSWSTEEL": "NSE:JSWSTEEL-EQ",
    "GRASIM": "NSE:GRASIM-EQ",
    "HINDALCO": "NSE:HINDALCO-EQ",
    "CIPLA": "NSE:CIPLA-EQ",
    "DRREDDY": "NSE:DRREDDY-EQ",
    "EICHERMOT": "NSE:EICHERMOT-EQ",
    "HEROMOTOCO": "NSE:HEROMOTOCO-EQ",
    "BRITANNIA": "NSE:BRITANNIA-EQ",
    "APOLLOHOSP": "NSE:APOLLOHOSP-EQ",
    "ADANIPORTS": "NSE:ADANIPORTS-EQ",
    "TATACONSUM": "NSE:TATACONSUM-EQ",
    "BPCL": "NSE:BPCL-EQ",
    "SHRIRAMFIN": "NSE:SHRIRAMFIN-EQ",
    "UPL": "NSE:UPL-EQ",
    "BAJAJ-AUTO": "NSE:BAJAJ-AUTO-EQ",
    "LTIM": "NSE:LTIM-EQ",
    "SBILIFE": "NSE:SBILIFE-EQ"
}

previous_data = {}
positions = []  # Store open positions

@app.route("/")
def home():
    return """
    <h2>Sajid Shaikh Algo Software : +91 9834370368</h2>
    <a href="/login" target="_blank">🔑 Login</a> |
    <a href="/chain?stock=RELIANCE" target="_blank">📊 View Stock Option Chain</a>
    <hr>
    <p>Use the dropdown on the Option Chain page to switch between NIFTY 50 stocks. The table auto-refreshes every second.</p>
    """

@app.route("/login")
def login():
    login_url = appSession.generate_authcode()
    webbrowser.open(login_url, new=1)
    return redirect(login_url)

@app.route("/callback")
def callback():
    global fyers
    auth_code = request.args.get("auth_code")
    if auth_code:
        try:
            appSession.set_token(auth_code)
            token_response = appSession.generate_token()
            access_token = token_response.get("access_token")
            fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, is_async=False)
            return "<h2>✅ Authentication Successful! You can return to the app 🚀</h2>"
        except Exception as e:
            return f"<h3>Callback error: {str(e)}</h3>"
    return "❌ Authentication failed. Please retry."

@app.route("/chain")
def fetch_option_chain():
    global fyers
    if fyers is None:
        return "<h3>⚠ Please <a href='/login'>login</a> first!</h3>"

    stock_name = request.args.get("stock", "RELIANCE")
    
    # Generate dropdown options
    stock_options = ""
    for stock in sorted(nifty50_stocks.keys()):
        selected = "selected" if stock == stock_name else ""
        stock_options += f'<option value="{stock}" {selected}>{stock}</option>'

    try:
        table_html, spot_price, analysis_html, ce_headers, pe_headers, equity_html = generate_full_table(stock_name)
    except Exception as e:
        table_html = f"<p>Error fetching option chain: {str(e)}</p>"
        spot_price = ""
        analysis_html = ""
        equity_html = ""

    html = f"""
    <!doctype html>
    <html>
    <head>
        <title>{stock_name} Option Chain (ATM ±3)</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 16px; }}
            h2, h3 {{ text-align:center; color:#1a73e8; }}
            table {{ width:100%; border-collapse: collapse; font-size:13px; margin-bottom: 20px; }}
            th, td {{ border:1px solid #ddd; padding:6px; text-align:center; }}
            th {{ background:#1a73e8; color:#fff; }}
            tr:nth-child(even) {{ background:#f7f7f7; }}
            .dropdown {{ margin:12px 0; text-align:center; }}
            #analysis {{ background:#eef; padding:10px; border-radius:5px; margin-top:15px; margin-bottom:15px; }}
            .equity-section {{ background:#f0f8ff; padding:15px; border-radius:5px; margin-bottom:15px; }}
            .positions-section {{ background:#fff3cd; padding:15px; border-radius:5px; margin-bottom:15px; }}
            .movers-section {{ background:#e8f5e9; padding:15px; border-radius:5px; margin-bottom:15px; }}
            .btn {{ padding:8px 16px; margin:2px; cursor:pointer; border:none; border-radius:4px; font-weight:bold; }}
            .btn-buy {{ background:#4caf50; color:white; }}
            .btn-sell {{ background:#f44336; color:white; }}
            .btn:hover {{ opacity:0.8; }}
            .profit-positive {{ color: green; font-weight: bold; }}
            .profit-negative {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h2 id="spot-title">{stock_name} Option Chain (ATM ±3) — Spot: {spot_price}</h2>

        <div class="dropdown">
            <form method="get" action="/chain">
                <label for="stock">Select NIFTY 50 Stock: </label>
                <select name="stock" id="stock" onchange="this.form.submit()">
                    {stock_options}
                </select>
            </form>
        </div>

        <div class="equity-section" id="equity-section">
            <h3>📈 Equity Stock Details</h3>
            {equity_html}
        </div>

        <div class="positions-section" id="positions-section">
            <h3>💼 Open Positions</h3>
            <table id="positions-table">
                <thead>
                    <tr>
                        <th>Stock Name</th>
                        <th>Type</th>
                        <th>Entry Price (LTP)</th>
                        <th>Current LTP</th>
                        <th>Profit/Loss</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody id="positions-body">
                    <tr><td colspan="6">No positions yet</td></tr>
                </tbody>
            </table>
        </div>

        <div class="movers-section" id="movers-section">
            <h3>📊 NIFTY 50 - Top Gainers & Losers</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <h4 style="color: green; text-align: center;">🚀 Top 5 Gainers</h4>
                    <table id="gainers-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Stock</th>
                                <th>LTP</th>
                                <th>Change %</th>
                            </tr>
                        </thead>
                        <tbody id="gainers-body">
                            <tr><td colspan="4">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
                <div>
                    <h4 style="color: red; text-align: center;">📉 Top 5 Losers</h4>
                    <table id="losers-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Stock</th>
                                <th>LTP</th>
                                <th>Change %</th>
                            </tr>
                        </thead>
                        <tbody id="losers-body">
                            <tr><td colspan="4">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="movers-section" id="price-patterns-section">
            <h3>📊 NIFTY 50 - Price Pattern Signals</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <h4 style="color: green; text-align: center;">🟢 Open = Low (Bullish Signal)</h4>
                    <table id="open-low-table">
                        <thead>
                            <tr>
                                <th>Stock</th>
                                <th>Open</th>
                                <th>Low</th>
                                <th>LTP</th>
                                <th>Change %</th>
                            </tr>
                        </thead>
                        <tbody id="open-low-body">
                            <tr><td colspan="5">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
                <div>
                    <h4 style="color: red; text-align: center;">🔴 Open = High (Bearish Signal)</h4>
                    <table id="open-high-table">
                        <thead>
                            <tr>
                                <th>Stock</th>
                                <th>Open</th>
                                <th>High</th>
                                <th>LTP</th>
                                <th>Change %</th>
                            </tr>
                        </thead>
                        <tbody id="open-high-body">
                            <tr><td colspan="5">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <h3>📊 Options Chain</h3>
        <table id="option-chain-table">
            <thead><tr>{ce_headers}<th>STRIKE</th>{pe_headers}</tr></thead>
            <tbody>{table_html}</tbody>
        </table>

        <div id="analysis">{analysis_html}</div>

        <script>
            const stockName = "{stock_name}";
            
            async function placeOrder(type) {{
                try {{
                    const resp = await fetch(`/place_order?stock=${{stockName}}&type=${{type}}`);
                    const result = await resp.json();
                    if (result.success) {{
                        alert(result.message);
                        refreshPositions();
                    }} else {{
                        alert('Error: ' + result.message);
                    }}
                }} catch (err) {{
                    console.error("Error placing order:", err);
                    alert('Error placing order');
                }}
            }}

            async function refreshTableRows() {{
                try {{
                    const resp = await fetch(`/chain_rows_diff?stock=${{stockName}}`);
                    const result = await resp.json();
                    if (result.rows) {{
                        document.querySelector("#option-chain-table tbody").innerHTML = result.rows;
                        document.querySelector("#spot-title").innerHTML = `${{stockName}} Option Chain (ATM ±3) — Spot: ${{result.spot}}`;
                        document.querySelector("#analysis").innerHTML = result.analysis;
                        document.querySelector("#equity-section").innerHTML = `<h3>📈 Equity Stock Details</h3>` + result.equity;
                    }}
                }} catch (err) {{
                    console.error("Error refreshing rows:", err);
                }}
            }}

            async function refreshPositions() {{
                try {{
                    const resp = await fetch(`/get_positions?stock=${{stockName}}`);
                    const result = await resp.json();
                    const tbody = document.querySelector("#positions-body");
                    if (result.positions && result.positions.length > 0) {{
                        tbody.innerHTML = result.positions;
                    }} else {{
                        tbody.innerHTML = '<tr><td colspan="6">No positions yet</td></tr>';
                    }}
                }} catch (err) {{
                    console.error("Error refreshing positions:", err);
                }}
            }}

            async function refreshMovers() {{
                try {{
                    const resp = await fetch('/get_movers');
                    const result = await resp.json();
                    
                    const gainersBody = document.querySelector("#gainers-body");
                    const losersBody = document.querySelector("#losers-body");
                    
                    if (result.gainers) {{
                        gainersBody.innerHTML = result.gainers;
                    }}
                    if (result.losers) {{
                        losersBody.innerHTML = result.losers;
                    }}
                }} catch (err) {{
                    console.error("Error refreshing movers:", err);
                }}
            }}

            async function refreshPricePatterns() {{
                try {{
                    const resp = await fetch('/get_price_patterns');
                    const result = await resp.json();
                    
                    const openLowBody = document.querySelector("#open-low-body");
                    const openHighBody = document.querySelector("#open-high-body");
                    
                    if (result.open_low) {{
                        openLowBody.innerHTML = result.open_low;
                    }}
                    if (result.open_high) {{
                        openHighBody.innerHTML = result.open_high;
                    }}
                }} catch (err) {{
                    console.error("Error refreshing price patterns:", err);
                }}
            }}

            setInterval(refreshTableRows, 1000);
            setInterval(refreshPositions, 1000);
            setInterval(refreshMovers, 5000);
            setInterval(refreshPricePatterns, 5000);
            refreshMovers(); // Initial load
            refreshPricePatterns(); // Initial load
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/place_order")
def place_order():
    global positions, fyers
    
    stock_name = request.args.get("stock", "RELIANCE")
    order_type = request.args.get("type", "BUY")
    
    if stock_name not in nifty50_stocks:
        return jsonify({"success": False, "message": "Invalid stock"})
    
    symbol = nifty50_stocks[stock_name]
    
    try:
        # Get current LTP
        quote_data = {"symbols": symbol}
        response = fyers.quotes(data=quote_data)
        
        ltp = None
        if response and "d" in response and len(response["d"]) > 0:
            ltp = response["d"][0].get("v", {}).get("lp")
        
        if ltp is None:
            return jsonify({"success": False, "message": "Could not fetch LTP"})
        
        # Add position
        position = {
            "stock": stock_name,
            "symbol": symbol,
            "type": order_type,
            "entry_ltp": float(ltp),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        positions.append(position)
        
        return jsonify({
            "success": True, 
            "message": f"{order_type} order placed for {stock_name} at ₹{ltp}"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/get_positions")
def get_positions():
    global positions, fyers
    
    stock_name = request.args.get("stock", "RELIANCE")
    
    if not positions:
        return jsonify({"positions": ""})
    
    # Get current LTPs for all positions
    symbols = list(set([p["symbol"] for p in positions]))
    ltp_map = {}
    
    try:
        quote_data = {"symbols": ",".join(symbols)}
        response = fyers.quotes(data=quote_data)
        
        if response and "d" in response:
            for item in response["d"]:
                sym = item.get("n")
                ltp = item.get("v", {}).get("lp")
                if sym and ltp:
                    ltp_map[sym] = float(ltp)
    except Exception as e:
        print(f"Error fetching LTPs: {e}")
    
    # Generate positions HTML
    positions_html = ""
    for pos in positions:
        current_ltp = ltp_map.get(pos["symbol"], pos["entry_ltp"])
        
        if pos["type"] == "BUY":
            profit = current_ltp - pos["entry_ltp"]
        else:  # SELL
            profit = pos["entry_ltp"] - current_ltp
        
        profit_class = "profit-positive" if profit >= 0 else "profit-negative"
        profit_symbol = "+" if profit >= 0 else ""
        
        positions_html += f"""
        <tr>
            <td><b>{pos['stock']}</b></td>
            <td><b>{pos['type']}</b></td>
            <td>₹{pos['entry_ltp']:.2f}</td>
            <td>₹{current_ltp:.2f}</td>
            <td class="{profit_class}">{profit_symbol}₹{profit:.2f}</td>
            <td>{pos['time']}</td>
        </tr>
        """
    
    return jsonify({"positions": positions_html})

@app.route("/get_movers")
def get_movers():
    global fyers
    
    if fyers is None:
        return jsonify({"gainers": "<tr><td colspan='4'>Please login first</td></tr>", 
                       "losers": "<tr><td colspan='4'>Please login first</td></tr>"})
    
    try:
        # Fetch quotes for all NIFTY 50 stocks
        symbols = ",".join(nifty50_stocks.values())
        quote_data = {"symbols": symbols}
        response = fyers.quotes(data=quote_data)
        
        if not response or "d" not in response:
            return jsonify({"gainers": "<tr><td colspan='4'>No data</td></tr>", 
                           "losers": "<tr><td colspan='4'>No data</td></tr>"})
        
        # Process stock data
        stock_data = []
        for item in response["d"]:
            try:
                symbol = item.get("n", "")
                stock_name = None
                for name, sym in nifty50_stocks.items():
                    if sym == symbol:
                        stock_name = name
                        break
                
                if not stock_name:
                    continue
                
                v = item.get("v", {})
                ltp = v.get("lp", 0)
                prev_close = v.get("prev_close_price", 0)
                
                if prev_close and prev_close > 0:
                    change_pct = ((ltp - prev_close) / prev_close) * 100
                    stock_data.append({
                        "name": stock_name,
                        "ltp": ltp,
                        "change_pct": change_pct
                    })
            except Exception as e:
                continue
        
        # Sort by change percentage
        stock_data.sort(key=lambda x: x["change_pct"], reverse=True)
        
        # Top 5 gainers
        gainers = stock_data[:5]
        gainers_html = ""
        for i, stock in enumerate(gainers, 1):
            gainers_html += f"""
            <tr style="background-color: #e8f5e9;">
                <td><b>{i}</b></td>
                <td><b>{stock['name']}</b></td>
                <td>₹{stock['ltp']:,.2f}</td>
                <td style="color: green; font-weight: bold;">+{stock['change_pct']:.2f}%</td>
            </tr>
            """
        
        # Top 5 losers
        losers = stock_data[-5:][::-1]
        losers_html = ""
        for i, stock in enumerate(losers, 1):
            losers_html += f"""
            <tr style="background-color: #ffebee;">
                <td><b>{i}</b></td>
                <td><b>{stock['name']}</b></td>
                <td>₹{stock['ltp']:,.2f}</td>
                <td style="color: red; font-weight: bold;">{stock['change_pct']:.2f}%</td>
            </tr>
            """
        
        return jsonify({"gainers": gainers_html, "losers": losers_html})
    
    except Exception as e:
        error_msg = f"<tr><td colspan='4'>Error: {str(e)}</td></tr>"
        return jsonify({"gainers": error_msg, "losers": error_msg})

@app.route("/get_price_patterns")
def get_price_patterns():
    global fyers
    
    if fyers is None:
        return jsonify({
            "open_low": "<tr><td colspan='5'>Please login first</td></tr>",
            "open_high": "<tr><td colspan='5'>Please login first</td></tr>"
        })
    
    try:
        # Fetch quotes for all NIFTY 50 stocks
        symbols = ",".join(nifty50_stocks.values())
        quote_data = {"symbols": symbols}
        response = fyers.quotes(data=quote_data)
        
        if not response or "d" not in response:
            return jsonify({
                "open_low": "<tr><td colspan='5'>No data</td></tr>",
                "open_high": "<tr><td colspan='5'>No data</td></tr>"
            })
        
        # Process stock data
        open_low_stocks = []
        open_high_stocks = []
        
        for item in response["d"]:
            try:
                symbol = item.get("n", "")
                stock_name = None
                for name, sym in nifty50_stocks.items():
                    if sym == symbol:
                        stock_name = name
                        break
                
                if not stock_name:
                    continue
                
                v = item.get("v", {})
                ltp = v.get("lp", 0)
                open_price = v.get("open_price", 0)
                high = v.get("high_price", 0)
                low = v.get("low_price", 0)
                prev_close = v.get("prev_close_price", 0)
                
                if not all([ltp, open_price, high, low, prev_close]):
                    continue
                
                change_pct = ((ltp - prev_close) / prev_close) * 100 if prev_close else 0
                
                # Check if Open = Low (with 0.1% tolerance)
                tolerance = open_price * 0.001  # 0.1% tolerance
                if abs(open_price - low) <= tolerance:
                    open_low_stocks.append({
                        "name": stock_name,
                        "open": open_price,
                        "low": low,
                        "ltp": ltp,
                        "change_pct": change_pct
                    })
                
                # Check if Open = High (with 0.1% tolerance)
                if abs(open_price - high) <= tolerance:
                    open_high_stocks.append({
                        "name": stock_name,
                        "open": open_price,
                        "high": high,
                        "ltp": ltp,
                        "change_pct": change_pct
                    })
            
            except Exception as e:
                continue
        
        # Sort by change percentage
        open_low_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        open_high_stocks.sort(key=lambda x: x["change_pct"])
        
        # Generate HTML for Open = Low stocks
        open_low_html = ""
        if open_low_stocks:
            for stock in open_low_stocks:
                change_color = "green" if stock["change_pct"] >= 0 else "red"
                change_symbol = "+" if stock["change_pct"] >= 0 else ""
                open_low_html += f"""
                <tr style="background-color: #e8f5e9;">
                    <td><b>{stock['name']}</b></td>
                    <td>₹{stock['open']:,.2f}</td>
                    <td>₹{stock['low']:,.2f}</td>
                    <td>₹{stock['ltp']:,.2f}</td>
                    <td style="color: {change_color}; font-weight: bold;">{change_symbol}{stock['change_pct']:.2f}%</td>
                </tr>
                """
        else:
            open_low_html = "<tr><td colspan='5'>No stocks with Open = Low pattern</td></tr>"
        
        # Generate HTML for Open = High stocks
        open_high_html = ""
        if open_high_stocks:
            for stock in open_high_stocks:
                change_color = "green" if stock["change_pct"] >= 0 else "red"
                change_symbol = "+" if stock["change_pct"] >= 0 else ""
                open_high_html += f"""
                <tr style="background-color: #ffebee;">
                    <td><b>{stock['name']}</b></td>
                    <td>₹{stock['open']:,.2f}</td>
                    <td>₹{stock['high']:,.2f}</td>
                    <td>₹{stock['ltp']:,.2f}</td>
                    <td style="color: {change_color}; font-weight: bold;">{change_symbol}{stock['change_pct']:.2f}%</td>
                </tr>
                """
        else:
            open_high_html = "<tr><td colspan='5'>No stocks with Open = High pattern</td></tr>"
        
        return jsonify({
            "open_low": open_low_html,
            "open_high": open_high_html
        })
    
    except Exception as e:
        error_msg = f"<tr><td colspan='5'>Error: {str(e)}</td></tr>"
        return jsonify({
            "open_low": error_msg,
            "open_high": error_msg
        })

@app.route("/chain_rows_diff")
def chain_rows_diff():
    global previous_data
    stock_name = request.args.get("stock", "RELIANCE")

    rows_html, spot_price, analysis_html, _, _, equity_html = generate_rows(stock_name)

    current_data = {"rows": rows_html, "analysis": analysis_html}

    diff_rows = ""
    if previous_data.get(stock_name) != current_data["rows"]:
        diff_rows = current_data["rows"]
        previous_data[stock_name] = current_data["rows"]

    return json.dumps({
        "rows": diff_rows, 
        "spot": spot_price, 
        "analysis": analysis_html,
        "equity": equity_html
    })

def generate_full_table(stock_name):
    rows_html, spot_price, analysis_html, ce_headers, pe_headers, equity_html = generate_rows(stock_name)
    return rows_html, spot_price, analysis_html, ce_headers, pe_headers, equity_html

def get_equity_details(stock_name):
    global fyers
    
    if stock_name not in nifty50_stocks:
        return "<p>Invalid stock</p>"
    
    symbol = nifty50_stocks[stock_name]
    
    try:
        # Fetch quote data
        quote_data = {"symbols": symbol}
        response = fyers.quotes(data=quote_data)
        
        if not response or "d" not in response or len(response["d"]) == 0:
            return f"<p>No equity data available for {stock_name}</p>"
        
        data = response["d"][0]["v"]
        
        ltp = data.get("lp", 0)
        open_price = data.get("open_price", 0)
        high = data.get("high_price", 0)
        low = data.get("low_price", 0)
        prev_close = data.get("prev_close_price", 0)
        volume = data.get("volume", 0)
        change = ltp - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        change_color = "green" if change >= 0 else "red"
        change_symbol = "+" if change >= 0 else ""
        
        equity_html = f"""
        <table>
            <tr>
                <th>Stock Name</th>
                <th>LTP</th>
                <th>Change</th>
                <th>Change %</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>Prev Close</th>
                <th>Volume</th>
                <th>Actions</th>
            </tr>
            <tr>
                <td><b>{stock_name}</b></td>
                <td><b>₹{ltp:,.2f}</b></td>
                <td style="color:{change_color}"><b>{change_symbol}₹{change:.2f}</b></td>
                <td style="color:{change_color}"><b>{change_symbol}{change_pct:.2f}%</b></td>
                <td>₹{open_price:,.2f}</td>
                <td>₹{high:,.2f}</td>
                <td>₹{low:,.2f}</td>
                <td>₹{prev_close:,.2f}</td>
                <td>{volume:,.0f}</td>
                <td>
                    <button class="btn btn-buy" onclick="placeOrder('BUY')">BUY</button>
                    <button class="btn btn-sell" onclick="placeOrder('SELL')">SELL</button>
                </td>
            </tr>
        </table>
        """
        
        return equity_html
    except Exception as e:
        return f"<p>Error fetching equity details: {str(e)}</p>"

def generate_rows(stock_name):
    global fyers
    
    # Get the stock symbol
    if stock_name not in nifty50_stocks:
        return "", "", "<p>Invalid stock name.</p>", "", "", ""
    
    symbol = nifty50_stocks[stock_name]
    
    # Fetch option chain data
    data = {"symbol": symbol, "strikecount": 50}
    response = fyers.optionchain(data=data)
    
    data_section = response.get("data", {}) if isinstance(response, dict) else {}
    options_data = data_section.get("optionsChain") or data_section.get("options_chain") or []

    if not options_data:
        equity_html = get_equity_details(stock_name)
        return "", "", f"<p>No option chain data available for {stock_name}. This stock may not have options.</p>", "", "", equity_html

    df = pd.json_normalize(options_data)
    if "strike_price" not in df.columns:
        possible_strike_cols = [c for c in df.columns if "strike" in c.lower()]
        if possible_strike_cols:
            df = df.rename(columns={possible_strike_cols[0]: "strike_price"})

    num_cols = ["strike_price", "ask", "bid", "ltp", "oi", "oich", "oichp", "prev_oi", "volume", "ltpch"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Get spot price
    spot_price = None
    for key in ("underlying_value", "underlyingValue", "underlying", "underlying_value_instrument"):
        if data_section.get(key) is not None:
            try:
                spot_price = float(data_section.get(key))
                break
            except Exception:
                pass

    strikes_all = sorted(df["strike_price"].dropna().unique())
    if spot_price is None:
        spot_price = float(strikes_all[len(strikes_all)//2]) if strikes_all else 0

    # Find ATM strike and show ±3 strikes
    atm_strike = min(strikes_all, key=lambda s: abs(s - spot_price)) if strikes_all else 0
    atm_index = strikes_all.index(atm_strike) if atm_strike in strikes_all else 0
    low = max(0, atm_index - 3)
    high = min(len(strikes_all), atm_index + 4)
    strikes_to_show = strikes_all[low:high] if strikes_all else []

    df = df[df["strike_price"].isin(strikes_to_show)]
    ce_df = df[df["option_type"] == "CE"].set_index("strike_price", drop=False) if "option_type" in df.columns else pd.DataFrame()
    pe_df = df[df["option_type"] == "PE"].set_index("strike_price", drop=False) if "option_type" in df.columns else pd.DataFrame()
    lr_cols = [c for c in ["ask", "bid", "ltp", "ltpch", "oi", "oich", "oichp", "prev_oi", "volume"] if c in df.columns]

    # Filter ITM options
    ce_itm_df = ce_df[ce_df["strike_price"] < spot_price] if not ce_df.empty else pd.DataFrame()
    pe_itm_df = pe_df[pe_df["strike_price"] > spot_price] if not pe_df.empty else pd.DataFrame()

    rows_html = ""
    for strike in strikes_to_show:
        ce_cells = ""
        pe_cells = ""
        for c in lr_cols:
            ce_val = ce_df.loc[strike, c] if (not ce_df.empty and strike in ce_df.index and c in ce_df.columns) else ""
            pe_val = pe_df.loc[strike, c] if (not pe_df.empty and strike in pe_df.index and c in pe_df.columns) else ""
            
            # Format values
            if ce_val != "" and not pd.isna(ce_val):
                ce_val = f"{ce_val:,.2f}" if c in ["ltp", "ltpch", "ask", "bid"] else f"{ce_val:,.0f}"
            else:
                ce_val = "-"
            
            if pe_val != "" and not pd.isna(pe_val):
                pe_val = f"{pe_val:,.2f}" if c in ["ltp", "ltpch", "ask", "bid"] else f"{pe_val:,.0f}"
            else:
                pe_val = "-"
            
            ce_cells += f"<td>{ce_val}</td>"
            pe_cells += f"<td>{pe_val}</td>"
        
        row_style = "style='background-color: #ffeb3b; font-weight: bold;'" if strike == atm_strike else ""
        rows_html += f"<tr {row_style}>{ce_cells}<td><b>{strike}</b></td>{pe_cells}</tr>"

    # Calculate totals
    ce_totals = ce_df[lr_cols].sum(numeric_only=True) if not ce_df.empty else pd.Series(0, index=lr_cols)
    pe_totals = pe_df[lr_cols].sum(numeric_only=True) if not pe_df.empty else pd.Series(0, index=lr_cols)
    ce_itm_totals = ce_itm_df[lr_cols].sum(numeric_only=True) if not ce_itm_df.empty else pd.Series(0, index=lr_cols)
    pe_itm_totals = pe_itm_df[lr_cols].sum(numeric_only=True) if not pe_itm_df.empty else pd.Series(0, index=lr_cols)

    ce_headers, pe_headers = generate_headers()

    ce_totals_cells = "".join([f"<td><b>{ce_totals[c]:,.2f}</b></td>" for c in lr_cols])
    rows_html += f"<tr style='background-color: #c8e6c9; font-weight: bold;'>{ce_totals_cells}<td>CE TOTAL</td><td></td></tr>"

    pe_totals_cells = "".join([f"<td></td>" for c in lr_cols])
    pe_totals_cells += "<td>PE TOTAL</td>" + "".join([f"<td><b>{pe_totals[c]:,.2f}</b></td>" for c in lr_cols])
    rows_html += f"<tr style='background-color: #c8e6c9; font-weight: bold;'>{pe_totals_cells}</tr>"

    ce_itm_totals_cells = "".join([f"<td><b>{ce_itm_totals[c]:,.2f}</b></td>" for c in lr_cols])
    rows_html += f"<tr style='background-color: #b3e5fc; font-weight: bold;'>{ce_itm_totals_cells}<td>CE ITM TOTAL</td><td></td></tr>"

    pe_itm_totals_cells = "".join([f"<td></td>" for c in lr_cols])
    pe_itm_totals_cells += "<td>PE ITM TOTAL</td>" + "".join([f"<td><b>{pe_itm_totals[c]:,.2f}</b></td>" for c in lr_cols])
    rows_html += f"<tr style='background-color: #b3e5fc; font-weight: bold;'>{pe_itm_totals_cells}</tr>"

    all_totals = ce_totals.add(pe_totals, fill_value=0)
    all_totals_cells = "".join([f"<td><b>{all_totals[c]:,.2f}</b></td>" for c in lr_cols])
    rows_html += f"<tr style='background-color: #ffd699; font-weight: bold;'>{all_totals_cells}<td>ALL TOTAL</td><td></td></tr>"

    analysis_html = generate_market_insights(ce_df, pe_df, spot_price, stock_name)
    equity_html = get_equity_details(stock_name)

    return rows_html, spot_price, analysis_html, ce_headers, pe_headers, equity_html

def generate_headers():
    lr_cols = ["ask", "bid", "ltp", "ltpch", "oi", "oich", "oichp", "prev_oi", "volume"]
    ce_headers = "".join([f"<th>{c.upper()}</th>" for c in lr_cols])
    pe_headers = "".join([f"<th>{c.upper()}</th>" for c in lr_cols])
    return ce_headers, pe_headers

def generate_market_insights(ce_df, pe_df, spot_price, stock_name):
    try:
        total_ce_oi = ce_df["oi"].sum() if not ce_df.empty and "oi" in ce_df.columns else 0
        total_pe_oi = pe_df["oi"].sum() if not pe_df.empty and "oi" in pe_df.columns else 0
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else None

        strongest_support = pe_df.loc[pe_df["oi"].idxmax(), "strike_price"] if not pe_df.empty and "oi" in pe_df.columns and len(pe_df) > 0 else None
        strongest_resistance = ce_df.loc[ce_df["oi"].idxmax(), "strike_price"] if not ce_df.empty and "oi" in ce_df.columns and len(ce_df) > 0 else None

        ce_vol = ce_df["volume"].sum() if not ce_df.empty and "volume" in ce_df.columns else 0
        pe_vol = pe_df["volume"].sum() if not pe_df.empty and "volume" in pe_df.columns else 0
        volume_trend = "CE Volume > PE Volume → Bullish" if ce_vol > pe_vol else "PE Volume > CE Volume → Bearish"

        trend_bias = ""
        if pcr is not None:
            if pcr > 1:
                trend_bias = "Bearish 📉"
            elif pcr < 0.8:
                trend_bias = "Bullish 📈"
            else:
                trend_bias = "Neutral ⚖️"

        return f"""
        <h3>🔎 Market Insights for {stock_name}</h3>
        <ul>
            <li><b>Spot Price:</b> ₹{spot_price:,.2f}</li>
            <li><b>Total CE OI:</b> {total_ce_oi:,.0f}</li>
            <li><b>Total PE OI:</b> {total_pe_oi:,.0f}</li>
            <li><b>Put-Call Ratio (PCR):</b> {pcr if pcr else 'N/A'}</li>
            <li><b>Volume Trend:</b> {volume_trend}</li>
            <li><b>Strongest Support (PE OI):</b> ₹{strongest_support if strongest_support else 'N/A'}</li>
            <li><b>Strongest Resistance (CE OI):</b> ₹{strongest_resistance if strongest_resistance else 'N/A'}</li>
            <li><b>Trend Bias:</b> {trend_bias}</li>
        </ul>
        """
    except Exception as e:
        return f"<p>Error in analysis: {e}</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print("\n" + "="*60)
    print("🚀 Sajid Shaikh NIFTY 50 Stocks Option Chain Viewer")
    print("="*60)
    print(f"📍 Server: http://127.0.0.1:{port}")
    print("📊 View NIFTY 50 stock options")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=True)
