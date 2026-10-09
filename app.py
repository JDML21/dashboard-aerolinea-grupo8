"""
Dashboard de operaciones y experiencia del pasajero
Grupo 8 - Aerolínea de operación nacional y regional

Ejecutar:  streamlit run app.py
Datos:     carpeta modelo/ (generada por preparacion_datos.py)
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Aerolínea · Operación y Experiencia", page_icon=":material/flight:", layout="wide")

CARPETA = Path(__file__).parent
CARPETA_MODELO = CARPETA / "modelo"

# Paleta semántica: cada color tiene un único significado en todo el dashboard
AZUL = "#1F4E79"    # dato principal / neutro
GRIS = "#B8C0CC"    # contexto, segmentos sin alerta
ROJO = "#C0392B"    # alerta: no cumple la meta
AMBAR = "#E0A030"   # precaución
VERDE = "#2E8B57"   # cumple la meta
ESCALA_SEMAFORO = [ROJO, AMBAR, VERDE]

# Metas de referencia para colorear los KPI
META_PUNTUALIDAD = 0.80     # estándar de la industria aérea
META_CANCELACION = 0.02
META_IRREGULARIDAD = 0.10
META_CALIFICACION = 4.0
META_OCUPACION = 80.0

ORDEN_RANGO = ["Sin retraso", "1-15 min", "16-45 min", "46-90 min", "Más de 90 min", "Cancelado"]
ORDEN_FRANJA = ["Madrugada", "Mañana", "Tarde", "Noche"]
ORDEN_TARIFA = ["Básica", "Flexible", "Ejecutiva"]


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------
def fmt_num(x, dec=0):
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x, dec=1):
    return f"{fmt_num(x * 100, dec)} %"


def fmt_millones(x):
    return f"${fmt_num(x / 1e6)} M"


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


def grafico(fig):
    st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False, "locale": "es"})


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
            border-radius: 16px; padding: 28px 32px; color: #fff; margin-bottom: 18px;
            box-shadow: 0 10px 30px rgba(11, 31, 58, .18);
        }}
        .hero .eyebrow {{ font-size: 12px; letter-spacing: .14em; text-transform: uppercase; opacity: .75; font-weight: 600; }}
        .hero h1 {{ font-size: clamp(24px, 3.2vw, 38px); font-weight: 800; margin: 6px 0 14px; line-height: 1.15; color: #fff; padding: 0; }}
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
        .seccion {{ margin: 18px 0 8px; }}
        .seccion .eyebrow {{ font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: {AZUL}; font-weight: 700; }}
        .seccion h2 {{ font-size: clamp(18px, 2vw, 24px); font-weight: 700; color: #0F172A; margin: 4px 0 0; padding: 0; }}

        /* Tarjetas KPI */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin: 6px 0 18px; }}
        .kpi {{ background: #fff; border: 1px solid #E2E8F0; border-top: 4px solid var(--c); border-radius: 12px;
            padding: 16px 18px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
        .kpi .lbl {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #64748B; font-weight: 600; }}
        .kpi .val {{ font-size: clamp(26px, 2.4vw, 32px); font-weight: 800; color: var(--c); line-height: 1.2; margin: 6px 0 8px; }}
        .kpi .foot {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }}
        .kpi .det {{ font-size: 12.5px; color: #475569; }}
        .pill {{ font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap;
            color: var(--c); background: color-mix(in srgb, var(--c) 12%, white); }}

        /* Hallazgos */
        .hallazgo {{ background: #F1F5FB; border-left: 4px solid {AZUL}; border-radius: 10px; padding: 12px 16px;
            margin: 4px 0 18px; font-size: 14.5px; color: #1E293B; line-height: 1.55; }}
        .hallazgo .tag {{ display: block; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
            color: {AZUL}; margin-bottom: 4px; }}

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


def kpi(titulo, valor, detalle, estado):
    color, etiqueta = ESTADOS[estado]
    return (
        f'<div class="kpi" style="--c:{color}"><div class="lbl">{titulo}</div><div class="val">{valor}</div>'
        f'<div class="foot"><span class="det">{detalle}</span><span class="pill">{etiqueta}</span></div></div>'
    )


def fila_kpis(tarjetas):
    st.markdown(f'<div class="kpi-grid">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def seccion(etiqueta, pregunta):
    st.markdown(
        f'<div class="seccion"><div class="eyebrow">{etiqueta}</div><h2>{pregunta}</h2></div>',
        unsafe_allow_html=True,
    )


def hallazgo(texto):
    st.markdown(f'<div class="hallazgo"><span class="tag">Hallazgo</span>{texto}</div>', unsafe_allow_html=True)


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
    return df


def resumir(d):
    """KPI principales para un subconjunto de vuelos."""
    operados = d[~d["vuelo_cancelado"]]
    return pd.Series(
        {
            "vuelos": len(d),
            "puntualidad": operados["vuelo_puntual"].mean(),
            "cancelacion": d["vuelo_cancelado"].mean(),
            "irregularidad": d["vuelo_irregular"].mean(),
            "calificacion": d["calificacion_1a5"].mean(),
            "ingresos": d["ingreso_efectivo_cop"].sum(),
            "ocupacion": operados["ocupacion_pct"].mean(),
        }
    )


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
    datos["fecha"].dt.date.between(inicio, fin)
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
    <span style="background:{VERDE}"></span>Cumple la meta<br>
    <span style="background:{AMBAR}"></span>Precaución<br>
    <span style="background:{ROJO}"></span>Bajo la meta<br>
    <span style="background:{AZUL}"></span>Dato de referencia</div>""",
    unsafe_allow_html=True,
)

