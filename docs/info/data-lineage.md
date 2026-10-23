
#### 3. `docs/data-lineage.md`
```markdown
# docs/data-lineage.md — Linaje de datos de MACRO2
Mapa de origen, flujo, almacenamiento y calidad de los datos de MACRO2.  
Si cambia un source, un endpoint, un schema o una regla de calidad, se actualiza este archivo. Es la fuente de verdad para responder "¿de dónde viene este dato?" o "¿cómo se valida?".

**Estado**: congelado desde T_0 = 2026-10-19 18:00 UTC.

## 1. Fuentes de datos
### 1.1 Crypto (Hyperliquid)
- **Endpoint REST**: `https://api.hyperliquid.xyz/info`
- **Endpoint WS**: `wss://api.hyperliquid.xyz/ws` *(Validado: path exacto correcto)*
- **Endpoints usados**: `candleSnapshot` (velas OHLCV históricas), `meta` (info de activos), `allMids` (mid prices actuales), `predictedFundings` / `fundingHistory` (funding rate).
- **Activos**: BTC, ETH, SOL, XRP, AVAX, HYPE
- **Timeframes**: 5m, 15m, 1h, 4h, 1d (relevantes para `ms_v2`)

### 1.2 TradFi (proxies sintéticos)
- **Fuente**: provider `xyz:` interno
- **Símbolos**: `xyz:SP500`, `xyz:XYZ100`, `xyz:GOLD`, `xyz:SILVER`, `xyz:EUR`, `xyz:CL`
- **Tratamiento**: marcados con `proxy_flag=1` en cada snapshot. Excluidos de `funding_pct`.

## 2. Pipeline (C0 → C4)
- **C0_INICIO_local.py**: valida disco, crea directorios, configura logging.
- **C1_CONFIG_local.py**: carga CONFIG desde variables de entorno (resuelve `PROJECT_ROOT` de forma defensiva).
- **C1_5_PARAM_local.py**: CENTRAL_PARAMS v2.8 — única fuente de verdad de parámetros.
- **C2_BOVEDA_local.py**: Bóveda schema-less v8.5 — crea DB, migraciones aditivas, audit mode.
- **C2_5_CONTEXTO_local.py**: Contexto Derivados v2.3 — LIQ, DOI, OBI, Beta, Sesión.
- **C3_MACRO_local.py**: Cartógrafo v7.9.3 — `macro_score` legacy + `macro_score_v2` paralelo.
- **C3_DATA_QUALITY.py**: Normalización OHLCV, `candle_status`, `data_quality`.
- **C3_5_REGIME_ENGINE.py**: Motor de Régimen v1.5 — TREND_UP/DOWN/RANGE/CHAOS, ADF, rate limit resilient.
- **C4_SENIAL_VALIDATOR.py**: Validador v1.3 — clasificación dual legacy/v2, resolución 4h/8h/24h.

## 3. Almacenamiento
### 3.1 Local
- **Ruta Windows**: `C:\Users\MD\Desktop\VSCODE\MACRO2\data\vault_v2.db`
- **Ruta Docker/Render**: `/app/data/vault_v2.db` (resuelto por `CONFIG.PROJECT_ROOT` con `_resolve_project_root()`)
- **Migraciones**: aditivas, idempotentes. Cada columna nueva se añade con `ALTER TABLE ... ADD COLUMN` y se documenta en el banner de C2.

### 3.2 Replicación a R2
- **Bucket**: `mercabot-qwen-db` *(Corregido: confirmado en logs de despliegue de Render)*
- **Path**: `vault/vault_v2.db`
- **Frecuencia**: continua vía Litestream (replica cada vez que la DB hace commit)
- **Restauración**: `litestream restore -config /etc/litestream.yml /app/data/vault_v2.db`

## 4. Tablas clave (resumen)
| Tabla | Qué guarda | Quién escribe |
|---|---|---|
| `gem_macro_snapshot` | Estado macro por activo en cada ciclo (incluye `macro_score`, `macro_score_v2`, `regime`, `regime_confidence`) | C3 |
| `senales_aprobadas` | Señales que C3 marcó como significativas | C3 |
| `senales_validadas` | Señales + clasificación de calidad legacy + v2 + `data_quality` audit | C4 |
| `macro_audit_log` | Log de auditoría (cambios, errores, calidad) | C2, C3, C4 |
| `logs_errores` | Registro de fallos del pipeline con contexto | C0-C4 |
*(Nota: No existe una tabla `regime_state` independiente; el régimen se almacena dentro de `gem_macro_snapshot`)*

## 5. Reglas de calidad
### 5.1 Enums (valores exactos, NO modificar)
- `candle_status`: `CLOSED`, `FORMING`, `INSUFFICIENT`, `ERROR`
- `data_quality`: `OK`, `DEGRADED`, `STALE`, `ERROR`
- `proxy_flag`: `0` (crypto real) o `1` (TradFi proxy sintético)
- `calidad_senal` (legacy): `ALTA`, `MEDIA`, `BAJA`, `NULA` *(Nota: en la práctica actual solo se observan RUIDO/BAJA en legacy)*
- `calidad_senal_v2`: `FUERTE`, `MODERADA`, `RUIDO`
- `regime`: `TREND_UP`, `TREND_DOWN`, `RANGE`, `CHAOS`, `UNKNOWN`

### 5.2 Reglas de inserción
- **Forming candles**: se permite registrar `candle_status=FORMING` solo con `data_quality=OK` y `age_seconds < 2·interval`. Si no, se descarta.
- **Funding N/A**: se convierte a 0 con `proxy_flag=1` solo si es TradFi. Si es crypto, se omite el ciclo y se loguea.
- **Cierres faltantes**: detección de gaps con tolerancia ±10% del intervalo esperado.

### 5.3 Auditoría
Cada registro lleva: `timestamp_unix`, `cycle_id` (formato `MACRO_YYYYMMDD_HHMM_xxxx`), `data_quality`, `candle_status`, `proxy_flag` cuando aplique.

## 6. Resolución de señales (ventanas)
Cada señal emitida en C4 se resuelve a tres horizontes:
- 4h — `resuelto_4h`, `pnl_pct_4h`
- 8h — `resuelto_8h`, `pnl_pct_8h`
- 24h — `resuelto_24h`, `pnl_pct_24h`
Una señal pasa a `resuelto_Xh=1` cuando se cumple la ventana desde su `timestamp_emision`.

## 7. Queries de referencia (linaje)
```sql
-- Última snapshot por activo
SELECT coin, cycle_id, macro_score, macro_score_v2, regime, data_quality
FROM gem_macro_snapshot
WHERE (coin, cycle_id) IN (
  SELECT coin, MAX(cycle_id) FROM gem_macro_snapshot GROUP BY coin
);

-- Conteo de señales por calidad y horizonte (post-T_0)
SELECT calidad_senal_v2,
       SUM(resuelto_4h)  AS n_4h,
       SUM(resuelto_8h)  AS n_8h,
       SUM(resuelto_24h) AS n_24h
FROM senales_validadas
WHERE timestamp_emision >= 1729360800 -- Unix timestamp de T_0
GROUP BY calidad_senal_v2;