from trading_bot import execute_buy, execute_sell, get_balance, get_position
import requests
import random
from flask import Flask, render_template, jsonify
import os
import json



app = Flask(__name__, template_folder="templates")

# Dummy wallet state (simulate some balance)
from trading_bot import guthaben, bitcoin_bestand

def get_live_wallet():
    return {
        "USDT": round(guthaben, 2),
        "BTC": round(bitcoin_bestand, 8),
        "positions": {}  # Option für spätere Erweiterung
    }


def get_mexc_cheap_coins(limit_usd=5, top_n=5, min_volume_usdt=300000, smart_suggestions=None):
    try:
        print("🔍 Starte get_mexc_cheap_coins()")
        exchange_info = requests.get("https://api.mexc.com/api/v3/exchangeInfo", timeout=10).json()
        tickers = requests.get("https://api.mexc.com/api/v3/ticker/price", timeout=10).json()
        volumes = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=10).json()

        prices = {x['symbol']: float(x['price']) for x in tickers}
        volume_map = {x['symbol']: float(x.get('quoteVolume', 0)) for x in volumes}

        potential = []

        for sym in exchange_info['symbols']:
            symbol = sym['symbol']
            if not symbol.endswith("USDT") or symbol.endswith("_M") or symbol.endswith("_W") or symbol.startswith("BTC"):
                continue

            price = prices.get(symbol)
            volume = volume_map.get(symbol, 0)
            if not price or price > limit_usd or volume < min_volume_usdt:
                continue

            volatility = round(random.uniform(0.01, 0.2), 4)  # simuliert
            min_qty = 1
            step_size = 1
            trade_value = price * min_qty

            potential.append({
                "symbol": symbol,
                "price": price,
                "minQty": min_qty,
                "minValueUSD": round(trade_value, 4),
                "stepSize": step_size,
                "volatility": volatility,
                "volume": round(volume, 2)
            })

        # Top-N nach Volatilität auswählen
        top_coins = sorted(potential, key=lambda x: x['volatility'], reverse=True)[:top_n]
        result = []

        for coin in top_coins:
            symbol = coin["symbol"]
            price = coin["price"]
            min_qty = coin["minQty"]
            trade_value = price * min_qty
            position_size = round(min_qty, 6)

            wallet = get_live_wallet()  # Live-Werte aus trading_bot
            if wallet["USDT"] >= trade_value:
                buy_percentage = min(0.05, trade_value / wallet["USDT"])
                success = kaufen_dynamic(price, buy_percentage)
                if success:
                    print(f"🛒 Gekauft (live): {symbol} für ca. {trade_value:.4f} USD")
                else:
                    print(f"❌ Kauf fehlgeschlagen für {symbol}")

            wallet = get_live_wallet()  # Aktuelles Wallet holen

            if symbol in wallet["positions"]:
            # Mit 10% Wahrscheinlichkeit oder wenn Position groß genug, verkaufen
                if random.random() < 0.1 or wallet["positions"][symbol] * price > 10:
                    print(f"📉 Verkaufssignal für {symbol}")

                    # Verkauf nur durchführen, wenn er größer als Mindestbetrag (1 USD)
                    selling_percentage = 1.0  # Komplett verkaufen
                    success = verkaufen_dynamic(price, selling_percentage)

                    if success:
                        print(f"💸 Verkauft (live): {symbol} für ca. {wallet['positions'][symbol] * price:.4f} USD")
                    else:
                        print(f"❌ Verkauf fehlgeschlagen für {symbol}")
            coin["walletPosition"] = round(get_live_wallet()["positions"].get(symbol, 0), 6)
            result.append(coin)

        print(f"✅ Top {top_n} Coins ausgewählt und verarbeitet")
        return result

    except Exception as e:
        print(f"❌ Fehler beim Laden der günstigen Coins: {e}")
        return []

