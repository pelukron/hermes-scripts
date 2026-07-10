# Plan: Tier 1+2 — Escalabilidad script noticias

**Objetivo:** Aplicar patrones de python-error-handling para tracking de fallos + extraer configuración a JSON.

## Cambios

### Tier 1: Dataclass + Partial Failures

Nuevo `FeedItem` dataclass reemplaza tuplas:

```python
@dataclass
class FeedItem:
    title: str
    link: str
```

`fetch_rss()` ahora devuelve `list[FeedItem]`.

Nuevo `FeedStats` trackea fallos:

```python
_stats = {"ok": 0, "fail": 0, "failed_feeds": []}
```

Footer al final del reporte:

```
📊 _Fuentes: 38/42 OK (4 fallos: France 24, RT EN...)_ 
```

### Tier 2: feeds.json externo

```json
{
  "sections": [
    {
      "name": "🌍 GEOPOLÍTICA & GLOBAL",
      "subsections": [
        {
          "name": "Mainstream / Wires",
          "sources": [
            {"name": "Reuters", "url": "https://..."},
            {"name": "AP", "url": "https://..."}
          ]
        }
      ]
    }
  ]
}
```

Script carga con `json.load()` al inicio.

## Archivos modificados

- `resumen-noticias-diario.py` (~40 líneas nuevas)
- `feeds.json` (nuevo, ~200 líneas)

## Validación

```bash
~/.hermes/venv/bin/python resumen-noticias-diario.py
# Verificar footer stats al final
```