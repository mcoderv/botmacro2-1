#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
actualizar_gobierno_h23.py  -  MACRO2.1

Ronda del 27/10: una IA nueva adoptó el proyecto desde el repo y encontró 5
contradicciones en el gobierno que no se habían visto. Este script:

  AGENTS.md   PARCHE por 3 anclas EXACTAS (las 3 las escribimos el 26/10):
              (a) §8.1  -> aviso de que §5.1.c está OBSOLETA
              (b) §11.1 -> corrige E1 (la ventana real es 08:00-17:00)
              (c) + §13 -> los 5 hallazgos de la ronda + H-20 crítico
              (d) banner antes de §5.1.c (con fallback: si no se encuentra
                  la ancla, escribe docs/REPARAR_AGENTS.md con el texto exacto)
  ESTADO.md   REESCRITO
  docs/PROMPT_DIAGNOSTICO_C0_C4.md   NUEVO (el prompt para la IA que audita
              el pipeline completo de C0 a C4)

  NO toca: docs/INFORME_MACRO2.1.md, verificar.py, el codigo del pipeline,
  produccion. NO arregla los bugs E1-E5: los documenta.

Idempotente. .bak + --deshacer + self-test.

USO
  python fixes\\actualizar_gobierno_h23.py --simular     (default)
  python fixes\\actualizar_gobierno_h23.py --aplicar
  python fixes\\actualizar_gobierno_h23.py --deshacer
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


MARKER13 = "<!-- H-23:RODA-IA-NUEVA -->"
MARKER81 = "<!-- H-23:OBSOLETA-5-1-C -->"


# ══════════════════════════════════════════════════════════════════════════
#  1 · AGENTS.md  -  PARCHES
# ══════════════════════════════════════════════════════════════════════════

# ── (a) §8.1 : ancla EXACTA (escrita el 26/10) ───────────────────────────
ANCLA_81_VIEJO = """### 8.1 Semántica del ADF (error histórico, ya corregido)

`p_value_adf < 0.05` significa **ESTACIONARIO**, NO momentum.
La rama momentum (p ≥ 0.05) se activa cuando la serie **NO** es estacionaria."""

ANCLA_81_NUEVO = """### 8.1 Semántica del ADF (error histórico, ya corregido)

> ⚠️ **Si llegaste desde §5.1.c: esa sección está OBSOLETA.** No reproduce la
> fórmula real (0/914) y su lectura de la rama momentum está invertida.
> **La §8 la reemplaza por completo. No uses §5.1.c para nada.**

`p_value_adf < 0.05` significa **ESTACIONARIO**, NO momentum.
La rama momentum (p ≥ 0.05) se activa cuando la serie **NO** es estacionaria."""

# ── (b) §11.1 : ancla EXACTA (escrita el 26/10) ──────────────────────────
ANCLA_E1_VIEJO = """- **E1** — mezcló **Caracas con UTC**. La ventana acordada es 04:00-16:00
  **Caracas (UTC−4)** (confirmado con 3 pares epoch↔fecha de la DB).
  Su conclusión "migrar a VPS por las 20:00" queda sin base…
  **PERO:** la franja de las 20:00 Caracas (HR 76%, n=25) está FUERA de la
  ventana 04:00-16:00, y la de las 08:00 (HR 7,1%, n=14) está DENTRO.
  ⇒ El recorte quita la mejor franja y conserva la peor ⇒ **ADR 011**."""

ANCLA_E1_NUEVO = """- **E1** — mezcló **Caracas con UTC**. La ventana operativa es **Caracas
  (UTC−4)** (confirmado con 3 pares epoch↔fecha de la DB).
  Su conclusión "migrar a VPS por las 20:00" queda sin base…
  **🔴 CORREGIDO EL 27/10:** la ventana **REAL** —la que el código ejecuta y la
  que miden los datos— es **08:00-17:00 Caracas**
  (`config/CONSOLIDADO/central_params.json` líneas 231-246; confirmado por H-10:
  674 de 674 señales pre-19/10 dentro de 08-17, las 9 fuera a las 17h).
  La ventana **04:00-16:00 nunca se aplicó** ⇒ la frase de este documento
  "la ventana acordada es 04:00-16:00" era **FALSA** y queda corregida.
  Y el argumento "el recorte quita la mejor franja" queda **invalidado**:
  las señales de 19:00-21:00 son las **fuera de ventana** (bug H-20), no una
  franja a capturar ⇒ **ADR 011 pierde su base.** Ver §13."""

