#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
actualizar_gobierno_h22.py  -  MACRO2.1

Gobierno de la sesion H-22 (26/10). Deja el proyecto listo para que CUALQUIER
IA (DeepSeek, Claude, GPT) lo adopte sin arrancar de cero.

  AGENTS.md         PARCHE ADITIVO idempotente: 2 secciones nuevas al final
                      (formula real del score v2 + afirmaciones prohibidas,
                       protocolo OOS).  Nunca reescribe lo que ya existe.
  ESTADO.md         REESCRITO (H-9 cerrado, H-21, H-22, Track A/B/C)
  HANDOFF.md        REESCRITO (cierre de sesion 5)
  docs/PENDIENTES.md REESCRITO (H-9 cerrado con evidencia, tareas nuevas)
  decisiones/008..012  NUEVOS (5 ADRs)

  NO toca: docs/INFORME_MACRO2.1.md (spec), verificar.py, produccion.

USO
  python fixes\\actualizar_gobierno_h22.py --simular     (default, no escribe)
  python fixes\\actualizar_gobierno_h22.py --aplicar
  python fixes\\actualizar_gobierno_h22.py --deshacer    (restaura .bak)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RAIZ = Path(__file__).resolve().parent.parent

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m"}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


# ══════════════════════════════════════════════════════════════════════════
#  1 · AGENTS.md  -  PARCHE ADITIVO
# ══════════════════════════════════════════════════════════════════════════

MARKER = "<!-- H-22:GOB-IQ -->"

AGENTS_AGREGADO = r'''
<!-- H-22:GOB-IQ -->
---

## 8. LA FÓRMULA REAL DE `macro_score_v2` (verificada en código, 26/10)

> `AGENTS.md` §5.1.c **no reproduce** el score real (0/914). Esta es la versión
> correcta, leída de `C3_MACRO_local.py` líneas 1484-1661. **Fuente de verdad.**

### 8.1 Semántica del ADF (error histórico, ya corregido)

`p_value_adf < 0.05` significa **ESTACIONARIO**, NO momentum.
La rama momentum (p ≥ 0.05) se activa cuando la serie **NO** es estacionaria.

### 8.2 Las piezas (`_calculate_ms_v2`, líneas 1588-1661)

| Pieza | Origen | Rango |
|---|---|---|
| `poc_score` | POC de la caja | {-1, +1} |
| `caja_p` | caja amplificada por volumen/ATR (`am` 0.5-2.0, línea 1495-1496) | {-2..+2} |
| `fvg` | FVG | {-1, 0, +1} |
| `rs` | **ordinal de `rvd`**, NO el CVD crudo (línea 1487) | {-2,-1,0,+1,+2} |
| `d` | divergencia POC/FLUJO (ver 8.4) | {−2, 0, +2} |

```python
# línea 1487  <-- CLAVE: rs es un ORDINAL de rvd, no el CVD crudo
rs = 2 if rvd > 0.3 else (1 if rvd > 0.1 else (-2 if rvd < -0.3 else (-1 if rvd < -0.1 else 0)))
```

### 8.3 Las dos ramas

```python
if is_stationary:      # p_value_adf < 0.05
    ms_v2 = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
else:                  # rama momentum
    ms_v2 = 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs

s_mtf = 0.30*bias_1h + 0.20*bias_4h + 0.15*bias_1d
d = -2.0 if (poc == 1 and rs <= -1) else (+2.0 if (poc == -1 and rs >= 1) else 0.0)
macro_score_v2 = round(ms_v2 + s_mtf + d, 2)
```

### 8.4 `d` NO es degenerado (refutado el 26/10)

`d` se activa cuando `|rvd| > 0.1` **y el POC está del lado opuesto al flujo**
⇒ es una **divergencia precio/flujo real**, con umbral FIJO (sin calibrar).
**No se elimina.** (Una revisión externa lo marcó como degenerado por leer el
nombre de la variable `score_desglose["cvd_crud"]`, que es engañoso.)

### 8.5 `score_desglose` real (líneas 1544-1552)

```
poc · caja · caja_raw · atr_multiplier · fvg · cvd_crud(=rs ordinal) · rvd_ultimo
```

### 8.6 Dos rutas silenciosas que devuelven 0.0

- línea 1603-1605: `if not isinstance(desglose, dict): return 0.0`
- línea 1659-1661: `except(...): logger.debug(...); return 0.0`

### 8.7 El score LEGACY (el que tiene el sesgo)

```python
# línea 1500
ms = poc_score + caja_p + fvg + rs          # pesos 1,1,1,1
# línea 1502-1510
if abs(ms) >= STRONG_BIAS_THRESHOLD and rs == 0:  bv, bi = "RANGO", "NOISE"
```

`STRONG_BIAS_THRESHOLD = 2` (línea 260).
**⇒ El filtro real de emisión es `|ms| >= 2` Y `rs != 0` ⇔ `|rvd| > 0.1`.**
**⇒ Y como `rs` pesa 1, `rs = ±2` (rvd > 0.3) ya alcanza el umbral solo
⇒ en la práctica el filtro es "`rvd` > 0,3" (o < −0,3).**

**⇒ `bias_visual` (BULL/BEAR/RANGO) y el tipo de señal (LONG/SHORT) salen del
MISMO número `ms`. Por eso coinciden en el 100% de las señales.**

---

## 9. EL FILTRO DE RÉGIMEN NO FUNCIONA (H-22, 26/10)

```python
# C3_MACRO_local.py 1901-1925
p42 = 1.0     # default
p50 = 1.0     # default
try:
    p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
    p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
except _C3_EXC as exc:
    logger.warning(f"C3 ADF/FFD fallback {coin}: {exc}")
# línea 2331
dual = "si" if (p42 <= _T_ADF_THR and p50 <= _T_ADF_THR) else "no"
```

**⇒ Los `p_value_adf = 1.0` EXACTOS (648 de 914 filas = 71%) NO son un p-value:
son el DEFAULT de la línea 1901 cuando la función lanza excepción.**
**⇒ En el 71% de las señales NO SE CORRIÓ NINGÚN TEST DE RÉGIMEN.**

### 9.1 Consecuencia fatal para el análisis

> "El score v2 se calcula sólo en régimen estacionario fuerte (p<0,001)" → **FALSO**.
> Es "en los casos donde el ADF **NO falló** y además dio p<0,001".

**⇒ Las señales con score real son un SUBMUESTRO SELECCIONADO POR ÉXITO DEL TEST.**
**⇒ NO se puede "activar/desactivar" el score a posteriori.**
**⇒ El OOS tiene que ser PROSPECTIVO: emitir siempre, registrar el score, decidir después.**

### 9.2 Regla para código nuevo

**Un test que falla NO puede dejar un valor por defecto indistinguible de un
resultado.** Si el ADF falla ⇒ `p_value_adf = NULL` + `regimen_test_ok = 0`.
Nunca `1.0`. (ADR 008)

---

## 10. AFIRMACIONES PROHIBIDAS (la lista negativa del gobierno)

**Si una de estas aparece en un análisis, en un chat o en un commit, está mal.
No se acepta sin volver a la fuente.**

1. ❌ **"El `macro_score_v2` tiene poder predictivo."** — No lo tiene demostrado.
   ρ(ms2, pnl24) = +0,119 dentro de RANGE. NO-GO cerrado el 26/10.
2. ❌ **"El sesgo multi-TF no funciona."** — FALSO. `gem_macro_snapshot` da
   N/A sólo 5,6% (1D), 5,8% (4H), 0% (15m). Funciona.
3. ❌ **"El score se calcula en régimen estacionario fuerte."** — FALSO.
   Se calcula donde el test NO FALLÓ (71% de las veces no corrió). Ver §9.
4. ❌ **"El score v2 está contaminado por la escala del volumen."** — FALSO.
   `caja_p` ya se normaliza por ATR (`am` 0.5-2.0) y `rs` es un ordinal acotado.
   El score ES comparable entre activos.
5. ❌ **"El término `d` es degenerado / hay que eliminarlo."** — FALSO.
   Es una divergencia precio/flujo real con umbral fijo sin calibrar.
6. ❌ **"El score v2 es una regresión por usar `cvd_crud` en vez de `rvd_ultimo`."**
   — FALSO: `rs` YA es un ordinal de `rvd`. El problema es otro: el v2 sube el
   peso de caja/fvg y baja el del flujo, que es lo único con evidencia.
7. ❌ **"MACRO2.1 es un bot de trading."** — NO. Es un **predictor + validador**
   de tendencia macro. No tiene posiciones, SL ni TP. El MAE/MFE es
   diagnóstico de TIMING, no P&L.
8. ❌ **"Se puede comparar HR/PF entre etiquetas o ventanas sin cortar por día."**
   — Y el grano correcto es el **CICLO**, no el día (25 ciclos para 146 señales;
   3 ciclos del 20/10 con HR 0% y 3 del 21/10 con HR 85-89%).

---

## 11. PROTOCOLO OOS (Track C) — se escribe ANTES de empezar

**Unidad de evaluación: el CICLO**, no la señal.
(25 ciclos para 146 señales; la mediana es 6 señales por ciclo ⇒ cortar por día
mezcla poblaciones distintas.)

| Elemento | Regla |
|---|---|
| **N** | nº de señales independientes, escrito ANTES |
| **M** | nº de días naturales distintos, escrito ANTES |
| **Benchmark** | aleatorio, con el MISMO perfil de señales (n, tipo, hora) |
| **Corrección** | Benjamini-Hochberg FDR + **t > 3,0** (Harvey-Liu-Zhu 2016, RFS 29(1):5-68) |
| **Expectativa** | se compara contra el benchmark, no contra 0 pelado |
| **T₀** | fecha del deploy con Track A listo |
| **Ventana** | 30 días |
| **NO-GO** | si la expectativa neta ≤ 0 ⇒ **CLAUSURA DEFINITIVA del proyecto** |

**⇒ "Si el score v2 predice" NO es la pregunta del OOS.**
**⇒ La pregunta es: _"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"_**

### 11.1 La segunda opinión (26/10) y sus 3 correcciones

La revisión externa concluyó con **NO-GO del score como predictor** y propuso:
agrupar por ciclo, t>3,0, lista negativa de gobierno y criterio de muerte.
**Sus 3 errores, ya corregidos:**

- **E1** — mezcló **Caracas con UTC**. La ventana acordada es 04:00-16:00
  **Caracas (UTC−4)** (confirmado con 3 pares epoch↔fecha de la DB).
  Su conclusión "migrar a VPS por las 20:00" queda sin base…
  **PERO:** la franja de las 20:00 Caracas (HR 76%, n=25) está FUERA de la
  ventana 04:00-16:00, y la de las 08:00 (HR 7,1%, n=14) está DENTRO.
  ⇒ El recorte quita la mejor franja y conserva la peor ⇒ **ADR 011**.
- **E2** — usó `cvd_crud` como si fuera el CVD crudo. **Resuelto el 26/10:**
  `rs` es un ordinal de `rvd` (línea 1487). Mi medición (ρ ≈ 0 con
  `cvd_raw_ultimo`) era la correcta.
- **E3** — usó `arXiv:2607.09230` (Jeon, U. Korea, 10-jul-2026) al revés: el
  paper es real pero trata transiciones de estado L2→1-5 min, NO precios a
  4h-24h. Su tesis real es **"state-first"** (el estado es el predictor de
  primer orden; cada capa sólo se acredita si aporta incremental), que sí
  respalda el NO-GO estructuralmente. **Su diseño (OOS enrollado, event-clustered,
  blocked permutation tests) es el que hay que montar.**

---

## 12. DÓNDE ESTÁ TODO (mapa para la IA que toma el control)

| Necesito | Archivo |
|---|---|
| **Brief completo para una IA nueva** | `docs/RELEVO_IA.md` ← **leé esto primero** |
| Reglas + mapa del pipeline | `AGENTS.md` (este archivo) |
| Dónde estoy hoy | `ESTADO.md` |
| Qué falta | `docs/PENDIENTES.md` |
| Qué se decidió y por qué | `decisiones/00X-*.md` (8 ADRs) |
| Spec original (NO editar) | `docs/INFORME_MACRO2.1.md` |
| Gate antes de commitear | `python verificar.py` |
| Historial de cambios | `python git/estado.py` · `git/guardar.py` · `git/deshacer.py` |

**⇒ Antes de tocar código: leé `docs/RELEVO_IA.md` + `ESTADO.md` + el ADR
vigente. Después: escribí el diseño en el chat y ESPERÁ el "ok".**
'''


