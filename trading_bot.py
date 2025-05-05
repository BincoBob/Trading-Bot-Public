from scanner.scanner import get_mexc_cheap_coins
import requests
import json
import time
import threading
from datetime import datetime, timedelta
import logging
import random
from brain import load_memory, evaluate_trade, get_score_for_pattern
import os
from mexc_handler import kaufen_dynamic, verkaufen_dynamic, get_mexc_balances




# Reset einlesen (falls vorhanden)
if os.path.exists("wallet_reset.json"):
    with open("wallet_reset.json", "r") as f:
        reset_data = json.load(f)
        guthaben = reset_data["guthaben"]
        bitcoin_bestand = reset_data["bitcoin_bestand"]
    os.remove("wallet_reset.json")
    print("🔄 Wallet-Reset übernommen.")


load_memory()

# These will be imported properly in init_bot function
from extensions import db
Trade = None
PriceHistory = None

# Trading variables
# Trading variables
guthaben, bitcoin_bestand = get_mexc_balances()

wallet = {
    "USDT": guthaben,
    "positions": {}
}


preise = []  # List to store recent prices
letzter_preis = None  # Variable for the last price
trades = []  # List of trades
trading_enabled = False  # Flag to enable/disable automated trading

def bewertung_nach_trade(aktueller_rsi, richtung, gewinn):
    try:
        evaluate_trade({
            "rsi": aktueller_rsi if aktueller_rsi is not None else 50,
            "price_direction": richtung,
            "profit": gewinn
        })
        logging.info("🧠 Trade wurde bewertet und gespeichert.")
    except Exception as e:
        logging.warning(f"Bewertung nach Trade fehlgeschlagen: {e}")

# Hinweis: Füge jetzt am besten in deine Kauf- und Verkaufsfunktionen folgendes ein:
# 1. berechne den RSI (aus historic_data['rsi'] oder frisch berechnen)
# 2. bestimme die Preisrichtung (z.B. 'up' oder 'down' anhand der letzten Preise)
# 3. rufe dann bewertung_nach_trade(rsi, richtung, gewinn) auf



# API status tracking
api_source = "coingecko"  # Current API source: "coingecko" or "binance"
api_status = "unknown"    # Current API status: "online", "cooldown", "error", "unknown"
trading_thread = None  # Thread for automated trading

# Price caching
price_cache = {
    'price': None,
    'timestamp': None,
    'cache_duration': 300,  # Increased cache duration to 5 minutes to prevent API rate limits
    'api_cooldown': False,  # Flag for API cooldown mode
    'api_cooldown_until': None  # Timestamp when cooldown ends
}

# Extended price and market data
historic_data = {
    'prices': [],       # Historische Preisentwicklung (mehr Datenpunkte)
    'volumes': [],      # Handelsvolumen
    'market_caps': [],  # Marktkapitalisierung
    'timestamps': [],   # Zeitstempel der Daten
    'max_data_points': 1000,  # Erhöhte maximale Datenpunkte (stark erhöht für Indikatoren)
    # Neue Indikatoren
    'rsi': [],          # Relative Strength Index
    'upper_band': [],   # Bollinger Band oben
    'lower_band': [],   # Bollinger Band unten
    'resistance': None, # Aktueller Widerstandslevel
    'support': None,    # Aktuelle Unterstützungslevel
    'ma_short': [],     # Kurzfristiger gleitender Durchschnitt (9)
    'ma_medium': [],    # Mittelfristiger gleitender Durchschnitt (20)
    'ma_long': []       # Langfristiger gleitender Durchschnitt (50)
}

