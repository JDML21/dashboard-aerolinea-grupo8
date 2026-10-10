"""
Dashboard de operaciones y experiencia del pasajero
Grupo 8 - Aerolínea de operación nacional y regional

Ejecutar:  streamlit run app.py
Datos:     carpeta modelo/ (generada por preparacion_datos.py)

Principios de diseño de esta versión
- Una sola definición por KPI (función `resumir`), reutilizada en todo el tablero.
- Los hallazgos se CALCULAN con los datos filtrados y muestran su evidencia; si la
  condición no se cumple, el texto cambia.
- Las metas son referencias PROPUESTAS por el grupo, no estándares universales.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Compatibilidad entre versiones de Streamlit: "stretch" solo existe desde la 1.50
_VERSION = tuple(int(x) for x in st.__version__.split(".")[:2] if x.isdigit())
ANCHO = {"width": "stretch"} if _VERSION >= (1, 50) else {"use_container_width": True}

st.set_page_config(page_title="Aerolínea · Operación y Experiencia", page_icon=":material/flight:", layout="wide")

CARPETA = Path(__file__).parent
CARPETA_MODELO = CARPETA / "modelo"

# ---------------------------------------------------------------------------
# Paleta semántica: cada color tiene un único significado en todo el dashboard
# ---------------------------------------------------------------------------
AZUL = "#1F4E79"    # dato principal / neutro
GRIS = "#B8C0CC"    # contexto, segmentos sin alerta
ROJO = "#C0392B"    # alerta: no cumple la meta / empeora
AMBAR = "#E0A030"   # precaución
VERDE = "#2E8B57"   # cumple la meta / mejora
ESCALA_SEMAFORO = [ROJO, AMBAR, VERDE]

# ---------------------------------------------------------------------------
# Metas de referencia PROPUESTAS por el grupo (no son estándares universales)
# ---------------------------------------------------------------------------
META_PUNTUALIDAD = 0.80
META_CANCELACION = 0.02
META_IRREGULARIDAD = 0.10
META_CALIFICACION = 4.0
META_CALIFICACION_CRITICA = 3.5
META_OCUPACION = 80.0

# Criterios de interpretación (documentados en la pestaña de metodología)
MIN_VUELOS = 100             # tamaño mínimo de muestra para comparar un grupo
BRECHA_LOCALIZADA = 0.05     # un grupo es "localizado" si está >= 5 p.p. bajo el resto...
Z_LOCALIZADA = 3.0           # ...y la diferencia es estadísticamente clara (|z| >= 3)
MIN_RESPUESTAS = 30          # mínimo de calificaciones para mostrar un promedio
ALERTA_PUNTUALIDAD = 0.04    # caída mensual de puntualidad que dispara alerta (~2 errores estándar)
ALERTA_CANCELACION = 0.01    # alza mensual de la tasa de cancelación que dispara alerta
ALERTA_CALIFICACION = 0.05   # caída mensual de la calificación que dispara alerta

ORDEN_FRANJA = ["Madrugada", "Mañana", "Tarde", "Noche"]
ORDEN_TARIFA = ["Básica", "Flexible", "Ejecutiva"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
TRAMOS = ["Sin retraso", "1-15 min", "16-30 min", "31-45 min", "46-60 min", "61-75 min", "76-90 min", "Más de 90 min"]
LIMITES_TRAMOS = [-1, 0, 15, 30, 45, 60, 75, 90, np.inf]
MIN_INICIO_TRAMO = dict(zip(TRAMOS, [0, 1, 16, 31, 46, 61, 76, 91]))

DIMENSIONES = {
    "Ruta": "ruta",
    "Aeropuerto de origen": "origen",
    "Aeropuerto de destino": "destino",
    "Franja de salida": "franja_salida",
    "Día de la semana": "dia",
    "Tarifa": "tarifa",
    "Canal de venta": "canal_venta",
}


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------
def fmt_num(x, dec=0):
    if x is None or pd.isna(x):
        return "–"
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x, dec=1):
    return "–" if x is None or pd.isna(x) else f"{fmt_num(x * 100, dec)} %"


def fmt_pp(x, dec=1):
    return f"{fmt_num(abs(x) * 100, dec)} p.p."


def fmt_millones(x):
    return f"${fmt_num(x / 1e6)} M"


def lista(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def estilo(fig, alto=360, leyenda=True):
    fig.update_layout(
        template="plotly_white",
        height=alto,
        margin=dict(l=10, r=10, t=50, b=10),
        separators=",.",
        showlegend=leyenda,
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, title_text=""),
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#334155"),
        title_font=dict(size=15, color="#0F172A"),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(gridcolor="#E6E9EF", zerolinecolor="#D0D5DD")
    if any(getattr(t, "x", None) is not None and np.issubdtype(np.asarray(t.x).dtype, np.datetime64) for t in fig.data):
        fig.update_xaxes(tickformat="%m/%Y")
    fig.update_yaxes(gridcolor="#E6E9EF", zerolinecolor="#D0D5DD")
    return fig


def grafico(fig, unidad, n, extra=""):
    """Dibuja el gráfico y debajo su unidad, periodo y número de observaciones."""
    config = {"displayModeBar": False, "locale": "es"}
    st.plotly_chart(fig, use_container_width=True, theme=None, config=config)
    pie = f"{unidad} · n = {fmt_num(n)} · {PERIODO}"
    st.caption(f"{pie}. {extra}" if extra else pie)


ESTADOS = {
    "ok": (VERDE, "Cumple la meta"),
    "alerta": (ROJO, "Bajo la meta"),
    "precaucion": (AMBAR, "Precaución"),
    "neutral": (AZUL, "Referencia"),
}


def estilos_globales():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"], .stMarkdown, .stTabs, .stRadio, .stMultiSelect, .stDateInput {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }}
        .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1480px; }}
        header[data-testid="stHeader"] {{ background: transparent; }}

        /* Encabezado */
        .hero {{
            background: linear-gradient(120deg, #0B1F3A 0%, {AZUL} 70%, #2B6CB0 100%);
            border-radius: 16px; padding: 24px 32px; color: #fff; margin-bottom: 16px;
            box-shadow: 0 10px 30px rgba(11, 31, 58, .18);
        }}
        .hero .eyebrow {{ font-size: 12px; letter-spacing: .14em; text-transform: uppercase; opacity: .75; font-weight: 600; }}
        .hero h1 {{ font-size: clamp(24px, 3.2vw, 36px); font-weight: 800; margin: 6px 0 12px; line-height: 1.15; color: #fff; padding: 0; }}
        .hero .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .hero .chip {{ background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.22);
            border-radius: 999px; padding: 5px 12px; font-size: 13px; }}
        .hero .chip b {{ font-weight: 600; opacity: .8; margin-right: 4px; }}

        /* Pestañas */
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid #E2E8F0; flex-wrap: wrap; }}
        .stTabs [data-baseweb="tab"] {{ padding: 10px 16px; font-weight: 600; color: #64748B; }}
        .stTabs [aria-selected="true"] {{ color: {AZUL}; }}
        .stTabs [data-baseweb="tab-highlight"] {{ background-color: {AZUL}; height: 3px; }}

        /* Encabezado de sección */
        .seccion {{ margin: 16px 0 8px; }}
        .seccion .eyebrow {{ font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: {AZUL}; font-weight: 700; }}
        .seccion h2 {{ font-size: clamp(18px, 2vw, 24px); font-weight: 700; color: #0F172A; margin: 4px 0 0; padding: 0; }}
        .subtitulo {{ font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #64748B; font-weight: 700; margin: 22px 0 6px; }}

        /* Tarjetas KPI (compactas: los seis caben en una fila) */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: 12px; margin: 6px 0 16px; }}
        .kpi {{ background: #fff; border: 1px solid #E2E8F0; border-top: 4px solid var(--c); border-radius: 12px;
            padding: 14px 16px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
        .kpi .lbl {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: .06em; color: #64748B; font-weight: 600; }}
        .kpi .val {{ font-size: clamp(24px, 2.1vw, 30px); font-weight: 800; color: var(--c); line-height: 1.2; margin: 4px 0 6px; }}
        .kpi .foot {{ display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-wrap: wrap; }}
        .kpi .det {{ font-size: 12px; color: #475569; }}
        .kpi .delta {{ font-size: 12px; font-weight: 600; margin-top: 6px; display: block; }}
        .pill {{ font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap;
            color: var(--c); background: color-mix(in srgb, var(--c) 12%, white); }}

        /* Hallazgos con evidencia */
        .hallazgo {{ background: #F1F5FB; border-left: 4px solid var(--c, {AZUL}); border-radius: 10px; padding: 12px 16px;
            margin: 6px 0 16px; font-size: 14.5px; color: #1E293B; line-height: 1.55; }}
        .hallazgo .tag {{ display: block; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
            color: var(--c, {AZUL}); margin-bottom: 4px; }}
        .hallazgo .evid {{ display: block; margin-top: 6px; font-size: 12.5px; color: #64748B; }}

        /* Alertas */
        .alertas {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 18px; }}
        .alertas h3 {{ font-size: 14px; margin: 0 0 8px; padding: 0; color: #0F172A; }}
        .alertas ul {{ margin: 0; padding-left: 18px; font-size: 13.5px; line-height: 1.7; color: #334155; }}

        /* Conclusiones */
        .concl-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
        .concl {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px 20px; border-top: 4px solid var(--c); }}
        .concl h3 {{ font-size: 16px; font-weight: 700; margin: 0 0 10px; padding: 0; color: #0F172A; }}
        .concl ul {{ margin: 0; padding-left: 18px; font-size: 14px; color: #334155; line-height: 1.6; }}

        /* Leyenda de color en la barra lateral */
        .leyenda {{ font-size: 13px; color: #334155; line-height: 1.9; }}
        .leyenda span {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }}

        /* Gráficos como tarjetas */
        [data-testid="stPlotlyChart"] {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 4px 2px; box-sizing: border-box; overflow: hidden; }}

        @media (max-width: 640px) {{
            .hero {{ padding: 20px; border-radius: 12px; }}
            .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def delta_html(actual, previo, tipo, mayor_es_mejor=True):
    """Variación frente al mes anterior; verde = mejora, rojo = empeora."""
    if previo is None or pd.isna(actual) or pd.isna(previo) or (tipo == "rel" and previo == 0):
        return ""
    d = actual - previo
    if abs(d) < 1e-12:
        return '<span class="delta" style="color:#64748B">= sin cambio vs. mes anterior</span>'
    texto = {
        "pp": lambda: fmt_pp(d),
        "pp100": lambda: f"{fmt_num(abs(d), 1)} p.p.",
        "abs": lambda: fmt_num(abs(d), 2),
        "rel": lambda: fmt_pct(abs(d / previo)),
    }[tipo]()
    color = VERDE if (d > 0) == mayor_es_mejor else ROJO
    return f'<span class="delta" style="color:{color}">{"▲" if d > 0 else "▼"} {texto} vs. mes anterior</span>'


def kpi(titulo, valor, detalle, estado, delta=""):
    color, etiqueta = ESTADOS[estado]
    return (
        f'<div class="kpi" style="--c:{color}"><div class="lbl">{titulo}</div><div class="val">{valor}</div>'
        f'<div class="foot"><span class="det">{detalle}</span><span class="pill">{etiqueta}</span></div>{delta}</div>'
    )


def fila_kpis(tarjetas):
    st.markdown(f'<div class="kpi-grid">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def seccion(etiqueta, pregunta):
    st.markdown(
        f'<div class="seccion"><div class="eyebrow">{etiqueta}</div><h2>{pregunta}</h2></div>',
        unsafe_allow_html=True,
    )


def subtitulo(texto):
    st.markdown(f'<div class="subtitulo">{texto}</div>', unsafe_allow_html=True)


def hallazgo(texto, evidencia="", estado="neutral"):
    color = ESTADOS[estado][0]
    evid = f'<span class="evid">Evidencia: {evidencia}</span>' if evidencia else ""
    st.markdown(
        f'<div class="hallazgo" style="--c:{color}"><span class="tag">Hallazgo</span>{texto}{evid}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Carga de datos: se reconstruye la tabla analítica a partir del modelo estrella
# ---------------------------------------------------------------------------
@st.cache_data
def cargar_datos():
    fact = pd.read_csv(CARPETA_MODELO / "fact_vuelos.csv")
    calendario = pd.read_csv(CARPETA_MODELO / "dim_calendario.csv", parse_dates=["fecha"])
    ruta = pd.read_csv(CARPETA_MODELO / "dim_ruta.csv")
    tarifa = pd.read_csv(CARPETA_MODELO / "dim_tarifa.csv")
    canal = pd.read_csv(CARPETA_MODELO / "dim_canal.csv")
    franja = pd.read_csv(CARPETA_MODELO / "dim_franja.csv")
    motivo = pd.read_csv(CARPETA_MODELO / "dim_motivo.csv")

    df = (
        fact.merge(calendario, on="id_fecha", how="left")
        .merge(ruta, on="id_ruta", how="left")
        .merge(tarifa, on="id_tarifa", how="left")
        .merge(canal, on="id_canal", how="left")
        .merge(franja, on="id_franja", how="left")
        .merge(motivo, on="id_motivo", how="left")
    )
    # Booleanos con nulos (vuelo cancelado / sin calificación) se llevan a 1, 0 o NaN
    for col in ["vuelo_puntual", "pasajero_satisfecho"]:
        df[col] = df[col].map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})
    df["mes_inicio"] = df["fecha"].dt.to_period("M").dt.to_timestamp()
    df["dia"] = (df["dia_semana"] - 1).map(dict(enumerate(DIAS)))
    df["tramo_retraso"] = pd.cut(df["retraso_salida_min"], bins=LIMITES_TRAMOS, labels=TRAMOS)
    df["tipo_irregularidad"] = np.where(
        df["vuelo_cancelado"], "Cancelado", np.where(df["vuelo_irregular"], "Retraso > 60 min", "Sin irregularidad")
    )
    return df


@st.cache_data
def perfil_calidad():
    """Perfil del archivo ORIGINAL (antes de la limpieza), para mostrar la calidad de los datos."""
    archivo = CARPETA / "08_aerolinea_regional.csv"
    if not archivo.exists():
        return None
    o = pd.read_csv(archivo)
    return {
        "registros": len(o),
        "dup_id": int(o["id_segmento_vuelo"].duplicated().sum()),
        "dup_fila": int(o.drop(columns="id_segmento_vuelo").duplicated().sum()),
        "faltantes": {c: int(n) for c, n in o.isna().sum().items() if n > 0},
        "cancelados_con_retraso": int(((o["vuelo_cancelado"] == "Sí") & (o["retraso_salida_min"] > 0)).sum()),
    }


def resumir(d):
    """ÚNICA definición de los KPI. Se reutiliza en todo el tablero."""
    operados = d[~d["vuelo_cancelado"]]
    return pd.Series(
        {
            "vuelos": len(d),
            "operados": len(operados),
            "puntualidad": operados["vuelo_puntual"].mean(),                       # retraso <= 15 min / operados
            "cancelacion": d["vuelo_cancelado"].mean(),                            # cancelados / total
            "irregularidad": d["vuelo_irregular"].mean(),                          # cancelado o retraso > 60 / total
            "calificacion": d["calificacion_1a5"].mean(),                          # sin contar vacíos
            "ingresos": d["ingreso_efectivo_cop"].sum(),                           # precio si operó, 0 si canceló
            "ocupacion": operados["ocupacion_pct"].mean(),                         # solo vuelos operados
            "expuesto": operados.loc[operados["vuelo_puntual"] == 0, "ingreso_efectivo_cop"].sum(),
        }
    )


def evaluar_grupos(operados, col):
    """Puntualidad por grupo y prueba de si el grupo se aparta del resto de la operación."""
    n_tot, s_tot = len(operados), operados["vuelo_puntual"].sum()
    g = operados.groupby(col, observed=True)["vuelo_puntual"].agg(media="mean", vuelos="size", exitos="sum")
    g = g[g["vuelos"] >= MIN_VUELOS].copy()
    g["brecha"], g["z"], g["localizado"] = np.nan, np.nan, False
    if len(g) < 2 or n_tot == 0:
        return g
    resto_n = n_tot - g["vuelos"]
    resto_p = (s_tot - g["exitos"]) / resto_n
    p = s_tot / n_tot
    se = np.sqrt(p * (1 - p) * (1 / g["vuelos"] + 1 / resto_n))
    g["brecha"] = g["media"] - resto_p
    g["z"] = g["brecha"] / se.replace(0, np.nan)
    g["localizado"] = (g["brecha"] <= -BRECHA_LOCALIZADA) & (g["z"] <= -Z_LOCALIZADA)
    return g


def tabla_rutas(d, puntualidad_ref):
    """Una fila por ruta: ingresos, puntualidad, cancelación, calificación, volumen y prioridad."""
    op = d[~d["vuelo_cancelado"]]
    claves = ["ruta", "origen", "destino", "latitud_origen", "longitud_origen", "latitud_destino", "longitud_destino"]
    t = d.groupby(claves).agg(
        ingresos=("ingreso_efectivo_cop", "sum"), vuelos=("id_segmento_vuelo", "size"),
        cancelacion=("vuelo_cancelado", "mean"), calificacion=("calificacion_1a5", "mean"),
    )
    t = t.join(op.groupby(claves).agg(puntualidad=("vuelo_puntual", "mean"), ocupacion=("ocupacion_pct", "mean")))
    t = t.join(op[op["vuelo_puntual"] == 0].groupby(claves)["ingreso_efectivo_cop"].sum().rename("expuesto"))
    t = t.fillna({"expuesto": 0}).reset_index()
    mediana = t.loc[t["vuelos"] >= MIN_VUELOS, "ingresos"].median()
    t["prioridad"] = np.select(
        [t["vuelos"] < MIN_VUELOS, (t["ingresos"] >= mediana) & (t["puntualidad"] < puntualidad_ref), t["ingresos"] >= mediana],
        ["Muestra pequeña", "Intervenir: alto ingreso, baja puntualidad", "Proteger: alto ingreso, puntualidad sobre el promedio"],
        default="Seguimiento: menor ingreso",
    )
    return t, mediana


def umbral_tramo(por_tramo, limite):
    bajo = por_tramo[por_tramo["media"] < limite]
    return None if bajo.empty else bajo.index[0]


def texto_umbral(tramo):
    return f"más de {MIN_INICIO_TRAMO[tramo] - 1} min"


estilos_globales()
datos = cargar_datos()

# ---------------------------------------------------------------------------
# Barra lateral: filtros globales
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

fecha_min, fecha_max = datos["fecha"].min().date(), datos["fecha"].max().date()
rango = st.sidebar.date_input(
    "Periodo", value=(fecha_min, fecha_max), min_value=fecha_min, max_value=fecha_max, format="DD/MM/YYYY"
)
inicio, fin = (rango[0], rango[1]) if len(rango) == 2 else (rango[0], rango[0])
PERIODO = f"{inicio:%d/%m/%Y} – {fin:%d/%m/%Y}"

regiones = sorted(datos["region_origen"].unique())
region_sel = st.sidebar.multiselect("Región de origen", regiones, default=regiones)

origenes = sorted(datos.loc[datos["region_origen"].isin(region_sel), "origen"].unique())
origen_sel = st.sidebar.multiselect("Aeropuerto de origen", origenes, default=origenes)

destinos = sorted(datos["destino"].unique())
destino_sel = st.sidebar.multiselect("Aeropuerto de destino", destinos, default=destinos)

tarifa_sel = st.sidebar.multiselect("Tarifa", ORDEN_TARIFA, default=ORDEN_TARIFA)
canales = sorted(datos["canal_venta"].unique())
canal_sel = st.sidebar.multiselect("Canal de venta", canales, default=canales)
franja_sel = st.sidebar.multiselect("Franja de salida", ORDEN_FRANJA, default=ORDEN_FRANJA)

df = datos[
    (datos["fecha"] >= pd.Timestamp(inicio))
    & (datos["fecha"] <= pd.Timestamp(fin))
    & datos["origen"].isin(origen_sel)
    & datos["destino"].isin(destino_sel)
    & datos["tarifa"].isin(tarifa_sel)
    & datos["canal_venta"].isin(canal_sel)
    & datos["franja_salida"].isin(franja_sel)
]

st.sidebar.markdown("---")
st.sidebar.caption(f"Vuelos en la selección: **{fmt_num(len(df))}** de {fmt_num(len(datos))}")
st.sidebar.markdown(
    f"""<div class="leyenda"><b>Código de color</b><br>
    <span style="background:{VERDE}"></span>Cumple la meta / mejora<br>
    <span style="background:{AMBAR}"></span>Precaución<br>
    <span style="background:{ROJO}"></span>Bajo la meta / empeora<br>
    <span style="background:{AZUL}"></span>Dato de referencia<br>
    <span style="background:{GRIS}"></span>Contexto, sin alerta</div>""",
    unsafe_allow_html=True,
)
st.sidebar.caption("Las metas son referencias propuestas por el grupo para este análisis, no estándares universales.")

if df.empty or df["vuelo_cancelado"].all():
    st.warning("No hay vuelos operados para la combinación de filtros seleccionada. Ajuste los filtros.")
    st.stop()

operados = df[~df["vuelo_cancelado"]]
k = resumir(df)
mensual = df.groupby("mes_inicio").apply(resumir, include_groups=False).reset_index().sort_values("mes_inicio")
ultimo = mensual.iloc[-1]
previo = mensual.iloc[-2] if len(mensual) >= 2 else None

# ---------------------------------------------------------------------------
# Cálculos compartidos (los hallazgos y las conclusiones salen de aquí)
# ---------------------------------------------------------------------------
# Pregunta 1: ¿localizado o sistémico?
diag = []
for nombre, col in DIMENSIONES.items():
    g = evaluar_grupos(operados, col)
    if len(g) >= 2:
        diag.append({"dimension": nombre, "col": col, "g": g})
localizados = [
    (r["dimension"], idx, fila) for r in diag for idx, fila in r["g"].iterrows() if fila["localizado"]
]
if diag:
    brecha_dim = max(diag, key=lambda r: r["g"]["media"].max() - r["g"]["media"].min())
    brecha_max = brecha_dim["g"]["media"].max() - brecha_dim["g"]["media"].min()
else:
    brecha_dim, brecha_max = None, np.nan

# Pregunta 2: satisfacción vs retraso
calificados = df.dropna(subset=["calificacion_1a5"])
cal_operados = calificados[~calificados["vuelo_cancelado"]]
por_tramo = cal_operados.groupby("tramo_retraso", observed=True)["calificacion_1a5"].agg(
    media="mean", desv="std", n="size"
).reindex(TRAMOS).dropna(subset=["media"])
por_tramo = por_tramo[por_tramo["n"] >= MIN_RESPUESTAS]
tramo_alerta = umbral_tramo(por_tramo, META_CALIFICACION)
tramo_critico = umbral_tramo(por_tramo, META_CALIFICACION_CRITICA)
pendiente_15 = np.nan
if cal_operados["retraso_salida_min"].nunique() > 2:
    pendiente_15 = 15 * np.polyfit(cal_operados["retraso_salida_min"], cal_operados["calificacion_1a5"], 1)[0]
cal_cancelados = calificados.loc[calificados["vuelo_cancelado"], "calificacion_1a5"]
cal_retraso_largo = calificados.loc[calificados["tipo_irregularidad"] == "Retraso > 60 min", "calificacion_1a5"]

# Pregunta 3: concentración de ingresos y exposición
tabla, mediana_ingresos = tabla_rutas(df, k.puntualidad)
top3 = tabla.sort_values("ingresos", ascending=False).head(3)
pct_expuesto = k.expuesto / k.ingresos if k.ingresos else np.nan
pct_no_puntuales = 1 - k.puntualidad
prioritarias = tabla[tabla["prioridad"].str.startswith("Intervenir")].sort_values("expuesto", ascending=False)

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
# Fecha del último vuelo registrado (no la del archivo: en el servidor esa fecha es la del despliegue)
fecha_datos = datos["fecha"].max()
st.markdown(
    f"""
    <div class="hero">
        <div class="eyebrow">Grupo 8 · Aerolínea de operación nacional y regional</div>
        <h1>Operación y experiencia del pasajero</h1>
        <div class="chips">
            <span class="chip"><b>Audiencia</b>Gerencia de Operaciones y Experiencia del Pasajero</span>
            <span class="chip"><b>Periodo</b>{PERIODO}</span>
            <span class="chip"><b>Vuelos</b>{fmt_num(len(df))} de {fmt_num(len(datos))}</span>
            <span class="chip"><b>Datos hasta</b>{fecha_datos:%d/%m/%Y}</span>
            <span class="chip"><b>Fuente</b>sintéticos y anonimizados</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_resumen, tab_operacion, tab_experiencia, tab_comercial, tab_conclusiones, tab_metodo = st.tabs(
    [
        "Resumen ejecutivo",
        "1 · Operación",
        "2 · Experiencia del pasajero",
        "3 · Comercial",
        "Conclusiones",
        "Datos y metodología",
    ]
)

