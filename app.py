"""Streamlit portfolio prototype. Uploaded rows are never cached or displayed."""
import os

import pandas as pd
import streamlit as st

from data import DataValidationError, LAT_BOUNDS, LON_BOUNDS, MAX_BYTES, load_csv, load_demo, split_data
from model import ComparableModel, Filters, Query, evaluate

st.set_page_config(page_title="Comparables geográficos | Properati", page_icon="🏙️", layout="wide")
st.title("Comparables geográficos")
st.caption("Proyecto de portfolio · filtros explícitos + vecinos por distancia Haversine")
st.warning("Demo educativa: no es una tasación ni permite concluir precios de mercado.")

with st.sidebar:
    st.header("Datos")
    uploads_enabled = os.environ.get("PROPERATI_ALLOW_UPLOADS") == "1"
    source = st.radio("Elegí el origen", ["Demo del autor", "Cargar archivo propio"] if uploads_enabled else ["Demo del autor"])
    if not uploads_enabled:
        st.caption("Este despliegue usa la demo del autor. La carga de archivos está deshabilitada; el README explica cómo habilitarla en tu computadora.")
    upload = None
    if source == "Cargar archivo propio":
        st.info("Subí únicamente datos que tengas permiso de procesar. En un despliegue público, el servidor recibe el archivo. Para datos privados, ejecutá la app en tu computadora.")
        consent = st.checkbox("Entiendo dónde se procesa el archivo y tengo permiso para usarlo")
        upload = st.file_uploader("Archivo CSV o TSV", type=["csv", "tsv", "txt"], disabled=not consent)
        st.caption("La app no guarda archivos, no usa caché de datos y no muestra direcciones, descripciones ni filas individuales. El proveedor de alojamiento puede tener sus propias políticas de registros y retención.")

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
    st.error("No pudimos preparar el archivo. Revisá el formato, las columnas requeridas y que haya suficientes ubicaciones distintas. El README detalla el esquema. No se muestran contenidos del archivo en este error.")
    st.stop()

author_demo = upload is None
if author_demo:
    st.info("Dataset ficticio proporcionado por el autor. Declaración del autor; no verificado de forma independiente. No representa precios de mercado.")
    st.caption("Se usa una proyección minimizada autorizada del archivo del autor, con 8 columnas y coordenadas redondeadas a 3 decimales. Ese redondeo puede cambiar vecinos, grupos espaciales y resultados.")
else:
    st.info("Archivo propio · La procedencia, el carácter ficticio o real, las fechas y el permiso de uso son responsabilidad de quien lo carga. La declaración del autor de la demo no se aplica a otros archivos. Estos resultados no permiten concluir precios de mercado.")

with st.expander("Preparación y separación de los datos"):
    a, b, c = st.columns(3)
    a.metric("Filas aceptadas", f"{len(frame):,}")
    b.metric("Entrenamiento", f"{len(train):,}")
    c.metric("Evaluación reservada", f"{len(test):,}")
    st.write("Los duplicados se eliminan antes de separar grupos espaciales. Los comparables de esta pantalla salen solamente del conjunto de entrenamiento; las filas reservadas no participan en la predicción.")
    st.caption("El corte por grupos espaciales reduce el solapamiento de ubicaciones, pero las celdas vecinas pueden contener propiedades cercanas. No garantiza independencia espacial completa ni mide evolución temporal.")
    st.caption("La caja geográfica es una comprobación de plausibilidad, no una frontera oficial de CABA. La deduplicación puede unir observaciones distintas con iguales características registradas, o conservar repeticiones con datos distintos.")
    if report:
        st.write(f"Filas recibidas: {report['input_rows']:,}. Rechazadas: {report['rejected_rows']:,}. Duplicados removidos: {report['duplicate_rows_removed']:,}.")
    st.caption("La evaluación conserva la misma separación reproducible. No se evalúa evolución temporal ni se usa una fecha de descarga como fecha de observación.")

