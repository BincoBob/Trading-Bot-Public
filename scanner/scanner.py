import requests
import logging
import time

WHITELIST = {"XRPUSDT", "DOGEUSDT", "SHIBUSDT", "ADAUSDT", "MATICUSDT"}

def has_enough_volume(symbol, min_usdt_volume=250000):
    try:
        url = f"https://api.mexc.com/api/v3/ticker/24hr?symbol={symbol}"
        response = requests.get(url, timeout=3)
        data = response.json()
        volume = float(data.get("quoteVolume", 0))
        return volume >= min_usdt_volume
    except Exception as e:
        logging.warning(f"⚠️ Volumenprüfung fehlgeschlagen für {symbol}: {e}")
        return False


def get_real_volatility(symbol, interval="1m", limit=20):
    try:
        url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if len(data) < 2:
            return 0.0

        closes = [float(candle[4]) for candle in data]
        average = sum(closes) / len(closes)
        volatility = (max(closes) - min(closes)) / average * 100

        return round(volatility, 2)

    except Exception as e:
        logging.warning(f"⚠️ Volatilität für {symbol} konnte nicht berechnet werden: {e}")
        return 0.0


def is_orderbook_active(symbol, min_orderbook_usd=10):
    try:
        url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit=5"
        response = requests.get(url, timeout=1.5)
        if not response.ok:
            return False
        data = response.json()
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        def has_volume(side):
            return any(float(price) * float(amount) >= min_orderbook_usd for price, amount in side)

        return has_volume(bids) and has_volume(asks)
    except Exception:
        return False



def get_mexc_cheap_coins(limit_usd=5, max_results=5):
    url = "https://api.mexc.com/api/v3/ticker/price"
    MIN_PRICE_USD = 0.0005  # ⛔ Unter diesem Preis ignorieren wir Coins

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        prices = response.json()

        cheap_coins = []
        symbols_checked = 0

        for entry in prices:
            symbol = entry["symbol"]
            price = float(entry["price"])

            # ✅ Nur USDT-Coins mit akzeptablem Preis
            if not (symbol.endswith("USDT") and (price < limit_usd or symbol in WHITELIST)):
                continue

            if price < MIN_PRICE_USD:
                print(f"⚠️  {symbol} übersprungen: Preis zu niedrig ({price})")
                continue

            if not has_enough_volume(symbol, min_usdt_volume=250000):
                continue

            if not is_orderbook_active(symbol):
                time.sleep(0.2)
                continue

            volatility = get_real_volatility(symbol)
            if volatility is None:
                continue

            entry_data = {
                "symbol": symbol,
                "price": price,
                "volatility": volatility,
                "entry_price": price * (1 + volatility / 100),
                "minValueUSD": round(price * 5, 4)
            }
            cheap_coins.append(entry_data)
            symbols_checked += 1
            time.sleep(0.2)

            if symbols_checked >= max_results:
                break

        cheap_coins.sort(key=lambda x: x["volatility"], reverse=True)
        return cheap_coins

    except Exception as e:
        logging.error(f"Fehler beim Laden der MEXC-Coin-Daten: {e}")
        return []


def simulate_volatility(price_history: list) -> float:
    """Berechnet eine einfache Volatilität aus Preisverlauf (Strings oder Floats)."""
    try:
        price_history = [float(p) for p in price_history]
        if len(price_history) < 2:
            return 0.0
        max_price = max(price_history)
        min_price = min(price_history)
        if max_price == 0:
            return 0.0
        volatility = ((max_price - min_price) / max_price) * 100
        return round(volatility, 2)
    except Exception as e:
        print(f"Volatility-Fehler: {e}")
        return 0.0

def get_recent_prices(symbol: str, limit: int = 5) -> list:
    try:
        url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={limit}"
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        data = response.json()
        bids = data.get("bids", [])
        return [float(price) for price, _ in bids if float(price) > 0]
    except Exception as e:
        logging.warning(f"⚠️ Fehler beim Abrufen der Preishistorie für {symbol}: {e}")
        return []

