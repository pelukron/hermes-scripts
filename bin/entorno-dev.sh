#!/usr/bin/env bash
# entorno-dev.sh — Pasos de montaje del entorno de desarrollo, definidos una sola vez (#327).
#
# Se SOURCEA (no se ejecuta) desde los dos métodos que conviven (D1):
#   - setup.sh (raíz): método corto, política «avisa y sigue».
#   - bin/setup-wizard.sh: wizard guiado, política estricta.
#
# Ejemplo:
#     # shellcheck source=bin/entorno-dev.sh
#     . "$SCRIPT_DIR/bin/entorno-dev.sh"
#     paso_uv_sync || exit 1
#
# Pre-commit NO es uno de los pasos (#418): el paso de git hooks fija `core.hooksPath`, y
# `pre-commit install` se niega a instalar con esa variable puesta. El lint lo cubre el gate;
# a mano queda `uv run pre-commit run --all-files` (lo que llama bin/bump-and-pr.sh).
#
# Política (D2): ENTORNO_DEV_ESTRICTO decide qué pasa cuando un paso falla.
#   0 (defecto) = avisa con ⚠️ y devuelve 0 — el llamador sigue.
#   1           = informa con ❌ y devuelve 1 — el llamador para y explica.
# Cada paso verifica su propio efecto antes de cantar ✅. Los pasos son
# idempotentes: re-ejecutar tras un fallo retoma donde quedó.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "entorno-dev.sh no se ejecuta: se sourcea desde setup.sh o bin/setup-wizard.sh" >&2
    exit 2
fi

ENTORNO_DEV_ESTRICTO="${ENTORNO_DEV_ESTRICTO:-0}"

# _fallo_o_aviso <mensaje> — informa según la política y devuelve el rc que toca
# (0 en laxo para que el llamador siga, 1 en estricto para que pare).
_fallo_o_aviso() {
    if [ "${ENTORNO_DEV_ESTRICTO:-0}" = "1" ]; then
        echo "  ❌ $1"
        return 1
    fi
    echo "  ⚠️  $1"
    return 0
}

# entorno_dev_uv — resuelve el binario de uv ($UV, PATH o $HOME/.hermes/bin/uv).
# Imprime la ruta, o nada si no lo encuentra. No escribe nada.
entorno_dev_uv() {
    local uv_bin
    uv_bin="${UV:-}"
    if [ -z "$uv_bin" ]; then
        uv_bin="$(command -v uv || true)"
    fi
    if [ -z "$uv_bin" ] && [ -x "$HOME/.hermes/bin/uv" ]; then
        uv_bin="$HOME/.hermes/bin/uv"
    fi
    printf '%s' "$uv_bin"
}

# verificar_prerrequisitos — solo lee (apta para --dry-run): git y uv presentes.
verificar_prerrequisitos() {
    local ok=0
    local version
    if command -v git >/dev/null 2>&1; then
        version="$(git --version 2>/dev/null || true)"
        echo "  ✅ git: $version"
    else
        _fallo_o_aviso "git no encontrado — instálalo antes de seguir"
        ok="$?"
    fi
    local uv_bin
    uv_bin="$(entorno_dev_uv)"
    if [ -n "$uv_bin" ]; then
        version="$("$uv_bin" --version 2>/dev/null || true)"
        echo "  ✅ uv: $version ($uv_bin)"
    else
        _fallo_o_aviso "'uv' no encontrado (PATH, \$UV o \$HOME/.hermes/bin/uv) — https://docs.astral.sh/uv/"
        ok="$?"
    fi
    return "$ok"
}

# paso_git_hooks — fija core.hooksPath a .githooks y verifica que quedó.
paso_git_hooks() {
    if [ ! -d ".githooks" ]; then
        _fallo_o_aviso "Directorio .githooks no encontrado"
        return "$?"
    fi
    if ! git config core.hooksPath .githooks; then
        _fallo_o_aviso "no se pudo fijar core.hooksPath"
        return "$?"
    fi
    local actual
    actual="$(git config core.hooksPath 2>/dev/null || true)"
    if [ "$actual" = ".githooks" ]; then
        echo "  ✅ Git hooks configurados (.githooks/pre-push)"
        return 0
    fi
    _fallo_o_aviso "core.hooksPath quedó en '$actual', esperaba '.githooks'"
    return "$?"
}

# paso_uv_sync — instala dependencias. El rc de uv decide: no se traga (D2).
paso_uv_sync() {
    if [ ! -f "pyproject.toml" ]; then
        _fallo_o_aviso "pyproject.toml no encontrado — salto dependencias"
        return "$?"
    fi
    local uv_bin
    uv_bin="$(entorno_dev_uv)"
    if [ -z "$uv_bin" ]; then
        _fallo_o_aviso "'uv' no encontrado — salto dependencias"
        return "$?"
    fi
    if "$uv_bin" sync --dev; then
        echo "  ✅ Dependencias instaladas (uv)"
        return 0
    fi
    _fallo_o_aviso "uv sync falló"
    return "$?"
}

# paso_github_token — comprueba presencia de GITHUB_TOKEN. No crea ni rota secretos.
paso_github_token() {
    local env_file
    env_file="${HERMES_HOME:-$HOME/.hermes}/.env"
    if [ -f "$env_file" ] && grep -q "^GITHUB_TOKEN=" "$env_file"; then
        echo "  ✅ GITHUB_TOKEN encontrado"
        return 0
    fi
    _fallo_o_aviso "GITHUB_TOKEN no configurado en $env_file"
    return "$?"
}

# paso_gateway_hooks — copia hooks/ a $HERMES_HOME/hooks y verifica entrada por entrada.
paso_gateway_hooks() {
    if [ ! -d "hooks" ]; then
        _fallo_o_aviso "Directorio hooks no encontrado"
        return "$?"
    fi
    local hooks_dir
    hooks_dir="${HERMES_HOME:-$HOME/.hermes}/hooks"
    mkdir -p "$hooks_dir"
    if ! cp -r hooks/. "$hooks_dir/"; then
        _fallo_o_aviso "no se pudo copiar hooks/ a $hooks_dir"
        return "$?"
    fi
    local nombre
    for nombre in hooks/*; do
        if [ -e "$hooks_dir/$(basename "$nombre")" ]; then
            continue
        fi
        _fallo_o_aviso "$nombre no quedó en $hooks_dir tras la copia"
        return "$?"
    done
    echo "  ✅ Gateway hooks instalados ($hooks_dir)"
    return 0
}
