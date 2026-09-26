# ADR 0007 — El .py sin modo chequea; el bash sin modo aplica

- Estado: aceptado
- Fecha: 2026-09-26
- Issue: #323

## Contexto

`src/install_cron.py` sin flags hacía upsert en Hermes. `bin/check-drift.sh` tenía que
forzar `--check` para no mutar, y un `python src/install_cron.py` a secas instalaba.
El comando que ya está documentado (`bin/install-cron.sh` después del merge, y el
remedio del digest de drift) sí tiene que instalar.

## Decisión

1. El `.py` sin modo hace `--check` y no escribe. `--apply` es el único camino que muta.
2. `bin/install-cron.sh` sin modo ejecuta `--apply`. Si el operador ya pasó un modo
   (`--check`, `--dry-run`, `--smoke`, `--doctor`, `--expectations`, `--remove`,
   `--init-targets`), el bash no añade `--apply`.
3. Un solo modo por invocación. Dos modos salen con código 2. `--quiet` solo con
   `--check`. `--force` solo con `--apply`.

## Consecuencias

Quien lea solo uno de los dos entrypoints va a creer que el otro está mal. No lo está:
el bash es el instalador que ya citan los docs; el `.py` es el que invocan los jobs y
un shell con prisa. `check-drift.sh` sigue pasando `--check` explícito.
