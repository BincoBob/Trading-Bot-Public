from extensions import db
import os
basedir = os.path.abspath(os.path.dirname(__file__))
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix
import json
from datetime import datetime, timedelta
import random
# ALT (vermeidet diese Variante!)
# from mexc_handler import get_current_price

# NEU
from mexc_handler import get_current_price as get_mexc_price
from trading_bot import wallet, get_mexc_cheap_coins



# Logging aktivieren
logging.basicConfig(level=logging.DEBUG)

# Flask App erstellen
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Datenbank konfigurieren
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'instance', 'bitcoin_trader.db')}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False



# DB mit App verbinden
db.init_app(app)

# Import models after initializing db
from models import Trade, PriceHistory

# Create database tables
with app.app_context():
    db.create_all()

# Import and initialize trading bot after db setup
import trading_bot
trading_bot.init_bot()

# Routes
@app.route('/')
def index():
    """Home page with basic information"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard with trading interface"""
    return render_template('dashboard.html')

@app.route('/config', methods=['GET', 'POST'])
def config():
    """Configuration page for trading parameters"""
    if request.method == 'POST':
        try:
            config_data = {
                "verkaufswert": float(request.form.get('verkaufswert', 94500)),
                "buying_percentage": float(request.form.get('buying_percentage', 0.05)),
                "selling_percentage_moderate": float(request.form.get('selling_percentage_moderate', 0.25)),
                "selling_percentage_high": float(request.form.get('selling_percentage_high', 0.5)),
                "ma_window": int(request.form.get('ma_window', 3)),
                "price_check_interval": int(request.form.get('price_check_interval', 30))
            }
            
            with open('config.json', 'w') as f:
                json.dump(config_data, f, indent=4)
            
            flash('Configuration updated successfully', 'success')
            return redirect(url_for('config'))
        except Exception as e:
            flash(f'Error updating configuration: {str(e)}', 'danger')
    
    # Load existing configuration
    config_data = trading_bot.lade_konfiguration()
    
    return render_template('config.html', config=config_data)

@app.route('/history')
def history():
    """Trade history page"""
    # Get trades from database
    trades = Trade.query.order_by(Trade.timestamp.desc()).all()
    return render_template('history.html', trades=trades)

# API routes
@app.route('/api/current_price')
def get_current_price():
    """Get current Bitcoin price from MEXC"""
    price = get_mexc_price()

    now = datetime.now().replace(microsecond=0)
    timezone_str = "+00:00"
    timestamp = now.isoformat() + timezone_str

    if price:
        with app.app_context():
            price_history = PriceHistory(price=price, timestamp=now)
            db.session.add(price_history)
            db.session.commit()

        return jsonify({
            "price": price,
            "timestamp": timestamp,
            "success": True,
            "cache_buster": random.randint(1, 1000000),
            "timezone_offset": timezone_str
        })
    else:
        logging.error("❌ Preis konnte nicht von MEXC geladen werden")
        return jsonify({"error": "Failed to fetch MEXC price", "success": False}), 500
        
@app.route('/api/config')
def get_config():
    """Get current configuration"""
    config_data = trading_bot.lade_konfiguration()
    return jsonify(config_data)
    
@app.route('/api/bot_status')
def get_bot_status():
    """Get current bot status"""
    return jsonify({
        "enabled": trading_bot.trading_enabled,
        "api_source": trading_bot.api_source,
        "api_status": trading_bot.api_status,
        "cooldown_until": trading_bot.price_cache['api_cooldown_until'].isoformat() + "+00:00" if trading_bot.price_cache['api_cooldown_until'] else None
    })
    
@app.route('/api/force_trade', methods=['GET'])
def force_trade():
    """Force a test trade (for debugging)"""
    current_price = trading_bot.get_bitcoin_price()
    
    if current_price and trading_bot.guthaben > 10:
        # Make a small test purchase to verify trading works
        success = trading_bot.kaufen(current_price, 10.0)
        if success:
            return jsonify({
                "success": True, 
                "message": f"Test purchase executed: $10.00 at price ${current_price}",
                "new_balance": trading_bot.guthaben,
                "new_bitcoin": trading_bot.bitcoin_bestand
            })
        else:
            return jsonify({"success": False, "message": "Failed to execute test trade"})
    else:
        return jsonify({"success": False, "message": "Insufficient balance or price data"})