# ===========================================================================
# RESUMEN EJECUTIVO: 6 KPI + una frase de estado + tendencia + alertas
# ===========================================================================
with tab_resumen:
    seccion("Panorama general", "Estado de la operación en el periodo seleccionado")

    estados_kpi = {
        "puntualidad": k.puntualidad >= META_PUNTUALIDAD,
        "cancelación": k.cancelacion <= META_CANCELACION,
        "irregularidad": k.irregularidad <= META_IRREGULARIDAD,
        "calificación": k.calificacion >= META_CALIFICACION,
        "ocupación": k.ocupacion >= META_OCUPACION,
    }
    cumplen = [n for n, ok in estados_kpi.items() if ok]
    incumplen = [n for n, ok in estados_kpi.items() if not ok]
    frase = (
        f"La puntualidad es de <b>{fmt_pct(k.puntualidad)}</b>, "
        f"{fmt_pp(k.puntualidad - META_PUNTUALIDAD)} {'por debajo de' if k.puntualidad < META_PUNTUALIDAD else 'sobre'} "
        f"la meta propuesta. Cumplen su meta {len(cumplen)} de 5 indicadores"
        + (f" ({lista(cumplen)})" if cumplen else "")
        + (f"; fuera de meta: {lista(incumplen)}." if incumplen else ".")
    )
    hallazgo(
        frase,
        f"{fmt_num(len(operados))} vuelos operados de {fmt_num(len(df))} en {PERIODO}. Metas propuestas por el grupo.",
        "ok" if not incumplen else ("alerta" if not estados_kpi["puntualidad"] else "precaucion"),
    )

    def d(col, tipo, mayor_es_mejor=True):
        return delta_html(ultimo[col], None if previo is None else previo[col], tipo, mayor_es_mejor)

    fila_kpis([
        kpi("Puntualidad (≤ 15 min)", fmt_pct(k.puntualidad), f"Meta: {fmt_pct(META_PUNTUALIDAD, 0)}",
            "ok" if estados_kpi["puntualidad"] else "alerta", d("puntualidad", "pp")),
        kpi("Tasa de cancelación", fmt_pct(k.cancelacion), f"Meta: ≤ {fmt_pct(META_CANCELACION, 0)}",
            "ok" if estados_kpi["cancelación"] else "alerta", d("cancelacion", "pp", False)),
        kpi("Vuelos con irregularidad", fmt_pct(k.irregularidad), f"Meta: ≤ {fmt_pct(META_IRREGULARIDAD, 0)}",
            "ok" if estados_kpi["irregularidad"] else "alerta", d("irregularidad", "pp", False)),
        kpi("Calificación promedio", f"{fmt_num(k.calificacion, 2)} / 5", f"Meta: ≥ {fmt_num(META_CALIFICACION, 1)}",
            "ok" if estados_kpi["calificación"] else "alerta", d("calificacion", "abs")),
        kpi("Ingresos totales", fmt_millones(k.ingresos), "COP · vuelos operados", "neutral", d("ingresos", "rel")),
        kpi("Ocupación promedio", f"{fmt_num(k.ocupacion, 1)} %", f"Meta: ≥ {fmt_num(META_OCUPACION, 0)} %",
            "ok" if estados_kpi["ocupación"] else "alerta", d("ocupacion", "pp100")),
    ])
    if previo is not None:
        st.caption(
            f"Variación del último mes del periodo ({ultimo['mes_inicio']:%m/%Y}) frente al mes anterior "
            f"({previo['mes_inicio']:%m/%Y}). Verde = mejora, rojo = empeora."
        )

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        fig = go.Figure()
        fig.add_scatter(
            x=mensual["mes_inicio"], y=mensual["puntualidad"], mode="lines+markers",
            line=dict(color=AZUL, width=2.5), name="Puntualidad",
            hovertemplate="%{x|%m/%Y}<br>Puntualidad: %{y:.1%}<extra></extra>",
        )
        fig.add_hline(
            y=META_PUNTUALIDAD, line_dash="dash", line_color=VERDE,
            annotation_text=f"Meta propuesta {fmt_pct(META_PUNTUALIDAD, 0)}", annotation_position="top left",
        )
        fig.update_yaxes(tickformat=".0%", range=[0, 1], title=None)
        fig.update_xaxes(title=None)
        fig.update_layout(title="Puntualidad mensual frente a la meta")
        grafico(estilo(fig, leyenda=False), "% de vuelos operados con retraso ≤ 15 min", len(operados))
    with col_der:
        m = mensual.assign(ingresos_m=mensual["ingresos"] / 1e6)
        fig = px.bar(m, x="mes_inicio", y="ingresos_m", title="Ingresos mensuales", color_discrete_sequence=[AZUL])
        fig.update_traces(hovertemplate="%{x|%m/%Y}<br>Ingresos: $%{y:,.0f} M<extra></extra>")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        grafico(estilo(fig, leyenda=False), "Millones de COP", len(operados))

    # Alertas: meses en que un indicador empeora más que el umbral definido
    alertas = []
    for i in range(1, len(mensual)):
        a, b = mensual.iloc[i], mensual.iloc[i - 1]
        mes = f"{a['mes_inicio']:%m/%Y}"
        if b["puntualidad"] - a["puntualidad"] >= ALERTA_PUNTUALIDAD:
            alertas.append((a["mes_inicio"], f"<b>{mes}</b> · puntualidad cae {fmt_pp(a['puntualidad'] - b['puntualidad'])} ({fmt_pct(b['puntualidad'])} → {fmt_pct(a['puntualidad'])})"))
        if a["cancelacion"] - b["cancelacion"] >= ALERTA_CANCELACION:
            alertas.append((a["mes_inicio"], f"<b>{mes}</b> · cancelaciones suben {fmt_pp(a['cancelacion'] - b['cancelacion'])} ({fmt_pct(b['cancelacion'])} → {fmt_pct(a['cancelacion'])})"))
        if b["calificacion"] - a["calificacion"] >= ALERTA_CALIFICACION:
            alertas.append((a["mes_inicio"], f"<b>{mes}</b> · calificación cae {fmt_num(b['calificacion'] - a['calificacion'], 2)} ({fmt_num(b['calificacion'], 2)} → {fmt_num(a['calificacion'], 2)})"))
    alertas.sort(key=lambda x: x[0], reverse=True)
    items = "".join(f"<li>{t}</li>" for _, t in alertas[:6]) or "<li>Ningún indicador empeoró más que el umbral en el periodo seleccionado.</li>"
    st.markdown(
        f'<div class="alertas"><h3>Alertas de variación mensual (las más recientes)</h3><ul>{items}</ul>'
        f'<div style="font-size:12px;color:#64748B;margin-top:6px">Se alerta si la puntualidad cae ≥ {fmt_num(ALERTA_PUNTUALIDAD * 100, 0)} p.p., '
        f'la cancelación sube ≥ {fmt_num(ALERTA_CANCELACION * 100, 0)} p.p. o la calificación cae ≥ {fmt_num(ALERTA_CALIFICACION, 2)} frente al mes anterior. '
        f'Umbrales fijados cerca de 2 errores estándar para no alertar por ruido.</div></div>',
        unsafe_allow_html=True,
    )

