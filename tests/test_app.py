import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_demo_starts_with_uploads_disabled(monkeypatch):
    import data

    frame, _ = data.load_demo()

    def no_replacement_generator(*args, **kwargs):
        raise AssertionError("The author demo must not use a replacement generator")

    monkeypatch.setattr(data, "synthetic_data", no_replacement_generator)
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert not app.exception
    assert app.radio[0].options == ["Demo del autor"]
    assert sum(item.value == "Demo educativa con datos ficticios" for item in app.caption) == 1
    assert not app.info
    assert not app.warning
    assert not app.expander
    assert next(item.value for item in app.metric if item.label == "Filas aceptadas") == f"{len(frame):,}"
    assert not app.get("deck_gl_json_chart")


def test_demo_form_runs_prediction_and_holdout_evaluation(monkeypatch):
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert any("Resultado de la comparación" == item.value for item in app.subheader)
    assert any("Evaluación con datos reservados" == item.value for item in app.subheader)
    assert any("cobertura" in item.value for item in app.markdown)
    assert sum(item.value == "Demo educativa con datos ficticios" for item in app.caption) == 1
    chart = app.get("deck_gl_json_chart")[0]
    points = json.loads(chart.proto.json)["layers"][0]["data"]
    from data import load_demo, split_data
    from model import ComparableModel, Query

    train, _, _ = split_data(load_demo()[0])
    estimate = ComparableModel(train).predict(Query("apartment", 70.0, 60.0, 3, -34.6, -58.44))
    assert [(point["lat"], point["lon"]) for point in points[:-1]] == list(estimate.comparable_locations)
    assert [(point["lat"], point["lon"]) for point in points[-1:]] == [(-34.6, -58.44)]
    assert len(points) == estimate.n_comparables + 1
    assert all(set(point) == {"lat", "lon", "color", "size"} for point in points)
    assert all(point["color"] == [5, 113, 176, 255] for point in points[:-1])
    assert points[-1]["color"] == [230, 97, 1, 255]
    assert "entrenamiento" in chart.proto.alt


def test_no_comparables_still_maps_the_coarsened_query(monkeypatch):
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    for item in app.number_input:
        if item.label in ("Superficie total (m²)", "Superficie cubierta (m²)"):
            item.set_value(10000.0)
        elif item.label == "Ambientes":
            item.set_value(20)
        elif item.label == "Latitud aproximada":
            item.set_value(-34.60012345)
        elif item.label == "Longitud aproximada":
            item.set_value(-58.44023456)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert any("0 comparables disponibles" in item.value for item in app.warning)
    points = json.loads(app.get("deck_gl_json_chart")[0].proto.json)["layers"][0]["data"]
    assert len(points) == 1
    assert points[0]["lat"] == -34.600
    assert points[0]["lon"] == -58.440
    assert not any("Media de la demo" in item.label for item in app.metric)


def test_invalid_covered_area_returns_clear_error(monkeypatch):
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    covered = next(item for item in app.number_input if item.label == "Superficie cubierta (m²)")
    covered.set_value(100.0)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert any("no superar la total" in item.value for item in app.error)
    assert not any("Resultado de la comparación" == item.value for item in app.subheader)
    assert not app.get("deck_gl_json_chart")


def test_upload_mode_requires_explicit_permission(monkeypatch):
    monkeypatch.setenv("PROPERATI_ALLOW_UPLOADS", "1")
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.radio[0].set_value("Cargar archivo propio").run(timeout=20)
    assert not app.exception
    assert not app.checkbox[0].value
    assert any("se procesa en el servidor" in item.value for item in app.info)
    assert any("revisá el aviso de privacidad" in item.value for item in app.info)
    assert not any("Demo educativa con datos ficticios" in item.value for item in app.caption)
    assert any("Privacidad de los archivos" in item.value for item in app.caption)
