"""Tests de src/install_cron.py y del manifiesto cron/jobs.json.

Estrategia de validacion (sin dependencias nuevas ni tocar el Hermes real):

- unitarios: expresiones cron, resolucion de destinos, render de wrappers;
- invariantes del repo: el manifiesto real valida, ningun archivo versionado
  tiene rutas /home/<usuario>, todos los bin/*.sh pasan `bash -n`;
- integracion sin efectos: apply_plan/verify con `run` monkeypatcheado contra
  un HERMES_HOME temporal (se valida el argv que se enviaria a hermes cron).
"""

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from src import install_cron as ic  # noqa: E402


def write_jobs_file(hermes_home: Path, jobs: list[dict]) -> Path:
    """Crea un cron/jobs.json temporal con los jobs dados."""
    path = hermes_home / "cron" / "jobs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    return path


def fake_job(**overrides) -> dict:
    """Job real (formato de Hermes) con defaults razonables."""
    job = {
        "id": "abc123",
        "name": "demo",
        "schedule": {"expr": "0 9 * * *"},
        "script": "demo.sh",
        "no_agent": True,
        "deliver": "origin",
        "enabled": True,
        "model": None,
        "provider": None,
    }
    job.update(overrides)
    return job


class TestCronExpr:
    """Validacion de expresiones cron de 5 campos."""

    @pytest.mark.parametrize(
        "expr",
        ["0 9 * * *", "*/30 * * * *", "55 18 * * 0-4", "5 8 * * 1,3,5", "0 3 * * 0"],
    )
    def test_validas(self, expr):
        assert ic.check_cron_expr(expr) is None

    @pytest.mark.parametrize(
        "expr",
        ["0 9 * *", "0 99 * * *", "0 9 * * 9", "cada hora", "0 9 * * */x"],
    )
    def test_invalidas(self, expr):
        assert ic.check_cron_expr(expr) is not None


class TestTargets:
    r"""Resolucion de destinos (${nombre} -> chat real)."""

    def test_resuelve_placeholder(self):
        assert ic.normalize_target("${reports}", {"reports": "telegram:-100"}) == "telegram:-100"

    def test_literal_pasa_tal_cual(self):
        assert ic.normalize_target("origin", {}) == "origin"

    def test_placeholder_sin_definir_falla(self):
        with pytest.raises(ic.ManifestError) as exc:
            ic.normalize_target("${reports}", {})
        assert "targets.local.json" in str(exc.value)