# ===========================================================================
# 1 · OPERACIÓN - ¿Localizado o de toda la operación? ¿Qué causas explican las irregularidades?
# ===========================================================================
with tab_operacion:
    seccion("Pregunta 1 · Operación", "¿La baja puntualidad es localizada o de toda la operación, y qué causas explican las irregularidades?")

    # --- Veredicto calculado con los datos filtrados -------------------------
    if not diag:
        hallazgo("Con los filtros actuales no hay grupos con muestra suficiente para comparar.",
                 f"se exigen al menos {MIN_VUELOS} vuelos operados por grupo.", "precaucion")
    elif localizados:
        peores = sorted(localizados, key=lambda x: x[2]["brecha"])[:4]
        detalle = "; ".join(f"<b>{idx}</b> ({dim}) {fmt_pct(f['media'])}, {fmt_pp(f['brecha'])} bajo el resto" for dim, idx, f in peores)
        hallazgo(
            f"La baja puntualidad tiene <b>focos localizados</b>: {detalle}.",
            f"se marcan grupos con ≥ {MIN_VUELOS} vuelos, ≥ {fmt_num(BRECHA_LOCALIZADA * 100, 0)} p.p. bajo el resto y |z| ≥ {fmt_num(Z_LOCALIZADA, 0)}.",
            "alerta",
        )
    elif k.puntualidad < META_PUNTUALIDAD:
        hallazgo(
            f"El problema es de <b>toda la operación</b>: la puntualidad ({fmt_pct(k.puntualidad)}) está bajo la meta en todas las "
            f"dimensiones y ningún grupo se aparta del resto. La mayor diferencia entre mejor y peor grupo es de "
            f"<b>{fmt_pp(brecha_max)}</b> ({brecha_dim['dimension'].lower()}), una diferencia que no es estadísticamente clara.",
            f"{len(diag)} dimensiones comparadas con grupos de ≥ {MIN_VUELOS} vuelos; ningún grupo cumple "
            f"(≥ {fmt_num(BRECHA_LOCALIZADA * 100, 0)} p.p. bajo el resto y |z| ≥ {fmt_num(Z_LOCALIZADA, 0)}).",
            "alerta",
        )
    else:
        hallazgo(f"La puntualidad ({fmt_pct(k.puntualidad)}) cumple la meta y no hay focos localizados.",
                 f"{len(diag)} dimensiones comparadas.", "ok")

    # --- Dispersión por dimensión: ¿dónde se separan los grupos? -------------
    fig = go.Figure()
    for r in diag:
        g = r["g"]
        fig.add_trace(go.Scatter(
            x=[g["media"].min(), g["media"].max()], y=[r["dimension"]] * 2, mode="lines",
            line=dict(color=GRIS, width=6), hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=g["media"], y=[r["dimension"]] * len(g), mode="markers", showlegend=False,
            marker=dict(size=10, opacity=0.8, color=[ROJO if v else AZUL for v in g["localizado"]],
                        line=dict(color="white", width=1)),
            text=g.index.astype(str), customdata=g["vuelos"],
            hovertemplate="%{text}<br>Puntualidad: %{x:.1%}<br>Vuelos operados: %{customdata:,}<extra></extra>",
        ))
    fig.add_vline(x=META_PUNTUALIDAD, line_dash="dash", line_color=VERDE,
                  annotation_text="Meta propuesta", annotation_position="top")
    fig.add_vline(x=k.puntualidad, line_dash="dot", line_color="#64748B",
                  annotation_text="Promedio", annotation_position="bottom")
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title="Puntualidad del grupo")
    fig.update_yaxes(title=None, autorange="reversed")
    fig.update_layout(title="Dispersión de la puntualidad por dimensión (cada punto es un grupo)")
    grafico(estilo(fig, alto=330, leyenda=False), "% de vuelos operados con retraso ≤ 15 min", len(operados),
            f"Azul = grupo en línea con el resto; rojo = foco localizado. Eje completo 0-100 % para no exagerar diferencias.")

    # --- Detalle por dimensión elegida + matriz de rutas ---------------------
    col_izq, col_der = st.columns([2, 3])
    with col_izq:
        dim_nombre = st.selectbox("Comparar la puntualidad por:", list(DIMENSIONES), index=3)
        g = evaluar_grupos(operados, DIMENSIONES[dim_nombre]).sort_values("media")
        if len(g) > 15:
            g = pd.concat([g.head(8), g.tail(7)])
            nota = "Se muestran los 8 grupos con menor y los 7 con mayor puntualidad."
        else:
            nota = "Ordenado de menor a mayor puntualidad."
        if g.empty:
            st.info("Sin grupos con muestra suficiente para esta dimensión.")
        else:
            fig = px.bar(
                g.reset_index(), y=DIMENSIONES[dim_nombre], x="media", orientation="h", text_auto=".1%",
                title=f"Puntualidad por {dim_nombre.lower()}", custom_data=["vuelos"],
            )
            fig.update_traces(
                marker_color=[ROJO if v else GRIS for v in g["localizado"]],
                hovertemplate="%{y}<br>Puntualidad: %{x:.1%}<br>Vuelos operados: %{customdata[0]:,}<extra></extra>",
            )
            fig.add_vline(x=META_PUNTUALIDAD, line_dash="dash", line_color=VERDE)
            fig.add_vline(x=k.puntualidad, line_dash="dot", line_color="#64748B")
            fig.update_xaxes(tickformat=".0%", range=[0, 1], title=None)
            fig.update_yaxes(title=None, type="category", autorange="reversed")
            grafico(estilo(fig, alto=430, leyenda=False), "% de vuelos operados con retraso ≤ 15 min", int(g["vuelos"].sum()),
                    f"{nota} Línea verde = meta; punteada = promedio.")
    with col_der:
        por_ruta = operados.groupby(["origen", "destino"]).agg(
            puntualidad=("vuelo_puntual", "mean"), vuelos=("vuelo_puntual", "size")
        ).reset_index()
        matriz = por_ruta.pivot(index="origen", columns="destino", values="puntualidad")
        vuelos_ruta = por_ruta.pivot(index="origen", columns="destino", values="vuelos")
        fig = go.Figure(
            go.Heatmap(
                z=matriz.values, x=matriz.columns, y=matriz.index, customdata=vuelos_ruta.values,
                colorscale=ESCALA_SEMAFORO, zmin=0.3, zmax=META_PUNTUALIDAD,
                text=[["" if pd.isna(v) else f"{v * 100:.0f}%" for v in fila] for fila in matriz.values],
                texttemplate="%{text}",
                hovertemplate="Ruta %{y} → %{x}<br>Puntualidad: %{z:.1%}<br>Vuelos operados: %{customdata:,}<extra></extra>",
                colorbar=dict(title="Puntualidad", tickformat=".0%"),
            )
        )
        fig.update_layout(title="Puntualidad por ruta (origen × destino)")
        fig.update_xaxes(title="Destino", side="bottom")
        fig.update_yaxes(title="Origen", autorange="reversed")
        grafico(estilo(fig, alto=430), "% de vuelos operados con retraso ≤ 15 min", len(operados),
                "Escala de color: rojo 30 % → verde 80 % (meta).")

    # --- Causas de irregularidad ---------------------------------------------
    subtitulo("Causas de las irregularidades")
    irregulares = df[df["vuelo_irregular"]].copy()
    if irregulares.empty:
        st.info("No hay vuelos irregulares con los filtros actuales.")
    else:
        reparto = irregulares["motivo_irregularidad"].value_counts(normalize=True)
        mayor, menor = reparto.index[0], reparto.index[-1]
        if reparto.iloc[0] >= 0.40:
            txt = (f"La causa <b>{mayor}</b> concentra el {fmt_pct(reparto.iloc[0], 0)} de las irregularidades: "
                   "es la primera palanca de mejora.")
        else:
            txt = (f"Ninguna causa domina: van del {fmt_pct(reparto.min(), 0)} ({menor}) al {fmt_pct(reparto.max(), 0)} ({mayor}). "
                   "Atacar una sola no resolvería el problema.")
        hallazgo(txt, f"{fmt_num(len(irregulares))} vuelos irregulares ({fmt_pct(k.irregularidad)} del total; meta ≤ {fmt_pct(META_IRREGULARIDAD, 0)}).",
                 "alerta" if k.irregularidad > META_IRREGULARIDAD else "ok")

        col_izq, col_der = st.columns(2)
        with col_izq:
            por_motivo = irregulares.groupby(["motivo_irregularidad", "tipo_irregularidad"]).size().reset_index(name="vuelos")
            orden = por_motivo.groupby("motivo_irregularidad")["vuelos"].sum().sort_values(ascending=False).index.tolist()
            fig = px.bar(
                por_motivo, y="motivo_irregularidad", x="vuelos", color="tipo_irregularidad", orientation="h",
                title="Vuelos irregulares por causa", text_auto=True,
                color_discrete_map={"Cancelado": ROJO, "Retraso > 60 min": AMBAR},
                category_orders={"motivo_irregularidad": orden},
            )
            fig.update_xaxes(title=None)
            fig.update_yaxes(title=None, autorange="reversed")
            grafico(estilo(fig), "Número de vuelos", len(irregulares))
        with col_der:
            por_ap = df.groupby("origen").agg(
                irregularidad=("vuelo_irregular", "mean"), cancelacion=("vuelo_cancelado", "mean"), vuelos=("vuelo_irregular", "size")
            ).sort_values("irregularidad", ascending=False).reset_index()
            fig = px.bar(por_ap, x="origen", y="irregularidad", text_auto=".1%", title="Vuelos con irregularidad por aeropuerto de origen",
                         custom_data=["vuelos", "cancelacion"])
            fig.update_traces(
                marker_color=[ROJO if v > META_IRREGULARIDAD else GRIS for v in por_ap["irregularidad"]],
                hovertemplate="%{x}<br>Irregularidad: %{y:.1%}<br>Cancelación: %{customdata[1]:.1%}<br>Vuelos: %{customdata[0]:,}<extra></extra>",
            )
            fig.add_hline(y=META_IRREGULARIDAD, line_dash="dash", line_color=VERDE,
                          annotation_text=f"Meta ≤ {fmt_pct(META_IRREGULARIDAD, 0)}", annotation_position="top right")
            fig.update_yaxes(tickformat=".0%", title=None)
            fig.update_xaxes(title=None)
            grafico(estilo(fig, leyenda=False), "% de vuelos (cancelados o con retraso > 60 min)", len(df),
                    "Rojo = sobre la meta; gris = dentro de la meta.")

    # --- Análisis temporal ----------------------------------------------------
    subtitulo("Cuándo empeora: variación mensual, día de la semana y franja")
    col_izq, col_der = st.columns(2)
    with col_izq:
        variacion = mensual[["mes_inicio", "puntualidad"]].copy()
        variacion["cambio"] = variacion["puntualidad"].diff()
        variacion = variacion.dropna()
        if variacion.empty:
            st.info("Se necesitan al menos dos meses para calcular la variación.")
        else:
            fig = go.Figure(go.Bar(
                x=variacion["mes_inicio"], y=variacion["cambio"] * 100,
                marker_color=[ROJO if c <= -ALERTA_PUNTUALIDAD else (VERDE if c >= ALERTA_PUNTUALIDAD else GRIS) for c in variacion["cambio"]],
                hovertemplate="%{x|%m/%Y}<br>Cambio: %{y:+.1f} p.p.<extra></extra>",
            ))
            fig.add_hline(y=0, line_color="#64748B")
            fig.update_yaxes(title=None, ticksuffix=" p.p.")
            fig.update_xaxes(title=None)
            fig.update_layout(title="Variación mensual de la puntualidad")
            grafico(estilo(fig, leyenda=False), "Puntos porcentuales vs. el mes anterior", len(operados),
                    f"Rojo/verde = cambio de al menos {fmt_num(ALERTA_PUNTUALIDAD * 100, 0)} p.p.; gris = variación normal.")
    with col_der:
        dia_franja = operados.groupby(["dia", "franja_salida"]).agg(
            puntualidad=("vuelo_puntual", "mean"), vuelos=("vuelo_puntual", "size")
        ).reset_index()
        mp = dia_franja.pivot(index="dia", columns="franja_salida", values="puntualidad").reindex(index=DIAS, columns=ORDEN_FRANJA)
        mv = dia_franja.pivot(index="dia", columns="franja_salida", values="vuelos").reindex(index=DIAS, columns=ORDEN_FRANJA)
        fig = go.Figure(go.Heatmap(
            z=mp.values, x=mp.columns, y=mp.index, customdata=mv.values,
            colorscale=ESCALA_SEMAFORO, zmin=0.3, zmax=META_PUNTUALIDAD,
            text=[["" if pd.isna(v) else f"{v * 100:.0f}%" for v in fila] for fila in mp.values], texttemplate="%{text}",
            hovertemplate="%{y} · %{x}<br>Puntualidad: %{z:.1%}<br>Vuelos operados: %{customdata:,}<extra></extra>",
            colorbar=dict(title="Puntualidad", tickformat=".0%"),
        ))
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title=None)
        fig.update_layout(title="Puntualidad por día de la semana y franja de salida")
        grafico(estilo(fig), "% de vuelos operados con retraso ≤ 15 min", len(operados))

