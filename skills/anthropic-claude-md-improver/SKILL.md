---
name: anthropic-claude-md-improver
description: Use when auditas o recortas AGENTS.md o una skill del repo. Adaptación Hermes de claude-md-improver.
disable-model-invocation: true
source: https://github.com/anthropics/claude-plugins-official
upstream: plugins/claude-md-management/skills/claude-md-improver/SKILL.md
---

# Mejorar el contexto que el agente carga (adapter)

El original audita `CLAUDE.md` de Claude Code y, tras un reporte, lo edita. Aquí el archivo que el
agente carga al entrar al repo es `AGENTS.md`. `CONTEXT.md` es el glosario, no ese archivo. El texto
leído es el `SKILL.md` de `main` el 2026-10-02. El adapter del perfil no estaba en esta máquina.

## Mapa

| En el original | Aquí |
|---|---|
| `./CLAUDE.md` | `AGENTS.md` |
| `./.claude.local.md` | no se versiona. Secretos e ids van fuera del repo (ADR 0003) |
| `~/.claude/CLAUDE.md` | no se toca desde un PR de este repo |
| `packages/*/CLAUDE.md` | `skills/<nombre>/SKILL.md` cuando el contexto es de una skill |
| Atajo `#` de Claude | no existe. Lo que se aprende entra por PR |

## Orden

1. Encontrar los archivos (`AGENTS.md`, y la skill que el usuario nombró). No recorras el árbol entero
   buscando cualquier markdown.
2. Puntuar cada uno con la rúbrica del original, en este orden de peso: comandos que se pueden copiar,
   arquitectura que se entiende, gotchas no obvias, vigencia, si se puede ejecutar, brevedad.
3. Publicar el reporte **antes** de editar. Nota por criterio, no un ensayo.
4. Proponer sólo el añadido que falta (el comando que ya no es verdad, el gotcha medido). Mostrar el
   diff. Parar hasta que el operador diga que sí.
5. Aplicar el diff sin reescribir el resto del archivo.

## Qué no meter

- Lo que ya se ve leyendo el código.
- Un consejo genérico («escribe tests»).
- Un arreglo de una sola vez que no va a repetirse.
- Ids de canal, tokens o rutas de un home concreto.

## Reglas Hermes

1. Español. Una línea por hallazgo.
2. Un comando documentado se prueba o se marca como no probado. No copies un comando del original
   (`npm run dev`) si este repo no lo tiene.
3. El reporte es el entregable. El edit es el segundo paso, y sólo con un sí.