# ══════════════════════════════════════════════════════════════════════════
#  2 · ESTADO.md  -  REESCRITO
# ══════════════════════════════════════════════════════════════════════════

ESTADO_NUEVO = r'''# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~110 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-26
Commit      : 31e6cd3 (H-18/H-10/H-20 + ADR 007) + commit de gobierno H-22
Repo        : botmacro2-1  (desarrollo, local, SIN Docker) | botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h) · zona horaria = CARACAS (UTC-4)
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre de punta a punta (`python main.py`), 8 celdas, sin excepciones
- [x] `data/vault_v2.1.db` con **914 señales (902 resueltas a 24h)**
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2)
- [x] **ADR 002** — umbral ADF unificado en 0.05, fuente única `CENTRAL_PARAMS["macro"]`
- [x] **ADR 004** — Max DD con capital compuesto (H-15) + fuente única del ADF (H-12)
- [x] **ADR 006** — ventana operativa configurable (H-17): VENTANA/CONTINUO, cruce de medianoche, días, CLI
- [x] **H-3 / H-5** — carpetas `backups_v2.1`/`logs_v2.1` y `_migrar_v28` sobrescribe
- [x] **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso (verifica ADR 000-006)
- [x] **Sin Docker en 2.1** (ADR 003) — producción intacta
- [x] **H-9 CERRADO** — diagnóstico completo del `macro_score_v2` (5 scripts de análisis)
- [x] **Zona horaria resuelta** — la DB guarda hora local Caracas (UTC−4), 3 pares epoch↔fecha
- [x] **Segunda opinión** recibida, revisada y sus 3 errores corregidos (E1/E2/E3)
- [x] **Plan de reorientación** escrito (Track A / B / C) — `docs/RELEVO_IA.md` §10

---

## 📊 MÉTRICAS (24h, 877 resueltas del 23/10)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| **GLOBAL** | 877 | 44.7% | 0.80 | −0.156% |
| LONG | 429 | 32.4% | **0.50** | −0.488% |
| SHORT | 448 | 56.5% | **1.28** | +0,163% |
| xyz:SILVER | 58 | 63.8% | 3.22 | +0,768% |
| xyz:GOLD | 93 | 51.6% | 2.64 | +0,309% |
| BTC | 64 | 23.4% | **0.30** | −0,630% |
| xyz:SP500 | 88 | 39.8% | **0.28** | −0,351% |

**LONG pierde plata, SHORT gana.** Problema estructural, no de umbral.
El k×σ (ADR 001) **no lo arregla**: el PF no depende del break-even.
Asimetría confirmada por 3 métodos: MFE/MAE (LONG payoff **−2,9:1** · SHORT **1,75x**) ·
movimiento contrario primero (LONG **54,0%** vs SHORT 34,3%) · PF por tipo (0,50 vs 1,28).

---

## 🧭 H-9 CERRADO — QUÉ ES REALMENTE MACRO2.1

**El score v2 NO tiene poder predictivo demostrado (NO-GO).**
ρ(ms2, pnl24) = **+0,119** dentro de RANGE. No separa nada.

**Lo que sí se midió (todo verificado contra la DB cruda):**

| Hallazgo | Dato | Dónde |
|---|---|---|
| `macro_score_v2 = 0.0` exacto | **768 de 914** = 13/10–19/10 = **PRE-DEPLOY, NO es bug vigente** | `data_quality_emision`=OK en las 768 |
| Score v2 real | **146** = 19/10–23/10 (4 días) | |
| El filtro de régimen **NO corrió** | **648 de 914 (71%)** tienen `p=1.0` = el DEFAULT del `except` | C3 líneas 1901-1925 |
| `p<0,05` significa | **ESTACIONARIO**, no momentum | |
| `riesgo_regime` real | NEUTRAL 83,4% / RISK_ON 13,0% / RISK_OFF 3,6% | |
| `bias` real (audit) | RANGO 62,3% / BULL 18,7% / BEAR 18,7% | |
| El sesgo multi-TF **SÍ funciona** | N/A sólo 5,6% (1D) · 5,8% (4H) · **0% (15m)** | |
| El grano correcto | **CICLO**, no día: 25 ciclos / 146 señales | 3 ciclos del 20/10 con HR 0% · 3 del 21/10 con HR 85-89% |
| El filtro real de emisión | **`rvd` > 0,3** (umbral legacy 2 ⇒ `rs=±2` alcanza solo) | C3 líneas 1500-1510, 260 |
| El score v2 vs legacy | v2 sube caja/fvg y **baja el flujo** ⇒ es una **regresión** | |

**⇒ ⭐ MACRO2.1 HOY ES UN DETECTOR DE FLUJO CON CONFLUENCIA, no un detector de
tendencia macro. Y su sesgo (BULL/BEAR) es el MISMO número que el tipo de señal
(LONG/SHORT) ⇒ no son dos señales, son una.**

**⇒ El único dato de eficacia es INCONSISTENTE** (LONG+BULL: pre-deploy HR
35,6% PF 0,52 · post-deploy HR 73,7% PF 9,24) ⇒ se resuelve SOLO con n suficiente.

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | Backup de la DB solo en un disco | Hecho local, **falta Drive** | ❗ **PRIORIDAD #1 (manual)** |
| **H-22** | **El test de régimen falla en el 71%** y deja `p=1.0` (indistinguible de un resultado) | La muestra de "señales con score" está **seleccionada por éxito del test** | 🔴 **NUEVO —>#1 técnico** |
| **H-9** | `macro_score_v2` sin poder predictivo demostrado | NO-GO cerrado | ✅ **CERRADO (evidencia)** |
| **H-10** | Las etiquetas no son comparables entre sí (19/10 = 1er deploy) | Confound temporal | ✅ RESUELTO |
| **H-20** | La ventana no se respeta al 100% (16,2% fuera) | Los cortes por hora no son exactos | ⬜ Nuevo |
| **H-21** | `en_ventana()` trabaja con **hora entera** | `VENTANA_FIN=16` corta el ciclo de las 16:00; no se puede expresar 03:40/16:20 | 🔴 **NUEVO — bloquea H-18/H-13** |
| **H-18** | `RESOLUTION_WINDOWS_HOURS=[4,8,24]` hardcoded | Sin cortes intermedios ⇒ no se mide timing temprano | ⬜ PROPUESTO (ADR 007) — default acordado **[4, 24]** |
| **H-13** | `senales_metricas` no agrega por `calidad_senal_v2`; escala legacy 14/8/4 muerta | Métricas por etiqueta salen de una escala inalcanzable | ❗ Pendiente |
| **H-14** | `_get_price_at_time` puede tomar precio posterior | 52% cambian de PnL, sesgo neto <1% | ❗ Pendiente |
| **H-16** | "ganancia" con 2 definiciones | Impacto <1% en PF | ⏸️ Medido y diferido (ADR 004) |
| **H-11** | `main.py` corre 8 celdas, no 9 | Cosmético, el mapa de AGENTS.md miente | ❗ Nuevo |
| **H-12** | C2 dice "Sin backups previos" ⇒ el auto-restore nunca restauró nada | Nunca probado de verdad | ❗ Nuevo |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo (≡ k=0,044σ) | Sesga HR (no el PF) | ❗ Pendente → ADR 001 |
| **H-6** | `SCORE_ALTA=14`/`MEDIA=8` con `macro_score` máx 6 | Código muerto | ❗ Pendiente |
| **H-8** | 6 cripto pierden (BTC PF 0,30) mientras TradFi gana | Estructural | ❗ En investigación |
| **H-2** | Dos ADF distintos (niveles C3_5 vs residuales FFD C3) | El régimen no mueve el conmutador | ❗ Pendiente |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | ❗ Pendiente |
| — | Rate limit de Hyperliquid | 1344 req/min > 1200 ⇒ **429**; ritmo 25-30 → **4-8 corridas/día** | 🔴 **Track A / A1** |
| — | Logs sobrescritos | 39 líneas ⇒ el motivo de los 648 fallos del ADF se perdió | 🔴 **Track A / A4** |
| — | `cycle_id` roto | join señales↔snapshot = **0/914** ⇒ auditoría rota | 🔴 **Track A / A2** |
| — | `data_quality` siempre NULL | El dict real es `zonas["data_quality"]["estado"]` | 🔴 **Track A / A3** |
| — | `duration_seconds` no es duración | No se puede medir el costo por ciclo | 🔴 **Track A / A5** |
| — | `_classify_signal_quality_v2` usa `abs()` | Etiqueta invertida (RUIDO 71,4% > FUERTE 64,7%) | ⬜ **Track B / B3** |
| — | `score_desglose["cvd_crud"]` mal nombrado | Ya produjo un error de análisis externo | ⬜ **Track A / A9** |

---

## 🔒 ANTES DE CUALQUIER COSA

**Subí `C:\Users\MD\Desktop\MACRO2.1_BACKUP\` a Drive.** El backup local ya
está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`. Es lo único del
proyecto que **no** se recupera de GitHub. **`data/` está gitignored.**

---

## 🎯 SIGUIENTE PASO (Track A, en este orden)

1. **A1 — Rate limit.** 1344 req/min > 1200 ⇒ 429 ⇒ 4-8 corridas/día.
   Cache de velas (TTL > 15 min) + WS + backoff + reducir TFs.
   **Objetivo: 0 × 429 y ≥ 60 corridas/día.**
2. **A2 — `cycle_id`.** C3.5 debe escribir `zonas["macro_cycle_id"]`.
   **Objetivo: 100% de match.**
3. **A3 — `data_quality`.** `zonas["data_quality"]["estado"]` ⇒ no NULL.
4. **A0 — Test de régimen.** `p=NULL` + `regimen_test_ok` en vez de `p=1.0`.
   Recalibrar la longitud de ventana del ADF (n ≈ 42 es insuficiente).
5. **A4 / A5 / A6** — logs acumulativos · `duration_seconds` real ·
   red de seguridad del score (`logger.warning` + contador).
6. **A9** — renombrar `score_desglose["cvd_crud"]` → `rs_ordinal`.
7. **A7 — Ventana** (ADR 011): 19 h (04:00-23:00) = 570-589 h/mes = 76-78% del
   free tier, y captura la franja de las 20:00 (HR 76%, n=25).
8. **H-21** (ventana en minutos) → **H-18** (`[4,24]`) → **H-13**.

**⇒ Track C (protocolo OOS) se escribe ANTES de T₀** (ADR 012).
**⇒ T₀ = fecha del deploy con el Track A listo.**
**⇒ Track B (B1/B3) se aplica SOLO en T₀, prospectivo. B4 (limpiar el score)
solo DESPUÉS del veredicto.**

---

## 🏠 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Un cambio por sesión. Un commit por cambio. `git/guardar.py` para commitear.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- **1 a 4 comandos por turno.** Si uno depende del anterior, de a uno.
- **No mezcles tareas:** cerrar el trabajo en curso antes de abrir el siguiente.
- **Nunca escribir archivos sin "ok" explícito del usuario.**
'''


