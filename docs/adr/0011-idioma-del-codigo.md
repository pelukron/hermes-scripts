# ADR 0011 — El código nuevo va en inglés; la prosa sigue en español

- Estado: aceptado
- Fecha: 2026-10-04
- Issue: #411

## Contexto

La revisión de arquitectura del 2026-10-04 dejó una regla sin escribir. Al aterrizar #325 (PR #410), el guard
nuevo de `cron_canary` salió en español —`entradas_sin_resolver`, con sus docstrings— y hubo que renombrarlo
en un commit de seguimiento (`b7b76ab`) para no dejar el código nuevo fuera de la regla que el operador pidió:
**el código va en inglés**.

La convención escrita decía lo contrario: nombres de artefactos nuevos en inglés, pero «contenido
(comentarios, docs, prompts) en español» (`AGENTS.md:59-61`, `CONTEXT.md:36-37`). Con esa regla, el código en
inglés se lee como un error y la siguiente sesión lo «corrige» de vuelta.

## Decisión

1. **`*.py` y `bin/*.sh`: identificadores, comentarios y docstrings en inglés.** Aplica al código **nuevo** y
   a lo que se toque de un archivo viejo mientras se toca por otro motivo.
2. **Prosa en español**: `.md` (`CONTEXT.md`, ADRs, `README.md`, `docs/`) y comentarios de configuración
   (`pyproject.toml`, `cron/jobs.json`, `config/*.json`), porque son documentación, no código.
3. **Los mensajes de commit siguen convencionales en español** (`feat:`, `fix:`, `infra:`): los lee quien
   revisa el repo y `python-semantic-release` arma con ellos las notas del release.
4. **Los artefactos vivos con nombre en español no se renombran** (`backup-diario`, `reporte-uso-hermes`,
   `resumen-*`, `aviso-*`, `emitir_secciones`): `install-cron.sh` empareja **por nombre**, así que renombrar
   produce drift en `--check`, deja el job anterior huérfano y borra su historial de corridas.
5. **Sin PR de traducción masiva.** El código viejo se migra cuando se toque por otro motivo; mientras, los
   archivos quedan mixtos **a propósito**.

## Alternativas rechazadas

| Opción | Por qué no |
|---|---|
| Traducir el árbol entero de una vez | Diff enorme sin cambio de comportamiento, imposible de revisar, y toca archivos que ningún issue está cambiando. |
| Dejar la regla vieja (todo el contenido en español) | Es lo que produjo el renombrado de `b7b76ab`: la regla pedida y la escrita no coincidían, y quien llegaba después adivinaba. |
| Renombrar también los artefactos vivos | Drift en `install-cron.sh --check`, job huérfano y pérdida del historial de corridas. El nombre en español de un job no le molesta a nadie. |

## Consecuencias

- Archivos mixtos por diseño: `src/cron_canary.py` tiene `_piezas` (viejo, en español) y `unresolved_entries`
  (nuevo, en inglés). No es descuido y no se «arregla» en un PR de limpieza.
- **No hay gate de idioma en este repo**: no existe un test que cuente español en el árbol (los aciertos de
  «español» en `src/` y `tests/` son de **fechas** en español: `news_utils.py:765`,
  `test_resumen_tigres.py:528`). La regla se sostiene con revisión, no con un assert; un conteo congelado
  sería otro issue.
- `CONTEXT.md` §3 y `AGENTS.md` apuntan aquí, así que un explorador futuro —o un agente— no propondrá volver
  al español para el código nuevo.