if df.empty:
    st.warning("No hay vuelos para la combinación de filtros seleccionada. Ajuste los filtros.")
    st.stop()

operados = df[~df["vuelo_cancelado"]]
k = resumir(df)

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="hero">
        <div class="eyebrow">Grupo 8 · Aerolínea de operación nacional y regional</div>
        <h1>Operación y experiencia del pasajero</h1>
        <div class="chips">
            <span class="chip"><b>Audiencia</b>Gerencia de Operaciones y Experiencia del Pasajero</span>
            <span class="chip"><b>Periodo</b>{inicio:%d/%m/%Y} – {fin:%d/%m/%Y}</span>
            <span class="chip"><b>Vuelos</b>{fmt_num(len(df))} de {fmt_num(len(datos))}</span>
            <span class="chip"><b>Fuente</b>datos sintéticos y anonimizados</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_resumen, tab_operacion, tab_experiencia, tab_comercial, tab_conclusiones, tab_metodo = st.tabs(
    [
        "Resumen",
        "Operación",
        "Experiencia del pasajero",
        "Comercial",
        "Conclusiones",
        "Datos y metodología",
    ]
)

# ===========================================================================
# 1. RESUMEN
# ===========================================================================
with tab_resumen:
    seccion("Panorama general", "Indicadores clave del periodo seleccionado")
    fila_kpis([
        kpi("Puntualidad (≤ 15 min)", fmt_pct(k.puntualidad), f"Meta: {fmt_pct(META_PUNTUALIDAD, 0)}",
            "ok" if k.puntualidad >= META_PUNTUALIDAD else "alerta"),
        kpi("Tasa de cancelación", fmt_pct(k.cancelacion), f"Meta: ≤ {fmt_pct(META_CANCELACION, 0)}",
            "ok" if k.cancelacion <= META_CANCELACION else "alerta"),
        kpi("Vuelos con irregularidad", fmt_pct(k.irregularidad), f"Meta: ≤ {fmt_pct(META_IRREGULARIDAD, 0)}",
            "ok" if k.irregularidad <= META_IRREGULARIDAD else "alerta"),
    ])
    fila_kpis([
        kpi("Calificación promedio", f"{fmt_num(k.calificacion, 2)} / 5", f"Meta: ≥ {fmt_num(META_CALIFICACION, 1)}",
            "ok" if k.calificacion >= META_CALIFICACION else "alerta"),
        kpi("Ingresos totales", fmt_millones(k.ingresos), f"COP · {fmt_num(len(operados))} segmentos operados", "neutral"),
        kpi("Ocupación promedio", f"{fmt_num(k.ocupacion, 1)} %", f"Meta: ≥ {fmt_num(META_OCUPACION, 0)} %",
            "ok" if k.ocupacion >= META_OCUPACION else "alerta"),
    ])

    mensual = df.groupby("mes_inicio").apply(resumir, include_groups=False).reset_index()

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        fig = go.Figure()
        fig.add_scatter(
            x=mensual["mes_inicio"], y=mensual["puntualidad"], mode="lines+markers",
            line=dict(color=ROJO, width=2.5), name="Puntualidad",
            hovertemplate="%{x|%m/%Y}<br>Puntualidad: %{y:.1%}<extra></extra>",
        )
        fig.add_hline(
            y=META_PUNTUALIDAD, line_dash="dash", line_color=VERDE,
            annotation_text=f"Meta {fmt_pct(META_PUNTUALIDAD, 0)}", annotation_position="top left",
        )
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        fig.update_layout(title="Puntualidad mensual frente a la meta")
        grafico(estilo(fig, leyenda=False))
    with col_der:
        fig = go.Figure()
        fig.add_scatter(
            x=mensual["mes_inicio"], y=mensual["calificacion"], mode="lines+markers",
            line=dict(color=AZUL, width=2.5), name="Calificación",
            hovertemplate="%{x|%m/%Y}<br>Calificación: %{y:.2f}<extra></extra>",
        )
        fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE,
                      annotation_text="Meta 4,0", annotation_position="bottom left")
        fig.update_yaxes(range=[3.5, 4.5])
        fig.update_layout(title="Calificación promedio mensual")
        grafico(estilo(fig, leyenda=False))

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        mensual["ingresos_m"] = mensual["ingresos"] / 1e6
        fig = px.bar(mensual, x="mes_inicio", y="ingresos_m", title="Ingresos mensuales (millones de COP)",
                     color_discrete_sequence=[AZUL])
        fig.update_traces(hovertemplate="%{x|%m/%Y}<br>Ingresos: $%{y:,.0f} M<extra></extra>")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        grafico(estilo(fig, leyenda=False))
    with col_der:
        fig = go.Figure()
        fig.add_scatter(
            x=mensual["mes_inicio"], y=mensual["ocupacion"], mode="lines+markers",
            line=dict(color=AZUL, width=2.5),
            hovertemplate="%{x|%m/%Y}<br>Ocupación: %{y:.1f} %<extra></extra>",
        )
        fig.add_hline(y=META_OCUPACION, line_dash="dash", line_color=VERDE,
                      annotation_text="Meta 80 %", annotation_position="bottom left")
        fig.update_yaxes(range=[70, 90], ticksuffix=" %")
        fig.update_layout(title="Ocupación promedio mensual")
        grafico(estilo(fig, leyenda=False))

    hallazgo(
        f"La puntualidad se mantiene alrededor de <b>{fmt_pct(k.puntualidad, 0)}</b> durante todo el periodo, "
        f"muy por debajo de la meta de {fmt_pct(META_PUNTUALIDAD, 0)}. Ocupación y calificación son estables: "
        "el problema no es estacional, es estructural."
    )

