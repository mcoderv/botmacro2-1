#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
actualizar_gobierno_h17.py  -  MACRO2.1

Gobierno tras H-17 (ventana operativa configurable, ADR 006).

Que hace:
  AGENTS.md          8 parches (reframe "no es un bot de trading", ADR 004/005/006,
                     H-13/H-14, ventana configurable, fixes de formato, 914 señales)
  ESTADO.md          reescrito (dice que se REESCRIBE, no se acumula)
  HANDOFF.md         reescrito (cierre de sesion 4)
  docs/PENDIENTES.md reescrito (tracking oficial)
  decisiones/005-*   NUEVO  - ADR 005 caja simetrica (PROPUESTO)
  decisiones/006-*   NUEVO  - ADR 006 ventana configurable (ACEPTADO)
  decisiones/001-*   append - k medido = 0,044 sigma
  .gitignore         + timing_real.json (artefacto de analisis)

Uso:
  python fixes\\actualizar_gobierno_h17.py --simular   (default, no escribe)
  python fixes\\actualizar_gobierno_h17.py --aplicar
  python fixes\\actualizar_gobierno_h17.py --deshacer
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


# =============================================================================
# AGENTS.md - PARCHES
# =============================================================================
# Todas las anclas son ASCII puro: los archivos del usuario tienen UTF-8 con
# acentos/emoji y el matching por subcadena los encuentra igual.

AG_SEC0 = '''## 0. QUÉ ES (Y QUÉ NO ES) ESTE PROYECTO

**MACRO2.1 NO ES UN BOT DE TRADING.** Es un **predictor + validador** de tendencia
macro. NO abre posiciones, NO tiene SL ni TP, NO calcula P&L de una cartera.

| | |
|---|---|
| Lo que hace | Calcula `macro_score_v2` (C3), **emite** una señal, y después **valida** si se equivocó (C4, a 4h/8h/24h) |
| Lo que NO hace | Abrir/cerrar posiciones. SL/TP. Dimensionar. Ejecutar órdenes |
| Quién ejecuta | **MACRO2** (producción, `botmacro`, capa C7). Congelada. |

**Consecuencia práctica:** cuando el análisis diga "43,8% de las señales tocan
el SL primero", eso es un diagnóstico de **TIMING** (¿cuándo se movió el precio?),
**no** un P&L perdido. No existe tal cosa como "SL" en este repo.
La ejecución con SL dinámico ATR que propone el GEM es de **MACRO2 (C7)**,
no de MACRO2.1.

**Y el score v2 no discrimina por cobertura, no por fórmula:** el score SÍ
ordena bien dentro de cada etiqueta (a 24h: FUERTE HR 93,8% > MODERADA 77,8%
> RUIDO 65,3%). El problema es que solo el **9,4%** de las señales son
FUERTE/MODERADA (ver H-9).

---

'''

AG_FIX5_3 = '''| Sin Docker en 2.1 | ✅ Decidido (ADR 003). `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.sh` y `litestream.yml` fueron borrados del clon local. **Producción (`botmacro`) los sigue teniendo.** |
| **Max DD con capital compuesto** | ✅ **ADR 004** (H-15). Antes `np.cumsum` (suma aritmética de %) daba DD de 270% — imposible. Ahora `np.cumprod` sobre índice base 1.0. El DD **siempre cae entre 0% y 100%**. Si ves DD > 100%, es un bug. |
| **Fuente única del umbral ADF** | ✅ **H-12** (implementación del ADR 002). El 0.02 huérfano salió del literal `validation`, de `val_defaults` y del fallback de C3_MACRO. El banner lee la fuente real. |
| **Ventana operativa configurable** | ✅ **ADR 006** (H-17). La ventana sale del JSON (`ventana_operativa`), no de constantes. `python ventana.py --ver / --continuo / --inicio X --fin Y`. Los resúmenes de Telegram ya no están atrapados dentro del `if not en_ventana()`. |'''

AG_H13_H14 = '''### 5.4.b Bugs de métrica conocidos (NO los re-descubrir)

| # | Bug | Dónde | Efecto | Estado |
|---|---|---|---|---|
| **H-13** | `senales_metricas` **no agrega por `calidad_senal_v2`** | `C4_SENIAL_VALIDATOR` | Las métricas por etiqueta salen de la escala **legacy** (14/8/4), que es inalcanzable porque `macro_score` máximo real es 6 | ⬜ Pendiente |
| **H-14** | `_get_price_at_time()` usa `ORDER BY ABS(timestamp_unix - ?) ASC LIMIT 1` | `C4_SENIAL_VALIDATOR` | Puede tomar el precio **posterior** al horizonte. Medido: 472 de 914 señales (52%) cambian de PnL, pero el sesgo neto en HR/PF es **< 1%** ⇒ los números se sostienen, el método no | ⬜ Pendiente (fix: `WHERE timestamp_unix <= ? ORDER BY timestamp_unix DESC LIMIT 1`) |
| **H-16** | "ganancia" significa 2 cosas: `hit_rate`/`wins`/`losses` usan `p > ±0.05%`; `profit_factor` (C4) y `avg_win`/`expectancy` usan `p > 0` | C4 + `report_validator` | Inconsistencia real, pero medida: **impacto < 1% en PF** ⇒ **diferido**, no aplicado | ⏸️ Diferido (ADR 004) |

'''

