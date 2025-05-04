import json

# Reset Wallet
with open("wallet_reset.json", "w") as f:
    json.dump({
        "guthaben": 100,
        "bitcoin_bestand": 0.00
    }, f)
    
# Setze Reset-Marker
with open("wallet_reset.lock", "w") as f:
    f.write("reset")

print("✅ Wallet wurde zurückgesetzt.")
print("🧠 Gedächtnis bleibt erhalten. Starte jetzt den Bot, um fortzufahren.")

