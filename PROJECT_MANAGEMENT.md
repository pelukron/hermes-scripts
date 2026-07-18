# Project Management Setup — hermes-scripts

Jira-style project management para `hermes-scripts` usando GitHub-native features.

## 🚀 Quick Start / Mini Tour

> _Guía usable con o sin CLI. Todo se puede hacer desde la web de GitHub._

### 📍 Donde está todo

| Recurso | Link |
|---|---|
| **Project Board** (kanban) | [github.com/users/pelukron/projects/3](https://github.com/users/pelukron/projects/3) |
| **Milestones** | [github.com/pelukron/hermes-scripts/milestones](https://github.com/pelukron/hermes-scripts/milestones) |
| **Epics abiertos** | [Issues labeled `👑 epic`](https://github.com/pelukron/hermes-scripts/issues?q=is%3Aissue+label%3A%22%F0%9F%91%91+epic%22+is%3Aopen) |
| **Roadmap** | [README.md#roadmap](README.md#roadmap) (futuro) |
| **Agent tracking** | [`.hermes/EPICS_TRACKING.md`](.hermes/EPICS_TRACKING.md) |
| **Current Epic** | [#58 Security & Tooling Quick Wins](https://github.com/pelukron/hermes-scripts/issues/58) |

---

### 🎯 Crear un epic — desde la web

1. Ve a [Issues → New Issue](https://github.com/pelukron/hermes-scripts/issues/new/choose)
2. Selecciona el template **Epic**
3. Llena:
   - **Title**: `[Epic] Nombre del bloque`
   - **Goal**: Una frase de lo que se logra
   - **Success criteria**: Checklist de cómo saber que está terminado
   - **Priority**: `p0` (crítico) a `p3` (baja)
4. Click **Submit new issue**
5. Asígnale un milestone desde la barra derecha del issue
6. Agrega labels manualmente: `size: M`, etc.

---

### 🎯 Crear epic — desde CLI

```bash
# 1. Crear el epic
gh issue create --template epic

# 2. Agregar labels
gh issue edit <N> --add-label "👑 epic,priority: p1 · high,size: M"

# 3. Asignar milestone
gh issue edit <N> --milestone "v0.4.0 — Security & Tooling"

# 4. Agregar al Project Board
gh project item-add 3 --owner pelukron --url "https://github.com/pelukron/hermes-scripts/issues/<N>"
```

---

### 📝 Agregar sub-issues (tareas hijas)

**Desde la web:**
1. Abre el epic issue
2. Crea un nuevo issue normal (feature/bug/chore)
3. Copia el link y pégalo en el checklist del epic: `- [ ] #N Descripción`

**Desde CLI:**
```bash
# Crear sub-issue
gh issue create --title "feat: descripción" --body "..." --label "✨ enhancement,size: S"

# Editar el body del epic para agregarlo al checklist
gh issue edit <EPIC_N> --body "$(gh issue view <EPIC_N> --json body --jq '.body')\n- [ ] #<N> descripción"
```

---

### 📋 Usar el Project Board

El board tiene 3 vistas (tabs en la web):

| Vista | Para qué sirve |
|---|---|
| **Board** | Kanban: arrastra tarjetas entre `Todo → In Progress → Done` |
| **Roadmap** | Línea de tiempo con milestones y fechas límite |
| **Table** | Vista hoja de cálculo, agrupa por Priority/Size/Block |

**Campos custom en cada tarjeta:**
- `Priority`: 🔴 p0 → ⚪ p3
- `Size`: XS → XL
- `Block`: número de bloque (1-3)
- `Status`: Todo / In Progress / Done

---

### 🔄 Flujo completo: de idea a done

```
1. Idea ──→ Crear Epic Issue (template epic)
              ├── Goal + Success criteria
              ├── Label: 👑 epic + priority + size
              └── Milestone: v0.X.0

2. Plan ──→ Crear sub-issues
              ├── Un issue por cada tarea concreta
              ├── Label: ✨ enhancement / 🐛 bug / 📚 docs
              └── Agregar al checklist del epic

3. Work ──→ Project Board
              ├── Agregar issues al board (gh project item-add)
              ├── Mover tarjetas: Todo → In Progress → Done
              └── Actualizar checklist del epic

4. Done ──→ Cerrar epic cuando todo el checklist esté ✅
```

---

## Overview

```
Epic Issue ──→ Milestone ──→ GitHub Project (kanban)
   │                │               │
   └─ Sub-issues ───┘               ├── Board view (Todo → In Progress → Done)
                                    ├── Roadmap view (Gantt timeline)
                                    └── Table view (spreadsheet)
```

## Labels

| Category | Labels |
|---|---|
| **Type** | `👑 epic`, `✨ enhancement`, `🐛 bug`, `📚 documentation`, `🔧 chore`, `🚨 hotfix` |
| **Priority** | `priority: p0 · critical`, `p1 · high`, `p2 · medium`, `p3 · low` |
| **Size** | `size: XS` (< 1h), `S` (1-4h), `M` (1-2d), `L` (3-5d), `XL` (> 1w) |
| **Status** | `🚧 blocked` |

## Milestones

| Milestone | Due | Scope |
|---|---|---|
| [v0.4.0 — Security & Tooling](https://github.com/pelukron/hermes-scripts/milestone/1) | 2026-07-31 | Quick wins de seguridad + extender mypy/bandit |
| [v0.5.0 — Performance & Concurrency](https://github.com/pelukron/hermes-scripts/milestone/2) | 2026-08-15 | requests.Session, concurrencia feeds, límites de descarga |
| [v0.6.0 — Refactor & Maintainability](https://github.com/pelukron/hermes-scripts/milestone/3) | 2026-09-15 | Estructura src/scripts, news_utils, logging, dataclasses |

## Epic Issues

Epics son issues padre que agrupan sub-issues. Usan label `👑 epic` y checklist body.

### Current epics

| Epic | Milestone | Status |
|---|---|---|
| [#TBD](https://github.com/pelukron/hermes-scripts/issues/) Security & Tooling Quick Wins | v0.4.0 | 🆕 Todo |
| [#TBD](https://github.com/pelukron/hermes-scripts/issues/) Performance & Concurrency | v0.5.0 | 🆕 Todo |
| [#TBD](https://github.com/pelukron/hermes-scripts/issues/) Maintainability Refactor | v0.6.0 | 🆕 Todo |

### Creating a new epic

1. Go to Issues → New Issue → **Epic** template
2. Fill in goal, success criteria, and sub-issues checklist
3. Assign to a milestone
4. Add priority and size labels

```bash
# CLI alternative
gh issue create --template epic
```

## GitHub Project Board ✅

> **Board URL:** [hermes-scripts](https://github.com/users/pelukron/projects/3)

### Setup

Board ya creado. Vistas recomendadas:

| View | Type | Layout | Purpose |
|---|---|---|---|---|
| **Board** | Kanban | Status columns | Day-to-day task tracking |
| **Roadmap** | Gantt | Date + milestone | High-level timeline |
| **By Block** | Table | Group by Block field | See progress per epic block |

### Workflow

1. Add epic issues to the project
2. Add sub-issues to the project (they auto-group under epics)
3. Move cards: `Todo → In Progress → In Review → Done`
4. Use Roadmap view to see milestones on timeline

## Automation ✅

### Auto-add to Project Board

New issues labeled `👑 epic` se agregan automáticamente al [Project Board](https://github.com/users/pelukron/projects/3) via `.github/workflows/project-automation.yml`.

**Trigger:** issue labeled `👑 epic`  
**Requires:** `PROJECT_PAT` secret with `project` scope

```bash
# Set up the secret (one-time)
gh secret set PROJECT_PAT --body "ghp_..." --repo pelukron/hermes-scripts
```

## CLI quick reference

```bash
# List milestones
gh api repos/pelukron/hermes-scripts/milestones --jq '.[] | "\(.title) — \(.due_on)"'

# Create epic
gh issue create --template epic

# Add issue to milestone
gh issue edit <N> --milestone "v0.4.0 — Security & Tooling"

# Filter by epic
gh issue list --label "👑 epic"

# View milestone progress
gh api repos/pelukron/hermes-scripts/milestones/1 --jq '{title, open_issues, closed_issues}'

# Add issue to project board
gh project item-add 3 --owner pelukron --url "https://github.com/pelukron/hermes-scripts/issues/<N>"
```

## 🤖 Hermes Agent Contributor

| Campo | Diego (humano) | Hermes Agent (bot) |
|---|---|---|
| **git user.name** | `Diego Moreno` | `Hermes Agent` |
| **git user.email** | `diego@example.com` | `hermes-agent@nousresearch.com` |
| **GitHub login** | `pelukron` | — (sin cuenta) |
| **Permisos** | Admin + merge | PRs y commits |
| **Alcance** | Global (~/.gitconfig) | Solo este repo (--local) |

### Setup

```bash
cd hermes-scripts

git config --local user.name "Hermes Agent"
git config --local user.email "hermes-agent@nousresearch.com"
```

### Reglas

- **Hermes Agent** crea branches, commits y PRs
- **@pelukron** revisa, aprueba y mergea
- Prohibido: `--force`, `--amend` después de push
- Un commit por cambio lógico
- Cada PR cierra un sub-issue con `Closes #N` en el body

## Related docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — PR workflow, commit conventions
- [CHANGELOG.md](CHANGELOG.md) — Release notes
- [README.md](README.md) — Project overview
- [`.hermes/EPICS_TRACKING.md`](.hermes/EPICS_TRACKING.md) — Agent tracking de épicas

## 📝 Agent Tracking

Durante el trabajo del agente, se mantiene `.hermes/EPICS_TRACKING.md` con:
- Épicas activas
- Sub-issues en progreso
- PRs abiertos
- Bloqueos
- Decisiones pendientes

Esto permite handoffs y continuidad entre sesiones.