AG_ASIMETRIA = '''### 5.6 La asimetría LONG/SHORT es el hallazgo MÁS SÓLIDO (no lo percas)

**MACRO2.1 hace más señales SHORT que LONG, y las SHORT funcionan mejor.**
Confirmado por **3 métodos independientes** (n=443 LONG / 471 SHORT):

| Método | LONG | SHORT |
|---|---|---|
| PF a 24h | **0,50** | **1,28** |
| MFE/MAE real | MFE +0,84% vs MAE 2,46% ⇒ **payoff −2,9:1** | MFE +2,84% vs MAE 1,62% ⇒ **1,75x** |
| Movimiento contrario primero | **54,0%** | 34,3% |

**Interpretación correcta:** el 54% de "SL primero" en LONG es un dato de
**timing** (el precio se movió en contra antes que a favor), **no** de P&L.
⇒ **ADR 005 (caja simétrica) PROPUESTO**, no aplicado.

**Ojo:** esto **NO lo arregla ningún umbral** (el PF no depende del break-even).
Es microestructura o lógica de entrada. Copiar el patrón de los que ganan
(`xyz:SILVER` PF 3,22 · `xyz:GOLD` PF 2,64) vale más que recalibrar umbrales.

### 5.7 El timing tiene look-ahead PARCIAL (no lo uses como feature todavía)

El timing actual se calcula sobre la trayectoria **completa** hasta el horizonte
⇒ correlaciona con el PnL final por construcción. No es 100% tautológico
(FAVOR a 24h tiene HR 67,2%, no 100%), pero la prueba limpia es **timing
temprano (1h) con PnL medido desde t+1h**. Falta el flag `--timing-h`.

**Aviso metodológico (obligatorio):** la distribución de etiquetas cambió por
completo el 19/10 (H-10). **Nunca comparar HR/PF entre etiquetas sin cortar por
día o por ventana.**

'''

AG_VENTANA_TABLA = '''| `ventana_operativa` | MODO + HORA_INICIO/FIN | `ventana.py`, `scheduler.py` | `config/CONSOLIDADO/central_params.json` → `CENTRAL_PARAMS["ventana_operativa"]` |'''

# --- parches (ancla, nuevo) ---
AG_PATCHES = [
    ("§0: MACRO2.1 NO es un bot de trading",
     "## 1. CONTACTO",
     AG_SEC0 + "## 1. CONTACTO"),

    ("§5.3: ADR 004 / H-12 / ADR 006 en 'lo que ya esta hecho'",
     "| Sin Docker en 2.1 |",
     AG_FIX5_3),

    ("§5.4.b: bugs de metrica H-13 / H-14 / H-16",
     "### 5.5 El r",
     AG_H13_H14 + "### 5.5 El r"),

    ("§5.6 + §5.7: asimetria LONG/SHORT y aviso de look-ahead",
     "## 6. MAPA DEL PROYECTO",
     AG_ASIMETRIA + "## 6. MAPA DEL PROYECTO"),

    ("§6: ventana.py ahora es configurable",
     "| `ventana.py` | Ventana operativa 08:00-17:00 Caracas |",
     "| `ventana.py` | **Ventana operativa CONFIGURABLE** (JSON `ventana_operativa`). `python ventana.py --ver` / `--continuo` / `--inicio X --fin Y` |"),

    ("§7: fila de la ventana en la tabla de umbrales",
     '| `ALL_ASSETS` | 12 activos | C1_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |',
     '| `ALL_ASSETS` | 12 activos | C1_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |\n' + AG_VENTANA_TABLA),

    ("fix: backtick de apertura faltante",
     "escore_umbral_v2.py`** (reconstruye el score",
     "`rescore_umbral_v2.py`** (reconstruye el score"),

    ("fix: 907/877 -> 914/902",
     "(877 resueltas a 24h)",
     "(902 resueltas a 24h). 914 señales"),
]


# =============================================================================
# ESTADO.md - REESCRITURA COMPLETA
# =============================================================================
ESTADO_NUEVO = '''# ESTADO — MACRO2.1

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
| **H-10** | **Las etiquetas NO son comparables entre sí**: la distribución cambió por completo el 19/10 (0 FUERTE → 1 → 9 → 10) | Cualquier HR/PF por etiqueta es un confound temporal | 🔤 **NUEVO** |
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
- Un cambio por sesión. Y un commit por cambio.
'''


