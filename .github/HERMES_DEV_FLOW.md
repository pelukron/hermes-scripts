---
name: hermes-dev-flow
description: "Pipeline de desarrollo para repos Hermes: grill, plan, bump-and-pr, code-review, merge."
disable-model-invocation: true
related_skills: [mattpocock-grill, plan, mattpocock-code-review]
---

# Pipeline de Desarrollo

Un pipeline deterministico para cambios en repos Hermes. Cinco puertas. Cada puerta tiene un completion criterion verificable.

## Puertas del pipeline

### Puerta 1: Alinear
**Skill:** `/mattpocock-grill`
**Criterion:** Diego confirma "entendimiento compartido".

- Entrevista una pregunta a la vez.
- Decisiones son del usuario, hechos del codebase.
- No continuar sin confirmacion explicita.

### Puerta 2: Planear
**Skill:** `plan`
**Criterion:** Plan escrito en `.hermes/plans/` con tasks bite-sized. Diego aprueba.

- Tasks de 2-5 minutos.
- Paths exactos, codigo completo, verificacion por paso.
- No tocar codigo hasta aprobacion.

### Puerta 3: Ejecutar
**Script:** `bump-and-pr.sh`
**Criterion:** PR creado en GitHub con CI en verde.

```bash
cd ~/.hermes/scripts
./bump-and-pr.sh <patch|minor|major> "tipo: descripcion" "- cambio"
```

El script crea: Issue, rama semantica, bump version, CHANGELOG, commit con Closes #N, push, PR.
Commit message usa conventional commits.

### Puerta 4: Revisar
**Skill:** `/mattpocock-code-review`
**Criterion:** 0 hallazgos hard de Standards. Spec conforme al commit message.

- Fixed point: tag anterior a HEAD.
- Dos sub-agentes en paralelo: Standards + Spec.
- Corregir issues encontrados antes de mergear.

### Puerta 5: Merge
**Accion:** Manual en GitHub.
**Criterion:** CI verde + review OK + Diego aprueba.

- Merge via GitHub UI.
- Issue se cierra automaticamente (Closes #N).
- Tag manual: `git tag -a vX.Y.Z && git push --tags`.

## Reglas

- No push directo a main.
- CHANGELOG actualizado en cada cambio.
- Conventional commits.
- Tests pasan antes de merge.

## Pitfalls

| Problema | Causa | Solucion |
|---|---|---|
| Saltar grill | Creer que el cambio es obvio | Grill SIEMPRE, incluso cambios pequenos |
| Premature completion | Paso parece hecho pero no | Verificar criterion antes de avanzar |
| CI rojo en PR | No correr tests local | `uv run pytest` antes de pushear |
| sed falla en changelog | Guiones en entrada | Usar python3 (ya corregido en bump-and-pr) |

## Referencias

- [pelukron/hermes-scripts](https://github.com/pelukron/hermes-scripts)
- `~/.hermes/scripts/bump-and-pr.sh`
- `~/.hermes/skills/external/` (mattpocock skills)
- `.hermes/plans/`