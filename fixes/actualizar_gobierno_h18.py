#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
actualizar_gobierno_h18.py  -  MACRO2.1

Gobierno tras el diagnostico H-10 / H-18 (24-26/10):

  AGENTS.md          + la regla "No mezcles tareas" (pedido explicito del
                       usuario): cuando se esta validando un script/fix/analisis,
                       ese es el UNICO foco del turno. Cerrarlo primero
                       (self-test + commit) y solo despues pasar a preguntas
                       abiertas o definir el trabajo siguiente.
                     + §7: RESOLUTION_WINDOWS_HOURS apunta al ADR 007.
  ESTADO.md          reescrito: H-10 CERRADO (causa del 19/10 identificada),
                     H-18 (ventanas de resolucion) y H-20 (16,2% de señales
                     fuera de la ventana) documentados.
  docs/PENDIENTES.md reescrito: H-10 cerrado con el dato empirico, H-18 con el
                     impacto real de schema (+25 columnas), y corregido un bug
                     de rutas con doble barra.
  decisiones/007-*   NUEVO: ADR 007 ventanas de resolucion configurables
                     (PROPUESTO, no aplicado).

Uso:
  python fixes\\actualizar_gobierno_h18.py --simular   (default, no escribe)
  python fixes\\actualizar_gobierno_h18.py --aplicar
  python fixes\\actualizar_gobierno_h18.py --deshacer
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

C = {
    "r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
    "c": "\033[96m", "B": "\033[1m",
}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