class TestRenderWrapper:
    """Wrappers portables: sin rutas absolutas, con fallbacks."""

    def test_uv_se_convierte_a_uv_bin(self, tmp_path):
        job = ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command="uv run python demo.py",
        )
        content = ic.render_wrapper(job, tmp_path)
        assert '"$UV_BIN" run python demo.py 2>&1' in content
        assert ic.WRAPPER_MARKER in content
        assert "/home/" not in content

    def test_command_con_exec_no_se_duplica(self, tmp_path):
        """Un comando que ya trae `exec` no debe generar `exec exec`.

        `job-scout daily run` traia `exec "$HOME/empleo/bin/cron-run.sh"` en el manifiesto: el
        prefijo ciego dejaba el wrapper en `exec exec ...` (rc=127) y el job no corria.
        """
        job = ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command='exec "$HOME/demo/bin/run.sh"',
        )
        content = ic.render_wrapper(job, tmp_path)
        assert "exec exec" not in content
        assert 'exec "$HOME/demo/bin/run.sh" 2>&1' in content

    def test_repo_por_env_con_fallback(self, tmp_path):
        job = ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command="bash bin/demo.sh",
        )
        content = ic.render_wrapper(job, tmp_path)
        assert f"HERMES_SCRIPTS_DIR:-{tmp_path}" in content
        assert 'UV_BIN="$HOME/.hermes/bin/uv"' in content
        assert 'export PATH="$(dirname "$UV_BIN"):$PATH"' in content

    def test_uv_alcanzable_desde_el_smoke(self, tmp_path):
        """El smoke de un clon corre con `bash -lc`: sin el export, `uv` a secas da rc=127 (#270).

        El PATH del cron no trae `$HOME/.hermes/bin`, asi que el wrapper debe dejar el `uv`
        que ya resolvio al alcance de sus hijos.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        fake_uv = fake_bin / "uv"
        fake_uv.write_text('#!/usr/bin/env bash\necho "uv resuelto: $*"\n', encoding="utf-8")
        fake_uv.chmod(0o755)
        job = ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command="env -u VIRTUAL_ENV uv run python -m demo --help",
        )
        wrapper = tmp_path / "demo.sh"
        wrapper.write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        proc = subprocess.run(
            ["bash", str(wrapper)],
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(tmp_path / "home"),
                "UV": str(fake_uv),
                "HERMES_SCRIPTS_DIR": str(repo),
            },
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "uv resuelto: run python -m demo --help" in proc.stdout

    def test_exporta_el_path_del_uv(self, tmp_path):
        """El hijo hereda el directorio de UV_BIN: si no, `uv` por nombre no existe (#257)."""
        content = ic.render_wrapper(no_agent_job(), tmp_path)
        assert 'export PATH="$(dirname "$UV_BIN"):$PATH"' in content

    def test_el_hijo_encuentra_uv_aunque_el_path_no_lo_traiga(self, tmp_path):
        bash = _bash_usable()
        if bash is None:
            pytest.skip("bash no disponible")
        home = tmp_path / "home"
        uv = home / ".hermes" / "bin" / "uv"
        uv.parent.mkdir(parents=True)
        uv.write_text("#!/bin/sh\necho uv-ok\n", encoding="utf-8")
        uv.chmod(0o755)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "child.sh").write_text("#!/bin/sh\nuv\n", encoding="utf-8")
        wrapper = tmp_path / "demo.sh"
        wrapper.write_text(
            ic.render_wrapper(no_agent_job(command="bash child.sh"), repo),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [bash, _posix(wrapper)],
            capture_output=True,
            text=True,
            env={
                "HOME": _posix(home),
                "PATH": "/usr/bin:/bin",
                "HERMES_SCRIPTS_DIR": _posix(repo),
            },
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert "uv-ok" in proc.stdout


def _posix(path: Path) -> str:
    """Ruta que bash de Git entiende: `/c/...` en Windows, tal cual en Linux."""
    text = path.resolve().as_posix()
    if len(text) >= 2 and text[1] == ":":
        return f"/{text[0].lower()}{text[2:]}"
    return text


def _bash_usable() -> str | None:
    """`bash` del PATH, salvo el stub de WSL que no arranca en esta máquina."""
    candidatos = [shutil.which("bash") or "", r"C:\Program Files\Git\bin\bash.exe"]
    for candidato in candidatos:
        if not candidato or "WindowsApps" in candidato.replace("/", "\\"):
            continue
        if Path(candidato).is_file():
            return candidato
    return None


class TestValidateManifest:
    """Reglas del manifiesto."""

    def manifest(self, jobs):
        return {"version": 1, "defaults": {"deliver": "origin"}, "jobs": jobs}

    def test_manifiesto_valido_no_reporta(self):
        jobs = ic.parse_jobs(
            self.manifest(
                [
                    {
                        "name": "demo",
                        "schedule": "0 9 * * *",
                        "command": "uv run python demo.py",
                    }
                ]
            )
        )
        assert ic.validate_manifest(self.manifest([]), jobs) == []

    def test_detecta_duplicados_y_faltantes(self):
        jobs = ic.parse_jobs(
            self.manifest(
                [
                    {"name": "demo", "schedule": "0 9 * * *", "command": "bash x.sh"},
                    {"name": "demo", "schedule": "0 9 * * *"},
                ]
            )
        )
        errors = ic.validate_manifest(self.manifest([]), jobs)
        assert any("sin 'schedule'" in e or "mode no_agent requiere 'command'" in e for e in errors)

    def test_no_agent_con_prompt_es_error(self):
        jobs = ic.parse_jobs(
            self.manifest(
                [
                    {
                        "name": "demo",
                        "schedule": "0 9 * * *",
                        "command": "bash x.sh",
                        "prompt": "no aplica",
                    }
                ]
            )
        )
        assert any("no usa 'prompt'" in e for e in ic.validate_manifest({}, jobs))

    def test_ruta_absoluta_de_home_es_error(self):
        jobs = ic.parse_jobs(
            self.manifest(
                [
                    {
                        "name": "demo",
                        "schedule": "0 9 * * *",
                        "command": "bash /home/otro/x.sh",
                    }
                ]
            )
        )
        assert any("ruta absoluta" in e for e in ic.validate_manifest({}, jobs))

    def test_version_incorrecta(self):
        jobs = ic.parse_jobs(
            self.manifest([{"name": "demo", "schedule": "0 9 * * *", "command": "bash x.sh"}])
        )
        assert any("version" in e for e in ic.validate_manifest({"version": 99}, jobs))

    def test_wrapper_compartido_con_distinto_command_falla(self):
        jobs = ic.parse_jobs(
            self.manifest(
                [
                    {
                        "name": "a",
                        "schedule": "0 9 * * *",
                        "wrapper": "x.sh",
                        "command": "bash a.sh",
                    },
                    {
                        "name": "b",
                        "schedule": "0 9 * * *",
                        "wrapper": "x.sh",
                        "command": "bash b.sh",
                    },
                ]
            )
        )
        assert any("ya declarado con otro command" in e for e in ic.validate_manifest({}, jobs))


class TestRepoInvariants:
    """Invariantes del repo real: manifiesto valido y sin rutas absolutas."""

    def test_manifiesto_real_valida(self):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        assert ic.validate_manifest(manifest, jobs) == []
        assert len(jobs) >= 5

    def test_sin_rutas_absolutas_en_archivos_versionados(self):
        assert ic.validate_repo_texts(REPO) == []

    def test_bin_scripts_pasan_bash_n(self):
        scripts = sorted((REPO / "bin").glob("*.sh"))
        assert scripts, "no hay bin/*.sh"
        for script in scripts:
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            assert result.returncode == 0, f"{script.name}: {result.stderr}"

    def test_manifiesto_y_wrappers_instalados_usan_mismos_nombres(self):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        for job in ic.parse_jobs(manifest):
            if job.is_no_agent:
                assert job.wrapper.endswith(".sh"), job.name


class TestDrift:
    """--check: deseado vs real."""

    def job(self):
        return ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command="bash bin/demo.sh",
        )

    def test_reporta_job_faltante(self, tmp_path):
        drift = ic.check_all([self.job()], {}, tmp_path, REPO)
        assert any("no existe en Hermes" in line for line in drift)
        assert any("falta en" in line for line in drift)

    def test_detecta_schedule_distinto(self, tmp_path):
        job = self.job()
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts" / "demo.sh").write_text(
            ic.render_wrapper(job, REPO), encoding="utf-8"
        )
        write_jobs_file(tmp_path, [fake_job(schedule={"expr": "0 10 * * *"})])
        drift = ic.check_all([job], {}, tmp_path, REPO)
        assert any("schedule: deseado='0 9 * * *'" in line for line in drift)

    def test_sin_drift_cuando_todo_coincide(self, tmp_path):
        job = self.job()
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts" / "demo.sh").write_text(
            ic.render_wrapper(job, REPO), encoding="utf-8"
        )
        write_jobs_file(tmp_path, [fake_job()])
        assert ic.check_all([job], {}, tmp_path, REPO) == []


