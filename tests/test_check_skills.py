"""check-skills (#252): las skills independientes se declaran y el repo avisa si faltan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

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


def test_el_manifiesto_declara_las_independientes():
    """El manifiesto es la lista de dependencias: si cambia, se ve aquí.

    `external-skills` salió de la lista al versionarse en `skills/` (#384): lo que el repo
    versiona lo vigilan `runtime-sync` y sus enlaces declarados, no este chequeo (#389).
    """
    requeridas = cs.load_required(MANIFIESTO)
    assert [r["name"] for r in requeridas] == [
        "repo-ci-gate-replication",
        "hermes-automation-cron",
    ]
    assert all(r.get("why") for r in requeridas), "cada dependencia declara por qué"


def test_detecta_las_que_faltan(tmp_path):
    home = _home(tmp_path / "home", "hermes-automation-cron")
    faltan = cs.faltantes(home, cs.load_required(MANIFIESTO))
    assert [f["name"] for f in faltan] == ["repo-ci-gate-replication"]


def test_ignora_las_skills_archivadas(tmp_path):
    """Una copia en `.archive/` no cuenta: la skill sigue sin estar disponible."""
    home = _home(tmp_path / "home")
    archivo = home / "skills" / ".archive" / "hermes-automation-cron"
    archivo.mkdir(parents=True)
    (archivo / "SKILL.md").write_text("---\nname: hermes-automation-cron\n---\n", encoding="utf-8")
    faltan = [f["name"] for f in cs.faltantes(home, cs.load_required(MANIFIESTO))]
    assert "hermes-automation-cron" in faltan


def test_el_name_del_frontmatter_es_la_identidad(tmp_path):
    """La carpeta puede llamarse distinto: manda el `name:` del frontmatter."""
    home = _home(tmp_path / "home")
    carpeta = home / "skills" / "otra-categoria" / "carpeta-distinta"
    carpeta.mkdir(parents=True)
    (carpeta / "SKILL.md").write_text(
        "---\nname: hermes-automation-cron\ndescription: x\n---\n", encoding="utf-8"
    )
    faltan = [f["name"] for f in cs.faltantes(home, cs.load_required(MANIFIESTO))]
    assert "hermes-automation-cron" not in faltan


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


def _skill_enlazada(tmp_path: Path, nombre: str) -> Path:
    """`$HERMES_HOME` con una skill desplegada por symlink, como en el despliegue real."""
    clon = tmp_path / "clon" / "skills" / nombre
    clon.mkdir(parents=True)
    (clon / "SKILL.md").write_text(f"---\nname: {nombre}\n---\n", encoding="utf-8")
    home = tmp_path / "home"
    enlace = home / "skills" / "productivity" / nombre
    enlace.parent.mkdir(parents=True)
    try:
        enlace.symlink_to(clon, target_is_directory=True)
    except OSError:
        pytest.skip("crear symlinks exige privilegio en este sistema")
    return home


def test_la_skill_desplegada_por_symlink_cuenta_como_instalada(tmp_path):
    """Un skill del despliegue es un enlace al clon, y `rglob` no entra en enlaces (#389).

    Medido el 2026-09-28 sobre el despliegue real: 203 `SKILL.md` por `rglob` contra 211 siguiendo
    enlaces. Las 8 invisibles incluían `external-skills`, que el job de drift reportaba como
    faltante mientras Hermes la listaba y el symlink resolvía.
    """
    home = _skill_enlazada(tmp_path, "external-skills")
    assert (home / "skills" / "productivity" / "external-skills").is_symlink()
    assert "external-skills" in cs.nombres_instalados(home)


def test_el_recorrido_sigue_enlaces_y_corta_los_circulares(tmp_path):
    """Seguir enlaces no puede colgarse: un enlace al propio `skills/` repetiría el árbol."""
    home = _skill_enlazada(tmp_path, "external-skills")
    raiz = home / "skills"
    (raiz / "circulo").symlink_to(raiz, target_is_directory=True)
    assert "external-skills" in cs.nombres_instalados(home)


def _enlaces_del_clon() -> set[str]:
    """Skills que este repo despliega por symlink (`config/runtime-clones.json`)."""
    data = json.loads((REPO / "config" / "runtime-clones.json").read_text(encoding="utf-8"))
    return {
        Path(enlace["path"]).name for clon in data["clones"] for enlace in clon.get("links") or []
    }


def test_el_manifiesto_no_declara_skills_que_el_repo_ya_versiona():
    """ADR 0003: el manifiesto declara lo que el repo **no** versiona.

    Medido el 2026-09-28: `external-skills` entró en `skills/` (#384) y su enlace quedó declarado en
    `runtime-clones.json`, pero siguió en el manifiesto; el job de drift reportaba como ausente una
    skill que el repo despliega y vigila (#389). Una entrada que vuelva a cruzar ese borde se ve
    aquí, no en el aviso del lunes.
    """
    versionadas = {path.parent.name for path in (REPO / "skills").glob("*/SKILL.md")}
    declaradas = {requerida["name"] for requerida in cs.load_required(MANIFIESTO)}
    repetidas = declaradas & (versionadas | _enlaces_del_clon())
    assert not repetidas, f"declaradas y además versionadas por el repo: {sorted(repetidas)}"
