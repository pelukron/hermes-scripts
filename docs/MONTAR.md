# Montar

`bin/setup-wizard.sh` lleva un clon fresco hasta el gate verde. Los pasos de esta página son los que el script ejecuta. Si un paso falla, el wizard se detiene: se corrige lo que indica y se vuelve a correr. Cada paso se puede repetir.

Los jobs y los destinos de chat no salen de aquí. Eso está en [`INSTALL.md`](INSTALL.md). Qué mensaje llega después, a qué hora y a qué destino, está en [`USUARIO.md`](USUARIO.md).

## Requisitos

- Un clon de este repo. El wizard se coloca en su raíz.
- `git` en el PATH.
- `uv` en `$UV`, en el PATH, o en `$HOME/.hermes/bin/uv`.
- Para el paso del token, salvo `--sin-token`: una línea `GITHUB_TOKEN=` en `${HERMES_HOME:-$HOME/.hermes}/.env`. El wizard comprueba que está. No crea ni rota el token.
- El clon ya trae `.githooks/`, `hooks/`, `pyproject.toml` y `.pre-commit-config.yaml`.

## Comandos

```bash
bin/setup-wizard.sh --dry-run    # muestra el plan y el estado; no escribe
bin/setup-wizard.sh              # pregunta antes de escribir si hay terminal
bin/setup-wizard.sh --yes        # escribe sin preguntar
bin/setup-wizard.sh --sin-token  # no exige GITHUB_TOKEN (el gate local no lo necesita)
bin/setup-wizard.sh --sin-gate   # monta y deja el gate para después
bin/setup-wizard.sh --help
```

## Los siete pasos

1. Comprueba que `git` y `uv` responden. No instala ninguno. Si falta `uv`: <https://docs.astral.sh/uv/>.
2. `git config core.hooksPath .githooks`
3. `uv sync --dev`
4. `pre-commit install`, o `uv run pre-commit install` si el comando no está en el PATH.
5. Busca `^GITHUB_TOKEN=` en el `.env` de Hermes.
6. Copia `hooks/` a `${HERMES_HOME:-$HOME/.hermes}/hooks`.
7. `bash bin/gate.sh`

El gate es ese único comando. Por dentro corre, en este orden: comprobación del lock, ruff, formato, shellcheck, mypy, bandit, pip-audit y pytest.

## Si un paso falla

El propio wizard dice cómo seguir. El arreglo, en corto:

| Paso | Qué hacer y volver a correr `bin/setup-wizard.sh` |
|---|---|
| 1 | Instalar el que falte (`git` o `uv`). |
| 2 | Leer el error de `git config`. |
| 3 | Leer la salida de `uv` (red, lock). |
| 4 | Leer la salida de `pre-commit`. |
| 5 | Crear un token en <https://github.com/settings/tokens> y guardarlo como `GITHUB_TOKEN=<token>` en el `.env`. Con `--sin-token` este paso se salta. |
| 6 | Revisar permisos de `$HERMES_HOME/hooks`. |
| 7 | El gate quedó rojo. La tabla de abajo. |

## Fallos típicos del gate

Estos ya se vieron en un `main` limpio. El rojo es del entorno con el que se lanzó el comando.

| Qué ves | Arreglo |
|---|---|
| `make: uv: No such file or directory` | `uv` no está en el PATH que usa `make`. Lanzar el gate así: `PATH="$HOME/.hermes/bin:$PATH" TMPDIR=/tmp bash bin/gate.sh` |
| `test_install_cron` rojo por una ruta bajo `/home/…` | Falta `TMPDIR=/tmp`. La misma línea de arriba. El temporal de pytest cayó dentro del home. |
| `Disk quota exceeded` en `git init --bare`, y caen tests de `test_sync_runtime.py` | `/tmp` es un tmpfs de 2.6 GB y va por encima del 80 %. Misma línea, con `TMPDIR=/var/tmp`. |
| `falta shellcheck en el PATH` | El gate lo exige. En la máquina del gate: `sudo apt-fast install -y shellcheck`. En CI entra por apt. |
| En Windows el gate no arranca | Falta `make`. El gate completo corre en Linux (CI y la máquina de Hermes). Git Bash (`C:\Program Files\Git\usr\bin\bash.exe`) sólo para los scripts. La receta medida está en `skills/github-pelukron-flow` §«Entorno por sistema». |
| `uv lock --check` dice que `uv.lock` no coincide | Entre el release y el commit `chore: sync uv.lock`, un clon nuevo falla aquí. `git fetch origin` y `git merge --ff-only origin/main` traen ese sync. |

Un rojo de ruff, mypy o pytest que nombra el archivo que acabas de tocar sí es del cambio: se corrige eso y se vuelve a correr el wizard.
