#!/bin/bash
# Alerta inmediata + resumen diario de sistema para Hermes
# - Si hay alerta (>80% disco, memoria o CPU): envía notificación inmediata.
# - Si no hay alerta y son las 8:00-8:05 AM: envía resumen diario.
# - En cualquier otro caso: silencioso.

UMBRAL_DISCO=${UMBRAL_DISCO:-80}
UMBRAL_MEMORIA=${UMBRAL_MEMORIA:-80}
UMBRAL_CPU=${UMBRAL_CPU:-80}

# Cooldown del aviso de alerta (#349): sin él, un umbral cruzado hablaba cada 30 min.
# FORCE_ALERT=1 lo salta, para que el remedio del propio mensaje siga sirviendo a mano.
COOLDOWN_MIN=${COOLDOWN_MIN:-360}
STATE_DIR=${HERMES_HOME:-$HOME/.hermes}
SELLO_AVISO="$STATE_DIR/sistema-alertas-last-aviso"

# ¿Toca avisar? Sin sello (nunca avisó) o con el cooldown vencido: sí.
toca_avisar() {
    [ -f "$SELLO_AVISO" ] || return 0
    local ultimo ahora
    ultimo=$(cat "$SELLO_AVISO" 2>/dev/null)
    case "$ultimo" in
        ''|*[!0-9]*) return 0 ;;   # sello ilegible: se trata como si no existiera
    esac
    ahora=$(date +%s)
    [ $((ahora - ultimo)) -ge $((COOLDOWN_MIN * 60)) ]
}

marcar_aviso() {
    mkdir -p "$STATE_DIR" 2>/dev/null
    date +%s > "$SELLO_AVISO" 2>/dev/null || true
}

# Métricas
USO_DISCO=$(df / | awk 'NR==2 {gsub(/%/,""); print $5}')
USO_MEMORIA=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
CARGA_1M=$(cut -d' ' -f1 /proc/loadavg)
CARGA_5M=$(cut -d' ' -f2 /proc/loadavg)
CARGA_15M=$(cut -d' ' -f3 /proc/loadavg)
NUM_CPUS=$(nproc)
CARGA_PCT=$(awk "BEGIN {printf \"%.0f\", ($CARGA_1M / $NUM_CPUS) * 100}")
UPTIME=$(uptime -p)
MEM_TOTAL=$(free -h | awk 'NR==2{print $2}')
MEM_USED=$(free -h | awk 'NR==2{print $3}')
DISCO_TOTAL=$(df -h / | awk 'NR==2{print $2}')
DISCO_USED=$(df -h / | awk 'NR==2{print $3}')
DISCO_PCT=$(df -h / | awk 'NR==2{print $5}')
USUARIOS=$(who | wc -l)
HORA=$(date '+%Y-%m-%d %H:%M %Z')
HORA_HORA=${HORA_HORA:-$(date '+%H:%M')}

ALERTAS=""

if [ "$USO_DISCO" -ge "$UMBRAL_DISCO" ]; then
    ALERTAS="${ALERTAS}• 💽 **Disco**: $USO_DISCO% usado (umbral $UMBRAL_DISCO%)"$'\n'
fi

if [ "$USO_MEMORIA" -ge "$UMBRAL_MEMORIA" ]; then
    ALERTAS="${ALERTAS}• 💾 **Memoria**: $USO_MEMORIA% usada (umbral $UMBRAL_MEMORIA%)"$'\n'
fi

if [ "$CARGA_PCT" -ge "$UMBRAL_CPU" ]; then
    ALERTAS="${ALERTAS}• 🧠 **Carga CPU**: $CARGA_PCT% (umbral $UMBRAL_CPU%, $NUM_CPUS CPUs)"$'\n'
fi

# Aviso inmediato si hay problemas (respetando el cooldown) o si se fuerza con FORCE_ALERT=1
if [ -n "$ALERTAS" ] || [ "$FORCE_ALERT" = "1" ]; then
    # Cooldown vencido: no se avisa, y tampoco se finge "todo normal" (silencio y rc 0).
    if [ "$FORCE_ALERT" != "1" ] && ! toca_avisar; then
        exit 0
    fi
    echo "⚠️ **sistema-alertas** — $(hostname) · $HORA"
    if [ -n "$ALERTAS" ]; then
        printf '%s' "$ALERTAS"
    else
        echo "• ✅ No hay alertas reales. Este es un mensaje de prueba forzado."
    fi
    echo "remedio: FORCE_ALERT=1 bash bin/sistema-alertas-y-resumen.sh · hermes cron list"
    marcar_aviso
    exit 0
fi

# Resumen diario solo entre las 8:00 y 8:05 AM o si se fuerza con FORCE_RESUMEN=1
if [[ "$HORA_HORA" =~ ^08:0[0-5]$ ]] || [ "$FORCE_RESUMEN" = "1" ]; then
    echo "🖥️ **sistema-alertas · resumen diario** — $(hostname) · $HORA"
    echo ""
    echo "⏱️ **Uptime**"
    echo "• Valor: $UPTIME"
    echo "• Estado: ✅ normal"
    echo ""
    echo "🧠 **Carga CPU**"
    echo "• Valor: 1m: $CARGA_1M / 5m: $CARGA_5M / 15m: $CARGA_15M"
    echo "• Estado: ✅ normal"
    echo ""
    echo "💾 **Memoria**"
    echo "• Valor: $MEM_USED / $MEM_TOTAL ($USO_MEMORIA%)"
    echo "• Estado: ✅ normal"
    echo ""
    echo "💽 **Disco (/)**"
    echo "• Valor: $DISCO_USED / $DISCO_TOTAL ($DISCO_PCT)"
    echo "• Estado: ✅ normal"
    echo ""
    echo "👤 **Usuarios activos**"
    echo "• Valor: $USUARIOS"
    echo "• Estado: ✅ normal"
    echo ""
    echo "Todas las métricas se encuentran dentro de rangos normales."
fi
