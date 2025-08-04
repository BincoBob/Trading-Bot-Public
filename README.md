# KI-Trading-Bot (Crypto / MEXC / Python)

## 🧠 Projektbeschreibung

Dieses Projekt ist ein vollständig automatisierter Trading-Bot für Kryptowährungen mit Fokus auf Bitcoin und dynamisch ausgewählten Altcoins.  
Der Bot nutzt Live-Marktdaten, trifft Kauf-/Verkaufsentscheidungen und verwaltet ein echtes Wallet über die MEXC API.

> ⚠️ **Work in Progress**: Das Projekt wird laufend weiterentwickelt und optimiert.

---

## 🚀 Features

- ✅ Live-Preisabfrage über CoinGecko API
- ✅ Dynamische Kauf-/Verkaufslogik
- ✅ Integration mit echter Wallet über MEXC API
- ✅ Gewinnüberwachung & Verkaufsregel
- ✅ Coin-Scanner: Auswahl der Top-Coins
- ✅ Blacklist-System für ungünstige Coins
- ✅ Live-Deployment auf AWS (EC2)
- 🧠 Einfaches Belohnung/Strafe-System zur Strategieverbesserung
- 🌐 Frontend (HTML/CSS/JS) unter `/templates` enthalten

---

## 🔍 Coin-Scanner (scanner.py)

Die `scanner.py` (bzw. `smart_selector.py`) enthält die dynamische Auswahl-Logik für Coins, basierend auf Markttrends und Toplisten-Ranking.  
Funktionen:
- Erkennt automatisch neue Top-Coins
- Entfernt Coins, die nicht mehr in der Liste sind
- Verhindert Re-Einstieg bei Verlust durch Blacklisting
- Berücksichtigt nur Verkauf bei realem Gewinn

Diese Logik bildet die Grundlage für strategisches, automatisiertes Handeln und ist später auch in KI-Logik integrierbar.

---

## 🔧 Technischer Stack

- **Sprache:** Python  
- **APIs:** CoinGecko, MEXC  
- **Cloud:** AWS EC2  
- **Logging:** JSON, TXT  
- **KI-Ansatz:** Einfaches Reinforcement Learning  
- **Frontend:** HTML / CSS / JavaScript

---

## 📂 Projektstruktur (Auszug)

bitcoin-trading-bot/
├── main.py
├── trading_bot.py
├── brain.py
├── smart_selector.py
├── scanner.py
├── config_example.json
├── templates/
│ ├── index.html
│ ├── style.css
│ └── script.js
├── .gitignore
├── README.md
└── requirements.txt

---

## 📈 Ziel

> Das Projekt dient als praxisnaher Einstieg in automatisiertes Trading mit KI-Unterstützung.  
> Ziel ist eine eigenständig agierende, lernfähige Bot-Logik mit stabiler Live-Integration und modularer Erweiterbarkeit.

---

## 👤 Autor

**Nicolas Hoffmann (aka BincoBob)**  
Quereinsteiger im Bereich KI, Automatisierung & Softwareentwicklung  
Berlin, Deutschland
