"""Streamlit portfolio prototype. Uploaded rows are never cached or displayed."""
import os

import pandas as pd
import streamlit as st

from data import DataValidationError, LAT_BOUNDS, LON_BOUNDS, MAX_BYTES, load_csv, load_demo, split_data
from model import ComparableModel, Filters, Query, evaluate

st.set_page_config(page_title="Comparables geográficos | Properati", page_icon="🏙️", layout="wide")
st.title("Comparables geográficos")

with st.sidebar:
    st.header("Datos")
    uploads_enabled = os.environ.get("PROPERATI_ALLOW_UPLOADS") == "1"
    source = st.radio("Elegí el origen", ["Demo del autor", "Cargar archivo propio"] if uploads_enabled else ["Demo del autor"])
    st.caption("[Cómo funciona y documentación](https://github.com/axel2307/properati-geographic-comparables#readme)")
    upload = None
    if source == "Cargar archivo propio":
        st.info("El archivo se procesa en el servidor que ejecuta la app.")
        st.caption("[Privacidad de los archivos](https://github.com/axel2307/properati-geographic-comparables/blob/main/PRIVACY.md)")
        consent = st.checkbox("Entiendo dónde se procesa el archivo y tengo permiso para usarlo")
        upload = st.file_uploader("Archivo CSV o TSV", type=["csv", "tsv", "txt"], disabled=not consent)

if source == "Cargar archivo propio" and upload is None:
    st.info("Para continuar, revisá el aviso de privacidad y elegí tu archivo en el panel de datos.")
    st.stop()

try:
    if upload is None:
        frame, report = load_demo()
    else:
        if upload.size > MAX_BYTES:
            st.error("El archivo supera 200 MiB. Prepará una copia más chica en tu computadora; no modifiques el original.")
            st.stop()
        frame, report = load_csv(upload)
    train, test, split_info = split_data(frame)
except (DataValidationError, ValueError, pd.errors.ParserError, UnicodeError):
    st.error("No pudimos preparar el archivo. Revisá el formato, las columnas y que haya suficientes ubicaciones distintas. El README detalla el esquema.")
    st.stop()

author_demo = upload is None
if author_demo:
    st.caption("Demo educativa con datos ficticios")

a, b, c = st.columns(3)
a.metric("Filas aceptadas", f"{len(frame):,}")
b.metric("Entrenamiento", f"{len(train):,}")
c.metric("Evaluación reservada", f"{len(test):,}")

st.subheader("La propiedad que querés comparar")
st.write("Ingresá sus características y una ubicación aproximada dentro de CABA.")
st.caption("Después de buscar, el mapa muestra la ubicación consultada y los comparables seleccionados.")

with st.form("comparison_form"):
    left, right = st.columns(2)
    with left:
        property_types = sorted(train["property_type"].unique())
        property_type = st.selectbox("Tipo de propiedad", property_types,
                                      index=property_types.index("apartment") if "apartment" in property_types else 0,
                                      format_func=lambda value: {"apartment": "Departamento", "house": "Casa", "PH": "PH"}.get(value, value))
        area_total = st.number_input("Superficie total (m²)", min_value=1.0, max_value=10000.0, value=70.0, step=1.0)
        area_covered = st.number_input("Superficie cubierta (m²)", min_value=1.0, max_value=10000.0, value=60.0, step=1.0)
        rooms = st.number_input("Ambientes", min_value=1, max_value=20, value=3, step=1)
    with right:
        lat = st.number_input("Latitud aproximada", min_value=LAT_BOUNDS[0], max_value=LAT_BOUNDS[1], value=-34.60, step=0.001, format="%.3f")
        lon = st.number_input("Longitud aproximada", min_value=LON_BOUNDS[0], max_value=LON_BOUNDS[1], value=-58.44, step=0.001, format="%.3f")
        st.caption("Distancia geográfica en kilómetros.")
    st.subheader("Cómo elegir los comparables")
    f1, f2, f3 = st.columns(3)
    with f1:
        rooms_tolerance = st.slider("Tolerancia de ambientes (±)", 0, 5, 1)
        area_percent = st.slider("Tolerancia de superficie total (± %)", 0, 100, 35, 5)
    with f2:
        ratio_percent = st.slider("Tolerancia de proporción cubierta (± puntos porcentuales)", 0, 100, 25, 5)
        radius = st.slider("Radio máximo (km)", 0.1, 20.0, 5.0, 0.1)
    with f3:
        k = st.slider("Cantidad máxima de comparables", 3, 5, 5)
        st.caption("Siempre se requieren al menos 3. Los filtros nunca se amplían automáticamente.")
    submitted = st.form_submit_button("Buscar comparables", type="primary")

