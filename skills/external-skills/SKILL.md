---
name: external-skills
description: Patrón para adoptar skills de terceros (mattpocock, vercel-labs, etc.) como adapters Hermes. Usar al evaluar o instalar skills externas.
disable-model-invocation: true
---

# External Skills Adoption

Clonar repo externo como fuente de verdad. Crear adapter skill Hermes con reglas de adaptación. `git pull` para actualizar.

## Layout

```
~/.hermes/skills/
├── external/                    # git clones
│   └── <autor>-skills/
└── productivity/                # adapters Hermes
    └── <autor>-<skill>/SKILL.md
```

## Instalación por defecto (CLI `skills`)

Desde 2026-09-27 el instalador por defecto es el CLI de `vercel-labs/skills` (npm global, `~/.local/bin/skills`):

```bash
export PATH="$HOME/.local/bin:$PATH"
skills add <owner>/<repo> -l --agent hermes-agent            # reconocer sin instalar
skills add <owner>/<repo> -s <skill> -a hermes-agent -g -y   # instalar (global)
skills list -g                                               # inventario
skills find "<query>"                                        # catálogo público (skills.sh)
skills update                                                # actualizar lo instalado
skills remove <skill>                                        # desinstalar
```

- **Soporta Hermes nativo**: `--agent hermes-agent` → global `~/.hermes/skills/`, proyecto `.hermes/skills/`.
- Instala en la **raíz** de `~/.hermes/skills/<skill>/`, no bajo `external/`: cada skill instalada entra al
  índice con su `description` en inglés (por eso se instala de a una, con `-s`).
- Devuelve un bloque de seguridad por skill (`gen`, socket, snyk) y acepta `--json` para leer el resultado.
- **Antes de instalar: ¿ya lo tenemos?** Con 199 skills cargadas el nombre nuevo no es hueco; y `-l` evita
  clonar repos enormes (`affaan-m/ecc`: 99 MB y 903 SKILL.md, de los que ~290 son distintos).
- El clon disperso a mano sigue sirviendo para leer un upstream **sin** instalarlo, pero ya no es el camino
  por defecto.

## Skills de referencia (bajadas, sin indexar)

`~/referencia-skills/{obra-superpowers,ecc,anthropics-skills}` = clones completos (15 / 903 / 20 SKILL.md,
119 MB) **fuera** de `~/.hermes/skills`: se consultan con `read_file` cuando hacen falta y **no pagan contexto
por turno**. Activarlas cuando se necesiten, de a una:

```bash
export PATH="$HOME/.local/bin:$PATH"
skills add <owner>/<repo> -s <skill> -a hermes-agent -g -y
```

**Regla para elegir entre lo nuestro y lo externo** (la librería se mantiene arriba; nosotros somos el delta):

- **Nuestra copia está adaptada** (menciona Hermes, `pelukron/*`, `~/.hermes`) → se queda. Retirarla pierde
  conocimiento local. Medido el 2026-09-27: `requesting-code-review` 285 líneas nuestras contra 95 del upstream;
  `systematic-debugging` 411 vs 283; `test-driven-development` 362 vs 330.
- **Nuestra copia es un fork fiel y viejo** (sólo difiere por el tiempo) → se retira y se instala el upstream,
  que se actualiza con `skills update`.
- **No la tenemos** → se instala la externa; no se copia a mano.
- **La licencia no lo permite** (`anthropics/skills`: `docx`/`pdf`/`pptx`/`xlsx` son source-available, no open
  source) → se queda la nuestra.
- **Mismo nombre, otro contenido** no es duplicado: comprobarlo con `diff` antes de tocar nada (`manim-video`
  aparecía duplicada entre ecc y `creative/`, y son cosas distintas).

## Adapter Template

```yaml
---
name: <autor>-<skill>
description: <desc español>. Adaptación Hermes de <autor>/<skill>.
disable-model-invocation: true
source: <url repo>
upstream: ~/.hermes/skills/external/<autor>-skills/skills/<path>/SKILL.md
# si vino del CLI: upstream: ~/.hermes/skills/<skill>/SKILL.md
---
```

### Reglas Hermes obligatorias

1. **Idioma:** Español
2. **Caveman:** Brevedad
3. **Plan mode:** Integrar `.hermes/plans/`
4. **Telegram:** Markdown optimizado
5. **Herramientas:** Usar herramientas Hermes, NO Claude Code/Codex/GitHub CLI

## Evaluación previa