# ── (c) §13 nueva al final ───────────────────────────────────────────────
SECCION_13 = r'''
<!-- H-23:RODA-IA-NUEVA -->
---

## 13. RONDA DEL 27/10 — UNA IA NUEVA ADOPTÓ EL PROYECTO Y ENCONTRÓ 5 BUGS

**Qué se hizo:** una IA sin contexto previo leyó **sólo** el repo
(`docs/RELEVO_IA.md` → `AGENTS.md` → `ESTADO.md` → `docs/PENDIENTES.md`) y
respondió un cuestionario de adopción. **Leyó todo bien**: las 8 afirmaciones
prohibidas textuales y con los números correctos, la pregunta del OOS
(`rvd` > 0,3), ρ = +0,119, 71% = 648/914, 25 ciclos, HR 0% / 85-89%, A1
primero, y el diseño del rate limit (caché con TTL, token bucket, backoff con
`Retry-After`). **No inventó un solo número** — declaró explícitamente lo que
no midió.

**⇒ El relevo funciona. Y la IA encontró 5 contradicciones que nosotros no
vimos.** Ése es el valor real de la prueba.

| # | Hallazgo de la IA | Estado |
|---|---|---|
| **E1** | La ventana tiene **3 valores**: este doc decía 04:00-16:00, ADR 011 propone 04:00-23:00, y **el JSON en disco dice 08:00-17:00** | 🔴 **REAL.** La real es **8-17**. La 4-16 nunca se aplicó |
| **E2** | 5 archivos vivos leen `data/vault_v2.db`, que **no existe** (la real es `vault_v2.1.db`): `scheduler.py:190`, `reporter.py:1012`, `report_validator.py:38`, `validar_gem_macro.py:26`, `test_telegram.py:34` | 🔴 **REAL** (es H-12, con más alcance) |
| **E3** | `AGENTS.md` §5.1.c contradice a §9 (la rama momentum) | 🔴 **REAL** — falla de un patch aditivo sin releer |
| **E4** | `ESTADO.md` declaraba un commit viejo | 🟡 Real, cosmético |
| **E5** | El commit `baf6985` decía "versionar diagnostico_h9 y h10_h18" y **no lo hizo** | ✅ Conocido: los excluye `diagnostico_*.py` |

### 13.1 Las 3 consecuencias que cambian el plan

**1) 🔴 H-20 SUBE A CRÍTICO.** El bug "16,2% de las señales se emiten fuera de
la ventana" (19:00-21:00) coincide **exactamente** con la franja de mayor HR
medido (20:00 → HR 76%, n=25). ⇒ **Si se arregla H-20, esas señales desaparecen
y con ellas puede caerse el único "edge" que se había medido.**
⇒ **El edge de las 20:00 puede ser un artefacto de un bug de scheduler.**
⇒ Esto hay que MEDIRLO (cruce hora × dentro/fuera de ventana) antes de tocar nada.

**2) ⛔ ADR 011 PIERDE SU BASE.** Proponía "ampliar a 04:00-23:00 para capturar
la franja de las 20:00" ⇒ eso sería **legalizar un bug**. ADR 011 queda
PROPUESTO pero **sin justificación** hasta el diagnóstico.

**3) 🔴 H-17 PARCIALMENTE TRABAJO SOBRE CÓDIGO MUERTO.** El resumen de
Telegram de la mañana (`scheduler.py:190`) lee una DB inexistente ⇒
`SELECT ... FROM senales_validadas` ⇒ "no such table" ⇒ el `try/except` lo
traga ⇒ **nunca se envió**. Por eso nadie notó el arreglo de H-17.
⇒ El pipeline C2→C4 **no** pasa por ahí ⇒ no está afectado.
⇒ `reporter.py`, `report_validator.py`, `validar_gem_macro.py` y
`test_telegram.py` leen la misma DB inexistente ⇒ sus reportes están vacíos.

### 13.2 La lección de método (auto-detectada por la IA)

**Un patch ADITIVO sobre un documento que no se releyó entero puede dejar
secciones que se contradicen.** El self-test verificaba que lo nuevo estuviera,
**no que no chocara con lo viejo**. ⇒ **Regla nueva: después de un patch
aditivo, releer el documento ENTERO y buscar contradicciones.**

### 13.3 El circuito que faltaba (detectado por la IA)

Entregar un `.py` ⇒ el usuario lo copia a `analisis/` ⇒ **nadie verifica que
quedó versionado**. Falló 2 veces (`diagnostico_h9.py`, `diagnostico_h10_h18.py`
caen en `diagnostico_*.py` del `.gitignore`, línea 34) y no se detectó hasta
que el `git add` falló. ⇒ **Falta un check en `verificar.py`** que detecte
`.py` en `analisis/`/`fixes/` que estén ignorados. **Pendiente.**

---

### 13.4 Las 3 reglas del diagnóstico (el aprendizaje de esta ronda)

**1. NINGUNA CORRECCIÓN SIN VALIDADOR.** El validador debe (a) ser ejecutable,
(b) tener un PASS/FAIL explícito, (c) **fallar con el código viejo** y (d) pasar
con el nuevo. Si no se puede escribir ese test, la corrección **no se aplica**:
se reporta como riesgo asumido.

**2. SI NO SABÉS ALGO, INVESTIGALO EN INTERNET** (fuente primaria) y decile al
usuario qué tiene que buscar, con el formato `PENDIENTE DE INVESTIGACIÓN`.
No inventes números, ni comportamiento de APIs, ni fuentes.

**3. NINGUNA AFIRMACIÓN DE LAS 8 PROHIBIDAS** (§10) puede repetirse.

---

## 14. EL SIGUIENTE TRABAJO NO ES CÓDIGO: ES EL DIAGNÓSTICO C0→C4

**Prompt listo:** `docs/PROMPT_DIAGNOSTICO_C0_C4.md`

Una IA debe auditar **celda por celda** (C0, C1/C1_5, C2, C2_5, C3, C3_5, C4,
scheduler, ventana, main) aplicando las **3 reglas de §13.4**.

**⇒ Antes de escribir código: presentá el diseño en el chat y esperá el "ok".**
'''


# ══════════════════════════════════════════════════════════════════════════
#  2 · ESTADO.md  -  REESCRITO
# ══════════════════════════════════════════════════════════════════════════

