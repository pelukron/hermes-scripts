#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Import hermes_common
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from hermes_common import get_headers, retry_request, smart_truncate

# ------------------------------- CONFIGURACIÓN -------------------------------
UMBRAL_ALERTA_PORCENTAJE = 5.0  # Alerta si baja más del 5% del precio mínimo histórico
UMBRAL_BAJADA_REPENTINA = 15.0  # Alerta si baja más del 15% respecto al último precio visto
COSTO_ENVIO_CYBERPUERTA = 133.00

HISTORICO_PATH = os.path.expanduser("~/.hermes/ram-mexico-history.json")

AMAZON_HEADERS = get_headers("amazon")
CYBER_HEADERS = get_headers("cyberpuerta")

PRODUCTOS = [
    {
        "id": "amazon_fury_16gb",
        "tienda": "Amazon México",
        "name": "Kingston Fury Impact 16 GB 3200 MHz SODIMM",
        "type": "individual",
        "url": "https://www.amazon.com.mx/dp/B097QLN123",
        "sku": "B097QLN123",
        "shipping": 0.0,
    },
    {
        "id": "amazon_fury_2x16_kit",
        "tienda": "Amazon México",
        "name": "Kingston Fury Impact 32 GB Kit (2×16 GB) 3200 MHz SODIMM",
        "type": "combo",
        "url": "https://www.amazon.com.mx/dp/B097QJ25NY",
        "sku": "B097QJ25NY",
        "shipping": 0.0,
    },
    {
        "id": "cyberpuerta_fury_16gb",
        "tienda": "Cyberpuerta",
        "name": "Kingston Fury Impact 16 GB 3200 MHz SODIMM",
        "type": "individual",
        "url": "https://www.cyberpuerta.mx/Computo-Hardware/Memorias-RAM-y-Flash/Memorias-RAM-para-Laptop/Memoria-RAM-para-Laptop-Kingston-FURY-Impact-DDR4-3200MHz-16GB-Non-ECC-CL20-260-pin-SO-DIMM-XMP.html",
        "sku": "KF432S20IB/16",
        "shipping": COSTO_ENVIO_CYBERPUERTA,
    },
    {
        "id": "cyberpuerta_fury_2x16_kit",
        "tienda": "Cyberpuerta",
        "name": "Kingston Fury Impact 32 GB Kit (2×16 GB) 3200 MHz SODIMM",
        "type": "combo",
        "url": "https://www.cyberpuerta.mx/Computo-Hardware/Memorias-RAM-y-Flash/Memorias-RAM-para-Laptop/Kit-Memoria-RAM-Kingston-FURY-Impact-DDR4-3200MHz-32GB-2-x-16GB-CL20-SO-DIMM-XMP.html",
        "sku": "KF432S20IBK2/32",
        "shipping": COSTO_ENVIO_CYBERPUERTA,
    },
]

# ---------------------------------------------------------------------------


def cargar_historial() -> Dict[str, Any]:
    """Carga histórico de precios desde JSON con migración de formato.

    Si el archivo no existe o está corrupto, retorna dict vacío.
    Convierte formato viejo (float) a nuevo (dict con min/last/ultimo_alerta).

    Returns:
        Dict[str, Any]: Diccionario producto_id -> {min, last, ultimo_alerta}.

    """
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                data = json.load(f)
                # Migración: formato viejo (float) → nuevo (dict con min/last/ultimo_alerta)
                migrado = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        # Ya está en formato nuevo
                        if "ultimo_alerta" not in v:
                            v["ultimo_alerta"] = 0
                        migrado[k] = v
                    else:
                        # Formato viejo: float → migrar
                        migrado[k] = {"min": float(v), "last": float(v), "ultimo_alerta": 0}
                return migrado
        except Exception:
            return {}
    return {}