# ===========================================================================
# 2. OPERACIÓN - P1: ¿La impuntualidad es localizada o de toda la operación?
# ===========================================================================
with tab_operacion:
    seccion("Pregunta 1 · Operación", "¿La baja puntualidad es un problema localizado o de toda la operación?")

    por_ruta = operados.groupby(["origen", "destino"]).agg(
        puntualidad=("vuelo_puntual", "mean"), vuelos=("vuelo_puntual", "size")
    ).reset_index()

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        matriz = por_ruta.pivot(index="origen", columns="destino", values="puntualidad")
        vuelos_ruta = por_ruta.pivot(index="origen", columns="destino", values="vuelos")
        fig = go.Figure(
            go.Heatmap(
                z=matriz.values, x=matriz.columns, y=matriz.index,
                customdata=vuelos_ruta.values,
                colorscale=ESCALA_SEMAFORO, zmin=0.3, zmax=META_PUNTUALIDAD,
                text=[["" if pd.isna(v) else f"{v * 100:.0f}%" for v in fila] for fila in matriz.values],
                texttemplate="%{text}",
                hovertemplate="Ruta %{y} → %{x}<br>Puntualidad: %{z:.1%}<br>Vuelos: %{customdata}<extra></extra>",
                colorbar=dict(title="Puntualidad", tickformat=".0%"),
            )
        )
        fig.update_layout(title="Puntualidad por ruta (origen × destino)")
        fig.update_xaxes(title="Destino", side="bottom")
        fig.update_yaxes(title="Origen", autorange="reversed")
        grafico(estilo(fig, alto=420))
    with col_der:
        por_franja = operados.groupby("franja_salida")["vuelo_puntual"].mean().reindex(ORDEN_FRANJA).reset_index()
        fig = px.bar(por_franja, x="franja_salida", y="vuelo_puntual", title="Puntualidad por franja de salida",
                     color_discrete_sequence=[ROJO], text_auto=".1%")
        fig.add_hline(y=META_PUNTUALIDAD, line_dash="dash", line_color=VERDE,
                      annotation_text="Meta", annotation_position="top left")
        fig.update_yaxes(tickformat=".0%", range=[0, 1], title=None)
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>Puntualidad: %{y:.1%}<extra></extra>")
        grafico(estilo(fig, alto=420, leyenda=False))

    rango_ruta = por_ruta.loc[por_ruta["vuelos"] >= 100, "puntualidad"]
    if not rango_ruta.empty:
        hallazgo(
            f"Entre rutas con al menos 100 vuelos, la puntualidad va de <b>{fmt_pct(rango_ruta.min())}</b> a "
            f"<b>{fmt_pct(rango_ruta.max())}</b>: ninguna ruta, franja ni aeropuerto se acerca a la meta. "
            "El problema es de toda la operación y requiere acciones de proceso, no de una ruta puntual."
        )

    col_izq, col_der = st.columns(2)
    with col_izq:
        irregulares = df[df["vuelo_irregular"]].copy()
        irregulares["tipo"] = np.where(irregulares["vuelo_cancelado"], "Cancelado", "Retraso > 60 min")
        por_motivo = irregulares.groupby(["motivo_irregularidad", "tipo"]).size().reset_index(name="vuelos")
        orden_motivo = por_motivo.groupby("motivo_irregularidad")["vuelos"].sum().sort_values().index.tolist()
        fig = px.bar(
            por_motivo, y="motivo_irregularidad", x="vuelos", color="tipo", orientation="h",
            title="Vuelos irregulares por causa",
            color_discrete_map={"Cancelado": ROJO, "Retraso > 60 min": AMBAR},
            category_orders={"motivo_irregularidad": orden_motivo[::-1]},
        )
        fig.update_xaxes(title="Vuelos")
        fig.update_yaxes(title=None)
        grafico(estilo(fig))
    with col_der:
        por_aeropuerto = df.groupby("origen").agg(
            cancelacion=("vuelo_cancelado", "mean"), vuelos=("vuelo_cancelado", "size")
        ).sort_values("cancelacion", ascending=False).reset_index()
        por_aeropuerto["estado"] = np.where(
            por_aeropuerto["cancelacion"] > META_CANCELACION, "Sobre la meta", "Dentro de la meta"
        )
        fig = px.bar(
            por_aeropuerto, x="origen", y="cancelacion", color="estado", text_auto=".1%",
            title="Tasa de cancelación por aeropuerto de origen",
            color_discrete_map={"Sobre la meta": ROJO, "Dentro de la meta": GRIS},
            custom_data=["vuelos"],
        )
        fig.add_hline(y=META_CANCELACION, line_dash="dash", line_color=VERDE,
                      annotation_text=f"Meta {fmt_pct(META_CANCELACION, 0)}", annotation_position="top right")
        fig.update_yaxes(tickformat=".1%", title=None)
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>Cancelación: %{y:.2%}<br>Vuelos: %{customdata[0]}<extra></extra>")
        grafico(estilo(fig))

    if not irregulares.empty:
        reparto = irregulares["motivo_irregularidad"].value_counts(normalize=True)
        hallazgo(
            f"Las causas de irregularidad están repartidas de forma pareja (entre {fmt_pct(reparto.min(), 0)} y "
            f"{fmt_pct(reparto.max(), 0)} cada una): no hay una sola causa dominante, por lo que el plan debe "
            "atacar mantenimiento, coordinación aeroportuaria, operación y contingencia climática en paralelo."
        )