# =============================================================================
# HANDOFF.md - REESCRITURA COMPLETA
# =============================================================================
HANDOFF_NUEVO = '''# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a los chats viejos que venís guardando a mano.
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `docs/PENDIENTES.md`
> + `git log --oneline -20` + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-24
Sesion   : 4
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : a78726b (H-17) + el commit de este gobierno
DB       : 914 señales (902 resueltas a 24h)
```

---

## 1. Qué hice en esta sesión

### A. ADR 004 — Max DD con capital compuesto (H-15) + fuente única del ADF (H-12)
- `report_validator.py` y `C4_SENIAL_VALIDATOR._calculate_metrics()` usaban
  `np.cumsum(pnls)` (suma aritmética de %) ⇒ Max DD de **270,88%**, imposible.
  Ahora `np.cumprod` sobre índice base 1.0 ⇒ **siempre entre 0% y 100%**.
- La curva que consume el reporte se expone en **PnL%** sobre el capital
  compuesto (`((_equity - 1.0) * 100.0)`): antes mostraba "+87,432%" en verde
  cuando era **−12,568%** de pérdida (unidad equivocada + signo invertido).
- **Medido en la DB real:** 4h DD 83,94%→**58,21%** · 8h 137,25%→**75,80%** ·
  24h 270,74%→**94,06%**. El PF se movió **< 1%** ⇒ H-16 queda **diferido**.
- **H-12:** el 0.02 huérfano del umbral ADF salió del literal `validation`, de
  `val_defaults` y del fallback de C3_MACRO. El banner lee la fuente real.

### B. ADR 006 — Ventana operativa configurable (H-17)
- La ventana sale del JSON (`CENTRAL_PARAMS["ventana_operativa"]`), no de
  constantes en 3 archivos. **NO** se importa `C1_5_PARAM_local` desde
  `ventana.py` (al importarse reescribe ese JSON).
- Nuevos modos: `VENTANA` (rango horario) y `CONTINUO` (24/7). Soporta
  **cruce de medianoche** (p.ej. 20:00→04:00) y `DIAS_SEMANA`.
- CLI: `python ventana.py --ver / --continuo / --inicio X --fin Y / --dias ... / --intervalo N`.
  La duración **no** tiene que ser múltiplo de 4h (solo avisa).
- **Bug corregido (H-17):** el bloque de resúmenes de Telegram estaba
  **dentro** de `if not en_ventana():` ⇒ en 24/7 el resumen de las 17:00 nunca
  se enviaba y las banderas nunca se reseteaban a medianoche. En el modo
  VENTANA 8-17, el **resumen de las 8:30 AM nunca se enviaba**.
- Ventana restaurada a **8-17** (el default del script era 8-16 y quitaba 1h).

### C. Análisis de timing y MAE/MFE reales (`analisis/analisis_timing_real.py`)
- **Timing (914 señales):** FAVOR 363 / CONTRA 512 / NEUTRO 39.
  HR por timing a 24h: FAVOR **67,2%** (PF 3,24) vs CONTRA **27,5%** (PF 0,26).
  A 4h: FAVOR 54,0% vs CONTRA 18,8%. A 8h: 53,4% vs 16,6%.
- **Bug del timing 100% CONTRA diagnosticado y corregido:** 908 de 914 señales
  tienen un snapshot con `ts == ts_emision` exacto ⇒ `dt=0` ⇒ el movimiento 0
  cumplía ambos criterios ⇒ el desempate daba CONTRA. Fix: excluir `dt <= 0`
  + `favor == contra → NEUTRO`.
- **MAE/MFE reales (902 señales):** LONG MFE +0,84% / MAE 2,46% ⇒ payoff
  **−2,9:1**; SHORT MFE +2,84% / MAE 1,62% ⇒ **1,75x**. movement contrario
  primero: LONG 54,0% vs SHORT 34,3%.
- **σ por señal:** mediana **1,1458%**, rango 0,318%–3,014% ⇒ el umbral fijo
  0,05% ≡ **k = 0,044σ** (22× más severo en el activo más volátil).
  **⇒ ADR 001 queda justificado con números.**
- **H-14 medido:** 472 de 914 señales (52%) cambian de PnL con la corrección,
  pero el sesgo neto en HR/PF es **< 1%** ⇒ los números se sostienen.
- **La resolución de 8h es inservible hoy:** lag mediano **4,03h** y
  **735/914 señales con lag > 1h** (la ventana 8-17 no tiene snapshots a
  las 20:00). **Con 24/7 el lag baja a ~21 min.**

### D. Gobierno
- `AGENTS.md`: §0 (MACRO2.1 NO es un bot de trading), §5.4.b (H-13/14/16),
  §5.6 (asimetría), §5.7 (aviso de look-ahead), ADR 004/005/006, ventana
  configurable, fixes de formato, 914 señales.
- `ESTADO.md`, `HANDOFF.md`, `docs/PENDIENTES.md`: reescritos.
- **ADR 005** (caja simétrica) PROPUESTO · **ADR 006** (ventana) ACEPTADO ·
  ADR 001 append con k = 0,044σ.

---

## 2. Los hallazgos importantes (léelos antes de tocar el score)

### 2.1 MACRO2.1 NO es un bot de trading
Calcula score, emite señal, valida. **No abre posiciones, no tiene SL ni TP.**
El "43,8% toca SL primero" del GEM es de **MACRO2 (C7, producción)**. En 2.1
esa cifra es **timing**, no P&L.

### 2.2 El score v2 SÍ discrimina — el problema es la COBERTURA
A 24h: FUERTE FAVOR HR **93,8%** (PF 25,65) · MODERADA **77,8%** · RUIDO
**65,3%**. Pero solo **86 de 914 señales (9,4%)** son FUERTE o MODERADA.
**H-9 manda.** Recalibrar umbrales sobre un score sin multi-TF es calibrar
sobre ruido.

### 2.3 La asimetría LONG/SHORT es el hallazgo más sólido
3 métodos independientes (ver `AGENTS.md` §5.6). **ADR 005 propuesto.**

### 2.4 H-10 sigue feroz (confound temporal)
21/10 HR 84,4% PF 20,05 · 23/10 HR 16,7% · 18/10 HR 25,9% PF 0,229.
**Un solo día mueve el PF de 0,23 a 20,05.** Nunca comparar etiquetas sin
cortar por día.

### 2.5 El timing actual tiene look-ahead parcial
Se calcula sobre la trayectoria completa hasta el horizonte. La prueba limpia
es **timing temprano (1h) con PnL medido desde t+1h** (`--timing-h`, falta).

---

## 3. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Activar el 24/7 | Depende de si el hosting es free o pago. **Decisión del usuario.** |
| Arreglar `s_mtf = 0` / la rama del `ms_v2` | Es un cambio al scoring ⇒ necesita ADR, y el diagnóstico del `N/A` no está cerrado. |
| Mover el timing a 1h (`--timing-h`) | Requiere v3 del script de análisis. |
| H-13 / H-14 / H-16 | Impacto medido bajo (< 1% en PF). Van después del diagnóstico de H-9. |
| ADR 001 (k×σ) implementado | La fórmula está justificada (k = 0,044σ) pero el PF no depende del break-even ⇒ no mueve el PF. |
| Matar los 5 fallbacks silenciosos | Toca 4 módulos. Sesión propia. |
| Actualizar `verificar.py` a 6 ADRs | Requiere ver el archivo. Pendiente. |
| Backup a Drive | **Es una acción manual tuya.** Es la prioridad #1 y no la puedo hacer yo. |

---

## 4. Qué creo que está frágil (opinión sin filtros)

1. **El score v2 no puede discriminar** (H-9). Arreglar esto tiene más impacto
   que recalibrar cualquier umbral.
2. **Cualquier análisis del v2 sobre las 877 señales es basura.** El grupo real
   son 111 (3 días), y aun esas están confundidas por fecha.
3. **Los 5 fallbacks silenciosos** siguen siendo el riesgo #1 latente.
4. **La ventana de 8h hoy no sirve** (lag mediano 4,03h). Con 24/7 se arregla
   sola; con 8-17 no.
5. **El auto-restore nunca se probó**: C2 dice "Sin backups previos".
6. **LONG pierde, SHORT gana.** Y dentro de los cripto, BTC PF 0.30 y SP500
   PF 0.28. Eso no lo arregla ningún umbral.
7. **Cero tests.** `verificar.py` es el primer paso, no el final.

---

## 5. Qué chequear primero en la próxima sesión

1. `python verificar.py` ⇒ tiene que dar **19 ok / 0 fallas**.
2. `python git\\estado.py` ⇒ leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `AGENTS.md` §0, §5.1.b, §5.1.c, §5.6 ⇒ los hallazgos de hoy.
4. Si tocás el v2: leer `AGENTS.md` §5.1.b **ANTES** de comparar etiquetas.

---

## 6. Cómo verificar que no rompiste nada

```cmd
python verificar.py
python git\revisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 7. Cosas pendientes de confirmación (preguntas abiertas)

- **¿Render free o de pago?** Define si el 24/7 se activa ya. (Si es free y
  el proceso se cae, corré el bot en local: los 30 días para el OOS del 21/11
  se collecting igual.)
- **¿Qué cambió el 2026-10-19 en el pipeline?** (despliegue v7.9.3 / cambio de
  ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es un
  artefacto de despliegue o de diseño.
- **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en
  `logs_v2.1\\*.log`).
- ¿Los 4 archivos "Nivel C" se borran o se quedan?
- ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
'''