def init_bot():
    """Initialize the trading bot"""
    global guthaben, bitcoin_bestand, preise, letzter_preis, trades, trading_thread
    global db, Trade, PriceHistory, historic_data

    # Importiere Models und DB
    from app import db as app_db
    from models import Trade as TradeModel, PriceHistory as PriceHistoryModel

    # In globale Variablen übergeben
    db = app_db
    Trade = TradeModel
    PriceHistory = PriceHistoryModel

    # Optional: Trades laden (nur für Anzeige/Historie, nicht zur Berechnung!)
    try:
        from app import app
        with app.app_context():
            trades_db = Trade.query.all()
            trades = []
            if trades_db:
                trades = [{
                    "typ": trade.type,
                    "preis": trade.price,
                    "menge": trade.amount,
                    "zeit": trade.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                } for trade in trades_db]
    except Exception as e:
        logging.error(f"Error loading trade history: {e}")

    # ✅ Live-Balance direkt von MEXC laden
    try:
        from mexc_handler import get_mexc_balances
        guthaben, bitcoin_bestand = get_mexc_balances()
        logging.info(f"💰 Live-Kontostand geladen: ${guthaben:.2f} | BTC: {bitcoin_bestand:.8f}")
    except Exception as e:
        logging.warning(f"⚠️ Konnte Live-Balances nicht laden: {e}")    
        guthaben, bitcoin_bestand = 0.0, 0.0
        
        # ➕ MEXC Scanner für günstige Coins mit Volatilität
    try:
        günstige_coins = get_mexc_cheap_coins(limit_usd=5)

        # Beispielhafte Volatilitätsberechnung (hier nur simuliert)
        for coin in günstige_coins:
            coin['volatility'] = random.uniform(1, 15)  # Später durch echte Daten ersetzen

        # Sortiere nach höchster Volatilität
        top5 = sorted(günstige_coins, key=lambda c: c["volatility"], reverse=True)[:5]

        print("\n📈 Top 5 Coins unter $5 mit höchster (simulierter) Volatilität:")
        for coin in top5:
            print(f"💥 {coin['symbol']} | Preis: {coin['price']} USD | Einstieg: ${coin['minValueUSD']} | Volatilität: {round(coin['volatility'], 2)}%")
    except Exception as e:
        logging.warning(f"⚠️ Scanner-Fehler: {e}")
    

    # ✅ Trading starten
    start_trading_thread()


