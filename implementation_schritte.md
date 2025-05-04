# Implementierungsschritte für BitcoinTracker Main

Folgen Sie diesen Schritten, um alle Optimierungen in Ihren Bitcoin Tracker Main-Code zu übertragen:

## 1. Backup erstellen

Bevor Sie Änderungen vornehmen, erstellen Sie am besten eine Sicherungskopie Ihres aktuellen Codes:

```bash
# In Ihrem Projektverzeichnis
mkdir backup
cp -r *.py templates/ static/ config.json backup/
```

## 2. Zeitzonen-Updates in app.py

1. Öffnen Sie die Datei `app.py`
2. Suchen Sie alle Stellen, an denen Zeitstempel als JSON zurückgegeben werden
3. Fügen Sie überall `+ "+00:00"` zu `.isoformat()` hinzu
4. Ändern Sie die `get_current_price()` Funktion, um die UTC-Zeitzone explizit anzugeben

## 3. API-Fallback-System einrichten

1. Öffnen Sie die Datei `trading_bot.py`
2. Fügen Sie die neuen API-Status-Variablen hinzu:
   - `api_source`, `api_status` und `price_cache`
3. Implementieren Sie die verbesserte `get_bitcoin_price()` Funktion mit Fallback
4. Fügen Sie die neue `get_bitcoin_price_binance()` Funktion hinzu
5. Aktualisieren Sie alle Stellen, die auf `get_bitcoin_price()` zugreifen

## 4. Dashboard mit Zeitzonenkonvertierung und API-Status

1. Bearbeiten Sie `templates/dashboard.html`:
   - Fügen Sie den API-Status-Container hinzu
2. Aktualisieren Sie `static/js/dashboard.js`:
   - Fügen Sie Zeitzonenkonvertierungsfunktionen hinzu
   - Implementieren Sie die `updateApiStatusDisplay` Funktion
   - Aktualisieren Sie die Refresh-Intervalle für unterschiedliche Datentypen
3. Aktualisieren Sie `static/css/style.css`:
   - Fügen Sie Styling für die Status-Anzeige hinzu

## 5. Charting-Verbesserungen

1. Bearbeiten Sie `static/js/charts.js`:
   - Aktualisieren Sie die Zeitstempel-Verarbeitung für korrekte lokale Anzeige
   - Verbessern Sie die Formatierung der X-Achse

## 6. Trading-Bot-Verbesserungen

1. Aktualisieren Sie die Trading-Strategie, falls gewünscht:
   - Verwenden Sie die verbesserten technischen Indikatoren
   - Implementieren Sie mehr Sicherheitsmaßnahmen

## 7. Testen

1. Starten Sie den Server neu
2. Überprüfen Sie das API-Fallback-System durch absichtliches Auslösen von Rate-Limiting
3. Bestätigen Sie, dass Zeitstempel korrekt in Ihrer lokalen Zeitzone angezeigt werden
4. Überprüfen Sie die API-Status-Anzeige im Dashboard
5. Testen Sie die Reaktion bei verschiedenen API-Fehlern

## 8. Fehlerbehebung

Falls Probleme auftreten:

1. Überprüfen Sie die Server-Logs auf Fehler
2. Stellen Sie sicher, dass alle Abhängigkeiten korrekt installiert sind
3. Überprüfen Sie die Browser-Konsole auf JavaScript-Fehler
4. Falls nötig, stellen Sie aus dem Backup wieder her und versuchen Sie es erneut mit einem schrittweisen Ansatz

## Zusammenfassung der wichtigsten Dateien

1. `app.py` - Zeitzonenkorrekturen in allen API-Endpunkten
2. `trading_bot.py` - API-Fallback-System und verbesserte Preisabfrage
3. `templates/dashboard.html` - API-Status-Anzeige
4. `static/js/dashboard.js` - Zeitzonenkonvertierung und Status-Updates
5. `static/css/style.css` - Styling für Status-Anzeige
6. `static/js/charts.js` - Verbesserte Zeitdarstellung in Charts