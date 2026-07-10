# Plan Tier 1+2: Dataclass + feeds.json

1. Extraer array FEEDS → feeds.json
2. Agregar FeedItem + FeedStats dataclasses
3. load_feeds() desde JSON
4. fetch_rss trackea fallos
5. Footer stats en main()
6. Ejecutar make lint + make test