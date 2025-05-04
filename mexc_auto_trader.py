import requests
import random
from flask import Flask, render_template, jsonify
import os

app = Flask(__name__, template_folder="templates")

# Dummy wallet state (simulate some balance)
wallet = {
    "USDT": 20.0,
    "BTC": 0.00022172,
    "positions": {}
}

def get_mexc_cheap_coins(limit_usd=5, top_n=5, min_volume_usdt=300000, smart_suggestions=None):
    try:
        print("🔍 Starte get_mexc_cheap_coins()")
        exchange_info = requests.get("https://api.mexc.com/api/v3/exchangeInfo", timeout=10).json()
        tickers = requests.get("https://api.mexc.com/api/v3/ticker/price", timeout=10).json()
        volumes = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=10).json()

        prices = {x['symbol']: float(x['price']) for x in tickers}
        volume_map = {x['symbol']: float(x.get('quoteVolume', 0)) for x in volumes}

        result = []
        count_checked = 0

        for sym in exchange_info['symbols']:
            symbol = sym['symbol']
            if not symbol.endswith("USDT") or symbol.endswith("_M") or symbol.endswith("_W") or symbol.startswith("BTC"):
                continue

            # NEU: Nur wenn der Coin auf der Smartlist steht (wenn übergeben)
            if smart_suggestions and symbol not in smart_suggestions:
                continue

            count_checked += 1

            price = prices.get(symbol)
            volume = volume_map.get(symbol, 0)

            if not price:
                print(f"🚫 Kein Preis für {symbol}")
                continue

            if price > limit_usd:
                continue

            if volume < min_volume_usdt:
                continue

            # Fallback-Werte
            min_qty = 1
            step_size = 1
            trade_value = price * min_qty

            volatility = round(random.uniform(0.01, 0.2), 4)
            should_buy = True
            position_size = round(min_qty, 6)

            if should_buy and wallet["USDT"] >= trade_value:
                wallet["USDT"] -= trade_value
                wallet["positions"][symbol] = wallet["positions"].get(symbol, 0) + position_size
                print(f"🛒 Gekauft: {symbol} | {position_size} Stück für {trade_value} USD")

            if symbol in wallet["positions"] and random.random() < 0.1:
                sell_amount = wallet["positions"][symbol]
                wallet["USDT"] += sell_amount * price
                del wallet["positions"][symbol]
                print(f"💸 Verkauft: {symbol} | {sell_amount} Stück für {sell_amount * price} USD")

            result.append({
                "symbol": symbol,
                "price": price,
                "minQty": min_qty,
                "minValueUSD": round(trade_value, 4),
                "stepSize": step_size,
                "volatility": volatility,
                "volume": round(volume, 2),
                "walletPosition": round(wallet["positions"].get(symbol, 0), 6)
            })

        print(f"🔢 Überprüfte Symbole: {count_checked}, passende Coins: {len(result)}")
        return result[:top_n]

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



@app.route("/")
def index():
    coins = get_mexc_cheap_coins()
    for coin in coins:
        coin['details'] = generate_coin_details(coin)
    return render_template("dashboard.html", wallet=wallet, coins=coins)

@app.route("/api/coins")
def api_coins():
    coins = get_mexc_cheap_coins()
    for coin in coins:
        coin['details'] = generate_coin_details(coin)
    return jsonify(coins)
    
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