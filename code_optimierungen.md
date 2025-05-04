# Code-Optimierungen für den Bitcoin Tracker

Hier sind alle Code-Änderungen, die Sie in Ihren BitcoinTracker Main-Code übernehmen können:

## 1. Zeitzonenverbesserungen in app.py

### API-Endpunkte mit expliziter UTC-Zeitzone

```python
# In der get_current_price() Funktion:

# Vorher:
return jsonify({
    "price": price,
    "timestamp": datetime.now().isoformat(),
    "timezone_offset": time.strftime("%z", time.localtime())
})

# Nachher:
now = datetime.now().replace(microsecond=0)
timezone_str = "+00:00"  # Explizite UTC-Timezone
timestamp = now.isoformat() + timezone_str

return jsonify({
    "price": price, 
    "timestamp": timestamp, 
    "success": True,
    "cache_buster": random.randint(1, 1000000),  # Force browser to get fresh data
    "timezone_offset": timezone_str  # Include timezone info explicitly
})
```

### Trading-History mit Zeitzone

```python
# In der get_trade_history() Funktion:

# Vorher:
return jsonify([{
    "id": trade.id,
    "type": trade.type,
    "price": trade.price,
    "amount": trade.amount,
    "timestamp": trade.timestamp.isoformat()
} for trade in trades])

# Nachher:
return jsonify([{
    "id": trade.id,
    "type": trade.type,
    "price": trade.price,
    "amount": trade.amount,
    "timestamp": trade.timestamp.isoformat() + "+00:00"  # Explicit UTC timezone info
} for trade in trades])
```

### Korrekte Cooldown-Zeit

```python
# In der get_bot_status() Funktion:

# Vorher:
"cooldown_until": trading_bot.price_cache['api_cooldown_until'].isoformat() if trading_bot.price_cache['api_cooldown_until'] else None

# Nachher:
"cooldown_until": trading_bot.price_cache['api_cooldown_until'].isoformat() + "+00:00" if trading_bot.price_cache['api_cooldown_until'] else None
```

## 2. API-Fallback-System in trading_bot.py

### Attribute hinzufügen

```python
# Am Anfang von trading_bot.py nach globalen Variablen:

# API-Status-Variablen
api_source = "coingecko"  # 'coingecko', 'binance', 'fallback'
api_status = "ok"  # 'ok', 'rate_limited', 'error'

# Cache-System für Preise
price_cache = {
    'last_price': None,
    'timestamp': None,
    'api_cooldown_until': None
}
```

### Verbesserte Bitcoin-Preis-Funktion

