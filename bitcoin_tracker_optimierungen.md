# Bitcoin Tracker - Optimierungen

## 1. Zeitzonenverbesserungen für bessere Darstellung

### Backend (app.py)
- Zeitstempel werden nun mit expliziter UTC-Zeitzoneninformation ausgeliefert
- API-Endpunkte geben Zeitstempel in ISO-Format mit "+00:00" (UTC)-Suffix zurück
- Cooldown-Zeitstempel werden ebenfalls mit Zeitzoneninformation versehen

Beispiel:
```python
# Vorher:
timestamp = now.isoformat()

# Nachher:
timestamp = now.isoformat() + "+00:00"  # Explicit UTC timezone info
```

### Frontend (dashboard.js)
- JavaScript-Code erkennt die lokale Zeitzone des Benutzers
- Timestamps werden korrekt in die lokale Zeit konvertiert 
- Die Zeit wird in einem benutzerfreundlichen Format angezeigt

## 2. API-Fallback-System

### Multi-API System (trading_bot.py)
- Hierarchisches API-System: CoinGecko → Binance → Simulierte Preise
- Automatische Erkennung von Rate-Limiting und API-Ausfällen
- 15-Minuten-Cooldown bei Erreichen von API-Limits
- Kennzeichnung der aktuellen Datenquelle im Frontend

### Cooldown-Mechanismus
- Wenn eine API nicht verfügbar ist, wird ein Zeitstempel für den nächsten Versuch gesetzt
- Während des Cooldowns werden simulierte Preise mit kleinen Variationen verwendet
- Nach Ablauf des Cooldowns wird automatisch ein neuer API-Versuch gestartet

## 3. Visuelle Status-Anzeige

- Farbcodierter Status-Indikator im Dashboard
  - Grün: Primäre API aktiv (CoinGecko)
  - Gelb: Sekundäre API aktiv (Binance) oder Rate-Limited
  - Rot: Alle APIs nicht verfügbar, Fallback auf simulierte Daten
- Anzeige der verbleibenden Cooldown-Zeit

## 4. Performance-Optimierungen

- Separater Aktualisierungsintervall für Preisdaten (30 Sek.) und Bot-Status (20 Sek.)
- Reduzierte Anzahl der API-Aufrufe durch intelligentes Caching
- Samplingverfahren für Preishistorie je nach angefordertem Zeitraum

## 5. Verbesserte Fehlerbehandlung

- Spezifische Fehlermeldungen je nach API-Status
- Automatisches Wiederherstellen nach API-Fehlern
- Transparentere Benutzeroberfläche mit eindeutiger Kennzeichnung von Datenquellen

## Implementierungsanweisungen:

1. Alle Zeitstempel mit expliziter UTC-Zeitzoneninformation versehen (+00:00)
2. API-Fallback-Mechanismus in trading_bot.py implementieren
3. Status-Indikator im Dashboard hinzufügen
4. Separate Aktualisierungsintervalle für verschiedene Datentypen einrichten
5. Fehlerbehandlung in allen API-Aufrufen verbessern