# ══════════════════════════════════════════════════════════════════════════
#  3 · docs/PENDIENTES.md  -  REESCRITO
# ══════════════════════════════════════════════════════════════════════════

PENDIENTES_NUEVO = r'''# PENDIENTES — MACRO2.1

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
'''


# ══════════════════════════════════════════════════════════════════════════
#  4 · HANDOFF.md  -  REESCRITO
# ══════════════════════════════════════════════════════════════════════════

HANDOFF_NUEVO = r'''# HANDOFF — MACRO2.1

> Estado al cierre de la sesión. La próxima IA debe leer:
> **`docs/RELEVO_IA.md`** (brief completo) → `AGENTS.md` → este archivo → `docs/PENDIENTES.md`.

```
Sesión     : 5  (cierre 2026-10-26)
Rama       : main
Último commit : 31e6cd3  (H-18 / H-10 / H-20 + ADR 007)
Pendiente de commit : gobierno H-22 (este paquete)
Producción  : botmacro — CONGELADA (DATA FREEZE), no tocar
Desarrollo  : botmacro2-1 — este repo
```

---

## ✅ Lo que se hizo en esta sesión

1. **H-9 cerrado CON EVIDENCIA** (no con intuición):
   `macro_score_v2` **no tiene poder predictivo demostrado** (NO-GO).
   ρ(ms2, pnl24) = +0,119 dentro de RANGE. El score no separa nada.
2. **5 scripts de análisis** corriendo contra la DB real:
   `diagnostico_h9.py` · `descomponer_score_v2.py` ·
   `poder_predictivo_score_v2.py` · `reconstruir_score_v2.py` ·
   `reconciliar_score_cero.py` (v2, 11 secciones).
3. **Corrección de semántica**: `p_value_adf < 0.05` = **ESTACIONARIO**, no momentum.
4. **768 de 914 con score 0.0 = PRE-DEPLOY** (13/10-19/10), **NO es un bug vigente**.
   146 reales = 19/10-23/10.
5. **El sesgo multi-TF SÍ funciona** (N/A sólo 5,6% / 5,8% / 0%).
6. **La zona horaria resuelta**: la DB guarda **hora local Caracas (UTC−4)**,
   confirmado con 3 pares epoch↔fecha. ⇒ El análisis por hora es en Caracas.
7. **Segunda opinión** recibida y revisada. Sus 3 errores corregidos (E1/E2/E3).
8. **H-22 (nuevo)**: el test de régimen **NO corrió en el 71%** de las señales
   (648 de 914 con `p=1.0` = el default del `except`) ⇒ la muestra está
   **seleccionada por éxito del test** ⇒ el OOS **tiene que ser prospectivo**.
9. **H-22 (nuevo)**: `rs` es un **ordinal de `rvd`**, no el CVD crudo ⇒
   ⛔ `d` NO es degenerado (contra la segunda opinión) y ⛔ el score NO está
   contaminado por escala.
10. **H-22 (nuevo)**: el filtro real de emisión es **`rvd` > 0,3** ⇒ la
    hipótesis de eficacia cabe en un solo número.
11. **Plan de reorientación** escrito: Track A (eficiencia) / B (eficacia,
    congelada) / C (protocolo OOS), con lista negativa de 8 afirmaciones.

---

## 📌 Lo que la próxima sesión tiene que hacer

**PRIMERO (manual, el usuario):** subir el backup de la DB a Drive.
**PRIMERO (código):** **A1 — rate limit.**

```cmd
python fixes\actualizar_gobierno_h22.py --aplicar
python verificar.py
python git\guardar.py "gobierno H-22: H-9 cerrado, H-22 (ADF falla 71%), ADR 008-012, RELEVO_IA"
git push origin main
```

**Después, en este orden:** A2 (`cycle_id`) → A3 (`data_quality`) →
A0 (test de régimen) → A4/A5/A6 → A9 → A7 (ventana 19 h) →
**H-21** → **H-18** → **H-13**.

**Track C (protocolo OOS) se escribe ANTES de T₀** (ADR 012).
**T₀ = fecha del deploy con el Track A listo.**

---

## ⚠️ Trampas documentadas (no repetirlas)

- **CMD.exe únicamente.** Sin PowerShell, sin `curl`/`wget` unix, sin `&&`, sin `;`.
- **`more` y `type` CUELGAN la consola** (el usuario tuvo que pegarle Ctrl+C y
  se le reinició el historial). Para volcar un archivo: `findstr /n "patron" archivo`
  o redirigir a un `.txt` y pegar ese.
- **UTF-8 en consola china/ANSI sale como mojibake** (`—` → `ÔÇö`).
  ⇒ En parches, anclar con **cadenas ASCII puras**.
- En Python, un `''` sin escaping dentro de un string SQL rompe todo
  (`no such column: senales_valADAS`, `no such column: ANTES`). Usar `?`.
- `findstr` con acentos no funciona en la consola ⇒ buscar por palabras ASCII.
- Los scripts de git **siempre en Python** (Windows).
- `git rm --cached <file>` para sacarlo del índice sin borrarlo del disco
  (se usó con `timing_real.json`).
- `verificar.py` es el **gate** antes de commitear. Si falla, no se avanza.

---

## 🎯 La pregunta abierta que define el proyecto

> **"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"**

No "¿el score v2 predice?" — esa ya está contestada (NO-GO).
El OOS es **prospectivo**, la unidad es el **CICLO**, N y M se escriben antes,
el benchmark es aleatorio con el mismo perfil, BH-FDR + **t > 3,0**,
y si la expectativa neta ≤ 0 ⇒ **clausura definitiva**.

---

## 📂 Archivos clave

| Archivo | Qué es |
|---|---|
| `docs/RELEVO_IA.md` | ⭐ **El brief completo para esta u otra IA** |
| `AGENTS.md` | Reglas de la casa + §8 fórmula real + §10 lista negativa + §11 OOS |
| `ESTADO.md` | Dónde estoy hoy (se reescribe, no se acumula) |
| `HANDOFF.md` | Este archivo (cierre de sesión) |
| `docs/PENDIENTES.md` | Tracking oficial de lo que falta |
| `docs/INFORME_MACRO2.1.md` | Spec original — **NO editar** |
| `decisiones/00X-*.md` | Los 8 ADRs (por qué se decidió cada cosa) |
| `verificar.py` | Gate de 19 checks |
| `git/guardar.py` · `estado.py` · `deshacer.py` | Kit de git |
| `analisis/*.py` | Los 5 scripts de diagnóstico de H-9 + timing + H-10/H-18 |
| `fixes/*.py` | Parches de una vez (se archivan a `docs/local/`) |
'''


