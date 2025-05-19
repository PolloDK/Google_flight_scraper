import asyncio
import csv
import os
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm
import re

OUTPUT_CSV = "data/vuelos_gf.csv"
HEADERS = [
    "departure_airport_id",
    "arrival_airport_id",
    "departure_date",
    "departure_time",
    "arrival_time",
    "airline",
    "travel_class",
    "duration_min",
    "price_clp",
    "type",
    "emissions_this_flight",
    "emissions_difference_percent",
    "stops"
]

AIRPORTS = [
    "LHR", "JFK", "CDG", "HND", "LAX", "ORD", "DFW", "DEN", "FRA", "AMS",
    "ATL", "PEK", "DXB", "MAD", "BCN", "GRU", "HKG", "ICN", "SYD", "SIN",
    "YYZ", "SFO", "MEX", "SEA", "MIA", "EZE", "GIG", "BOG", "SCL", "PTY",
    "ZRH", "VIE", "MUC", "BKK", "DEL", "BOM", "MNL", "DOH", "CPH", "OSL",
    "ARN", "HEL", "WAW", "LIS", "BRU", "DUB", "MAN", "FCO", "ORY", "BVA"
]

TRIP_TYPES = ["One way", "Round trip"]
TRAVEL_CLASSES = ["Economy", "Premium economy", "Business", "First"]

async def parsear_vuelo(card, origen, destino, fecha, travel_class, tipo_viaje):
    try:
        times_elem = await card.inner_text()
        if not times_elem:
            raise ValueError("times_elem vacío")
        print("🧾 Texto del vuelo:\n", times_elem)
        if not times_elem:
            raise ValueError("times_elem vacío")

        horas = re.findall(r'\d{1,2}:\d{2}\s?[APMapm]{2}', times_elem)
        horas = list(dict.fromkeys(horas))
        if len(horas) < 2:
            raise ValueError("No se encontraron horarios válidos")
        departure_time, arrival_time = horas[:2]

        airlines_match = re.findall(r'(?:Operated by\s)?([A-Z][a-zA-Z\s]+?)(?=\d{1,2}\s?hr)', times_elem)
        airline = airlines_match[0].strip() if airlines_match else None

        dur_match = re.search(r'(\d{1,2})\s?hr(?:s)?\s?(\d{1,2})?\s?min', times_elem)
        if dur_match:
            h = int(dur_match.group(1))
            m = int(dur_match.group(2)) if dur_match.group(2) else 0
            duration_min = h * 60 + m
        else:
            duration_min = None

        iata = re.findall(r'([A-Z]{3})(?=[A-Z][a-z])', times_elem)
        if len(iata) < 2:
            raise ValueError("No se encontraron códigos IATA")
        departure_airport_id, arrival_airport_id = iata[:2]

        price_clp = None
        price_match = re.search(r'CLP[\s\u00a0]?([\d.,]+)', times_elem)
        if price_match:
            price_str = price_match.group(1).replace(".", "").replace(",", "").strip()
            if price_str.isdigit():
                price_clp = int(price_str)

        emissions_match = re.search(r'(\d{2,4})\s?kg CO2e', times_elem)
        emissions_this_flight = int(emissions_match.group(1)) if emissions_match else None

        diff_match = re.search(r'([+-]\d{1,3})% emissions', times_elem)
        emissions_diff = int(diff_match.group(1)) if diff_match else None

        if "Nonstop" in times_elem:
            stops = "Nonstop"
        else:
            stop_match = re.search(r'(\d+) stop', times_elem)
            stops = f"{stop_match.group(1)} stop" if stop_match else "Desconocido"

        return {
            "departure_airport_id": departure_airport_id,
            "arrival_airport_id": arrival_airport_id,
            "departure_date": fecha,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "airline": airline,
            "travel_class": travel_class,
            "duration_min": duration_min,
            "price_clp": price_clp,
            "type": tipo_viaje,
            "emissions_this_flight": emissions_this_flight,
            "emissions_difference_percent": emissions_diff,
            "stops": stops,
        }

    except Exception as e:
        print(f"⚠️ Error leyendo vuelo: {e}")
        return None

async def scrape_google_flights(n_consultas=1):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context()
        page = await context.new_page()

        for _ in tqdm(range(n_consultas), desc="Consultando Google Flights"):
            origen, destino = random.sample(AIRPORTS, 2)
            tipo_viaje = random.choice(TRIP_TYPES)
            tipo_asiento = random.choice(TRAVEL_CLASSES)
            fecha = (datetime.today() + timedelta(days=random.randint(5, 60))).strftime("%Y-%m-%d")
            url = f"https://www.google.com/travel/flights?q=flights+from+{origen}+to+{destino}+on+{fecha}"

            print(f"\n🌍 Buscando vuelos: {origen} → {destino} en {fecha}")
            print(f"🔗 URL: {url}")

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div[role='main']", timeout=15000)

            # === Selección de tipo de viaje (One way / Round trip) ===
            try:
                trip_selector = "div[aria-label='Select trip type']"
                await page.wait_for_selector(trip_selector, timeout=10000)
                await page.click(trip_selector)
                await page.wait_for_timeout(500)  # pequeña espera tras abrir menú

                # Selecciona opción según valor en inglés: "Round trip", "One way", etc.
                await page.locator(f"li[role='option']:has-text('{tipo_viaje}')").click()
                print(f"🧭 Tipo de viaje seleccionado: {tipo_viaje}")
            except Exception as e:
                print(f"⚠️ No se pudo seleccionar tipo de viaje: {e}")

            # === Selección de clase de asiento ===
            try:
                seat_selector = "div[aria-label='Select cabin class']"
                await page.wait_for_selector(seat_selector, timeout=10000)
                await page.click(seat_selector)
                await page.wait_for_timeout(500)

                await page.locator(f"li[role='option']:has-text('{tipo_asiento}')").click()
                print(f"💺 Clase seleccionada: {tipo_asiento}")
            except Exception as e:
                print(f"⚠️ No se pudo seleccionar clase: {e}")

                
            while True:
                try:
                    more_button = page.locator("text=Ver más vuelos").last
                    if await more_button.is_visible():
                        print("🔁 Clic en 'Ver más vuelos'")
                        await more_button.click()
                        await page.wait_for_timeout(4000)
                    else:
                        break
                except:
                    break

            cards = page.locator("div.yR1fYc")
            total = await cards.count()
            print(f"✈️ {total} resultados encontrados")

            vuelos = []
            for i in range(total):
                card = cards.nth(i)
                vuelo = await parsear_vuelo(card, origen, destino, fecha, tipo_asiento, tipo_viaje)
                if vuelo:
                    vuelos.append(vuelo)

            if vuelos:
                existe = os.path.exists(OUTPUT_CSV)
                with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=HEADERS)
                    if not existe:
                        writer.writeheader()
                    writer.writerows(vuelos)
                print(f"✅ {len(vuelos)} vuelos guardados en {OUTPUT_CSV}")
            else:
                print("⚠️ No se guardaron vuelos.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_google_flights(n_consultas=1))