# ===========================================================================
# 2 · EXPERIENCIA - ¿Cuánto cae la satisfacción y desde qué umbral es crítica?
# ===========================================================================
with tab_experiencia:
    seccion("Pregunta 2 · Experiencia", "¿Cuánto cae la satisfacción según el retraso y el tipo de irregularidad, y desde qué umbral es crítica?")

    if len(por_tramo) < 2:
        st.info("No hay suficientes calificaciones por tramo de retraso con los filtros actuales.")
    else:
        primero, ultimo_tramo = por_tramo.index[0], por_tramo.index[-1]
        caida = por_tramo.loc[primero, "media"] - por_tramo.loc[ultimo_tramo, "media"]
        partes = [
            f"La calificación baja de <b>{fmt_num(por_tramo.loc[primero, 'media'], 2)}</b> ({primero.lower()}) a "
            f"<b>{fmt_num(por_tramo.loc[ultimo_tramo, 'media'], 2)}</b> ({ultimo_tramo.lower()})"
        ]
        if not np.isnan(pendiente_15):
            partes[0] += f", unos <b>{fmt_num(abs(pendiente_15), 2)} puntos por cada 15 minutos</b> de retraso adicional"
        partes[0] += "."
        if tramo_alerta is not None:
            partes.append(
                f"Queda bajo la meta de {fmt_num(META_CALIFICACION, 1)} desde el tramo <b>{tramo_alerta}</b> "
                f"(<b>{texto_umbral(tramo_alerta)}</b>)"
                + (f" y bajo {fmt_num(META_CALIFICACION_CRITICA, 1)} (nivel crítico) con <b>{texto_umbral(tramo_critico)}</b>." if tramo_critico is not None else ".")
            )
        else:
            partes.append(f"Ningún tramo cae bajo la meta de {fmt_num(META_CALIFICACION, 1)}.")
        if len(cal_cancelados) >= MIN_RESPUESTAS and len(cal_retraso_largo) >= MIN_RESPUESTAS:
            c, r = cal_cancelados.mean(), cal_retraso_largo.mean()
            partes.append(
                f"Un vuelo cancelado se califica {'mejor' if c > r else 'peor'} ({fmt_num(c, 2)}) que uno con retraso de más de 60 min ({fmt_num(r, 2)})."
            )
        hallazgo(
            " ".join(partes),
            f"{fmt_num(len(cal_operados))} calificaciones de vuelos operados; pendiente por regresión lineal; "
            f"el nivel crítico ({fmt_num(META_CALIFICACION_CRITICA, 1)}) es un criterio propuesto.",
            "alerta" if tramo_alerta is not None else "ok",
        )

        # --- Calificación por tramo de retraso (con intervalo de confianza) ---
        def color_cal(v):
            return VERDE if v >= META_CALIFICACION else (AMBAR if v >= META_CALIFICACION_CRITICA else ROJO)

        x = list(por_tramo.index)
        y = list(por_tramo["media"])
        err = list(1.96 * por_tramo["desv"] / np.sqrt(por_tramo["n"]))
        ns = list(por_tramo["n"])
        colores = [color_cal(v) for v in y]
        if len(cal_cancelados) >= MIN_RESPUESTAS:
            x.append("Cancelado")
            y.append(cal_cancelados.mean())
            err.append(1.96 * cal_cancelados.std() / np.sqrt(len(cal_cancelados)))
            ns.append(len(cal_cancelados))
            colores.append(GRIS)

        col_izq, col_der = st.columns(2)
        with col_izq:
            fig = go.Figure(go.Bar(
                x=x, y=y, marker_color=colores, text=[f"{v:.2f}".replace(".", ",") for v in y], textposition="outside",
                error_y=dict(type="data", array=err, color="#64748B", thickness=1.2), customdata=ns,
                hovertemplate="%{x}<br>Calificación: %{y:.2f}<br>Respuestas: %{customdata:,}<extra></extra>",
            ))
            fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE,
                          annotation_text="Meta 4,0", annotation_position="top right")
            fig.add_hline(y=META_CALIFICACION_CRITICA, line_dash="dot", line_color=ROJO,
                          annotation_text="Crítico 3,5", annotation_position="bottom right")
            fig.update_yaxes(range=[1, 5], title="Calificación (1 a 5)")
            fig.update_xaxes(title=None)
            fig.update_layout(title="Calificación promedio según los minutos de retraso")
            grafico(estilo(fig, alto=400, leyenda=False), "Calificación promedio (escala completa 1-5)", int(sum(ns)),
                    "Verde ≥ meta; ámbar entre 3,5 y 4,0; rojo < 3,5; gris = cancelado. Las barras de error son el intervalo de confianza del 95 %.")
        with col_der:
            distribucion = cal_operados.copy()
            distribucion["nivel"] = pd.cut(
                distribucion["calificacion_1a5"], bins=[0, 2, 3, 5],
                labels=["Insatisfecho (1-2)", "Neutral (3)", "Satisfecho (4-5)"],
            )
            dist = (
                distribucion.groupby(["tramo_retraso", "nivel"], observed=True).size()
                .groupby(level=0, observed=True).transform(lambda s: s / s.sum()).reset_index(name="porcentaje")
            )
            fig = px.bar(
                dist, x="tramo_retraso", y="porcentaje", color="nivel", title="Distribución de la calificación según el retraso",
                category_orders={"tramo_retraso": TRAMOS, "nivel": ["Satisfecho (4-5)", "Neutral (3)", "Insatisfecho (1-2)"]},
                color_discrete_map={"Satisfecho (4-5)": VERDE, "Neutral (3)": AMBAR, "Insatisfecho (1-2)": ROJO},
            )
            fig.update_yaxes(tickformat=".0%", title=None)
            fig.update_xaxes(title=None)
            fig.update_traces(hovertemplate="%{x}<br>%{y:.1%}<extra></extra>")
            grafico(estilo(fig, alto=400), "% de respuestas por nivel de satisfacción", len(cal_operados))

    # --- Tipo de irregularidad ------------------------------------------------
    subtitulo("Tipo de irregularidad y perfil del pasajero")
    col_izq, col_der = st.columns(2)
    with col_izq:
        irreg_cal = calificados[calificados["vuelo_irregular"]]
        por_tipo = irreg_cal.groupby(["motivo_irregularidad", "tipo_irregularidad"])["calificacion_1a5"].agg(["mean", "size"]).reset_index()
        por_tipo = por_tipo[por_tipo["size"] >= MIN_RESPUESTAS]
        if por_tipo.empty:
            st.info("Sin suficientes calificaciones de vuelos irregulares con los filtros actuales.")
        else:
            fig = px.bar(
                por_tipo, x="motivo_irregularidad", y="mean", color="tipo_irregularidad", barmode="group", text_auto=".2f",
                title="Calificación según la causa y el tipo de irregularidad", custom_data=["size"],
                color_discrete_map={"Cancelado": GRIS, "Retraso > 60 min": ROJO},
            )
            sin_irreg = calificados.loc[~calificados["vuelo_irregular"], "calificacion_1a5"].mean()
            fig.add_hline(y=sin_irreg, line_dash="dot", line_color=AZUL,
                          annotation_text=f"Vuelos sin irregularidad: {fmt_num(sin_irreg, 2)}", annotation_position="top left")
            fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE)
            fig.update_traces(hovertemplate="%{x}<br>Calificación: %{y:.2f}<br>Respuestas: %{customdata[0]:,}<extra></extra>")
            fig.update_yaxes(range=[1, 5], title="Calificación (1 a 5)")
            fig.update_xaxes(title=None)
            grafico(estilo(fig, alto=400), "Calificación promedio (escala completa 1-5)", int(por_tipo["size"].sum()),
                    "Línea verde = meta; azul punteada = vuelos sin irregularidad.")
    with col_der:
        segmentos = {
            "Cliente frecuente": "cliente_frecuente",
            "Vuelo con conexión": "conexion",
            "Equipaje facturado": "equipaje_facturado",
            "Tarifa": "tarifa",
            "Canal de venta": "canal_venta",
        }
        eleccion = st.radio("Comparar la caída de satisfacción por:", list(segmentos), horizontal=True)
        columna_seg = segmentos[eleccion]
        seg = cal_operados.copy()
        if seg[columna_seg].dtype == bool:
            seg[columna_seg] = seg[columna_seg].map({True: "Sí", False: "No"})
        curva = seg.groupby(["tramo_retraso", columna_seg], observed=True)["calificacion_1a5"].agg(["mean", "size"]).reset_index()
        curva = curva[curva["size"] >= MIN_RESPUESTAS]
        fig = px.line(
            curva, x="tramo_retraso", y="mean", color=columna_seg, markers=True, custom_data=["size"],
            title=f"Calificación según el retraso, por {eleccion.lower()}",
            category_orders={"tramo_retraso": TRAMOS},
            color_discrete_sequence=[AZUL, AMBAR, "#7B8794", "#5DADE2"],
        )
        fig.update_traces(hovertemplate="%{x}<br>Calificación: %{y:.2f}<br>Respuestas: %{customdata[0]:,}<extra></extra>")
        fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE)
        fig.update_yaxes(range=[1, 5], title="Calificación")
        fig.update_xaxes(title=None)
        fig.update_layout(legend_title_text=eleccion)
        grafico(estilo(fig, alto=370), "Calificación promedio (escala completa 1-5)", len(seg),
                f"Se omiten puntos con menos de {MIN_RESPUESTAS} respuestas. Línea verde = meta.")

    # --- Tendencia mensual de la calificación ---------------------------------
    fig = go.Figure()
    fig.add_scatter(
        x=mensual["mes_inicio"], y=mensual["calificacion"], mode="lines+markers", line=dict(color=AZUL, width=2.5),
        hovertemplate="%{x|%m/%Y}<br>Calificación: %{y:.2f}<extra></extra>",
    )
    fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE, annotation_text="Meta 4,0", annotation_position="bottom left")
    fig.update_yaxes(range=[3, 5], title=None)
    fig.update_xaxes(title=None)
    fig.update_layout(title="Calificación promedio mensual")
    grafico(estilo(fig, alto=300, leyenda=False), "Calificación promedio", len(calificados),
            "Eje truncado (3 a 5) para que se vea la tendencia; la meta propuesta es 4,0.")

