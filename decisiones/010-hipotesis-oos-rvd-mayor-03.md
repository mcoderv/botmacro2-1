# ADR 010 — La hipótesis del OOS: el filtro real es `rvd` > 0,3

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