# ══════════════════════════════════════════════════════════════════════════
#  5 · LOS 5 ADRs NUEVOS
# ══════════════════════════════════════════════════════════════════════════

ADR008 = r'''# ADR 008 — Un test que falla no puede dejar un valor por defecto

- **Estado:** PROPUESTO (no aplicado)
- **Fecha:** 2026-10-26
- **Alcance:** `C3_MACRO_local.py` (`_calculate_ms_v2` y el bloque de régimen),
  `macro_audit_log`, `gem_macro_snapshot`.
- **Problema:** H-22.

## Contexto

El test de régimen del score v2 se computa así (`C3_MACRO_local.py` 1901-1925):

```python
p42 = 1.0     # default
p50 = 1.0     # default
try:
    p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
    p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
except _C3_EXC as exc:
    logger.warning(f"C3 ADF/FFD fallback {coin}: {exc}")
```

Y el score guarda `"p_value_adf": p42` (línea 1937) y
`dual = p42 <= _T_ADF_THR and p50 <= _T_ADF_THR` (línea 2331).

**Medición sobre la DB real (26/10):** **648 de 914 filas (71%)** tienen
`p_value_adf = 1.0` **exacto** y `p_value_v50 = 1.0` **exacto**.
Ese 1.0 no es un p-value: **es el default de la línea 1901**.

**⇒ En el 71% de las señales NO SE CORRIÓ NINGÚN TEST DE RÉGIMEN.**

### Consecuencia estadística (grave)

> "El score v2 se calcula sólo en régimen estacionario fuerte (p<0,001)" → **FALSO**.
> Es: "en los casos donde el ADF **no falló** y además dio p<0,001".

**⇒ Las señales con score real son un SUBMUESTRO SELECCIONADO POR ÉXITO DEL
TEST** (los casos donde la regresión converge son los más "limpios").
**⇒ Cualquier comparación "con score" vs "sin score" sobre datos retrospectivos
está contaminada por selección.**
**⇒ NO se puede "activar/desactivar" el score a posteriori. El OOS tiene que ser
PROSPECTIVO: emitir siempre, registrar el score, y decidir después.**

### Consecuencia operativa

El `logger.warning` SÍ existe, pero **los logs se sobrescriben** (39 líneas hoy).
⇒ El motivo de los 648 fallos **se perdió**. Por eso el log acumulativo (A4) es
prerrequisito de este ADR.

## Decisión (PROPUESTA)

1. Si el test falla ⇒ `p_value_adf = NULL` y `p_value_v50 = NULL`.
2. Se agrega una columna `regimen_test_ok` (0/1) a `macro_audit_log`.
3. La rama del score (`is_stationary`) usa un valor **explícito**:
   `True` sólo si `regimen_test_ok = 1` y `p < 0.05`;
   `None` si el test no corrió (⇒ el score registra `NULL`, no `0.0`).
4. El `dual` (p42 Y p50) pasa a 3 estados: `si` / `no` / `desconocido`.
5. `logger.warning` + **contador persistente** de fallos (no sólo texto de log).
6. Los logs pasan a ser acumulativos (A4) — **prerrequisito**.

## Consecuencias

**A favor:**
- Un `p=NULL` es distinguible de un `p=1.0` ⇒ la selección desaparece de los
  datos ⇒ el análisis retrospectivo deja de estar contaminado.
- El motivo del fallo queda en el log y en un contador ⇒ no se pierde más.
- Permite medir, en OOS, **qué pasa con las señales que el test no evaluó**
  (que hoy son el 71% y están invisiblemente descartadas).

**En contra / a tener en cuenta:**
- Toca el schema de `macro_audit_log` ⇒ migración aditiva e idempotente en C2.
- El score v2 passa a tener un tercer estado ⇒ hay que actualizar el cálculo
  de `macro_score_v2` y sus consumidores (`scheduler.py` línea ~510 ya usa
  `macro_score_v2 IS NULL OR macro_score_v2 = 0.0` como marcador).
- **No arregla** la longitud de la ventana del ADF (n ≈ 42), que es un problema
  aparte (A0): aunque el test corra, con n=42 el ADF tiene baja potencia.
  Este ADR hace que el problema sea **visible**, no que desaparezca.

## Alternativas descartadas

- **A) Dejar `p=1.0` y filtrar los fallos en el análisis.** Descartado: el
  valor no distingue "no estacionario" de "no se evaluó" ⇒ el sesgo de
  selección es invisible y se propaga a cada informe.
- **B) Propagar la excepción y abortar el ciclo.** Descartado: una sola señal
  con datos raro mataría el pipeline entero.
- **C) Subir n a ≥500 obs y arreglar el ADF.** Necesario (A0) pero **no
  suficiente**: aunque el test sea válido, puede fallar. Ambas cosas hacen falta.

## Relación

- **ADR 002** (fuente única del umbral 0,05) sigue vigente: el problema no es
  el umbral, es que el test no corría.
- **ADR 009** (congelar el score) evita el riesgo de reescribir la rama del
  score mientras el test es un box negro.
'''