# ===========================================================================
# 3 · COMERCIAL - ¿Dónde se concentran los ingresos y cuánto está expuesto?
# ===========================================================================
with tab_comercial:
    seccion("Pregunta 3 · Comercial", "¿Dónde se concentran los ingresos y cuánto de ese ingreso está expuesto a la impuntualidad?")

    top3_pct = top3["ingresos"].sum() / k.ingresos if k.ingresos else np.nan
    fila_kpis([
        kpi("Ingresos totales", fmt_millones(k.ingresos), "COP · vuelos operados", "neutral"),
        kpi("Ingreso expuesto a impuntualidad", fmt_millones(k.expuesto),
            f"{fmt_pct(pct_expuesto)} del ingreso salió con más de 15 min de retraso", "alerta"),
        kpi("Concentración en 3 rutas", fmt_pct(top3_pct, 0), lista(top3["ruta"]), "neutral"),
        kpi("Tiquete promedio", f"${fmt_num(operados['precio_tiquete_cop'].mean())}", "COP por segmento operado", "neutral"),
    ])

    comparacion = (
        "proporcional a su peso en vuelos: el ingreso no está más expuesto que el resto"
        if abs(pct_expuesto - pct_no_puntuales) < 0.02
        else ("mayor que su peso en vuelos: se vende más en vuelos impuntuales" if pct_expuesto > pct_no_puntuales
              else "menor que su peso en vuelos: los vuelos impuntuales son de menor valor")
    )
    texto = (
        f"<b>{fmt_pct(pct_expuesto, 0)}</b> del ingreso viaja en vuelos impuntuales, {comparacion} "
        f"({fmt_pct(pct_no_puntuales, 0)} de los vuelos operados). "
        f"Las 3 rutas que más facturan ({lista(top3['ruta'])}) suman <b>{fmt_pct(top3_pct, 0)}</b> del ingreso."
    )
    por_tarifa = df.groupby("tarifa").agg(pasajeros=("id_segmento_vuelo", "size"), ingresos=("ingreso_efectivo_cop", "sum")).reindex(ORDEN_TARIFA).dropna()
    if "Ejecutiva" in por_tarifa.index and por_tarifa["pasajeros"].sum():
        e = por_tarifa.loc["Ejecutiva"]
        texto += (f" La tarifa Ejecutiva es el {fmt_pct(e.pasajeros / por_tarifa['pasajeros'].sum(), 0)} de los pasajeros "
                  f"y aporta el {fmt_pct(e.ingresos / por_tarifa['ingresos'].sum(), 0)} del ingreso.")
    hallazgo(texto, f"ingreso = precio de vuelos operados; expuesto = ingreso de vuelos con retraso > 15 min; {fmt_num(len(operados))} vuelos operados.",
             "alerta" if pct_expuesto > pct_no_puntuales + 0.02 else "neutral")

    # --- Matriz de priorización + exposición por dimensión --------------------
    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        colores_prio = {
            "Intervenir: alto ingreso, baja puntualidad": ROJO,
            "Proteger: alto ingreso, puntualidad sobre el promedio": AZUL,
            "Seguimiento: menor ingreso": GRIS,
            "Muestra pequeña": "#E2E8F0",
        }
        t = tabla.assign(ingresos_m=tabla["ingresos"] / 1e6)
        fig = px.scatter(
            t, x="puntualidad", y="ingresos_m", size="vuelos", color="prioridad", color_discrete_map=colores_prio,
            size_max=28, custom_data=["ruta", "vuelos", "cancelacion", "calificacion"],
            title="Matriz de priorización de rutas: ingresos × puntualidad × vuelos",
            category_orders={"prioridad": list(colores_prio)},
        )
        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Ingresos: $%{y:,.0f} M<br>Puntualidad: %{x:.1%}"
            "<br>Vuelos: %{customdata[1]:,}<br>Cancelación: %{customdata[2]:.1%}<br>Calificación: %{customdata[3]:.2f}<extra></extra>",
            marker=dict(line=dict(color="white", width=1), opacity=0.85),
        )
        fig.add_vline(x=k.puntualidad, line_dash="dot", line_color="#64748B", annotation_text="Puntualidad promedio", annotation_position="top")
        if pd.notna(mediana_ingresos):
            fig.add_hline(y=mediana_ingresos / 1e6, line_dash="dot", line_color="#64748B", annotation_text="Ingreso mediano", annotation_position="top left")
        fig.update_xaxes(tickformat=".0%", title="Puntualidad de la ruta")
        fig.update_yaxes(title="Ingresos (millones de COP)")
        n_prio = len(prioritarias)
        grafico(estilo(fig, alto=470), "Cada burbuja es una ruta; tamaño = número de vuelos", len(df),
                f"{n_prio} ruta(s) en «Intervenir» (arriba a la izquierda). Rutas con menos de {MIN_VUELOS} vuelos se marcan como muestra pequeña.")
    with col_der:
        dim_exp = st.selectbox("Ver el ingreso expuesto por:", ["Tarifa", "Canal de venta", "Aeropuerto de origen", "Franja de salida"])
        col_exp = DIMENSIONES[dim_exp]
        exp = operados.assign(
            estado=np.where(operados["vuelo_puntual"] == 1, "Ingreso en vuelos puntuales", "Ingreso expuesto (retraso > 15 min)")
        ).groupby([col_exp, "estado"], observed=True)["ingreso_efectivo_cop"].sum().div(1e6).reset_index(name="ingresos_m")
        orden = exp.groupby(col_exp, observed=True)["ingresos_m"].sum().sort_values(ascending=False).index.tolist()
        fig = px.bar(
            exp, x="ingresos_m", y=col_exp, color="estado", orientation="h", barmode="stack", text_auto=",.0f",
            title=f"Ingreso puntual vs. expuesto por {dim_exp.lower()}",
            color_discrete_map={"Ingreso en vuelos puntuales": VERDE, "Ingreso expuesto (retraso > 15 min)": ROJO},
            category_orders={col_exp: orden},
        )
        fig.update_traces(hovertemplate="%{y}<br>%{fullData.name}: $%{x:,.0f} M<extra></extra>")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None, autorange="reversed")
        grafico(estilo(fig, alto=470), "Millones de COP", len(operados))

    # --- Mapa + peso de la tarifa ---------------------------------------------
    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        fig = go.Figure()
        maximo = tabla["ingresos"].max()
        for _, r in tabla.iterrows():
            fig.add_trace(go.Scattergeo(
                lon=[r.longitud_origen, r.longitud_destino], lat=[r.latitud_origen, r.latitud_destino],
                mode="lines", line=dict(width=0.5 + 6 * r.ingresos / maximo, color=AZUL), opacity=0.55,
                hoverinfo="text", showlegend=False,
                text=f"{r.ruta}<br>Ingresos: {fmt_millones(r.ingresos)}<br>Vuelos: {fmt_num(r.vuelos)}",
            ))
        aeropuertos = operados.groupby(["origen", "ciudad_origen", "latitud_origen", "longitud_origen"]).agg(
            ingresos=("ingreso_efectivo_cop", "sum")
        ).reset_index()
        fig.add_trace(go.Scattergeo(
            lon=aeropuertos["longitud_origen"], lat=aeropuertos["latitud_origen"], text=aeropuertos["origen"],
            mode="markers+text", textposition="middle right",
            marker=dict(size=8 + 30 * aeropuertos["ingresos"] / aeropuertos["ingresos"].max(), color=AZUL, line=dict(color="white", width=1)),
            customdata=np.stack([aeropuertos["ciudad_origen"], aeropuertos["ingresos"].map(fmt_millones)], axis=-1),
            hovertemplate="%{customdata[0]} (%{text})<br>Ingresos con origen aquí: %{customdata[1]}<extra></extra>",
            showlegend=False,
        ))
        fig.update_geos(
            lataxis_range=[2, 12.5], lonaxis_range=[-83, -68], showcountries=True, countrycolor="#999",
            showland=True, landcolor="#F2F2F2", showocean=True, oceancolor="#E8F0F8", resolution=50,
        )
        fig.update_layout(title="Red de rutas: grosor = ingresos, tamaño del punto = ingresos por origen")
        grafico(estilo(fig, alto=430, leyenda=False), "Millones de COP", len(operados),
                "El mapa muestra dónde está el ingreso; la tabla de abajo ayuda a decidir dónde intervenir.")
    with col_der:
        participacion = pd.DataFrame({
            "tarifa": list(por_tarifa.index) * 2,
            "medida": ["% de pasajeros"] * len(por_tarifa) + ["% de ingresos"] * len(por_tarifa),
            "valor": list(por_tarifa["pasajeros"] / por_tarifa["pasajeros"].sum()) + list(por_tarifa["ingresos"] / por_tarifa["ingresos"].sum()),
        })
        fig = px.bar(
            participacion, x="tarifa", y="valor", color="medida", barmode="group", text_auto=".0%",
            title="Peso de cada tarifa: pasajeros vs. ingresos",
            color_discrete_map={"% de pasajeros": GRIS, "% de ingresos": AZUL},
        )
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>%{y:.1%}<extra></extra>")
        grafico(estilo(fig, alto=430), "% del total de la selección", len(df))

    # --- Ranking de oportunidades (tabla ordenable) ---------------------------
    subtitulo("Ranking de rutas con oportunidad de mejora (clic en el encabezado para ordenar)")
    vista = tabla.assign(
        ingresos_m=tabla["ingresos"] / 1e6, expuesto_m=tabla["expuesto"] / 1e6,
        punt=tabla["puntualidad"] * 100, canc=tabla["cancelacion"] * 100,
    ).sort_values("expuesto_m", ascending=False)[
        ["ruta", "prioridad", "ingresos_m", "expuesto_m", "punt", "canc", "calificacion", "ocupacion", "vuelos"]
    ]
    st.dataframe(
        vista, hide_index=True, height=380, **ANCHO,
        column_config={
            "ruta": "Ruta", "prioridad": "Prioridad",
            "ingresos_m": st.column_config.NumberColumn("Ingresos (M COP)", format="%.0f"),
            "expuesto_m": st.column_config.NumberColumn("Ingreso expuesto (M COP)", format="%.0f"),
            "punt": st.column_config.NumberColumn("Puntualidad (%)", format="%.1f"),
            "canc": st.column_config.NumberColumn("Cancelación (%)", format="%.1f"),
            "calificacion": st.column_config.NumberColumn("Calificación", format="%.2f"),
            "ocupacion": st.column_config.NumberColumn("Ocupación (%)", format="%.1f"),
            "vuelos": st.column_config.NumberColumn("Vuelos", format="%d"),
        },
    )
    st.caption(
        f"Unidad: millones de COP y porcentajes · n = {fmt_num(len(df))} vuelos · {PERIODO}. "
        f"«Intervenir» = ingreso ≥ mediana ({fmt_millones(mediana_ingresos)}) y puntualidad bajo el promedio de la selección ({fmt_pct(k.puntualidad)}). "
        f"Se exige un mínimo de {MIN_VUELOS} vuelos por ruta."
    )

    # --- Ocupación -------------------------------------------------------------
    fig = go.Figure()
    fig.add_scatter(
        x=mensual["mes_inicio"], y=mensual["ocupacion"], mode="lines+markers", line=dict(color=AZUL, width=2.5),
        hovertemplate="%{x|%m/%Y}<br>Ocupación: %{y:.1f} %<extra></extra>",
    )
    fig.add_hline(y=META_OCUPACION, line_dash="dash", line_color=VERDE, annotation_text="Meta 80 %", annotation_position="bottom left")
    fig.update_yaxes(range=[60, 100], ticksuffix=" %", title=None)
    fig.update_xaxes(title=None)
    fig.update_layout(title="Ocupación promedio mensual")
    grafico(estilo(fig, alto=300, leyenda=False), "% de asientos ocupados en vuelos operados", len(operados),
            "Eje truncado (60 a 100 %) para que se vea la tendencia; la meta propuesta es 80 %.")