class TestApplySinEfectos:
    """apply_plan con `run` monkeypatcheado: se valida el argv, no se toca Hermes."""

    def job(self):
        return ic.Job(
            name="demo",
            description="demo",
            schedule="0 9 * * *",
            mode="no_agent",
            deliver="origin",
            enabled=True,
            wrapper="demo.sh",
            command="bash bin/demo.sh",
        )

    def test_crea_job_nuevo_y_verifica(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        state = {"created": False}

        def fake_run(cmd: list[str]) -> None:
            calls.append(cmd)
            if cmd[:3] == ["hermes", "cron", "create"]:
                state["created"] = True

        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", fake_run)
        # `hermes cron create` deja el job en jobs.json: se simula leyendo de nuevo
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda home: (
                [fake_job(id="new1", name="demo", script="demo.sh")] if state["created"] else []
            ),
        )
        log = ic.apply_plan([self.job()], {}, tmp_path, REPO)
        assert calls and calls[0][:3] == ["hermes", "cron", "create"]
        assert "demo.sh" in calls[0]
        assert any("creado" in line for line in log)
        assert (tmp_path / "scripts" / "demo.sh").is_file()

    def test_edita_job_existente_por_id(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: calls.append(cmd))
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda home: [fake_job(id="keepme", name="demo", script="demo.sh")],
        )
        ic.apply_plan([self.job()], {}, tmp_path, REPO)
        assert calls[0][:3] == ["hermes", "cron", "edit"]
        assert calls[0][3] == "keepme"

    def test_pausa_job_deshabilitado(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: calls.append(cmd))
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda home: [fake_job(id="p1", name="demo", script="demo.sh", enabled=True)],
        )
        job = self.job()
        job.enabled = False
        log = ic.apply_plan([job], {}, tmp_path, REPO)
        assert ["hermes", "cron", "pause", "p1"] in calls
        assert any("pausado" in line for line in log)

    def test_no_sobrescribe_wrapper_ajeno(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: None)
        monkeypatch.setattr(ic, "read_live_jobs", lambda home: [])
        scripts = tmp_path / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "demo.sh").write_text("# manual, sin marca\n", encoding="utf-8")
        log = ic.apply_plan([self.job()], {}, tmp_path, REPO)
        assert any("OMITIDO" in line for line in log)
        assert (scripts / "demo.sh").read_text(encoding="utf-8") == "# manual, sin marca\n"

    def test_force_reemplaza_wrapper_ajeno(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: None)
        monkeypatch.setattr(ic, "read_live_jobs", lambda home: [])
        scripts = tmp_path / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "demo.sh").write_text("# manual, sin marca\n", encoding="utf-8")
        log = ic.apply_plan([self.job()], {}, tmp_path, REPO, force=True)
        assert any("actualizado" in line for line in log)
        assert ic.WRAPPER_MARKER in (scripts / "demo.sh").read_text(encoding="utf-8")

    def test_verificacion_detecta_drift(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            ic, "read_live_jobs", lambda home: [fake_job(schedule={"expr": "0 1 * * *"})]
        )
        problems = ic.verify([self.job()], {}, tmp_path)
        assert any("schedule" in line for line in problems)

    def test_cli_check_sale_1_con_drift(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ic, "read_live_jobs", lambda home: [])
        code = ic.main(
            [
                "--repo",
                str(REPO),
                "--manifest",
                ic.MANIFEST_DEFAULT,
                "--hermes-home",
                str(tmp_path),
                "--check",
                "--only",
                "backup-diario",
            ]
        )
        assert code == 1
        assert "Drift detectado" in capsys.readouterr().out

    def test_cli_dry_run_no_toca_nada(self, tmp_path, capsys):
        code = ic.main(
            [
                "--repo",
                str(REPO),
                "--hermes-home",
                str(tmp_path),
                "--dry-run",
                "--only",
                "backup-diario",
            ]
        )
        assert code == 0
        assert not (tmp_path / "cron").exists()

    def test_cli_manifiesto_inexistente(self, tmp_path, capsys):
        code = ic.main(["--repo", str(tmp_path), "--manifest", "cron/jobs.json"])
        assert code == 2
        assert "ERROR" in capsys.readouterr().err


def write_manifest(repo: Path, jobs: list[dict]) -> None:
    """Manifiesto mínimo válido en un repo temporal."""
    cron = repo / "cron"
    cron.mkdir(parents=True, exist_ok=True)
    (cron / "jobs.json").write_text(json.dumps({"version": 1, "jobs": jobs}), encoding="utf-8")


def demo_manifest_job(**overrides) -> dict:
    """Entrada de manifiesto no_agent mínima y válida."""
    job = {
        "name": "demo",
        "description": "demo",
        "schedule": "0 9 * * *",
        "mode": "no_agent",
        "deliver": "origin",
        "wrapper": "demo.sh",
        "command": "uv run python demo.py",
    }
    job.update(overrides)
    return job


def base_args(repo: Path, home: Path, *extra: str) -> list[str]:
    """Argv base contra repo y hermes-home temporales."""
    return [
        "--repo",
        str(repo),
        "--manifest",
        "cron/jobs.json",
        "--hermes-home",
        str(home),
        *extra,
    ]