ESTADO_NUEVO = r'''# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~75 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-24
Commit      : a78726b (H-17 ventana configurable) + commit de gobierno
Repo        : botmacro2-1  (desarrollo, local, SIN Docker)  |  botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h)
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre de punta a punta (`python main.py`), 8 celdas, sin excepciones
- [x] `data/vault_v2.1.db` con **914 señales (902 resueltas a 24h)**
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2)
- [x] **I-2** — Motor de régimen ADF real
- [x] **ADR 002 aplicado** — umbral ADF unificado en 0.05, fuente única `CENTRAL_PARAMS["macro"]`
- [x] **ADR 004 aplicado** — Max DD con capital compuesto (H-15) + fuente única del ADF (H-12)
- [x] **ADR 006 aplicado** — ventana operativa configurable (H-17): VENTANA/CONTINUO, cruce de medianoche, días, CLI
- [x] **H-3 y H-5 corregidos** — carpetas `backups_v2.1`/`logs_v2.1` y `_migrar_v28` sobrescribe
- [x] **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso
- [x] **Sin Docker en 2.1** (ADR 003) — producción intacta
- [x] **`docs/` ordenada** — `docs/local/` fuera de GitHub, `docs/LEEME.md` con las reglas
- [x] **Backup local de la DB** en `Desktop\\MACRO2.1_BACKUP\\` (falta subirlo a Drive)

---

## 📊 MÉTRICAS (24h, snapshot de 877 resueltas del 23/10)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| **GLOBAL** | 877 | 44.7% | 0.80 | −0.156% |
| LONG | 429 | 32.4% | **0.50** | −0.488% |
| SHORT | 448 | 56.5% | **1.28** | +0.163% |
| xyz:SILVER | 58 | 63.8% | 3.22 | +0.768% |
| xyz:GOLD | 93 | 51.6% | 2.64 | +0.309% |
| BTC | 64 | 23.4% | **0.30** | −0.630% |
| xyz:SP500 | 88 | 39.8% | **0.28** | −0.351% |

**LONG pierde plata, SHORT gana.** Problema estructural, no de umbral.
El k×σ (ADR 001) **no lo arregla**: el PF no depende del break-even.

**Asimetría confirmada por 3 métodos independientes (24/10):**
MFE/MAE real (LONG payoff **−2,9:1** · SHORT **1,75x**) · movimiento contrario
primero (LONG **54,0%** vs SHORT 34,3%) · PF por tipo (0,50 vs 1,28).
⇒ **ADR 005 (caja simétrica) PROPUESTO.**

**El score v2 SÍ discrimina dentro de cada etiqueta** (24h): FUERTE HR 93,8% ·
MODERADA 77,8% · RUIDO 65,3%. El problema es la **cobertura**: solo 9,4% son
FUERTE/MODERADA (H-9).

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | Backup de la DB solo en un disco | Hecho local (`Desktop\\MACRO2.1_BACKUP\\`), falta Drive | ❗ **Falta subirlo a Drive** |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | ❗ Pendiente → matar fallbacks |
| **H-9** | **`ms_v2` con `s_mtf = 0`** (bias 1D/4H/1H sale N/A en 7 de 12 activos) y **la rama momentum casi nunca se activa** (856 de 877 señales con p < 0.02) | El score v2 no tiene su componente multi-TF y `rs` (el flujo) pesa 0.5 en vez de 2.0 | 🔤 **NUEVO — MÁXIMA prioridad** |
| **H-10** | **Las etiquetas NO son comparables entre sí**: el 19/10 = 1er deploy a Render (v7.9.3 ⇒ `ms_v2` real). Antes no existía score v2 | Cualquier HR/PF por etiqueta es un confound temporal | ✅ **RESUELTO** (24/10: causa identificada) |
| **H-13** | `senales_metricas` no agrega por `calidad_senal_v2` | Las métricas por etiqueta salen de la escala legacy muerta | ❗ Nuevo → pendiente |
| **H-14** | `_get_price_at_time` puede tomar precio posterior al horizonte | 52% de señales cambian de PnL, pero sesgo neto < 1% | ❗ Nuevo → pendiente |
| **H-16** | "ganancia" con 2 definiciones (`p > ±0.05%` vs `p > 0`) | Impacto < 1% en PF | ⏸️ Medido y diferido (ADR 004) |
| **H-11** | `main.py` corre **8 celdas, no 9** (falta `C3_DATA_QUALITY` como celda) y el runner dice "Celdas ejecutadas: 3" | Cosmético, pero el mapa de `AGENTS.md` miente | ❗ Nuevo |
| **H-12** | C2 dice "Sin backups previos" → el auto-restore nunca tuvo nada que restaurar. La nota operativa apunta a `GEM5_INSTITUTIONAL_VAULT.db` (no existe) | El auto-restore nunca se probó de verdad | ❗ Nuevo |
| **H-2** | Dos ADF distintos (niveles en C3_5 vs residuales FFD en C3_MACRO) | El régimen no mueve el conmutador de `ms_v2` | ❗ Pendiente de decisión |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo (≡ k = 0,044σ medido) | Sesga HR (no el PF) | ❗ Pendiente → ADR 001 |
| **H-6** | `SCORE_ALTA=14` / `SCORE_MEDIA=8` con `macro_score` máximo 6 | Código muerto. Todo cae en BAJA o RUIDO | ❗ Pendiente |
| **H-8** | 6 cripto pierden (BTC PF 0.30) mientras TradFi gana | Estructural, no de umbral | ❗ En investigación |
| **H-5** | `_migrar_v28` no sobrescribía el JSON guardado | El default del código no se aplicaba | ✅ RESUELTO |
| **H-1** | Umbral ADF 0.02 en C3_MACRO vs 0.05 en C3_5 | El régimen y el `ms_v2` se contradecían | ✅ RESUELTO |
| **H-3** | `C0` escribía en `backups/`, `C2` leía de `backups_v2.1/` | El auto-restore no encontraba nada | ✅ RESUELTO |
| **H-15** | Max DD con `np.cumsum` (suma aritmética) | DD de 270% — imposible | ✅ RESUELTO (ADR 004) |
| **H-17** | Ventana hardcodeada + resúmenes de Telegram atrapados en `if not en_ventana()` | Sin 24/7 posible; resumen 8:30 AM nunca se enviaba | ✅ RESUELTO (ADR 006) |
| **H-18** | `RESOLUTION_WINDOWS_HOURS` hardcoded en `[4, 8, 24]` | Sin cortes intermedios: no se puede ver la trayectoria ni medir timing temprano | ⬜ **PROPUESTO** (ADR 007) — el storage de `senales_validadas` es de columnas fijas ⇒ requiere migración |
| **H-20** | La ventana 8-17 **no se respeta al 100%**: 39 de 240 señales (16,2%) se emitieron fuera de rango | El muestreo real ≠ el configurado ⇒ los cortes por hora no son exactos | ⬜ Nuevo |

---

## 🔒 ANTES DE CUALQUIER COSA

**Subí `C:\\Users\\MD\\Desktop\\MACRO2.1_BACKUP\\` a Drive.** El backup
local ya está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`.
Es lo único del proyecto que **no** se recupera de GitHub.

---

## 🎯 SIGUIENTE PASO (uno solo)

**Cerrar H-9 y H-10: entender por qué el `bias` 1D/4H/1H sale `N/A` y qué
pasó el 19/10.**

Dos comandos ya pendientes:
```
findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\\*.log
```
→ dice si el `N/A` es por pocas velas (Hyperliquid no devolvió 20) o por error.

**Pregunta para el usuario:** ¿qué cambió el 2026-10-19 en el pipeline? Candidatas:
(1) desplegaste v7.9.3, (2) cambiaste la ventana operativa o reiniciaste el
scheduler, (3) tocaste C3_MACRO / C3_DATA_QUALITY, (4) cambió el mercado.

**Después:** métricas por etiqueta **dentro de cada día** (elimina el confound de
H-10) y, con el diagnóstico cerrado, un ADR para la rama del `ms_v2`.

**Herramienta:** `python analisis\\rescore_umbral_v2.py` (ya tiene el corte
por día y el corte por subgrupo).

---

## 🏠 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- Un cambio por sesión. Y un commit por cambio.'''

