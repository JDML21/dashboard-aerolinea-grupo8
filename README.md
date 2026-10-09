# Dashboard de operación y experiencia del pasajero

Proyecto final 2026-2 · Herramientas de Visualización para la Inteligencia de Negocios · Maestría en Analítica
**Grupo 8:** Aerolínea de operación nacional y regional

Dashboard interactivo en Streamlit para la **Gerencia de Operaciones y Experiencia del Pasajero**. Responde tres preguntas de negocio:

1. ¿La baja puntualidad es un problema localizado (rutas, franjas, aeropuertos) o de toda la operación, y qué causas explican las irregularidades?
2. ¿Cuánto cae la satisfacción según los minutos de retraso y el tipo de irregularidad, y a partir de qué umbral se vuelve crítica?
3. ¿Dónde se concentran los ingresos (rutas, tarifas y canales) y cuánto de ese ingreso está expuesto a la impuntualidad?

## KPI

Puntualidad (retraso ≤ 15 min) · Tasa de cancelación · % de vuelos con irregularidad · Calificación promedio · Ingresos totales · Ocupación promedio

## Estructura

| Archivo | Contenido |
|---|---|
| `08_aerolinea_regional.csv` | Dataset original asignado (55.000 segmentos de vuelo, 2024-01 a 2026-09) |
| `08_aerolinea_regional_limpio.csv` | Versión procesada en una sola tabla |
| `modelo/` | Versión procesada en esquema estrella: `fact_vuelos` + 6 dimensiones (fuente de la app) |
| `preparacion_datos.py` | Limpieza, variables derivadas y construcción del modelo |
| `registro_limpieza.txt` | Decisiones de limpieza y su impacto |
| `app.py` | Aplicación Streamlit |

## Ejecución local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python preparacion_datos.py   # opcional: regenera modelo/ y el CSV limpio
.venv/bin/streamlit run app.py
```

Los datos son sintéticos y anonimizados.
