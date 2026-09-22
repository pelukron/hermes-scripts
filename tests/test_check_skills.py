"""check-skills (#252): las skills independientes se declaran y el repo avisa si faltan."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import check_skills as cs  # noqa: E402

MANIFIESTO = REPO / cs.MANIFEST_DEFAULT


def _home(base: Path, *nombres: str) -> Path:
    """Crea un `$HERMES_HOME` de prueba con las skills indicadas."""
    base.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        carpeta = base / "skills" / "categoria" / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "SKILL.md").write_text(f"---\nname: {nombre}\n---\n", encoding="utf-8")
    return base


def test_el_manifiesto_declara_las_tres_independientes():
    """El manifiesto es la lista de dependencias: si cambia, se ve aquí."""
    requeridas = cs.load_required(MANIFIESTO)
    assert [r["name"] for r in requeridas] == [
        "repo-ci-gate-replication",
        "hermes-automation-cron",
        "external-skills",
    ]
    assert all(r.get("why") for r in requeridas), "cada dependencia declara por qué"


def test_detecta_las_que_faltan(tmp_path):
    home = _home(tmp_path / "home", "external-skills")
    faltan = cs.faltantes(home, cs.load_required(MANIFIESTO))
    assert [f["name"] for f in faltan] == ["repo-ci-gate-replication", "hermes-automation-cron"]


def test_ignora_las_skills_archivadas(tmp_path):
    """Una copia en `.archive/` no cuenta: la skill sigue sin estar disponible."""
    home = _home(tmp_path / "home")
    archivo = home / "skills" / ".archive" / "external-skills"
    archivo.mkdir(parents=True)
    (archivo / "SKILL.md").write_text("---\nname: external-skills\n---\n", encoding="utf-8")
    faltan = [f["name"] for f in cs.faltantes(home, cs.load_required(MANIFIESTO))]
    assert "external-skills" in faltan


def test_el_name_del_frontmatter_es_la_identidad(tmp_path):
    """La carpeta puede llamarse distinto: manda el `name:` del frontmatter."""
    home = _home(tmp_path / "home")
    carpeta = home / "skills" / "otra-categoria" / "carpeta-distinta"
    carpeta.mkdir(parents=True)
    (carpeta / "SKILL.md").write_text(
        "---\nname: external-skills\ndescription: x\n---\n", encoding="utf-8"
    )
    faltan = [f["name"] for f in cs.faltantes(home, cs.load_required(MANIFIESTO))]
    assert "external-skills" not in faltan


def test_digest_calla_en_verde_y_nombra_lo_que_falta(tmp_path):
    manifiesto = cs.load_required(MANIFIESTO)
    completo = _home(tmp_path / "completo", *(r["name"] for r in manifiesto))
    assert cs.render_digest(cs.faltantes(completo, manifiesto)) == ""

    texto = cs.render_digest(cs.faltantes(tmp_path / "vacio", manifiesto))
    assert "check-skills" in texto
    assert len(texto.splitlines()) <= cs.QUIET_MAX_LINEAS


def test_el_digest_cabe_en_una_pantalla_con_muchas_faltantes():
    """Presupuesto del aviso: el peor caso también entra en una pantalla."""
    muchas = [{"name": f"skill-{i}", "category": "categoria", "why": "motivo"} for i in range(20)]
    assert len(cs.render_digest(muchas).splitlines()) <= cs.QUIET_MAX_LINEAS


def test_cli_sale_1_si_falta_y_0_si_estan(tmp_path, capsys):
    nombres = [r["name"] for r in cs.load_required(MANIFIESTO)]
    args = ["--manifest", str(MANIFIESTO)]
    assert cs.main([*args, "--home", str(_home(tmp_path / "ok", *nombres))]) == 0
    assert cs.main([*args, "--home", str(tmp_path / "vacio")]) == 1
    capsys.readouterr()


def test_quiet_no_imprime_nada_en_verde(tmp_path, capsys):
    nombres = [r["name"] for r in cs.load_required(MANIFIESTO)]
    rc = cs.main(
        ["--manifest", str(MANIFIESTO), "--quiet", "--home", str(_home(tmp_path / "ok", *nombres))]
    )
    assert rc == 0
    assert capsys.readouterr().out == ""
