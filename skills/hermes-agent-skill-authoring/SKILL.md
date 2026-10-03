---
name: hermes-agent-skill-authoring
description: Use when escribes una skill en skills/ de este repo. El tope de 60 caracteres no rige aquí.
disable-model-invocation: true
source: https://github.com/NousResearch/hermes-agent
upstream: skills/software-development/hermes-agent-skill-authoring/SKILL.md
---

# Escribir una skill en este repo (parche)

El original dice cómo se commitea una skill **dentro de NousResearch/hermes-agent**. Aquí el árbol es
otro. Se carga el original para el oficio (frontmatter, no duplicar, referencias aparte) y se aplican
las diferencias de abajo. El parche que vivía sólo en el perfil no estaba en esta máquina: esto es la
diferencia medida contra ese `SKILL.md` (v2.0.0) y contra las skills que ya están en `skills/`.

## Dónde vive el archivo

| El original | Este repo |
|---|---|
| `skills/<categoría>/<nombre>/SKILL.md` | `skills/<nombre>/SKILL.md` |
| `optional-skills/` | no existe. Si no es de este repo, no se versiona (ADR 0003) |
| categoría en el path | categoría sólo en el symlink de `config/runtime-clones.json` |
| `skill_manage(action='create')` | no escribe en este árbol. El archivo entra por el PR |

`name:` del frontmatter es el nombre de la carpeta. Lo afirma `tests/test_skills_del_repo.py`.

## Qué del original no se copia

- **Descripción de ≤ 60 caracteres.** Es la hardline de hermes-agent. Las skills de este repo abren con
  `Use when` y pasan de 60. No recortes una descripción para cumplir el otro repo.
- **`author: Nombre (handle), Hermes Agent`.** Las skills de aquí firman `Hermes Agent` cuando firman.
  Esa regla aplica si el PR es contra hermes-agent, no contra este.
- **Tests en `tests/skills/test_<skill>_skill.py` y el generador de docs del website.** Aquí el contrato
  lo cubren `tests/test_skills_del_repo.py` (el link existe, el `name` coincide, no hay id de canal) y,
  si la skill es independiente, `config/skills.json` con `tests/test_check_skills.py`.
- **`platforms:` y `related_skills` obligatorios.** Úsalos si la skill ya los trae. Un `related_skills`
  tiene que nombrar una skill que esté en este árbol en el mismo PR.

## Qué sí se trae

- El frontmatter abre en el primer byte con `---` y cierra antes del cuerpo.
- La descripción es el disparador. El detalle va al cuerpo: el índice paga `name` + `description` en
  cada turno (`ecc-context-budget`).
- Nada de rutas `/home/...`, ids de canal ni tokens (ADR 0003). El test rechaza `-100` seguido de 6 dígitos.
- Un paso termina en algo que se puede comprobar.
- Material largo va a `references/`, no al cuerpo.
- `disable-model-invocation: true` en un adapter que sólo se lee cuando se nombra.

## Verificación

```bash
uv run pytest tests/test_skills_del_repo.py tests/test_check_skills.py -q
```

Cada skill nueva de `skills/` tiene su entrada en `links` de `config/runtime-clones.json`. Sin esa
entrada el job `runtime-sync` no vigila el symlink.