| Criterio | Adoptar | Skip |
|---|---|---|
| Principios agnósticos de lenguaje | ✅ | ❌ |
| Específico de framework (React, Next.js) | ❌ | ✅ |
| Herramienta/binario (redundante) | ❌ | ✅ |
| CLI package manager (competidor) | ❌ | ✅ |

## Actualización

```bash
bash ~/hermes-scripts/bin/update-external-skills.sh   # recorre ~/.hermes/skills/external/*/ y hace git pull --ff-only
```

## Adapters existentes

| Adapter | Upstream | Estado |
|---|---|---|
| `mattpocock-grill` | mattpocock/grilling | ✅ |
| `mattpocock-grill-docs` | mattpocock/grill-with-docs + domain-modeling | ✅ |
| `superpowers-receiving-code-review` | obra/superpowers → skills/receiving-code-review | ✅ 2026-09-27 |

## Textos bajados

Estos tres no tienen adapter. El procedimiento está en el archivo descargado. Aquí sólo está cuándo
leerlo y qué de este repo el original no sabe. No se copia ese texto a otro `SKILL.md`.

| Cuándo | Archivo | Commit | Qué cambia aquí |
|---|---|---|---|
| Un diff traga un error | `vendor/skills/silent-failure-hunter/silent-failure-hunter.md` | `anthropics/claude-plugins-official` `d182ca45` | El silencio de un job `no_agent` en verde es el contrato. No hay Sentry ni `errorIds.ts`. |
| Auditar el contexto que carga el agente | `vendor/skills/claude-md-improver/SKILL.md` | el mismo commit | El archivo es `AGENTS.md`, no `CLAUDE.md`. |
| Añadir una skill a este repo | `vendor/skills/hermes-agent-skill-authoring/SKILL.md` | `NousResearch/hermes-agent` `e09e4018` | El path de aquí es `skills/<nombre>/SKILL.md` más el enlace en `config/runtime-clones.json`. El manual describe el otro repo. |

`resuming-interrupted-work` no se baja: la fusión del perfil no tiene archivo público. Retomar un corte sigue en `ecc-handoff-memory`.

## Pitfalls

- **Nunca copiar** — Desync garantizado. Siempre git clone + adapter.
- **Verificar relevancia** — Mayoría de skills externas son frontend. Solo adoptar si principios son agnósticos.
- **User-invoked default** — `disable-model-invocation: true` ahorra contexto.
- **El clon completo se paga en el índice, en cada turno.** Medido el 2026-09-27: `affaan-m/ecc` trae
  **903** SKILL.md (99 MB, de los que ~290 son skills distintas y el resto traducciones a 6 idiomas),
  `anthropics/skills` 20 y `obra/superpowers` 15. Por eso el clon entra **disperso y sólo con lo adoptado**
  (`--filter=blob:none --sparse` + `git sparse-checkout set <lo que sí>`), y la evaluación se hace sobre un
  clon de scratch, no dentro de `~/.hermes/skills/external/`.
- **Licencia antes que utilidad.** Un repo sin `LICENSE` en la raíz no es adoptable sin leer sus términos: el
  README de `anthropics/skills` declara que `docx`/`pdf`/`pptx`/`xlsx` son **source-available, no open
  source** (los demás Apache-2.0). `gh api repos/<o>/<r> --jq .license.spdx_id` primero; `null` = leer a mano.
- **Antes de adoptar, mirar si ya lo tenemos.** Con 199 skills cargadas, «nombre nuevo» no es «hueco»: el
  solapamiento real se mide comparando el **concepto** contra el índice, no el título (3 de los 15 de
  superpowers eran duplicado exacto de nombre, y otros 8 cubrían el mismo proceso con otro nombre).
- **El clon completo paga contexto dos veces**: cada `SKILL.md` bajo `external/<repo>/` entra al índice de
  skills en cada turno, aunque nunca lo uses. Medido: el marketplace `claude-plugins-official` trae **31**
  SKILL.md que este despliegue no quiere. Clonar sparse y traer sólo el plugin adoptado:
  `git clone --filter=blob:none --sparse <url> && git sparse-checkout set plugins/<plugin>` — queda en ~120 KB
  y el loader sólo ve los `SKILL.md` del plugin cuyo `skills/` hayas traído: **0** si el plugin sólo trae
  `agents/` (`pr-review-toolkit`), **1** si trae una skill (`claude-md-management`). Añadir otro después:
  `git sparse-checkout add plugins/<otro>`.
  Los `agents/*.md` y `commands/*.md` de un plugin **no** los lee el loader: sólo se cargan cuando el adapter
  los manda cargar con `read_file`.