# =============================================================================
# docs/PENDIENTES.md - REESCRITURA COMPLETA
# =============================================================================
PENDIENTES_NUEVO = '''# PENDIENTES — MACRO2.1

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
| 13 | **Backup local de la DB** en `Desktop\\MACRO2.1_BACKUP\\` | 2026-10-23 |
| 14 | **Max DD con capital compuesto** (H-15) + **fuente única del ADF** (H-12) | **ADR 004** |
| 15 | **Ventana operativa configurable** (VENTANA/CONTINUO, cruce de medianoche, días, CLI) + **resúmenes de Telegram fuera del `if not en_ventana()`** (H-17) | **ADR 006** |
| 16 | Análisis de timing real (914 señales) + MAE/MFE reales + σ por señal | `analisis/analisis_timing_real.py` |
| 17 | **ADR 005 (caja simétrica) PROPUESTO** + ADR 001 con k = 0,044σ medido | `decisiones/` |

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
  ⇒ `findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\\*.log`
- **Posibles fixes (todas necesitan ADR):** (A) guardar ambas ramas en columnas
  separadas; (B) decidir la rama por detección de breakout en vez del ADF;
  (C) piso al `rs` en la rama estacionario.
- **Ojo:** `AGENTS.md` §5.1.c

### 2. El score v2 no se puede evaluar todavía (H-10)
- **Problema:** la distribución de etiquetas cambió por completo el 19/10
  (0 FUERTE → 1 → 9 → 10). Comparar HR/PF entre etiquetas = comparar días distintos.
- **Pendiente:** (a) saber qué cambió el 19/10; (b) medir por día antes de comparar.
- **Herramienta:** `python analisis\\rescore_umbral_v2.py` (ya corta por día y por subgrupo).

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
- `data\\vault_v2.1.db` (914 señales) y `.env`.
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
2. **¿Qué cambió el 2026-10-19 en el pipeline?** (despliegue v7.9.3 / cambio de
   ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es
   artefacto de despliegue o de diseño.
3. **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en `logs_v2.1\\*.log`)
4. ¿Los 4 archivos "Nivel C" se borran o se quedan?
5. ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
6. ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
7. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
'''