def generate_coin_details(coin):
    details_html = f"""
    <div class='coin-box card p-3'>
        <h4>{coin['symbol']} Übersicht</h4>
        <ul>
            <li>Preis: {coin['price']}</li>
            <li>minQty: {coin['minQty']}</li>
            <li>Minimale Investition: {coin['minValueUSD']} USD</li>
            <li>Volatilität (simuliert): {coin['volatility']}</li>
            <li>24h Volumen: {coin['volume']} USD</li>
            <li>Wallet Bestand: {coin['walletPosition']}</li>
        </ul>
        <a href="/coin/{coin['symbol']}" class="btn btn-primary mt-2">🔍 Details anzeigen</a>
    </div>
    """
    return details_html

def load_smart_suggestions():
    try:
        with open("smart_top.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ Noch keine smart_top.json vorhanden – verwende alle Coins.")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Laden der Smartlist: {e}")
        return None



@app.route("/")
def index():
    smart_top = load_smart_suggestions()
    coins = get_mexc_cheap_coins(smart_suggestions=smart_top)
    for coin in coins:
        coin['details'] = generate_coin_details(coin)
    return render_template("dashboard.html", wallet=wallet, coins=coins)

@app.route("/api/coins")
def api_coins():
    smart_top = load_smart_suggestions()
    coins = get_mexc_cheap_coins(smart_suggestions=smart_top)
    for coin in coins:
        coin['details'] = generate_coin_details(coin)
    return jsonify(coins)

@app.route("/api/wallet")
def api_wallet():
    # Gesamtwert starten mit deinem USDT-Bestand
    total_value = wallet["USDT"]

    # Hier speichern wir, wie viel jeder Coin in USD wert ist
    coin_values = {}

    # Preise von allen Coins holen
    tickers = requests.get("https://api.mexc.com/api/v3/ticker/price", timeout=10).json()
    prices = {x['symbol']: float(x['price']) for x in tickers}

    # Durch deine gehaltenen Coins gehen
    for symbol, amount in wallet["positions"].items():
        price = prices.get(symbol, 0)  # aktuellen Preis holen
        coin_value = price * amount    # Wert in USD berechnen
        total_value += coin_value      # zum Gesamtwert hinzufügen
        coin_values[symbol] = round(coin_value, 6)  # z. B. {'DOGEUSDT': 2.15}

    # JSON-Antwort mit allem zurückgeben
    return jsonify({
        "USDT": round(wallet["USDT"], 2),          # z. B. 17.36
        "BTC": round(wallet.get("BTC", 0), 8),     # z. B. 0.00021342
        "total": round(total_value, 2),            # z. B. 24.28
        "positions": coin_values                   # alle Coins im Wallet
    })

    
@app.route("/api/current_price")
def current_price():
    # Beispiel-Daten zurückgeben
    return jsonify({"price": 0.0134, "change": "+3.2%", "last_updated": "just now"})

@app.route("/api/portfolio")
def portfolio():
    return jsonify({
        "value": 12.50,
        "usd_balance": 4.60,
        "btc_balance": 0.00018,
        "usd_pct": 36.8,
        "btc_pct": 63.2
    })

@app.route("/api/trade_history")
def trade_history():
    return jsonify([
        {"type": "BUY", "amount": 0.0001, "price": 0.013, "value": 1.3, "time": "02:13"},
        {"type": "SELL", "amount": 0.0001, "price": 0.014, "value": 1.4, "time": "03:05"}
    ])

@app.route("/api/config")
def config():
    return jsonify({
        "sell_threshold": 0.015,
        "buy_percentage": 25,
        "sell_percentage": 15,
        "check_interval": 10
    })

@app.route("/api/bot_status")
def bot_status():
    return jsonify({"enabled": True})

@app.route("/api/price_history")
def price_history():
    return jsonify({
        "labels": ["03:00", "03:10", "03:20"],
        "prices": [0.012, 0.013, 0.0134]
    })    

@app.route("/coin/<symbol>")
def coin_detail(symbol):
    coins = get_mexc_cheap_coins()
    selected = next((c for c in coins if c['symbol'] == symbol), None)
    if not selected:
        return f"Coin {symbol} nicht gefunden", 404
    return render_template("coin_detail.html", coin=selected)


if __name__ == "__main__":
    app.run(debug=True)