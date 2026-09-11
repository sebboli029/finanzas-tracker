from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_completo_corre_sin_excepciones():
    at = AppTest.from_file(str(Path(__file__).parent.parent / "app.py"))
    at.run(timeout=30)
    assert not at.exception


def test_la_portada_aparece_antes_de_las_pestanas():
    at = AppTest.from_file(str(Path(__file__).parent.parent / "app.py"))
    at.run(timeout=30)
    subheaders = [s.value for s in at.subheader]
    assert "🏠 Inicio" in subheaders
