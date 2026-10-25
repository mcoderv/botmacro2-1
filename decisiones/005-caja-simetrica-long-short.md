# ADR 005 — Caja simétrica para compensar la asimetría LONG/SHORT (H-17b)

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