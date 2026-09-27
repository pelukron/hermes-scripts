#!/usr/bin/env bash
# slug.sh — Única regla de slug para ramas y worktrees (#344).
#
# Se SOURCEA (no se ejecuta) desde bin/bump-and-pr.sh y bin/gh-issue:
#
#     # shellcheck source=bin/slug.sh
#     . "$SCRIPT_DIR/slug.sh"
#     SLUG="$(slug "$descripcion")"
#
# Regla: minúsculas, todo lo que no sea [a-z0-9] pasa a '-', se colapsan los guiones,
# se recortan las puntas y se corta a MAX_SLUG **en frontera de palabra**.
#
# El tope es corto a propósito: `git branch` falla el ref cuando el componente del
# `.lock` pasa de 255 bytes (medido, git 2.53.0 sobre ext4: 207 chars OK, 257 falla con
# `cannot lock ref … File name too long`), y el directorio del worktree lleva el mismo
# slug (PATH_MAX del path completo, componentes de 255 bytes). Con 40 el techo deja de
# depender del título del issue, que es lo que no estaba declarado.
#
# Una sola constante: para subir o bajar el tope se toca aquí.

MAX_SLUG="${MAX_SLUG:-40}"

slug() {
    local limpio
    limpio="$(printf '%s' "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$//')"

    if [ "${#limpio}" -le "$MAX_SLUG" ]; then
        printf '%s' "$limpio"
        return 0
    fi

    # Recorta a MAX_SLUG y suelta la última palabra si el corte cayó a media palabra.
    # Si la primera palabra ya es más larga que el tope no hay frontera que respetar:
    # el `sed` no encuentra guion y deja el corte duro.
    printf '%s' "$(printf '%s' "$limpio" | cut -c1-"$MAX_SLUG" | sed 's/-[^-]*$//')"
}
