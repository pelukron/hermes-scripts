#!/usr/bin/env bash
# setup-wizard.sh — Wizard de montaje: de clon fresco a gate verde (#327, hija de #322).
#
# Uso:
#   bin/setup-wizard.sh             # guía paso a paso (pregunta antes de escribir si hay TTY)
#   bin/setup-wizard.sh --yes       # ejecuta sin preguntar
#   bin/setup-wizard.sh --dry-run   # muestra el plan y el estado actual, no escribe nada
#   bin/setup-wizard.sh --sin-gate  # monta sin correr el gate final
#   bin/setup-wizard.sh --sin-token # no exige GITHUB_TOKEN (el gate local no lo necesita)
#   bin/setup-wizard.sh --help      # esta ayuda
#
# Estricto: si un paso falla, el wizard para (rc≠0) y explica cómo seguir.
# Los pasos son idempotentes: re-ejecutar tras un fallo retoma donde quedó.
#
# Pre-commit queda FUERA del arranque (#418): el paso 2 fija `core.hooksPath` y
# `pre-commit install` se niega a instalar con esa variable puesta. El lint lo cubre el
# gate, y a mano queda `uv run pre-commit run --all-files` (lo que llama bump-and-pr.sh).
#
# Lo que este wizard NO hace (fuera de alcance, #322): cron
# (bin/install-cron.sh), secretos (solo comprueba GITHUB_TOKEN) ni targets.local.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

ENTORNO_DEV_ESTRICTO=1
# shellcheck source=bin/entorno-dev.sh
. "$REPO_DIR/bin/entorno-dev.sh"

ayuda() {
    echo "Uso: bin/setup-wizard.sh [--yes] [--dry-run] [--sin-gate] [--sin-token]"
    echo ""
    echo "Lleva un clon fresco a gate verde, paso a paso y verificando cada paso:"
    echo "  1) prerrequisitos (git, uv)  2) git hooks  3) uv sync"
    echo "  4) GITHUB_TOKEN  5) gateway hooks  6) gate (bash bin/gate.sh)"
    echo ""
    echo "Flags:"
    echo "  --yes        no pregunta antes de escribir (para pipes y CI)"
    echo "  --dry-run    muestra el plan y el estado, no escribe nada"
    echo "  --sin-gate   monta sin correr el gate final (lento: lint + tipos + tests)"
    echo "  --sin-token  no exige GITHUB_TOKEN; el gate local no lo necesita"
    echo "  -h, --help   esta ayuda"
    echo ""
    echo "No hace: cron (usa bin/install-cron.sh), secretos ni targets.local."
    echo "Si un paso falla, corrige lo que indica y re-ejecuta: retoma donde quedó."
    echo "Al terminar: docs/MONTAR.md (montaje y gate) y docs/USUARIO.md (qué llega)."
}

dry_run=0
auto_si=0
sin_gate=0
sin_token=0
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            ayuda
            exit 0
            ;;
        --dry-run)
            dry_run=1
            ;;
        --yes)
            auto_si=1
            ;;
        --sin-gate)
            sin_gate=1
            ;;
        --sin-token)
            sin_token=1
            ;;
        *)
            echo "setup-wizard: flag desconocido '$arg'" >&2
            ayuda >&2
            exit 2
            ;;
    esac
done

echo "🧙 Wizard de montaje de hermes-scripts (issue #327)"
echo "   Monta: prerrequisitos, git hooks, dependencias,"
echo "          GITHUB_TOKEN, gateway hooks y gate."
echo "   No monta: cron (bin/install-cron.sh), secretos ni targets.local."

if [ "$dry_run" -eq 1 ]; then
    echo ""
    echo "Plan (--dry-run: no escribo nada):"
    echo "  1) verificar prerrequisitos (git, uv)"
    echo "  2) git config core.hooksPath .githooks"
    echo "  3) uv sync --dev"
    echo "  4) comprobar GITHUB_TOKEN en \${HERMES_HOME:-\$HOME/.hermes}/.env"
    echo "  5) copiar hooks/ a \$HERMES_HOME/hooks"
    echo "  6) bash bin/gate.sh"
    echo ""
    echo "Estado actual (solo lectura):"
    verificar_prerrequisitos || true
    if [ "$sin_token" -eq 1 ]; then
        echo "  ➖ GITHUB_TOKEN: omitido por --sin-token"
    else
        paso_github_token || true
    fi
    if [ -d ".githooks" ]; then
        echo "  ✅ .githooks presente en el clon"
    else
        echo "  ❌ .githooks ausente en el clon"
    fi
    if [ "$sin_gate" -eq 1 ]; then
        echo "  ➖ gate: omitido por --sin-gate"
    elif [ -f "bin/gate.sh" ]; then
        echo "  ✅ gate disponible (bin/gate.sh)"
    else
        echo "  ❌ bin/gate.sh no encontrado"
    fi
    exit 0