# ===========================================================================
# 3. EXPERIENCIA - P2: ¿Cuánto cae la satisfacción con el retraso?
# ===========================================================================
with tab_experiencia:
    seccion("Pregunta 2 · Experiencia", "¿Cuánto cae la satisfacción según el retraso y a partir de qué umbral se vuelve crítica?")

    calificados = df.dropna(subset=["calificacion_1a5"])
    por_rango = calificados.groupby("rango_retraso").agg(
        calificacion=("calificacion_1a5", "mean"), vuelos=("calificacion_1a5", "size"),
    ).reindex(ORDEN_RANGO).dropna().reset_index()

    col_izq, col_der = st.columns(2)
    with col_izq:
        colores_rango = {
            "Sin retraso": VERDE, "1-15 min": VERDE, "16-45 min": AMBAR,
            "46-90 min": ROJO, "Más de 90 min": ROJO, "Cancelado": GRIS,
        }
        fig = px.bar(
            por_rango, x="rango_retraso", y="calificacion", color="rango_retraso", text_auto=".2f",
            title="Calificación promedio según el retraso", color_discrete_map=colores_rango,
            custom_data=["vuelos"],
        )
        fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=AZUL,
                      annotation_text="Meta 4,0", annotation_position="top right")
        fig.update_yaxes(range=[1, 5], title="Calificación (1 a 5)")
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>Calificación: %{y:.2f}<br>Respuestas: %{customdata[0]}<extra></extra>")
        grafico(estilo(fig, leyenda=False))
    with col_der:
        distribucion = calificados.copy()
        distribucion["nivel"] = pd.cut(
            distribucion["calificacion_1a5"], bins=[0, 2, 3, 5],
            labels=["Insatisfecho (1-2)", "Neutral (3)", "Satisfecho (4-5)"],
        )
        dist = (
            distribucion.groupby(["rango_retraso", "nivel"], observed=True).size()
            .groupby(level=0).transform(lambda s: s / s.sum()).reset_index(name="porcentaje")
        )
        fig = px.bar(
            dist, x="rango_retraso", y="porcentaje", color="nivel", title="Distribución de la calificación según el retraso",
            category_orders={"rango_retraso": ORDEN_RANGO, "nivel": ["Satisfecho (4-5)", "Neutral (3)", "Insatisfecho (1-2)"]},
            color_discrete_map={"Satisfecho (4-5)": VERDE, "Neutral (3)": AMBAR, "Insatisfecho (1-2)": ROJO},
        )
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>%{y:.1%}<extra></extra>")
        grafico(estilo(fig))

    valores = por_rango.set_index("rango_retraso")["calificacion"]
    if {"Sin retraso", "Más de 90 min"}.issubset(valores.index):
        hallazgo(
            f"La calificación cae de <b>{fmt_num(valores['Sin retraso'], 2)}</b> sin retraso a "
            f"<b>{fmt_num(valores['Más de 90 min'], 2)}</b> con más de 90 minutos. El umbral crítico está en los "
            "<b>45 minutos</b>: a partir de ahí el promedio cae por debajo de la meta de 4,0. "
            "Un vuelo cancelado se califica mejor que uno con retraso largo: la gestión de la espera pesa más que la cancelación."
        )

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        segmentos = {
            "Cliente frecuente": "cliente_frecuente",
            "Vuelo con conexión": "conexion",
            "Equipaje facturado": "equipaje_facturado",
            "Tarifa": "tarifa",
            "Canal de venta": "canal_venta",
        }
        eleccion = st.radio("Comparar la caída de satisfacción por:", list(segmentos), horizontal=True)
        columna_seg = segmentos[eleccion]
        seg = calificados[calificados["rango_retraso"] != "Cancelado"].copy()
        if seg[columna_seg].dtype == bool:
            seg[columna_seg] = seg[columna_seg].map({True: "Sí", False: "No"})
        curva = seg.groupby(["rango_retraso", columna_seg])["calificacion_1a5"].mean().reset_index()
        curva = curva.sort_values("rango_retraso", key=lambda c: c.map(ORDEN_RANGO.index))
        fig = px.line(
            curva, x="rango_retraso", y="calificacion_1a5", color=columna_seg, markers=True,
            title=f"Calificación según el retraso, por {eleccion.lower()}",
            category_orders={"rango_retraso": ORDEN_RANGO[:-1]},
            color_discrete_sequence=[AZUL, AMBAR, "#7B8794", "#5DADE2"],
        )
        fig.add_hline(y=META_CALIFICACION, line_dash="dash", line_color=VERDE)
        fig.update_yaxes(range=[2.5, 5], title="Calificación")
        fig.update_xaxes(title=None)
        fig.update_layout(legend_title_text=eleccion)
        grafico(estilo(fig, alto=380))
    with col_der:
        por_motivo_calif = (
            calificados.groupby("motivo_irregularidad")["calificacion_1a5"].mean().sort_values().reset_index()
        )
        por_motivo_calif["estado"] = np.where(
            por_motivo_calif["calificacion_1a5"] >= META_CALIFICACION, "Cumple la meta", "Bajo la meta"
        )
        fig = px.bar(
            por_motivo_calif, y="motivo_irregularidad", x="calificacion_1a5", color="estado", orientation="h",
            text_auto=".2f", title="Calificación según la causa de irregularidad",
            color_discrete_map={"Cumple la meta": VERDE, "Bajo la meta": ROJO},
        )
        fig.add_vline(x=META_CALIFICACION, line_dash="dash", line_color=AZUL)
        fig.update_xaxes(range=[1, 5], title="Calificación")
        fig.update_yaxes(title=None)
        grafico(estilo(fig, alto=430))