def guardar_historial(historial: Dict[str, Any]):
    """Guarda histórico de precios a JSON, limpiando entradas obsoletas.

    Elimina productos sin update en más de 7 días.

    Args:
        historial (Dict[str, Any]): Diccionario a persistir.

    """
    os.makedirs(os.path.dirname(HISTORICO_PATH), exist_ok=True)
    # Limpiar stats vacíos o muy antiguos (>7 días sin update)
    ahora = time.time()
    limpio = {}
    for k, v in historial.items():
        if isinstance(v, dict) and v.get("last"):
            if ahora - v.get("last", 0) < 7 * 86400:  # Keep only if updated in last 7 days
                limpio[k] = v
    with open(HISTORICO_PATH, "w") as f:
        json.dump(limpio, f, indent=2)


def limpiar_precio(texto: str) -> Optional[float]:
    """Extrae valor numérico de string de precio.

    Args:
        texto (str): String con formato de precio (ej. \"$2,549.00\").

    Returns:
        Optional[float]: Precio como float, o None si no se puede parsear.

    """
    if not texto:
        return None
    nums = re.findall(r"[\d,]+\.?\d*", texto.replace(",", ""))
    try:
        return float(nums[0]) if nums else None
    except Exception:
        return None


def extraer_precio_amazon(html: str) -> Optional[float]:
    """Extrae precio de HTML de página de producto Amazon.

    Prueba 3 estrategias en orden: a-price > displayPrice JSON > cualquier a-offscreen.
    Descarta precios <= 1000 (falsos positivos).

    Args:
        html (str): HTML completo de la página de producto.

    Returns:
        Optional[float]: Precio detectado, o None.

    """
    m = re.search(
        r'<span class="a-price[^"]*"[^>]*>\s*<span class="a-offscreen">\$([\d,]+\.\d{2})</span>',
        html,
    )
    if m:
        p = limpiar_precio(m.group(1))
        if p and p > 1000:
            return p

    # Estrategia 2: JSON displayPrice
    matches = re.findall(r'"displayPrice":"\$([\d,]+\.\d{2})"', html)
    for p_str in matches:
        p = limpiar_precio(p_str)
        if p and p > 1000:
            return p

    # Estrategia 3: Cualquier a-offscreen con formato de precio
    matches = re.findall(r'<span class="a-offscreen">\$([\d,]+\.\d{2})</span>', html)
    precios = [limpiar_precio(p) for p in matches if limpiar_precio(p)]
    validos = [p for p in precios if p and p > 1000]
    if validos:
        return min(validos)

    return None


def precio_cyberpuerta(url: str) -> Optional[float]:
    """Obtiene precio de producto en Cyberpuerta vía scraping HTML.

    Args:
        url (str): URL del producto en Cyberpuerta.

    Returns:
        Optional[float]: Precio detectado, o None si falla.

    """
    try:
        r = retry_request(url, timeout=15)
        m = re.search(r"<h2[^>]*>.*?\$([\d,]+\\.\d{2}).*?</h2>", r.text, re.S)
        if m:
            return limpiar_precio(m.group(1))
        return None
    except Exception:
        return None


def precio_amazon(producto: Dict[str, Any]) -> Optional[float]:
    """Obtiene precio de producto en Amazon México vía scraping HTML.

    Args:
        producto (Dict[str, Any]): Diccionario con clave 'url'.

    Returns:
        Optional[float]: Precio detectado, o None si falla/timeout.

    """
    try:
        r = retry_request(
            producto["url"],
            timeout=5,
        )
        if r.status_code == 200:
            return extraer_precio_amazon(r.text)
        return None
    except (requests.Timeout, requests.ConnectionError):
        return None
    except Exception:
        return None


def obtener_precio(producto: Dict[str, Any]) -> Optional[float]:
    """Despacha a scraper correcto según tienda del producto.

    Args:
        producto (Dict[str, Any]): Diccionario con claves 'tienda' y 'url'.

    Returns:
        Optional[float]: Precio detectado, o None.

    """
    if producto["tienda"] == "Amazon México":
        return precio_amazon(producto)
    if producto["tienda"] == "Cyberpuerta":
        return precio_cyberpuerta(producto["url"])
    return None


