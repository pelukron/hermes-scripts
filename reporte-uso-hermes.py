#!/usr/bin/env python3
"""
Reporte de uso de Hermes con tablas, porcentajes y gráficas ASCII.
Sin imágenes. Enviado como texto plano al canal de alertas.
"""

import os
import sqlite3
import sys
from datetime import datetime

HERMES_HOME = os.path.expanduser("~/.hermes")
DB_PATH = os.path.join(HERMES_HOME, "state.db")


def fetch_daily_stats(days=7):
    """Fetch daily session statistics for the last N days.

    Args:
        days: Number of days to look back. Defaults to 7.

    Returns:
        list[tuple]: Rows of (date, session_count, input_tokens,
            output_tokens, total_tokens).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT date(started_at, 'unixepoch') as dia,
               COUNT(*) as sesiones,
               COALESCE(SUM(input_tokens), 0) as input_tokens,
               COALESCE(SUM(output_tokens), 0) as output_tokens,
               COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
        FROM sessions
        WHERE started_at >= strftime('%s', 'now', '-{days} days')
        GROUP BY dia
        ORDER BY dia
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_model_stats(days=7):
    """Fetch session statistics grouped by model for the last N days.

    Args:
        days: Number of days to look back. Defaults to 7.

    Returns:
        list[tuple]: Rows of (model, session_count, input_tokens,
            output_tokens, total_tokens), sorted by total_tokens descending.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT model,
               COUNT(*) as sesiones,
               COALESCE(SUM(input_tokens), 0) as input_tokens,
               COALESCE(SUM(output_tokens), 0) as output_tokens,
               COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
        FROM sessions
        WHERE started_at >= strftime('%s', 'now', '-{days} days')
        GROUP BY model
        ORDER BY total_tokens DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_total_stats(days=7):
    """Fetch aggregate session statistics for the last N days.

    Args:
        days: Number of days to look back. Defaults to 7.

    Returns:
        tuple: (total_sessions, total_input_tokens, total_output_tokens,
            total_tokens).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT COUNT(*),
               COALESCE(SUM(input_tokens), 0),
               COALESCE(SUM(output_tokens), 0),
               COALESCE(SUM(input_tokens + output_tokens), 0)
        FROM sessions
        WHERE started_at >= strftime('%s', 'now', '-{days} days')
        """
    )
    row = cursor.fetchone()
    conn.close()
    return row


def fmt(n):
    """Format a number as human-readable string (k/M).

    Args:
        n: Integer to format.

    Returns:
        str: Formatted string, e.g. "1.5k", "3.2M", or "42".
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.2f}k"
    return str(n)


def pct(part, total):
    """Calculate percentage string.

    Args:
        part: Numerator.
        total: Denominator.

    Returns:
        str: Percentage formatted as "X.X%". Returns "0.0%" if total is 0.
    """
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def bar(value, max_value, width=20):
    """Generate an ASCII bar chart string.

    Args:
        value: Current value to represent.
        max_value: Maximum value for scaling.
        width: Bar width in characters. Defaults to 20.

    Returns:
        str: ASCII bar made of █ (filled) and ░ (empty) characters.
    """
    if max_value == 0:
        return "░" * width
    filled = int(value / max_value * width)
    return "█" * filled + "░" * (width - filled)


def main():
    """Generate and print the weekly Hermes usage report.

    Queries the sessions database for the last 7 days and outputs
    a Markdown-formatted report with summary table, per-model breakdown,
    and ASCII charts for tokens and sessions per day.
    """
    if not os.path.exists(DB_PATH):
        print("No se encontró state.db.")
        sys.exit(1)

    rows = fetch_daily_stats(days=7)
    models = fetch_model_stats(days=7)
    total = fetch_total_stats(days=7)

    if not rows:
        print("Aún no hay suficientes datos históricos.")
        sys.exit(0)

    total_sessions = total[0]
    total_input = total[1]
    total_output = total[2]
    total_tokens = total[3]

    output = []
    output.append("📊 **Reporte de uso de Hermes**")
    output.append("")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    output.append(f"_Período: últimos 7 días · Generado el {fecha} México_")
    output.append("")

    # Tabla resumen
    output.append("**📈 Resumen general**")
    output.append("")
    output.append("| Métrica | Valor | % del total |")
    output.append("|---|---:|---:|")
    output.append(f"| 🧠 Sesiones | **{total_sessions}** | 100% |")
    output.append(f"| ⬇️ Input tokens | **{fmt(total_input)}** | {pct(total_input, total_tokens)} |")
    output.append(
        f"| ⬆️ Output tokens | **{fmt(total_output)}** | {pct(total_output, total_tokens)} |"
    )
    output.append(f"| 🔢 Total tokens | **{fmt(total_tokens)}** | 100% |")
    output.append("")

    # Desglose por modelo
    output.append("**🤖 Desglose por modelo**")
    output.append("")
    output.append("| Modelo | Ses. | Tokens | % |")
    output.append("|---|---:|---:|---:|")

    # Extraer el modelo actual para destacarlo
    active_model = os.environ.get("HERMES_MODEL") or "gemini-3-flash-preview"

    for model, sesiones, inp, out, tot in models:
        model_str = str(model) if model else "desc"
        # Truncar si el nombre del modelo es muy largo
        model_disp = (model_str[:17] + "...") if len(model_str) > 20 else model_str
        model_name = f"**{model_disp}** 🪨" if model_str in active_model else f"`{model_disp}`"
        output.append(f"| {model_name} | {sesiones} | {fmt(tot)} | {pct(tot, total_tokens)} |")
    output.append("")

    # Gráfica ASCII de tokens por día
    output.append("**📉 Tokens por día**")
    output.append("```")
    max_tokens = max(r[4] for r in rows) if rows else 1
    for dia, sesiones_count, inp, out, tot in rows:
        output.append(f"{dia} │ {bar(tot, max_tokens, width=24)} {fmt(tot):>8}")
    output.append("```")
    output.append("")

    # Gráfica ASCII de sesiones por día
    output.append("**📅 Sesiones por día**")
    output.append("```")
    max_sessions = max(r[1] for r in rows) if rows else 1
    for dia, sesiones_count, inp, out, tot in rows:
        output.append(f"{dia} │ {bar(sesiones_count, max_sessions, width=24)} {sesiones_count:>4}")
    output.append("```")
    output.append("")

    output.append("_Actualizado automáticamente cada mañana._")

    print("\n".join(output))


if __name__ == "__main__":
    main()