ADR009 = r'''# ADR 009 — Congelar `macro_score_v2` y `bias_visual`

- **Estado:** ACEPTADO
- **Fecha:** 2026-10-26
- **Alcance:** `C3_MACRO_local.py` (`_calculate_ms_v2`, líneas 1484-1661).
- **Problema:** H-9 + H-22.

## Contexto

El score v2 **no tiene poder predictivo demostrado** (NO-GO cerrado el 26/10
con 5 scripts de análisis contra la DB real):

- ρ(`macro_score_v2`, pnl24) = **+0,119** dentro de RANGE ⇒ no separa.
- HR por cuartil de score: 65,5% / 53,3% / 82,8% / 63,3% ⇒ **no monótono**.
- El único efecto real es **régimen + tiempo + grano de ciclo**.

Peor: con solo 4 días de datos post-deploy (146 señales), **reescribir el score
es data snooping** (la segunda opinión lo señaló explícitamente).

### El score v2 vs el legacy (el dato que faltaba)

```python
# legacy, línea 1500
ms = poc_score + caja_p + fvg + rs            # pesos 1, 1, 1, 1
```

```python
# v2
if is_stationary:  ms_v2 = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
else:              ms_v2 = 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs
```

**⇒ El v2 SUBE el peso de caja y fvg y BAJA el del flujo (`rs`).**
**⇒ El legacy prioriza el flujo, que es lo único con evidencia (el filtro real
de emisión es `rvd` > 0,3).**
**⇒ ⭐ El score v2 es, en la práctica, una REGRESIÓN sobre la señal que sí
funciona.**

### `bias_visual` y el tipo de señal son el MISMO número

`bv`/`bi` (líneas 1502-1510) se derivan del MISMO `ms` que define LONG/SHORT.
⇒ No son dos señales, son una. Por eso el `bias` coincide con el tipo en el
**100%** de las señales (0 contradicciones en 914).

## Decisión

1. **`macro_score_v2` y `bias_visual` quedan CONGELADOS.** No se reescriben,
   no se "arreglan", no se les cambian pesos.
2. El score se sigue **calculando y registrando** ⇒ queda como *covariate*
   para el análisis y para el OOS.
3. **La decisión de emitir NO se apoya en el score v2** durante el OOS.
   Se apoya en el sesgo legacy (`ms` ≥ 2 con `rs != 0` ⇔ `rvd` > 0,3).
4. El único cambio permitido en el score mientras dure el OOS es **de
   transparencia**, no de peso:
   - **A9**: renombrar `score_desglose["cvd_crud"]` → `rs_ordinal`
     (el nombre YA produjo un error de análisis externo: se creyó que era el
     CVD crudo, y no lo es).
   - **A10/ADR 008**: `p=NULL` + `regimen_test_ok` cuando el test falla.

## Consecuencias

**A favor:**
- Ninguna tentación de reescribir con n chico.
- El OOS mide una hipótesis limpia: ¿`rvd` > 0,3 ⇒ el LONG rinde?
- El score sigue siendo un covariate gratis para el análisis de mediana.

**En contra / a tener en cuenta:**
- Se deja de usar una señal que "parecía" promising (ρ +0,119). **Es correcto**:
  ρ +0,119 con n=118 es indistinguible de ruido.
- Se acepta que el producto no mejora "el score" ⇒ **el producto es el filtro
  de régimen + el umbral de flujo**, no el score.

## Alternativas descartadas

- **A) Reescribir el score con un ensamble ADF+KPSS+VR+Hurst.** Descartado:
  4 días de datos, y la segunda opinión ya señaló el data snooping.
- **B) Construir un "score v3".** Descartado: es exactamente lo que este ADR
  prohíbe, y con la muestra contaminada por selección (ADR 008) sería peor.
- **C) Invertir la polaridad del régimen YA, a ciegas.** El buckete `p ≥ 0,50`
  da HR 81,8% / PF 8,68 / E +1,087 con **n = 11**. ⇒ Se hace **prospectivo
  en T₀** (B1), no en retrospectivo.

## Relación

- **ADR 008** (p=NULL) es la excepción permitida a la congelación: es
  transparencia, no peso.
- **ADR 012** (protocolo OOS) define cómo se mide.
'''

