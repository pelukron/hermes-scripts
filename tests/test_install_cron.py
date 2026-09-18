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
        assert "info: job 'otro' existe en Hermes pero no en el manifiesto" in out

    def test_manifiesto_real_trae_cron_drift_check(self, tmp_path):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        assert len(jobs) == 15
        found = [job for job in jobs if job.name == "cron-drift-check"]
        assert len(found) == 1
        job = found[0]
        assert job.schedule == "0 10 * * 1"
        assert job.is_no_agent
        assert job.wrapper == "cron-check.sh"
        assert "--check --quiet" in job.command
        assert job.deliver == "origin"
        wrapper = tmp_path / "cron-check.sh"
        wrapper.write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
        result = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

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