# =============================================================================
# ADRs NUEVOS
# =============================================================================
ADR005 = '''# ADR 005 — Caja simétrica para compensar la asimetría LONG/SHORT (H-17b)

- **Estado:** PROPUESTO (no aplicado)
- **Fecha:** 2026-10-24
- **Alcance:** `C3_MACRO_local.py` (cálculo de `caja_p`) y el scoring de `ms_v2`.
- **Problema:** asimetría estructural LONG/SHORT.

## Contexto

MACRO2.1 emite **más señales SHORT que LONG**, y las SHORT rinden mucho mejor.
El hallazgo está confirmado por **tres métodos independientes** sobre 914 señales
(902 resueltas a 24h):

| Método | LONG | SHORT |
|---|---|---|
| Profit Factor a 24h | **0.50** | **1.28** |
| MFE / MAE real | MFE +0,84% vs MAE 2,46% ⇒ payoff **−2,9:1** | MFE +2,84% vs MAE 1,62% ⇒ **1,75x** |
| Movimiento contrario primero | **54,0%** | 34,3% |

Corroborado por activo: `xyz:SILVER` PF 3,22 · `xyz:GOLD` PF 2,64 (ganan) vs
BTC PF 0,30 · `xyz:SP500` PF 0,28 (pierden). Dentro de los cripto, BTC y SP500
pierden y los dos son **LONG-dominantes**.

**MACRO2.1 no es un bot de trading**: no hay posiciones, no hay SL ni TP. El
"54% toca el stop primero" es un dato de **TIMING** (¿el precio se movió en
contra antes que a favor?), no una pérdida.

## Por qué ningún umbral lo arregla

`profit_factor` se calcula con `p > 0` / `p < 0` en `C4_SENIAL_VALIDATOR`, sin
el umbral de break-even. **El ADR 001 (k×σ) mueve el HR, no el PF.** Medido:
unificar la definición de "ganancia" cambia el PF en **< 1%**. Por lo tanto,
cualquier solución que sea un simple umbral es insuficiente.

## Decisión (PROPUESTA)

Hacer la **caja simétrica en el scoring**: cuando el setup es LONG, la
distancia objetivo (`caja_p`) se calcula de forma **asimétrica a favor**, de
modo que el score de un LONG comparable al de un SHORT comparable.

Concretamente: penalizar el término `caja` en la rama LONG en la misma
proporción en que hoy se favorece a la rama SHORT, hasta que el HR/PF por tipo
se iguale.

**Regla de decisión (Go/No-Go), del GEM:**
> Si la asimetría **se mantiene en todos los regímenes** (todos los activos, todos
> los días, todas las ventanas de resolución), ⇒ **Go CAJA simétrica**.

## Estado: la evidencia aún no alcanza

La condición de Go **todavía no se puede evaluar**:
- H-9 (el score v2 tiene 2 inputs degradados) hace que el score no sea confiable.
- H-10 (confound temporal) hace que la comparación entre días no sea válida.
- El timing actual tiene **look-ahead parcial** ⇒ no sirve como feature.

## Consecuencias

- **A favor:** ataca la asimetría en su origen (el scoring), no con un parche
  estadístico. Es la única vía que mueve el PF.
- **En contra / riesgo:** con 111 señales de score v2 real, cualquier cambio en
  el scoring tiene **riesgo alto de sobreajuste**. El ADR no se aplica hasta que
  la muestra sea mayor y H-9/H-10 estén cerrados.
- **No toca producción** (`botmacro`). DATA FREEZE vigente.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Solo recalibrar umbrales / k×σ | No mueve el PF (< 1% medido) |
| Invertir el signo del score en LONG | Arriesga destruir el 28% de aciertos LONG que sí existen |
| Reducir el universo a 2 activos | Ya descartado por el usuario (ADR 001, 2026-10-21) |
| Aplicarlo ya "a ojo" | Sobreajuste con n=111 y dos confounders abiertos |

## Cómo se verifica

1. La asimetría se mantiene en todos los regímenes (por activo, por día, por
   ventana de resolución) — con el **timing temprano** (`--timing-h 1.0`), no el
   actual que tiene look-ahead.
2. La caja simétrica mueve el **PF por tipo** de 0,50 / 1,28 hacia la paridad,
   sin degradar el PF global.
3. La validación es **out-of-sample**: T_0 = 2026-10-22 → 2026-11-21.

## Referencias

- `analisis/analisis_timing_real.py` (sección MFE/MAE y timing por tipo).
- `AGENTS.md` §5.6.
- ADR 001 (umbral k×σ, con k = 0,044σ medido).
'''

