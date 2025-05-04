from extensions import db
import json
import os

# Das ist unser Gedächtnis – hier merkt sich der Bot, was gut/schlecht war
memory = {}

MEMORY_FILE = "memory.json"

# Speicher aus Datei laden (falls vorhanden)
def load_memory():
    global memory
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    else:
        memory = {}

# Speicher in Datei schreiben
def save_memory():
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

# Aus einem Trade (z. B. RSI + Kursrichtung) ein erkennbares Muster bauen
def extract_pattern(trade_data):
    rsi = trade_data.get("rsi")
    direction = trade_data.get("price_direction")
    return f"RSI<{rsi}_Price_{direction}"

# Lernen: War der Trade gut oder schlecht?
def evaluate_trade(trade_data):
    pattern = extract_pattern(trade_data)
    profit = trade_data.get("profit", 0)

    if pattern not in memory:
        memory[pattern] = 0

    memory[pattern] += 1 if profit > 0 else -1
    save_memory()

# Gibt zurück, ob ein Muster in der Vergangenheit gut war
def get_score_for_pattern(trade_data):
    pattern = extract_pattern(trade_data)
    return memory.get(pattern, 0)