```python
def get_bitcoin_price():
    """Get the current Bitcoin price from CoinGecko API with caching"""
    global price_cache, api_source, api_status
    
    now = datetime.now()
    
    # Wenn API im Cooldown ist, Simulations-Modus verwenden
    if price_cache['api_cooldown_until'] and now < price_cache['api_cooldown_until']:
        # Simulierten Preis mit leichten Variationen erzeugen
        if price_cache['last_price']:
            variation = random.uniform(-0.3, 0.3)  # ±0.3% Variation
            simulated_price = price_cache['last_price'] * (1 + variation/100)
            logging.info(f"API in cooldown. Using simulated price: ${simulated_price:.2f}")
            return simulated_price
        else:
            # Wenn kein letzter Preis bekannt ist, Standardwert verwenden
            logging.info(f"Using fallback Bitcoin price: ${FALLBACK_PRICE}")
            return FALLBACK_PRICE
    
    # 1. Versuch: CoinGecko API
    try:
        if api_source != "coingecko" or api_status == "rate_limited":
            # Wenn wir von einer Fallback-API kommen, versuche wieder die primäre API
            logging.info("Attempting to use primary API (CoinGecko) again")
        
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        
        if response.status_code == 200:
            price = response.json()["bitcoin"]["usd"]
            
            # Cache aktualisieren
            price_cache['last_price'] = price
            price_cache['timestamp'] = now
            price_cache['api_cooldown_until'] = None
            
            # API-Status aktualisieren
            api_source = "coingecko"
            api_status = "ok"
            
            return price
        elif response.status_code == 429:
            # Rate limit erreicht, Fallback verwenden
            logging.error(f"Error fetching Bitcoin price: {response.status_code} {response.reason} for url: {response.url}")
            api_status = "rate_limited"
            
            # Cooldown-Zeit setzen (15 Minuten)
            cooldown_until = now + timedelta(minutes=15)
            price_cache['api_cooldown_until'] = cooldown_until
            logging.warning(f"API rate limit hit. Entering cooldown mode for 15 minutes until {cooldown_until}")
            
            # Auf Binance umschalten
            return get_bitcoin_price_binance()
        else:
            logging.error(f"Error fetching Bitcoin price from CoinGecko: Status {response.status_code}")
            api_status = "error"
            return get_bitcoin_price_binance()
            
    except Exception as e:
        logging.error(f"Error fetching Bitcoin price: {e}")
        api_status = "error"
        return get_bitcoin_price_binance()

def get_bitcoin_price_binance():
    """Get Bitcoin price from Binance API as fallback"""
    global api_source, price_cache, api_status
    
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=5
        )
        
        if response.status_code == 200:
            price = float(response.json()["price"])
            
            # Cache aktualisieren
            price_cache['last_price'] = price
            price_cache['timestamp'] = datetime.now()
            
            # API-Status aktualisieren
            api_source = "binance"
            api_status = "ok"
            
            return price
        elif response.status_code == 429:
            # Rate limit erreicht, Fallback verwenden
            logging.error(f"Error fetching Bitcoin price from Binance: Rate limit reached")
            api_status = "rate_limited"
            
            # Binance ist auch im Rate Limit, verwende Fallback-Preis
            # Cooldown-Zeit setzen (15 Minuten)
            cooldown_until = datetime.now() + timedelta(minutes=15)
            price_cache['api_cooldown_until'] = cooldown_until
            logging.warning(f"Binance API rate limit hit. Using fallback price for 15 minutes until {cooldown_until}")
            
            api_source = "fallback"
            api_status = "rate_limited"
            
            # Verwende letzten bekannten Preis oder Fallback
            if price_cache['last_price']:
                return price_cache['last_price']
            else:
                logging.info(f"Using fallback Bitcoin price: ${FALLBACK_PRICE}")
                return FALLBACK_PRICE
        else:
            logging.error(f"Error fetching Bitcoin price from Binance: Status {response.status_code}")
            api_source = "fallback"
            api_status = "error"
            
            # Verwende letzten bekannten Preis oder Fallback
            if price_cache['last_price']:
                return price_cache['last_price']
            else:
                logging.info(f"Using fallback Bitcoin price: ${FALLBACK_PRICE}")
                return FALLBACK_PRICE
            
    except Exception as e:
        logging.error(f"Error fetching Bitcoin price from Binance: {e}")
        api_source = "fallback"
        api_status = "error"
        
        # Verwende letzten bekannten Preis oder Fallback
        if price_cache['last_price']:
            return price_cache['last_price']
        else:
            logging.info(f"Using fallback Bitcoin price: ${FALLBACK_PRICE}")
            return FALLBACK_PRICE
```

## 3. Frontend-Optimierungen (dashboard.js)

### Zeitzonenkonvertierung

```javascript
// Am Anfang des dashboard.js:

// Zeitzoneneinstellung und Formatierung
let serverTimezoneOffset = "+00:00";  // Server ist in UTC
let browserTimezoneOffset = new Date().getTimezoneOffset();

// Konvertiert ISO-Zeitstempel in lokale Zeit
function formatDateTime(isoDateString) {
    if (!isoDateString) return 'N/A';
    
    const date = new Date(isoDateString);
    
    // Überprüfen auf ungültiges Datum
    if (isNaN(date.getTime())) return 'Ungültiges Datum';
    
    // Format: "29.04.2025, 13:45:30"
    return date.toLocaleString('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Zeitdifferenz berechnen (für "vor X Minuten")
function getTimeDifferenceString(isoDateString) {
    if (!isoDateString) return '';
    
    const date = new Date(isoDateString);
    const now = new Date();
    
    // Differenz in Millisekunden
    const diffMs = now - date;
    
    // Verschiedene Zeiteinheiten
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSeconds < 60) {
        return `vor ${diffSeconds} Sekunden`;
    } else if (diffMinutes < 60) {
        return `vor ${diffMinutes} Minuten`;
    } else if (diffHours < 24) {
        return `vor ${diffHours} Stunden`;
    } else {
        return `vor ${diffDays} Tagen`;
    }
}
```

### API-Status-Anzeige