ADR006 = '''# ADR 006 — La ventana operativa es un valor de configuración

- **Estado:** ACEPTADO
- **Fecha:** 2026-10-24
- **Alcance:** `ventana.py`, `scheduler.py`, `C1_5_PARAM_local.py`,
  `config/CONSOLIDADO/central_params.json`.
- **Problema:** H-17.

## Contexto

La ventana operativa estaba **hardcodeada en tres lugares**:
`ventana.py` (`VENTANA_INICIO = 8`, `VENTANA_FIN = 17`), el *fallback* del
`try/except ImportError` de `scheduler.py`, y el log de arranque. Cambiarla
significaba editar código y reiniciar.

Eso era un problema por dos motivos:

1. **El 24/7 era imposible.** El modo CONTINUO existía *de facto* (por el
   fallback sin `ventana.py`), pero no se podía activar a propósito. Con la
   estructura de la ventana (8-17) y una resolución de 8h, el **lag mediano era
   de 4,03h** y **735 de 914 señales** quedaban con lag > 1h: la ventana de 8h
   era inservible.
2. **El bug H-17.** El bloque de resúmenes de Telegram estaba **dentro** de
   `if not en_ventana():`. En modo CONTINUO el resumen de las 17:00 nunca se
   enviaba y las banderas nunca se reseteaban a la medianoche. En el modo
   VENTANA 8-17, el **resumen de las 8:30 AM nunca se enviaba** (a esa hora se
   está dentro de ventana, así que el bloque no se ejecutaba).

## Decisión

**La ventana operativa pasa a ser un valor de configuración**, en la sección
`ventana_operativa` de `CENTRAL_PARAMS`:

```json
"ventana_operativa": {
  "MODO": "VENTANA",
  "HORA_INICIO": 8,
  "HORA_FIN": 17,
  "INTERVALO_SEGUNDOS": 900,
  "DIAS_SEMANA": [0, 1, 2, 3, 4, 5, 6],
  "TZ": "America/Caracas"
}
```

Reglas de implementación:

- `ventana.py` lee el **JSON**, no las constantes. **NO** importa
  `C1_5_PARAM_local`, porque al importarse ese módulo **reescribe** el JSON
  (y se pisaría a sí mismo).
- `MODO`: `VENTANA` (rango horario) | `CONTINUO` (24/7, siempre dentro).
- Se soporta el **cruce de medianoche** (p.ej. 20:00 → 04:00): antes
  `en_ventana()` comparaba `INICIO <= hora < FIN` y una ventana invertida
  quedaba **siempre fuera**.
- `DIAS_SEMANA` (0 = lunes) permite operar solo algunos días.
- La **duración no tiene que ser múltiplo de 4h**. Los múltiplos de 4
  (4/8/12/16/20/24) son **presets sugeridos** porque encajan con las ventanas
  de resolución de C4 (`RESOLUTION_WINDOWS_HOURS = [4, 8, 24]`); si la duración
  no lo es, el CLI **avisa** pero acepta. *(El usuario operaba 8-17 = 9h.)*
- El fallback `except ImportError` de `scheduler.py` **se mantiene** como red
  de seguridad (24/7).
- **El bloque de resúmenes diarios se mueve FUERA del `if not en_ventana()`**:
  los resúmenes de Telegram y el reset de banderas a medianoche deben
  ejecutarse en cada ciclo, esté dentro o fuera de ventana.

### CLI

```cmd
python ventana.py --ver                    :: muestra la ventana actual
python ventana.py --continuo               :: 24/7
python ventana.py --inicio 4 --fin 16      :: ventana de 4h a 16h
python ventana.py --inicio 20 --fin 4      :: cruza la medianoche
python ventana.py --dias 0,1,2,3,4         :: solo lunes a viernes
python ventana.py --intervalo 900          :: segundos entre ciclos
```

La ventana **es un valor libre**: el CLI no impone nada, solo avisa.

## Consecuencias

**A favor:**
- Cambiar el horario es **un comando**, sin editar código y sin buscar en 3 archivos.
- El **24/7 se puede activar a propósito** (no por accidente).
- Con 24/7: el lag de la resolución de 8h **deja de ser 4h**, el
  *confirmation filter* (emitir → confirmar → resolver) aplica al **100%** en
  vez del 67%, y desaparece el sesgo de régimen horario en las muestras.
- El bug de los resúmenes queda cerrado.
- Las ventanas que cruzan medianoche funcionan.

**En contra / a tener en cuenta:**
- **Cambiar la ventana cambia el régimen de muestreo** ⇒ los datos nuevos **no
  son comparables** con los viejos. Con H-10 abierto, esto puede ser justo la
  causa del corte del 19/10. **Coordinar antes de tocar la ventana** y, cuando
  se toque, **cortar por día** en todo análisis.
- `ventana.py` ahora depende del JSON en disco: si el JSON se corrompe, la
  ventana cae a los `_DEFAULTS` (8-17). Es el comportamiento deseado, pero
  hay que saberlo.
- El JSON lo regenera `C1_5_PARAM_local` al importarse ⇒ **el literal y el JSON
  tienen que coincidir**. Por eso la sección está en los dos y
  `verificar.py` debería compararlos.

**No toca producción** (`botmacro`). El DATA FREEZE sigue vigente. La
ventana 08:00-17:00 de `decisiones/000-render-litestream-r2.md` describe la
**producción** y no cambia.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Seguir con constantes hardcodeadas | La ventana iba a cambiar (free → pago) y eso no puede requerir editar 3 archivos |
| Dejar la ventana solo en variables de entorno | No se versiona, no se ve en `verificar.py`, y no sobrevive a un reinicio sin `.env` |
| Importar `C1_5_PARAM_local` desde `ventana.py` | Al importarse **reescribe el JSON**: se pisa a sí mismo y genera una carrera |
| Imponer duraciones múltiplo de 4h | Contradice el uso real (8-17 = 9h) y la regla de que la ventana es un valor libre |
| Quitar el fallback `except ImportError` de `scheduler.py` | Es la red de seguridad que mantiene vivo al scheduler si `ventana.py` falta |

## Cómo se verifica

```cmd
python ventana.py --ver
```
⇒ debe mostrar MODO, rango, duración, intervalo, días y la ruta del JSON.

```cmd
python verificar.py
```
⇒ 19 ok / 0 fallas / 1 aviso.

```cmd
python fixes\aplicar_ventana_config.py --deshacer
```
⇒ restaura `ventana.py`, `scheduler.py`, `C1_5_PARAM_local.py` y el JSON desde
los `.bak`.

## Referencias

- `AGENTS.md` §5.3 y §6.
- `docs/PENDIENTES.md` §3.
- `decisiones/000-render-litestream-r2.md` (la ventana de **producción**).
'''

