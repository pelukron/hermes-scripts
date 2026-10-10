"""The official-fetcher failure protocol has one owner (#431)."""

from pathlib import Path

from hermes_common import news_utils
from scripts import team_pipeline
from scripts.team_pipeline import ERROR_TITLE_PREFIX, _official_failed, official_error

REPO = Path(__file__).resolve().parent.parent
TEAM_SCRIPTS = (
    REPO / "src" / "scripts" / "resumen_rayados_diario.py",
    REPO / "src" / "scripts" / "resumen_tigres_diario.py",
    REPO / "src" / "scripts" / "titans_daily.py",
)


def test_no_error_literal_in_team_scripts():
    """Scripts delegate to `official_error`; the sentinel is never hand-built."""
    for script in TEAM_SCRIPTS:
        assert '"[Error' not in script.read_text(encoding="utf-8"), script.name


def test_official_error_shape():
    item = official_error("rayados.com", ValueError("x" * 100))[0]
    assert item.title.startswith(f"{ERROR_TITLE_PREFIX} rayados.com: ")
    assert len(item.title) <= len(f"{ERROR_TITLE_PREFIX} rayados.com: ") + 80
    assert (item.source, item.origin, item.category) == (
        "rayados.com",
        "rayados.com",
        "confirmadas",
    )


def test_official_failed_recognizes_constructor_output():
    assert _official_failed(official_error("tigres.com.mx", RuntimeError("boom"))) is True
    assert _official_failed([]) is False
    assert _official_failed([news_utils.NewsItem(title="plain", category="confirmadas")]) is False


def test_prefix_lives_in_team_pipeline():
    assert team_pipeline.ERROR_TITLE_PREFIX == "[Error"
