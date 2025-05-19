import requests
import os
import csv
import random
import time
from datetime import datetime, timedelta
from tqdm import tqdm

# === CONFIGURACIÓN ===
AMADEUS_CLIENT_ID = "ItFhzyqprytaUw9bz5Kclz2XhG9Wupp5"
AMADEUS_CLIENT_SECRET = "bFKPZwviYxiILvsu"
GOOGLE_API_KEY = "AIzaSyCXxVeDtWcmMB0Qq9Tb4ytpTtYpZDWd4Dc"

OUTPUT_CSV = "data/vuelos_amadeus.csv"
os.makedirs("data", exist_ok=True)

HEADERS = [
    "departure_iata", "arrival_iata", "departure_time", "arrival_time",
    "duration", "carrier", "flight_number", "class", "aircraft",
    "emissions_economy_kg", "emissions_business_kg", "emissions_first_kg",
    "departure_date"
]

AIRPORTS = ["MAD", "NYC", "LON", "CDG"]

# === FUNCIÓN: Obtener token de Amadeus ===
def get_amadeus_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# === FUNCIÓN: Consultar vuelos Amadeus ===
def get_flight_offers(token, origin, destination, date_str):
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": date_str,
        "adults": 1,
        "nonStop": False,
        "max": 10,
        "currencyCode": "USD"
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    return r.json().get("data", [])

# === FUNCIÓN: Consultar emisiones Google TIM ===
def get_emissions(carrier, flight_number, origin, destination, departure_date):
    url = f"https://travelimpactmodel.googleapis.com/v1/flights:computeFlightEmissions?key={GOOGLE_API_KEY}"
    payload = {
        "flights": [{
            "origin": origin,
            "destination": destination,
            "operatingCarrierCode": carrier,
            "flightNumber": flight_number,
            "departureDate": departure_date
        }]
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        return None
    data = r.json().get("flightEmissions", [])[0]["emissionsGramsPerPax"]
    return {
        "economy": round(data.get("economy", 0) / 1000, 2),
        "business": round(data.get("business", 0) / 1000, 2),
        "first": round(data.get("first", 0) / 1000, 2)
    }

# === FUNCIÓN PRINCIPAL ===
def scrape_amadeus(n_consultas=5):
    archivo_nuevo = not os.path.exists(OUTPUT_CSV)
    existentes = set()

    if not archivo_nuevo:
        with open(OUTPUT_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existentes.add((row["flight_number"], row["departure_date"]))

    token = get_amadeus_token()
    print("🔐 Token Amadeus obtenido")

    nuevos = []

    for _ in tqdm(range(n_consultas), desc="Consultando Amadeus"):
        origin, destination = random.sample(AIRPORTS, 2)
        date = datetime.today() + timedelta(days=random.randint(1, 60))
        date_str = date.strftime("%Y-%m-%d")

        try:
            flights = get_flight_offers(token, origin, destination, date_str)
        except Exception as e:
            print(f"⚠️ Error Amadeus: {e}")
            continue

        for offer in flights:
            for segment in offer["itineraries"][0]["segments"]:
                carrier = segment["carrierCode"]
                flight_number = segment["number"]
                dep_iata = segment["departure"]["iataCode"]
                arr_iata = segment["arrival"]["iataCode"]
                dep_time = segment["departure"]["at"]
                arr_time = segment["arrival"]["at"]
                aircraft = segment.get("aircraft", {}).get("code")
                travel_class = offer["travelerPricings"][0]["fareDetailsBySegment"][0]["cabin"]

                key = (flight_number, date_str)
                if key in existentes:
                    continue

                emissions = get_emissions(carrier, flight_number, dep_iata, arr_iata, date_str)
                if not emissions:
                    continue

                registro = {
                    "departure_iata": dep_iata,
                    "arrival_iata": arr_iata,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "duration": segment["duration"],
                    "carrier": carrier,
                    "flight_number": flight_number,
                    "class": travel_class,
                    "aircraft": aircraft,
                    "emissions_economy_kg": emissions["economy"],
                    "emissions_business_kg": emissions["business"],
                    "emissions_first_kg": emissions["first"],
                    "departure_date": date_str
                }
                nuevos.append(registro)
                existentes.add(key)

        time.sleep(1)

    if nuevos:
        with open(OUTPUT_CSV, "a", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            if archivo_nuevo:
                writer.writeheader()
            writer.writerows(nuevos)
        print(f"\n✅ {len(nuevos)} vuelos guardados en {OUTPUT_CSV}")
    else:
        print("\n⚠️ No se guardaron nuevos vuelos.")

# Ejecutar
if __name__ == "__main__":
    scrape_amadeus(n_consultas=10)