# ===========================================================================
# CONCLUSIONES (se recalculan con los filtros)
# ===========================================================================
with tab_conclusiones:
    seccion("Conclusiones", "Síntesis para la gerencia")
    st.caption("Todo el texto se recalcula con los filtros de la barra lateral; si una condición deja de cumplirse, la conclusión cambia.")

    def bloque(titulo, puntos, estado):
        items = "".join(f"<li>{p}</li>" for p in puntos)
        return f'<div class="concl" style="--c:{ESTADOS[estado][0]}"><h3>{titulo}</h3><ul>{items}</ul></div>'

    # Operación
    if localizados:
        foco = lista(f"<b>{idx}</b>" for _, idx, _ in sorted(localizados, key=lambda x: x[2]["brecha"])[:3])
        p_loc = f"Hay focos localizados: {foco}."
    elif k.puntualidad < META_PUNTUALIDAD and diag:
        p_loc = (f"Ningún grupo se aparta del resto (máx. {fmt_pp(brecha_max)} entre mejor y peor): <b>problema de toda la operación</b>.")
    else:
        p_loc = "No se detectan focos localizados."
    op_pts = [
        f"Puntualidad de <b>{fmt_pct(k.puntualidad)}</b>, {fmt_pp(k.puntualidad - META_PUNTUALIDAD)} {'bajo' if k.puntualidad < META_PUNTUALIDAD else 'sobre'} la meta propuesta.",
        p_loc,
    ]
    if not irregulares.empty:
        op_pts.append(
            f"<b>{fmt_pct(k.irregularidad)}</b> de vuelos con irregularidad; causa principal: {reparto.index[0]} "
            f"({fmt_pct(reparto.iloc[0], 0)}){', sin una causa dominante' if reparto.iloc[0] < 0.40 else ''}."
        )

    # Experiencia
    ex_pts = [f"Calificación promedio <b>{fmt_num(k.calificacion, 2)}</b> (meta {fmt_num(META_CALIFICACION, 1)})."]
    if len(por_tramo) >= 2:
        if not np.isnan(pendiente_15):
            ex_pts.append(f"Cada 15 min de retraso restan unos <b>{fmt_num(abs(pendiente_15), 2)}</b> puntos.")
        if tramo_alerta is not None:
            ex_pts.append(f"Bajo la meta desde <b>{texto_umbral(tramo_alerta)}</b>"
                          + (f"; nivel crítico (&lt; 3,5) con <b>{texto_umbral(tramo_critico)}</b>." if tramo_critico is not None else "."))
        else:
            ex_pts.append("Ningún tramo de retraso cae bajo la meta.")

    # Comercial
    co_pts = [
        f"Ingresos de <b>{fmt_millones(k.ingresos)}</b> COP con ocupación de <b>{fmt_num(k.ocupacion, 1)} %</b>.",
        f"<b>{fmt_pct(pct_expuesto, 0)}</b> del ingreso viaja en vuelos impuntuales ({fmt_pct(pct_no_puntuales, 0)} de los vuelos).",
        f"Las 3 rutas de mayor ingreso ({lista(top3['ruta'])}) concentran el <b>{fmt_pct(top3_pct, 0)}</b>.",
    ]

    st.markdown(
        '<div class="concl-grid">'
        + bloque("Operación", op_pts, "ok" if k.puntualidad >= META_PUNTUALIDAD else "alerta")
        + bloque("Experiencia del pasajero", ex_pts, "ok" if k.calificacion >= META_CALIFICACION and tramo_alerta is None else "precaucion")
        + bloque("Comercial", co_pts, "neutral")
        + "</div>",
        unsafe_allow_html=True,
    )

    seccion("Plan de acción", "Decisiones que habilita este tablero")
    acciones = []
    if localizados:
        foco = lista(str(idx) for _, idx, _ in sorted(localizados, key=lambda x: x[2]["brecha"])[:3])
        acciones.append(f"**Intervenir primero en los focos detectados ({foco})**: revisar rotación en tierra, mantenimiento y coordinación en esos grupos.")
    elif k.puntualidad < META_PUNTUALIDAD:
        acciones.append(
            "**Plan de puntualidad de toda la red**, no por ruta: tiempos de rotación en tierra, mantenimiento preventivo y "
            "coordinación con aeropuertos, con una meta intermedia definida por la gerencia y seguimiento mensual en este tablero."
        )
    if tramo_alerta is not None:
        acciones.append(
            f"**Protocolo de retraso desde {texto_umbral(tramo_alerta)}**: información proactiva, compensación y reacomodación "
            f"antes de que la espera cruce el punto donde la calificación queda bajo {fmt_num(META_CALIFICACION, 1)}."
        )
    if len(prioritarias):
        acciones.append(
            f"**Priorizar las rutas «Intervenir»** ({lista(prioritarias.head(3)['ruta'])}), que combinan alto ingreso y puntualidad bajo el promedio, "
            "en la asignación de aeronaves de reserva y tripulaciones."
        )
    if not acciones:
        acciones.append("Con los filtros actuales no se detectan brechas que exijan acción inmediata; mantener el seguimiento mensual.")
    st.markdown("\n".join(f"{i}. {a}" for i, a in enumerate(acciones, 1)))

