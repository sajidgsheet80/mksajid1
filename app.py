import logging
from tradingapi_a.mconnect import *
import pandas as pd
import io

logging.basicConfig(level=logging.INFO)

# -------- LOGIN --------
mconnect_obj = MConnect()
mconnect_obj.verify_totp("CJOHJvQ/lUBtRZSXIVAtd3wkLRaSDpVGbO92K+FAIo8=", "557404")

# -------- DOWNLOAD INSTRUMENTS --------
res = mconnect_obj.get_instruments()
csv = io.BytesIO(res)
df = pd.read_csv(csv)

print("Available Columns:", df.columns)

# -------- FIND TOKEN COLUMN --------
token_col = None
for col in ["token","instrument_token","symboltoken","instrumenttoken"]:
    if col in df.columns:
        token_col = col
        break

print("Token column used:", token_col)

# -------- FILTER NIFTY OPTIONS --------
nifty = df[
    (df["segment"] == "OPTIDX") &
    (df["exchange"] == "NFO") &
    (df["tradingsymbol"].str.startswith("NIFTY"))
]

# -------- NEAREST EXPIRY --------
exp_list = nifty["expiry"].dropna().unique().tolist()
exp_list.sort()
nearest_exp = exp_list[0]

print("Nearest Expiry:", nearest_exp)

nifty_exp = nifty[nifty["expiry"] == nearest_exp]

# -------- EXAMPLE NIFTY PRICE --------
nifty_price = 25620

# -------- ATM STRIKE --------
atm_strike = round(nifty_price / 50) * 50
print("ATM Strike:", atm_strike)

# -------- ±10 STRIKES --------
lower_strike = atm_strike - 500
upper_strike = atm_strike + 500

strike_range = nifty_exp[
    (nifty_exp["strike"] >= lower_strike) &
    (nifty_exp["strike"] <= upper_strike)
]

# -------- CE / PE FILTER --------
if "option_type" in strike_range.columns:
    ce_options = strike_range[strike_range["option_type"] == "CE"]
    pe_options = strike_range[strike_range["option_type"] == "PE"]
else:
    ce_options = strike_range[strike_range["tradingsymbol"].str.endswith("CE")]
    pe_options = strike_range[strike_range["tradingsymbol"].str.endswith("PE")]

# -------- OUTPUT --------
print("\nCALL OPTIONS (±10 strikes)")
if token_col:
    print(ce_options[["tradingsymbol","strike",token_col]].sort_values("strike"))
else:
    print(ce_options[["tradingsymbol","strike"]].sort_values("strike"))

print("\nPUT OPTIONS (±10 strikes)")
if token_col:
    print(pe_options[["tradingsymbol","strike",token_col]].sort_values("strike"))
else:
    print(pe_options[["tradingsymbol","strike"]].sort_values("strike"))