if submitted:
    try:
        query = Query(property_type, area_total, area_covered, rooms, lat, lon)
        filters = Filters(rooms_tolerance, area_percent / 100, ratio_percent / 100, radius, k)
        estimate = ComparableModel(train, filters).predict(query)
    except ValueError as error:
        st.error(str(error))
        st.stop()
    st.subheader("Resultado de la comparación")
    st.caption(f"Proporción cubierta: {query.ratio:.1%} · Radio máximo: {radius:.1f} km")
    if not estimate.sufficient:
        st.warning(estimate.insufficient_reason or f"Evidencia insuficiente: {estimate.n_comparables} comparables disponibles; hacen falta al menos 3. Podés cambiar los filtros de forma explícita o probar otra ubicación. No se calcula un precio.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Media de la demo (USD/m²)" if author_demo else "Media del archivo (USD/m²)", f"{estimate.usd_m2:,.0f}")
        m2.metric("Total de la demo (USD)" if author_demo else "Referencia del archivo (USD)", f"{estimate.asking_price_usd:,.0f}")
        m3.metric("Comparables utilizados", estimate.n_comparables)
        st.write(f"{estimate.n_within_filters} filas cumplen los filtros. Se usan las {estimate.n_comparables} más cercanas, a {estimate.distance_min_km:.2f}–{estimate.distance_max_km:.2f} km.")
        st.write(f"Rango observado: USD {estimate.observed_min_usd_m2:,.0f}–{estimate.observed_max_usd_m2:,.0f} por m².")
    st.subheader("Ubicación y comparables")
    map_points = pd.DataFrame([
        {"lat": point_lat, "lon": point_lon, "color": "#0571B0", "size": 15}
        for point_lat, point_lon in estimate.comparable_locations
    ] + [{"lat": round(query.lat, 3), "lon": round(query.lon, 3), "color": "#E66101", "size": 25}])
    st.map(map_points, latitude="lat", longitude="lon", color="color", size="size",
           height=400, width="stretch",
           alt=f"Mapa con la ubicación consultada en naranja y {estimate.n_comparables} comparables de entrenamiento en azul.")
    st.caption("Naranja: consulta · Azul: comparables · Ubicaciones aproximadas")
    st.subheader("Evaluación con datos reservados")
    with st.spinner("Evaluando los mismos filtros en hasta 300 casos reservados…"):
        metrics = evaluate(train, test, filters)
    st.write(f"Muestra: {metrics['sample_rows']} de {metrics['holdout_rows']} filas reservadas. Casos con evidencia suficiente: {metrics['covered_rows']} · cobertura {metrics['coverage']:.1%}.")
    if metrics["covered_rows"]:
        st.dataframe(pd.DataFrame({
            "Método": ["Comparables geográficos", "Mediana del entrenamiento"],
            "Error absoluto medio (USD/m²)": [metrics["mae"], metrics["baseline_mae"]],
            "Mediana del error absoluto (USD/m²)": [metrics["median_absolute_error"], metrics["baseline_median_absolute_error"]],
        }), hide_index=True, width="stretch")
        st.caption("Ambos métodos se evalúan sobre los mismos casos con cobertura. Menor error es mejor.")
    else:
        st.info("No hubo casos con suficientes comparables. No se muestran métricas de error para un conjunto vacío.")