ESTADO_NUEVO = r'''# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~120 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-27
Commit      : baf6985 (gate con 13 ADRs) + commit de gobierno H-23
Repo        : botmacro2-1  (desarrollo, local, SIN Docker) | botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h) · zona horaria = CARACAS (UTC−4)
VENTANA     : 08:00-17:00 Caracas  ← la REAL (ver H-23 / E1)
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
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso · ahora valida los **13 ADRs**
- [x] **Sin Docker en 2.1** (ADR 003) — producción intacta
- [x] **H-9 CERRADO** — diagnóstico completo del `macro_score_v2` (5 scripts de análisis)
- [x] **Zona horaria resuelta** — la DB guarda hora local Caracas (UTC−4), 3 pares epoch↔fecha
- [x] **Segunda opinión** revisada; sus 3 errores corregidos (E1/E2/E3)
- [x] **Plan de reorientación** escrito (Track A / B / C) — `docs/RELEVO_IA.md` §10
- [x] **Gobierno H-22** — `AGENTS.md` §8-§12, `ESTADO.md`, `HANDOFF.md`, `PENDIENTES.md`, ADR 008-012
- [x] **Prueba de adopción (27/10)** — una IA sin contexto leyó el repo y entendió todo;
      **encontró 5 bugs del gobierno** (§13 de `AGENTS.md`)

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

**El score v2 NO tiene poder predictivo demostrado. NO-GO.**
ρ(ms2, pnl24) = **+0,119** dentro de RANGE. No separa nada.

| Hallazgo | Dato | Dónde |
|---|---|---|
| `macro_score_v2 = 0.0` exacto | **768 de 914** = 13/10–19/10 = **PRE-DEPLOY, NO es bug vigente** | `data_quality_emision`=OK en las 768 |
| Score v2 real | **146** = 19/10–23/10 (4 días) | |
| El filtro de régimen **NO corrió** | **648 de 914 (71%)** con `p=1.0` = el DEFAULT del `except` | C3 líneas 1901-1925 |
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

## 🔴 LOS 5 HALLAZGOS DE LA RONDA DEL 27/10 (los encontró una IA nueva)

| # | Qué | Gravedad |
|---|---|---|
| **E1** | **La ventana real es 08:00-17:00** (`central_params.json` 231-246), no 04:00-16:00. La 4-16 **nunca se aplicó** ⇒ el gobierno mentía | 🔴 Alta |
| **E2** | **5 archivos leen `data/vault_v2.db`, que no existe** (la real es `vault_v2.1.db`): `scheduler.py:190`, `reporter.py:1012`, `report_validator.py:38`, `validar_gem_macro.py:26`, `test_telegram.py:34` ⇒ leen una DB **vacía** ⇒ el resumen de Telegram de la mañana **nunca se envió** y los reportes salen vacíos. El pipeline C2→C4 **no** está afectado | 🔴 Media (H-12) |
| **E3** | `AGENTS.md` §5.1.c contradice a §9 ⇒ un patch aditivo dejó secciones viejas que chocan | 🔴 Media |
| **E4** | `ESTADO.md` declaraba un commit viejo | 🟡 Baja |
| **E5** | El commit `baf6985` decía "versionar diagnostico_h9 y h10_h18" y no lo hizo (los excluye `diagnostico_*.py`, `.gitignore` línea 34) | ✅ Conocido |

**⇒ ⭐⭐ CONSECUENCIA CRÍTICA: las señales de 19:00-21:00 (fuera de la
ventana 8-17, bug H-20) son **la franja con el HR más alto medido**
(20:00 → HR 76%, n=25). ⇒ Si se arregla H-20, **pueden desaparecer.**
⇒ **El "edge" puede ser un artefacto de un bug de scheduler.**
⇒ ⇒ **ADR 011 pierde su base** (proponía ampliar a 23:00 "para capturar" esa franja).
⇒ ⇒ **H-20 sube de "menor" a CRÍTICO.**

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | Backup de la DB solo en un disco | Hecho local, **falta Drive** | ❗ **PRIORIDAD #1 (manual)** |
| **H-20** | **16,2% de las señales se emiten FUERA de la ventana** (19-21h) | **Puede ser el "edge" medido ⇒ puede desaparecer al arreglarlo** | 🔴 **NUEVO —>#1 técnico** |
| **E2 / H-12** | 5 scripts leen `data/vault_v2.db` (no existe) | Reportes vacíos; el resumen de la mañana nunca se envió | 🔴 **NUEVO** |
| **E1** | El gobierno dice una ventana y el código ejecuta otra | La ventana "acordada" nunca se aplicó | 🔴 **NUEVO** |
| **E3** | `AGENTS.md` §5.1.c vs §9 | Contradicción en el documento que gobierna | 🔴 **NUEVO** |
| **H-22** | El test de régimen falla en el 71% y deja `p=1.0` | La muestra de "señales con score" está **seleccionada por éxito del test** | 🔴 **>#1 técnico** |
| **H-9** | `macro_score_v2` sin poder predictivo demostrado | NO-GO cerrado | ✅ **CERRADO (evidencia)** |
| **H-10** | Las etiquetas no son comparables entre sí (19/10 = 1er deploy) | Confound temporal | ✅ RESUELTO |
| **H-21** | `en_ventana()` trabaja con **hora entera** | `VENTANA_FIN` corta el ciclo de la hora final; no se puede expresar 03:40/17:20 | 🔴 Bloquea H-18/H-13 |
| **H-18** | `RESOLUTION_WINDOWS_HOURS=[4,8,24]` hardcoded | Sin cortes intermedios ⇒ no se mide timing temprano | ⬜ PROPUESTO (ADR 007) — default **[4, 24]** |
| **H-13** | `senales_metricas` no agrega por `calidad_senal_v2`; escala legacy 14/8/4 muerta | Métricas por etiqueta salen de una escala inalcanzable | ❗ Pendiente |
| **H-14** | `_get_price_at_time` puede tomar precio posterior | 52% cambian de PnL, sesgo neto <1% | ❗ Pendiente |
| **H-16** | "ganancia" con 2 definiciones | Impacto <1% en PF | ⏸️ Medido y diferido (ADR 004) |
| **H-11** | `main.py` corre 8 celdas, no 9 | Cosmético, el mapa de AGENTS.md miente | ❗ Nuevo |
| **H-2** | Dos ADF distintos (niveles C3_5 vs residuales FFD C3) | El régimen no mueve el conmutador | ❗ Pendiente |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo (≡ k=0,044σ) | Sesga HR (no el PF) | ❗ Pendiente → ADR 001 |
| **H-6** | `SCORE_ALTA=14`/`MEDIA=8` con `macro_score` máx 6 | Código muerto | ❗ Pendiente |
| **H-8** | 6 cripto pierden (BTC PF 0,30) mientras TradFi gana | Estructural | ❗ En investigación |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | ❗ Pendiente |
| — | Rate limit de Hyperliquid | 1344 req/min > 1200 ⇒ **429**; ritmo 25-30 → **4-8 corridas/día** | 🔴 **Track A / A1** |
| — | Logs sobrescritos | 39 líneas ⇒ el motivo de los 648 fallos del ADF se perdió | 🔴 **Track A / A4** |
| — | `cycle_id` roto | join señales↔snapshot = **0/914** ⇒ auditoría rota | 🔴 **Track A / A2** |
| — | `data_quality` siempre NULL | El dict real es `zonas["data_quality"]["estado"]` | 🔴 **Track A / A3** |
| — | `duration_seconds` no es duración | No se puede medir el costo por ciclo | 🔴 **Track A / A5** |
| — | `_classify_signal_quality_v2` usa `abs()` | Etiqueta invertida (RUIDO 71,4% > FUERTE 64,7%) | ⬜ **Track B / B3** |
| — | `score_desglose["cvd_crud"]` mal nombrado | Ya produjo un error de análisis externo | ⬜ **Track A / A9** |
| — | `verificar.py` no valida que los `.py` entregados queden versionados | Ya falló 2 veces | ⬜ **Nuevo** |
| — | `verificar.py` no chequea los ADR 007-012 | Gate parcial | ✅ Resuelto (27/10) |

---

## 🔒 ANTES DE CUALQUIER COSA

**Subí `C:\Users\MD\Desktop\MACRO2.1_BACKUP\` a Drive.** El backup local ya
está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`. Es lo único del
proyecto que **no** se recupera de GitHub. **`data/` está gitignored.**

---

## 🎯 SIGUIENTE PASO

**1 · El diagnóstico C0→C4.** Prompt listo en
`docs/PROMPT_DIAGNOSTICO_C0_C4.md`. Lo ejecuta una IA (o vos con
`docs/RELEVO_IA.md` como contexto). Reglas: **ninguna corrección sin
validador**, **si no sabés, investigá en internet y decile al usuario qué
buscar**, y **ninguna de las 8 afirmaciones prohibidas**.

**2 · Medir el cruce hora × dentro/fuera de la ventana (H-20).**
Es lo que decide si el "edge" de las 20:00 es real o es el bug H-20.
Cae dentro del diagnóstico.

**3 · Track A (eficiencia), en este orden** — el diseño de A1 ya está hecho
(cache con TTL ≥900s · un solo fetch por ciclo compartido · token bucket a
~600/min con backoff y `Retry-After` · WS con `HL_WS_URL` ya presente en
CONFIG · auditar timeframes) y su métrica de no-regresión es:
**requests/min p95 < 600 + la MISMA distribución de señales por activo/hora
que antes (NO HR/PF: las etiquetas cambian con el tiempo).**
   1. **A1** rate limit → 2. **A2** `cycle_id` → 3. **A3** `data_quality` →
   4. **A0** test de régimen → 5. **A4/A5/A6** → 6. **A9** → 7. **H-21** →
   8. **H-18** → 9. **H-13**

**4 · Track C (protocolo OOS) se escribe ANTES de T₀** (ADR 012).
**T₀ = fecha del deploy con el Track A listo.**
**5 · Track B (B1/B3) sólo en T₀, prospectivo. B4 (limpiar el score) sólo
DESPUÉS del veredicto.**

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
- **Después de un patch aditivo, releer el documento ENTERO** (lección del 27/10).
'''


