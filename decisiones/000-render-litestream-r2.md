# decisiones/000-render-litestream-r2.md — Stack de producción de MACRO2

**ADR** — Architecture Decision Record. Documenta una decisión técnica de MACRO2 y sus consecuencias. NO se modifica retroactivamente. Si la decisión cambia, se crea un nuevo ADR que apunte a este.

**Estado**: Aceptado, vigente desde el deploy inicial (T_0 = 2026-10-19 18:00 UTC).

## Contexto
MACRO2 (`mercabot_qwen`) requiere ejecución continua, persistencia local, réplica de seguridad, monitorización externa y notificaciones. El proyecto corre en local (Windows) y en producción (Render) en paralelo. Necesitamos:
- Hosting que ejecute el pipeline cada 15 min.
- Persistencia local + backup automático.
- Monitor que avise si el servicio cae.
- Notificaciones diarias al usuario.
- Stack barato (fase de validación OOS).

## Decisión
Stack elegido:
1. **Render Web Service** (Docker, `python:3.12-slim`) — hosting principal.
2. **Cloudflare R2 + Litestream** — backup continuo de la DB.
3. **UptimeRobot** — monitor HTTP en `/health`.
4. **Telegram Bot** — notificaciones 8 AM y 5 PM Caracas.
5. **SQLite local + schema-less** — base de datos embebida.
6. **Ventana operativa 08:00-17:00 Caracas** — solo ejecuta en horario de liquidez alta.

## Consecuencias

### Positivas
- **Coste cero**: Render Free, R2 free tier, UptimeRobot free, Telegram gratis, SQLite sin coste. Apto para fase de validación.
- **Persistencia fiable**: Litestream replica cada commit a R2. Si el servicio se reinicia, la DB no se pierde.
- **Detección rápida de caídas**: UptimeRobot revisa `/health` cada 5 min. Si falla, avisa por email.
- **Visibilidad diaria**: Telegram manda resumen 8 AM y 5 PM sin intervención manual.

### Limitaciones conocidas (aceptadas)
- **Render Free**: Puede dormir tras 15 min de inactividad. El cron interno del bot y UptimeRobot ayudan a mantenerlo activo.
- **SQLite**: No escala a multi-instancia. Solo relevante si en futuro se quisiera paralelizar.
- **Schema-less**: Añade complejidad al schema (auditoría, migraciones aditivas explícitas).
- **Ventana 08:00-17:00**: Deja gaps nocturnos. Intencionado, alineado con la liquidez del mercado.

## Sub-decisiones

### 1. Render Web Service
- **Plan**: Free (suficiente para fase OOS).
- **Runtime**: Docker con `python:3.12-slim`.
- **Trigger**: `python main.py --celdas 4` (configurado vía variable de entorno `PIPELINE_CMD`).
- **Frecuencia interna**: cada 15 min, durante la ventana operativa.
- **Health endpoint**: `/health` → 200 OK si el proceso responde.
- **CI/CD**: push a `main` en GitHub → Render auto-deploy.
- **URL pública**: `https://botmacro.onrender.com`

### 2. Cloudflare R2 + Litestream
- **Bucket**: `mercabot-qwen-db` *(Corregido: confirmado en logs de despliegue de Render)*.
- **Path**: `vault/vault_v2.db`.
- **Frecuencia de réplica**: continua (cada commit de SQLite).
- **Restore manual**: `litestream restore -config /etc/litestream.yml /app/data/vault_v2.db` (solo si se pierde local o en deploy nuevo).
- **Variables de entorno**: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`.

### 3. UptimeRobot
- **Monitor**: HTTP(s) GET a `https://botmacro.onrender.com/health`.
- **Intervalo**: cada 5 min.
- **Alerta**: email al admin.
- **Threshold**: 2 fallos consecutivos → alerta.

### 4. Telegram
- **Bot**: `@mercabot_qwen_notifier` *(Nombre real configurado vía `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env`)*.
- **Reportes diarios**: 8 AM Caracas (resumen pre-mercado) y 5 PM Caracas (resumen post-mercado).
- **Trigger**: al inicio y al cierre de la ventana operativa (manejado por `scheduler.py` v2.0).
- **Contenido**: #señales, %resueltas, desglose LONG/SHORT, validación v2 (OOS), salud del sistema.

### 5. SQLite schema-less
- **Engine**: SQLite 3, embebido.
- **Modo**: schema-less con auditoría. Las tablas no tienen PRIMARY KEY rígido; cada fila lleva `id` autoincrement + columnas de audit.
- **Migraciones**: aditivas, idempotentes. Documentadas en el banner de cada celda (ej. `C2_BOVEDA_local.py` v8.5).
- **Auditoría**: cada registro lleva `timestamp_unix`, `cycle_id`, `data_quality`, `candle_status`, `proxy_flag`.
- **Detalle completo**: `docs/data-lineage.md` §3-5.

### 6. Ventana operativa 08:00-17:00 Caracas
- **Razón**: alinearse con la liquidez del mercado (apertura Europa + sesión US, donde el flujo macro es mayor).
- **Implementación**: cron interno del bot (`scheduler.py`), no del sistema operativo.
- **Gaps nocturnos**: intencionados. Las señales fuera de ventana no se emiten.

## Alternativas consideradas
- **Heroku / Railway / Fly.io**: descartados por coste o por requerir tarjeta en free tier.
- **Postgres externo**: descartado por coste y por requerir migración completa del schema-less.
- **S3 de AWS**: descartado por coste de egress. R2 sin egress fee.
- **Monitor con Sentry / Datadog**: overkill para la fase actual.

## Referencias
- Linaje de datos: `docs/data-lineage.md`
- Spec de la metodología: `docs/spec-ms-v2.md`
- Estado actual del proyecto: `ESTADO.md`