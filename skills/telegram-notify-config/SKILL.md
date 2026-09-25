---
name: telegram-notify-config
description: "Configure Telegram delivery for CI/repo notifications — resolve a PRIVATE channel's numeric chat_id (-100...) from its invite link (+...), set GitHub Actions secrets, and verify the bot can post. Covers the 'uv sync --locked' lockfile desync that breaks CI after a version bump."
tags: [telegram, ci, notifications, github-actions, secrets, devops]
---

# Telegram Notify Config

Use when a user wants repo/CI notifications (GitHub Actions `notify` job, or any bot-driven alert) sent to a Telegram **channel** instead of a DM, or when you must obtain a channel's numeric `chat_id`.

## When to Use
- "send CI notifications to my channel"
- "configure Telegram alerts for this repo"
- Need a channel `chat_id` but only have an invite link like `t.me/+bZ3N4xSQqEIzNzZh`
- CI notify silently fails or posts to the wrong chat

## Key Fact
A Telegram **invite link** (`t.me/+XXXX`) is NOT addressable by the Bot API. `sendMessage`/`getChat` reject it with `400 chat not found`. You must resolve the channel to its numeric id: **`-100…`** (negative, 13 digits). Two ways:
1. **Channel has a public `@username`** → `getChat?chat_id=@username` returns the `-100...` instantly. Easiest. Ask the user to set a public username.
2. **Private invite-only channel** → the bot (must be admin) must *see* an update from the channel. Post any message in the channel, then `getUpdates` shows `"chat":{"id":-100...}`.

> **Ids de este despliegue:** los `chat_id` reales viven en `cron/targets.local.json` (no versionado) bajo
> las claves `reports` (`hermes_alertas`) y `notify` (`ci_notify`). Este archivo se versiona en
> `pelukron/hermes-scripts/skills/telegram-notify-config/` y sólo lleva placeholders (ADR 0003, punto 4:
> ids, tokens y destinos no se versionan en el repo público).

## Canal único de avisos de repos (convención desde 2026-09-17)

Todos los repos activos de `pelukron` avisan al mismo canal: **`${notify}`** (`ci_notify 🤖`, tipo
`channel`, el bot ya es miembro). Ahí también se movieron los avisos de infra del cron de Hermes que vivían en
`hermes_alertas 📟` y en el DM (backups, uso, drift, RAM, sistema-alertas); los canales de contenido
(`aletheia_feed 🧧`, `rayados_info`, `tigres_info`) y los avisos personales del DM no se tocan. Un solo destino ⇒
el formato tiene que decir **de qué repo** es el aviso.

- **Etiqueta de repo en la primera línea**, desde el mapa `repo_labels` del dato de plantillas (fallback: nombre del
  repo): `✅ hermes-empleo · PR #161 listo para review · higiene en verde`.
- **Layout** (4 líneas, elegido 2026-09-17): `estado + etiqueta + asunto` · **separador** (`multiply sign x20`, vive en
  el dato como clave `separator`) · título humano · enlaces (`run:` / release url). En el aviso de fallo se añaden los
  `checks` (`code=… pr-link=…`) porque es cuando se usan para triage; en el de éxito no.
- **El texto vive en dato + renderer testeable, no en el YAML**: `config/notify-messages.json` +
  `bin/notify-render.py --ci` (hermes-empleo) o `src/notify_render.py --ci/--release` (hermes-scripts), con goldens
  en `tests/`.
