# PENDIENTES — MACRO2.1

> **Este archivo es el tracking oficial.** Si algo está pendiente, va acá.
> `docs/INFORME_MACRO2.1.md` es la **spec de referencia** (no se edita);
> este archivo es el que dice **qué falta y qué se hizo**.
>
> Actualizado: 2026-10-24

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
| 9 | `verificar.py` con 19 checks, incluidos los 4 ADRs | commit `da0ad11` |
| 10 | `rescore_umbral.py` v2 (solo reconstruibles, aborta si AV1 < 90%) | `analisis/` |
| 11 | `fixes/` y `analisis/` limpios (parches de una vez → `docs/local/`) | commit `23efea4` |
| 12 | **Pipeline verificado de punta a punta** (`python main.py`, 8 celdas, +7 señales) | 2026-10-23 |
| 13 | **Backup local de la DB** en `Desktop\MACRO2.1_BACKUP\` | 2026-10-23 |
| 14 | **Max DD con capital compuesto** (H-15) + **fuente única del ADF** (H-12) | **ADR 004** |
| 15 | **Ventana operativa configurable** (VENTANA/CONTINUO, cruce de medianoche, días, CLI) + **resúmenes de Telegram fuera del `if not en_ventana()`** (H-17) | **ADR 006** |
| 16 | Análisis de timing real (914 señales) + MAE/MFE reales + σ por señal | `analisis/analisis_timing_real.py` |
| 17 | **ADR 005 (caja simétrica) PROPUESTO** + ADR 001 con k = 0,044σ medido | `decisiones/` |
| 18 | **H-10 cerrado**: causa del cambio del 19/10 identificada (1er deploy a Render + v7.9.3 ⇒ `ms_v2` real) + **H-20** (16,2% de señales fuera de la ventana) | `analisis/diagnostico_h10_h18.py` |

---

## 🔤 CÓDIGO (pendientes)

### 1. `ms_v2`: `s_mtf = 0` + rama momentum inactiva  — **AHORA ES EL #1**
- **Problema (H-9):** el bias 1D/4H/1H sale `N/A` en 7 de 12 activos ⇒ `s_mtf = 0`.
  Y el p del residual FFD sale < 0.02 en 856 de 877 señales ⇒ **la rama momentum
  casi nunca se activa**. El score v2 queda siempre en
  `0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs + 0 + d`.
- **Pero el score SÍ discrimina dentro de cada etiqueta** (24h): FUERTE HR 93,8%
  · MODERADA 77,8% · RUIDO 65,3%. El problema es la **cobertura**: solo 9,4%
  de las señales son FUERTE/MODERADA.
- **Bloqueante:** no se sabe todavía por qué el bias sale `N/A`.
  ⇒ `findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\*.log`
- **Posibles fixes (todas necesitan ADR):** (A) guardar ambas ramas en columnas
  separadas; (B) decidir la rama por detección de breakout en vez del ADF;
  (C) piso al `rs` en la rama estacionario.
- **Ojo:** `AGENTS.md` §5.1.c

### 2. ✅ H-10 CERRADO — la causa era el deploy, no el mercado
- **Qué cambió el 19/10/2026:** ese día fue el **primer deploy a Render** (chat del
  19/10, logs: *"Sin backup previo en R2 (primer deploy)"*). Simultaneó:
  1. **v7.9.3** → `macro_score_v2` pasa de placeholder `0.0` a **score real**.
  2. El bot pasó de **local** a **Render** (y Render aplica la ventana 8-17).
- **La ventana NO fue el cambio:** la distribución horaria real de la DB muestra
  que las 674 señales anteriores al 19/10 ya estaban casi todas **dentro de
  08-17** (solo 9 de 674, 1,3%, fuera, todas a las 17h).
- **Hallazgo NUEVO (H-20):** desde el 19/10, **39 de 240 señales (16,2%) se
  emitieron FUERA de 08-17** (19:00, 20:00, 21:00) ⇒ **la ventana no se respeta
  al 100%** (retrasos del scheduler o proceso local en paralelo).
- **Consecuencia:** el 13-18/10 y el 19/10+ son **dos poblaciones distintas**
  (sin score v2 vs con score v2). **No se mezclan.** Para el OOS (T_0 = 22/10)
  solo cuentan las señales desde el 19/10.
- **Herramienta:** `python analisis\diagnostico_h10_h18.py` (schema + distribución
  horaria + cómo persiste C4 las resoluciones).
- **Problema:** la distribución de etiquetas cambió por completo el 19/10
  (0 FUERTE → 1 → 9 → 10). Comparar HR/PF entre etiquetas = comparar días distintos.
- **Pendiente:** (a) saber qué cambió el 19/10; (b) medir por día antes de comparar.
- **Herramienta:** `python analisis\rescore_umbral_v2.py` (ya corta por día y por subgrupo).

### 2.b H-18 — Ventanas de resolución configurables (ADR 007, PROPUESTO)
- **Problema:** `RESOLUTION_WINDOWS_HOURS = [4, 8, 24]` hardcoded en
  `C4_SENIAL_VALIDATOR.py:56`. Con 3 cortes no se ve la trayectoria de una
  señal ⇒ **no se puede medir el timing temprano** (que es lo que mata el
  look-ahead del análisis actual).
- **Propuesta:** `[4, 8, 12, 16, 20, 24]` (6 cortes, cada 4h hasta las 24h),
  leído de `CENTRAL_PARAMS["validation"]["RESOLUTION_WINDOWS_HOURS"]`.
- **Impacto REAL (medido el 24/10):** las **métricas** (`senales_metricas`) ya
  son genéricas (`ventana TEXT` + `f"{ventana}h"`) ✅ pero **`senales_validadas`
  tiene columnas FIJAS**: `precio/pnl_pct/resultado/hit/resuelto_4h|8h|24h`
  = 15 columnas ⇒ **6 ventanas = +25 columnas y una migración de schema.**
- **El schema-less del proyecto lo hace posible** (migraciones aditivas,
  idempotentes, documentadas en el banner de C2) — pero hay que hacerlo bien.
- **Ojo:** el flag `estado='RESUELTA'` se setea cuando resuelve la ventana de
  24h (línea 497) ⇒ con 6 ventanas seguiría mandando la última. Correcto.
- **Sin backfill:** las 914 señales actuales SOLO tienen 4/8/24. Los snapshots
  de precio viejos ya no existen ⇒ **12/16/20 arrancan en cero desde el día
  que se active.**
- **Decisión pendiente del usuario:** ¿6 ventanas o se quedan en 3?

### 3. Confirmar/activar el 24/7 (ADR 006)
- **Decisión pendiente del usuario:** ¿Render free o de pago?
- **Con 24/7:** el lag de la resolución de 8h baja de **4,03h a ~21 min**
  (hoy 735 de 914 señales tienen lag > 1h); el confirmation filter aplica al
  100% en vez del 67%; desaparece el sesgo de régimen horario.
- **Con 8-17:** se conserva el comportamiento actual. **Correr el bot en local**
  si el hosting free se cae: los 30 días del OOS (21/11) se collecting igual.

### 4. Análisis de timing v3 (`--timing-h 1.0`)
- **Problema:** el timing actual se calcula sobre la trayectoria **completa**
  hasta el horizonte ⇒ correlaciona con el PnL final por construcción.
- **Fix:** timing solo con snapshots hasta t+X, y PnL medido desde t+X.
- **Extra:** timing por franja horaria + LONG/SHORT por activo (para el criterio
  del GEM: "si la asimetría se mantiene en todos los regímenes → Go CAJA simétrico").
- **Criterio Go/No-Go:** HR diff ≥ 15pp en los 3 días más recientes y que se
  mantenga en ≥ 7 de 11 días.

### 5. Etiquetas de calidad — H-13 (métricas) y H-6 (escala legacy)
- **H-13:** `senales_metricas` **no agrega por `calidad_senal_v2`** ⇒ las
  métricas por etiqueta salen de la escala legacy (14/8/4), inalcanzable con
  `macro_score` máximo 6.
- **Corrección:** agregar la agregación por `calidad_senal_v2` (o calcularla a
  mano) y **matar la escala legacy 14/8/4**.
- **Ojo:** con 111 señales reales, los cortes quedan en 20-40 ⇒ **riesgo alto de
  sobreajuste.** Considerar **columna nueva**, sin mutar la legacy.

### 6. Umbral dinámico k×σ — ADR 001 (ahora con números)
- **Problema (H-4):** `BREAKEVEN_THRESHOLD_PCT = 0.05` fijo.
- **Medido (24/10):** σ por señal mediana **1,1458%** (rango 0,318%–3,014%).
  ⇒ el umbral fijo equivale a **k = 0,044σ**, o sea **22× más severo** en el
  activo más volátil que en el menos volátil.
- **Corrección:** `umbral = k * σ`, en **columna nueva**, con baseline recalculado.
- **Realidad:** mueve el **HR**, **no el PF** (`C4` calcula el PF con `p > 0` / `p < 0`).
- **Decisión pendiente:** ¿se implementa o se pospone?

### 7. H-14 — `_get_price_at_time` puede tomar precio posterior
- `ORDER BY ABS(timestamp_unix - ?) ASC LIMIT 1` ⇒ 472 de 914 señales (52%)
  cambian de PnL con la corrección. **Sesgo neto < 1%** en HR/PF ⇒ los números
  del re-score se sostienen, el método no.
- **Fix:** `WHERE timestamp_unix <= ? ORDER BY timestamp_unix DESC LIMIT 1`
  + marcar contaminadas por staleness.

### 8. H-16 — "ganancia" con 2 definiciones
- `hit_rate`/`wins`/`losses` usan `p > ±0.05%`; `profit_factor` (C4) y
  `avg_win`/`expectancy` usan `p > 0`.
- **Medido: impacto < 1% en PF.** Unificar en el umbral de break-even es seguro
  y cosméticas la consistencia. **Diferido en ADR 004.**

### 9. Matar los 5 fallbacks silenciosos de import — **riesgo #1 latente**
- `C2_5_CONTEXTO_local.py:78`, `C3_MACRO_local.py:42`, `:51`, `:126`, `C3_5_REGIME_ENGINE.py:60`
- Deben fallar fuerte, o tener un flag explícito.
- **Verificado el 23/10 que hoy ninguno se dispara.** El día que uno se dispare,
  el pipeline se degrupa sin avisar.

### 10. `main.py` corre 8 celdas, no 9
- Falta `C3_DATA_QUALITY` como celda (sí se importa). **Sin efectos a nivel de
  módulo ⇒ no rompe nada**, pero el mapa de `AGENTS.md` miente.
- El runner reporta "Celdas ejecutadas: 3" cuando corrieron 8.

### 11. C2: "Sin backups previos" + nombre de archivo equivocado
- El auto-restore **nunca ha tenido nada que restaurar**. Si mañana corrompés la DB,
  no hay de dónde recuperar.
- La nota operativa apunta a `GEM5_INSTITUTIONAL_VAULT.db`, que no existe
  (el real es `vault_v2.1.db`).

### 12. `verificar.py` debe chequear 6 ADRs (001-006), hoy chequea 4
- Requiere ver el archivo para parchearlo con precisión.

---

## ❗ INFRAESTRUCTURA

### 13. Backup externo de la DB — **PRIORIDAD #1**
- `data\vault_v2.1.db` (914 señales) y `.env`.
- Es lo único que **no** se recupera de GitHub.
- Copiar a Drive. Verificar que abre bien.

---

## 🚫 DESCARTADOS / EN MONITOREO

- **Eliminar los cripto del universo** ⇒ descartado. Se mantienen los 12.
- **Filtro v2 con pocas señales** ⇒ se resuelve con acumulación de datos. Ojo:
  solo **111 señales tienen score v2 real** (58 con `ms_v2 >= 2`, de las cuales 20
  son FUERTE). Con 20 señales cualquier comparación de HR es ruido.
- **MACRO2 (producción en Render)** ⇒ **DATA FREEZE**.
- **"Go SL dinámico ATR" del GEM** ⇒ es de **MACRO2 (C7)**, no de MACRO2.1.

---

## ❓ PREGUNTAS ABIERTAS (sin respuesta del usuario)

1. **¿Render free o de pago?** (define si el 24/7 se activa ya)
2. **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en `logs_v2.1\*.log`)
3. ¿Los 4 archivos "Nivel C" se borran o se quedan?
4. ¿La DB de producción (Turso) usa las mismas 23 tablas que la local?
5. ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
6. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?