ADR010 = r'''# ADR 010 — La hipótesis del OOS: el filtro real es `rvd` > 0,3

- **Estado:** PROPUESTO (no aplicado)
- **Fecha:** 2026-10-26
- **Alcance:** definición del OOS; no toca código de producción todavía.
- **Problema:** H-22.

## Contexto

### El filtro de emisión real (verificado en código)

```python
# C3_MACRO_local.py línea 260
STRONG_BIAS_THRESHOLD = int(_get_macro_param("STRONG_BIAS_THRESHOLD", 2))

# línea 1500
ms = poc_score + caja_p + fvg + rs

# líneas 1502-1510
if abs(ms) >= STRONG_BIAS_THRESHOLD and rs == 0:
    bv, bi = "RANGO", "NOISE"
else:
    bv = "BULL" if ms >= STRONG_BIAS_THRESHOLD else ("BEAR" if ms <= -STRONG_BIAS_THRESHOLD else "RANGO")
```

Y `rs` es un **ordinal de `rvd`** (línea 1487):
`rs = 2` si `rvd > 0.3` · `1` si `rvd > 0.1` · `-1` si `rvd < -0.1` · `-2` si `rvd < -0.3`.

**⇒ El filtro de emisión es `|ms| >= 2` Y `rs != 0` ⇔ `|rvd| > 0.1`.**
**⇒ Y como `rs` pesa 1 en el legacy, `rs = ±2` (rvd > 0,3) YA alcanza el umbral
por sí solo ⇒ en la práctica el filtro es "`rvd` > 0,3" (o < −0,3), y
poc/caja/fvg sólo desempatan.**

### El dato de eficacia (inconsistente ⇒ no se puede decidir en retrospectivo)

| Población | LONG + BULL | SHORT + BEAR |
|---|---|---|
| pre-deploy (768, 13-19/10) | HR 35,6% · PF 0,52 | HR 57,8% · PF 1,27 |
| post-deploy (146, 19-23/10) | HR 73,7% · PF 9,24 | HR 59,7% · PF 1,87 |

**⇒ El único dato de eficacia del proyecto se contradice entre poblaciones.**
**⇒ Se resuelve SÓLO con n suficiente (OOS prospectivo).**

### El grano correcto es el ciclo

25 ciclos para 146 señales (mediana 6). 3 ciclos del 20/10 con HR 0,0%;
3 ciclos del 21/10 con HR 85-89%. **El día es el grano equivocado.**

## Decisión (PROPUESTA)

La pregunta del OOS **no** es "¿el score v2 predice?". Es:

> **"¿`rvd` suavizado > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"**

Sub-preguntas, en orden de prioridad:

1. **H-A (principal):** expectativa neta del grupo `rvd > 0,3` (LONG) vs benchmark.
2. **H-B:** ¿el régimen (`regimen_test_ok` + `d_ffd` + `memoria_pct`) modula esa
   expectativa? (interacción, no efecto principal)
3. **H-C:** ¿el umbral 0,1 vs 0,3 vs 0,5 cambia la expectativa neta? (es un
   problema de **umbral**, no de score)
4. **H-D (secundaria, exploratoria):** el score v2 como covariate — ¿aporta
   incremental sobre `rvd`? (es la forma de "cada capa sólo se acredita si
   aporta incremental", del paper *state-first*).

**⇒ Los umbrales se evalúan como un problema de ROC, NO se reescriben a mano.**

## Consecuencias

**A favor:**
- Una sola variable, un solo umbral, una pregunta binaria ⇒ el OOS es
  interpretable y el resultado es accionable en los dos sentidos.
- Si H-A falla ⇒ **NO-GO ⇒ clausura**, que es un resultado VÁLIDO y barato.
- Si H-A pasa ⇒ H-D justifica o no resurrectar el score v2.

**En contra / a tener en cuenta:**
- `rvd` es un indicador de flujo relativo, no de tendencia ⇒ **el horizonte de
  24h puede ser el equivocado**. La literatura verificada (OFI de
  Cont-Kukanov-Stoikov) dice que el order flow predice a **50 ms-5 min**.
  ⇒ El OOS debe registrar también el resultado a **1h y 4h**, no sólo 24h.
- `rvd` es un **proxy** del order flow, no el order flow real (OBI no es
  reconstruible del histórico de Hyperliquid: `s3://hyperliquid-archive` no
  garantiza completitud).

## Alternativas descartadas

- **A) "¿El score v2 predice?"** ⇒ ya contestado: NO-GO.
- **B) Invertir la polaridad del régimen a ciegas (n=11).** ⇒ se hace
  prospectivo en T₀ (B1), no en retrospectivo.
- **C) Reescribir el score.** ⇒ ADR 009 lo prohíbe.

## Relación

- **ADR 009** congela el score ⇒ esta ADR define qué se testea.
- **ADR 012** define el protocolo (N, M, benchmark, t>3,0, NO-GO).
- **ADR 011** decide la ventana operativa, que define **cuántos ciclos** hay por
  día ⇒ define N.
'''