def get_bitcoin_price():
    """Get the current Bitcoin price from CoinGecko API with caching"""
    global price_cache, letzter_preis, historic_data, api_status
    
    # Check if we have a valid cached price
    now = datetime.now()
    
    # Check if we're in API cooldown mode
    if price_cache['api_cooldown'] and price_cache['api_cooldown_until'] and now < price_cache['api_cooldown_until']:
        api_status = "cooldown"  # Update API status to show in UI
        
        if letzter_preis:
            variation = random.uniform(-0.01, 0.01)  # Smaller variation during cooldown
            simulated_price = letzter_preis * (1 + variation)
            logging.info(f"API in cooldown. Using simulated price: ${simulated_price:.2f}")
            return simulated_price
    
    # Normal cache check
    if (price_cache['price'] is not None and price_cache['timestamp'] is not None and
        now - price_cache['timestamp'] < timedelta(seconds=price_cache['cache_duration'])):
        return price_cache['price']
    
    # If we're out of API calls, provide a simulated value
    if letzter_preis is not None:
        # Add small random variation to the last price to simulate market changes
        simulation_enabled = True  # Set to False to disable simulated prices
        if simulation_enabled and random.random() < 0.7:  # 70% chance to use simulation
            # Simulate a small price change (±2%)
            variation = random.uniform(-0.02, 0.02)
            simulated_price = letzter_preis * (1 + variation)
            logging.info(f"Using simulated Bitcoin price: ${simulated_price:.2f} (based on last price ${letzter_preis:.2f})")
            
            # Update cache with simulated price
            price_cache['price'] = simulated_price
            price_cache['timestamp'] = now
            letzter_preis = simulated_price
            
            # Auch die historischen Daten aktualisieren
            historic_data['prices'].append(simulated_price)
            historic_data['timestamps'].append(now)
            # Simuliertes Volumen und Marktkapitalisierung
            simulated_volume = simulated_price * random.uniform(20000, 50000)  # Simuliertes Handelsvolumen
            simulated_market_cap = simulated_price * 19000000  # Ca. 19 Mio. BTC im Umlauf
            historic_data['volumes'].append(simulated_volume)
            historic_data['market_caps'].append(simulated_market_cap)
            
            # Maximale Datenpunkte einhalten
            if len(historic_data['prices']) > historic_data['max_data_points']:
                historic_data['prices'].pop(0)
                historic_data['timestamps'].pop(0)
                historic_data['volumes'].pop(0)
                historic_data['market_caps'].pop(0)
                
            return simulated_price
    
    # Call the API
    try:
        # Einfache Preisabfrage
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        price = data['bitcoin']['usd']
        
        # Update cache and last price
        price_cache['price'] = price
        price_cache['timestamp'] = now
        letzter_preis = price
        
        # Set API status to online
        api_status = "online"
        
        # Zusätzlich: Alle 10 Minuten versuchen, detaillierte Marktdaten zu holen
        try_detailed_data = len(historic_data['timestamps']) == 0 or (
            len(historic_data['timestamps']) > 0 and 
            now - historic_data['timestamps'][-1] > timedelta(minutes=10)
        )
        
        if try_detailed_data:
            try:
                # Detaillierte Marktdaten für den letzten Tag (Stundendaten)
                # Kostenlose Basisdaten statt Premium-API verwenden
                market_url = "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false"
                market_response = requests.get(market_url, headers=headers, timeout=30)
                market_response.raise_for_status()
                market_data = market_response.json()
                
                # Marktdaten extrahieren
                current_price = market_data.get('market_data', {}).get('current_price', {}).get('usd', price)
                total_volume = market_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                market_cap = market_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                
                # Ein einzelner Datenpunkt ist besser als keiner
                historic_data['prices'].append(current_price)
                historic_data['timestamps'].append(now)
                historic_data['volumes'].append(total_volume)
                historic_data['market_caps'].append(market_cap)
                
                # Für das Logging
                extracted_data = [{
                    'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'price': current_price,
                    'volume': total_volume,
                    'market_cap': market_cap
                }]
                
                # Daten extrahieren und zum historischen Datensatz hinzufügen
                for i, price_data in enumerate(market_data.get('prices', [])):
                    if i < len(market_data.get('prices', [])):
                        timestamp = datetime.fromtimestamp(price_data[0]/1000)  # Unix-Timestamp in ms
                        price_value = price_data[1]
                        volume = market_data.get('total_volumes', [])[i][1] if i < len(market_data.get('total_volumes', [])) else 0
                        market_cap = market_data.get('market_caps', [])[i][1] if i < len(market_data.get('market_caps', [])) else 0
                        
                        # Daten speichern
                        historic_data['prices'].append(price_value)
                        historic_data['timestamps'].append(timestamp)
                        historic_data['volumes'].append(volume)
                        historic_data['market_caps'].append(market_cap)
                
                # Maximale Datenpunkte einhalten
                while len(historic_data['prices']) > historic_data['max_data_points']:
                    historic_data['prices'].pop(0)
                    historic_data['timestamps'].pop(0)
                    historic_data['volumes'].pop(0)
                    historic_data['market_caps'].pop(0)
                    
                logging.info(f"Updated historic market data with {len(market_data.get('prices', []))} data points")
            except Exception as e:
                logging.warning(f"Could not fetch detailed market data: {e}")
                
                # Trotzdem den aktuellen Preis zu historischen Daten hinzufügen
                historic_data['prices'].append(price)
                historic_data['timestamps'].append(now)
                historic_data['volumes'].append(0)  # Keine Volumendaten verfügbar
                historic_data['market_caps'].append(0)  # Keine Marktkapitalisierungsdaten verfügbar
                
                # Maximale Datenpunkte einhalten
                if len(historic_data['prices']) > historic_data['max_data_points']:
                    historic_data['prices'].pop(0)
                    historic_data['timestamps'].pop(0)
                    historic_data['volumes'].pop(0)
                    historic_data['market_caps'].pop(0)
        else:
            # Nur aktuellen Preis zu historischen Daten hinzufügen, wenn nötig
            if len(historic_data['timestamps']) == 0 or now - historic_data['timestamps'][-1] > timedelta(minutes=1):
                historic_data['prices'].append(price)
                historic_data['timestamps'].append(now)
                # Ohne API-Aufruf keine Volumendaten
                historic_data['volumes'].append(0)
                historic_data['market_caps'].append(0)
                
                # Maximale Datenpunkte einhalten
                if len(historic_data['prices']) > historic_data['max_data_points']:
                    historic_data['prices'].pop(0)
                    historic_data['timestamps'].pop(0)
                    historic_data['volumes'].pop(0)
                    historic_data['market_caps'].pop(0)
        
        return price
    except requests.RequestException as e:
        logging.error(f"Error fetching Bitcoin price: {e}")
        
        # Check if it's a rate limit error (429)
        if "429" in str(e):
            # Set cooldown for 15 minutes
            cooldown_minutes = 15
            price_cache['api_cooldown'] = True
            price_cache['api_cooldown_until'] = now + timedelta(minutes=cooldown_minutes)
            logging.warning(f"API rate limit hit. Entering cooldown mode for {cooldown_minutes} minutes until {price_cache['api_cooldown_until']}")
        
        # Return last known price if available
        if letzter_preis is not None:
            # Add small variation to avoid flatline
            variation = random.uniform(-0.005, 0.005)  # Very small variation (±0.5%)
            simulated_price = letzter_preis * (1 + variation)
            logging.info(f"Using simulated price based on last known price: ${simulated_price:.2f}")
            return simulated_price
        
        # Fallback to a reasonable value if we have no price history
        if price_cache['price'] is None and letzter_preis is None:
            fallback_price = 67500.0  # Approximate BTC price as of development time
            logging.info(f"Using fallback Bitcoin price: ${fallback_price}")
            price_cache['price'] = fallback_price
            price_cache['timestamp'] = now
            letzter_preis = fallback_price
            return fallback_price
            
        return None

