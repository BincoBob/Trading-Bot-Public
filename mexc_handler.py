import os
import time
import hmac
import hashlib
import requests
import urllib.parse
import logging
from dotenv import load_dotenv

# .env laden
load_dotenv()

# API-Zugangsdaten
API_KEY = os.getenv("MEXC_API_KEY")
SECRET_KEY = os.getenv("MEXC_API_SECRET")
base_url = "https://api.mexc.com"

# ✅ Signatur korrekt generieren (alphabetisch sortiert!)
def sign_request(params, secret_key):
    if not secret_key:
        raise ValueError("SECRET_KEY ist nicht gesetzt. Bitte .env prüfen!")
    sorted_params = dict(sorted(params.items()))
    query_string = urllib.parse.urlencode(sorted_params)
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# ✅ BTC-Balance vom MEXC-Konto abrufen (nur mit timestamp!)
def hole_btc_balance():
    try:
        endpoint = "/api/v3/account"
        url = f"{base_url}{endpoint}"
        timestamp = int(time.time() * 1000)

        params = {
            "timestamp": timestamp
        }
        params["signature"] = sign_request(params, SECRET_KEY)

        headers = {
            "X-MEXC-APIKEY": API_KEY
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        balances = response.json().get("balances", [])
        for b in balances:
            if b["asset"] == "BTC":
                return float(b["free"])
        return 0.0
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der BTC-Balance: {e}")
        return 0.0

# ✅ BTCUSDT Preis von MEXC holen
def get_current_price(symbol="BTCUSDT"):
    try:
        url = f"{base_url}/api/v3/ticker/price"
        params = {"symbol": symbol.upper()}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return float(response.json()["price"])
    except Exception as e:
        logging.error(f"Fehler beim Abrufen des Preises für {symbol}: {e}")
        return None

# ✅ Gesamtguthaben (geschätzt in USD) + BTC-Balance abrufen
def get_mexc_balances():
    try:
        endpoint = "/api/v3/account"
        url = f"{base_url}{endpoint}"
        timestamp = int(time.time() * 1000)

        params = {
            "timestamp": timestamp
        }
        params["signature"] = sign_request(params, SECRET_KEY)
        headers = {
            "X-MEXC-APIKEY": API_KEY
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        balances = response.json().get("balances", [])

        btc = 0.0
        usdt = 0.0

        for b in balances:
            if b["asset"] == "BTC":
                btc = float(b["free"])
            elif b["asset"] == "USDT":
                usdt = float(b["free"])

        return usdt, btc

    except Exception as e:
        logging.error(f"Fehler in get_mexc_balances: {e}")
        return 0.0, 0.0

def get_mexc_wallet_positions():
    """Lädt alle Wallet-Positionen vom MEXC-Konto"""
    try:
        endpoint = "/api/v3/account"
        url = f"{base_url}{endpoint}"
        timestamp = int(time.time() * 1000)

        params = {
            "timestamp": timestamp
        }
        params["signature"] = sign_request(params, SECRET_KEY)
        headers = {
            "X-MEXC-APIKEY": API_KEY
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        usdt_balance = 0.0
        positions = {}

        for asset in data.get("balances", []):
            free = float(asset["free"])
            symbol = asset["asset"]

            if free > 0:
                if symbol == "USDT":
                    usdt_balance = free
                else:
                    positions[symbol + "USDT"] = free  # z. B. "DOGE" → "DOGEUSDT"

        return usdt_balance, positions

    except Exception as e:
        logging.error(f"❌ Fehler beim Laden der Wallet-Positionen: {e}")
        return 0.0, {}




# ✅ Effektive Market-Order platzieren (BUY/SELL)
def place_market_order(symbol, side, quantity=None, quoteOrderQty=None):
    try:
        endpoint = "/api/v3/order"
        url = base_url + endpoint
        timestamp = int(time.time() * 1000)

        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "timestamp": timestamp
        }

        if quantity:
            if quantity < 0.0001:
                logging.warning(f"❌ BTC-Menge zu gering für MEXC: {quantity:.8f}")
                return None
            params["quantity"] = quantity
        elif quoteOrderQty:
            params["quoteOrderQty"] = quoteOrderQty
        else:
            raise ValueError("Entweder quantity oder quoteOrderQty muss gesetzt sein.")

        params["signature"] = sign_request(params, SECRET_KEY)
        headers = {"X-MEXC-APIKEY": API_KEY}

        response = requests.post(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    except Exception as e:
        logging.error(f"Fehler bei Market-Order: {e}")
        return None

# ✅ BTC kaufen mit USDT-Betrag
def kaufen(quote_usdt):
    preis = get_current_price("BTCUSDT")
    if preis is None:
        return False
    return place_market_order("BTCUSDT", "BUY", quoteOrderQty=round(quote_usdt, 2))

# ✅ BTC verkaufen mit Menge in BTC
def verkaufen(menge_btc):
    preis = get_current_price("BTCUSDT")
    if preis is None:
        return False
    return place_market_order("BTCUSDT", "SELL", quantity=round(menge_btc, 6))

# ✅ Dynamisch verkaufen (prozentual vom Bestand)
def verkaufen_dynamic(aktueller_preis, prozent_des_bestands):
    try:
        _, bitcoin_bestand = get_mexc_balances()
        min_sale_usd = 5.0
        menge_btc = bitcoin_bestand * prozent_des_bestands
        erlös = menge_btc * aktueller_preis

        if erlös < min_sale_usd:
            min_btc_needed = min_sale_usd / aktueller_preis
            if bitcoin_bestand >= min_btc_needed:
                menge_btc = min_btc_needed
            else:
                return False

        result = verkaufen(menge_btc)
        return result is not None
    except Exception as e:
        logging.error(f"Fehler in verkaufen_dynamic: {e}")
        return False

# ✅ Dynamisch kaufen (prozentual vom Guthaben)
def kaufen_dynamic(aktueller_preis, prozent_des_guthabens):
    try:
        guthaben, _ = get_mexc_balances()
        min_kauf_usd = 5.0
        betrag_usdt = guthaben * prozent_des_guthabens

        if betrag_usdt < min_kauf_usd:
            if guthaben >= min_kauf_usd:
                betrag_usdt = min_kauf_usd
            else:
                return False

        result = kaufen(betrag_usdt)
        return result is not None
    except Exception as e:
        logging.error(f"Fehler in kaufen_dynamic: {e}")
        return False
