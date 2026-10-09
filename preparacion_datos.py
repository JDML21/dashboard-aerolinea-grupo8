"""
Preparación de datos - Grupo 8: Aerolínea de operación nacional y regional.

Entrada:  08_aerolinea_regional.csv
Salida:   08_aerolinea_regional_limpio.csv  (versión procesada en una sola tabla)
          modelo/  (esquema estrella: fact_vuelos + dimensiones)
          registro_limpieza.txt  (decisiones tomadas y su impacto)
"""

from pathlib import Path

import numpy as np
import pandas as pd

CARPETA = Path(__file__).parent
ARCHIVO_ORIGINAL = CARPETA / "08_aerolinea_regional.csv"
ARCHIVO_LIMPIO = CARPETA / "08_aerolinea_regional_limpio.csv"
ARCHIVO_REGISTRO = CARPETA / "registro_limpieza.txt"
CARPETA_MODELO = CARPETA / "modelo"

UMBRAL_PUNTUALIDAD_MIN = 15  # estándar de la industria aérea

registro = []


def log(texto=""):
    print(texto)
    registro.append(texto)


# 1. Carga y perfilamiento inicial
df = pd.read_csv(ARCHIVO_ORIGINAL)

log("=== 1. PERFILAMIENTO INICIAL ===")
log(f"Registros: {len(df):,} | Columnas: {df.shape[1]}")
log("Unidad de observación: un segmento de vuelo vendido (id_segmento_vuelo único).")
log(f"IDs duplicados: {df['id_segmento_vuelo'].duplicated().sum()}")
log(f"Filas duplicadas (sin ID): {df.drop(columns='id_segmento_vuelo').duplicated().sum()}")
log(f"Vuelos con origen = destino: {(df['origen'] == df['destino']).sum()}")
log("Valores faltantes por columna:")
for col, n in df.isna().sum().items():
    if n > 0:
        log(f"  - {col}: {n:,} ({n / len(df):.1%})")
log()

# 2. Tipado
log("=== 2. TIPADO ===")
df["fecha_vuelo"] = pd.to_datetime(df["fecha_vuelo"], format="%Y-%m-%d")
log(f"fecha_vuelo -> datetime. Rango: {df['fecha_vuelo'].min().date()} a {df['fecha_vuelo'].max().date()}")

columnas_si_no = ["vuelo_cancelado", "equipaje_facturado", "conexion", "cliente_frecuente"]
for col in columnas_si_no:
    df[col] = df[col].map({"Sí": True, "No": False})
log(f"Sí/No -> booleano: {', '.join(columnas_si_no)}")

for col in ["origen", "destino", "franja_salida", "tarifa", "canal_venta"]:
    df[col] = df[col].astype("category")
log()

# 3. Tratamiento de faltantes
log("=== 3. VALORES FALTANTES ===")
n_motivo = df["motivo_irregularidad"].isna().sum()
df["motivo_irregularidad"] = df["motivo_irregularidad"].fillna("Sin irregularidad")
log(f"motivo_irregularidad: {n_motivo:,} vacíos -> 'Sin irregularidad'.")
log("  Justificación: el motivo solo se registra en vuelos cancelados o con retraso > 60 min;")
log("  el vacío indica ausencia de irregularidad, no un dato perdido.")

n_calif = df["calificacion_1a5"].isna().sum()
log(f"calificacion_1a5: {n_calif:,} vacíos se conservan como nulos (no se imputan).")
log("  Justificación: imputar inventaría opiniones de pasajeros; los promedios de")
log("  satisfacción se calculan solo con calificaciones registradas.")
log()

# 4. Inconsistencias
log("=== 4. INCONSISTENCIAS ===")
cancelados_con_retraso = df["vuelo_cancelado"] & (df["retraso_salida_min"] > 0)
log(f"Vuelos cancelados con retraso registrado: {cancelados_con_retraso.sum():,} de {df['vuelo_cancelado'].sum():,} cancelados.")
df["retraso_salida_min"] = df["retraso_salida_min"].astype("float")
df.loc[df["vuelo_cancelado"], "retraso_salida_min"] = np.nan
log("  Decisión: retraso -> nulo en todos los cancelados (un vuelo que no operó no tiene")
log("  retraso de salida). Así no distorsionan puntualidad ni retraso promedio.")

fuera_rango = {
    "ocupacion_pct (0-100)": (~df["ocupacion_pct"].between(0, 100)).sum(),
    "calificacion_1a5 (1-5)": (~df["calificacion_1a5"].dropna().between(1, 5)).sum(),
    "precio_tiquete_cop (> 0)": (df["precio_tiquete_cop"] <= 0).sum(),
    "retraso_salida_min (>= 0)": (df["retraso_salida_min"].dropna() < 0).sum(),
}
for regla, n in fuera_rango.items():
    log(f"Valores fuera de rango en {regla}: {n}")
log()