PENDIENTES_NUEVO = r'''# PENDIENTES — MACRO2.1

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
6. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?'''

ADR007 = r'''# ADR 007 — Ventanas de resolución configurables (H-18)

- **Estado:** PROPUESTO (no aplicado)
- **Fecha:** 2026-10-26
- **Alcance:** `C4_SENIAL_VALIDATOR.py`, `C1_5_PARAM_local.py`,
  `config/CONSOLIDADO/central_params.json`, y la migración de
  `senales_validadas`.
- **Problema:** H-18.

## Contexto

`C4_SENIAL_VALIDATOR.py:56` tiene:

```python
RESOLUTION_WINDOWS_HOURS: List[int] = [4, 8, 24]
```

Cada señal se resuelve (mide su PnL) a **3 horizontes**: 4h, 8h y 24h.

**Por qué es un problema:** con 3 cortes no se ve la **trayectoria** del
precio después de la señal. No se puede saber *cuándo* se movió a favor o en
contra ⇒ **no se puede medir el timing temprano**, que es justamente lo que
hace falta para matar el look-ahead del análisis actual (el timing se calcula
sobre la trayectoria completa hasta el horizonte ⇒ correlaciona con el PnL
final por construcción).

El GEM ya lo propuso como *"validación escalonada (4→8, 12→16)"*.

## Estado real medido (diagnóstico del 24/10)

El almacenamiento **NO es uniforme**:

| Dónde | Cómo persiste | ¿Genérico? |
|---|---|---|
| `senales_metricas` | columna `ventana TEXT` + el valor `f"{ventana}h"` | ✅ **SÍ** |
| `senales_validadas` | **columnas fijas**: `precio/pnl_pct/resultado/hit/resuelto_4h`, `_8h`, `_24h` = **15 columnas** | ❌ **NO** |

**⇒ Pasar de 3 a 6 ventanas exige +25 columnas en `senales_validadas` y una
migración de schema.** (Las métricas no necesitan nada: ya son genéricas.)

El proyecto es **schema-less con migraciones aditivas e idempotentes**
(documentadas en el banner de cada celda, ej. `C2_BOVEDA_local.py` v8.5), así
que la migración es viable — pero hay que hacerla bien: `ALTER TABLE ... ADD
COLUMN` por cada columna nueva, en el `CREATE`/`_migrar` de C2.

## Decisión (PROPUESTA)

1. `RESOLUTION_WINDOWS_HOURS` deja de ser una constante y pasa a leerse de
   `CENTRAL_PARAMS["validation"]["RESOLUTION_WINDOWS_HOURS"]`, con default
   `[4, 8, 12, 16, 20, 24]`.
2. `C4` genera las columnas dinámicamente a partir de esa lista
   (`f"pnl_pct_{ventana}h"`), como ya hace con las métricas.
3. La migración de `senales_validadas` añade las columnas de 12h/16h/20h
   (5 columnas × 3 ventanas) de forma **aditiva e idempotente**.
4. `estado = 'RESUELTA'` sigue mandando la **última** ventana (24h), que es
   la de mayor horizonte.

## Consecuencias

**A favor:**
- 6 puntos de trayectoria por señal ⇒ se puede medir el timing a 1h, 2h, 3h…
  ⇒ **el look-ahead se puede eliminar** y el ADR 005 queda evaluable.
- Coherente con el ADR 006 (todo configurable, sin hardcodes dispersos).
- 6 cortes cada 4h cubren las 24h ⇒ con la ventana operativa en 24/7, cada
  señal tiene su trayectoria completa.

**En contra / a tener en cuenta:**
- **Migración de schema** (25 columnas nuevas) ⇒ hay que hacerla bien y
  documentarla. Riesgo de romper C2/C4.
- **3× más resoluciones por señal** ⇒ más trabajo de C4 y más filas en
  `senales_metricas` (1450 filas ahora).
- **Sin backfill:** las 914 señales actuales SOLO tienen 4/8/24. Los snapshots
  de precio viejos ya no existen en `price_snapshots` ⇒ **12/16/20 arrancan en
  cero** desde el día que se active. Eso no es un bug: es la línea base.
- **Cambia el régimen de datos otra vez** ⇒ igual que con la ventana operativa,
  hay que **cortar por fecha** en todo análisis posterior.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Dejar `[4, 8, 24]` y medir el timing de otra forma | El timing temprano necesita snapshots intermedios; con 3 cortes solo hay 2 puntos previos al horizonte. |
| Agregar solo 12h y 20h (5 cortes) | Arbitrario. 6 cortes a 4h de espaciado cubren las 24h simétricamente. |
| Una tabla nueva `senales_resoluciones` en vez de columnas | El schema es **schema-less con columnas**, no relacional. Una tabla nueva obligaría a reescribir todo el consumo de métricas y reportes. Inconsistente con el resto del proyecto. |
| Hardcodear `[4, 8, 12, 16, 20, 24]` en C4 | Reintroduce un hardcode disperso, que es exactamente lo que el ADR 006 vino a eliminar. |

## Cómo se verifica

```cmd
python verificar.py
```
⇒ 19 ok / 0 fallas / 1 aviso, **y** un check nuevo que confirma que las
ventanas del JSON coinciden con las de C4.

```cmd
python -c "import sqlite3;c=sqlite3.connect('data/vault_v2.1.db');print([r[1] for r in c.execute('PRAGMA table_info(senales_validadas)')])"
```
⇒ deben aparecer `pnl_pct_12h`, `pnl_pct_16h`, `pnl_pct_20h` y sus columnas.

## Referencias

- `analisis/diagnostico_h10_h18.py` (schema + cómo persiste C4).
- ADR 006 (ventana operativa configurable).
- `AGENTS.md` §7 (tabla de umbrales).'''