ADR011 = r'''# ADR 011 — Ventana operativa: 19 h en Render free (no 8-17, no 24/7)

- **Estado:** PROPUESTO (esperando decisión del usuario)
- **Fecha:** 2026-10-26
- **Alcance:** `C1_5_PARAM_local.py`, `central_params.json`, `ventana.py`.
- **Problema:** H-21 + la zona horaria resuelta.

## Contexto

### La zona horaria (resuelta el 26/10)

3 pares epoch↔`fecha_hora` de la propia DB:

```
1791894866 → 2026-10-13 08:35:03   offset −3,99 h
1792432869 → 2026-10-19 14:07:12   offset −3,90 h
1792799471 → 2026-10-23 19:51:11   offset −4,00 h
```

**⇒ La DB guarda HORA LOCAL CARACAS (UTC−4).** ⇒ El análisis por hora es en
Caracas. (La segunda opinión mezcló Caracas con UTC: su conclusión "migrar a
VPS por las 20:00" quedaba sin base.)

### El problema: el recorte quita la mejor franja

| Hora Caracas | HR 4h | n | ¿En 04:00-16:00? |
|---|---|---|---|
| 08:00 | 7,1% | 14 | **SÍ — y es la peor hora** |
| 09:00 | 40,0% | 10 | sí |
| 10:00 | 20,0% | 10 | sí |
| 13:00 | 23,5% | 17 | sí |
| 14:00 | 30,0% | 20 | sí |
| 15:00 | 55,6% | 18 | sí |
| 16:00 | 33,3% | 18 | no |
| **20:00** | **76,0%** | **25** | **NO — y es la mejor** |
| 21:00 | 0,0% | 7 | no |

**⇒ El recorte 04:00-16:00 conserva la peor hora y descarta la mejor.**

### El presupuesto de Render free

El free tier da **750 h/mes**. Con la ventana en minutos y el ciclo alineado a
la cuadrícula de 15 min:

| Opción | h/día | h/mes (31 d) | % del tier | ¿captura las 20:00? |
|---|---|---|---|---|
| 04:00-16:00 (12 h) | 12 | 360-372 | 48-50% | ❌ |
| **04:00-23:00 (19 h)** | **19** | **570-589** | **76-78%** | **✅** |
| 24/7 | 24 | 744 | **99,2%** ⚠️ | ✅ |

**⇒ ⭐ 24/7 en Render free es aritméticamente viable pero deja 6 h de margen
(sin margen si el mes tiene 31 días y hay reinicios). 19 h deja 21% de margen.**

**⇒ Y con el rate limit arreglado (A1), 19 h/día ⇒ ~60-80 corridas/día
(hoy 4-8) ⇒ el grano de ciclo se multiplica ⇒ el OOS se vuelve posible.**

## Decisión (PROPUESTA)

**Ventana por defecto: 04:00-23:00 Caracas (19 h)**, modo VENTANA.
CONTINUO queda disponible con 1 comando para VPS (ADR 006).

**⇒ Requiere H-21 primero**: `en_ventana()` hoy trabaja con **hora entera** ⇒
`VENTANA_FIN=16` corta el ciclo de las 16:00 y no permite expresar 03:40/16:20.
El fix es migrar a **minutos del día** (`"04:00"` / `"23:00"`).

## Consecuencias

**A favor:**
- Captura la franja de las 20:00 (HR 76%, n=25) ⇒ más ciclos por día ⇒ N más
  grande en el OOS.
- 78% del tier ⇒ margen para reinicios y para el auto-restore.
- Mismo modo CONTINUO para VPS (sin tocar código).

**En contra / a tener en cuenta:**
- **n por hora es 7-25 ⇒ NO alcanza para decidir nada.** La franja de las 20:00
  puede ser ruido ⇒ la ventana es un **parámetro a calibrar**, no una decisión
  final.
- A 19 h/día el consumo de horas sube ⇒ hay que vigilar el tier.
- Si el rate limit (A1) NO se arregla, 19 h/día **no** da 60-80 corridas/día
  ⇒ la hipótesis de la tabla se cae ⇒ **A1 es prerrequisito de esta ADR.**

## Alternativas descartadas

- **A) Mantener 04:00-16:00.** Descartado: descarta la mejor franja y conserva
  la peor, con el mismo consumo de horas que la opción de 19 h es más barata
  que 24/7.
- **B) 24/7 en Render free.** Descartado por ahora: 744 h/mes = 99,2% del
  tier ⇒ cualquier reinicio se come el margen. **Se revisita si A1 reduce el
  costo por ciclo Y el tier sube.**
- **C) VPS.** Descartado por ahora: no hace falta para el OOS si 19 h dan
  suficientes ciclos. Es la opción si A1+A7 no dan N suficiente.

## Relación

- **ADR 006** (ventana configurable) ya da el mecanismo.
- **H-21** es el prerrequisito técnico.
- **A1** es el prerrequisito de negocio.
'''

ADR012 = r'''# ADR 012 — Protocolo OOS prospectivo, con criterio de muerte

- **Estado:** PROPUESTO (se escribe ANTES de T₀)
- **Fecha:** 2026-10-26
- **Alcance:** gobierno (`AGENTS.md` §11, `ESTADO.md`, `docs/PENDIENTES.md`).
- **Problema:** el proyecto no tiene un criterio de falsación ⇒ no puede morir.

## Contexto

El proyecto lleva 4+ meses con datos de ~900 señales y **ningún criterio
escrito** de cuándo se considera que la hipótesis es falsa. Sin eso, el OOS se
autoengaña: cualquier resultado se puede reinterpretar.

Además, H-22 mostró que **la muestra retrospectiva está contaminada por
selección** (el 71% de las señales no tiene test de régimen ⇒ las 146 "con
score" son las que el test pudo evaluar). ⇒ **No se puede decidir a posteriori.

## Decisión (PROPUESTA)

### 1. Prospectivo, no retrospectivo

**T₀ = la fecha del deploy con el Track A listo.** Desde T₀:
**se emite SIEMPRE**, se registra TODO (incluido `rvd`, `regime_test_ok`, el
score, la hora, el ciclo) y **se decide después**.

### 2. La unidad de evaluación es el CICLO

No la señal, no el día. 25 ciclos para 146 señales (mediana 6) ⇒ cortar por
día mezcla poblaciones distintas: 3 ciclos del 20/10 con HR 0,0% y 3 del 21/10
con HR 85-89%.

### 3. N y M se escriben ANTES de empezar

- **N** = nº de señales independientes necesarias.
- **M** = nº de días naturales distintos.
- Se escriben en `docs/PENDIENTES.md` con fecha, ANTES de T₀.
- **Ventana: 30 días.** Si al día 30 no se llegó a N, se sigue hasta llegar
  (y se documenta el tiempo real).

### 4. Benchmark aleatorio con el MISMO perfil

Para cada ciclo, un conjunto aleatorio de señales con el mismo n, el mismo
tipo (LONG/SHORT) y la misma franja horaria. **La expectativa se compara contra
el benchmark, no contra 0 pelado.** (Contra 0, cualquier ruido da "edge".)

### 5. Corrección por múltiples tests

**Benjamini-Hochberg FDR + |t| > 3,0.**
Referencia: Harvey, Liu & Zhu (2016), *RFS* 29(1):5-68, *"…and the Cross-Section
of Expected Returns"* — con múltiples tests y el estadístico T, un |t| > 3,0 es el
umbral estándar (no 2,0).

### 6. La pregunta y sus sub-preguntas

> **"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"** (ADR 010)

### 7. ⭐ CRITERIO DE MUERTE

**Si la expectativa neta (H-A) ≤ 0 frente al benchmark, con el protocolo
aplicado y N/M alcanzados ⇒ NO-GO ⇒ CLAUSURA DEFINITIVA del proyecto.**

No hay "reformulemos la hipótesis". Un NO-GO con N suficiente es un resultado
**válido y barato** (30 días de collecting, no meses más de análisis).

### 8. La lista negativa (8 afirmaciones)

Vive en `AGENTS.md` §10. **Si una aparece en un análisis, un chat o un commit,
está mal** y hay que volver a la fuente.

## Consecuencias

**A favor:**
- El proyecto puede **terminar**. Hoy no puede.
- Los datos de T₀ en adelante son **no contaminados** (a diferencia de todo lo
  anterior).
- El benchmark aleatorio mate la tentación de "buscar el corte bueno".
- El t > 3,0 + FDR protege del data snooping de las sub-preguntas.

**En contra / a tener en cuenta:**
- **30 días de espera** ⇒ hay que resisting la tentación de analizar antes.
- Si N no se alcanza en 30 días ⇒ hay que extender (y documentar).
- El OOS NO puede arrancar hasta que el Track A esté (si no, se repite el
  problema del rate limit y del log sobrescrito).

## Alternativas descartadas

- **A) Cortar por día.** Descartado: el grano correcto es el ciclo.
- **B) Comparar contra 0.** Descartado: el benchmark aleatorio es el control
  correcto.
- **C) t > 2,0.** Descartado: Harvey-Liu-Zhu (2016).
- **D) Decidir "a ojo" después de ver los datos.** Es exactamente lo que
  produjo la contradicción pre/post-deploy que hoy tenemos.

## Relación

- **ADR 009** congela el score ⇒ este protocolo mide sin tocarlo.
- **ADR 010** define la hipótesis.
- **ADR 011** (ventana) define cuántos ciclos hay por día ⇒ define N.
- **ADR 008** (p=NULL) ⇒ los datos de T₀ no arrastran la contaminación de H-22.
'''


ADRS = [
    ("008-test-de-regimen-no-puede-dejar-default.md", ADR008),
    ("009-congelar-macro-score-v2-y-bias-visual.md", ADR009),
    ("010-hipotesis-oos-rvd-mayor-03.md", ADR010),
    ("011-ventana-operativa-19h-render-free.md", ADR011),
    ("012-protocolo-oos-prospectivo-con-criterio-de-muerte.md", ADR012),
]


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════

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