def calcular_comparativa(resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula mejor opción para 32 GB comparando combos vs 2 individuales.

    Args:
        resultados (List[Dict[str, Any]]): Lista de productos con precios.

    Returns:
        Dict con claves: recomendado, precio_final_recomendacion,
        recomendacion_texto, mejor_combo, costo_dos_individuales, ahorro.

    """
    for r in resultados:
        if r["precio"] is not None:
            if r["type"] == "individual":
                r["costo_32gb"] = (r["precio"] * 2) + r["shipping"]
            else:
                r["costo_32gb"] = r["precio"] + r["shipping"]
            r["precio_final"] = r["precio"] + r["shipping"]
        else:
            r["costo_32gb"] = None
            r["precio_final"] = None

    opciones = [r for r in resultados if r["costo_32gb"] is not None]
    if not opciones:
        return {
            "recomendado": None,
            "precio_final_recomendacion": 0,
            "recomendacion_texto": "No disponible",
            "mejor_combo": None,
            "costo_dos_individuales": None,
        }

    recomendado = min(opciones, key=lambda x: x["costo_32gb"])

    indivs = [r for r in opciones if r["type"] == "individual"]
    mejor_indiv = min(indivs, key=lambda x: x["costo_32gb"]) if indivs else None
    costo_2_indivs = mejor_indiv["costo_32gb"] if mejor_indiv else None

    combos = [r for r in opciones if r["type"] == "combo"]
    mejor_combo = min(combos, key=lambda x: x["costo_32gb"]) if combos else None

    if recomendado["type"] == "combo":
        name_trunc = smart_truncate(recomendado["name"], 25)
        texto_rec = f"{name_trunc} ({recomendado['tienda']})"
        ahorro = (costo_2_indivs - recomendado["costo_32gb"]) if costo_2_indivs else 0.0
    else:
        name_trunc = smart_truncate(recomendado["name"], 25)
        texto_rec = f"2 × {name_trunc} ({recomendado['tienda']})"
        ahorro = 0.0

    return {
        "recomendado": recomendado,
        "precio_final_recomendacion": recomendado["costo_32gb"],
        "recomendacion_texto": texto_rec,
        "mejor_combo": mejor_combo,
        "costo_dos_individuales": costo_2_indivs,
        "ahorro": ahorro,
    }


def main():
    """Punto de entrada: monitorea precios RAM, detecta ofertas y genera reporte.

    Solo imprime salida si: hay alerta de oferta, hora de resumen (9 AM), o --force.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Forzar salida del reporte")
    args = parser.parse_args()

    ahora_dt = datetime.now()
    ahora_str = ahora_dt.strftime("%Y-%m-%d %H:%M")

    # Resumen diario (ej. 9 AM)
    es_hora_resumen = ahora_dt.hour == 9 and ahora_dt.minute < 35

    historial = cargar_historial()
    resultados = []
    hay_oferta_nueva = False
    detalles_alerta = []

    for prod in PRODUCTOS:
        precio_actual = obtener_precio(prod)
        if precio_actual:
            prod_id = prod["id"]
            stats = historial.get(prod_id, {})

            # Migración/Inicialización: si stats es float (formato viejo)
            if isinstance(stats, (int, float)):
                stats = {"min": float(stats), "last": float(stats), "ultimo_alerta": 0}

            precio_min_previo = stats.get("min")
            precio_last_previo = stats.get("last")
            ahora = time.time()

            # 1. Alerta por mínimo histórico (5%)
            if precio_min_previo and precio_actual < (
                precio_min_previo * (1 - UMBRAL_ALERTA_PORCENTAJE / 100)
            ):
                tiempo_desde_alerta = ahora - stats.get("ultimo_alerta", 0)
                # Solo alertar si pasaron >2h (7200s) desde última alerta
                if tiempo_desde_alerta > 7200:
                    hay_oferta_nueva = True
                    ahorro_vs_hist = precio_min_previo - precio_actual
                    detalles_alerta.append(
                        f"🔥 **NUEVO MÍNIMO HISTÓRICO** en {prod['tienda']}\\n"
                        f"📦 {prod['name']}\\n"
                        "💰 Precio: **${:,.2f}** (Bajó ${:,.2f} del mínimo)".format(
                            precio_actual, ahorro_vs_hist
                        )
                    )
                    stats["ultimo_alerta"] = ahora

            # 2. Alerta por bajada repentina (>15% vs último precio)
            if precio_last_previo and precio_actual < (
                precio_last_previo * (1 - UMBRAL_BAJADA_REPENTINA / 100)
            ):
                tiempo_desde_alerta = ahora - stats.get("ultimo_alerta", 0)
                # Solo alertar si pasaron >2h desde última alerta
                if tiempo_desde_alerta > 7200:
                    hay_oferta_nueva = True
                    ahorro_vs_last = precio_last_previo - precio_actual
                    porcentaje_caida = (ahorro_vs_last / precio_last_previo) * 100
                    detalles_alerta.append(
                        f"⚡ **BAJADA REPENTINA ({porcentaje_caida:.1f}%)** en {prod['tienda']}\n"
                        f"📦 {prod['name']}\n"
                        f"💰 Precio: **${precio_actual:,.2f}** (Antes: ${precio_last_previo:,.2f})"
                    )
                    stats["ultimo_alerta"] = ahora

            # Actualizar historial
            if not precio_min_previo or precio_actual < precio_min_previo:
                stats["min"] = precio_actual

            stats["last"] = precio_actual
            historial[prod_id] = stats

        resultados.append({**prod, "precio": precio_actual})
        time.sleep(1)

    guardar_historial(historial)
    comp = calcular_comparativa(resultados)

    if not (hay_oferta_nueva or es_hora_resumen or args.force):
        return

    if hay_oferta_nueva:
        print("🚨 **¡ALERTA DE OFERTA RELÁMPAGO!** 🚨")
        for detalle in detalles_alerta:
            print(detalle)
        print("\n" + "─" * 20 + "\n")

    if not comp["recomendado"]:
        if args.force or es_hora_resumen:
            print(f"🛒 RAM Monitor - {ahora_str}\nStatus: Sin stock/precios detectados.")
        return

    # Output report
    print(f"🛒 RAM Monitor - {ahora_str}")
    print(
        "💰 Mejor: **{}** - **${:,.2f}**".format(
            comp["recomendacion_texto"], comp["precio_final_recomendacion"]
        )
    )

    print("\n| Tienda | Producto | Unit | Total |")
    print("|---|---|---:|---:|")

    tienda_map = {"Amazon México": "Amazon", "Cyberpuerta": "Cyber"}

    for r in resultados:
        tienda = tienda_map.get(r["tienda"], r["tienda"])
        nombre_simple = smart_truncate(r["name"], 30)
        unit = f"${r['precio_final']:,.0f}" if r["precio_final"] else "N/A"
        total = f"${r['costo_32gb']:,.0f}" if r["costo_32gb"] else "N/A"
        marker = "✅ " if r["costo_32gb"] == comp["precio_final_recomendacion"] else "  "
        print(f"| {marker}{tienda:<6} | {nombre_simple} | {unit:>6} | {total:>6} |")

    print("\n🔗 **Comprar (haz clic en la tienda):**")
    for r in resultados:
        if r["precio"]:
            nombre_corto = smart_truncate(r["name"], 15)
            tienda = tienda_map.get(r["tienda"], r["tienda"])
            print(f"- [🛒 {tienda} - {nombre_corto} (${r['precio']:,.0f})]({r['url']})")


if __name__ == "__main__":
    main()
