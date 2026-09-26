"""Seam de TeamPipeline: un ensamble, dos configs, y un guard contra la deriva."""

from pathlib import Path

from hermes_common import news_utils
from scripts.team_pipeline import TeamConfig, build_report

NewsItem = news_utils.NewsItem

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src" / "scripts"


def _config(**overrides) -> TeamConfig:
    base = dict(
        history_name="equipo-history.json",
        queries={"confirmadas": '"Equipo"', "rumores": '"Equipo" fichaje'},
        sitios_oficiales=["equipo.test"],
        header_title="**Equipo — Noticias del día**",
        sources_line="Fuentes: prueba",
        prefilter_official=False,
        announce_overflow=False,
    )
    base.update(overrides)
    return TeamConfig(**base)


def _notas(n: int) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Asunto-{i:04d}-abc relleno que no colapsa",
            link=f"https://ejemplo.com/nota-{i}",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
        for i in range(n)
    ]


def _report(config: TeamConfig, items: list[NewsItem], tmp_path: Path) -> list[str]:
    def fetch_google(query: str, category: str) -> list[NewsItem]:
        return items if category == "confirmadas" else []

    return build_report(
        config,
        history_path=str(tmp_path / config.history_name),
        fetch_google_news=fetch_google,
        fetch_official=list,
        enrich_official=lambda found: found,
    )


def _confirmado(blocks: list[str]) -> str:
    return next(block for block in blocks if "CONFIRMADO" in block)


def test_el_contador_de_tigres_anuncia_el_recorte(tmp_path):
    blocks = _report(
        _config(announce_overflow=True, history_name="tigres.json"), _notas(12), tmp_path
    )
    header = _confirmado(blocks).splitlines()[0]
    assert header.startswith("**✅ CONFIRMADO** (8 de 12)")


def test_el_contador_de_rayados_cuenta_el_total(tmp_path):
    blocks = _report(
        _config(announce_overflow=False, history_name="rayados.json"), _notas(12), tmp_path
    )
    header = _confirmado(blocks).splitlines()[0]
    assert header.startswith("**✅ CONFIRMADO** (12)")
    assert " de " not in header
    bullets = [line for line in _confirmado(blocks).splitlines() if line.startswith("- ")]
    assert len(bullets) == 8


def test_las_listas_compartidas_viven_una_sola_vez():
    pipeline = (SCRIPTS / "team_pipeline.py").read_text(encoding="utf-8")
    assert pipeline.count('"milenio.com"') == 1
    for name in ("resumen_rayados_diario.py", "resumen_tigres_diario.py"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "HistoryManager" not in text
        assert "BeautifulSoup" not in text
        assert "milenio.com" not in text
        assert "def build_report_blocks" in text
        assert len(text.splitlines()) < 140