class TestQuiet:
    """--check --quiet para el job semanal no_agent."""

    def test_quiet_sin_drift_stdout_vacio(self, tmp_path, monkeypatch, capsys):
        repo = tmp_path / "repo"
        home = tmp_path / "home"
        write_manifest(repo, [demo_manifest_job()])
        job = ic.parse_jobs(ic.load_manifest(repo / "cron" / "jobs.json"))[0]
        (home / "scripts").mkdir(parents=True)
        (home / "scripts" / "demo.sh").write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        monkeypatch.setattr(ic, "read_live_jobs", lambda h: [fake_job()])
        code = ic.main(base_args(repo, home, "--check", "--quiet"))
        assert code == 0
        assert capsys.readouterr().out == ""

    def test_quiet_con_drift_digest_rc0(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ic, "read_live_jobs", lambda h: [])
        code = ic.main(
            [
                "--repo",
                str(REPO),
                "--manifest",
                ic.MANIFEST_DEFAULT,
                "--hermes-home",
                str(tmp_path),
                "--check",
                "--quiet",
                "--only",
                "backup-diario",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert out.startswith("🛡️ Cron drift — ")
        assert "remedio: bin/install-cron.sh" in out
        assert len(out.splitlines()) <= 8

    def test_quiet_sin_check_es_error_de_uso(self, tmp_path, capsys):
        code = ic.main(base_args(tmp_path, tmp_path, "--quiet"))
        assert code == 2
        captured = capsys.readouterr()
        assert "--quiet" in captured.err
        assert captured.out == ""

    def test_check_manual_lista_extras_como_info(self, tmp_path, monkeypatch, capsys):
        repo = tmp_path / "repo"
        home = tmp_path / "home"
        write_manifest(repo, [demo_manifest_job()])
        job = ic.parse_jobs(ic.load_manifest(repo / "cron" / "jobs.json"))[0]
        (home / "scripts").mkdir(parents=True)
        (home / "scripts" / "demo.sh").write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        monkeypatch.setattr(
            ic, "read_live_jobs", lambda h: [fake_job(), fake_job(id="x9", name="otro")]
        )
        code = ic.main(base_args(repo, home, "--check"))
        out = capsys.readouterr().out
        assert code == 0
        assert "Sin drift" in out
        assert "info: job 'otro' existe en Hermes pero no en el manifiesto" in out

    def test_quiet_solo_extra_informativo_silencio(self, tmp_path, monkeypatch, capsys):
        """Solo un extra informativo: --quiet calla (#259; el digest es para drift real)."""
        repo = tmp_path / "repo"
        home = tmp_path / "home"
        write_manifest(repo, [demo_manifest_job()])
        job = ic.parse_jobs(ic.load_manifest(repo / "cron" / "jobs.json"))[0]
        (home / "scripts").mkdir(parents=True)
        (home / "scripts" / "demo.sh").write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        monkeypatch.setattr(
            ic, "read_live_jobs", lambda h: [fake_job(), fake_job(id="x9", name="otro")]
        )
        code = ic.main(base_args(repo, home, "--check", "--quiet"))
        out = capsys.readouterr().out
        assert code == 0
        assert out == ""

    def test_quiet_con_drift_real_omite_el_extra(self, tmp_path, monkeypatch, capsys):
        """Con drift real el digest sale, pero sin la línea del extra informativo."""
        repo = tmp_path / "repo"
        home = tmp_path / "home"
        write_manifest(repo, [demo_manifest_job()])
        job = ic.parse_jobs(ic.load_manifest(repo / "cron" / "jobs.json"))[0]
        (home / "scripts").mkdir(parents=True)
        (home / "scripts" / "demo.sh").write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda h: [
                fake_job(schedule={"expr": "0 10 * * *"}),
                fake_job(id="x9", name="otro"),
            ],
        )
        code = ic.main(base_args(repo, home, "--check", "--quiet"))
        out = capsys.readouterr().out
        assert code == 0
        assert out.startswith("🛡️ Cron drift — ")
        assert "schedule" in out
        assert "otro" not in out

    def test_check_manual_con_drift_y_extra_muestra_ambos(self, tmp_path, monkeypatch, capsys):
        """Con drift real: rc 1 con la línea de drift más el info: del extra."""
        repo = tmp_path / "repo"
        home = tmp_path / "home"
        write_manifest(repo, [demo_manifest_job()])
        job = ic.parse_jobs(ic.load_manifest(repo / "cron" / "jobs.json"))[0]
        (home / "scripts").mkdir(parents=True)
        (home / "scripts" / "demo.sh").write_text(ic.render_wrapper(job, repo), encoding="utf-8")
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda h: [
                fake_job(schedule={"expr": "0 10 * * *"}),
                fake_job(id="x9", name="otro"),
            ],
        )
        code = ic.main(base_args(repo, home, "--check"))
        out = capsys.readouterr().out
        assert code == 1
        assert "Drift detectado" in out
        assert "schedule" in out
        assert "info: job 'otro' existe en Hermes pero no en el manifiesto" in out

    def test_manifiesto_real_trae_cron_drift_check(self, tmp_path):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        assert len(jobs) == 21
        found = [job for job in jobs if job.name == "cron-drift-check"]
        assert len(found) == 1
        job = found[0]
        assert job.schedule == "0 10 * * 1"
        assert job.is_no_agent
        assert job.wrapper == "cron-check.sh"
        assert "--check --quiet" in job.command
        assert job.deliver == "${notify}"
        wrapper = tmp_path / "cron-check.sh"
        wrapper.write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
        result = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_manifiesto_real_trae_gate_audit(self, tmp_path):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        found = [job for job in jobs if job.name == "gate-audit"]
        assert len(found) == 1
        job = found[0]
        assert job.schedule == "0 10 * * 3"
        assert job.is_no_agent
        assert job.wrapper == "gate-audit.sh"
        assert "--digest --quiet" in job.command
        assert job.deliver == "${notify}"
        wrapper = tmp_path / "gate-audit.sh"
        wrapper.write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
        result = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_manifiesto_real_trae_cron_doctor_check(self, tmp_path):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        found = [job for job in jobs if job.name == "cron-doctor-check"]
        assert len(found) == 1
        job = found[0]
        assert job.schedule == "0 10 * * 2"
        assert job.is_no_agent
        assert job.wrapper == "cron-doctor.sh"
        assert "--doctor" in job.command
        assert job.deliver == "origin"
        assert ic.validate_manifest(manifest, jobs) == []
        wrapper = tmp_path / "cron-doctor.sh"
        wrapper.write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
        result = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