AG_PATCHES = [
    ("§2: no mezclar tareas (validar primero, preguntar despues)",
     '  - Nunca mas de 4, y nunca una cadena de 6 pasos para encadenar analisis.',
     '  - Nunca mas de 4, y nunca una cadena de 6 pasos para encadenar analisis.\n  - **No mezcles tareas.** Cuando estemos validando un script, un fix o un\n    analisis, ese es el UNICO foco del turno: cerralo (self-test + commit) y\n    recien ahi pasar a responder preguntas abiertas o definir el trabajo\n    siguiente. **No agregues preguntas ni ordenes extra al mismo turno de\n    validacion.**'),

    ("§7: RESOLUTION_WINDOWS_HOURS apunta al ADR 007",
     '| `RESOLUTION_WINDOWS_HOURS` | 4, 8, 24 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |',
     '| `RESOLUTION_WINDOWS_HOURS` | 4, 8, 24 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded). **ADR 007 PROPUESTO**: hacerlo config `[4,8,12,16,20,24]` (requiere +25 columnas) |'),
]


def _leer_lineas(ruta: Path):
    txt = ruta.read_text(encoding="utf-8", errors="surrogateescape")
    crlf = "\r\n" in txt
    return txt.replace("\r\n", "\n").split("\n"), crlf


