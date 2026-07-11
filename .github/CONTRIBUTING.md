# Contributing

## GitFlow

**main** está protegida. Todos los cambios entran vía Pull Request.

### Ramas

| Prefijo | Uso | Ejemplo |
|---|---|---|
| `feat/` | Nueva funcionalidad | `feat/v0.4.0-nuevo-script` |
| `fix/` | Corrección de bug | `fix/v0.3.2-imports-muertos` |
| `docs/` | Documentación | `docs/v0.3.2-readme` |
| `refactor/` | Refactor sin cambio funcional | `refactor/v0.4.0-centralizar` |
| `ci/` | CI/CD | `ci/v0.3.2-github-actions` |
| `test/` | Tests | `test/v0.3.2-coverage` |

### Flujo

```bash
# 1. Crear rama desde main
git checkout main && git pull
git checkout -b feat/v0.4.0-mi-feature

# 2. Hacer cambios + commit
git add -A
git commit -m "feat: descripción"

# 3. Push y crear PR
git push -u origin feat/v0.4.0-mi-feature
# Crear PR en GitHub

# 4. CI corre automáticamente (ruff + pytest)
# 5. Merge cuando CI pase
```

### Automatizado

```bash
# Alternativa automatizada con bump automático
./bump-and-pr.sh patch "fix: mensaje" "- cambio 1" "- cambio 2"
```

### Reglas

- ❌ No push directo a main
- ✅ PR obligatorio para merge
- ✅ CI debe pasar antes de merge
- ✅ CHANGELOG actualizado en cada PR
- ✅ Conventional commits (`feat:`, `fix:`, `docs:`, etc.)