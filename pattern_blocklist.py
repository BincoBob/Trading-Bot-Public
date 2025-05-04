import json

# Threshold definieren (ab wann gilt ein Muster als "schlecht")
SCHLECHT_GRENZE = -3

# Dateien
MEMORY_FILE = "memory.json"
BLOCKLIST_FILE = "bad_patterns.json"

# Memory laden
try:
    with open(MEMORY_FILE, "r") as f:
        memory = json.load(f)
except FileNotFoundError:
    print("❌ Es existiert keine memory.json – Bot hat noch nichts gelernt.")
    exit()

# Schlechte Muster extrahieren
bad_patterns = {pattern: score for pattern, score in memory.items() if score <= SCHLECHT_GRENZE}

# Wenn welche gefunden → speichern
if bad_patterns:
    with open(BLOCKLIST_FILE, "w") as f:
        json.dump(bad_patterns, f, indent=4)
    print(f"🧠 {len(bad_patterns)} schlechte Muster gespeichert in {BLOCKLIST_FILE}")
else:
    print("✅ Keine schlechten Muster gefunden – alles im grünen Bereich!")
