# Instalación

De cero a tus cron jobs corriendo, sin editar nada a mano.

## Requisitos

- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) instalado y con el gateway corriendo (`hermes gateway status`).
- `uv` (o exporta `UV=/ruta/a/uv`).
- Opcional: `gh` autenticado, solo si vas a usar el flujo de PRs (`bin/bump-and-pr.sh`).

## Pasos

```bash
git clone https://github.com/pelukron/hermes-scripts.git ~/hermes-scripts
cd ~/hermes-scripts
uv sync

# 1. Destinos de entrega (IDs de chat fuera del repo)
cp cron/targets.example.json cron/targets.local.json
$EDITOR cron/targets.local.json      # pon tus chat_id reales
# o en una sola: crea desde el ejemplo si falta + valida contra el manifiesto
uv run python src/install_cron.py --init-targets

# 2. Revisa el plan y el estado actual
bin/install-cron.sh --dry-run        # qué va a hacer
bin/install-cron.sh --check          # deseado vs real (exit 1 si hay drift)

# 3. Aplica (idempotente: se puede repetir sin duplicar nada)
bin/install-cron.sh
```

`install-cron.sh` hace tres cosas:

1. **Wrappers portables** en `$HERMES_HOME/scripts/` (generados; no se editan a mano).
2. **Upsert de jobs** con `hermes cron create/edit`, emparejando por nombre.
3. **Verificación (read-back)**: relee `~/.hermes/cron/jobs.json` y compara
   schedule, script, `no_agent`, deliver, enabled y modelo. Si algo no coincide, sale 1.

## Personalizar

- **Qué corre y cuándo:** `cron/jobs.json` es la fuente de verdad. Cambia `schedule`,
  `enabled` o borra la entrada y vuelve a correr `bin/install-cron.sh`.
- **Fuentes de noticias:** `config/feeds.json`.
- **A quién entrega:** `cron/targets.local.json` (nombres usados como `${reports}` en el manifiesto).
- **Jobs que no aplican a tu caso:** deshabilítalos con `"enabled": false` — el instalador los pausa
  (`monitor-ram-mexico` viene así, y `job-scout daily run` requiere el repo externo `hermes-empleo`).
- **Testigo externo (dead-man's switch):** crea un check en [healthchecks.io](https://healthchecks.io)
  (periodo 1 día, gracia ~2 h) y pon `HEALTHCHECK_PING_URL=https://hc-ping.com/<uuid>` en
  `$HERMES_HOME/.env`. La auditoría nocturna hace ping `/start` al arrancar y success/`/fail`
  al terminar. Sin esa variable los pings son no-op.

## Verificar

```bash
bin/install-cron.sh --check                      # sin drift = instalado como dice el manifiesto
uv run python src/install_cron.py --check --quiet  # modo job: vacio si ok, digest si hay drift
uv run python src/install_cron.py --doctor         # salud de la flota (job semanal cron-doctor-check)
hermes cron list                                 # jobs activos (los no-agent se ven por jobs.json)
python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.hermes/cron/jobs.json').read_text()); [print(j['name'], j.get('script'), j.get('no_agent')) for j in d['jobs']]"
```

## Verificar un job `no_agent` nuevo (condiciones de cron)

Tu shell interactiva **no** es el entorno del cron: la tuya trae `uv` y `~/.hermes/bin` en el PATH, la del
gateway no. Un job puede dar exit 0 a mano y morir a la hora programada — así fallaron `adopted-sha-audit`
(05:00) y `cron-canary` (02:30) en su primer horario, con `FileNotFoundError: [Errno 2] ... 'uv'` (#254).

Regla: **ningún `subprocess` a una herramienta externa usa el nombre relativo.** Para `uv` hay un solo
resolver, `hermes_common.uv_bin()` (`$UV` → PATH → `~/.hermes/bin/uv`); si no está en ninguno de los tres
devuelve `"uv"`, para que el paso falle con el error de siempre en vez de en silencio.

```bash
# entorno mínimo, como el del cron: exit 0 y stdout vacío = verde
env -i HOME=$HOME PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  /bin/bash ~/.hermes/scripts/<job>.sh
```

- Con `HERMES_HOME` y `HERMES_SCRIPTS_DIR` apuntas la corrida a un estado o a un clon de prueba sin tocar el
  real (útil para no ensuciar `adopted-sha-history.json` ni el sandbox del canary).
- Si el job vive en un **worktree**, el chequeo de drift no puede salir limpio: los wrappers embeben la ruta
  del repo donde se renderizaron. Su verificación completa es desde el clon desplegado.
- Un job no está verificado por haber corrido una vez: las corridas programadas son las que cierran el DoD.

## Aviso semanal de drift

El job `cron-drift-check` (lunes 10:00, `no_agent`, `deliver: origin`) ejecuta
`--check --quiet`: con todo en orden no imprime nada (el job no entrega nada,
cero tokens); con drift entrega el digest `Cron drift — <fecha>` + remedio.
Solo avisa, nunca auto-repara: aplicar sigue siendo `bin/install-cron.sh`.
Los jobs creados por el agente fuera del manifiesto salen como líneas `info:`
en el `--check` manual, sin contar como drift.

## Quitar

```bash
uv run python src/install_cron.py --remove <nombre>  # hermes cron remove + borra wrapper generado
# manual equivalente:
hermes cron remove <job_id>            # por job (id en hermes cron list / jobs.json)
rm ~/.hermes/scripts/<wrapper>.sh      # opcional: los wrappers generados
```

## Hooks del gateway (back-online)

`hooks/gateway-back-online/` avisa al canal personal cuando el gateway
arranca tras estar apagado (evento `gateway:startup`, envío directo sin
agente). Requiere en el entorno del gateway `TELEGRAM_BOT_TOKEN` y
`TELEGRAM_HOME_CHANNEL` (mismo chat de los avisos peak).

```bash
./setup.sh                               # instala hooks/ en ~/.hermes/hooks/
hermes gateway restart                   # probar: reinicia el gateway
hermes logs --follow | grep back-online  # verificado si sale el aviso
```

## Validación del repo (lo que corre CI)

```bash
make check                             # lint + format + typecheck + security + test
uv run pytest tests/test_install_cron.py -q
```

`tests/test_install_cron.py` valida, además de la lógica:

- que el manifiesto real (`cron/jobs.json`) pase las reglas (cron válido, sin duplicados,
  `deliver` resoluble, `mode` coherente con `command`/`prompt`);
- que **ningún archivo versionado** tenga rutas `/home/<usuario>` (el repo es portable);
- que todos los `bin/*.sh` pasen `bash -n`;
- el plan completo (`create`/`edit`/`pause`) con `run` monkeypatcheado, sin tocar tu Hermes.
