# ADR 004 * Curva de capital compuesta para el Max Drawdown (H-15)

- **Estado:** ACEPTADO
- **Fecha:** 2026-10-24
- **Alcance:** `report_validator.py`, `C4_SENIAL_VALIDATOR.py`
- **Problema:** H-15 (y H-16, medido pero NO aplicado - ver abajo)
- **Fuera de alcance pero en el mismo script:** H-12 (fuente única del umbral
  ADF), que es la implementación de ADR 002 y no requiere un ADR propio.

## Contexto

`report_validator.py` y `C4_SENIAL_VALIDATOR._calculate_metrics()` construían la
curva de capital así:

```python
equity_curve = np.cumsum(pnls)
peak        = np.maximum.accumulate(equity_curve)
drawdown    = peak - equity_curve
max_dd      = float(np.max(drawdown))
```

`np.cumsum(pnls)` es una **suma aritmética de porcentajes**, no una curva de
capital. La estructura pico-valle es correcta; **la curva base es incorrecta**.

Consecuencia medida: con ~900 señales, el "Max Drawdown" reportado fue de
**270.88%**, un valor imposible para una pérdida real. Lo que ese número
representa es *cuánto se movió la suma acumulada de ~900 porcentajes*, no una
pérdida de capital.

**Lo que NO se ve afectado** (verificado en el código):
- `hit_rate` -> se calcula sobre PnL individuales
- `profit_factor` -> `sum(p>0) / abs(sum(p<0))` sobre PnL individuales
- `avg_pnl`, `max_win`, `max_loss`

**⇒ H-15 es un bug de *reporting*, no de métrica de señal.** Los HR/PF del
proyecto no se ven afectados.

## Decisión

La curva de capital se construye **compuesta**:

```python
_equity = np.cumprod(1.0 + np.array(pnls, dtype=float) / 100.0)   # indice, base 1.0
_peak   = np.maximum.accumulate(_equity)
max_dd  = float(np.max((1.0 - _equity / _peak) * 100.0))
equity_curve = ((_equity - 1.0) * 100.0).tolist()   # PnL% acumulado
```

**El Max DD se calcula sobre el índice de capital (base 1.0). La curva que
consume el reporte se expresa en PnL% sobre ese capital compuesto**, que es la
unidad que el reporte ya espera: columna "PnL acumulado", color por signo y
tooltip en `%`. Exponer el índice base 100 hacía que el reporte mostrara
"+87.432%" pintado de verde cuando en realidad era una pérdida del 12.568%
(unidad equivocada + signo invertido).

**Propiedad garantizada:** el Max Drawdown así calculado **siempre cae entre
0% y 100%**. Si alguna vez se vuelve a ver un Max DD > 100%, es un bug.

### Consecuencias aceptadas

1. **La curva que consume el reporte pasa a ser PnL% sobre capital compuesto.**
   Antes era "% PnL acumulado" sobre una suma aritmética; ahora es ese mismo
   porcentaje, pero calculado con capital compuesto. La columna, el color por
   signo y el tooltip en `%` siguen siendo correctos **sin tocar el reporte**.
   Beneficio adicional: el chart de barras escala por
   `max(abs(min), abs(max))`, así que antes dibujaba una escalera de valores
   positivos hasta +270; ahora dibuja la trayectoria real del capital.
2. **Los valores históricos de `senales_metricas.max_drawdown_pct` quedan
   obsoletos**: fueron calculados con la suma aritmética. Se recalculan en la
   próxima corrida de C4. Hasta entonces, ese campo no debe usarse.
3. `report_validator.py` deja de exponer un "Max Drawdown" comparable con
   históricos previos.

## H-16 * MEDIDO, NO APLICADO (decisión diferida)

Se detectó que **"ganancia" significa dos cosas distintas** en el código:

| Métrica | Definición actual |
|---|---|
| `hit_rate`, `wins`, `losses` | `p > +0.05%` / `p < -0.05%` (umbral de break-even) |
| `profit_factor` (C4), `avg_win` / `expectancy` (report_validator) | `p > 0` |

Es decir: una señal con PnL `+0.03%` cuenta como **no-hit** en `hit_rate` pero
entra en `avg_win`, y el `expectancy` multiplica `win_rate` (definición A) por
`avg_win` (definición B). **Inconsistencia real.**

Unificar en el umbral de break-even cambia los PF históricos citados en los
documentos del proyecto. **No se aplica a ciegas:** el script
`aplicar_h15_h12.py` mide con datos reales de la DB la diferencia entre ambas
definiciones (cuántas señales caen en la banda de break-even y cuánto se mueve
el PF) y deja la decisión documentada aquí.

**Pendiente de decisión explícita** con esas cifras en la mano.

## H-12 * Implementación de ADR 002 (fuente única del umbral ADF)

Se приложен en el mismo script porque son la **misma decisión ya tomada**
(ADR 002: "fuente única 0.05"). Eran **tres** umbrales huérfanos:

| # | Dónde | Valor | Por qué era un problema |
|---|---|---|---|
| (a) | `C1_5` literal `validation` | 0.02 | Segundo umbral ADF vivo |
| (b) | `C1_5` `val_defaults` | 0.02 | `if k not in val_sec` -> se reinyectaba **en cada corrida** (el bloque `validation` existe en el JSON pero sin esa key) |
| (c) | `C3_MACRO` fallback | 0.02 | Si la key falta en `CENTRAL_PARAMS["macro"]`, el motor cae **en silencio** a 0.02 |

**El JSON sí tenía 0.05 en `macro`** (ADR 002 aplicado), pero el **literal del
código no** -> si el JSON se regenera o no es compatible por versión, el motor
volvía a 0.02 sin avisar. Por eso el fix **agrega** `ADF_P_VALUE_THRESHOLD:
0.05` al literal de `macro` y **quita** el 0.02 de los otros dos sitios.

## Impacto en el resto del proyecto

- El `verificar.py` no cambia en este ADR (la lista de ADRs se actualiza en el
  paso de gobierno).
- **No toca producción** (`botmacro`): el DATA FREEZE sigue vigente. Este ADR
  aplica únicamente al clon local `MACRO2.1`.
- Los ADR 001 (umbral k×σ) y 002 (fuente única ADF) no cambian.
