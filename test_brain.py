from brain import load_memory, evaluate_trade, get_score_for_pattern

# Gehirn laden
load_memory()

# Beispiel-Trade bewerten
evaluate_trade({
    "rsi": 25,
    "price_direction": "down",
    "profit": 4.0
})

# Gelernte Bewertung abfragen
score = get_score_for_pattern({
    "rsi": 25,
    "price_direction": "down"
})

print(f"Gelernter Score: {score}")
