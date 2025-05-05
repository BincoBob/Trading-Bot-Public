# smart_selector.py
import json
import random

def generate_smart_top_5():
    # Simulierte Auswahl – später ersetzt du das durch echte Analyse
    all_candidates = [
        "DOGEUSDT", "SHIBUSDT", "FLOKIUSDT", "XECUSDT", "BONKUSDT",
        "PEPEUSDT", "SATSUSDT", "LUNCUSDT", "AMPUSDT", "VRAUSDT"
    ]
    top5 = random.sample(all_candidates, 5)  # Zufällige Auswahl als Platzhalter

    with open("smart_top.json", "w") as f:
        json.dump(top5, f)

    print("✅ Top 5 Coins gespeichert:", top5)

if __name__ == "__main__":
    generate_smart_top_5()
