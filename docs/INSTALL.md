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

## Verificar

```bash
bin/install-cron.sh --check                      # sin drift = instalado como dice el manifiesto
uv run python src/install_cron.py --check --quiet  # modo job: vacio si ok, digest si hay drift
uv run python src/install_cron.py --doctor         # salud de la flota (job semanal cron-doctor-check)
hermes cron list                                 # jobs activos (los no-agent se ven por jobs.json)
python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.hermes/cron/jobs.json').read_text()); [print(j['name'], j.get('script'), j.get('no_agent')) for j in d['jobs']]"
```

## Aviso semanal de drift

El job `cron-drift-check` (lunes 10:00, `no_agent`, `deliver: origin`) ejecuta
`--check --quiet`: con todo en orden no imprime nada (el job no entrega nada,
cero tokens); con drift entrega el digest `Cron drift — <fecha>` + remedio.
Solo avisa, nunca auto-repara: aplicar sigue siendo `bin/install-cron.sh`.
Los jobs creados por el agente fuera del manifiesto salen como líneas `info:`
en el `--check` manual, sin contar como drift.

## Quitar

```bash
hermes cron remove <job_id>            # por job (id en hermes cron list / jobs.json)
rm ~/.hermes/scripts/<wrapper>.sh      # opcional: los wrappers generados
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