fi

if [ "$auto_si" -eq 0 ] && [ -t 0 ]; then
    respuesta=""
    read -r -p "¿Ejecutar estos pasos? [S/n] " respuesta || respuesta="n"
    case "$respuesta" in
        [Ss]|"")
            ;;
        *)
            echo "Anulado: no se escribió nada."
            exit 0
            ;;
    esac
fi

paso_n=0
total=6
anuncia() {
    paso_n=$((paso_n + 1))
    echo ""
    echo "── Paso $paso_n/$total — $1"
    echo "   $2"
}
siguiente() {
    echo "   Siguiente: $1"
}
falla() {
    echo "  ❌ $1"
    echo "   Cómo seguir: $2"
    exit 1
}

anuncia "Prerrequisitos" "compruebo git y uv antes de tocar nada."
verificar_prerrequisitos || falla "faltan prerrequisitos." \
    "instálalos y re-ejecuta bin/setup-wizard.sh."
siguiente "fijar los git hooks del repo."

anuncia "Git hooks" "apunto core.hooksPath a .githooks (hook pre-push del repo)."
paso_git_hooks || falla "no quedaron los git hooks." \
    "revisa el error de git config y re-ejecuta bin/setup-wizard.sh."
siguiente "instalar las dependencias Python con uv."

anuncia "Dependencias" "uv sync --dev instala lo fijado en uv.lock."
paso_uv_sync || falla "uv sync no completó." \
    "revisa tu red y la salida de uv, y re-ejecuta bin/setup-wizard.sh."
siguiente "comprobar GITHUB_TOKEN."

anuncia "GITHUB_TOKEN" "solo compruebo que existe en \$HERMES_HOME/.env; no creo secretos."
if [ "$sin_token" -eq 1 ]; then
    echo "  ➖ Omitido por --sin-token (el gate local no lo necesita)."
else
    paso_github_token || falla "falta GITHUB_TOKEN en \$HERMES_HOME/.env." \
        "crea un token en https://github.com/settings/tokens, guárdalo como GITHUB_TOKEN=<token> en \$HERMES_HOME/.env y re-ejecuta bin/setup-wizard.sh (o usa --sin-token si solo quieres el gate local)."
fi
siguiente "copiar los gateway hooks."

anuncia "Gateway hooks" "copio hooks/ a \$HERMES_HOME/hooks (avisos del propio Hermes)."
paso_gateway_hooks || falla "no se copiaron los gateway hooks." \
    "revisa permisos de \$HERMES_HOME/hooks y re-ejecuta bin/setup-wizard.sh."
siguiente "correr el gate completo."

anuncia "Gate" "bash bin/gate.sh: lint, tipos, seguridad y tests (tarda minutos)."
if [ "$sin_gate" -eq 1 ]; then
    echo "  ➖ Omitido por --sin-gate: corre 'bash bin/gate.sh' cuando quieras el verde."
else
    bash bin/gate.sh || falla "el gate quedó rojo." \
        "corrige lo que marque el gate (docs/MONTAR.md) y re-ejecuta bin/setup-wizard.sh."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Montaje completo: clon listo para trabajar"
echo "  Flujo: ./bin/bump-and-pr.sh \"tipo: descripcion\" [--worktree]"
echo ""
echo "  Este wizard NO hizo (fuera de alcance):"
echo "  - cron: instala los jobs con bin/install-cron.sh"
echo "  - secretos: solo comprobó GITHUB_TOKEN, no creó ni rotó ninguno"
echo "  - targets.local: cada operador lo define en su máquina"
echo ""
echo "  Montaje y fallos del gate: docs/MONTAR.md"
echo "  Qué llega, cuándo y a dónde: docs/USUARIO.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