ADR001_APPEND = '''
---

## ACTUALIZACIÓN 2026-10-24 — k medido sobre datos reales

El valor de **k** dejó de ser una estimación cualitativa. Medido sobre las
**914 señales** (902 resueltas a 24h), con la dispersión de los retornos
absolutos por señal:

| | σ por señal |
|---|---|
| mediana | **1,1458 %** |
| mínimo | 0,318 % |
| máximo | 3,014 % |

El umbral fijo actual es `BREAKEVEN_THRESHOLD_PCT = 0.05`.

> **k = 0,05 / 1,1458 = 0,0436σ ≈ 0,044σ**

Es decir: el umbral actual es **22× más severo en el activo más volátil**
(0,05 / 0,318 = 0,157σ) que en el menos volátil (0,05 / 3,014 = 0,017σ).
El problema de "sesgo por volatilidad" que justificaba este ADR **queda
confirmado con números**.

**Recordatorio importante (medido el mismo día):**
`profit_factor` en `C4_SENIAL_VALIDATOR` se calcula con `p > 0` / `p < 0`,
**sin** el umbral de break-even. Y unificar la definición de "ganancia" mueve
el PF en **< 1%** (H-16, medido). Por lo tanto:

> **Implementar k×σ mueve el HR, pero NO el PF.**
> No resuelve la asimetría LONG/SHORT (PF 0,50 vs 1,28). Eso es el **ADR 005**.

**Estado de la decisión:** la fórmula queda **justificada**, pero la
implementación sigue **pendiente de decisión explícita** del usuario
(¿se implementa o se pospone?). La asimetría LONG/SHORT tiene prioridad
mayor porque es la que mueve el PF.
'''


# =============================================================================
# .gitignore
# =============================================================================
GITIGNORE_LINE = "timing_real.json"


