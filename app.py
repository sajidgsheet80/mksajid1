from fyers_apiv3 import fyersModel
from flask import Flask, request, render_template_string, jsonify, redirect
import webbrowser
import pandas as pd
import os
from datetime import datetime

# ---- Credentials ----
client_id = "VMS68P9EK0-100"
secret_key = "ZJ0CFWZEL1"
redirect_uri = "http://127.0.0.1:5000/callback"
grant_type = "authorization_code"
response_type = "code"
state = "sample"

# ---- Session ----
appSession = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type=response_type,
    grant_type=grant_type,
    state=state
)

# ---- Flask ----
app = Flask(__name__)
app.secret_key = "sajid_secret"

# ---- Globals ----
access_token_global = None
fyers = None
atm_strike = None
initial_data = None

atm_ce_plus20 = 20
atm_pe_plus20 = 20
signals = []

# To store LTP logs
ltp_log = []

@app.route("/", methods=["GET", "POST"])
def index():
    global atm_ce_plus20, atm_pe_plus20
    if request.method == "POST":
        try:
            atm_ce_plus20 = float(request.form.get("atm_ce_plus20", atm_ce_plus20))
        except (ValueError, TypeError):
            atm_ce_plus20 = 20
        try:
            atm_pe_plus20 = float(request.form.get("atm_pe_plus20", atm_pe_plus20))
        except (ValueError, TypeError):
            atm_pe_plus20 = 20
    return render_template_string(TEMPLATE, atm_ce_plus20=atm_ce_plus20, atm_pe_plus20=atm_pe_plus20, ltp_log=ltp_log)

@app.route("/login")
def login():
    login_url = appSession.generate_authcode()
    webbrowser.open(login_url, new=1)
    return redirect(login_url)

@app.route("/callback")
def callback():
    global access_token_global, fyers
    auth_code = request.args.get("auth_code")
    if auth_code:
        appSession.set_token(auth_code)
        token_response = appSession.generate_token()
        access_token_global = token_response.get("access_token")
        fyers = fyersModel.FyersModel(client_id=client_id, token=access_token_global, is_async=False, log_path="")
        return "<h2>✅ Authentication Successful! You can return to the app 🚀</h2>"
    return "❌ Authentication failed. Please retry."