class TestDoctor:
    def _fake_run(self, monkeypatch, rc=0, out="", err="", exc=None):
        import types

        def fake(cmd, **kwargs):
            if exc is not None:
                raise exc
            return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)

        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic.subprocess, "run", fake)

    def test_sano_silencioso(self, monkeypatch, capsys):
        self._fake_run(monkeypatch, rc=0, out="todo bien\n")
        assert ic.run_doctor() == 0
        assert capsys.readouterr().out == ""

    def test_hallazgos_se_entregan(self, monkeypatch, capsys):
        self._fake_run(monkeypatch, rc=1, out="FALLA: job x\n")
        assert ic.run_doctor() == 1
        assert "FALLA: job x" in capsys.readouterr().out

    def test_sin_detalle_avisa(self, monkeypatch, capsys):
        self._fake_run(monkeypatch, rc=1, out="", err="")
        assert ic.run_doctor() == 1
        assert "sin detalle" in capsys.readouterr().out

    def test_hermes_ausente(self, monkeypatch, capsys):
        monkeypatch.setattr(
            ic, "hermes_cli", lambda: (_ for _ in ()).throw(ic.ManifestError("sin binario"))
        )
        assert ic.run_doctor() == 2
        assert "ERROR" in capsys.readouterr().err

    def test_subprocess_falla(self, monkeypatch, capsys):
        self._fake_run(monkeypatch, exc=OSError("no exec"))
        assert ic.run_doctor() == 2

    def test_main_doctor(self, monkeypatch, capsys):
        self._fake_run(monkeypatch, rc=0, out="")
        assert ic.main(["--doctor"]) == 0
        assert capsys.readouterr().out == ""

    def test_manifiesto_real_trae_aviso_offpeak(self, tmp_path):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = {job.name: job for job in ic.parse_jobs(manifest)}
        for name, schedule in (
            ("aviso-offpeak-22h", "0 22 * * 0-4"),
            ("aviso-offpeak-04h", "0 4 * * 1-5"),
        ):
            job = jobs[name]
            assert job.schedule == schedule
            assert job.is_no_agent
            assert job.wrapper == "aviso-offpeak.sh"
            assert "aviso-offpeak.sh" in job.command
            assert job.deliver == "${personal}"
            wrapper = tmp_path / "aviso-offpeak.sh"
            wrapper.write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
            result = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
            assert result.returncode == 0, result.stderr


def _write_manifest_targets(repo, jobs, local=None, example=None):
    """Manifiesto + example (+local opcional) en repo temporal."""
    import json
    from pathlib import Path

    cron = Path(repo) / "cron"
    cron.mkdir(parents=True, exist_ok=True)
    (cron / "jobs.json").write_text(json.dumps({"version": 1, "jobs": jobs}), encoding="utf-8")
    (cron / "targets.example.json").write_text(
        json.dumps({"_doc": "ejemplo", "a": "origin", **(example or {})}, ensure_ascii=False),
        encoding="utf-8",
    )
    if local is not None:
        (cron / "targets.local.json").write_text(json.dumps(local), encoding="utf-8")


def _job_t(name="demo", deliver="origin"):
    return demo_manifest_job(name=name, deliver=deliver)


