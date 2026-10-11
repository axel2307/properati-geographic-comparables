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
    assert any("Dataset ficticio proporcionado por el autor" in info.value for info in app.info)
    assert any("no verificado de forma independiente" in info.value for info in app.info)
    assert any("no es una tasación" in item.value for item in app.warning)
    assert next(item.value for item in app.metric if item.label == "Filas aceptadas") == f"{len(frame):,}"


def test_demo_form_runs_prediction_and_holdout_evaluation(monkeypatch):
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert any("Resultado de la comparación" == item.value for item in app.subheader)
    assert any("Evaluación con datos reservados" == item.value for item in app.subheader)
    assert any("cobertura" in item.value for item in app.markdown)
    assert any("dataset de demostración del autor" in item.value for item in app.caption)


def test_invalid_covered_area_returns_clear_error(monkeypatch):
    monkeypatch.delenv("PROPERATI_ALLOW_UPLOADS", raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    covered = next(item for item in app.number_input if item.label == "Superficie cubierta (m²)")
    covered.set_value(100.0)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert any("no superar la total" in item.value for item in app.error)
    assert not any("Resultado de la comparación" == item.value for item in app.subheader)


def test_upload_mode_requires_explicit_permission(monkeypatch):
    monkeypatch.setenv("PROPERATI_ALLOW_UPLOADS", "1")
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.radio[0].set_value("Cargar archivo propio").run(timeout=20)
    assert not app.exception
    assert not app.checkbox[0].value
    assert any("servidor recibe" in item.value for item in app.info)
    assert any("revisá el aviso de privacidad" in item.value for item in app.info)
    assert not any("Dataset ficticio proporcionado por el autor" in item.value for item in app.info)
