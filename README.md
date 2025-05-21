# Google Flights Scraper ✈️

Este scraper automatiza la extracción de vuelos desde [Google Flights](https://www.google.com/travel/flights) usando Playwright.

## 📦 Características
- Selección aleatoria de aeropuertos de origen y destino
- Soporte para viajes **One way** y **Round trip**
- Selección de clase aleatoria: Economy, Premium economy, Business, First
- Selección de fechas aleatorias dentro de los próximos 60 días
- Extracción detallada de:
  - Horarios de salida y llegada
  - Aerolínea(s)
  - Duración del vuelo
  - Precio en CLP
  - Emisiones de CO2 y comparación porcentual
  - Número de escalas
- Guardado en archivo CSV (`data/vuelos_gf.csv`)
- Apto para scraping de múltiples vuelos por ejecución

## ▶️ Cómo usar

### 1. Clonar el repositorio
```bash
git clone https://github.com/tuusuario/google-flights-scraper.git
cd google-flights-scraper
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
playwright install
```

### 3. Ejecutar
```bash
python src/scrape_flights.py
```

## 🧪 Estructura esperada de datos
```
departure_airport_id,departure_airport_name,arrival_airport_id,arrival_airport_name,departure_date,
departure_time,arrival_time,airline,travel_class,duration_min,price_clp,type,emissions_this_flight,
emissions_difference_percent,stops
```

## 🗂 Estructura del proyecto
```
google-flights-scraper/
├── data/                    # CSVs generados
├── src/                     # Código fuente
│   ├── manual_flight_scraper.py    # Script principal
├── requirements.txt
├── .gitignore
├── README.md
└── LICENSE
```