- **Sin `parse_mode`, siempre (decidido en #281, ADR 0006)**: texto plano. Un título con `<`, `&`, comillas,
  `_` o `*` no puede romper el aviso ni perderlo justo cuando importa. Los enlaces van desnudos (no clicables):
  se acepta a cambio de que ningún título rompa la entrega. Nada de `parse_mode=HTML`, Markdown ni MarkdownV2
  en avisos de CI, ni siquiera con `escape()`: el camino con formato murió en #278/#279 sin que ningún gate se
  pusiera rojo.
- **Alcance: solo avisos de CI.** Los reportes de cron (`no_agent`) tienen su propio dialecto (Markdown vía
  `format_message`, ADR 0005) y quedan fuera de este contrato.
- **Renderer único de referencia**: `src/notify_render.py --ci/--release` con dato `config/notify-messages.json`
  (claves `ci_pr_ok`, `ci_pr_fail`, `ci_main_ok`, `ci_main_fail`, `release`) y goldens en `tests/`. Los hermanos
  convergen a este contrato en sus propios tickets.
- **Aviso de release**: solo si el repo no corta release en cada merge (hermes-empleo publica en cada push a `main`
  ⇒ avisar sería ruido).

## Resolution Recipe (private channel)
```bash
# 1. Have the user post a message in the channel (bot is admin → receives update)
# 2. Poll updates:
TOKEN="<BOT_TOKEN>"
curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);[print(r['message']['chat']['id'],r['message']['chat'].get('title')) for r in d.get('result',[]) if r.get('message',{}).get('chat',{}).get('id')]"
# => prints -100… (clave `reports` de cron/targets.local.json en este despliegue)
```
- If `getUpdates` is empty: the bot hasn't seen the post (wrong bot / not admin / update already consumed by another process). Re-post and poll immediately.
- Prefer a public `@username` to avoid this fragility.

## Configure GitHub Actions notify
Convention that worked for `pelukron/financial-advisor`:
- Secrets: `TELEGRAM_BOT_TOKEN` (bot that is channel admin) + `TELEGRAM_CHANNEL_ID` (the `-100...`).
- Keep DM secret `TELEGRAM_CHAT_ID` separate; do NOT overwrite it. Use a distinct `TELEGRAM_CHANNEL_ID` so the two destinations stay independent.
- `ci.yml` notify job:
  ```yaml
  notify:
    needs: [backend, frontend, changelog]
    if: always()
    steps:
      - name: Notificar Telegram
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHANNEL_ID: ${{ secrets.TELEGRAM_CHANNEL_ID }}
        run: |
          curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHANNEL_ID}" -d "text=${EMOJI} ${TEXT}" -d "parse_mode=HTML"
  ```
- Prefix the message text (e.g. `[Hermes·financial-advisor]`) so the destination/channel is identifiable.

## Set the secret
```bash
# gh CLI (may 503 transiently — retry):
echo "<CHAT_ID>" | gh secret set TELEGRAM_CHANNEL_ID -R owner/repo
# verify (names only, never values):
gh secret list -R owner/repo | grep -i telegram
```
If `gh secret set` hits HTTP 503, retry with a short sleep loop. UI fallback: repo Settings → Secrets → Actions → New repository secret.

## Verify delivery (do this BEFORE merging the CI change)
```bash
TOKEN="<BOT_TOKEN>"
curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=<CHAT_ID>" -d "text=[Hermes·financial-advisor] test de configuración"
# => {"ok":true,...}  and the message appears in the channel
```

## Pitfalls
- **Secretos faltantes = job rojo, no aviso perdido.** Si el repo no tiene `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`,
  `bin/notify-telegram.sh` sale `exit 2` con `ERROR: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en el entorno` y el
  job queda **rojo en cada run**: la señal existe pero nadie la lee (medido en `pelukron/hermes-scripts`, donde
  además mantenía rojo el CI de un PR abierto). Verifica con `gh secret list -R <owner>/<repo>` (nombres, nunca
  valores) y pon los dos con `gh secret set` (el token por stdin, jamás en argv: queda en el historial y en `ps`).
- **Invite link ≠ chat_id.** Never put `t.me/+...` as the `chat_id` value. Resolve to `-100...` first.
- **Bot must be admin** of the channel to send (and to read updates for private channels).
- **`getUpdates` only shows unread updates** — if another process already consumed them, they're gone. Post fresh, poll fast.
- **uv.lock desync**: if the CI job runs `uv sync --locked` and `pyproject.toml` version was bumped (e.g. by a bump-and-pr script) without regenerating the lock, CI fails `The lockfile at uv.lock needs to be updated, but --locked was provided.` Fix: `cd <dir-with-pyproject> && uv lock` and commit the updated `uv.lock` in the same change. See `references/uv-lock-desync.md`.

## SECURITY
- Bot tokens are secrets. The agent must NOT persist the token in memory or files. Use it inline for resolution only, then discard. If the model tier is "free/gratuito", do not read stored secrets without explicit user consent each time (SECURITY-gate).
- Prefer `gh secret set` so the value never touches the conversation log durably.

## References
- `references/uv-lock-desync.md` — transcript + fix for the uv.lock / uv sync --locked CI failure after a version bump.