# ===========================================================================
# 4. COMERCIAL - P3: ¿Dónde se concentran los ingresos y cuánto está expuesto?
# ===========================================================================
with tab_comercial:
    seccion("Pregunta 3 · Comercial", "¿Dónde se concentran los ingresos y cuánto de ese ingreso está expuesto a la impuntualidad?")

    ingreso_expuesto = operados.loc[operados["vuelo_puntual"] == 0, "ingreso_efectivo_cop"].sum()
    ticket = operados["precio_tiquete_cop"].mean()
    fila_kpis([
        kpi("Ingresos totales", fmt_millones(k.ingresos), "COP, solo vuelos operados", "neutral"),
        kpi("Ingreso expuesto a impuntualidad", fmt_millones(ingreso_expuesto),
            f"{fmt_pct(ingreso_expuesto / k.ingresos if k.ingresos else 0)} del ingreso salió con más de 15 min de retraso",
            "alerta"),
        kpi("Tiquete promedio", f"${fmt_num(ticket)}", "COP por segmento operado", "neutral"),
    ])

    por_ruta_com = operados.groupby(
        ["ruta", "origen", "destino", "latitud_origen", "longitud_origen", "latitud_destino", "longitud_destino"]
    ).agg(
        ingresos=("ingreso_efectivo_cop", "sum"), vuelos=("ingreso_efectivo_cop", "size"),
        ocupacion=("ocupacion_pct", "mean"), puntualidad=("vuelo_puntual", "mean"),
    ).reset_index()

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        fig = go.Figure()
        maximo = por_ruta_com["ingresos"].max()
        for _, r in por_ruta_com.iterrows():
            fig.add_trace(
                go.Scattergeo(
                    lon=[r.longitud_origen, r.longitud_destino], lat=[r.latitud_origen, r.latitud_destino],
                    mode="lines", line=dict(width=0.5 + 6 * r.ingresos / maximo, color=AZUL), opacity=0.55,
                    hoverinfo="text",
                    text=f"{r.ruta}<br>Ingresos: {fmt_millones(r.ingresos)}<br>Vuelos: {fmt_num(r.vuelos)}",
                    showlegend=False,
                )
            )
        aeropuertos = operados.groupby(["origen", "ciudad_origen", "latitud_origen", "longitud_origen"]).agg(
            ingresos=("ingreso_efectivo_cop", "sum")
        ).reset_index()
        fig.add_trace(
            go.Scattergeo(
                lon=aeropuertos["longitud_origen"], lat=aeropuertos["latitud_origen"],
                text=aeropuertos["origen"], mode="markers+text", textposition="middle right",
                marker=dict(size=8 + 30 * aeropuertos["ingresos"] / aeropuertos["ingresos"].max(), color=AZUL,
                            line=dict(color="white", width=1)),
                customdata=np.stack([aeropuertos["ciudad_origen"],
                                     aeropuertos["ingresos"].map(fmt_millones)], axis=-1),
                hovertemplate="%{customdata[0]} (%{text})<br>Ingresos con origen aquí: %{customdata[1]}<extra></extra>",
                showlegend=False,
            )
        )
        fig.update_geos(
            lataxis_range=[2, 12.5], lonaxis_range=[-83, -68], showcountries=True,
            countrycolor="#999", showland=True, landcolor="#F2F2F2", showocean=True, oceancolor="#E8F0F8",
            resolution=50,
        )
        fig.update_layout(title="Red de rutas: grosor = ingresos, tamaño del punto = ingresos por origen")
        grafico(estilo(fig, alto=470, leyenda=False))
    with col_der:
        por_tarifa = df.groupby("tarifa").agg(
            pasajeros=("id_segmento_vuelo", "size"), ingresos=("ingreso_efectivo_cop", "sum")
        ).reindex(ORDEN_TARIFA).dropna()
        participacion = pd.DataFrame({
            "tarifa": list(por_tarifa.index) * 2,
            "medida": ["% de pasajeros"] * len(por_tarifa) + ["% de ingresos"] * len(por_tarifa),
            "valor": list(por_tarifa["pasajeros"] / por_tarifa["pasajeros"].sum())
            + list(por_tarifa["ingresos"] / por_tarifa["ingresos"].sum()),
        })
        fig = px.bar(
            participacion, x="tarifa", y="valor", color="medida", barmode="group", text_auto=".0%",
            title="Peso de cada tarifa: pasajeros vs. ingresos",
            color_discrete_map={"% de pasajeros": GRIS, "% de ingresos": AZUL},
        )
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_xaxes(title=None)
        fig.update_traces(hovertemplate="%{x}<br>%{y:.1%}<extra></extra>")
        grafico(estilo(fig, alto=470))

    col_izq, col_der = st.columns([3, 2])
    with col_izq:
        top = por_ruta_com.sort_values("ingresos", ascending=False).head(15).sort_values("ingresos")
        top["ingresos_m"] = top["ingresos"] / 1e6
        fig = px.bar(
            top, y="ruta", x="ingresos_m", orientation="h", color="puntualidad",
            color_continuous_scale=ESCALA_SEMAFORO, range_color=[0.3, META_PUNTUALIDAD],
            title="Top 15 rutas por ingresos (color = puntualidad)",
            custom_data=["vuelos", "ocupacion", "puntualidad"],
        )
        fig.update_traces(
            hovertemplate="%{y}<br>Ingresos: $%{x:,.0f} M<br>Vuelos: %{customdata[0]}"
            "<br>Ocupación: %{customdata[1]:.1f} %<br>Puntualidad: %{customdata[2]:.1%}<extra></extra>"
        )
        fig.update_coloraxes(colorbar=dict(title="Puntualidad", tickformat=".0%"))
        fig.update_xaxes(title="Ingresos (millones de COP)")
        fig.update_yaxes(title=None)
        grafico(estilo(fig, alto=480))
    with col_der:
        por_canal = operados.groupby("canal_venta").agg(
            ingresos=("ingreso_efectivo_cop", "sum"), ticket=("precio_tiquete_cop", "mean")
        ).sort_values("ingresos").reset_index()
        por_canal["ingresos_m"] = por_canal["ingresos"] / 1e6
        fig = px.bar(
            por_canal, y="canal_venta", x="ingresos_m", orientation="h", title="Ingresos por canal de venta",
            color_discrete_sequence=[AZUL], custom_data=["ticket"],
        )
        fig.update_traces(
            texttemplate="$%{x:,.0f} M", textposition="inside",
            hovertemplate="%{y}<br>Ingresos: $%{x:,.0f} M<br>Tiquete promedio: $%{customdata[0]:,.0f}<extra></extra>",
        )
        fig.update_xaxes(title="Ingresos (millones de COP)")
        fig.update_yaxes(title=None)
        grafico(estilo(fig, alto=480, leyenda=False))

    if k.ingresos:
        top3 = por_ruta_com.sort_values("ingresos", ascending=False).head(3)
        ejecutiva = por_tarifa.loc["Ejecutiva"] if "Ejecutiva" in por_tarifa.index else None
        texto = (
            f"<b>{fmt_pct(ingreso_expuesto / k.ingresos, 0)}</b> del ingreso viaja en vuelos impuntuales. "
            f"Las 3 rutas que más facturan ({', '.join(top3['ruta'])}) suman "
            f"<b>{fmt_pct(top3['ingresos'].sum() / k.ingresos, 0)}</b> del ingreso: son la prioridad para mejorar la puntualidad."
        )
        if ejecutiva is not None and por_tarifa["pasajeros"].sum():
            texto += (
                f" La tarifa Ejecutiva es el {fmt_pct(ejecutiva.pasajeros / por_tarifa['pasajeros'].sum(), 0)} de los pasajeros "
                f"pero aporta el {fmt_pct(ejecutiva.ingresos / por_tarifa['ingresos'].sum(), 0)} del ingreso."
            )
        hallazgo(texto)

