# RELEVO_IA — MACRO2.1

> **Brief de adopción para una IA que arranca hoy.**
> Leé esto PRIMERO. Después: `AGENTS.md` → `ESTADO.md` → `docs/PENDIENTES.md`.
>
> **Generado:** 2026-10-26 · **Sesión:** 5
> **Estado del proyecto:** vivo, con el camino reorientado, esperando arrancar el Track A.
>
> Este documento existe porque el trabajo hecho del 20 al 26/10 (un diagnóstico
> que cambió la dirección del proyecto) **no puede ser re-derivado cheaply**.
> Está todo aquí: números, líneas de código, trampas, decisiones y lo que falta.

---

## 0. Cómo usar este documento

| Si sos… | Leé |
|---|---|
| **Una IA nueva** (Cline, DeepSeek, Claude, GPT) | Todo este archivo, en este orden. Es autocontenido. |
| **El usuario** | §1 (qué es), §2 (reglas), §10 (plan), §12 (próximo paso) |
| **Querés contributo técnico** | §7 (código real), §8 (hallazgos), §13 (trampas) |
| **Querés decidir** | §9 (segunda opinión), §10 (tracks), §11 (protocolo + muerte) |

**Regla de oro de este proyecto:** *el que escribe, primero en el chat; el
usuario dice "ok"; recién ahí se escribe el archivo.* Si sos la IA que sigue,
respetá eso — el usuario es consciente del costo en tokens.

---

## 1. Qué es MACRO2.1 (y qué NO es)

**MACRO2.1 es un bot de PREDICCIÓN y VALIDACIÓN de tendencia macro.**
**NO es un bot de trading.** No tiene posiciones, ni SL, ni TP, ni órdenes.
Emite una señal direccional (LONG/SHORT) con un score, y después **valida**
si el precio hizo lo que se esperaba (mide PnL, MAE/MFE, timing).

> Consecuencia práctica: el MAE/MFE de MACRO2.1 es **diagnóstico de TIMING**,
> no P&L. Y el 43,8% "toca SL primero" no es una pérdida: es una medida de
> cuándo se movió el precio.

**Gemini (GEM) produce señales; MACRO2.1 las audita.** Es un sistema de
verificación adversarial, no un generador de entradas para trading.

**Universo:** 12 activos (cripto + índices/metales con prefijo `xyz:` de HIP-3).
**Horizonte de validación:** 4h / 8h / 24h (H-18 quiere hacerlo configurable).
**Mercado:** Hyperliquid (spot/perps), precios por `price_snapshots` cada 15 min.

---

## 2. Las reglas de la casa (no negociables)

1. **Producción (`botmacro`) está CONGELADA — DATA FREEZE.** Todo se valida en
   desarrollo (`botmacro2-1`) primero.
2. **Si algo funciona, no se toca sin un ADR.** (`decisiones/00X-*.md`)
3. **`python verificar.py` es el gate antes de commitear.** Si falla, no se avanza.
4. **Un cambio por sesión. Un commit por cambio.** Se commitea con `python git/guardar.py "msg"`.
5. **Nunca crear ni editar archivos sin el "ok" explícito del usuario.**
   Primero el diseño en el chat, después el archivo.
6. **CMD.exe únicamente.** Sin PowerShell, sin `curl`/`wget` unix, sin `&&`, sin `;`.
7. **Ritmo: 1 a 4 comandos por turno.** Si uno depende del anterior (o puede
   fallar), de a uno. Nunca una cadena de 6 pasos. Cada comando lleva **output
   esperado** + **"pegá la salida"**.
8. **No mezcles tareas:** cuando se está validando un script/fix/análisis, ese es
   el **único** foco del turno. Cerrarlo (self-test + commit) antes de abrir
   preguntas o definir el trabajo siguiente.
9. **Nunca comparar HR/PF entre etiquetas o ventanas sin cortar por día.**
   Y ahora sabemos que el grano correcto es el **CICLO**, no el día.
10. **Los scripts de git siempre en Python** (Windows).
11. **En CMD: nada de `more` ni `type`** (cuelgan la consola). Usar
    `findstr /n "patron" archivo` o redirigir a un `.txt` y pegar eso.
12. **UTF-8 en consola china/ANSI sale como mojibake** ⇒ en parches, anclar con
    **cadenas ASCII puras**.

---

## 3. Mapa del repo

