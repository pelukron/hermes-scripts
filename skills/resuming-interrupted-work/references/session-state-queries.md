# Consultas para retomar una sesión

Fuente: `website/docs/user-guide/sessions.md` de NousResearch/hermes-agent, leído el 2026-10-02.
No es el `session-state-queries.md` de 265 líneas que vivía en el perfil.

## Reanudar en la terminal

```bash
hermes --continue                      # la última sesión cli; -c es por terminal
hermes -c "titulo"                     # por título; si hay linaje, la más reciente
hermes --resume 20250305_091523_a1b2c3 # por id
hermes --resume latest --in ./repo     # la última de ese directorio
hermes sessions list --limit 50
```

`latest` es palabra reservada de `--resume`. Un título que sea literalmente «latest» se abre por id
o con `-c latest`.

## Buscar desde el agente

`session_search` no llama a un modelo. Devuelve mensajes guardados.

```python
session_search(query="frase del corte", limit=3, sort="newest")
session_search(session_id="20260510_174648_805cc2", around_message_id=590803, window=10)
session_search(session_id="20260510_174648_805cc2")  # la sesión, o cabeza y cola si es larga
session_search()  # las recientes, sin tema
```

FTS5: las palabras se unen con AND. Frase exacta entre comillas. `palabra*` es prefijo.
`role_filter` por defecto es `user,assistant`. Para ver herramientas: `user,assistant,tool`.

Una página corta no es el archivo completo: `hermes sessions list` avisa cuando `--limit` recorta.
