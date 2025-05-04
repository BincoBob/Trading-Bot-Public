import json
from tabulate import tabulate

# Datei einlesen
try:
    with open("memory.json", "r") as f:
        memory = json.load(f)
except FileNotFoundError:
    print("❌ Keine memory.json gefunden – der Bot hat noch nichts gelernt.")
    exit()

# Liste vorbereiten
muster_liste = [[key, score] for key, score in memory.items()]
muster_liste.sort(key=lambda x: x[1], reverse=True)  # Nach Score sortieren

# Ausgabe
print("\n🧠 Gelernte Muster:")
print(tabulate(muster_liste, headers=["Muster", "Score"], tablefmt="pretty"))
