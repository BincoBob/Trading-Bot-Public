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


def kaufen_dynamic(aktueller_preis, prozent_des_guthabens):
    global guthaben, bitcoin_bestand

    try:
        betrag_usd = guthaben * prozent_des_guthabens
        min_kauf_usd = 5.0  # Mindestbetrag für die Order in USD
        min_btc = 0.0001    # Mindestmenge laut MEXC

        # Wenn Kaufbetrag kleiner als Mindestbetrag ist, prüfe ob genug USD für min_btc vorhanden ist
        if betrag_usd < min_kauf_usd:
            min_betrag = min_btc * aktueller_preis
            if guthaben >= min_betrag:
                betrag_usd = min_betrag  # Handle mit Mindestbetrag
                logging.info(f"💡 Erzwungener Mindestkauf: {min_btc:.6f} BTC für ca. ${betrag_usd:.2f}")
            else:
                logging.warning(f"❌ Kaufbetrag zu gering und nicht genug Guthaben: ${betrag_usd:.2f}")
                return False

        return kaufen(aktueller_preis, betrag_usd)

    except Exception as e:
        logging.error(f"❌ Fehler in kaufen_dynamic: {e}")
        return False





def verkaufen_dynamic(aktueller_preis, prozent_des_bestands):
    global guthaben, bitcoin_bestand

    try:
        menge_btc = bitcoin_bestand * prozent_des_bestands
        min_btc = 0.0001  # Mindestmenge laut MEXC
        erloes = menge_btc * aktueller_preis

        # Wenn Menge zu klein ist, prüfe ob genug BTC für Mindestmenge da ist
        if menge_btc < min_btc:
            if bitcoin_bestand >= min_btc:
                menge_btc = min_btc
                erloes = menge_btc * aktueller_preis
                logging.info(f"💡 Erzwungener Mindestverkauf: {menge_btc:.6f} BTC für ca. ${erloes:.2f}")
            else:
                logging.warning(f"❌ Zu wenig BTC für Mindestverkauf: {bitcoin_bestand:.6f} BTC < {min_btc} BTC")
                return False

        return verkaufen(aktueller_preis, menge_btc)

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
    
    # Set minimum trade amount but remove cooldown as requested
    min_trade_amount_usd = 1.0  # Minimum trade size in USD
    
    while trading_enabled:
        try:
            # Load configuration
            config = lade_konfiguration()
            verkaufswert = config.get("verkaufswert", 94500)
            ma_window = config.get("ma_window", 3)
            price_check_interval = config.get("price_check_interval", 30)
            
            # Get current price
            aktueller_preis = get_bitcoin_price()
            if aktueller_preis is not None:
                logging.info(f"Current Bitcoin price: ${aktueller_preis}")
                
                # Store price in list with increased capacity
                preise.append(aktueller_preis)
                if len(preise) > 1000:  # Keep max 1000 prices in the list (stark erhöht für bessere Analysen)
                    preise.pop(0)
                
                # Berechne alle technischen Indikatoren
                indikatoren = aktualisiere_indikatoren(preise)
                # --- RSI einfügen ---
                # --- Indikatorwerte sicher abfragen ---
                rsi = indikatoren.get("rsi")
                upper_band = indikatoren.get("upper_band")
                lower_band = indikatoren.get("lower_band")
                ma_short = indikatoren.get("ma_short")
                ma_medium = indikatoren.get("ma_medium")
                ma_long = indikatoren.get("ma_long")
                support = indikatoren.get("support")
                resistance = indikatoren.get("resistance")

                kauf_signale = []
                verkauf_signale = []

                # --- RSI ---
                if rsi is not None:
                    if rsi < 30:
                        kauf_signale.append(f"RSI überverkauft: {rsi:.1f}")
                    elif rsi > 70:
                        verkauf_signale.append(f"RSI überkauft: {rsi:.1f}")
                else:
                    logging.warning("RSI konnte nicht berechnet werden – zu wenig Daten.")

                # --- Bollinger Bands ---
                if lower_band is not None and aktueller_preis <= lower_band * 1.01:
                    kauf_signale.append(f"Preis am unteren Bollinger-Band: ${aktueller_preis:.2f}")
                if upper_band is not None and aktueller_preis >= upper_band * 0.99:
                    verkauf_signale.append(f"Preis am oberen Bollinger-Band: ${aktueller_preis:.2f}")

                # --- Moving Averages ---
                if ma_short and ma_medium and ma_short < ma_medium:
                    verkauf_signale.append(f"Death Cross: MA9 ({ma_short:.2f}) unter MA20 ({ma_medium:.2f})")

                # --- Support / Resistance ---
                if support is not None and aktueller_preis <= support * 1.01:
                    kauf_signale.append(f"Preis nahe Support-Level: ${support:.2f}")
                if resistance is not None and aktueller_preis >= resistance * 0.99:
                    verkauf_signale.append(f"Preis nahe Resistance-Level: ${resistance:.2f}")
                
                # Standardmäßig den konfigurierten Moving Average verwenden (Kompatibilität mit altem Code)
                durchschnitt = berechne_gleitenden_durchschnitt(preise, ma_window)

                # 💥 AGGRESSIV: Kauf- & Verkaufssignale erweitern

                # ----- KAUFSIGNALE -----
                if rsi is not None and rsi < 40:
                    kauf_signale.append(f"RSI < 40 – früher Einstieg ({rsi})")

                if aktueller_preis < durchschnitt * 0.99:
                    kauf_signale.append(f"Preis unter MA – Einstiegschance")
                
                # Zusätzlicher Einstieg bei leichtem Kurs unter Durchschnitt
                if durchschnitt is not None and aktueller_preis < durchschnitt * 0.997:
                    kauf_signale.append("📉 Preis leicht unter MA – Einstieg möglich")
    
                if len(preise) >= 3 and preise[-1] < preise[-2] * 0.97:
                    kauf_signale.append("3% Crash erkannt – Schnapp-Buy")

                # ----- VERKAUFSSIGNALE -----
                if upper_band is not None and aktueller_preis > upper_band * 0.99:
                    verkauf_signale.append("Oberes Bollinger-Band fast erreicht")

                if rsi is not None and rsi > 65:
                    verkauf_signale.append(f"RSI über 65 – Gewinnmitnahme ({rsi})")

                # Statt ab 2 Signalen → jetzt ab 1!
                if len(verkauf_signale) >= 1 and bitcoin_bestand > 0:
                    signal_faktor = min(1.0, len(verkauf_signale) * 0.4)
                    selling_percentage = 0.1 + (0.3 * signal_faktor)  # 10–40 %
                    btc_to_sell = bitcoin_bestand * selling_percentage
                    sell_value = btc_to_sell * aktueller_preis

                    if sell_value >= min_trade_amount_usd:
                        verkaufen_dynamic(aktueller_preis, selling_percentage)
                        logging.info(f"🔥 AGGRESSIVER VERKAUF ausgelöst wegen: {', '.join(verkauf_signale)}")

                # Wenn genug Daten für erweiterte Indikatoren vorhanden sind, verwende diese
                if indikatoren and len(indikatoren) > 0:
                    # Fortgeschrittene Handelsstrategien basierend auf technischen Indikatoren
                    
                    # Kauf-/Verkaufssignale aus Indikatoren extrahieren
                    ma_short = indikatoren.get('ma_short')
                    ma_medium = indikatoren.get('ma_medium')
                    ma_long = indikatoren.get('ma_long')
                    upper_band = indikatoren.get('upper_band')
                    lower_band = indikatoren.get('lower_band')
                    rsi = indikatoren.get('rsi')
                    support = indikatoren.get('support')
                    resistance = indikatoren.get('resistance')
                    
                    # KAUFSIGNALE AUS TECHNISCHEN INDIKATOREN
                    kauf_signale = []
                    
                    # 1. Bollinger-Band Kaufsignal: Preis nahe oder unter dem unteren Band
                    if lower_band is not None and aktueller_preis <= lower_band * 1.01:
                        kauf_signale.append(f"Bollinger-Band: Preis (${aktueller_preis:.2f}) am unteren Band (${lower_band:.2f})")
                    
                    # 2. RSI Kaufsignal: Überverkauft (RSI < 30)
                    if rsi is not None and rsi < 55:
                        kauf_signale.append(f"RSI überverkauft: {rsi:.1f}")
                    
                    # 3. Support-Level Kaufsignal: Preis nahe am Support
                    if support is not None and aktueller_preis <= support * 1.01:
                        kauf_signale.append(f"Preis nahe Support-Level: ${support:.2f}")
                    
                    # 4. Golden Cross Kaufsignal: Kurzfristiger MA kreuzt langfristigen MA von unten nach oben
                    if ma_short is not None and ma_medium is not None and ma_short > ma_medium and len(historic_data.get('prices', [])) > 2:
                        # Prüfe, ob es vorher eine Kreuzung gab
                        prev_ma_short = berechne_gleitenden_durchschnitt(preise[:-1], 9) 
                        prev_ma_medium = berechne_gleitenden_durchschnitt(preise[:-1], 20)
                        if len(preise) > 10 and prev_ma_short is not None and prev_ma_medium is not None and prev_ma_short < prev_ma_medium:
                            kauf_signale.append(f"Golden Cross: MA9 (${ma_short:.2f}) über MA20 (${ma_medium:.2f})")
                    
                    # VERKAUFSSIGNALE AUS TECHNISCHEN INDIKATOREN
                    verkauf_signale = []
                    
                    # 1. Bollinger-Band Verkaufssignal: Preis nahe oder über dem oberen Band
                    if upper_band is not None and aktueller_preis >= upper_band * 0.99:
                        verkauf_signale.append(f"Bollinger-Band: Preis (${aktueller_preis:.2f}) am oberen Band (${upper_band:.2f})")
                    
                    # 2. RSI Verkaufssignal: Überkauft (RSI > 70)
                    if rsi is not None and rsi > 70:
                        verkauf_signale.append(f"RSI überkauft: {rsi:.1f}")
                    
                    # 3. Resistance-Level Verkaufssignal: Preis nahe am Widerstand
                    if resistance is not None and aktueller_preis >= resistance * 0.99:
                        verkauf_signale.append(f"Preis nahe Resistance-Level: ${resistance:.2f}")
                    
                    # 4. Death Cross Verkaufssignal: Kurzfristiger MA kreuzt langfristigen MA von oben nach unten
                    if ma_short is not None and ma_medium is not None and ma_short < ma_medium and len(historic_data.get('prices', [])) > 2:
                        # Prüfe, ob es vorher eine Kreuzung gab
                        prev_ma_short = berechne_gleitenden_durchschnitt(preise[:-1], 9)
                        prev_ma_medium = berechne_gleitenden_durchschnitt(preise[:-1], 20)
                        if len(preise) > 10 and prev_ma_short is not None and prev_ma_medium is not None and prev_ma_short > prev_ma_medium:
                            verkauf_signale.append(f"Death Cross: MA9 (${ma_short:.2f}) unter MA20 (${ma_medium:.2f})")
                    
                    # HANDLUNGEN BASIEREND AUF KAUF-/VERKAUFSSIGNALEN
                    config = lade_konfiguration()
                    min_trade_amount_usd = config.get("min_trade_amount_usd", 1.0)
                    # Kaufsignal, wenn mindestens 2 Indikatoren gleichzeitig ein Kaufsignal geben
                    if len(kauf_signale) >= 1 and guthaben > min_trade_amount_usd:
                        # Je mehr Signale, desto aggressiver kaufen
                        signal_faktor = min(1.0, len(kauf_signale) * 0.3)  # 2 Signale = 0.6, 3 Signale = 0.9, >=4 Signale = 1.0
                        
                        # Kaufprozentsatz basierend auf Signalstärke
                        buying_percentage = config.get("buying_percentage", 0.05) * (1 + signal_faktor)
                        buy_amount = guthaben * buying_percentage
                        
                        if buy_amount >= min_trade_amount_usd:
                            # Führe den Kauf aus
                            kaufen_dynamic(aktueller_preis, buying_percentage)
                            logging.info(f"TECHNISCHE KAUFSIGNALE aktiviert: {', '.join(kauf_signale)}")
                            logging.info(f"Kauf mit {buying_percentage*100:.1f}% des Guthabens (${buy_amount:.2f})")
                        else:
                            logging.info(f"Kaufsignale erkannt, aber Betrag zu gering: ${buy_amount:.2f} < ${min_trade_amount_usd}")
                    
                    # Verkaufssignal, wenn mindestens 2 Indikatoren gleichzeitig ein Verkaufssignal geben
                    elif len(verkauf_signale) >= 2 and bitcoin_bestand > 0:
                        # Je mehr Signale, desto aggressiver verkaufen
                        signal_faktor = min(1.0, len(verkauf_signale) * 0.3)  # 2 Signale = 0.6, 3 Signale = 0.9, >=4 Signale = 1.0
                        
                        # Verkaufsprozentsatz basierend auf Signalstärke
                        min_selling_percentage = config.get("min_selling_percentage", 0.05)
                        max_selling_percentage = config.get("max_selling_percentage", 0.25)
                        
                        # Dynamische Verkaufsmenge basierend auf Signalstärke
                        selling_percentage = min_selling_percentage + (max_selling_percentage - min_selling_percentage) * signal_faktor
                        btc_to_sell = bitcoin_bestand * selling_percentage
                        sell_value = btc_to_sell * aktueller_preis
                        
                        if sell_value >= min_trade_amount_usd:
                            # Führe den Verkauf aus
                            verkaufen_dynamic(aktueller_preis, selling_percentage)
                            logging.info(f"TECHNISCHE VERKAUFSSIGNALE aktiviert: {', '.join(verkauf_signale)}")
                            logging.info(f"Verkauf von {selling_percentage*100:.1f}% BTC-Bestand (${sell_value:.2f})")
                        else:
                            logging.info(f"Verkaufssignale erkannt, aber Betrag zu gering: ${sell_value:.2f} < ${min_trade_amount_usd}")
                    
                    # Wenn keine Signale oder zu wenige, nutze traditionelle Strategien
                    else:
                        # Keine klaren Indikatorsignale: Nutze die traditionelle MA-basierte Strategie
                        if durchschnitt is not None:
                            logging.info(f"Moving average ({ma_window}): ${durchschnitt}")
                            
                            # Calculate difference
                            differenz = aktueller_preis - durchschnitt
                            logging.info(f"Difference from average: ${differenz:.2f}")
                            
                            # Strategie 1: Kaufen bei leichtem Anstieg (wie bisher)
                            if aktueller_preis > durchschnitt and aktueller_preis <= durchschnitt + 50:
                                # Small increase - buy more (only if we have enough balance)
                                buying_percentage = config.get("buying_percentage", 0.05)
                                buy_amount = guthaben * buying_percentage
                                
                                if buy_amount >= min_trade_amount_usd:
                                    kaufen_dynamic(aktueller_preis, buying_percentage)
                                    logging.info(f"Making a buy trade (small increase) with {buying_percentage*100}% of balance (${buy_amount:.2f})")
                                else:
                                    logging.info(f"Buy amount ${buy_amount:.2f} below minimum trade size of ${min_trade_amount_usd}")
                            
                            # Strategie 2: Kaufen bei Kursfall (neu - aggressiver!)
                            elif aktueller_preis < durchschnitt:
                                # Der Preis liegt unter dem Durchschnitt - "Buy the Dip"
                                # Je größer der Abfall, desto größer der Kauf (mit Begrenzung)
                                diff_percentage = (durchschnitt - aktueller_preis) / durchschnitt
                                
                                # NEUE STRATEGIE: Aggressivere Kaufmengen
                                # Maximaler Kauf bei 3% Kursfall (kaufe 20% des Guthabens statt vorher 10%)
                                # Bei kleineren Kursfällen entsprechend weniger
                                max_buying_percentage = 0.20  # Maximal 20% des Guthabens investieren (erhöht von 10%)
                                min_buying_percentage = 0.03  # Mindestens 3% des Guthabens investieren (erhöht von 2%)
                                
                                # Stärkere Reaktion auf Preisdips: Multiplikator 5 statt vorher 3
                                # Bei 1% Dip kauft der Bot jetzt ca. 8% des Guthabens (vorher 5%)
                                buying_percentage = min(max_buying_percentage, 
                                                     max(min_buying_percentage, diff_percentage * 5))
                                
                                buy_amount = guthaben * buying_percentage
                                
                                # Niedrigere Schwelle aus der Konfiguration lesen
                                min_dip_percentage = config.get("min_dip_percentage", 0.002)  # Default: 0.2%
                                
                                # Kauf nur, wenn genug Guthaben und der Dip größer als Mindestwert
                                if buy_amount >= min_trade_amount_usd and diff_percentage >= min_dip_percentage:
                                    kaufen_dynamic(aktueller_preis, buying_percentage)
                                    logging.info(f"Buy the dip! Price {diff_percentage*100:.1f}% below average. " + 
                                               f"Buying with {buying_percentage*100:.1f}% of balance (${buy_amount:.2f})")
                                else:
                                    if diff_percentage < min_dip_percentage:
                                        logging.info(f"Price dip of {diff_percentage*100:.2f}% too small to trigger buy (minimum: {min_dip_percentage*100:.2f}%)")
                                    else:
                                        logging.info(f"Buy amount ${buy_amount:.2f} below minimum trade size of ${min_trade_amount_usd}")
                            
                            elif aktueller_preis > durchschnitt + 50:
                                # Verkaufsstrategie: Gradueller Verkauf basierend auf Höhe über dem Durchschnitt
                                # Je höher über dem Durchschnitt, desto mehr wird verkauft, aber in kleineren Schritten
                                
                                # Berechnen, wie weit der Preis über dem Durchschnitt liegt (in Prozent)
                                prozent_ueber_durchschnitt = (aktueller_preis - durchschnitt) / durchschnitt
                                
                                # Basis-Verkaufsprozentsatz (Minimum)
                                min_selling_percentage = config.get("min_selling_percentage", 0.05)  # Start mit 5%
                                
                                # Maximaler Verkaufsprozentsatz: Im Hochpreisbereich genau 25% verkaufen
                                max_selling_percentage = config.get("max_selling_percentage", 0.25)  # Genau 25% (ein Viertel) verkaufen
                                
                                # Berechne Verkaufsprozentsatz basierend auf Abstand zum Durchschnitt
                                # Bei 5% über Durchschnitt -> ca. 15% verkaufen
                                # Bei 8% oder mehr über Durchschnitt -> genau 25% verkaufen
                                selling_percentage = min(max_selling_percentage, 
                                                      min_selling_percentage + (prozent_ueber_durchschnitt * 2.5))
                                
                                # Verkaufswerte berechnen
                                btc_to_sell = bitcoin_bestand * selling_percentage
                                sell_value = btc_to_sell * aktueller_preis
                                
                                # Stufenweise Verkaufsintensität für Logging
                                if prozent_ueber_durchschnitt > 0.1:
                                    verkaufstyp = "starker"
                                elif prozent_ueber_durchschnitt > 0.05:
                                    verkaufstyp = "moderater"
                                else:
                                    verkaufstyp = "leichter"
                                
                                # Verkauf durchführen, wenn genug BTC vorhanden sind
                                if sell_value >= min_trade_amount_usd:
                                    verkaufen_dynamic(aktueller_preis, selling_percentage)
                                    logging.info(f"Verkauf bei {verkaufstyp} Kursanstieg: {prozent_ueber_durchschnitt*100:.1f}% über Durchschnitt. " + 
                                               f"Verkaufe {selling_percentage*100:.1f}% des BTC-Bestands (${sell_value:.2f})")
                                else:
                                    logging.info(f"Sell value ${sell_value:.2f} below minimum trade size of ${min_trade_amount_usd}")
                else:  # Nicht genug Daten für fortgeschrittene Indikatoren
                    # Traditionelle Moving Average Strategie (Fallback)
                    if durchschnitt is not None:
                        logging.info(f"Moving average ({ma_window}): ${durchschnitt}")
                        
                        # Calculate difference
                        differenz = aktueller_preis - durchschnitt
                        logging.info(f"Difference from average: ${differenz:.2f}")
                        
                        # Einfache MA-basierte Strategie (siehe oben in den Indikator-Strategien)
                        # Verwende einfachere Regeln bei nicht genug Daten
                
                # Zusätzliche Verkaufsoption basierend auf konfiguriertem Verkaufswert
                # (Dieser Wert dient als "Notausgang" und sollte nur genutzt werden wenn der Preis den konfigurierten Wert überschreitet)
                if aktueller_preis > verkaufswert:
                    # Auch hier: Moderatere Verkaufsstrategie (15% statt vorher 25%)
                    selling_percentage = 0.15
                    btc_to_sell = bitcoin_bestand * selling_percentage
                    sell_value = btc_to_sell * aktueller_preis
                    
                    if sell_value >= min_trade_amount_usd:
                        logging.info(f"Preis über konfiguriertem Schwellenwert von ${verkaufswert} - Verkaufe 15% des BTC-Bestands")
                        verkaufen_dynamic(aktueller_preis, selling_percentage)
                    else:
                        logging.info(f"Sell value ${sell_value:.2f} below minimum trade size of ${min_trade_amount_usd}")
            else:
                logging.error("Error fetching price. Waiting for next attempt...")

            # Marktanalyse aufrufen
            marktanalyse = analysiere_markt(preise)
            logging.info(
                f"📊 Marktanalyse: Trend={marktanalyse['trend']} | Momentum={marktanalyse['momentum']} | Empfehlung={marktanalyse['empfehlung']}")

            # Beispiel: bei starker negativer Empfehlung auf Verkauf forcieren
            if marktanalyse['empfehlung'].startswith("schnell verkaufen") and bitcoin_bestand > 0:
                btc_to_sell = bitcoin_bestand * 0.25  # direkt 25% verkaufen
                sell_value = btc_to_sell * aktueller_preis
                if sell_value >= min_trade_amount_usd:
                    verkaufen_dynamic(aktueller_preis, 0.25)
                    logging.info("🚨 Automatischer Panik-Verkauf wegen Marktanalyse ausgelöst!")

            # Pause between checks
            time.sleep(price_check_interval)
            
        except Exception as e:
            logging.error(f"Error in trading loop: {e}")
            time.sleep(10)  # Wait a bit on error
    
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