```
MACRO2.1/
├─ AGENTS.md              ← reglas + §8 fórmula real + §10 lista negativa + §11 OOS
├─ ESTADO.md              ← "dónde estoy" (se REESCRIBE, no se acumula)
├─ HANDOFF.md             ← cierre de cada sesión
├─ main.py                ← runner del pipeline (8 celdas)
├─ scheduler.py           ← loop de Render (HEALTH_PORT desde PORT, fallback 24/7)
├─ ventana.py             ← en_ventana()  ⚠️ H-21: trabaja con HORA ENTERA
├─ C0_*.py … C4_*.py      ← las celdas del pipeline
├─ C1_5_PARAM_local.py    ← CENTRAL_PARAMS (fuente única de params)
├─ verificar.py           ← gate de 19 checks (verifica ADR 000-006)
├─ config/CONSOLIDADO/central_params.json
├─ decisiones/            ← 8 ADRs (00X-slug.md)
├─ docs/
│  ├─ INFORME_MACRO2.1.md  ← SPEC ORIGINAL — NO EDITAR
│  ├─ PENDIENTES.md        ← tracking oficial
│  ├─ RELEVO_IA.md         ← ESTE ARCHIVO
│  └─ local/               ← gitignored (parches de una vez ya aplicados)
├─ analisis/              ← scripts de diagnóstico (NO de producción)
├─ fixes/                 ← parches de una vez (se archivan a docs/local/)
├─ git/                   ← guardar.py · estado.py · deshacer.py · revisar_archivo.py
├─ plantillas/            ← plantillas de ADR, changelog, etc.
├─ data/                  ← GITIGNORED (la DB no está en GitHub)
└─ logs_v2.1/ backups_v2.1/
```

**Remotos:** `origin` = `botmacro2-1` (desarrollo, privado) · `origin-macro2` = `botmacro` (producción, congelada).

**Comandos útiles:** `python verificar.py` · `python git/estado.py` ·
`python git/guardar.py "msg"` · `python git/deshacer.py` · `python git/revisar_archivo.py <archivo>`

---

## 4. El pipeline C0 → C4

| Celda | Qué hace | Tabla que escribe |
|---|---|---|
| **C0** | Config / params / snapshot de mercado | `backups_v2.1` |
| **C1 / C1_5** | Parámetros centralizados | `central_params.json` |
| **C2** | Bóveda: migraciones de schema, **auto-restore** | `vault_v2.1.db` (23 tablas) |
| **C2_5** | Contexto (import con fallback silencioso ⚠️) | contexto |
| **C3** | **Macro engine**: ADF/FFD, POC/caja/FVG, score v2, `macro_audit_log` | `macro_audit_log` (3036) · `gem_macro_snapshot` (2402) |
| **C3_5** | **Regime engine**: `regime_state` / `regime_features` | `regime_state` (2472) · `regime_features` (2338) |
| **C4** | **Validador**: emite, captura precios, resuelve a 4/8/24h | `senales_validadas` (914) · `senales_metricas` · `price_snapshots` (1886) · `c4_execution_log` (204) |

**Conceptos que no hay que confundir:**
- **Emitir ≠ Confirmar ≠ Resolver.** C3 emite; el confirmation filter/timing
  temprano confirma; C4 resuelve.
- `macro_score` (legacy) ≠ `macro_score_v2` (nuevo). El **sesgo** (BULL/BEAR) y
  el tipo de señal (LONG/SHORT) salen del **legacy** — del mismo número.

---

## 5. La base de datos

- **Ruta:** `data/vault_v2.1.db` — **`data/` está GITIGNORED**. Es lo único
  que no se recupera de GitHub. **Backup en Drive = prioridad manual #1.**
- **Contenido:** 914 señales, 902 resueltas a 24h. 23 tablas.
- **Zona horaria: HORA LOCAL CARACAS (UTC−4)** ← verificado el 26/10 con 3 pares
  epoch↔`fecha_hora`:
  ```
  1791894866 → 2026-10-13 08:35:03   offset −3,99 h
  1792432869 → 2026-10-19 14:07:12   offset −3,90 h
  1792799471 → 2026-10-23 19:51:11   offset −4,00 h
  ```
  ⇒ **Todo análisis por hora es en hora Caracas.** La ventana operativa
  acordada (04:00–16:00) es también Caracas.
- **Tablas clave:** `senales_validadas` (35 col) · `macro_audit_log` (3036) ·
  `regime_state` (2472) · `regime_features` (2338) · `c4_execution_log` (204) ·
  `price_snapshots` (1886) · `gem_macro_snapshot` (2402) · `senales_metricas` ·
  `logs_v2.1` (39 líneas ⚠️ se sobrescribe).

**Cuidado con dos bases mezcladas:** la DB local mezcla el histórico de
producción (13–19/10, sin score v2 real) y el local (19–23/10, con score real).
**Son dos poblaciones. No se mezclan.**

---

## 6. Cronología de hallazgos (H-1 → H-22)