# ===========================================================================
# DATOS Y METODOLOGÍA
# ===========================================================================
with tab_metodo:
    seccion("Componente técnico", "Datos, preparación y modelo")

    # --- Calidad de los datos --------------------------------------------------
    subtitulo("Calidad de los datos")
    perfil = perfil_calidad()
    if perfil is None:
        st.info("Coloque 08_aerolinea_regional.csv junto a app.py para ver el perfil del archivo original.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Registros originales", fmt_num(perfil["registros"]))
        c2.metric("Registros finales", fmt_num(len(datos)))
        c3.metric("Duplicados", fmt_num(perfil["dup_id"] + perfil["dup_fila"]), help=f"IDs repetidos: {perfil['dup_id']} · filas repetidas sin ID: {perfil['dup_fila']}")
        faltantes = perfil["faltantes"]
        c4.metric("Columnas con faltantes", len(faltantes),
                  help="; ".join(f"{c}: {n:,} ({n / perfil['registros']:.1%})" for c, n in faltantes.items()))
        c5.metric("Registros excluidos", fmt_num(perfil["registros"] - len(datos)))
        st.table(pd.DataFrame(
            [
                ("motivo_irregularidad", f"{faltantes.get('motivo_irregularidad', 0):,} vacíos", "Se rellena con «Sin irregularidad»: el motivo solo se registra en cancelados o retrasos > 60 min."),
                ("calificacion_1a5", f"{faltantes.get('calificacion_1a5', 0):,} vacíos", "Se conserva como nulo; los promedios usan solo calificaciones registradas."),
                ("retraso_salida_min", f"{perfil['cancelados_con_retraso']:,} cancelados con retraso", "Se lleva a nulo: un vuelo cancelado no tiene retraso de salida."),
                ("precio_tiquete_cop", "Atípicos por IQR", "Se conservan: corresponden a las tarifas Ejecutiva y Flexible."),
            ],
            columns=["Variable", "Hallazgo", "Regla aplicada"],
        ).set_index("Variable"))
    st.caption(f"Los datos cubren vuelos hasta el {fecha_datos:%d/%m/%Y}.")

    with st.expander("Origen de los datos", expanded=True):
        st.markdown(
            "- Dataset **sintético y anonimizado** asignado al grupo 8: `08_aerolinea_regional.csv`.\n"
            f"- **{fmt_num(len(datos))} registros**, del {datos['fecha'].min():%d/%m/%Y} al {datos['fecha'].max():%d/%m/%Y}.\n"
            "- **Unidad de observación:** un segmento de vuelo vendido (`id_segmento_vuelo`).\n"
            f"- {datos['origen'].nunique()} aeropuertos, {datos['ruta'].nunique()} rutas, {datos['tarifa'].nunique()} tarifas, "
            f"{datos['canal_venta'].nunique()} canales de venta y {datos['franja_salida'].nunique()} franjas de salida."
        )

    with st.expander("Registro completo de la limpieza"):
        registro = CARPETA / "registro_limpieza.txt"
        if registro.exists():
            st.code(registro.read_text(encoding="utf-8"), language=None)
        else:
            st.info("Ejecute preparacion_datos.py para generar el registro de limpieza.")

    with st.expander("Modelo de datos (esquema estrella)"):
        st.markdown(
            "La tabla de hechos `fact_vuelos` (un registro por segmento) se relaciona 1 a muchos con seis dimensiones. "
            "Al iniciar, la aplicación une las tablas para construir la vista analítica."
        )
        st.graphviz_chart(
            f"""
            digraph {{
                rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
                fact [label="fact_vuelos\\n{fmt_num(len(datos))} filas", fillcolor="#1F4E79", fontcolor="white"];
                node [fillcolor="#EEF3F9"];
                cal [label="dim_calendario"]; ruta [label="dim_ruta"]; tar [label="dim_tarifa"];
                can [label="dim_canal"]; fra [label="dim_franja"]; mot [label="dim_motivo"];
                cal -> fact [label="id_fecha"]; ruta -> fact [label="id_ruta"]; tar -> fact [label="id_tarifa"];
                can -> fact [label="id_canal"]; fra -> fact [label="id_franja"]; mot -> fact [label="id_motivo"];
            }}
            """
        )

    with st.expander("Definición de los KPI (una sola fórmula por indicador)"):
        st.table(pd.DataFrame(
            [
                ("Puntualidad", "Vuelos operados con retraso ≤ 15 min ÷ vuelos operados", "≥ 80 %"),
                ("Tasa de cancelación", "Vuelos cancelados ÷ total de vuelos", "≤ 2 %"),
                ("Vuelos con irregularidad", "Vuelos cancelados o con retraso > 60 min ÷ total de vuelos", "≤ 10 %"),
                ("Calificación promedio", "Promedio de calificacion_1a5 (sin contar vacíos)", "≥ 4,0"),
                ("Ingresos totales", "Suma de ingreso_efectivo_cop (= precio_tiquete_cop si el vuelo operó, 0 si fue cancelado)", "Referencia"),
                ("Ingreso expuesto", "ingreso_efectivo_cop de vuelos operados con retraso > 15 min", "Referencia"),
                ("Ocupación promedio", "Promedio de ocupacion_pct de vuelos operados", "≥ 80 %"),
            ],
            columns=["KPI", "Fórmula", "Meta propuesta"],
        ).set_index("KPI"))
        st.caption(
            "Las metas son referencias propuestas por el grupo para colorear los indicadores; no son estándares universales "
            "ni provienen de una norma. El umbral de 15 min para puntualidad es una convención habitual del sector."
        )

    with st.expander("Criterios de interpretación de los hallazgos"):
        st.markdown(
            f"- **Foco localizado:** grupo con al menos {MIN_VUELOS} vuelos operados, ≥ {fmt_num(BRECHA_LOCALIZADA * 100, 0)} p.p. por debajo del resto "
            f"de la operación y diferencia estadísticamente clara (|z| ≥ {fmt_num(Z_LOCALIZADA, 0)}). Si ningún grupo cumple, la baja puntualidad se declara de toda la operación.\n"
            f"- **Umbral de satisfacción:** primer tramo de 15 min de retraso cuyo promedio queda bajo {fmt_num(META_CALIFICACION, 1)} (meta) o bajo "
            f"{fmt_num(META_CALIFICACION_CRITICA, 1)} (nivel crítico, criterio propuesto). Se exigen al menos {MIN_RESPUESTAS} respuestas por tramo.\n"
            f"- **Alertas mensuales:** puntualidad −{fmt_num(ALERTA_PUNTUALIDAD * 100, 0)} p.p., cancelación +{fmt_num(ALERTA_CANCELACION * 100, 0)} p.p. "
            f"o calificación −{fmt_num(ALERTA_CALIFICACION, 2)} frente al mes anterior.\n"
            f"- **Prioridad de ruta:** «Intervenir» si el ingreso es ≥ la mediana y la puntualidad está bajo el promedio de la selección."
        )
        st.caption("Limitaciones: datos sintéticos; la calificación solo existe para los pasajeros que respondieron; los hallazgos describen asociaciones, no causalidad.")

    with st.expander("Datos filtrados"):
        st.dataframe(
            df.drop(columns=[c for c in df.columns if c.startswith("id_") and c != "id_segmento_vuelo"]),
            height=350, **ANCHO,
        )