class Buffer:
    def __init__(self):
        self.d = {}

    def get(self, ruta):
        if ruta in self.d:
            return self.d[ruta]
        return _leer_lineas(ruta)

    def set(self, ruta, lineas, crlf):
        self.d[ruta] = (lineas, crlf)


# ══════════════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════════════

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

    try:
        ag = (raiz / "AGENTS.md").read_text(encoding="utf-8")
        chk("AGENTS.md: seccion 8 (formula real del score v2)",
            "## 8. LA F" in ag and "RMULA REAL" in ag)
        chk("AGENTS.md: seccion 9 (el filtro de regimen no funciona)", "## 9. EL FILTRO DE REGIMEN NO FUNCIONA" in ag or "## 9. EL FILTRO DE RÉGIMEN NO FUNCIONA" in ag)
        chk("AGENTS.md: seccion 10 (afirmaciones prohibidas)", "AFIRMACIONES PROHIBIDAS" in ag)
        chk("AGENTS.md: seccion 11 (protocolo OOS)", "PROTOCOLO OOS" in ag)
        chk("AGENTS.md: la regla de no mezclar tareas sigue", "No mezcles tareas" in ag)
        chk("AGENTS.md: la regla de ritmo sigue", "Ritmo: 1 a 4 comandos por turno" in ag)
        chk("AGENTS.md: NO se duplico el bloque (marker unico)",
            ag.count(MARKER) == 1)
        chk("AGENTS.md: apunta a docs/RELEVO_IA.md", "RELEVO_IA.md" in ag)
    except Exception as exc:
        chk(f"AGENTS.md: no se pudo leer ({exc})", False)

    try:
        es = (raiz / "ESTADO.md").read_text(encoding="utf-8")
        chk("ESTADO.md: H-9 cerrado", "H-9 CERRADO" in es)
        chk("ESTADO.md: H-22 documentado", "H-22" in es)
        chk("ESTADO.md: H-21 documentado", "H-21" in es)
        chk("ESTADO.md: zona horaria Caracas", "CARACAS" in es)
        chk("ESTADO.md: proximo paso = Track A", "TRACK A" in es.upper())
        chk("ESTADO.md: sin dobles barras en rutas", "\\\\" not in es)
    except Exception as exc:
        chk(f"ESTADO.md: no se pudo leer ({exc})", False)

    try:
        ho = (raiz / "HANDOFF.md").read_text(encoding="utf-8")
        chk("HANDOFF.md: sesion 5", "Sesión     : 5" in ho or "Sesion     : 5" in ho)
        chk("HANDOFF.md: apunta a RELEVO_IA.md", "RELEVO_IA.md" in ho)
        chk("HANDOFF.md: trampas documentadas", "mojibake" in ho)
    except Exception as exc:
        chk(f"HANDOFF.md: no se pudo leer ({exc})", False)

    try:
        pe = (raiz / "docs" / "PENDIENTES.md").read_text(encoding="utf-8")
        chk("PENDIENTES.md: Track A", "TRACK A" in pe.upper())
        chk("PENDIENTES.md: Track B", "TRACK B" in pe.upper())
        chk("PENDIENTES.md: Track C", "TRACK C" in pe.upper())
        chk("PENDIENTES.md: H-9 cerrado con evidencia", "H-9 CERRADO" in pe)
        chk("PENDIENTES.md: default de resolucion [4, 24]", "[4, 24]" in pe)
        chk("PENDIENTES.md: H-22 (ADF falla 71%)", "71%" in pe)
        chk("PENDIENTES.md: sin dobles barras en rutas", "\\\\" not in pe)
    except Exception as exc:
        chk(f"PENDIENTES.md: no se pudo leer ({exc})", False)

    for nombre, cuerpo in ADRS:
        f = raiz / "decisiones" / nombre
        ok = f.exists() and "**Estado:**" in f.read_text(encoding="utf-8")
        chk(f"decisiones/{nombre[:40]}...", ok)

    if not (raiz / "docs" / "RELEVO_IA.md").exists():
        p(f"  {C['y']}AVISO{C['r']} docs/RELEVO_IA.md no esta todavia "
          f"(descargalo a docs\\) — no es un fallo")

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


# ══════════════════════════════════════════════════════════════════════════
#  APLICAR / DESHACER
# ══════════════════════════════════════════════════════════════════════════

def aplicar(simular: bool) -> int:
    hdr("actualizar_gobierno_h22.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    hdr("  1 · ARCHIVOS DE GOBIERNO")
    buf = Buffer()

    # ---- AGENTS.md : PARCHE ADITIVO idempotente ----
    ag = RAIZ / "AGENTS.md"
    if not ag.exists():
        p(f"  {C['R']}XX{C['r']} AGENTS.md no existe")
        return 1
    lineas, crlf = buf.get(ag)
    texto = "\n".join(lineas)
    if MARKER in texto:
        p(f"  {C['y']}·{C['r']} AGENTS.md: el bloque H-22 ya esta "
          f"(no se duplica)")
    else:
        lineas = lineas + AGENTS_AGREGADO.strip("\n").split("\n")
        buf.set(ag, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} AGENTS.md: +3 secciones (8 formula, "
          f"9 regimen, 10 lista negativa, 11 OOS)")

    # ---- reescrituras completas ----
    for rel, contenido in (
        ("ESTADO.md", ESTADO_NUEVO),
        ("HANDOFF.md", HANDOFF_NUEVO),
        (os.path.join("docs", "PENDIENTES.md"), PENDIENTES_NUEVO),
    ):
        ruta = RAIZ / rel
        if not ruta.exists():
            p(f"  {C['y']}·{C['r']} {rel}: no existe, se crea")
        lineas = contenido.rstrip("\n").split("\n")
        crlf = True
        if ruta.exists():
            _, crlf = _leer_lineas(ruta)
        buf.set(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {rel}: reescrito")

    # ---- ADRs nuevos ----
    for nombre, cuerpo in ADRS:
        ruta = RAIZ / "decisiones" / nombre
        if ruta.exists():
            p(f"  {C['y']}·{C['r']} decisiones/{nombre}: ya existe, NO se toca")
            continue
        buf.set(ruta, cuerpo.rstrip("\n").split("\n"), True)
        p(f"  {C['g']}OK{C['r']} decisiones/{nombre}: nuevo")

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\actualizar_gobierno_h22.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (un .bak por archivo)")
    for ruta, (lineas, crlf) in buf.d.items():
        if ruta.exists():
            bak = ruta.with_suffix(ruta.suffix + ".bak")
            shutil.copy2(ruta, bak)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        _escribir_lineas(ruta, lineas, crlf)
        try:
            rel = ruta.relative_to(RAIZ)
        except ValueError:
            rel = ruta
        p(f"  {C['g']}OK{C['r']} {rel}")

    hdr("  3 · VERIFICACION")
    rc = _self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\actualizar_gobierno_h22.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Gobierno H-22 aplicado.{C['r']}")
    p(f"  {C['c']}Siguiente: python verificar.py + commit{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    rels = ["AGENTS.md", "ESTADO.md", "HANDOFF.md",
            os.path.join("docs", "PENDIENTES.md")]
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
    for nombre, _ in ADRS:
        f = RAIZ / "decisiones" / nombre
        bak = RAIZ / "decisiones" / (nombre + ".bak")
        if bak.exists():
            shutil.copy2(bak, f)
            p(f"  {C['g']}OK{C['r']} restaurado: decisiones/{nombre}")
            n += 1
        elif f.exists():
            f.unlink()
            p(f"  {C['g']}OK{C['r']} eliminado: decisiones/{nombre} (era nuevo)")
            n += 1
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gobierno H-22 (H-9 cerrado, H-22, ADR 008-012, RELEVO_IA)")
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