# 5. Atípicos de precio
log("=== 5. ATÍPICOS DE PRECIO ===")
q1, q3 = df["precio_tiquete_cop"].quantile([0.25, 0.75])
limite = q3 + 1.5 * (q3 - q1)
atipicos = df["precio_tiquete_cop"] > limite
log(f"Atípicos por IQR global (precio > {limite:,.0f}): {atipicos.sum():,}")
log("Distribución de atípicos por tarifa:")
for tarifa, n in df.loc[atipicos, "tarifa"].value_counts().items():
    log(f"  - {tarifa}: {n:,}")
log("Precio promedio por tarifa:")
for tarifa, p in df.groupby("tarifa", observed=True)["precio_tiquete_cop"].mean().items():
    log(f"  - {tarifa}: ${p:,.0f}")
log("  Decisión: se conservan. Son precios válidos explicados por la tarifa Ejecutiva/Flexible.")
log()

# 6. Variables derivadas
log("=== 6. VARIABLES DERIVADAS ===")
df["anio"] = df["fecha_vuelo"].dt.year
df["mes"] = df["fecha_vuelo"].dt.month
df["trimestre"] = df["fecha_vuelo"].dt.quarter
df["anio_mes"] = df["fecha_vuelo"].dt.to_period("M").astype(str)
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
df["dia_semana"] = df["fecha_vuelo"].dt.dayofweek.map(dict(enumerate(DIAS)))
df["ruta"] = df["origen"].astype(str) + "-" + df["destino"].astype(str)

df["vuelo_puntual"] = (df["retraso_salida_min"] <= UMBRAL_PUNTUALIDAD_MIN).astype("boolean")
df.loc[df["vuelo_cancelado"], "vuelo_puntual"] = pd.NA

df["rango_retraso"] = pd.cut(
    df["retraso_salida_min"],
    bins=[-1, 0, 15, 45, 90, np.inf],
    labels=["Sin retraso", "1-15 min", "16-45 min", "46-90 min", "Más de 90 min"],
)
df["rango_retraso"] = df["rango_retraso"].cat.add_categories("Cancelado")
df.loc[df["vuelo_cancelado"], "rango_retraso"] = "Cancelado"

df["vuelo_irregular"] = df["motivo_irregularidad"] != "Sin irregularidad"
df["pasajero_satisfecho"] = (df["calificacion_1a5"] >= 4).astype("boolean")
df.loc[df["calificacion_1a5"].isna(), "pasajero_satisfecho"] = pd.NA
df["ingreso_efectivo_cop"] = np.where(df["vuelo_cancelado"], 0, df["precio_tiquete_cop"])

log("anio, mes, trimestre, anio_mes, dia_semana: desagregación temporal.")
log("ruta: origen-destino.")
log(f"vuelo_puntual: retraso <= {UMBRAL_PUNTUALIDAD_MIN} min (nulo si cancelado).")
log("rango_retraso: Sin retraso / 1-15 / 16-45 / 46-90 / Más de 90 min / Cancelado.")
log("vuelo_irregular: tiene motivo de irregularidad.")
log("pasajero_satisfecho: calificación >= 4 (nulo si no calificó).")
log("ingreso_efectivo_cop: precio si el vuelo operó, 0 si fue cancelado.")
log()

# 7. Resumen de KPIs de referencia
operados = df[~df["vuelo_cancelado"]]
log("=== 7. KPIs DE REFERENCIA (dataset completo) ===")
log(f"% de puntualidad:          {operados['vuelo_puntual'].mean():.1%}")
log(f"Tasa de cancelación:       {df['vuelo_cancelado'].mean():.1%}")
log(f"% vuelos con irregularidad:{df['vuelo_irregular'].mean():.1%}")
log(f"Calificación promedio:     {df['calificacion_1a5'].mean():.2f}")
log(f"Ingresos totales:          ${df['ingreso_efectivo_cop'].sum():,.0f} COP")
log(f"Ocupación promedio:        {operados['ocupacion_pct'].mean():.1f} %")
log()

# 8. Exportación
log("=== 8. RESULTADO ===")
log(f"Registros finales: {len(df):,} (no se eliminó ningún registro)")
log(f"Columnas finales: {df.shape[1]}")
df.to_csv(ARCHIVO_LIMPIO, index=False)
log(f"Archivo generado: {ARCHIVO_LIMPIO.name}")
log()

# 9. Modelo de datos (esquema estrella)
log("=== 9. MODELO DE DATOS (ESQUEMA ESTRELLA) ===")
CARPETA_MODELO.mkdir(exist_ok=True)

aeropuertos = pd.DataFrame(
    [
        ("BOG", "Bogotá", "Andina", 4.7016, -74.1469),
        ("MDE", "Medellín", "Andina", 6.1645, -75.4231),
        ("CLO", "Cali", "Pacífico", 3.5432, -76.3816),
        ("CTG", "Cartagena", "Caribe", 10.4424, -75.5130),
        ("BAQ", "Barranquilla", "Caribe", 10.8896, -74.7808),
        ("BGA", "Bucaramanga", "Andina", 7.1265, -73.1848),
        ("PEI", "Pereira", "Andina", 4.8127, -75.7395),
        ("SMR", "Santa Marta", "Caribe", 11.1196, -74.2306),
    ],
    columns=["codigo", "ciudad", "region", "latitud", "longitud"],
)