def lade_konfiguration():
    """Load the configuration from config.json"""
    try:
        with open('config.json', 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading configuration file: {e}")
        return {
            "verkaufswert": 95000,  # Höherer Notfall-Verkaufswert
            "buying_percentage": 0.05,
            "min_selling_percentage": 0.05,  # Minimaler Verkaufsprozentsatz (gradueller Verkauf)
            "max_selling_percentage": 0.25,  # Maximaler Verkaufsprozentsatz (gradueller Verkauf)
            "min_dip_percentage": 0.002,    # Kauft bereits bei 0.2% Dip (statt 0.5%)
            "ma_window": 3,               # Durchschnitt aus 3 Werten
            "price_check_interval": 30    # Prüft alle 30 Sekunden den Preis
        }

import logging
from mexc_handler import place_market_order  # Wichtig: besser ganz oben importieren

def kaufen(aktueller_preis, betrag_usd):
    global guthaben, bitcoin_bestand

    try:
        menge_btc = betrag_usd / aktueller_preis
        min_btc = 0.0001
        min_usd = min_btc * aktueller_preis

        if menge_btc < min_btc:
            if guthaben >= min_usd:
                menge_btc = min_btc
                betrag_usd = min_usd
                logging.info(f"⚠️ Mindestkaufmenge erreicht, kaufe trotzdem 0.0001 BTC für ca. ${betrag_usd:.2f}")
            else:
                logging.warning(f"❌ Zu wenig Guthaben für Mindestkauf: {guthaben:.2f} USD < {min_usd:.2f}")
                return False

        result = place_market_order("BTCUSDT", "BUY", quantity=round(menge_btc, 6))

        if result and "orderId" in result:
            bitcoin_bestand += menge_btc
            guthaben -= betrag_usd
            speichere_trade("kauf", aktueller_preis, menge_btc)
            logging.info(f"✅ Echte BTC gekauft: {menge_btc:.6f} BTC für ${betrag_usd:.2f}")
            return True
        else:
            logging.error(f"❌ Kauf fehlgeschlagen: {result}")
            return False

    except Exception as e:
        logging.error(f"❌ Ausnahmefehler beim Kaufen: {e}")
        return False



import logging
from mexc_handler import place_market_order  # Auch hier am besten oben importieren

def verkaufen(aktueller_preis, menge_btc):
    global guthaben, bitcoin_bestand

    try:
        # MEXC Market-Order platzieren
        result = place_market_order("BTCUSDT", "SELL", quantity=round(menge_btc, 6))

        if result and "orderId" in result:
            erloes = menge_btc * aktueller_preis
            bitcoin_bestand -= menge_btc
            guthaben += erloes
            speichere_trade("verkauf", aktueller_preis, menge_btc)
            logging.info(f"✅ Echte BTC verkauft: {menge_btc:.6f} BTC für ca. ${erloes:.2f}")
            return True
        else:
            logging.error(f"❌ Verkauf fehlgeschlagen: {result}")
            return False

    except Exception as e:
        logging.error(f"❌ Ausnahmefehler beim Verkaufen: {e}")
        return False


def kaufen_dynamic(aktueller_preis, prozent_des_guthabens, symbol="BTCUSDT"):
    global guthaben, bitcoin_bestand

    try:
        # ❌ Deaktivierter BTC-Kauf
        if symbol == "BTCUSDT":
            logging.info("⛔️ Automatischer BTC-Kauf ist dauerhaft deaktiviert.")
            return False

        betrag_usd = guthaben * prozent_des_guthabens
        min_kauf_usd = 5.0  # Mindestbetrag für die Order in USD

        if betrag_usd < min_kauf_usd:
            logging.warning(f"❌ Kaufbetrag zu gering (${betrag_usd:.2f}) – Mindestkauf: ${min_kauf_usd}")
            return False

        result = place_market_order(symbol, "BUY", quantity=round(betrag_usd / aktueller_preis, 6))

        if result and "orderId" in result:
            menge = betrag_usd / aktueller_preis
            wallet["USDT"] -= betrag_usd
            wallet["positions"][symbol] = wallet["positions"].get(symbol, 0) + menge
            speichere_trade("kauf", aktueller_preis, menge)
            logging.info(f"✅ Coin gekauft: {symbol} | {menge:.6f} Stück für ${betrag_usd:.2f}")
            return True
        else:
            logging.error(f"❌ Kauf fehlgeschlagen für {symbol}: {result}")
            return False

    except Exception as e:
        logging.error(f"❌ Fehler in kaufen_dynamic: {e}")
        return False


def verkaufen_dynamic(aktueller_preis, prozent_des_bestands, symbol_override=None):
    global guthaben, bitcoin_bestand, wallet

    try:
        # ❌ Deaktivierter BTC-Verkauf
        if symbol_override is None:
            logging.info("⛔️ Automatischer BTC-Verkauf ist dauerhaft deaktiviert.")
            return False

        # ✅ Verkauf eines spezifischen Coins (z. B. ETHUSDT)
        symbol = symbol_override
        menge = wallet["positions"].get(symbol, 0)

        if menge <= 0:
            logging.warning(f"⚠️ Keine Position für {symbol} vorhanden – kein Verkauf möglich.")
            return False

        result = place_market_order(symbol, "SELL", quantity=round(menge, 6))

        if result and "orderId" in result:
            erloes = menge * aktueller_preis
            wallet["USDT"] += erloes
            del wallet["positions"][symbol]
            speichere_trade("verkauf", aktueller_preis, menge)
            logging.info(f"✅ Coin verkauft: {symbol} | {menge:.6f} Stück für ca. ${erloes:.2f}")
            return True
        else:
            logging.error(f"❌ Verkauf fehlgeschlagen für {symbol}: {result}")
            return False

    except Exception as e:
        logging.error(f"❌ Fehler in verkaufen_dynamic: {e}")
        return False








def speichere_trade(typ, preis, menge):
    """Save a trade to the database and local list"""
    zeit = datetime.now()
    trade = {"typ": typ, "preis": preis, "menge": menge, "zeit": zeit.strftime("%Y-%m-%d %H:%M:%S")}
    trades.append(trade)
    
    # Save to database
    try:
        # Only attempt to save to database if DB is initialized
        if db is not None and Trade is not None:
            from app import app
            with app.app_context():
                total_value = preis * menge
                db_trade = Trade(
                    type=typ,
                    price=preis,
                    amount=menge,
                    total_value=total_value,
                    timestamp=zeit
                )
                db.session.add(db_trade)
                db.session.commit()
                logging.info(f"Trade saved to database: {trade}")
        else:
            logging.warning("Database not initialized yet, trade only saved locally")
    except Exception as e:
        logging.error(f"Error saving trade to database: {e}")
    
    logging.info(f"Trade saved locally: {trade}")

def berechne_gleitenden_durchschnitt(preise, fenster):
    """Calculate moving average of prices from in-memory list and database"""
    global db, PriceHistory
    
    # If we have enough prices in memory, use them
    if len(preise) >= fenster:
        return sum(preise[-fenster:]) / fenster
    
    # Otherwise, try to get more data from the database
    try:
        from app import app
        with app.app_context():
            # Get recent price records from database
            if db is not None and PriceHistory is not None:
                recent_prices = PriceHistory.query.order_by(PriceHistory.timestamp.desc()).limit(fenster).all()
                if recent_prices:
                    # Combine DB prices with in-memory prices
                    db_prices = [p.price for p in recent_prices]
                    all_prices = db_prices + preise
                    # Use the most recent ones up to the window size
                    recent_prices_slice = all_prices[-fenster:]
                    if len(recent_prices_slice) >= fenster:
                        return sum(recent_prices_slice) / fenster
    except Exception as e:
        logging.error(f"Error calculating moving average from database: {e}")
    
    # If we don't have enough data, return None
    if len(preise) < fenster:
        return None
        
    return sum(preise[-fenster:]) / fenster

def ist_aufwärtstrend(preise, fenster=3):
    """Check if prices show an upward trend"""
    if len(preise) < fenster:
        return False
    return all(preise[i] < preise[i+1] for i in range(-fenster, -1))

def berechne_bollinger_baender(preise, fenster=20, anzahl_standardabweichungen=2):
    """Bollinger Bands berechnen (auf Basis des gleitenden Durchschnitts mit Standardabweichungen)"""
    if len(preise) < fenster:
        return None, None, None
    
    # Gleitender Durchschnitt
    ma = berechne_gleitenden_durchschnitt(preise, fenster)
    if ma is None:
        return None, None, None
    
    # Standardabweichung berechnen
    preise_fenster = preise[-fenster:]
    standardabweichung = (sum([(p - ma) ** 2 for p in preise_fenster]) / len(preise_fenster)) ** 0.5
    
    # Oberes und unteres Bollinger-Band
    upper_band = ma + (standardabweichung * anzahl_standardabweichungen)
    lower_band = ma - (standardabweichung * anzahl_standardabweichungen)
    
    return ma, upper_band, lower_band

def berechne_rsi(preise, fenster=14):
    """Relative Strength Index (RSI) berechnen"""
    if len(preise) < 7:
        return None
    
    # Preisänderungen berechnen
    aenderungen = [preise[i+1] - preise[i] for i in range(len(preise)-1)]
    aenderungen = aenderungen[-(fenster+1):]  # Nur die letzten n+1 Änderungen
    
    # Gewinne und Verluste trennen
    gewinne = [max(0, aenderung) for aenderung in aenderungen]
    verluste = [abs(min(0, aenderung)) for aenderung in aenderungen]
    
    # Durchschnitt der Gewinne und Verluste berechnen
    if sum(verluste) == 0:  # Vermeidet Division durch Null
        return 100  # Wenn keine Verluste, dann RSI = 100
    
    avg_gain = sum(gewinne) / len(gewinne)
    avg_loss = sum(verluste) / len(verluste)
    
    # Relative Strength berechnen
    rs = avg_gain / avg_loss if avg_loss > 0 else float('inf')
    
    # RSI berechnen (0-100)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def finde_support_resistance(preise, fenster=50):
    """Unterstützungs- und Widerstandslinien erkennen basierend auf lokalen Maxima und Minima"""
    if len(preise) < fenster:
        return None, None
    
    lokale_maxima = []
    lokale_minima = []
    
    # Preishistorie auf ein angemessenes Fenster begrenzen
    preise_fenster = preise[-fenster:]
    
    # Lokale Maxima und Minima finden (nicht die Ränder)
    for i in range(1, len(preise_fenster) - 1):
        # Lokales Maximum (höher als beide Nachbarn)
        if preise_fenster[i] > preise_fenster[i-1] and preise_fenster[i] > preise_fenster[i+1]:
            lokale_maxima.append(preise_fenster[i])
            
        # Lokales Minimum (niedriger als beide Nachbarn)
        if preise_fenster[i] < preise_fenster[i-1] and preise_fenster[i] < preise_fenster[i+1]:
            lokale_minima.append(preise_fenster[i])
    
    # Widerstand: Durchschnitt der letzten 3 lokalen Maxima (oder weniger, falls nicht genug)
    resistance = sum(lokale_maxima[-3:]) / len(lokale_maxima[-3:]) if lokale_maxima and len(lokale_maxima) >= 3 else None
    
    # Unterstützung: Durchschnitt der letzten 3 lokalen Minima (oder weniger, falls nicht genug)
    support = sum(lokale_minima[-3:]) / len(lokale_minima[-3:]) if lokale_minima and len(lokale_minima) >= 3 else None
    
    return support, resistance

def aktualisiere_indikatoren(preise):
    """Berechnet und aktualisiert alle technischen Indikatoren"""
    global historic_data
    
    # Stelle sicher, dass wir genug Daten haben
    if len(preise) < 50:
        logging.warning(f"Nicht genug Daten für alle Indikatoren: {len(preise)} Datenpunkte")
        return {}
    
    # Kurz-, Mittel- und Langfristige gleitende Durchschnitte
    ma_short = berechne_gleitenden_durchschnitt(preise, 9) 
    ma_medium = berechne_gleitenden_durchschnitt(preise, 20)
    ma_long = berechne_gleitenden_durchschnitt(preise, 50)
    
    # Bollinger Bänder
    _, upper, lower = berechne_bollinger_baender(preise)
    
    # RSI
    rsi = berechne_rsi(preise)
    
    # Support und Resistance
    support, resistance = finde_support_resistance(preise)
    
    # Ergebnisse in Dictionary packen
    indikatoren = {
        'ma_short': ma_short,
        'ma_medium': ma_medium,
        'ma_long': ma_long,
        'upper_band': upper,
        'lower_band': lower,
        'rsi': rsi,
        'support': support,
        'resistance': resistance
    }
    
    # Werte in historic_data speichern
    historic_data['ma_short'] = ma_short
    historic_data['ma_medium'] = ma_medium
    historic_data['ma_long'] = ma_long
    historic_data['upper_band'] = upper
    historic_data['lower_band'] = lower
    historic_data['rsi'] = rsi
    historic_data['support'] = support
    historic_data['resistance'] = resistance
    
    # Log-Ausgabe
    logging.info("---- Technische Indikatoren ----")
    if ma_short: logging.info(f"MA9: ${ma_short:.2f}")
    if ma_medium: logging.info(f"MA20: ${ma_medium:.2f}")
    if ma_long: logging.info(f"MA50: ${ma_long:.2f}")
    if upper and lower: logging.info(f"Bollinger: ${lower:.2f} - ${upper:.2f}")
    if rsi: logging.info(f"RSI: {rsi:.1f}")
    if support and resistance: logging.info(f"Support: ${support:.2f}, Resistance: ${resistance:.2f}")
    
    return indikatoren

def start_trading_thread():
    """Start the automated trading thread"""
    global trading_thread, trading_enabled
    
    if trading_thread and trading_thread.is_alive():
        return  # Thread already running
    
    trading_enabled = True
    trading_thread = threading.Thread(target=automated_trading_loop)
    trading_thread.daemon = True  # Daemon thread will exit when main program exits
    trading_thread.start()
    logging.info("Automated trading started")

def stop_trading_thread():
    """Stop the automated trading thread"""
    global trading_enabled
    trading_enabled = False
    logging.info("Automated trading stopped")

def automated_trading_loop():
    """Main loop for automated trading"""
    global preise, trading_enabled

    logging.info(f"Starting capital: ${guthaben} | Bitcoin: {bitcoin_bestand} BTC")

    min_trade_amount_usd = 1.0  # Minimum trade size in USD

    while trading_enabled:
        try:
            config = lade_konfiguration()
            price_check_interval = config.get("price_check_interval", 30)

            aktueller_preis = get_bitcoin_price()
            if aktueller_preis is not None:
                logging.info(f"Current Bitcoin price: ${aktueller_preis}")
                preise.append(aktueller_preis)
                if len(preise) > 1000:
                    preise.pop(0)

                indikatoren = aktualisiere_indikatoren(preise)
                rsi = indikatoren.get("rsi")
                upper_band = indikatoren.get("upper_band")
                lower_band = indikatoren.get("lower_band")
                ma_short = indikatoren.get("ma_short")
                ma_medium = indikatoren.get("ma_medium")
                support = indikatoren.get("support")
                resistance = indikatoren.get("resistance")

                # Nur zur Analyse verwenden – kein BTC-Handel mehr
                logging.info("📊 Nur Analyse – kein automatischer BTC-Handel aktiv")

            else:
                logging.error("Error fetching price. Waiting for next attempt...")

            marktanalyse = analysiere_markt(preise)
            logging.info(
                f"📊 Marktanalyse: Trend={marktanalyse['trend']} | Momentum={marktanalyse['momentum']} | Empfehlung={marktanalyse['empfehlung']}")

        except Exception as e:
            logging.error(f"Error in trading loop: {e}")
            time.sleep(10)

        try:
            aktuelle_top_coins = get_mexc_cheap_coins(limit_usd=5, max_results=5)
            top_symbole = [coin["symbol"] for coin in aktuelle_top_coins]

            ignored_file = "ignored_coins.json"
            if os.path.exists(ignored_file):
                with open(ignored_file, "r") as f:
                    ignored_coins = json.load(f)
            else:
                ignored_coins = []

            for symbol in list(wallet["positions"].keys()):
                if symbol not in top_symbole and symbol not in ignored_coins:
                    aktuelle_preise = requests.get("https://api.mexc.com/api/v3/ticker/price", timeout=10).json()
                    preis_map = {x["symbol"]: float(x["price"]) for x in aktuelle_preise}
                    aktueller_preis = preis_map.get(symbol)

                    if aktueller_preis:
                        kaufwert = wallet["positions"][symbol] * 0.98
                        verkaufswert = wallet["positions"][symbol] * aktueller_preis

                        if verkaufswert > kaufwert:
                            verkaufen_dynamic(aktueller_preis, 1.0, symbol_override=symbol)
                            logging.info(f"🚮 {symbol} ist nicht mehr in der Liste und im Gewinn – wird verkauft.")
                            ignored_coins.append(symbol)
                        else:
                            logging.info(f"⏳ {symbol} ist nicht mehr in der Liste, aber noch im Minus – wird gehalten.")

            with open(ignored_file, "w") as f:
                json.dump(ignored_coins, f)

        except Exception as e:
            logging.warning(f"⚠️ Fehler bei Auto-Verkauf von Coins außerhalb der Topliste: {e}")

        time.sleep(price_check_interval)

    logging.info("Trading loop stopped")


def analysiere_markt(preise):
    if len(preise) < 10:
        return {"trend": "neutral", "volatilität": 0, "momentum": 0, "empfehlung": "nicht genug daten"}

    letzter = preise[-1]
    vor_3 = preise[-3]
    vor_5 = preise[-5]
    vor_10 = preise[-10]

    # Trend
    if letzter > vor_3 > vor_5:
        trend = "bullish"
    elif letzter < vor_3 < vor_5:
        trend = "bearish"
    else:
        trend = "seitwärts"

    # Volatilität (Preisänderung in % über 10 Schritte)
    volatilität = abs(letzter - vor_10) / vor_10

    # Momentum
    momentum = letzter - vor_5

    # Intelligente Entscheidung
    if trend == "bullish" and momentum > 100:
        empfehlung = "abwarten – Preis zieht an"
    elif trend == "bearish" and momentum < -100:
        empfehlung = "schnell verkaufen – Preis fällt stark"
    elif volatilität > 0.05:
        empfehlung = "vorsicht – hohe Volatilität"
    else:
        empfehlung = "normal handeln"

    return {
        "trend": trend,
        "volatilität": round(volatilität, 4),
        "momentum": round(momentum, 2),
        "empfehlung": empfehlung
    }

# Don't auto-initialize the bot when this module is imported
# This will be called explicitly from app.py after db setup
