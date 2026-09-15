"""Tests de src/install_cron.py y del manifiesto cron/jobs.json.

Estrategia de validacion (sin dependencias nuevas ni tocar el Hermes real):

- unitarios: expresiones cron, resolucion de destinos, render de wrappers;
- invariantes del repo: el manifiesto real valida, ningun archivo versionado
  tiene rutas /home/<usuario>, todos los bin/*.sh pasan `bash -n`;
- integracion sin efectos: apply_plan/verify con `run` monkeypatcheado contra
  un HERMES_HOME temporal (se valida el argv que se enviaria a hermes cron).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

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