# ══════════════════════════════════════════════════════════════════════════
#  3 · docs/PROMPT_DIAGNOSTICO_C0_C4.md  -  NUEVO
# ══════════════════════════════════════════════════════════════════════════

PROMPT_DIAGNOSTICO = r'''# PROMPT — DIAGNÓSTICO COMPLETO DEL PIPELINE C0→C4

> **Qué es esto:** el brief de trabajo para auditar el proyecto MACRO2.1
> celda por celda, de C0 a C4, con correcciones **validadas**.
>
> **Cómo usarlo:** pegá el bloque "EL BRIEF" de abajo (desde `## EL BRIEF`
> hasta el final) como primer mensaje de una sesión nueva de Cline, con la
> raíz del proyecto como working directory.
>
> **Fecha:** 2026-10-27 · **Sesión de referencia:** 5 (ver `HANDOFF.md`)

---

## EL BRIEF

Sos un ingeniero de software que audita un proyecto existente. No sos el
autor: **auditas, medís y corregís lo que encuentres, con pruebas.**

### 0. El proyecto en 30 segundos

**MACRO2.1 es un bot de PREDICCIÓN y VALIDACIÓN de tendencia macro para
Hyperliquid. NO es un bot de trading.** No tiene posiciones, SL ni TP: emite
una señal direccional (LONG/SHORT) con un score y después **valida** si el
precio hizo lo esperado (PnL a 4h/8h/24h, MAE/MFE, timing).
GEM (Gemini) produce las señales; MACRO2.1 las audita.

Stack: Python + SQLite + Hyperliquid API. Corre **local en Windows** (CMD) y
en **Render free** (Linux). Producción = repo `botmacro` = **CONGELADA, no
tocar**. Desarrollo = repo `botmacro2-1` = este.

**El pipeline:**
| Celda | Qué hace |
|---|---|
| C0 | Config / params / snapshot de mercado → `backups_v2.1` |
| C1 / C1_5 | Parámetros centralizados (`CENTRAL_PARAMS`) → `central_params.json` |
| C2 | Bóveda: migraciones de schema + auto-restore → `vault_v2.1.db` (23 tablas) |
| C2_5 | Contexto (⚠️ import con fallback silencioso) |
| C3 | Macro engine: ADF/FFD, POC/caja/FVG, score v2 → `macro_audit_log`, `gem_macro_snapshot` |
| C3_5 | Regime engine → `regime_state`, `regime_features` |
| C4 | Validador: emite, captura precios, resuelve a 4/8/24h → `senales_validadas`, `senales_metricas`, `price_snapshots`, `c4_execution_log` |
| `scheduler.py` | El loop de Render (orquesta + Telegram) |
| `ventana.py` | `en_ventana()` — la ventana operativa |

**Estado de la DB:** 914 señales, 902 resueltas a 24h. **Zona horaria: hora
local Caracas (UTC−4).**

### 1. Antes de tocar NADA, leé esto

En este orden (es autocontenido, no vas a necesitar contexto de nadie):

1. `docs/RELEVO_IA.md` — **el brief completo del proyecto** (18 secciones).
   Es la fuente de verdad del diagnóstico anterior: hallazgos H-1→H-22, la
   fórmula real del score, las 8 afirmaciones prohibidas y el plan.
2. `AGENTS.md` — las reglas + §8 (fórmula real) + §10 (lista negativa) +
   §11 (protocolo OOS) + §13 (la ronda del 27/10).
3. `ESTADO.md` — dónde estamos y qué está roto.
4. `docs/PENDIENTES.md` — el tracking oficial.
5. `decisiones/` — los 13 ADR. Cada corrección que propongas debe ser
   coherente con el ADR vigente; si lo contradice, **decilo y proponé el ADR
   nuevo** (no lo ignores).
6. `verificar.py` — el gate. Entendé qué chequea antes de tocarlo.

### 2. Las reglas de la casa (no negociables)

- **Producción (`botmacro`) está CONGELADA. No la tocas.**
- **Si algo funciona, no se toca sin un ADR.**
- **Nunca creás ni editás un archivo sin que el usuario diga "ok".** Presentás
  el diseño en el chat y esperás. Esto aplica a TODO: scripts, parches,
  docs, migraciones.
- **CMD.exe únicamente** (el usuario trabaja en Windows CMD): sin PowerShell,
  sin `curl`/`wget` de unix, sin `&&`, sin `;`.
- **1 a 4 comandos por turno.** Independientes o de solo lectura → juntos.
  Dependientes o que pueden fallar → de a uno, con **output esperado** y
  **"pegá la salida"**.
- **No mezcles tareas:** si estás validando un fix, ese es el ÚNICO foco del
  turno. Cerralo (self-test + commit) antes de abrir otra cosa.
- **Después de cada cambio: `python verificar.py`.** Si falla, no avanzás.
- **Un commit por cambio**, con `python git/guardar.py "mensaje"`.
- **Nunca comparás HR/PF entre etiquetas o ventanas sin cortar por día.**
  Y el grano correcto es el **CICLO**, no el día.
- Los parches siguen el patrón del proyecto: `.bak` + `--deshacer` +
  **self-test** que falla si el cambio no quedó bien.

### 3. ⭐ REGLA 1 — NINGUNA CORRECCIÓN SIN VALIDADOR

**Este es el punto central del encargo. No lo saltees.**

Una "corrección" sin validador **no se aplica**. Se reporta y se explica por
qué no se pudo validadar.

**Qué es un validador aceptable:**

| ✅ Aceptable | ❌ NO aceptable |
|---|---|
| Un test que **falla con el código viejo** y **pasa con el nuevo** | "Revisé el código y parece correcto" |
| Un script que compara el estado ANTES vs DESPUÉS (con y sin el fix) sobre la DB real | "La documentación dice que debería ser así" |
| Un `PRAGMA table_info` / `PRAGMA integrity_check` que demuestra el schema esperado | "Es un patrón conocido" |
| `verificar.py` extendido con un check nuevo que falla antes del fix | Un print de un valor sin comparar contra nada |
| Un contador A/B sobre la DB real | Razonamiento theoretical |
| Un test de la API real (request real, respuesta real) contra un mock | Un test que mockea el comportamiento a verificar |

**El validador tiene que cumplir 4 cosas:**
1. **Ejecutable** — se corre con un comando y devuelve un resultado.
2. **PASS/FAIL explícito** — no "parece que anda". Un exit code o un `OK`/`XX`.
3. **Discriminante** — **demonstra el bug ANTES** de aplicar el fix. Si el
   validador pasa con el código viejo, **no sirve**: no prueba nada.
4. **Repetible** — se puede volver a correr después y sigue diciendo lo mismo.

**Si no podés escribir un validador discriminante para una corrección, NO la
aplicás.** La reportás como "riesgo asumido" con el motivo. Eso es una
respuesta profesional, no una falla.

**Cada corrección que entregues va con:**
- el validador (código),
- **la salida del validador ANTES del fix** (que debe fallar y por qué),
- **la salida DESPUÉS del fix** (que debe pasar),
- y el `.bak` + `--deshacer` para poder revertir.

**Trampa conocida del proyecto:** el self-test de un patch verifica que lo
*nuevo* esté presente, **no que no rompa lo viejo**. Un parche aditivo sobre
un documento que no se releyó entero dejó dos secciones contradictorias
(`AGENTS.md` §5.1.c vs §9, ambos escritos por nosotros). **Después de cada
patch, releé el archivo ENTERO y buscá contradicciones.**

### 4. ⭐ REGLA 2 — SI NO SABÉS, INVESTIGALO EN INTERNET

**No inventés.** Ni un número, ni el comportamiento de una API, ni una fórmula.

Cuando te falte un dato para poder corregir algo:

1. **Buscalo en la fuente primaria** (docs oficiales, spec, RFC, paper, código
   fuente del proyecto). Si hay que usar búsqueda web, buscá la fuente
   primaria, no un blog.
2. **Registralo** con este formato exacto:

```
### PENDIENTE DE INVESTIGACIÓN — <número>
Pregunta      : <qué no sabés, en una línea>
Por qué importa: <qué corrección o decisión depende de esto>
Fuente a mirar: <URL o nombre del doc oficial>
Qué buscar    : <términos exactos / endpoint / parámetro>
Qué decidirá  : <qué harías con cada respuesta posible>
```

3. **Decíselo al usuario al final del informe**, en una sección
   **"PENDIENTE DE INVESTIGACIÓN (para el usuario)"**. El usuario las busca.
   Mientras tanto, **no avanzás con la corrección que depende de eso** (podés
   avanzar con las demás).

**Casos donde esto aplica siempre:**
- Cómo se comporta un endpoint de Hyperliquid (rate limits, pesos, límites de
  velas, WS) ⇒ **docs oficiales de Hyperliquid**.
- Qué significa un p-value, un test, un criterio de significancia ⇒ **paper
  original o libro**, no Wikipedia.
- Cómo se comporta una fórmula de un paper ⇒ **el paper**.
- Cualquier versión de una librería ⇒ **su changelog/release notes**.

**Ejemplo de cómo se aplicó en este proyecto (27/10):** una IA externa usó
`arXiv:2607.09230` (Jeon, U. Korea, 10-jul-2026) diciendo que validaba el
diseño del bot. Al verificarlo, el paper trata transiciones de estado
L2→1-5 min, **no** precios a 4h-24h. Su tesis real ("state-first") sí
respalda el NO-GO estructuralmente, pero **el uso que se le dio estaba mal**.
⇒ Ese tipo de error se evita verificando la fuente primaria.

### 5. ⭐ REGLA 3 — LAS 8 AFIRMACIONES PROHIBIDAS

**Si una de estas aparece en tu informe, está mal.** Están en `AGENTS.md` §10.
No las repitas, no las contradigas y no las des por buenas:

1. "El `macro_score_v2` tiene poder predictivo." (ρ = +0,119 · NO-GO)
2. "El sesgo multi-TF no funciona." (N/A sólo 5,6% / 5,8% / 0% ⇒ funciona)
3. "El score se calcula en régimen estacionario fuerte." (se calcula donde el
   test **no falló**; en el 71% no corrió)
4. "El score v2 está contaminado por la escala del volumen." (ya normalizado)
5. "El término `d` es degenerado / hay que eliminarlo." (es divergencia real)
6. "El score v2 es una regresión por usar `cvd_crud` en vez de `rvd_ultimo`."
   (`rs` ya es un ordinal de `rvd`)
7. "MACRO2.1 es un bot de trading." (es predictor + validador)
8. "Se puede comparar HR/PF entre etiquetas o ventanas sin cortar por día."
   (el grano correcto es el ciclo)

### 6. Qué auditar, celda por celda

Para **cada** celda de la lista: `C0`, `C1`, `C1_5`, `C2`, `C2_5`, `C3`, `C3_5`,
`C4`, `scheduler.py`, `ventana.py`, `main.py`.

**Para cada una, entrega:**

1. **Qué hace realmente** — verificado en el código, con **nº de línea**.
   No lo que dice la doc; lo que hace el código.
2. **Qué escribe y dónde** — tabla, columnas, archivos.
3. **Fallos encontrados** — con **evidencia**: cita de línea, o salida de un
   comando, o un número medido sobre la DB.
4. **Severidad** — `P0` (rompe algo o pierde datos) / `P1` (degrada o
   invalida una medición) / `P2` (higiene o deuda).
5. **Corrección propuesta** + **su validador** (Regla 1) + el impacto de no
   corregirla.

**Temas que ya sabemos que están mal — verificálos, no los repitas de memoria:**
`vault_v2.db` vs `vault_v2.1.db` (5 archivos) · la ventana real 8-17 vs la que
dice el gobierno · H-20 (16,2% de señales fuera de la ventana) · el test de
régimen que falla en el 71% · `cycle_id` en 0/914 · `data_quality` siempre NULL ·
logs sobrescritos · rate limit 1344 vs 1200 req/min · `en_ventana()` con hora
entera · los 5 imports con fallback silencioso · `main.py` con 8 celdas y no 9.

**Y buscá los que NO sabemos que están mal — ese es el valor de este encargo.**

### 7. Sobre la base de datos

- `data/vault_v2.1.db` — **leer sí, escribir NO.** Es la única fuente de verdad
  y `data/` está gitignored (no está en GitHub ⇒ **hacé un backup antes de
  tocar nada**, y recordá al usuario que lo suba a Drive).
- Para medir, **copiá la DB a un scratch** y trabajá sobre la copia, o abrila
  en modo read-only. **Nunca** `UPDATE`/`DELETE`/`DROP` sobre la original.
- Toda medición debe decir **cómo se midió** (query o script) y **con qué n**.

### 8. Entregables

**A · Un informe** en Markdown, una sección por celda, con los 5 puntos de §6.
Guardalo donde el usuario te lo pida (por defecto `analisis/` o `docs/`).

**B · Una lista de correcciones** al final, ordenada por severidad, con:
| # | Corrección | Archivos | Severidad | Validador | ¿Aplicable ya? |

**C · Una sección "PENDIENTE DE INVESTIGACIÓN (para el usuario)"** con lo que
tenés que buscar (Regla 2).

**D · Tu veredicto de una línea:** ¿el pipeline está en condiciones de
sostener un OOS de 30 días, sí o no? Y si no, **qué falta**.

### 9. Lo primero que hacés

**No escribas código todavía.** En el **primer turno**:

1. Leé los 6 documentos de §1.
2. Corré `python verificar.py` y pegá la salida.
3. Corré `git log --oneline -10` y pegá la salida.
4. Entregame un **plan de auditoría**: en qué orden vas a atacar las celdas,
   qué medirías primero, y qué contradicciones ya te aparecen entre lo que
   dice la doc y lo que hace el código.
5. Preguntame lo que falte para arrancar.

**Después de ese plan y mi "ok", recién ahí proponés correcciones, una por
turno, con su validador.**

### 10. Lo que NO hacés

- No tocás la producción ni el repo `botmacro`.
- No reescribís el `macro_score_v2` (congelado, ADR 009) ni su rama.
- No tocás `docs/INFORME_MACRO2.1.md` (es la spec de referencia).
- No creás ADR sin que lo pidamos.
- No aplicás una corrección sin validador discriminante.
- No inventás números, ni fuentes, ni comportamientos de APIs.
- No reformateás código que funciona (el diff tiene que ser **mínimo y
  justificado**).
- No hacés las 11 correcciones en un turno: **una por turno**, con su
  self-test y su commit.
'''


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


