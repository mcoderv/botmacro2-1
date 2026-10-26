# PENDIENTES — MACRO2.1

> **Este archivo es el tracking oficial.** Si algo está pendiente, va acá.
> `docs/INFORME_MACRO2.1.md` es la **spec de referencia** (no se edita);
> este archivo es el que dice **qué falta y qué se hizo**.
>
> Actualizado: 2026-10-26

---

## ✅ HECHOS (cerrados)

| # | Qué | Dónde |
|---|---|---|
| 1 | Umbral ADF unificado en **0.05**, fuente única `CENTRAL_PARAMS["macro"]` | ADR 002, commit `5361b4f` |
| 2 | `C0`/`C2` usan `backups_v2.1` / `logs_v2.1` | H-3, commit `5361b4f` |
| 3 | `_migrar_v28` **sobrescribe** el `central_params.json` guardado | H-5, commit `5361b4f` |
| 4 | **`scheduler.py` ya lee `PORT`** del entorno | Ya estaba, confirmado en `5e0c481` |
| 5 | Bucket R2 = `mercabot-qwen-db` (no `macrobot-vault`) | Ya estaba |
| 6 | Sin Docker en MACRO2.1 | ADR 003, commit `5e0c481` |
| 7 | `docs/` reordenada, `textos/` eliminada, `docs/local/` fuera de GitHub | commit `5e0c481` |
| 8 | Kit de git (`guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`) | commit `5361b4f` |
| 9 | `verificar.py` con 19 checks, incluidos los 7 ADRs | commit `6a5a37a` |
| 10 | `rescore_umbral.py` v2 (solo reconstruibles, aborta si AV1 < 90%) | `analisis/` |
| 11 | `fixes/` y `analisis/` limpios (parches de una vez → `docs/local/`) | commit `23efea4` |
| 12 | **Pipeline verificado de punta a punta** (`python main.py`, 8 celdas, +7 señales) | 2026-10-23 |
| 13 | **Backup local de la DB** en `Desktop\MACRO2.1_BACKUP\` | 2026-10-23 |
| 14 | **Max DD con capital compuesto** (H-15) + **fuente única del ADF** (H-12) | **ADR 004** |
| 15 | **Ventana operativa configurable** (VENTANA/CONTINUO, cruce de medianoche, días, CLI) | **ADR 006** |
| 16 | Análisis de timing real (914 señales) + MAE/MFE reales + σ por señal | `analisis/analisis_timing_real.py` |
| 17 | **ADR 005 (caja simétrica) PROPUESTO** + ADR 001 con k = 0,044σ medido | `decisiones/` |
| 18 | **H-10 cerrado**: 19/10 = 1er deploy a Render + v7.9.3 ⇒ `ms_v2` real | `analisis/diagnostico_h10_h18.py` |
| 19 | **H-9 CERRADO con evidencia**: el score v2 NO tiene poder predictivo (ρ=+0,119). 5 scripts de análisis | `analisis/{diagnostico_h9,descomponer_score_v2,poder_predictivo_score_v2,reconstruir_score_v2,reconciliar_score_cero}.py` |
| 20 | **Zona horaria resuelta**: la DB guarda **hora local Caracas (UTC−4)** — 3 pares epoch↔fecha | análisis 26/10 |
| 21 | **Segunda opinión** recibida y revisada; sus 3 errores (E1 Caracas/UTC, E2 `cvd_crud`, E3 arXiv) corregidos | `docs/RELEVO_IA.md` |
| 22 | **Plan de reorientación** escrito: Track A (eficiencia) / B (eficacia, congelada) / C (protocolo OOS) | `docs/RELEVO_IA.md` |
| 23 | **Fórmula real del score v2** documentada con números de línea + lista negativa de 8 afirmaciones | **ADR 008-012**, `AGENTS.md` §8-§12 |

---

## 🔤 CÓDIGO (pendientes)

### 0. ⭐ TRACK A — EFICIENCIA (va primero, completo)

| # | Qué | Métrica de éxito |
|---|---|---|
| **A1** | **Rate limit.** 1344 req/min > 1200 ⇒ 429 ⇒ el ritmo bajó de 25-30 a **4-8 corridas/día** (señales/día ~120 → ~30). Cache de velas (TTL > 15 min, porque el snapshot es de 15 min) + WS + backoff + reducir TFs | **0 × 429** y **≥ 60 corridas/día** |
| **A2** | **`cycle_id`.** C3 inserta `cycle_id="PRE_REGIME"` (línea ~2045) y C3.5 no lo completa, aunque `zonas["macro_cycle_id"]` existe (línea 1534). ⇒ join señales↔snapshot = **0/914** | **100% de match** |
| **A3** | **`data_quality`.** `data_quality_status` no existe ⇒ el dict real es `zonas["data_quality"]["estado"]` ⇒ siempre NULL | ≠ NULL |
| **A4** | **Logs sin sobrescribir.** Hoy hay 39 líneas ⇒ el motivo de los 648 fallos del ADF se perdió | historial acumulativo |
| **A5** | **`duration_seconds` real.** La columna existe pero no mide la duración del ciclo | duración correcta |
| **A6** | **Red de seguridad del score.** 2 rutas silenciosas que devuelven 0.0 (líneas 1603-1605 y 1659-1661) | `logger.warning` + contador, 0 fallos mudos |
| **A7** | **Ventana 19 h (ADR 011).** 570 h/mes = 76% del free tier, captura la franja de las 20:00 (HR 76%, n=25) | margen de horas ≥ 20% |
| **A9** | **Renombrar `score_desglose["cvd_crud"]` → `rs_ordinal`.** El nombre ya produjo un error de análisis externo | contrato sin ambigüedad |
| **A10** | **`p_value_adf = NULL` + `regimen_test_ok`** en vez del default `1.0` (ADR 008). **Hoy 648 de 914 filas (71%) tienen `p=1.0` = el default del `except`** ⇒ el test de régimen NO corrió | 0 filas con "p=1" indistinguible de "no corrió" |

### 0.b ⭐ TRACK B — EFICACIA (congelada hasta el veredicto)

| # | Qué | Nota |
|---|---|---|
| **B0** | **Congelar `macro_score_v2` Y `bias_visual`** (ambos salen del mismo `ms` legacy) | modificarlo con 4 días de datos = data snooping |
| **B1** | **Invertir la polaridad del régimen** (`p<0,05` ⇒ `p>0,05` como condición de emisión) | **prospectiva**: se activa en T₀ y se mide. n=11 no la justifica a ciegas |
| **B2** | **Segregar universo**: cripto vs índices/metales. El percentil por activo es monótono en cripto (BTC +0,56 · xyz:CL +0,65) y **negativo** en índices/metales (SILVER −0,44 · SP500 −0,42) | n=9-14 por activo ⇒ nada significativo todavía |
| **B3** | `direccion_v2` sin `abs()` | la etiqueta v2 está invertida (RUIDO 71,4% > FUERTE 64,7%) |
| **B4** | Eliminar `d` · FVG y caja a peso 0 | ⛔ **CANCELADO**: `d` NO es degenerado (ver H-22). Sólo DESPUÉS del veredicto |

### 0.c ⭐ TRACK C — PROTOCOLO OOS (ADR 012)

**Se escribe ANTES de T₀.** Unidad = **CICLO**. N y M escritos antes.
Benchmark aleatorio con el mismo perfil. BH-FDR + **t > 3,0**
(Harvey-Liu-Zhu 2016, RFS 29(1):5-68). **NO-GO ⇒ clausura definitiva.**
⇒ La pregunta NO es "¿el score v2 predice?" sino
**"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"**

### 1. H-21 — `en_ventana()` con hora entera (NUEVO, bloquea H-18/H-13)
- `ventana.py` compara con hora entera ⇒ `VENTANA_FIN=16` **corta el ciclo de las
  16:00** y no permite expresar 03:40/16:20.
- **Fix:** minutos del día (`"04:00"` / `"16:00"`) + ciclo alineado a la
  cuadrícula de 15 min.

### 2. H-18 — Ventanas de resolución configurables (ADR 007, PROPUESTO)
- `RESOLUTION_WINDOWS_HOURS = [4, 8, 24]` hardcoded en `C4_SENIAL_VALIDATOR.py:56`.
- **Default acordado: `[4, 24]`** (no 6 ventanas). El +24h queda como control
  interno (cobertura 100%); el trader usa el +4h.
- **Geometría medida** (intervalo 15 min, ventana 04:00-16:00): +4h ⇒ 66,7% con
  snapshot limpio · +8h ⇒ 33,3% · **+12h ⇒ 0%** · +24h ⇒ 100%.
  Con `[4]` solo, 16 de 48 emisiones quedarían sin check; con `[4,24]`, 48/48.
- **Impacto de schema:** `senales_metricas` ya es genérica (`ventana TEXT`) ✅
  pero `senales_validadas` tiene **columnas fijas** (`pnl_pct/hit/resuelto_4h|8h|24h`)
  ⇒ migración aditiva e idempotente en C2.
- **Sin backfill:** los snapshots viejos ya no existen ⇒ 4h y 24h arrancan
  desde cero el día que se active.

### 3. H-13 — Etiquetas de calidad y muerte de la escala legacy
- `senales_metricas` **no agrega por `calidad_senal_v2`** ⇒ las métricas por
  etiqueta salen de la escala legacy 14/8/4, inalcanzable (`macro_score` máx 6).
- Considerar **columna nueva**, sin mutar la legacy (riesgo de sobreajuste).

### 4. Análisis de timing v3 (`--timing-h 1.0`)
- El timing actual se calcula sobre la trayectoria **completa** ⇒ correlaciona
  con el PnL final por construcción.
- **Fix:** timing sólo con snapshots hasta t+X, y PnL medido desde t+X.
- **Extra:** timing por franja horaria + LONG/SHORT por activo.

### 5. Umbral dinámico k×σ — ADR 001 (con números)
- σ por señal mediana **1,1458%** ⇒ el umbral fijo 0,05% ≡ **k = 0,044σ**,
  22× más severo en el activo más volátil.
- Mueve el **HR**, no el PF. **Decisión pendiente: ¿se implementa o se pospone?**

### 6. H-14 — `_get_price_at_time` puede tomar precio posterior
- `ORDER BY ABS(timestamp_unix - ?) ASC LIMIT 1` ⇒ 472 de 914 (52%) cambian de
  PnL. Sesgo neto < 1% ⇒ los números se sostienen, el método no.
- **Fix:** `WHERE timestamp_unix <= ? ORDER BY timestamp_unix DESC LIMIT 1`.

### 7. H-16 — "ganancia" con 2 definiciones — ⏸️ medido y diferido (ADR 004)
- `hit_rate` usa `p > ±0,05%`; `profit_factor` (C4) usa `p > 0`. Impacto <1%.

### 8. Matar los 5 fallbacks silenciosos de import — riesgo latente
- `C2_5_CONTEXTO_local.py:78`, `C3_MACRO_local.py:42,51,126`,
  `C3_5_REGIME_ENGINE.py:60`. Hoy verificado que ninguno se dispara.

### 9. `main.py` corre 8 celdas, no 9
- Falta `C3_DATA_QUALITY` como celda (sí se importa). Cosmético.

### 10. C2: "Sin backups previos" + nombre de archivo equivocado
- El auto-restore **nunca ha tenido nada que restaurar**. La nota operativa
  apunta a `GEM5_INSTITUTIONAL_VAULT.db`, que no existe (el real es `vault_v2.1.db`).

### 11. `verificar.py` debe chequear los ADR 007-012
- Hoy verifica ADR 000-006. **No se tocó** en H-22 (cambio de gate ⇒ sesión aparte).

---

## ❗ INFRAESTRUCTURA

### 12. Backup externo de la DB — **PRIORIDAD #1 (acción manual)**
- `data\vault_v2.1.db` (914 señales) y `.env`.
- Es lo único que **no** se recupera de GitHub (**`data/` está gitignored**).
- El usuario dijo que ya guardó el `.db`, pero **no confirmó que esté en Drive**.
- Copiar a Drive. Verificar que abre bien.

### 13. Actualizar `verificar.py` para los ADR 007-012 (pendiente de sesión propia)

---

## 🚫 DESCARTADOS / EN MONITOREO

- **Eliminar los cripto del universo** ⇒ descartado. Se mantienen los 12.
- **Matar el término `d` del score** ⇒ ⛔ CANCELADO el 26/10 (H-22): `d` es una
  divergencia precio/flujo real, no una constante.
- **Normalizar el score por volumen** ⇒ ⛔ CANCELADO: `caja_p` ya está
  normalizado por ATR y `rs` ya es un ordinal acotado.
- **MACRO2 (producción en Render)** ⇒ **DATA FREEZE**.
- **"Go SL dinámico ATR" del GEM** ⇒ es de MACRO2 (C7), no de MACRO2.1.
- **Reescribir el score v2** ⇒ ⛔ CANCELADO: con 4 días de datos es data snooping.
  Se congela y se testea prospectivamente.

---

## ❓ PREGUNTAS ABIERTAS (sin respuesta del usuario)

1. **¿Render 19 h (04:00-23:00) o 24/7?** (ADR 011) — 24/7 = 744 h/mes = 99% del
   free tier ⇒ sin margen. 19 h = 570 h = 76% ⇒ con margen y captura las 20:00.
2. **¿La DB de producción (Turso) usa las mismas 23 tablas que la local?**
3. **¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?**
4. **¿El `scheduler.py` local y el de Render comparten código o están duplicados?**
5. ¿Los 4 archivos "Nivel C" (`evaluar_nube.py`, `test_telegram.py`,
   `verificar_progreso.bat`, `diagnostico_bat.py`) se borran o se quedan?
6. **¿Ventana 19 h o 24/7 en Render?** (misma que 1)
7. ¿La longitud de ventana del ADF se sube a ≥500 obs (1h/4h) o se acepta el
   ruido y se marca `regimen_test_ok=0`? (A0)