@app.route("/fetch")
def fetch_option_chain():
    global fyers, atm_strike, initial_data, atm_ce_plus20, atm_pe_plus20, signals
    if fyers is None:
        return jsonify({"error": "⚠ Please login first!"})
    try:
        data = {"symbol": "NSE:NIFTY50-INDEX", "strikecount": 50, "timestamp": ""}
        response = fyers.optionchain(data=data)

        if "data" not in response or "optionsChain" not in response["data"]:
            return jsonify({"error": f"Invalid response from API: {response}"})

        options_data = response["data"]["optionsChain"]
        if not options_data:
            return jsonify({"error": "No options data found!"})

        df = pd.DataFrame(options_data)
        if df.empty:
            return jsonify({"error": "Options chain data is empty."})

        df_ce = df[df['option_type'] == 'CE'].set_index('strike_price')
        df_pe = df[df['option_type'] == 'PE'].set_index('strike_price')

        df_ce.columns = [f"CE_{col}" for col in df_ce.columns]
        df_pe.columns = [f"PE_{col}" for col in df_pe.columns]

        df_pivot = df_ce.join(df_pe, how="outer").reset_index()

        if atm_strike is None:
            nifty_spot = response["data"].get("underlyingValue", df_pivot["strike_price"].iloc[len(df_pivot) // 2])
            atm_strike = min(df_pivot["strike_price"], key=lambda x: abs(x - nifty_spot))
            initial_data = df_pivot.to_dict(orient="records")
            signals.clear()
        else:
            initial_data = df_pivot.to_dict(orient="records")

        sorted_strikes = sorted(df_pivot["strike_price"].unique())
        atm_index = sorted_strikes.index(atm_strike)

        before_atm = sorted_strikes[max(0, atm_index - 7):atm_index]
        after_atm = sorted_strikes[atm_index + 1:atm_index + 8]
        selected_strikes = before_atm + [atm_strike] + after_atm

        df_pivot = df_pivot[df_pivot["strike_price"].isin(selected_strikes)]
        df_pivot["strike_order"] = df_pivot["strike_price"].apply(lambda x: selected_strikes.index(x))
        df_pivot = df_pivot.sort_values(by="strike_order")

        return df_pivot.to_json(orient="records")

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/ltp", methods=["GET"])
def ltp_calculator():
    global ltp_log
    strike = request.args.get("strike", type=float)
    option_type = request.args.get("type", default="CE")
    if initial_data is None:
        return jsonify({"error": "Option chain not loaded yet. Please fetch first."})

    df = pd.DataFrame(initial_data)
    col_prefix = option_type
    ltp_col = f"{col_prefix}_ltp"

    row = df[df["strike_price"] == strike]
    if row.empty:
        return jsonify({"error": f"No data for strike {strike} {option_type}"})

    ltp = row[ltp_col].values[0]

    # Add record to log with unique ID
    now = datetime.now()
    record_id = len(ltp_log) + 1
    record = {
        "id": record_id,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "strike": strike,
        "type": option_type,
        "ltp": ltp
    }
    ltp_log.append(record)

    return jsonify({"strike": strike, "type": option_type, "ltp": ltp, "log": ltp_log})

@app.route("/delete_ltp/<int:id>", methods=["DELETE"])
def delete_ltp(id):
    global ltp_log
    ltp_log = [rec for rec in ltp_log if rec["id"] != id]
    return jsonify({"success": True})

# ---- HTML Template ----
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Sajid Shaikh Algo Software</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 20px; }
    table { border-collapse: collapse; width: 100%; font-size: 12px; }
    th, td { border: 1px solid #aaa; padding: 6px; text-align: center; }
    th { background-color: #1a73e8; color: white; }
    tr:nth-child(even) { background-color: #f2f2f2; }
    tr.atm { background-color: #ffeb3b; font-weight: bold; }
    tr.total { background-color: #4caf50; color: white; font-weight: bold; }
    .msg { margin-top: 10px; font-size: 14px; font-weight: bold; padding: 5px; }
    .bullish { background: #d4edda; color: #155724; }
    .bearish { background: #f8d7da; color: #721c24; }
    .sideways { background: #fff3cd; color: #856404; }
    .delete-btn { background:red;color:white;border:none;padding:2px 6px;cursor:pointer;border-radius:3px;}
  </style>
</head>
<body>
  <h2>Sajid Shaikh Algo Software : +91 9834370368</h2>
  <a href="/login" target="_blank">🔑 Login</a>
  <form method="POST" action="/">
    <label>CE Threshold (+ over initial):</label>
    <input type="number" id="atm_ce_plus20" name="atm_ce_plus20" step="0.1" value="{{ atm_ce_plus20 }}" required>
    <label>PE Threshold (+ over initial):</label>
    <input type="number" id="atm_pe_plus20" name="atm_pe_plus20" step="0.1" value="{{ atm_pe_plus20 }}" required>
    <button type="submit">Update Thresholds</button>
  </form>

  <h3>Option Chain with Live LTP</h3>
  <table>
    <tbody id="chain"></tbody>
  </table>

  <div id="sellersCompare" class="msg"></div>
  <div id="writingCompare" class="msg"></div>
  <div id="marketSentiment" class="msg"></div>
  <div id="volumeSignal" class="msg"></div>

  <h3>Live LTP Calculator</h3>
  <form id="ltpForm">
    <label>Strike Price:</label>
    <input type="number" id="strikeInput" step="1" required>
    <label>Option Type:</label>
    <select id="optionType">
      <option value="CE">Call (CE)</option>
      <option value="PE">Put (PE)</option>
    </select>
    <button type="submit">Get LTP</button>
  </form>
  <div id="ltpResult" class="msg"></div>

  <h3>LTP Log</h3>
  <table id="ltpLog" border="1">
    <tr>
      <th>Date</th><th>Time</th><th>Strike</th><th>Type</th><th>LTP</th><th>Action</th>
    </tr>
    {% for record in ltp_log %}
    <tr data-id="{{ record.id }}">
      <td>{{ record.date }}</td>
      <td>{{ record.time }}</td>
      <td>{{ record.strike }}</td>
      <td>{{ record.type }}</td>
      <td>{{ record.ltp }}</td>
      <td><button class="delete-btn" onclick="deleteLTP({{ record.id }})">Delete</button></td>
    </tr>
    {% endfor %}
  </table>

<script>
var atmStrike = null;

async function fetchChain(){
    let res = await fetch("/fetch");
    let data = await res.json();
    let tbl = document.getElementById("chain");
    tbl.innerHTML = "";

    if(data.error){
        tbl.innerHTML = `<tr><td colspan="20">${data.error}</td></tr>`;
        return;
    }

    if(atmStrike === null){
        atmStrike = data[Math.floor(data.length / 2)].strike_price;
    }

    tbl.innerHTML += `
        <tr>
            <th colspan="6">CE</th>
            <th>Strike</th>
            <th colspan="6">PE</th>
        </tr>
        <tr>
            <th>Volume</th><th>POI</th><th>OI</th><th>Oich</th><th>LTPch</th><th>LTP</th>
            <th></th>
            <th>LTP</th><th>LTPch</th><th>Oich</th><th>OI</th><th>POI</th><th>Volume</th>
        </tr>
    `;

    let totals = { CE_volume:0, CE_prev_oi:0, CE_oi:0, CE_oich:0, CE_ltpch:0, CE_ltp:0,
                   PE_ltp:0, PE_ltpch:0, PE_oich:0, PE_oi:0, PE_prev_oi:0, PE_volume:0 };

    data.forEach(row=>{
        let cls = (row.strike_price === atmStrike) ? "atm" : "";

        tbl.innerHTML += `
            <tr class="${cls}" data-strike="${row.strike_price}">
                <td>${row.CE_volume ?? "-"}</td>
                <td>${row.CE_prev_oi ?? "-"}</td>
                <td>${row.CE_oi ?? "-"}</td>
                <td>${row.CE_oich ?? "-"}</td>
                <td>${row.CE_ltpch ?? "-"}</td>
                <td class="CE_ltp">${row.CE_ltp ?? "-"}</td>

                <td>${row.strike_price ?? "-"}</td>

                <td class="PE_ltp">${row.PE_ltp ?? "-"}</td>
                <td>${row.PE_ltpch ?? "-"}</td>
                <td>${row.PE_oich ?? "-"}</td>
                <td>${row.PE_oi ?? "-"}</td>
                <td>${row.PE_prev_oi ?? "-"}</td>
                <td>${row.PE_volume ?? "-"}</td>
            </tr>
        `;

        for (let key in totals){
            let val = row[key];
            if(val !== undefined && !isNaN(val)){
                totals[key] += Number(val);
            }
        }
    });

    tbl.innerHTML += `
        <tr class="total">
            <td>${totals.CE_volume}</td>
            <td>${totals.CE_prev_oi}</td>
            <td>${totals.CE_oi}</td>
            <td>${totals.CE_oich}</td>
            <td>${totals.CE_ltpch}</td>
            <td class="CE_ltp">${totals.CE_ltp}</td>
            <td>Total</td>
            <td class="PE_ltp">${totals.PE_ltp}</td>
            <td>${totals.PE_ltpch}</td>
            <td>${totals.PE_oich}</td>
            <td>${totals.PE_oi}</td>
            <td>${totals.PE_prev_oi}</td>
            <td>${totals.PE_volume}</td>
        </tr>
    `;

    updateSignals(totals);
}

function updateSignals(totals){
    let sellersMsg = totals.CE_oi > totals.PE_oi ? "🧑‍💼 Sellers Active on CE" :
                     totals.PE_oi > totals.CE_oi ? "🧑‍💼 Sellers Active on PE" : "⚖ Sellers Balanced";
    document.getElementById("sellersCompare").innerText = sellersMsg;

    let writingMsg = totals.CE_oich > totals.PE_oich ? "✍️ Writing Active on CE" :
                     totals.PE_oich > totals.CE_oich ? "✍️ Writing Active on PE" : "⚖ Writing Balanced";
    document.getElementById("writingCompare").innerText = writingMsg;

    let marketMsg="", marketClass="";
    if(totals.CE_ltpch < 0 && totals.PE_ltpch < 0){marketMsg="↔ Market Sideways"; marketClass="sideways";}
    else if(totals.CE_ltpch > 0 && totals.PE_ltpch < 0){marketMsg="📈 Bullish Market"; marketClass="bullish";}
    else if(totals.CE_ltpch < 0 && totals.PE_ltpch > 0){marketMsg="📉 Bearish Market"; marketClass="bearish";}
    else if(totals.CE_ltpch > 0 && totals.PE_ltpch > 0){marketMsg="🟢 Buy Any"; marketClass="bullish";}
    else {marketMsg="⚖ Neutral Market"; marketClass="sideways";}
    let marketDiv = document.getElementById("marketSentiment");
    marketDiv.innerText = marketMsg;
    marketDiv.className = "msg " + marketClass;

    let volumeMsg="", volumeClass="";
    if(totals.CE_volume > totals.PE_volume){volumeMsg="🔹 Bullish Volume Signal"; volumeClass="bullish";}
    else if(totals.CE_volume < totals.PE_volume){volumeMsg="🔻 Bearish Volume Signal"; volumeClass="bearish";}
    else {volumeMsg="⚖ Neutral Volume Signal"; volumeClass="sideways";}
    let volumeDiv=document.getElementById("volumeSignal");
    volumeDiv.innerText=volumeMsg;
    volumeDiv.className="msg "+volumeClass;
}

// LTP Calculator
document.getElementById("ltpForm").addEventListener("submit", async function(e){
    e.preventDefault();
    let strike = document.getElementById("strikeInput").value;
    let type = document.getElementById("optionType").value;
    let res = await fetch(`/ltp?strike=${strike}&type=${type}`);
    let data = await res.json();
    let ltpDiv = document.getElementById("ltpResult");
    let logTbl = document.getElementById("ltpLog");
    if(data.error){
        ltpDiv.innerText = data.error;
        ltpDiv.className = "msg sideways";
    } else {
        ltpDiv.innerText = `LTP of ${data.strike} ${data.type} = ${data.ltp}`;
        ltpDiv.className = "msg bullish";

        // Append to log table with Delete button
        let record = data.log[data.log.length-1];
        let row = logTbl.insertRow(-1);
        row.setAttribute("data-id", record.id);
        row.insertCell(0).innerText = record.date;
        row.insertCell(1).innerText = record.time;
        row.insertCell(2).innerText = record.strike;
        row.insertCell(3).innerText = record.type;
        row.insertCell(4).innerText = record.ltp;
        let actionCell = row.insertCell(5);
        let delBtn = document.createElement("button");
        delBtn.innerText = "Delete";
        delBtn.className = "delete-btn";
        delBtn.onclick = () => deleteLTP(record.id);
        actionCell.appendChild(delBtn);
    }
});

async function deleteLTP(id){
    let res = await fetch(`/delete_ltp/${id}`, { method: 'DELETE' });
    let data = await res.json();
    if(data.success){
        let row = document.querySelector(`tr[data-id='${id}']`);
        if(row) row.remove();
    }
}

setInterval(fetchChain, 2000);
window.onload = fetchChain;
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