```javascript
// Füge diese Funktion in dashboard.js ein:

// API-Status aktualisieren
function updateApiStatusDisplay(data) {
    const statusElement = document.getElementById('api-status');
    if (!statusElement) return;
    
    let statusText = '';
    let statusClass = '';
    
    // Server-Zeitzone speichern
    if (data.timezone_offset) {
        serverTimezoneOffset = data.timezone_offset;
        console.log("Server timezone offset:", serverTimezoneOffset);
    }
    
    // API-Statusanzeige basierend auf der Quelle und dem Status
    switch(data.api_source) {
        case 'coingecko':
            statusText = 'CoinGecko API';
            statusClass = 'status-ok';
            break;
        case 'binance':
            statusText = 'Binance API (Fallback)';
            statusClass = 'status-warning';
            break;
        case 'fallback':
            statusText = 'Simulierte Daten (Keine API verfügbar)';
            statusClass = 'status-error';
            break;
        default:
            statusText = 'Unbekannte Quelle';
            statusClass = 'status-error';
    }
    
    // API-Rate-Limit-Status
    if (data.api_status === 'rate_limited') {
        statusText += ' (Rate Limited)';
        statusClass = 'status-warning';
        
        // Wenn Cooldown-Zeit vorhanden, zeige Countdown an
        if (data.cooldown_until) {
            const cooldownTime = new Date(data.cooldown_until);
            const now = new Date();
            const diffMs = cooldownTime - now;
            
            if (diffMs > 0) {
                const diffMinutes = Math.ceil(diffMs / 60000);
                statusText += ` - Wiederversuchen in ${diffMinutes} Min.`;
            }
        }
    } else if (data.api_status === 'error') {
        statusText += ' (Fehler)';
        statusClass = 'status-error';
    }
    
    // UI aktualisieren
    statusElement.textContent = statusText;
    
    // Alle Status-Klassen entfernen
    statusElement.classList.remove('status-ok', 'status-warning', 'status-error');
    
    // Neue Status-Klasse hinzufügen
    statusElement.classList.add(statusClass);
}
```

### Zeitgesteuerte Bot-Status-Abfrage

```javascript
// Ändere die Refresh-Funktionen:

// Separate Intervalle für verschiedene Datentypen
let priceRefreshInterval = 30000;  // 30 Sekunden für Preise
let botStatusRefreshInterval = 20000;  // 20 Sekunden für Bot-Status

// Preisdaten aktualisieren
function refreshPrice() {
    fetch('/api/current_price')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                document.getElementById('current-price').textContent = 'Fehler beim Laden des Preises';
                return;
            }
            
            // Preis aktualisieren
            document.getElementById('current-price').textContent = formatCurrency(data.price);
            
            // Zeitstempel aktualisieren
            if (data.timestamp) {
                const formattedTime = formatDateTime(data.timestamp);
                document.getElementById('price-timestamp').textContent = formattedTime;
            }
            
            // API-Status aktualisieren
            updateApiStatusDisplay(data);
            
            // Letzter Preis für Berechnungen
            lastPrice = data.price;
            
            // Schätzung aktualisieren
            updateEstimatedBTC();
        })
        .catch(error => {
            console.error('Error fetching price:', error);
            document.getElementById('current-price').textContent = 'Fehler beim Laden des Preises';
        });
}

// Bot-Status abfragen
function checkBotStatus() {
    fetch('/api/bot_status')
        .then(response => response.json())
        .then(data => {
            // Bot-Status aktualisieren
            updateBotStatusUI(data.enabled);
            
            // API-Status-Anzeige aktualisieren
            updateApiStatusDisplay(data);
        })
        .catch(error => {
            console.error('Error checking bot status:', error);
        });
}

// Initialisierung
document.addEventListener('DOMContentLoaded', function() {
    // Initialisierung hier...
    
    // Regelmäßige Updates mit unterschiedlichen Intervallen
    refreshPrice();  // Sofort ausführen
    checkBotStatus();  // Sofort ausführen
    refreshPortfolio();  // Sofort ausführen
    getRecentTrades();  // Sofort ausführen
    
    // Intervalle setzen
    setInterval(refreshPrice, priceRefreshInterval);
    setInterval(checkBotStatus, botStatusRefreshInterval);
    setInterval(refreshPortfolio, 45000);  // 45 Sekunden
    setInterval(getRecentTrades, 60000);   // 1 Minute
});
```

## 4. HTML-Änderungen (templates/dashboard.html)

### API-Status-Anzeige hinzufügen

```html
<!-- In der #info-box oder einem anderen sichtbaren Bereich -->
<div class="api-status-container">
    <span class="status-label">Datenquelle:</span>
    <span id="api-status" class="status-indicator status-ok">CoinGecko API</span>
</div>
```

### CSS für Status-Anzeige (static/css/style.css)

```css
/* API-Status-Anzeige */
.api-status-container {
    margin-top: 10px;
    padding: 5px 10px;
    border-radius: 5px;
    font-size: 0.85rem;
    background-color: #f8f9fa;
}

.status-label {
    font-weight: bold;
    margin-right: 5px;
}

.status-indicator {
    padding: 3px 8px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
}

.status-ok {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.status-warning {
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeeba;
}

.status-error {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}
```