# =============================================================================
# MOTOR
# =============================================================================
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
    chk("AGENTS.md: §0 'NO es un bot de trading'", "## 0. QUÉ ES" in ag)
    chk("AGENTS.md: ADR 004 / 006 en §5.3", "ADR 004" in ag and "ADR 006" in ag)
    chk("AGENTS.md: §5.4.b con H-13/H-14/H-16", "5.4.b" in ag and "H-13" in ag)
    chk("AGENTS.md: §5.6 asimetria LONG/SHORT", "5.6" in ag and "−2,9:1" in ag)
    chk("AGENTS.md: §5.7 aviso de look-ahead", "5.7" in ag)
    chk("AGENTS.md: ventana.py configurable", "CONFIGURABLE" in ag)
    chk("AGENTS.md: backtick de rescore arreglado",
        "`rescore_umbral_v2.py`**" in ag and "\nescore_umbral_v2.py`**" not in ag)
    chk("AGENTS.md: 902 resueltas", "902 resueltas a 24h" in ag)
    chk("AGENTS.md: fila de la ventana en §7", "ventana_operativa` | MODO" in ag)

    es = (raiz / "ESTADO.md").read_text(encoding="utf-8")
    chk("ESTADO.md: H-13/H-14/H-15/H-17 en riesgos",
        all(k in es for k in ("H-13", "H-14", "H-15", "H-17")))
    chk("ESTADO.md: 914 / 902", "914 señales" in es and "902 resueltas" in es)
    chk("ESTADO.md: commit a78726b", "a78726b" in es)

    ho = (raiz / "HANDOFF.md").read_text(encoding="utf-8")
    chk("HANDOFF.md: sesion 4", "Sesion   : 4" in ho)
    chk("HANDOFF.md: ADR 004/005/006", "ADR 004" in ho and "ADR 005" in ho and "ADR 006" in ho)

    pe = (raiz / "docs" / "PENDIENTES.md").read_text(encoding="utf-8")
    chk("PENDIENTES.md: 13+ items", "### 13." in pe)
    chk("PENDIENTES.md: H-13/H-14/H-16", "H-13" in pe and "H-14" in pe and "H-16" in pe)
    chk("PENDIENTES.md: k = 0,044 sigma", "0,044σ" in pe)

    for f, needle in (
        ("decisiones/005-caja-simetrica-long-short.md", "ADR 005"),
        ("decisiones/006-ventana-operativa-configurable.md", "ADR 006"),
    ):
        fp = raiz / f
        chk(f"{f} existe y menciona {needle}",
            fp.exists() and needle in fp.read_text(encoding="utf-8"))

    a1 = (raiz / "decisiones" / "001-umbral-dinamico-volatilidad-PENDIENTE.md")
    if a1.exists():
        chk("ADR 001 tiene la actualizacion con k medido",
            "0,0436σ" in a1.read_text(encoding="utf-8"))

    gi = (raiz / ".gitignore").read_text(encoding="utf-8")
    chk(".gitignore ignora timing_real.json", "timing_real.json" in gi)

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("actualizar_gobierno_h17.py  -  MACRO2.1")
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
        ("ESTADO.md", ESTADO_NUEVO, "ESTADO.md reescrito"),
        ("HANDOFF.md", HANDOFF_NUEVO, "HANDOFF.md reescrito"),
        (os.path.join("docs", "PENDIENTES.md"), PENDIENTES_NUEVO, "docs/PENDIENTES.md reescrito"),
    ):
        ruta = RAIZ / rel
        if not ruta.exists():
            fallidos.append((rel, "no existe"))
            p(f"  {C['R']}XX{C['r']} {rel}: no existe")
            continue
        _, crlf = _leer_lineas(ruta)
        lineas = contenido.rstrip("\n").split("\n")
        buf.set(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {etiqueta}")

    # ---- ADRs nuevos ----
    for rel, contenido in (
        ("decisiones/005-caja-simetrica-long-short.md", ADR005),
        ("decisiones/006-ventana-operativa-configurable.md", ADR006),
    ):
        ruta = RAIZ / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        buf.set(ruta, contenido.rstrip("\n").split("\n"), False)
        p(f"  {C['g']}OK{C['r']} {rel} creado")

    # ---- ADR 001: append ----
    a1 = RAIZ / "decisiones" / "001-umbral-dinamico-volatilidad-PENDIENTE.md"
    if a1.exists():
        lineas, crlf = _leer_lineas(a1)
        if "ACTUALIZACIÓN 2026-10-24" not in "\n".join(lineas):
            buf.set(a1, lineas + ADR001_APPEND.rstrip("\n").split("\n"), crlf)
            p(f"  {C['g']}OK{C['r']} decisiones/001-* — k medido 0,044 sigma agregado")
        else:
            p(f"  {C['y']}·{C['r']} decisiones/001-* — ya tiene la actualizacion (no se toca)")
    else:
        p(f"  {C['y']}·{C['r']} decisiones/001-* no encontrado (se omite el append)")

    # ---- .gitignore ----
    gi = RAIZ / ".gitignore"
    if gi.exists():
        lineas, crlf = _leer_lineas(gi)
        if GITIGNORE_LINE not in lineas:
            buf.set(gi, lineas + [GITIGNORE_LINE], crlf)
            p(f"  {C['g']}OK{C['r']} .gitignore — timing_real.json ignorado")
        else:
            p(f"  {C['y']}·{C['r']} .gitignore — timing_real.json ya estaba ignorado")
    else:
        fallidos.append((".gitignore", "no existe"))

    if fallidos:
        hdr("  ABORTADO - no se escribio NADA")
        for a, d in fallidos:
            p(f"  {C['R']}XX{C['r']} {a} — {d}")
        p()
        p("  Pega este informe a la IA para ajustar los parches.")
        return 1

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\actualizar_gobierno_h17.py --aplicar{C['r']}")
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
        p(f"  {C['R']}restaurar: python fixes\\actualizar_gobierno_h17.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Gobierno actualizado.{C['r']}")
    p(f"  {C['c']}Siguiente: python verificar.py  (y despues un commit){C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    rels = ["AGENTS.md", "ESTADO.md", "HANDOFF.md", "docs/PENDIENTES.md",
            ".gitignore", "decisiones/001-umbral-dinamico-volatilidad-PENDIENTE.md"]
    nuevos = ["decisiones/005-caja-simetrica-long-short.md",
              "decisiones/006-ventana-operativa-configurable.md"]
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
    for rel in nuevos:
        f = RAIZ / rel
        if f.exists():
            f.unlink()
            p(f"  {C['g']}OK{C['r']} eliminado: {rel} (era nuevo)")
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Actualiza el gobierno tras H-17 (ADR 006) y escribe ADR 005")
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
