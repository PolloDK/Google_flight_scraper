import requests
import random
import os
import json
import csv
from datetime import datetime, timedelta

# === CONFIG ===
API_KEY = "daf23758d899bf2b18aac86130a12308cb4bb1306fa75cfc38fafa0ede3b8ddc"
OUTPUT_JSON = "data/ultima_respuesta.json"
OUTPUT_CSV = "data/vuelos.csv"
AIRPORTS = ["JFK", "LAX", "CDG", "SCL", "LHR", "MAD", "MEX", "GRU", "FRA", "AMS", "PTY", "EZE", "YYZ", "MIA", "ORD"]

# Crear carpeta
os.makedirs("data", exist_ok=True)

# Columnas completas
HEADERS = [
    "departure_airport_id", "departure_airport_name", "departure_time",
    "arrival_airport_id", "arrival_airport_name", "arrival_time",
    "airline", "flight_number", "airplane", "travel_class", "duration_min",
    "legroom", "overnight", "extensions_flight", "index_tramo",
    "total_duration", "layovers", "price_usd", "type",
    "extensions_group", "emissions_this_flight", "emissions_typical_route",
    "emissions_difference_percent", "booking_token", "departure_date"
]

def prueba_consulta_serpapi(n_consultas):
    from tqdm import tqdm

    archivo_nuevo = not os.path.exists(OUTPUT_CSV)
    existentes = set()
    if not archivo_nuevo:
        with open(OUTPUT_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if all(k in row for k in ["flight_number", "departure_date", "index_tramo"]):
                    existentes.add((row["flight_number"], row["departure_date"], row["index_tramo"]))

    nuevos = []

    for _ in tqdm(range(n_consultas), desc="Consultas a SerpAPI"):
        origin, destination = random.sample(AIRPORTS, 2)
        date = datetime.today() + timedelta(days=random.randint(1, 60))
        date_str = date.strftime("%Y-%m-%d")

        print(f"\n🔍 Consulta: {origin} → {destination} en {date_str}")

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": date_str,
            "type": "2",
            "max_flights": "100",
            "hl": "en",
            "api_key": API_KEY
        }

        response = requests.get("https://serpapi.com/search", params=params)
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            continue

        data = response.json()

        # Guardar el último JSON por si se quiere inspeccionar
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        vuelos = data.get("best_flights", []) + data.get("other_flights", [])
        print(f"✅ {len(vuelos)} grupos de vuelos encontrados")

        for grupo in vuelos:
            layovers = grupo.get("layovers", [])
            layovers_str = "; ".join([f"{l['id']} ({l['duration']}min)" for l in layovers])
            extensions_group = "; ".join(grupo.get("extensions", []))

            for idx, tramo in enumerate(grupo.get("flights", [])):
                dep_time = tramo.get("departure_airport", {}).get("time")
                if not dep_time:
                    continue

                dep_date = dep_time.split(" ")[0]
                clave = (tramo.get("flight_number"), dep_date, str(idx))
                if clave in existentes:
                    continue

                registro = {
                    "departure_airport_id": tramo.get("departure_airport", {}).get("id"),
                    "departure_airport_name": tramo.get("departure_airport", {}).get("name"),
                    "departure_time": tramo.get("departure_airport", {}).get("time"),
                    "arrival_airport_id": tramo.get("arrival_airport", {}).get("id"),
                    "arrival_airport_name": tramo.get("arrival_airport", {}).get("name"),
                    "arrival_time": tramo.get("arrival_airport", {}).get("time"),
                    "airline": tramo.get("airline"),
                    "flight_number": tramo.get("flight_number"),
                    "airplane": tramo.get("airplane"),
                    "travel_class": tramo.get("travel_class"),
                    "duration_min": tramo.get("duration"),
                    "legroom": tramo.get("legroom"),
                    "overnight": tramo.get("overnight", False),
                    "extensions_flight": "; ".join(tramo.get("extensions", [])),
                    "index_tramo": str(idx),
                    "total_duration": grupo.get("total_duration"),
                    "layovers": layovers_str,
                    "price_usd": grupo.get("price"),
                    "type": grupo.get("type"),
                    "extensions_group": extensions_group,
                    "emissions_this_flight": grupo.get("carbon_emissions", {}).get("this_flight"),
                    "emissions_typical_route": grupo.get("carbon_emissions", {}).get("typical_for_this_route"),
                    "emissions_difference_percent": grupo.get("carbon_emissions", {}).get("difference_percent"),
                    "booking_token": grupo.get("booking_token"),
                    "departure_date": dep_date
                }

                nuevos.append(registro)
                existentes.add(clave)

    if nuevos:
        with open(OUTPUT_CSV, "a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=nuevos[0].keys())
            if archivo_nuevo:
                writer.writeheader()
            writer.writerows(nuevos)
        print(f"\n✅ Se guardaron {len(nuevos)} nuevos tramos de vuelo en {OUTPUT_CSV}")
    else:
        print("\n⚠️ No se encontraron vuelos nuevos para guardar.")

# === EJECUCIÓN ===
if __name__ == "__main__":
    prueba_consulta_serpapi(n_consultas=2)
    #scrape_vuelos(n_consultas=100)  # Puedes cambiar este número