st.subheader("La propiedad que querés comparar")
st.write("Ingresá sus características y una ubicación aproximada dentro de CABA. El tipo, los ambientes, la superficie y la proporción cubierta participan en la selección.")

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
        st.caption("La distancia se mide en kilómetros sobre la superficie terrestre. No incluye recorridos por calles ni diferencias dentro de un barrio.")
        st.caption("No se solicitan baños ni comodidades porque el esquema disponible no los contiene de forma confiable.")
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
    st.caption(f"Proporción cubierta consultada: {query.ratio:.1%}. Se filtra por tipo exacto, ambientes, superficie y proporción; luego se eligen los más cercanos dentro de {radius:.1f} km.")
    if not estimate.sufficient:
        st.warning(estimate.insufficient_reason or f"Evidencia insuficiente: {estimate.n_comparables} comparables disponibles; hacen falta al menos 3. Podés cambiar los filtros de forma explícita o probar otra ubicación. No se calcula un precio.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Media de la demo (USD/m²)" if author_demo else "Media del archivo (USD/m²)", f"{estimate.usd_m2:,.0f}")
        m2.metric("Total de la demo (USD)" if author_demo else "Referencia del archivo (USD)", f"{estimate.asking_price_usd:,.0f}")
        m3.metric("Comparables utilizados", estimate.n_comparables)
        st.write(f"Hay {estimate.n_within_filters} filas que cumplen todos los filtros. Se usan las {estimate.n_comparables} más cercanas, a distancias de {estimate.distance_min_km:.2f} a {estimate.distance_max_km:.2f} km.")
        st.write(f"Rango observado entre esos comparables: USD {estimate.observed_min_usd_m2:,.0f}–{estimate.observed_max_usd_m2:,.0f} por m². Es un mínimo y máximo descriptivo; no es un intervalo de confianza ni de predicción.")
        st.caption("La referencia total multiplica la media de USD/m² por la superficie total ingresada. Con pocas observaciones, valores atípicos y diferencias no observadas pueden influir mucho.")
    st.subheader("Evaluación con datos reservados")
    st.caption("Evaluación exploratoria: ajustar filtros mirando estos errores puede sobreajustar este conjunto. Para una comparación formal, reservá un test final adicional sin usarlo para elegir filtros.")
    with st.spinner("Evaluando los mismos filtros en hasta 300 casos reservados…"):
        metrics = evaluate(train, test, filters)
    st.write(f"Se evaluaron {metrics['sample_rows']} de {metrics['holdout_rows']} filas reservadas con una muestra determinista (semilla {metrics['seed']}). Hubo evidencia suficiente en {metrics['covered_rows']} casos: cobertura {metrics['coverage']:.1%}.")
    if metrics["covered_rows"]:
        st.dataframe(pd.DataFrame({
            "Método": ["Comparables geográficos", "Mediana del entrenamiento"],
            "Error absoluto medio (USD/m²)": [metrics["mae"], metrics["baseline_mae"]],
            "Mediana del error absoluto (USD/m²)": [metrics["median_absolute_error"], metrics["baseline_median_absolute_error"]],
        }), hide_index=True, width="stretch")
        st.caption("Ambos métodos se miden sobre exactamente los mismos casos con al menos 3 comparables y una referencia finita y positiva. Menor error es mejor. El error no describe los casos sin cobertura. Al cambiar filtros también puede cambiar el subconjunto evaluado, así que los errores entre consultas no son directamente comparables.")
    else:
        st.info("No hubo casos con suficientes comparables. No se muestran métricas de error para un conjunto vacío.")
    if author_demo:
        st.caption("Estos errores evalúan únicamente el dataset de demostración del autor. No miden exactitud sobre propiedades reales ni el mercado.")

with st.expander("Qué puede y qué no puede mostrar este proyecto"):
    st.write("Es una demostración educativa de comparables filtrados y vecinos geográficos. No considera estado, antigüedad, orientación, piso, expensas, vistas, calidad de publicación ni condiciones de una operación. Tampoco ajusta inflación o cambios del mercado.")
    st.write("No hay garantía estadística de incertidumbre: el rango observado describe solamente los comparables elegidos. La media puede ser sensible a valores extremos y a sesgos de selección.")
    st.write("El autor declaró ficticio el archivo proporcionado y autorizó publicar su proyección minimizada. Esa declaración no fue verificada de forma independiente. No se distribuyen el archivo completo, textos libres, contactos ni coordenadas con la precisión original.")