class TestInitTargets:
    def test_crea_desde_ejemplo(self, tmp_path, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        _write_manifest_targets(repo, [_job_t(deliver="${a}")])
        code = ic.main(base_args(repo, home, "--init-targets"))
        out = capsys.readouterr().out
        assert code == 0
        assert (repo / "cron" / "targets.local.json").is_file()
        assert "creado" in out

    def test_valida_ok(self, tmp_path, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        _write_manifest_targets(repo, [_job_t(deliver="${a}")], local={"a": "origin"})
        code = ic.main(base_args(repo, home, "--init-targets"))
        assert code == 0
        assert "targets OK" in capsys.readouterr().out

    def test_falta_clave(self, tmp_path, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        _write_manifest_targets(repo, [_job_t(deliver="${b}")], local={"a": "origin"})
        code = ic.main(base_args(repo, home, "--init-targets"))
        assert code == 1
        assert "b" in capsys.readouterr().err

    def test_valor_invalido(self, tmp_path, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        _write_manifest_targets(repo, [_job_t(deliver="${a}")], local={"a": "telegram:xxx"})
        code = ic.main(base_args(repo, home, "--init-targets"))
        assert code == 1

    def test_sin_ejemplo_ni_local(self, tmp_path, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        (repo / "cron").mkdir(parents=True)
        code = ic.main(base_args(repo, home, "--init-targets"))
        assert code == 2


class TestRemove:
    def _setup(self, tmp_path, monkeypatch, live):
        repo, home = tmp_path / "repo", tmp_path / "home"
        write_manifest(repo, [_job_t()])
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "read_live_jobs", lambda h: live)
        return repo, home

    def test_baja_job_y_wrapper(self, tmp_path, monkeypatch, capsys):
        repo, home = self._setup(tmp_path, monkeypatch, [{"name": "demo", "id": "job-1"}])
        llamadas = []
        monkeypatch.setattr(ic, "run", lambda cmd: llamadas.append(cmd))
        scripts = home / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "demo.sh").write_text("# GENERADO por bin/install-cron.sh\n", encoding="utf-8")
        code = ic.main(base_args(repo, home, "--remove", "demo"))
        out = capsys.readouterr().out
        assert code == 0
        assert llamadas == [["hermes", "cron", "remove", "job-1"]]
        assert not (scripts / "demo.sh").exists()
        assert "eliminado de Hermes" in out

    def test_sin_live_solo_wrapper(self, tmp_path, monkeypatch, capsys):
        repo, home = self._setup(tmp_path, monkeypatch, [])
        llamadas = []
        monkeypatch.setattr(ic, "run", lambda cmd: llamadas.append(cmd))
        scripts = home / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "demo.sh").write_text("# GENERADO por bin/install-cron.sh\n", encoding="utf-8")
        code = ic.main(base_args(repo, home, "--remove", "demo"))
        assert code == 0
        assert llamadas == []
        assert not (scripts / "demo.sh").exists()
        assert "no existe en Hermes" in capsys.readouterr().out

    def test_wrapper_sin_marca_no_se_toca(self, tmp_path, monkeypatch, capsys):
        repo, home = self._setup(tmp_path, monkeypatch, [])
        monkeypatch.setattr(ic, "run", lambda cmd: None)
        scripts = home / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "demo.sh").write_text("#!/bin/bash\necho manual\n", encoding="utf-8")
        code = ic.main(base_args(repo, home, "--remove", "demo"))
        assert code == 0
        assert (scripts / "demo.sh").exists()
        assert "sin marca" in capsys.readouterr().out

    def test_job_desconocido(self, tmp_path, monkeypatch, capsys):
        repo, home = self._setup(tmp_path, monkeypatch, [])
        code = ic.main(base_args(repo, home, "--remove", "otro"))
        assert code == 2
        assert "no hay job" in capsys.readouterr().err

    def test_sin_hermes(self, tmp_path, monkeypatch, capsys):
        repo, home = tmp_path / "repo", tmp_path / "home"
        write_manifest(repo, [_job_t()])
        monkeypatch.setattr(
            ic, "hermes_cli", lambda: (_ for _ in ()).throw(ic.ManifestError("sin binario"))
        )
        code = ic.main(base_args(repo, home, "--remove", "demo"))
        assert code == 2


def no_agent_job(**overrides) -> "ic.Job":
    """Job no_agent minimo para probar el argv."""
    base = dict(
        name="demo",
        description="demo",
        schedule="0 9 * * *",
        mode="no_agent",
        deliver="origin",
        enabled=True,
        wrapper="demo.sh",
        command="bash bin/demo.sh",
    )
    base.update(overrides)
    return ic.Job(**base)


def agent_job(**overrides) -> "ic.Job":
    """Job de agente con prompt y skills."""
    return no_agent_job(
        name="agente",
        mode="agent",
        wrapper="",
        command="",
        prompt="Haz algo util",
        skills=["hermes-agent"],
        model="deepseek-flash",
        provider="deepseek",
        **overrides,
    )


class TestSmoke:
    """--smoke corre no_agent en sandbox y no toca el estado real (#257)."""

    def test_omite_deny_list_y_no_escribe_en_el_home_real(self, tmp_path, capsys):
        repo = tmp_path / "repo"
        real = tmp_path / "real"
        write_manifest(
            repo,
            [
                demo_manifest_job(command="bash child.sh"),
                demo_manifest_job(
                    name="backup-diario",
                    wrapper="backup-diario.sh",
                    command="uv run backup-diario",
                ),
                {
                    "name": "agente",
                    "schedule": "0 9 * * *",
                    "mode": "agent",
                    "deliver": "origin",
                    "prompt": "hola",
                },
            ],
        )
        sentinel = real / "cron" / "jobs.json"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("intacto", encoding="utf-8")
        vistos: list[dict[str, str]] = []

        def runner(argv, env):
            vistos.append(env)
            assert env["HERMES_HOME"] != str(real)
            assert env["HOME"] == str(Path.home())
            assert env["PATH"] == ic.SMOKE_PATH
            assert env["HERMES_SCRIPTS_DIR"] == str(repo)
            return subprocess.CompletedProcess(argv, 0, "ok\n", "")

        args = ic.build_parser().parse_args(base_args(repo, real, "--smoke"))
        ctx = ic.prepare_run(args)
        code = ic.run_smoke(ctx, runner=runner)
        out = capsys.readouterr().out
        assert code == 0
        assert len(vistos) == 1
        assert "demo: rc=0" in out
        assert "backup-diario: omitido (muta)" in out
        assert "agente: omitido (agent)" in out
        assert sentinel.read_text(encoding="utf-8") == "intacto"

    def test_un_fallo_deja_rc_1(self, tmp_path, capsys):
        repo = tmp_path / "repo"
        write_manifest(repo, [demo_manifest_job(command="bash child.sh")])

        def runner(argv, env):
            return subprocess.CompletedProcess(argv, 3, "", "boom")

        args = ic.build_parser().parse_args(base_args(repo, tmp_path / "real", "--smoke"))
        code = ic.run_smoke(ic.prepare_run(args), runner=runner)
        out = capsys.readouterr().out
        assert code == 1
        assert "demo: rc=3" in out
        assert "boom" in out


class TestArgvContraElCLI:
    """El argv debe respetar el contrato real de `hermes cron create/edit` (issue #147).

    Verificado contra Hermes v0.21.3:
    - `create` recibe el schedule (y el prompt) POSICIONALES: no existen --schedule, --prompt ni
      --agent; el flag de skills es --skill (repetible).
    - `edit` si acepta --schedule/--prompt/--skill (el manifiesto usa --skill, no --add-skill).
    """

    def test_create_no_usa_flags_de_schedule_ni_prompt(self):
        argv = ic.create_args(no_agent_job(), {}, "demo.sh")
        assert argv[0] == "0 9 * * *"
        assert "--schedule" not in argv
        assert "--prompt" not in argv
        assert "--agent" not in argv

    def test_create_agent_pone_el_prompt_posicional(self):
        argv = ic.create_args(agent_job(), {}, "demo.sh")
        assert argv[0] == "0 9 * * *"
        assert argv[1] == "Haz algo util"

    def test_create_usa_skill_repetible(self):
        argv = ic.create_args(agent_job(), {}, "demo.sh")
        assert "--skill" in argv
        assert "--add-skill" not in argv

    def test_edit_usa_schedule_y_prompt_como_flags(self):
        argv = ic.edit_args(agent_job(), {}, "demo.sh")
        assert argv[:2] == ["--schedule", "0 9 * * *"]
        assert "--prompt" in argv
        assert "--add-skill" not in argv

    def test_apply_plan_crea_con_schedule_posicional(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: calls.append(cmd))
        monkeypatch.setattr(ic, "read_live_jobs", lambda home: [])
        ic.apply_plan([no_agent_job()], {}, tmp_path, REPO)
        assert calls[0][:4] == ["hermes", "cron", "create", "0 9 * * *"]

    def test_apply_plan_edita_con_flags(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(ic, "hermes_cli", lambda: "hermes")
        monkeypatch.setattr(ic, "run", lambda cmd: calls.append(cmd))
        monkeypatch.setattr(
            ic,
            "read_live_jobs",
            lambda home: [fake_job(id="keepme", name="demo", script="demo.sh")],
        )
        ic.apply_plan([no_agent_job()], {}, tmp_path, REPO)
        assert calls[0][:5] == ["hermes", "cron", "edit", "keepme", "--schedule"]
        assert calls[0][5] == "0 9 * * *"


@pytest.mark.skipif(shutil.which("hermes") is None, reason="CLI de Hermes no disponible (CI)")
class TestContratoConElCLI:
    """Falla si el argv usa un flag que el CLI real no acepta: evita repetir #147."""

    @staticmethod
    def _aceptados(*args: str) -> set[str]:
        result = subprocess.run(["hermes", "cron", *args, "--help"], capture_output=True, text=True)
        return set(re.findall(r"--[a-z][a-z-]+", result.stdout + result.stderr))

    @staticmethod
    def _flags(argv: list[str]) -> set[str]:
        return {arg for arg in argv if arg.startswith("--")}

    def test_flags_de_create_existen(self):
        aceptados = self._aceptados("create")
        usados = self._flags(ic.create_args(agent_job(), {}, "demo.sh"))
        faltantes = sorted(usados - aceptados)
        assert not faltantes, f"`hermes cron create` no acepta: {faltantes}"

    def test_flags_de_edit_existen(self):
        aceptados = self._aceptados("edit")
        usados = self._flags(ic.edit_args(agent_job(), {}, "demo.sh"))
        faltantes = sorted(usados - aceptados)
        assert not faltantes, f"`hermes cron edit` no acepta: {faltantes}"


class TestManifestFueraDeLaVentanaPeak:
    """Los jobs que gastan CPU no deben caer en la ventana peak de DeepSeek.

    Peak: 01:00-04:00 y 06:00-10:00 UTC de lunes a viernes = 19:00-22:00 y
    00:00-04:00 en Monterrey (UTC-6).
    """

    def test_backup_diario_no_arranca_en_peak(self):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = [job for job in ic.parse_jobs(manifest) if job.name == "backup-diario"]
        assert len(jobs) == 1
        schedule = jobs[0].schedule
        minute, hour, *_ = schedule.split()
        start = int(hour) + int(minute) / 60
        assert not (0 <= start < 4), f"backup-diario cae en peak: {schedule}"
        assert not (19 <= start < 22), f"backup-diario cae en peak: {schedule}"


class TestUpdateSemanalDesacoplado:
    """El job agent del update semanal no puede reiniciar el gateway que lo hospeda (#221).

    Medido el 2026-09-18: la corrida del 2026-09-13 murió con "Interrupted by
    shutdown before terminal completion" porque el update reinicia el propio
    `hermes-gateway.service` que hospeda el cron. El reinicio debe quedar
    **agendado** (systemd-run) para que la corrida termine y entregue el resumen.
    """

    @staticmethod
    def _job():
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = [j for j in ic.parse_jobs(manifest) if j.name == "Hermes weekly update + backup"]
        assert len(jobs) == 1
        return jobs[0]

    def test_el_job_sigue_siendo_agent(self):
        # Los conflictos de merge del update necesitan criterio: no es un script.
        assert self._job().mode == "agent"

    def test_prompt_no_invoca_hermes_update(self):
        job = self._job()
        # El prompt nombra la orden prohibida para explicar por qué no se usa: lo
        # que se comprueba es que no la invoque.
        assert "hermes update --backup" not in job.prompt
        assert "NO uses `hermes update`" in job.prompt

    def test_prompt_hace_el_update_a_mano(self):
        job = self._job()
        assert "git -C /usr/local/lib/hermes-agent merge origin/main" in job.prompt
        assert "uv sync --frozen" in job.prompt

    def test_prompt_agenda_el_reinicio_desacoplado(self):
        job = self._job()
        assert "systemd-run" in job.prompt
        assert "--on-active" in job.prompt


# ═══════════════════════════════════════════
# Expectativas del día (#217)
# ═══════════════════════════════════════════

AHORA = datetime(2026, 9, 18, 11, 0)  # viernes


def _job_dict(name="job", expr="0 8 * * *", enabled=True, created_at=None, job_id="abc123"):
    """Job como lo lee `read_live_jobs()`."""
    job = {
        "id": job_id,
        "name": name,
        "enabled": enabled,
        "schedule": {"expr": expr},
    }
    if created_at is not None:
        job["created_at"] = created_at.isoformat()
    return job


def _run(hora, status="completed", delivery=None, scheduled=None):
    """Corrida como la normaliza `read_runs()`."""
    return {
        "started_at": hora,
        "scheduled_instant": scheduled if scheduled is not None else hora,
        "status": status,
        "delivery_outcome": delivery,
    }


class TestExpectativasDelDia:
    """Qué debía correr hoy y no corrió (#217).

    Medido en el spike del 2026-09-18: el chequeo ingenuo da 356 falsos positivos
    (`suppressed` es el 59% de las entregas), declara perdidos jobs que no
    disparan hoy, tiene off-by-one en la hora base y no conoce la fecha de alta
    ni el catch-up del scheduler.
    """

    def test_ocurrencias_incluyen_la_hora_base(self):
        # `*/30 * * * *` a las 11:00: 00:00 incluida y tope de gracia (10:45) = 22.
        assert len(ic.occurrences_today("*/30 * * * *", AHORA)) == 22

    def test_ocurrencias_de_un_job_diario(self):
        assert ic.occurrences_today("0 8 * * *", AHORA) == [datetime(2026, 9, 18, 8, 0)]

    def test_sin_ocurrencias_cuando_el_schedule_no_dispara_hoy(self):
        # Viernes: el job dominical no tiene nada que hacer hoy.
        assert ic.occurrences_today("0 4 * * 0", AHORA) == []
        assert ic.occurrences_today("0 10 * * 1", AHORA) == []

    def test_respeta_la_ventana_de_gracia(self):
        # El scheduler recupera corridas perdidas (catch_up_occurrences): a las
        # 08:05 todavía no se puede declarar perdida la de las 08:00.
        assert ic.occurrences_today("0 8 * * *", datetime(2026, 9, 18, 8, 5)) == []
        assert ic.occurrences_today("0 8 * * *", datetime(2026, 9, 18, 8, 20)) == [
            datetime(2026, 9, 18, 8, 0)
        ]

    def test_no_espera_corridas_anteriores_al_alta_del_job(self):
        alta = datetime(2026, 9, 18, 9, 50)
        esperadas = ic.expected_runs([_job_dict(expr="0 4 * * *", created_at=alta)], AHORA)
        assert esperadas == {}

    def test_job_deshabilitado_no_genera_expectativa(self):
        esperadas = ic.expected_runs([_job_dict(enabled=False)], AHORA)
        assert esperadas == {}

    def test_espera_la_ocurrencia_de_un_job_diario_vivo(self):
        esperadas = ic.expected_runs(
            [_job_dict(job_id="j1", expr="0 8 * * *", created_at=datetime(2026, 9, 1))], AHORA
        )
        assert esperadas == {"j1": [datetime(2026, 9, 18, 8, 0)]}

    @pytest.mark.parametrize("delivery", [None, "delivered", "suppressed"])
    def test_entregas_sanas(self, delivery):
        assert ic.delivery_verdict("completed", delivery) == ic.VERDICT_OK

    def test_entrega_fallida_es_hallazgo(self):
        assert ic.delivery_verdict("completed", "failed") == ic.VERDICT_FAILED

    def test_corrida_fallida_es_hallazgo(self):
        assert ic.delivery_verdict("failed", "delivered") == ic.VERDICT_FAILED

    def test_digest_silencioso_con_el_estado_sano(self):
        jobs = [
            _job_dict(job_id="j1", name="resumen-noticias-diario", expr="30 8 * * *"),
            _job_dict(job_id="j2", name="cleanup-housekeeping", expr="0 6 * * *"),
        ]
        runs = {
            "j1": [_run(datetime(2026, 9, 18, 8, 30), delivery="delivered")],
            "j2": [_run(datetime(2026, 9, 18, 6, 0), delivery="suppressed")],
        }
        assert ic.doctor_digest(jobs, runs, AHORA) == []

    def test_digest_reporta_la_corrida_perdida(self):
        jobs = [_job_dict(job_id="j1", name="job-scout daily run", expr="0 8 * * *")]
        lineas = ic.doctor_digest(jobs, {}, AHORA)
        assert len(lineas) == 1
        assert "job-scout daily run" in lineas[0]
        assert "08:00" in lineas[0]

    def test_digest_reporta_la_entrega_fallida(self):
        jobs = [_job_dict(job_id="j1", name="resumen-noticias-diario", expr="30 8 * * *")]
        runs = {"j1": [_run(datetime(2026, 9, 18, 8, 30), delivery="failed")]}
        lineas = ic.doctor_digest(jobs, runs, AHORA)
        assert len(lineas) == 1
        assert "resumen-noticias-diario" in lineas[0]
        assert "entrega" in lineas[0]

    def test_digest_reporta_la_corrida_fallida(self):
        jobs = [_job_dict(job_id="j1", name="runtime-sync", expr="25 4 * * *")]
        runs = {"j1": [_run(datetime(2026, 9, 18, 4, 25), status="failed")]}
        lineas = ic.doctor_digest(jobs, runs, AHORA)
        assert len(lineas) == 1
        assert "runtime-sync" in lineas[0]

    def test_una_corrida_tardia_cubre_su_ocurrencia(self):
        """El catch-up corre minutos después: no es una corrida perdida."""
        jobs = [_job_dict(job_id="j1", name="job-scout daily run", expr="0 8 * * *")]
        runs = {"j1": [_run(datetime(2026, 9, 18, 8, 9), scheduled=datetime(2026, 9, 18, 8, 0))]}
        assert ic.doctor_digest(jobs, runs, AHORA) == []


class TestJobDiarioDelDoctor:
    """El manifiesto declara el job diario con el comando de expectativas (#217)."""

    @staticmethod
    def _job():
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = [j for j in ic.parse_jobs(manifest) if j.name == "cron-doctor-daily"]
        assert len(jobs) == 1
        return jobs[0]

    def test_existe_y_es_no_agent(self):
        assert self._job().is_no_agent

    def test_corre_a_las_11_tras_la_tanda_de_la_manana(self):
        assert self._job().schedule == "0 11 * * *"

    def test_usa_el_modo_de_expectativas(self):
        assert "--expectations" in self._job().command