@app.route('/api/portfolio')
def get_portfolio():
    """Get current portfolio status directly from MEXC"""
    from mexc_handler import get_mexc_balances, get_current_price

    usd_balance, btc_bestand = get_mexc_balances()
    current_price = get_current_price() or 0
    btc_value = btc_bestand * current_price
    portfolio_value = usd_balance + btc_value

    return jsonify({
        "balance": round(usd_balance, 2),
        "bitcoin": round(btc_bestand, 8),
        "btc_value": round(btc_value, 2),
        "portfolio_value": round(portfolio_value, 2),
        "price": round(current_price, 2)
    })




@app.route('/api/trade_history')
def get_trade_history():
    """Get trading history"""
    trades = Trade.query.order_by(Trade.timestamp.desc()).limit(50).all()
    
    return jsonify([{
        "id": trade.id,
        "type": trade.type,
        "price": trade.price,
        "amount": trade.amount,
        "timestamp": trade.timestamp.isoformat() + "+00:00"  # Explicit UTC timezone info
    } for trade in trades])

@app.route('/api/price_history')
def get_price_history():
    """Get price history for charts"""
    days = request.args.get('days', 1, type=int)
    limit = request.args.get('limit', 1000, type=int)  # Maximum number of data points
    interval_minutes = request.args.get('interval', 0, type=int)  # Sampling interval in minutes (0 = auto)
    
    # Automatisches Intervall basierend auf Zeitraum
    if interval_minutes == 0:
        if days == 1:
            interval_minutes = 5  # 5-Minuten-Intervall für Tagesansicht
        elif days <= 7:
            interval_minutes = 30  # 30-Minuten-Intervall für Wochenansicht
        elif days <= 30:
            interval_minutes = 120  # 2-Stunden-Intervall für Monatsansicht
        else:
            interval_minutes = 360  # 6-Stunden-Intervall für längere Zeiträume
    
    # Versuche zuerst, erweiterte Daten aus dem Trading Bot zu bekommen
    try:
        from trading_bot import historic_data
        
        if historic_data and historic_data['prices'] and len(historic_data['prices']) > 0:
            # Zeitraum filtern
            cutoff = datetime.now() - timedelta(days=days)
            filtered_data = []
            
            # Wir verwenden einen Zeitraum-basierten Ansatz für das Sampling
            last_included_timestamp = None
            
            # Füge nur die Datenpunkte innerhalb des Zeitraums mit dem gewünschten Intervall hinzu
            for i, ts in enumerate(historic_data['timestamps']):
                if ts >= cutoff:
                    # Prüfen, ob dieser Datenpunkt gemäß dem Intervall hinzugefügt werden soll
                    if last_included_timestamp is None or (ts - last_included_timestamp).total_seconds() >= interval_minutes * 60:
                        data_point = {
                            "price": historic_data['prices'][i],
                            "timestamp": ts.isoformat() + "+00:00"  # Explicit UTC timezone info
                        }
                        
                        # Füge Volumen und Marktkapitalisierung hinzu, falls vorhanden
                        if i < len(historic_data['volumes']) and historic_data['volumes'][i] > 0:
                            data_point["volume"] = historic_data['volumes'][i]
                        
                        if i < len(historic_data['market_caps']) and historic_data['market_caps'][i] > 0:
                            data_point["marketCap"] = historic_data['market_caps'][i]
                        
                        filtered_data.append(data_point)
                        last_included_timestamp = ts
            
            # Wenn wir genügend Daten haben, verwende diese
            if len(filtered_data) > 5:  # Mindestanzahl für sinnvolle Darstellung
                logging.info(f"Returning {len(filtered_data)} extended data points from trading bot (interval: {interval_minutes} min)")
                return jsonify(filtered_data)
    except Exception as e:
        logging.error(f"Error getting extended price history: {e}")
    
    # Fallback auf die Datenbank, wenn keine erweiterten Daten verfügbar sind
    try:
        # Get data since the specified number of days ago
        since = datetime.now() - timedelta(days=days)
        
        # Hier könnten wir SQL-Abfragen mit GROUP BY für das Sampling verwenden,
        # aber für Einfachheit verwenden wir einen Python-basierten Ansatz
        prices = PriceHistory.query.filter(
            PriceHistory.timestamp >= since
        ).order_by(PriceHistory.timestamp).limit(limit).all()
        
        # Zeitraum-basiertes Sampling
        sampled_prices = []
        last_included_timestamp = None
        
        for price in prices:
            if last_included_timestamp is None or (price.timestamp - last_included_timestamp).total_seconds() >= interval_minutes * 60:
                sampled_prices.append(price)
                last_included_timestamp = price.timestamp
        
        logging.info(f"Returning {len(sampled_prices)} price data points from database (interval: {interval_minutes} min)")
        return jsonify([{
            "price": price.price,
            "timestamp": price.timestamp.isoformat() + "+00:00"  # Explicit UTC timezone info
        } for price in sampled_prices])
    except Exception as e:
        logging.error(f"Error sampling price history from database: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/execute_trade', methods=['POST'])
def execute_trade():
    """Execute a manual trade"""
    try:
        data = request.get_json()
        trade_type = data.get('type')
        amount = float(data.get('amount', 0))
        
        if trade_type not in ['buy', 'sell']:
            return jsonify({"error": "Invalid trade type", "success": False}), 400
        
        current_price = trading_bot.get_bitcoin_price()
        if not current_price:
            return jsonify({"error": "Could not get current price", "success": False}), 500
        
        if trade_type == 'buy':
            if amount > trading_bot.guthaben:
                return jsonify({"error": "Not enough balance for this purchase", "success": False}), 400
                
            trading_bot.kaufen(current_price, amount)
            message = f"Successfully bought Bitcoin for ${amount}"
            
        else:  # sell
            btc_amount = amount / current_price  # Convert USD to BTC
            if btc_amount > trading_bot.bitcoin_bestand:
                return jsonify({"error": "Not enough Bitcoin in your portfolio", "success": False}), 400
                
            trading_bot.verkaufen(current_price, btc_amount)
            message = f"Successfully sold {btc_amount:.8f} Bitcoin"
            
        return jsonify({"message": message, "success": True})
        
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/toggle_bot', methods=['POST'])
def toggle_bot():
    """Toggle the automated trading bot on/off"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        if enabled:
            # Start the trading thread
            trading_bot.start_trading_thread()
        else:
            # Stop the trading thread
            trading_bot.stop_trading_thread()
        
        return jsonify({
            "success": True, 
            "message": f"Trading bot {'enabled' if enabled else 'disabled'}",
            "status": trading_bot.trading_enabled
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route("/price")
def get_price():
    try:
        from models import PriceHistory
        last_price = PriceHistory.query.order_by(PriceHistory.timestamp.desc()).first()
        if last_price and last_price.price:
            return jsonify({"preis": round(last_price.price, 2)})
        else:
            return jsonify({"preis": "unbekannt"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"preis": f"Fehler: {str(e)}"}), 500

@app.route('/api/bad_patterns')
def get_bad_patterns():
    """Returns bad_patterns.json content if it exists"""
    try:
        with open("bad_patterns.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({})  # Leere Liste zurückgeben, wenn Datei nicht da ist
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reset_wallet", methods=["POST"])
def reset_wallet():
    """Setzt Wallet-Daten zurück (für Testzwecke)"""
    try:
        with open("wallet_reset.json", "w") as f:
            json.dump({
                "guthaben": 100.0,
                "bitcoin_bestand": 0.01
            }, f)
        with open("wallet_reset.lock", "w") as f:
            f.write("reset")
        return jsonify({"success": True, "message": "Wallet reset requested"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/memory")
def get_memory():
    try:
        with open("memory.json", "r") as f:
            memory = json.load(f)
        return jsonify(memory)
    except FileNotFoundError:
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/portfolio_data')
def portfolio_data():
    from mexc_handler import get_current_price as get_mexc_price, get_mexc_balances
    preis = get_mexc_price()
    guthaben, bitcoin_bestand = get_mexc_balances()

    if preis is None or guthaben is None or bitcoin_bestand is None:
        return jsonify({"error": "Fehler beim Abrufen der Daten"}), 500

    total_value = guthaben + (bitcoin_bestand * preis)
    btc_percent = (bitcoin_bestand * preis) / total_value * 100
    usd_percent = guthaben / total_value * 100

    return jsonify({
        "btc": bitcoin_bestand,
        "usd": guthaben,
        "total": total_value,
        "btc_percent": round(btc_percent, 2),
        "usd_percent": round(usd_percent, 2)
    })

@app.route("/api/wallet")
def api_wallet():
    return jsonify(wallet)

@app.route("/api/coins")
def api_coins():
    coins = get_mexc_cheap_coins(limit_usd=5, max_results=5)
    return jsonify(coins)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)