import asyncio
import csv
import os
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm
import re
from dataclasses import dataclass
from datetime import date

OUTPUT_CSV = "data/vuelos_gf.csv"
HEADERS = [
    "consulta_fecha",
    "dias_anticipacion",
    "departure_airport_id",
    "departure_airport_name",
    "arrival_airport_id",
    "arrival_airport_name",
    "departure_date",
    "departure_time",
    "arrival_time",
    "airline_1", "airline_2", "airline_3", "airline_4",
    "operator_1", "operator_2", "operator_3", "operator_4",
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
CABIN_CLASSES = ["Economy", "Premium Economy", "Business", "First"]

@dataclass
class SearchParameters:
    departure: str
    destination: str
    departure_date: str
    return_date: str 
    ticket_type: str
    cabin_class: str

async def _fill_search_form(page, params: SearchParameters):
    """
    Esta función llena el formulario de búsqueda de vuelos en Google Flights con
    las opciones de búsqueda proporcionadas en el objeto params.
    Parameters:
        page: La página de Playwright donde se encuentra el formulario.
        params: Un objeto SearchParameters que contiene:
            - departure: Ciudad de origen.
            - destination: Ciudad de destino.
            - departure_date: Fecha de salida (formato YYYY-MM-DD).
            - return_date: Fecha de regreso (formato YYYY-MM-DD).
            - ticket_type: Tipo de viaje (One way o Round trip).
            - cabin_class: Clase de cabina (Economy, Premium Economy, Business, First).
    """
    print(f"✈️ Buscando vuelos de {params.departure} a {params.destination} el {params.departure_date}. Con tipo de viaje: {params.ticket_type} y clase: {params.cabin_class}")
    
    # === Selecciona tipo de viaje ===
    ticket_type_div = page.locator("div.VfPpkd-TkwUic[jsname='oYxtQd']").first
    await ticket_type_div.click()
    await page.wait_for_selector("ul[aria-label='Select your ticket type.']")
    await page.locator("li").filter(has_text=params.ticket_type).nth(0).click()
    await page.wait_for_timeout(500)
    await page.keyboard.press("Tab")
    await page.keyboard.press("Tab")
    
    # === Selecciona tipo de asiento ===
    focused_element = page.locator(":focus")
    await focused_element.click()
    await page.wait_for_timeout(500)
    cabin_option = page.locator("ul[role='listbox'] li").filter(has_text=params.cabin_class)
    await cabin_option.first.click()
    print(f"✅ Clase seleccionada: {params.cabin_class}")

    # === Selecciona ciudad de origen ===
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(params.departure, delay=100)
    await page.wait_for_timeout(1000)
    await page.keyboard.press("ArrowDown")
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(800)
    await page.keyboard.press("Tab")

    # === Selecciona ciudad de destino ===
    await page.keyboard.type(params.destination, delay=100)
    await page.wait_for_timeout(1000)
    await page.keyboard.press("ArrowDown")
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(1500)
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(800)
    
    # === Selecciona fechas de ida y vuelta (si corresponde)===
    focused_element = page.locator(":focus")
    await focused_element.click()
    
    if params.ticket_type == "One way":
        await page.keyboard.type(params.departure_date)
        await page.keyboard.press("Enter")
    else:
        await page.keyboard.type(params.departure_date)
        await page.keyboard.press("Tab")
        focused_element = page.locator(":focus")
        await focused_element.click()
        await page.keyboard.type(params.return_date)
        await page.keyboard.press("Enter")
    await page.keyboard.press("Tab")
    await page.keyboard.press("Tab")
    await page.keyboard.press("Enter")

def extract_airlines_and_operators(text):
    """
    Esta función extrae las aerolíneas y operadores de un texto dado.
    Parameters:
        text: El texto que contiene la información de las aerolíneas y operadores.
    Returns:
        Una lista de tuplas que contienen el nombre de la aerolínea y el operador (si está disponible).
    """
    known_airlines = sorted([
        "Air France", "Air Canada", "American", "Alaska", "British Airways", "Cathay Pacific", "China Airlines",
        "China Eastern", "COPA", "Delta", "Emirates", "EVA Air", "Finnair", "Iberia", "Icelandair", "JAL",
        "Jetstar", "KLM", "Korean Air", "Lufthansa", "Malaysia Airlines", "Philippine Airlines", "Qantas",
        "Qatar Airways", "Royal Air Maroc", "Royal Jordanian", "Scoot", "Singapore Airlines", "SWISS",
        "T'Way Air", "Turkish Airlines", "United", "Virgin Australia", "AirAsia", "AirAsia X", "Asiana Airlines",
        "ANA", "Austrian", "Condor", "Batik Air", "Envoy Air", "BA Cityflyer", "KLM Cityhopper", "Horizon Air",
        "HOP!", "Shanghai Airlines", "THAI", "Etihad", "ITA", "Helvetic", "Gulf Air", "WestJet", "Ethiopian",
        "Air Europa", "Pegasus", "Scandinavian Airlines", "Brussels Airlines", "Aeromexico", "Air China", "Frontier",
        "Southwest", "Air India", "LATAM", "Tap Air Portugal", "Avianca", "LOT", "Shenzhen", "Virgin Atlantic",
        "Vueling", "SAS", "Alitalia", "Aegean Airlines", "Air Serbia", "Air Malta", "Croatia Airlines",
        "Bulgaria Air", "LOT Polish Airlines", "S7 Airlines", "Nordwind Airlines", "Ural Airlines", "Azul",
        "Gol", "Viva Aerobus", "Volaris", "Interjet"
    ], key=lambda x: len(x.replace(" ", "")), reverse=True)

    text_no_spaces = text.replace(" ", "").replace(",", "")
    airline_matches = []
    for airline in known_airlines:
        if airline in text or airline.replace(" ", "") in text_no_spaces:
            airline_matches.append(airline)

    operator_matches = re.findall(r"Operated by ([\w\s!&.'\-]+?)(?=\s(?:for|as|by|with|$)|\d|\()", text, flags=re.IGNORECASE)
    operators = [op.strip() for op in operator_matches if op.strip()]

    airline_operator_pairs = []
    for i, airline in enumerate(airline_matches):
        operator = operators[i] if i < len(operators) else None
        airline_operator_pairs.append((airline, operator))

    return airline_operator_pairs

    
async def parsear_vuelo(card, origen, destino, fecha, travel_class, tipo_viaje):
    """
    Esta función extrae información de un vuelo a partir de un elemento de tarjeta de vuelo.
    Parameters:
        card: El elemento de tarjeta de vuelo que contiene la información del vuelo.
        origen: Ciudad de origen.
        destino: Ciudad de destino.
        fecha: Fecha de salida (formato YYYY-MM-DD).
        travel_class: Clase de cabina seleccionada.
        tipo_viaje: Tipo de viaje (One way o Round trip).
    """
    try:
        times_elem = await card.text_content()
        print("🧾 Texto del vuelo:\n", times_elem)
        if not times_elem:
            raise ValueError("times_elem vacío")

        # === Fecha ===
        consulta_fecha = date.today().strftime("%Y-%m-%d")
        dias_anticipacion = (datetime.strptime(fecha, "%Y-%m-%d").date() - date.today()).days
        
        # === Horas
        horas = re.findall(r'\d{1,2}:\d{2}\s?[APMapm]{2}', times_elem)
        horas = list(dict.fromkeys(horas))
        if len(horas) < 2:
            raise ValueError("No se encontraron horarios válidos")
        departure_time, arrival_time = horas[:2]

        # === Aerolínea(s) ===
        airline_operator_pairs = extract_airlines_and_operators(times_elem)

        airlines = [pair[0] for pair in airline_operator_pairs]
        operators = [pair[1] for pair in airline_operator_pairs]

        # Ajustar longitud
        while len(airlines) < 4:
            airlines.append(None)
        while len(operators) < 4:
            operators.append(None)
        print("🛫 Aerolíneas:", airlines)
        print("🤝 Operadas por:", operators)

        # === Duración
        dur_match = re.search(r'(\d{1,2})\s?hr(?:s)?\s?(\d{1,2})?\s?min', times_elem)
        if dur_match:
            h = int(dur_match.group(1))
            m = int(dur_match.group(2)) if dur_match.group(2) else 0
            duration_min = h * 60 + m
        else:
            duration_min = None

        # === Códigos IATA y nombres de aeropuerto (mejor extracción)
        iata_and_names = re.findall(r'([A-Z]{3})([A-Za-z\s\-\'./()]+?(?:Airport|Aeropuerto|lufthavn))', times_elem)

        if len(iata_and_names) < 2:
            print("⚠️ No se encontraron aeropuertos completos, continuando con None")
            return None

        (departure_airport_id, departure_airport_name), (arrival_airport_id, arrival_airport_name) = iata_and_names[:2]
        departure_airport_name = departure_airport_name.strip()
        arrival_airport_name = arrival_airport_name.strip()

        # === Precio
        price_clp = None
        price_match = re.search(r'CLP[\s\u00a0]?([\d.,]+)', times_elem)
        if price_match:
            price_str = price_match.group(1).replace(".", "").replace(",", "").strip()
            if price_str.isdigit():
                price_clp = int(price_str)

        # === Emisiones
        emissions_match = re.search(r'(\d{2,4})\s?kg CO2e', times_elem)
        emissions_this_flight = int(emissions_match.group(1)) if emissions_match else None

        diff_match = re.search(r'([+-]\d{1,3})% emissions', times_elem)
        emissions_diff = int(diff_match.group(1)) if diff_match else None

        # === Escalas
        if "Nonstop" in times_elem:
            stops = "Nonstop"
        else:
            stop_match = re.search(r'(\d+) stop', times_elem)
            stops = f"{stop_match.group(1)} stop" if stop_match else "Desconocido"

        return {
            "consulta_fecha": consulta_fecha,
            "dias_anticipacion": dias_anticipacion,
            "departure_airport_id": departure_airport_id,
            "departure_airport_name": departure_airport_name,
            "arrival_airport_id": arrival_airport_id,
            "arrival_airport_name": arrival_airport_name,
            "departure_date": fecha,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "airline_1": airlines[0], "airline_2": airlines[1], "airline_3": airlines[2], "airline_4": airlines[3],
            "operator_1": operators[0], "operator_2": operators[1], "operator_3": operators[2], "operator_4": operators[3],
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
    """
    Esta función realiza la búsqueda de vuelos en Google Flights utilizando Playwright.
    Parameters:
        n_consultas: Número de consultas a realizar.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=200)
        context = await browser.new_context()
        page = await context.new_page()

        for _ in tqdm(range(n_consultas), desc="Consultando Google Flights"):
            origen, destino = random.sample(AIRPORTS, 2)
            departure_date = datetime.today() + timedelta(days=random.randint(5, 60))
            return_date = departure_date + timedelta(days=random.randint(3, 14))  # retorno 3 a 14 días después

            params = SearchParameters(
                departure=origen,
                destination=destino,
                departure_date=departure_date.strftime("%Y-%m-%d"),
                return_date=return_date.strftime("%Y-%m-%d"), 
                ticket_type=random.choice(TRIP_TYPES),
                cabin_class=random.choice(CABIN_CLASSES)
            )

            await page.goto("https://www.google.com/travel/flights", timeout=60000)
            await page.wait_for_timeout(3000)
            await _fill_search_form(page, params)
            await page.wait_for_timeout(5000)

            cards = page.locator("div.yR1fYc")
            total = await cards.count()
            print(f"✈️ {total} resultados encontrados")

            vuelos = []
            for i in range(total):
                card = cards.nth(i)
                vuelo = await parsear_vuelo(card, params.departure, params.destination, params.departure_date, params.cabin_class, params.ticket_type)
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
    asyncio.run(scrape_google_flights(n_consultas=100))
