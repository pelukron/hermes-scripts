---
name: hermes-dev-flow
description: "Flujo completo de desarrollo para repos Hermes: grill, plan, bump-and-pr, code-review, merge. Usar antes de cualquier cambio en scripts, skills o configuracion."
disable-model-invocation: true
related_skills: [mattpocock-grill, plan, mattpocock-code-review]
---

# Flujo de Desarrollo Hermes

Workflow completo para cambios en repos Hermes. Una skill que orquesta todo el ciclo.

## Skills requeridas

| Paso | Skill | Cuando |
|---|---|---|
| 1. Alinear | `/mattpocock-grill` | Antes de empezar cualquier feature |
| 2. Planear | `plan` skill | Despues del grill, antes de tocar codigo |
| 3. Ejecutar | `bump-and-pr.sh` | Para crear rama + bump + changelog + PR |
| 4. Revisar | `/mattpocock-code-review` | Antes de mergear, con sub-agentes |
| 5. Merge | Manual en GitHub | Solo si CI pasa y review OK |

## Flujo paso a paso

### 1. Alinear (`/mattpocock-grill`)
```
/mattpocock-grill
```
- Entrevista una pregunta a la vez
- Define alcance, enfoque, riesgos
- NO ejecutar sin confirmacion

### 2. Planear
```
Escribe plan a .hermes/plans/YYYY-MM-DD_HHMMSS-descripcion.md
```
- Tasks bite-sized (2-5 min)
- Paths exactos, codigo completo
- Esperar aprobacion antes de ejecutar

### 3. Ejecutar (`bump-and-pr.sh`)
```bash
cd ~/.hermes/scripts
./bump-and-pr.sh <patch|minor|major> "tipo: descripcion" "- cambio 1" "- cambio 2"
```
Que hace:
- Crea Issue en GitHub (con label automatico)
- Crea rama `tipo/descripcion`
- Bump version en pyproject.toml
- Actualiza CHANGELOG.md (formato Keep a Changelog)
- Commit con `Closes #N`
- Push + crea PR vinculado al Issue

### 4. Revisar (`/mattpocock-code-review`)
```
/mattpocock-code-review
```
- Fixed point: tag anterior a HEAD
- 2 sub-agentes en paralelo: Standards + Spec
- Reporte con hallazgos
- Corregir issues antes de mergear

### 5. Merge
- Revisar PR en GitHub
- CI debe pasar (ruff + pytest + notify)
- Merge manual: Issue se cierra solo
- Crear tag: `git tag -a vX.Y.Z -m "vX.Y.Z: descripcion" && git push --tags`

## Reglas

- No push directo a main
- PR obligatorio
- CHANGELOG actualizado en cada cambio
- Conventional commits (`feat:`, `fix:`, `docs:`, etc.)
- Tests pasan antes de merge
- Grill antes de empezar

## Referencias

- Repo: `~/.hermes/scripts/` - [pelukron/hermes-scripts](https://github.com/pelukron/hermes-scripts)
- Scripts externos: `~/.hermes/skills/external/`
- Update externals: `~/.hermes/scripts/update-external-skills.sh`
- Planes: `.hermes/plans/`