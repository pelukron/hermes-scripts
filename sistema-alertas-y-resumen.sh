#!/bin/bash
# Alerta inmediata + resumen diario de sistema para Hermes
# - Si hay alerta (>80% disco, memoria o CPU): envía notificación inmediata.
# - Si no hay alerta y son las 8:00-8:05 AM: envía resumen diario.
# - En cualquier otro caso: silencioso.

UMBRAL_DISCO=80
UMBRAL_MEMORIA=80
UMBRAL_CPU=80

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
    ALERTAS="${ALERTAS}• 💽 **Disco**: $USO_DISCO% usado (umbral $UMBRAL_DISCO%)\n"
fi

if [ "$USO_MEMORIA" -ge "$UMBRAL_MEMORIA" ]; then
    ALERTAS="${ALERTAS}• 💾 **Memoria**: $USO_MEMORIA% usada (umbral $UMBRAL_MEMORIA%)\n"
fi

if [ "$CARGA_PCT" -ge "$UMBRAL_CPU" ]; then
    ALERTAS="${ALERTAS}• 🧠 **Carga CPU**: $CARGA_PCT% (umbral $UMBRAL_CPU%, $NUM_CPUS CPUs)\n"
fi

# Enviar alerta inmediata si hay problemas o si se fuerza con FORCE_ALERT=1
if [ -n "$ALERTAS" ] || [ "$FORCE_ALERT" = "1" ]; then
    echo "⚠️ **Alerta de sistema** en \`$(hostname)\`"
    echo ""
    if [ -n "$ALERTAS" ]; then
        echo "$ALERTAS"
    else
        echo "• ✅ No hay alertas reales. Este es un mensaje de prueba forzado."
    fi
    echo ""
    echo "_Hora: ${HORA}_"
    exit 0
fi

# Resumen diario solo entre las 8:00 y 8:05 AM o si se fuerza con FORCE_RESUMEN=1
if [[ "$HORA_HORA" =~ ^08:0[0-5]$ ]] || [ "$FORCE_RESUMEN" = "1" ]; then
    echo "🖥️ **Estado del servidor**"
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
    echo ""
    echo "_Hora: ${HORA}_"
fi