def _escribir_lineas(ruta: Path, lineas, crlf: bool) -> None:
    txt = "\n".join(lineas)
    if crlf:
        txt = txt.replace("\n", "\r\n")
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(txt)


def _buscar(lineas, sec):
    """Busca `sec` (lista de lineas). 1) exacto. 2) por subcadena (1 linea)."""
    n = len(sec)
    for i in range(len(lineas) - n + 1):
        if all(lineas[i + j].strip() == sec[j].strip() for j in range(n)):
            return i
    if n == 1:
        needle = sec[0].strip()
        if len(needle) >= 12:
            for i in range(len(lineas)):
                if needle in lineas[i]:
                    return i
    return -1


def _reemplazar(lineas, viejo, nuevo):
    i = _buscar(lineas, viejo)
    if i < 0:
        return None
    return lineas[:i] + nuevo + lineas[i + len(viejo):]


class Buffer:
    """Acumula los cambios por archivo y escribe una sola vez."""

    def __init__(self):
        self.d = {}

    def get(self, ruta):
        if ruta in self.d:
            return self.d[ruta]
        return _leer_lineas(ruta)

    def set(self, ruta, lineas, crlf):
        self.d[ruta] = (lineas, crlf)


def _self_test(raiz: Path) -> int:
    fallos = 0

    def chk(nombre, cond):
        nonlocal fallos
        if cond:
            p(f"  {C['g']}OK{C['r']} {nombre}")
        else:
            fallos += 1
            p(f"  {C['R']}XX{C['r']} {nombre}")

    p(f"\n{C['B']}  SELF-TEST{C['r']}")

    ag = (raiz / "AGENTS.md").read_text(encoding="utf-8")
    chk("AGENTS.md: la regla de no mezclar tareas esta", "No mezcles tareas" in ag)
    chk("AGENTS.md: la regla de ritmo sigue", "Ritmo: 1 a 4 comandos por turno" in ag)
    chk("AGENTS.md: §7 apunta al ADR 007", "ADR 007 PROPUESTO" in ag)

    es = (raiz / "ESTADO.md").read_text(encoding="utf-8")
    chk("ESTADO.md: H-10 marcado como RESUELTO",
        "H-10" in es and "RESUELTO" in es)
    chk("ESTADO.md: H-18 y H-20 documentados", "H-18" in es and "H-20" in es)

    pe = (raiz / "docs" / "PENDIENTES.md").read_text(encoding="utf-8")
    chk("PENDIENTES.md: seccion H-10 cerrada", "H-10 CERRADO" in pe)
    chk("PENDIENTES.md: seccion H-18 con el impacto de schema",
        "H-18" in pe and "+25 columnas" in pe)
    chk("PENDIENTES.md: H-20", "H-20" in pe)
    chk("PENDIENTES.md: sin dobles barras en las rutas", "\\\\" not in pe)

    a7 = raiz / "decisiones" / "007-ventanas-resolucion-configurables.md"
    chk("ADR 007 existe y menciona las 6 ventanas",
        a7.exists() and "4, 8, 12, 16, 20, 24" in a7.read_text(encoding="utf-8"))

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("actualizar_gobierno_h18.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    hdr("  1 · ARCHIVOS DE GOBIERNO")
    buf = Buffer()
    fallidos = []

    # ---- AGENTS.md (parches) ----
    ag = RAIZ / "AGENTS.md"
    if ag.exists():
        lineas, crlf = _leer_lineas(ag)
        for desc, viejo, nuevo in AG_PATCHES:
            res = _reemplazar(lineas, [viejo], nuevo.split("\n"))
            if res is None:
                fallidos.append(("AGENTS.md", desc))
                p(f"  {C['R']}XX{C['r']} AGENTS.md — {desc}")
                p(f"      {C['R']}ancla no encontrada{C['r']}")
                continue
            lineas = res
            p(f"  {C['g']}OK{C['r']} AGENTS.md — {desc}")
        buf.set(ag, lineas, crlf)
    else:
        fallidos.append(("AGENTS.md", "no existe"))

    # ---- reescrituras completas ----
    for rel, contenido, etiqueta in (
        ("ESTADO.md", ESTADO_NUEVO, "ESTADO.md reescrito (H-10 cerrado, H-18, H-20)"),
        (os.path.join("docs", "PENDIENTES.md"), PENDIENTES_NUEVO, "docs/PENDIENTES.md reescrito"),
    ):
        ruta = RAIZ / rel
        if not ruta.exists():
            fallidos.append((rel, "no existe"))
            p(f"  {C['R']}XX{C['r']} {rel}: no existe")
            continue
        _, crlf = _leer_lineas(ruta)
        buf.set(ruta, contenido.rstrip("\n").split("\n"), crlf)
        p(f"  {C['g']}OK{C['r']} {etiqueta}")

    # ---- ADR 007 ----
    a7 = RAIZ / "decisiones" / "007-ventanas-resolucion-configurables.md"
    a7.parent.mkdir(parents=True, exist_ok=True)
    buf.set(a7, ADR007.rstrip("\n").split("\n"), False)
    p(f"  {C['g']}OK{C['r']} decisiones/007-* creado")

    if fallidos:
        hdr("  ABORTADO - no se escribio NADA")
        for a, d in fallidos:
            p(f"  {C['R']}XX{C['r']} {a} — {d}")
        p()
        p("  Pega este informe a la IA para ajustar los parches.")
        return 1

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\actualizar_gobierno_h18.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (un .bak por archivo)")
    for ruta, (lineas, crlf) in buf.d.items():
        if ruta.exists():
            bak = ruta.with_suffix(ruta.suffix + ".bak")
            shutil.copy2(ruta, bak)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        _escribir_lineas(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {ruta.relative_to(RAIZ)}")

    hdr("  3 · VERIFICACION")
    rc = _self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\actualizar_gobierno_h18.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Gobierno actualizado.{C['r']}")
    p(f"  {C['c']}Siguiente: python verificar.py + commit{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    rels = ["AGENTS.md", "ESTADO.md", "docs/PENDIENTES.md"]
    n = 0
    for rel in rels:
        bak = RAIZ / (rel + ".bak")
        orig = RAIZ / rel
        if not bak.exists():
            p(f"  {C['y']}·{C['r']} {rel}: sin .bak (nada que restaurar)")
            continue
        shutil.copy2(bak, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {rel}")
        n += 1
    a7 = RAIZ / "decisiones" / "007-ventanas-resolucion-configurables.md"
    if a7.exists():
        a7.unlink()
        p(f"  {C['g']}OK{C['r']} eliminado: decisiones/007-* (era nuevo)")
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gobierno H-18 + regla de no mezclar tareas (AGENTS.md)")
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