dim_calendario = pd.DataFrame({"fecha": pd.date_range(df["fecha_vuelo"].min(), df["fecha_vuelo"].max())})
dim_calendario["id_fecha"] = dim_calendario["fecha"].dt.strftime("%Y%m%d").astype(int)
dim_calendario["anio"] = dim_calendario["fecha"].dt.year
dim_calendario["trimestre"] = dim_calendario["fecha"].dt.quarter
dim_calendario["mes"] = dim_calendario["fecha"].dt.month
dim_calendario["anio_mes"] = dim_calendario["fecha"].dt.to_period("M").astype(str)
dim_calendario["dia_semana"] = dim_calendario["fecha"].dt.dayofweek + 1
dim_calendario["es_fin_de_semana"] = dim_calendario["dia_semana"] >= 6

rutas = df[["ruta", "origen", "destino"]].drop_duplicates().sort_values("ruta").reset_index(drop=True)
rutas["origen"] = rutas["origen"].astype(str)
rutas["destino"] = rutas["destino"].astype(str)
rutas.insert(0, "id_ruta", range(1, len(rutas) + 1))
dim_ruta = (
    rutas.merge(aeropuertos.add_suffix("_origen"), left_on="origen", right_on="codigo_origen")
    .merge(aeropuertos.add_suffix("_destino"), left_on="destino", right_on="codigo_destino")
    .drop(columns=["codigo_origen", "codigo_destino"])
    .sort_values("id_ruta")
)
dim_ruta["tipo_ruta"] = np.where(
    dim_ruta["region_origen"] == dim_ruta["region_destino"], "Intrarregional", "Interregional"
)


def dimension(columna, nombre_id):
    tabla = pd.DataFrame({columna: sorted(df[columna].astype(str).unique())})
    tabla.insert(0, nombre_id, range(1, len(tabla) + 1))
    return tabla


dim_tarifa = dimension("tarifa", "id_tarifa")
dim_canal = dimension("canal_venta", "id_canal")
dim_franja = dimension("franja_salida", "id_franja")
dim_motivo = dimension("motivo_irregularidad", "id_motivo")

hechos = df.copy()
hechos["id_fecha"] = hechos["fecha_vuelo"].dt.strftime("%Y%m%d").astype(int)
for dim, col, id_col in [
    (dim_ruta, "ruta", "id_ruta"),
    (dim_tarifa, "tarifa", "id_tarifa"),
    (dim_canal, "canal_venta", "id_canal"),
    (dim_franja, "franja_salida", "id_franja"),
    (dim_motivo, "motivo_irregularidad", "id_motivo"),
]:
    hechos[col] = hechos[col].astype(str)
    hechos = hechos.merge(dim[[col, id_col]], on=col, how="left")

fact_vuelos = hechos[
    [
        "id_segmento_vuelo", "id_fecha", "id_ruta", "id_tarifa", "id_canal", "id_franja", "id_motivo",
        "precio_tiquete_cop", "ingreso_efectivo_cop", "ocupacion_pct", "retraso_salida_min",
        "rango_retraso", "vuelo_cancelado", "vuelo_puntual", "vuelo_irregular",
        "calificacion_1a5", "pasajero_satisfecho",
        "equipaje_facturado", "conexion", "cliente_frecuente",
    ]
]
assert fact_vuelos[["id_fecha", "id_ruta", "id_tarifa", "id_canal", "id_franja", "id_motivo"]].notna().all().all()
assert fact_vuelos["id_fecha"].isin(dim_calendario["id_fecha"]).all()

tablas = {
    "fact_vuelos": fact_vuelos,
    "dim_calendario": dim_calendario,
    "dim_ruta": dim_ruta,
    "dim_tarifa": dim_tarifa,
    "dim_canal": dim_canal,
    "dim_franja": dim_franja,
    "dim_motivo": dim_motivo,
}
for nombre, tabla in tablas.items():
    tabla.to_csv(CARPETA_MODELO / f"{nombre}.csv", index=False)
    log(f"{nombre}: {len(tabla):,} filas x {tabla.shape[1]} columnas")
log("Relaciones (1 a muchos, dimensión -> hechos):")
log("  dim_calendario.id_fecha -> fact_vuelos.id_fecha")
log("  dim_ruta.id_ruta        -> fact_vuelos.id_ruta")
log("  dim_tarifa.id_tarifa    -> fact_vuelos.id_tarifa")
log("  dim_canal.id_canal      -> fact_vuelos.id_canal")
log("  dim_franja.id_franja    -> fact_vuelos.id_franja")
log("  dim_motivo.id_motivo    -> fact_vuelos.id_motivo")
log("Granularidad de la tabla de hechos: un segmento de vuelo vendido.")
log(f"Tablas guardadas en: {CARPETA_MODELO.name}/")

ARCHIVO_REGISTRO.write_text("\n".join(registro), encoding="utf-8")