| # | Qué | Estado |
|---|---|---|
| H-1 | Umbral ADF 0.02 en C3 vs 0.05 en C3_5 | ✅ Resuelto (ADR 002) |
| H-2 | Dos ADF distintos (niveles vs residuales FFD) | ❗ Pendiente |
| H-3 | C0 escribía en `backups/`, C2 leía `backups_v2.1/` | ✅ Resuelto |
| H-4 | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo (≡ k=0,044σ) | ❗ Pendiente (ADR 001) |
| H-5 | `_migrar_v28` sobrescribía el JSON guardado | ✅ Resuelto |
| H-6 | `SCORE_ALTA=14`/`MEDIA=8` con `macro_score` máx 6 | ❗ Pendiente (matar) |
| H-7a | Backup de la DB en un solo disco | ❗ **PRIORIDAD #1 (manual)** |
| H-7b | 5 imports con fallback silencioso | ❗ Pendiente |
| H-8 | 6 cripto pierden (BTC PF 0,30), TradFi gana | ❗ En investigación |
| H-9 | `macro_score_v2` sin poder predictivo | ✅ **CERRADO con evidencia (26/10)** |
| H-10 | Las etiquetas no son comparables (19/10 = 1er deploy) | ✅ Cerrado |
| H-11 | `main.py` corre 8 celdas, no 9 | ❗ Cosmético |
| H-12 | C2 dice "Sin backups previos" ⇒ nunca restauró nada | ❗ Pendiente |
| H-13 | Métricas no agregan por `calidad_senal_v2`; escala legacy muerta | ❗ Pendiente |
| H-14 | `_get_price_at_time` puede tomar precio posterior | ❗ Pendiente |
| H-15 | Max DD con `np.cumsum` (DD de 270%, imposible) | ✅ Resuelto (ADR 004) |
| H-16 | "ganancia" con 2 definiciones (`p > ±0,05%` vs `p > 0`) | ⏸️ Medido, <1% en PF (ADR 004) |
| H-17 | Ventana hardcodeada + resúmenes de Telegram atrapados | ✅ Resuelto (ADR 006) |
| H-18 | `RESOLUTION_WINDOWS_HOURS=[4,8,24]` hardcoded | ⬜ Propuesto (ADR 007), default **[4,24]** |
| H-20 | La ventana no se respeta al 100% (16,2% fuera) | ⬜ Nuevo |
| **H-21** | `en_ventana()` con **hora entera** | 🔴 **NUEVO — bloquea H-18/H-13** |
| **H-22** | **El test de régimen NO corrió en el 71%** + `rs` es ordinal de `rvd` | 🔴 **NUEVO —>#1 técnico** |

---

## 7. LA FÓRMULA REAL DE `macro_score_v2` (verificada en código)

> `AGENTS.md` §5.1.c **no reproduce** el score real (0/914). Esta es la correcta.

### 7.1 Semántica del ADF (error histórico, ya corregido)

**`p_value_adf < 0.05` significa ESTACIONARIO, NO momentum.**
La rama momentum (p ≥ 0.05) se activa cuando la serie **no** es estacionaria.

### 7.2 Las piezas (`C3_MACRO_local.py` líneas 1484-1661)

| Pieza | Origen | Rango |
|---|---|---|
| `poc_score` | POC de la caja | {-1, +1} |
| `caja_p` | caja amplificada por volumen/ATR (`am` 0.5-2.0, líneas 1494-1496) | {-2..+2} |
| `fvg` | FVG | {-1, 0, +1} |
| `rs` | **ordinal de `rvd`** (línea 1487) | {-2,-1,0,+1,+2} |
| `d` | divergencia POC/FLUJO | {−2, 0, +2} |

```python
# línea 1487 — CLAVE: rs es un ORDINAL de rvd, NO el CVD crudo
rs = 2 if rvd > 0.3 else (1 if rvd > 0.1 else (-2 if rvd < -0.3 else (-1 if rvd < -0.1 else 0)))
```

### 7.3 Las dos ramas

```python
if is_stationary:      # p_value_adf < 0.05
    ms_v2 = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
else:                  # rama momentum
    ms_v2 = 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs

s_mtf = 0.30*bias_1h + 0.20*bias_4h + 0.15*bias_1d
d = -2.0 if (poc == 1 and rs <= -1) else (+2.0 if (poc == -1 and rs >= 1) else 0.0)
macro_score_v2 = round(ms_v2 + s_mtf + d, 2)
```

### 7.4 `d` NO es degenerado (refutado el 26/10)

`d` se activa cuando `|rvd| > 0.1` **y el POC está del lado opuesto al flujo**
⇒ es una **divergencia precio/flujo real**, con umbral FIJO (sin calibrar).
**No se elimina.** Una revisión externa lo marcó como degenerado por leer el
nombre de la variable `score_desglose["cvd_crud"]`, que es engañoso.

### 7.5 El score LEGACY (el que tiene el sesgo) — `línea 1500`

```python
ms = poc_score + caja_p + fvg + rs          # pesos 1,1,1,1
```
```python
# líneas 1502-1510
if abs(ms) >= STRONG_BIAS_THRESHOLD and rs == 0:   bv, bi = "RANGO", "NOISE"
else: bv = "BULL" if ms >= STRONG_BIAS_THRESHOLD else ("BEAR" if ms <= -STRONG_BIAS_THRESHOLD else "RANGO")
```
`STRONG_BIAS_THRESHOLD = int(_get_macro_param("STRONG_BIAS_THRESHOLD", 2))` — **línea 260**.