def _texto(lineas):
    return "\n".join(lineas)


def _reemplazar_bloque(lineas, viejo, nuevo):
    """Viejo es un bloque de texto. Devuelve lineas nuevas o None."""
    txt = _texto(lineas)
    if viejo not in txt:
        return None
    nt = txt.replace(viejo, nuevo, 1)
    return nt.split("\n")


def _insertar_antes_de_linea(lineas, needle, bloque, excluir=()):
    """Inserta `bloque` antes de la 1ra linea que contenga `needle`.
    Devuelve (lineas_nuevas, indice) o (None, -1)."""
    for i, l in enumerate(lineas):
        s = l.strip()
        if needle in s and not any(x in s for x in excluir):
            nuevo = bloque.rstrip("\n").split("\n") + lineas[i:]
            return nuevo, i
    return None, -1


REPARAR_AGENTS = r'''# REPARAR `AGENTS.md` — ancla §5.1.c no encontrada

El script `actualizar_gobierno_h23.py` **no pudo** insertar el aviso de
"§5.1.c está OBSOLETA" porque no encontró la línea de la sección §5.1.c con
una ancla ASCII confiable.

**Todo lo demás se aplicó normalmente.** Para terminar este punto:

1. Abrí `AGENTS.md` y buscá la sección **5.1** (la que describe la fórmula
   del score / la rama estacionaria vs momentum).
2. Pegá este bloque **justo arriba** de esa sección:

```markdown
> ⚠️ **ESTA SECCIÓN ESTÁ OBSOLETA (27/10).** No reproduce la fórmula real del
> `macro_score_v2` (0/914) y su lectura de la rama momentum está invertida.
> **La §8 de este mismo archivo la reemplaza por completo.**
> No uses esta sección para nada. El detalle del hallazgo está en la §13.
```

3. Guardá y corré `python verificar.py`.

**Por qué no lo hizo el script:** la línea de la §5.1.c en este archivo tiene
acentos, y en la consola del usuario (ANSI chino) los acentos salen como
mojibake ⇒ no se puede usar como ancla. El script prefirió **no tocar** una
línea que no podía identificar con certeza, antes que escribir en el lugar
equivocado.
'''


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
        chk("AGENTS.md: §8.1 avisa que §5.1.c esta obsoleta",
            "está OBSOLETA" in ag and "5.1.c" in ag)
        chk("AGENTS.md: §11.1 corrige E1 (ventana real 08:00-17:00)",
            "08:00-17:00" in ag)
        chk("AGENTS.md: ya no dice 'la ventana acordada es 04:00-16:00'",
            "La ventana acordada es 04:00-16:00" not in ag)
        chk("AGENTS.md: §13 presente (ronda IA nueva)", "## 13. RONDA DEL 27/10" in ag)
        chk("AGENTS.md: §13 menciona H-20 critico", "H-20 SUBE A CRÍTICO" in ag)
        chk("AGENTS.md: §13 menciona que ADR 011 pierde su base",
            "ADR 011 PIERDE SU BASE" in ag)
        chk("AGENTS.md: §13 registra los 5 hallazgos E1-E5",
            all(x in ag for x in ["**E1**", "**E2**", "**E3**", "**E4**", "**E5**"]))
        chk("AGENTS.md: §13.4 tiene la regla del validador",
            "NINGUNA CORRECCIÓN SIN VALIDADOR" in ag)
        chk("AGENTS.md: §13.4 tiene la regla de investigar en internet",
            "INVESTIGALO EN INTERNET" in ag)
        chk("AGENTS.md: §14 apunta al prompt de diagnostico",
            "PROMPT_DIAGNOSTICO_C0_C4.md" in ag)
        chk("AGENTS.md: seccion 13 no duplicada",
            ag.count("<!-- H-23:RODA-IA-NUEVA -->") == 1)
        chk("AGENTS.md: §5.1.c tiene aviso o hay REPARAR_AGENTS.md",
            ("<!-- H-23:OBSOLETA-5-1-C -->" in ag)
            or (raiz / "docs" / "REPARAR_AGENTS.md").exists())
    except Exception as exc:
        chk(f"AGENTS.md: no se pudo leer ({exc})", False)

    try:
        es = (raiz / "ESTADO.md").read_text(encoding="utf-8")
        chk("ESTADO.md: ventana real 08:00-17:00", "08:00-17:00" in es)
        chk("ESTADO.md: los 5 hallazgos de la ronda", "E1" in es and "E5" in es)
        chk("ESTADO.md: H-20 marcado como critico", "CRÍTICO" in es.upper())
        chk("ESTADO.md: siguiente paso = diagnostico C0-C4",
            "PROMPT_DIAGNOSTICO_C0_C4.md" in es)
        chk("ESTADO.md: la leccion del patch aditivo",
            "releer el documento ENTERO" in es)
        chk("ESTADO.md: sin dobles barras en rutas", "\\\\" not in es)
    except Exception as exc:
        chk(f"ESTADO.md: no se pudo leer ({exc})", False)

    try:
        pr = (raiz / "docs" / "PROMPT_DIAGNOSTICO_C0_C4.md").read_text(encoding="utf-8")
        chk("PROMPT: existe y tiene el brief", "## EL BRIEF" in pr)
        chk("PROMPT: regla del validador", "NINGUNA CORRECCIÓN SIN VALIDADOR" in pr)
        chk("PROMPT: validador discriminante (falla antes / pasa despues)",
            "falla con el código viejo" in pr and "pasa con el nuevo" in pr)
        chk("PROMPT: regla de investigar en internet",
            "INVESTIGALO EN INTERNET" in pr)
        chk("PROMPT: bloque PENDIENTE DE INVESTIGACION",
            "PENDIENTE DE INVESTIGACIÓN" in pr)
        chk("PROMPT: las 8 afirmaciones prohibidas", "8 AFIRMACIONES PROHIBIDAS" in pr)
        chk("PROMPT: audita celda por celda", "C0" in pr and "C3_5" in pr and "C4" in pr)
        chk("PROMPT: DB solo lectura", "leer sí, escribir NO" in pr)
        chk("PROMPT: pide plan primero, no codigo",
            "No escribas código todavía" in pr)
    except Exception as exc:
        chk(f"PROMPT: no se pudo leer ({exc})", False)

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
    hdr("actualizar_gobierno_h23.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    hdr("  1 · ARCHIVOS")

    ag = RAIZ / "AGENTS.md"
    if not ag.exists():
        p(f"  {C['R']}XX{C['r']} AGENTS.md no existe")
        return 1
    lineas, crlf = _leer_lineas(ag)
    txt = _texto(lineas)
    cambios = []

    # (a) §8.1
    if "está OBSOLETA" in txt and "Si llegaste desde §5.1.c" in txt:
        cambios.append("§8.1 ya tiene el aviso (no se toca)")
    else:
        r = _reemplazar_bloque(lineas, ANCLA_81_VIEJO, ANCLA_81_NUEVO)
        if r is None:
            p(f"  {C['y']}·{C['r']} AGENTS.md: no se encontro el ancla de §8.1 (se deja como esta)")
        else:
            lineas = r
            cambios.append("AGENTS.md §8.1: aviso de que §5.1.c esta obsoleta")

    # (b) §11.1 (E1)
    txt = _texto(lineas)
    if "La ventana **REAL**" in txt:
        cambios.append("§11.1 ya corregido (no se toca)")
    else:
        r = _reemplazar_bloque(lineas, ANCLA_E1_VIEJO, ANCLA_E1_NUEVO)
        if r is None:
            p(f"  {C['y']}·{C['r']} AGENTS.md: no se encontro el ancla de §11.1 (se deja como esta)")
        else:
            lineas = r
            cambios.append("AGENTS.md §11.1: E1 corregido (ventana real 08:00-17:00)")

    # (c) banner antes de §5.1.c
    txt = _texto(lineas)
    if MARKER81 in txt:
        cambios.append("§5.1.c ya tiene el banner (no se duplica)")
    else:
        bloque = (
            MARKER81 + "\n"
            "> ⚠️ **ESTA SECCION ESTA OBSOLETA (27/10).** No reproduce la formula real\n"
            "> del `macro_score_v2` (0/914) y su lectura de la rama momentum esta invertida.\n"
            "> **La §8 de este mismo archivo la reemplaza por completo.**\n"
            "> No uses esta seccion para nada. El detalle esta en la §13.\n"
        )
        nuevo, idx = _insertar_antes_de_linea(lineas, "5.1", bloque,
                                             excluir=("5.1.1", "5.10", "5.11"))
        if nuevo is None:
            p(f"  {C['y']}·{C['r']} AGENTS.md: no se encontro la seccion §5.1.c")
            p(f"      {C['c']}se escribiria docs/REPARAR_AGENTS.md con el texto exacto{C['r']}")
            cambios.append("PENDIENTE: banner de §5.1.c (ver docs/REPARAR_AGENTS.md)")
        else:
            lineas = nuevo
            cambios.append(f"AGENTS.md: banner de §5.1.c insertado (linea {idx + 1})")

    # (d) §13 al final
    txt = _texto(lineas)
    if MARKER13 in txt:
        cambios.append("§13 ya existe (no se duplica)")
    else:
        lineas = lineas + SECCION_13.strip("\n").split("\n")
        cambios.append("AGENTS.md: +§13 (ronda IA nueva) y +§14 (siguiente trabajo)")

    # ---- escribir ----
    ag_bak = ag.with_suffix(ag.suffix + ".bak")
    if not simular:
        shutil.copy2(ag, ag_bak)
        _escribir_lineas(ag, lineas, crlf)
    for c in cambios:
        p(f"  {C['g']}OK{C['r']} {c}")

    # ---- ESTADO.md ----
    est = RAIZ / "ESTADO.md"
    elines = ESTADO_NUEVO.rstrip("\n").split("\n")
    ecrlf = True
    if est.exists():
        _, ecrlf = _leer_lineas(est)
    if not simular:
        shutil.copy2(est, est.with_suffix(est.suffix + ".bak"))
        _escribir_lineas(est, elines, ecrlf)
    p(f"  {C['g']}OK{C['r']} ESTADO.md: reescrito")

    # ---- el prompt ----
    pr = RAIZ / "docs" / "PROMPT_DIAGNOSTICO_C0_C4.md"
    plines = PROMPT_DIAGNOSTICO.rstrip("\n").split("\n")
    if not simular:
        pr.parent.mkdir(parents=True, exist_ok=True)
        if pr.exists():
            shutil.copy2(pr, pr.with_suffix(pr.suffix + ".bak"))
        _escribir_lineas(pr, plines, True)
    p(f"  {C['g']}OK{C['r']} docs/PROMPT_DIAGNOSTICO_C0_C4.md: nuevo")

    # ---- REPARAR_AGENTS.md (solo si el banner no se pudo poner) ----
    rep = RAIZ / "docs" / "REPARAR_AGENTS.md"
    if any("PENDIENTE: banner" in c for c in cambios):
        if not simular:
            rep.parent.mkdir(parents=True, exist_ok=True)
            _escribir_lineas(rep, REPARAR_AGENTS.rstrip("\n").split("\n"), True)
        p(f"  {C['y']}·{C['r']} docs/REPARAR_AGENTS.md: escrito (banner manual de §5.1.c)")

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\actualizar_gobierno_h23.py --aplicar{C['r']}")
        return 0

    hdr("  2 · VERIFICACION")
    rc = _self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\actualizar_gobierno_h23.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Gobierno H-23 aplicado.{C['r']}")
    p(f"  {C['c']}Siguiente: python verificar.py + commit{C['r']}")
    p(f"  {C['c']}Despues: pega docs/PROMPT_DIAGNOSTICO_C0_C4.md a la IA nueva{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    rels = ["AGENTS.md", "ESTADO.md",
            os.path.join("docs", "PROMPT_DIAGNOSTICO_C0_C4.md")]
    n = 0
    for rel in rels:
        bak = RAIZ / (rel + ".bak")
        orig = RAIZ / rel
        if not bak.exists():
            if orig.exists():
                orig.unlink()
                p(f"  {C['g']}OK{C['r']} eliminado: {rel} (era nuevo)")
                n += 1
            else:
                p(f"  {C['y']}·{C['r']} {rel}: sin .bak y no existe (nada que hacer)")
            continue
        shutil.copy2(bak, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {rel}")
        n += 1
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gobierno H-23: ronda IA nueva, E1-E5, prompt de diagnostico C0-C4")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--deshacer", action="store_true")
    args = ap.parse_args()
    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