# ===========================================================================
# 5. CONCLUSIONES
# ===========================================================================
with tab_conclusiones:
    seccion("Conclusiones", "Síntesis para la gerencia")
    st.caption("Los valores se recalculan con los filtros de la barra lateral.")

    calif_alto = valores.get("Más de 90 min", np.nan)
    expuesto_pct = ingreso_expuesto / k.ingresos if k.ingresos else 0

    def bloque(titulo, puntos, estado):
        items = "".join(f"<li>{p}</li>" for p in puntos)
        return f'<div class="concl" style="--c:{ESTADOS[estado][0]}"><h3>{titulo}</h3><ul>{items}</ul></div>'

    st.markdown(
        '<div class="concl-grid">'
        + bloque("Operación", [
            f"Puntualidad de <b>{fmt_pct(k.puntualidad)}</b>, a {fmt_num((META_PUNTUALIDAD - k.puntualidad) * 100, 0)} puntos de la meta.",
            "La brecha es igual en todas las rutas, franjas y aeropuertos: <b>problema sistémico</b>.",
            f"<b>{fmt_pct(k.irregularidad)}</b> de vuelos con irregularidad, con causas repartidas por igual.",
        ], "ok" if k.puntualidad >= META_PUNTUALIDAD else "alerta")
        + bloque("Experiencia del pasajero", [
            f"Calificación promedio <b>{fmt_num(k.calificacion, 2)}</b>, sostenida por los vuelos puntuales.",
            f"Con más de 90 min de retraso cae a <b>{fmt_num(calif_alto, 2)}</b>.",
            "Umbral crítico: <b>45 minutos</b>. Desde ahí la calificación queda bajo la meta.",
        ], "precaucion")
        + bloque("Comercial", [
            f"Ingresos de <b>{fmt_millones(k.ingresos)}</b> COP con ocupación de <b>{fmt_num(k.ocupacion, 1)} %</b>.",
            f"<b>{fmt_pct(expuesto_pct, 0)}</b> del ingreso viaja en vuelos impuntuales.",
            "La tarifa Ejecutiva y las rutas desde BOG concentran el valor.",
        ], "neutral")
        + "</div>",
        unsafe_allow_html=True,
    )

    seccion("Plan de acción", "Recomendaciones")
    st.markdown(
        "1. **Plan de puntualidad de toda la red**, no por ruta: tiempos de rotación en tierra, mantenimiento "
        "preventivo y coordinación con aeropuertos, con meta intermedia de 60 % y seguimiento mensual en este tablero.\n"
        "2. **Protocolo de retraso a los 45 minutos**: información proactiva, compensación y reacomodación "
        "antes de que la espera pase el umbral donde la satisfacción cae bajo 4,0.\n"
        "3. **Priorizar las rutas de mayor ingreso y a los pasajeros de tarifa Ejecutiva** en la asignación de "
        "aeronaves de reserva y tripulaciones, porque concentran el ingreso expuesto."
    )