**⇒ El filtro real de emisión es `|ms| >= 2` Y `rs != 0` ⇔ `|rvd| > 0.1`.**
**⇒ Y como `rs` pesa 1, `rs = ±2` (rvd > 0,3) ya alcanza el umbral solo
⇒ en la práctica el filtro es "`rvd` > 0,3" (o < −0,3).**

### 7.6 Dos rutas silenciosas que devuelven 0.0
- líneas 1603-1605: `if not isinstance(desglose, dict): return 0.0`
- líneas 1659-1661: `except(...): logger.debug(...); return 0.0`

### 7.7 `score_desglose` real (líneas 1544-1552)
```
poc · caja · caja_raw · atr_multiplier · fvg · cvd_crud(=rs ordinal) · rvd_ultimo
```

---

## 8. H-9 CERRADO — el diagnóstico completo

### 8.1 El veredicto

**El `macro_score_v2` NO tiene poder predictivo demostrado. NO-GO.**
- ρ(`macro_score_v2`, pnl_24h) = **+0,119** dentro de RANGE ⇒ no separa.
- HR por cuartil de score: 65,5% / 53,3% / 82,8% / 63,3% ⇒ **no monótono**.
- El único efecto real es **régimen + tiempo + grano de ciclo**.

### 8.2 La reconciliación de los 914

| | n | Cuándo | Qué es |
|---|---|---|---|
| `macro_score_v2 = 0.0` **exacto** | **768** | 13/10 – 19/10 | **PRE-DEPLOY — NO es un bug vigente.** `data_quality_emision`=OK en las 768 |
| `macro_score_v2` **real** | **146** | 19/10 – 23/10 | 4 días de datos |

⇒ Antes del 19/10 el score era un placeholder `0.0` (v7.9.3 lo volvió real).
⇒ **Son dos poblaciones. No se mezclan.**

### 8.3 🔴 El hallazgo de H-22: el test de régimen NO corrió en el 71%

```python
# C3_MACRO_local.py 1901-1925
p42 = 1.0     # default
p50 = 1.0     # default
try:
    p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
    p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
except _C3_EXC as exc:
    logger.warning(f"C3 ADF/FFD fallback {coin}: {exc}")
# línea 1937:  "p_value_adf": p42
# línea 2331:  dual = p42 <= _T_ADF_THR and p50 <= _T_ADF_THR
```

**⇒ Los `p_value_adf = 1.0` EXACTOS (648 de 914 = 71%) NO son un p-value:
son el DEFAULT de la línea 1901 cuando la función lanza excepción.**
**⇒ En el 71% de las señales no se corrió ningún test de régimen.**

**Consecuencia fatal:**
> "El score v2 se calcula sólo en régimen estacionario fuerte (p<0,001)" → **FALSO**.
> Es "en los casos donde el ADF **no falló** y además dio p<0,001".

⇒ **Las 146 señales con score real son un SUBMUESTRO SELECCIONADO POR ÉXITO DEL TEST.**
⇒ **NO se puede "activar/desactivar" el score a posteriori.**
⇒ **El OOS tiene que ser PROSPECTIVO: emitir siempre, registrar el score, decidir después.**

⇒ Y el motivo de los 648 fallos **se perdió** porque los logs se sobrescriben
(39 líneas). De ahí que "dejar de sobrescribir logs" (A4) sea prerrequisito.

### 8.4 Lo que SÍ funciona (no romperlo)

- **El sesgo multi-TF funciona.** `gem_macro_snapshot` da N/A sólo **5,6% (1D)**,
  **5,8% (4H)**, **0% (15m)**. La idea de "s_mtf = 0 por N/A" era **falsa**.
- `riesgo_regime` real: **NEUTRAL 83,4% / RISK_ON 13,0% / RISK_OFF 3,6%**
  (NO era RANGE/TREND).
