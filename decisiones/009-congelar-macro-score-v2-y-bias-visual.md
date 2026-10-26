# ADR 009 — Congelar `macro_score_v2` y `bias_visual`

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