# ===========================================================================
# 6. DATOS Y METODOLOGÍA
# ===========================================================================
with tab_metodo:
    seccion("Componente técnico", "Datos, preparación y modelo")

    with st.expander("Origen de los datos", expanded=True):
        st.markdown(
            "- Dataset **sintético y anonimizado** asignado al grupo 8: `08_aerolinea_regional.csv`.\n"
            "- **55.000 registros**, del 01/01/2024 al 30/09/2026.\n"
            "- **Unidad de observación:** un segmento de vuelo vendido (`id_segmento_vuelo`).\n"
            "- 8 aeropuertos, 56 rutas, 3 tarifas, 4 canales de venta y 4 franjas de salida."
        )

    with st.expander("Preparación y limpieza"):
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
            """
            digraph {
                rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
                fact [label="fact_vuelos\\n55.000 filas", fillcolor="#1F4E79", fontcolor="white"];
                node [fillcolor="#EEF3F9"];
                cal [label="dim_calendario"]; ruta [label="dim_ruta"]; tar [label="dim_tarifa"];
                can [label="dim_canal"]; fra [label="dim_franja"]; mot [label="dim_motivo"];
                cal -> fact [label="id_fecha"]; ruta -> fact [label="id_ruta"]; tar -> fact [label="id_tarifa"];
                can -> fact [label="id_canal"]; fra -> fact [label="id_franja"]; mot -> fact [label="id_motivo"];
            }
            """
        )

    with st.expander("Definición de los KPI"):
        st.table(pd.DataFrame(
            [
                ("Puntualidad", "Vuelos operados con retraso ≤ 15 min ÷ vuelos operados", "≥ 80 %"),
                ("Tasa de cancelación", "Vuelos cancelados ÷ total de vuelos", "≤ 2 %"),
                ("Vuelos con irregularidad", "Vuelos cancelados o con retraso > 60 min ÷ total de vuelos", "≤ 10 %"),
                ("Calificación promedio", "Promedio de calificacion_1a5 (sin contar vacíos)", "≥ 4,0"),
                ("Ingresos totales", "Suma de precio_tiquete_cop de vuelos operados", "Referencia"),
                ("Ocupación promedio", "Promedio de ocupacion_pct de vuelos operados", "≥ 80 %"),
            ],
            columns=["KPI", "Fórmula", "Meta"],
        ).set_index("KPI"))

    with st.expander("Datos filtrados"):
        st.dataframe(
            df.drop(columns=[c for c in df.columns if c.startswith("id_") and c != "id_segmento_vuelo"]),
            width="stretch", height=350,
        )