- `macro_audit_log.bias`: **RANGO 62,3% / BULL 18,7% / BEAR 18,7%** / N/A 0,2%.
- El **score v2 está normalizado**: `caja_p` ya se escala por ATR y `rs` es un
  ordinal acotado ⇒ **es comparable entre activos** (la "contaminación por
  escala" era un error de lectura).

### 8.5 El grano de ciclo

- 146 señales → **25 ciclos** (mediana 6 señales por ciclo).
- **3 ciclos del 20/10 con HR 0,0%. 3 ciclos del 21/10 con HR 85-89%.**
- ⇒ **El día es el grano equivocado. El ciclo es el correcto.**

### 8.6 El percentil por activo (el único fix con evidencia, y es débil)

ρ(ms2, pnl24) por percentil **dentro de cada activo**: **+0,192 y monótono**
(51,5% / 64,7% / 69,7% / 76,5%). Pero **5 de 12 activos con ρ negativo**
(XRP −0,34 · GOLD −0,30 · SILVER −0,44 · SP500 −0,42 · XYZ100 −0,44) con n=9-14
⇒ nada significativo. ⇒ **Segregar cripto vs índices/metales** (B2).

### 8.7 La hipótesis de "score = volumen" — REFUTADA

ρ(|ms2|, |cvd_raw_ultimo|) = **+0,015** (nulo). El |cvd| medio varía **2476×**
entre activos (BTC 3.220 … XRP 4.457.653) mientras el ms2 medio va de −3,5 a +2,26
⇒ **el `rs` que entra YA está normalizado. NO tocar la normalización del flujo.**

### 8.8 Métricas globales (24h, 877 resueltas del 23/10)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| GLOBAL | 877 | 44,7% | 0,80 | −0,156% |
| **LONG** | 429 | 32,4% | **0,50** | −0,488% |
| **SHORT** | 448 | 56,5% | **1,28** | +0,163% |
| xyz:SILVER | 58 | 63,8% | 3,22 | +0,768% |
| xyz:GOLD | 93 | 51,6% | 2,64 | +0,309% |
| BTC | 64 | 23,4% | **0,30** | −0,630% |
| xyz:SP500 | 88 | 39,8% | **0,28** | −0,351% |

**Asimetría confirmada por 3 métodos independientes:** MFE/MAE (LONG payoff
**−2,9:1** · SHORT **1,75x**) · movimiento contrario primero (LONG **54,0%** vs
SHORT 34,3%) · PF por tipo (0,50 vs 1,28).
**El k×σ (ADR 001) no lo arregla: el PF no depende del break-even.**

**Timing real:** FAVOR 363 / CONTRA 512 / NEUTRO 39 · HR 24h FAVOR **67,2%**
vs CONTRA 27,5%. σ por señal mediana **1,1458%** ⇒ el umbral fijo 0,05% ≡
**k = 0,044σ** (22× más severo en el activo más volátil).

### 8.9 El único dato de eficacia — y es INCONSISTENTE

| Población | LONG + BULL | SHORT + BEAR |
|---|---|---|
| pre-deploy (768, 13–19/10) | HR 35,6% · PF 0,52 | HR 57,8% · PF 1,27 |
| post-deploy (146, 19–23/10) | HR 73,7% · PF 9,24 | HR 59,7% · PF 1,87 |

**⇒ No se puede decidir con datos retrospectivos. Sólo con n suficiente (OOS).**

### 8.10 La distribución horaria (hora Caracas)

| Hora | HR 4h | n | ¿En 04:00-16:00? |
|---|---|---|---|
| 08:00 | 7,1% | 14 | **SÍ — la peor hora** |
| 09:00 | 40,0% | 10 | sí |
| 10:00 | 20,0% | 10 | sí |
| 13:00 | 23,5% | 17 | sí |
| 14:00 | 30,0% | 20 | sí |
| 15:00 | 55,6% | 18 | sí |
| 16:00 | 33,3% | 18 | no |
| **20:00** | **76,0%** | **25** | **NO — la mejor franja** |
| 21:00 | 0,0% | 7 | no |

**⇒ El recorte 04:00-16:00 conserva la peor hora y descarta la mejor.**

---

## 9. La segunda opinión (26/10) y sus 3 correcciones

Se le pasó un **prompt adversarial** (`PROMPT_VALIDACION_ADVERSARIAL_MACRO2.1.md`,
v3, 39 KB) con anti-confirmación explícita, 10 preguntas, ≥8 citas nuevas y
semáforo 🟢/🟡/🔴 por subdivisión. La respuesta fue un informe de 617 líneas
(`/workspace/attachments/64dac675b065ed93/`) — **con los números convertidos
en `![][imageN]` por un bug de rendering del agente que lo escribió**; los
números hay que reconstruirlos desde nuestro propio output.

**Lo que la revisión acertó:**
- NO-GO del score como predictor. ✔ confirmado con datos propios.
- `cycle_id` = prioridad 1. ✔
- Rate limit = prioridad 2. ✔
- `d` degenerado. ✘ **CORREGIDO (era el nombre engañoso de la variable).**
- FVG / caja sin edge. ✔ (el v2 los sube de peso, sin evidencia).
- Agrupar por ciclo. ✔
- Harvey-Liu-Zhu, t > 3,0. ✔ (RFS 29(1):5-68).
- **Lista negativa de gobierno** ✔ (adoptada, 8 afirmaciones).
- **Criterio de muerte explícito (NO-GO ⇒ clausura)** ✔ (adoptado, ADR 012).

**Sus 3 errores (corregidos el 26/10):**
- **E1** — mezcló **Caracas con UTC**. La ventana acordada es Caracas (UTC−4).
  Su conclusión "migrar a VPS por las 20:00" quedaba sin base…
  **PERO** la franja de las 20:00 Caracas está FUERA de la ventana 04-16 y la de
  las 08:00 está DENTRO ⇒ ⇒ el recorte quita la mejor y conserva la peor.
  **Resolución ⇒ ADR 011 (ventana 19 h en Render, 78% del tier, sin VPS).**
- **E2** —淹 tomó `cvd_crud` como si fuera el CVD crudo.
  **Resolución: `rs` es un ordinal de `rvd` (línea 1487).** Mi medición (ρ ≈ 0)
  era la correcta. ⇒ ⛔ `d` NO es degenerado.
- **E3** — usó `arXiv:2607.09230` (Jeon, U. Korea, 10-jul-2026) al revés: el
  paper es real pero trata transiciones de estado L2→1-5 min, **no** precios a
  4h-24h. Su tesis real es **"state-first"** (el estado es el predictor de
  primer orden; cada capa sólo se acredita si aporta incremental), que **sí**
  respalda el NO-GO estructuralmente. **Su diseño (OOS enrollado, event-clustered,
  blocked permutation tests) es el que hay que montar.**

---

## 10. El plan: Track A / B / C

### TRACK A — EFICIENCIA (va primero y completo)

| # | Qué | Métrica |
|---|---|---|
| **A1** | **Rate limit.** 1344 req/min > 1200 ⇒ **429** ⇒ el ritmo bajó de **25-30 a 4-8 corridas/día** (señales/día ~120 → ~30). 18 eventos 429 en los logs. Cache de velas (TTL > 15 min) + WS + backoff + reducir TFs | **0 × 429** y **≥ 60 corridas/día** |
| **A2** | **`cycle_id`.** C3 inserta `cycle_id="PRE_REGIME"` (~línea 2045) y C3.5 no lo completa, aunque `zonas["macro_cycle_id"]` existe (1534) ⇒ join señales↔snapshot = **0/914** | **100% match** |
| **A3** | **`data_quality`.** `data_quality_status` no existe ⇒ el dict real es `zonas["data_quality"]["estado"]` ⇒ siempre NULL | ≠ NULL |
| **A4** | **Logs sin sobrescribir.** Hoy 39 líneas | historial |
| **A5** | **`duration_seconds` real.** La columna existe pero no mide duración | correcto |
| **A6** | **Red de seguridad del score.** 2 rutas silenciosas que devuelven 0.0 | 0 fallos mudos |
| **A7** | **Ventana 19 h** (ADR 011): 04:00-23:00 = 589 h/mes = **78%** del free tier, y captura las 20:00 | margen ≥ 20% |
| **A9** | **Renombrar `score_desglose["cvd_crud"]` → `rs_ordinal`** | sin ambigüedad |
| **A10** | **`p=NULL` + `regimen_test_ok`** en vez de `p=1.0` default (ADR 008) | 0 "p=1" indistinguibles |

**⇒ ¿Por qué A1 primero?** Porque A1 es lo que pasa de 4-8 a 60+ corridas/día, y
con 60 el grano de ciclo se multiplica ⇒ el OOS se vuelve posible.
**A0 sin A1 es medir con una cuchara de madera.**

### TRACK B — EFICACIA (congelada)

| # | Qué | Nota |
|---|---|---|
| **B0** | **Congelar `macro_score_v2` Y `bias_visual`** (ADR 009) | 4 días de datos = data snooping |
| **B1** | **Invertir la polaridad del régimen** (`p<0,05` ⇒ `p>0,05` como condición de emisión) | **prospectivo**, en T₀. n=11 no la justifica a ciegas |
| **B2** | **Segregar cripto vs índices/metales** | percentil monótono en cripto, negativo en índices/metales |
| **B3** | `direccion_v2` **sin `abs()`** | etiqueta invertida: RUIDO HR 71,4% > FUERTE 64,7% |
| **B4** | Eliminar `d` · FVG y caja a peso 0 | ⛔ **CANCELADO** (`d` no es degenerado). Sólo después del veredicto |

### TRACK C — PROTOCOLO OOS (ADR 012, se escribe ANTES de T₀)

- **Unidad = CICLO.** No señal, no día.
- **N y M escritos antes** de empezar. Ventana: **30 días**.
- **Benchmark aleatorio** con el MISMO perfil (n, tipo, hora).
- **BH-FDR + t > 3,0** (Harvey-Liu-Zhu 2016).
- **Prospectivo**: desde T₀ se emite siempre y se registra todo.
- **T₀ = fecha del deploy con el Track A listo.**
- **NO-GO ⇒ clausura definitiva.**

**⇒ La pregunta del OOS NO es "¿el score v2 predice?"**
**⇒ Es: _"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"_**

---

## 11. La lista negativa (8 afirmaciones prohibidas)

**Si una de estas aparece en un análisis, un chat o un commit, está mal.**

1. ❌ "El `macro_score_v2` tiene poder predictivo." — ρ = +0,119. NO-GO.
2. ❌ "El sesgo multi-TF no funciona." — N/A sólo 5,6% / 5,8% / 0%. **Funciona.**
3. ❌ "El score se calcula en régimen estacionario fuerte." — Se calcula donde el test **no falló** (71% no corrió).
4. ❌ "El score v2 está contaminado por la escala del volumen." — `caja_p` ya está normalizado por ATR; `rs` es un ordinal acotado.
5. ❌ "El término `d` es degenerado / hay que eliminarlo." — Es una divergencia precio/flujo real.
6. ❌ "El score v2 es una regresión por usar `cvd_crud` en vez de `rvd_ultimo`." — `rs` **ya** es un ordinal de `rvd`. El problema es otro: el v2 sube caja/fvg y baja el flujo.
7. ❌ "MACRO2.1 es un bot de trading." — Es predictor + validador.
8. ❌ "Se puede comparar HR/PF entre etiquetas o ventanas sin cortar por día." — Y el grano correcto es el **ciclo**.

---

## 12. El próximo paso exacto

**Manual (usuario), prioridad #1:**
```cmd
xcopy "C:\Users\MD\Desktop\MACRO2.1_BACKUP\*" "G:\Drive\MACRO2.1_BACKUP\" /E /Y
```
(ajustá la unidad; **verificá que el .db abre bien**).

**Código, en este orden:**
```cmd
python fixes\actualizar_gobierno_h22.py --aplicar
python verificar.py
python git\guardar.py "gobierno H-22: H-9 cerrado, H-22 (ADF falla 71%), ADR 008-012, RELEVO_IA"
git push origin main
```
**Después:** A1 (rate limit) → A2 (`cycle_id`) → A3 (`data_quality`) → A0 (test de
régimen) → A4/A5/A6 → A9 → A7 (ventana 19 h) → **H-21** → **H-18** → **H-13**.

**Y en paralelo, antes de T₀:** escribir el protocolo OOS (ADR 012) con N y M
concretos en `docs/PENDIENTES.md`.

---

## 13. Trampas (historia de errores — no repetirlas)

- **CMD.exe únicamente.** Sin PowerShell, sin `curl`/`wget` unix, sin `&&`, sin `;`.
- **`more` y `type` CUELGAN la consola** (el usuario pegó Ctrl+C y se le reinició
  el historial). Para volcar: `findstr /n "patron" archivo` o `> dump.txt`.
- **UTF-8 en consola china/ANSI → mojibake** (`—` → `ÔÇö`). Anclar con ASCII puro.
- En Python, un `''` sin escaping dentro de un string SQL rompe:
  `no such column: senales_validadas` / `no such column: ANTES`. Usar `?`.
- `findstr` con acentos no funciona ⇒ buscar por palabras ASCII.
- Los scripts de git **siempre en Python**.
- `git rm --cached <file>` saca del índice sin borrar del disco (usado con `timing_real.json`).
- `verificar.py` es el gate. Si falla, no se avanza. (Bug corregido: ADR 003
  estaba duplicado ×4 y ADR 004 nunca se chequeaba.)
- **Errores ya pagados en scripts de análisis** (no los repitas):
  `TypeError: unsupported operand type(s) for -: 'str' and 'float'` (índices de
  columnas) · `NameError: name 'metricas'/'s'/'rho_pct' is not defined` ·
  `SyntaxError: unmatched ')'` · `SyntaxError: invalid character '，' (U+FF0C)`
  · `TypeError: can only concatenate list (not "str") to list` ·
  `IndentationError` · `AttributeError: type object 'DB' has no attribute 'exists'`
  · tupla inmutable (`s["PCT"]`) · identificador CJK `找` accidental ·
  **shadowing de `DB`** · histograma demasiado granular (884 valores p distintos).
- **SQL no anida `AVG`** en SQLite ⇒ las correlaciones Pearson se calculan en Python
  (regresión OLS a mano con Gauss-Jordan, sin numpy, para no depender de paquetes).
- **Typo real del proyecto:** la columna es `data_quality_emision` (**una** "s").

---

## 14. Los scripts de análisis (en `analisis/`)

| Script | Qué responde |
|---|---|
| `diagnostico_h9.py` | Schema, 23 tablas, distribución horaria, persistencia de C4 |
| `descomponer_score_v2.py` | Join v1→v2: `senales_validadas` × `macro_audit_log` por `cycle_id`+`activo` (914/914). El join con `gem_macro_snapshot` = **0/914** (por eso `macro_audit_log` es la fuente de verdad) |
| `poder_predictivo_score_v2.py` | OLS a mano, HR/PF por cuartil, Spearman, por rama/calidad/tipo/activo |
| `reconstruir_score_v2.py` | §§1-6: ramas, bias, riesgo, día, diario, agrupación del residuo, escalas, tabla 2×2 tipo×bias (0 contradicciones), horizonte 4h |
| `reconciliar_score_cero.py` | v2 con §§7-11: reconciliación 768/146, régimen vs score, HR pre-deploy por `p_value_adf`, grano de ciclo, test percentil-por-activo, test de volumen |
| `analisis_timing_real.py` | v2: timing FAVOR/CONTRA/NEUTRO, MAE/MFE, σ por señal |
| `diagnostico_h10_h18.py` | Schema + distribución horaria + cómo persiste C4 las resoluciones |
| `rescore_umbral_v2.py` | Re-score con corte por día y por subgrupo |

---

## 15. Conceptos verificados (para no alucinar)

Verificados por búsqueda durante el diagnóstico del 26/10:

- **ADF:** `p < α` ⇒ **estacionario** (no momentum). Los niveles de cripto son
  I(1). ADF y KPSS pueden discrepar. **Mín ~500 obs** para ADF, ~1000 para Hurst.
  La microestructura genera anti-persistencia espuria. FDR por múltiples tests.
- **OFI (Cont-Kukanov-Stoikov):** predictivo a **50 ms – 5 min**, R² ~65%.
  ⇒ **A 24h no hay garantía de que el flujo prediga.**
- **FVG:** 83,4% de fill vs 83,5% de baseline aleatoria; **0 de 54** rentables
  tras costes.
- **Hyperliquid:** 1200 request-weight/min/IP · `info`=20 · `candleSnapshot` +1/60
  items · si estás limited, **1 request / 10 s** · `candleSnapshot` devuelve **máx
  5.000 velas** ⇒ 1m=3,5 d · 5m=17 d · 15m=52 d · 1h=208 d · 4h=2,3 años ·
  1d=13,7 años · WS: 10 conexiones / 1000 subs / 2000 msg/min · HIP-3 con
  prefijo `xyz:` (funding/OI desde 16-feb-2026) ·
  `s3://hyperliquid-archive` **sin garantía de completitud** ⇒ **el OBI no es
  reconstruible del histórico** ⇒ `rvd` es un *proxy* del order flow.
- **Harvey-Liu-Zhu (2016)**, *RFS* 29(1):5-68 ⇒ con múltiples tests, **t > 3,0**.

---

## 16. Glosario

| Término | Qué es |
|---|---|
| **C0→C4** | Las 5 celdas del pipeline (§4) |
| **Emitir / Confirmar / Resolver** | C3 emite · el confirmation filter confirma · C4 resuelve |
| **poc / caja / fvg** | Point of Control / rango de caja (amplificado por volumen) / Fair Value Gap |
| **rvd** | *Relative Volume Delta* — flujo relativo suavizado. `rs` es su ordinal |
| **cvd** | Cumulative Volume Delta. `cvd_raw_ultimo` es el valor crudo (millones) |
| **ADF / FFD** | Augmented Dickey-Fuller / Fractionally Differenced (con `d` óptimo) |
| **HR / PF / E** | Hit Rate / Profit Factor / Expectancy |
| **MAE / MFE** | Adverse/Favorable Excursion — **timing**, no P&L |
| **Ciclo** | Un ciclo de emisión del bot. La unidad de evaluación del OOS |
| **GO / NO-GO** | Veredicto del OOS. NO-GO ⇒ clausura |
| **Track A/B/C** | Eficiencia / Eficacia / Protocolo (§10) |
| **ADR** | Architecture Decision Record, en `decisiones/` |
| **T₀** | Fecha del deploy con Track A listo. Empieza el OOS |

---

## 17. Índice de commits

| Commit | Qué |
|---|---|
| `5361b4f` | Umbral ADF unificado, backups/logs, kit de git, verificar.py |
| `5e0c481` | Sin Docker, docs reordenadas, scheduler lee PORT |
| `da0ad11` | verificar.py con 19 checks |
| `23efea4` | limpieza de `fixes/` y `analisis/` |
| `a78726b` | **H-17** — ventana configurable (13 parches) |
| `cadcec1` | Gobierno H-17 + ADR 005/006 + fix 8-17 |
| `6a5a37a` | Ritmo 1-4 + verificar.py (ADR 003 duplicado, ADR 004 sin chequear) |
| `31e6cd3` | **H-18 / H-10 cerrado / H-20 / ADR 007** |
| (este) | **Gobierno H-22** — H-9 cerrado, H-22, ADR 008-012, este RELEVO |

---

## 18. Una cosa más

**La recomendación del GEM de usar FastAPI (no Django) queda para después.**
Ahora no: primero que el bot funcione, después la infraestructura.

Y una regla de la casa que se ganó en el camino:
**cuando la evidencia contradice la hipótesis, la hipótesis pierde — no los datos.**
El 26/10 se cayó el score v2 como predictor, se cayó el "d es degenerado" de la
revisión externa, y se cayó la idea de que la ventana 8-17 era neutra.
Eso es el proyecto avanzando, no retrocediendo.
