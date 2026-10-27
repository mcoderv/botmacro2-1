# ADR 016 — Qué es "tendencia" en este proyecto

- **Estado:** PROPUESTO (decisión tomada; falta implementación)
- **Fecha:** 2026-10-27
- **Alcance:** `C3_5_REGIME_ENGINE.py` (clasificación TREND_UP / TREND_DOWN / RANGE).
  No toca el score ni el sesgo multi-TF.
- **Problema:** B1 del `HANDOFF.md` ("el umbral de tendencia es imposible de pasar").

## Contexto

La regla vigente es un número fijo:

> se ajusta una recta al logaritmo del precio sobre las **últimas 20 velas** de 1 h;
> si la pendiente supera **0,0012 por vela** (≈ 2,88% por día) el régimen es TREND;
> si no, es RANGE.

Ese mismo 0,0012 se aplica a los 12 activos, sin mirar cuánto se mueve cada uno.

**Medido el 2026-10-27 sobre la base real (1 ciclo, 12 activos, ver `HANDOFF.md`):**
12 de 12 dieron RANGE, y el activo con mayor pendiente llegó al **63,2%** del umbral.
De las 12 filas del motor, **12 vinieron de la rama "deriva baja"** y **0** de la rama
"estacionaria" (el ADF dio p entre 0,0819 y 0,8964, nunca ≤ 0,05).

## La medición que decide este ADR

Script: `analisis/medir_regla_tendencia.py` (solo lectura; baja velas de la misma API
que usa el motor, descarta la vela abierta).

Se compararon cuatro reglas sobre **200 paseos aleatorios sin deriva** (a tres niveles
de volatilidad) y sobre **12 activos reales** (720 velas cripto / 1.440 TradFi).

### Tasa de falsos positivos (declarar TREND cuando no hay tendencia)

| σ por hora | R1 actual (umbral fijo) | R2 deriva ÷ σ | R3 t sobre el **precio** | R4 t sobre los **retornos** |
|---|---|---|---|---|
| 0,001 | 0% | 0% | **88%** | 3% |
| 0,003 | 9% | 0% | **88%** | 3% |
| 0,006 | **43%** | 0% | **88%** | 3% |

### Datos reales (2026-10-27, n = 12 activos)

| Dato | Valor |
|---|---|
| σ diaria | 0,31% (`xyz:EUR`) a 4,13% (`AVAX`) ⇒ **13,5×** entre activos |
| deriva diaria | −0,83% a +0,14% |
| deriva ÷ σ (máximo) | **0,27** |
| `|t|` sobre retornos (máximo) | **1,8** |
| Activos TREND por regla | R1 **0/12** · R2 **0/12** · R3 **12/12** · R4 **0/12** |

### Los cuatro hallazgos

1. **El umbral fijo no tiene una tasa de error: tiene una por activo.** 0% en un activo
   calmo, 43% en uno volátil. Es el defecto estructural de un número absoluto.
2. **El test sobre el precio es inválido.** 88% de falsos positivos con cualquier
   volatilidad: el precio no es estacionario (regresión espuria). Queda descartado
   como implementación del "camino 2" que proponía el handoff.
3. **El test sobre los retornos sí tiene la tasa que declara:** 3% con nivel 5%.
4. **Hoy no hay tendencia en ningún activo.** La deriva más grande es un cuarto del
   ruido diario. Por lo tanto **"12/12 RANGE" no prueba por sí solo que haya un bug**:
   lo que prueba el bug es la regla, no la etiqueta de hoy. Arreglarla **no** va a
   hacer aparecer señales de tendencia en este momento del mercado.

## Decisión

1. **TREND significa "la deriva es estadísticamente distinguible de cero"**, medido
   sobre los **retornos logarítmicos** de la ventana que el motor ya descarga
   (30 días cripto, 60 días TradFi).
2. **Estadístico:** t sobre la media de los retornos, errores **HAC** (Newey-West,
   núcleo de Bartlett, rezagos ⌊4·(n/100)^(2/9)⌋), umbral **|t| > 1,96**
   (α = 0,05, dos colas), **fijado antes de mirar los datos**.
3. El **signo** de la deriva define `TREND_UP` / `TREND_DOWN`.
4. **Se retira** `TREND_SLOPE_THRESHOLD = 0.0012`.
5. **La rama estacionaria del ADF no cambia:** p ≤ 0,05 ⇒ RANGE, como hasta ahora.
   Este ADR no toca el ADR 002 ni el umbral de ADF.
6. **La magnitud se sigue registrando** (deriva diaria y σ diaria) para poder auditar,
   pero **no** es la etiqueta.
7. **El horizonte de la etiqueta queda declarado:** es la ventana de la regla
   (30 / 60 días). No es un pronóstico ni coincide con la ventana operativa 8–16.

## Lo que este ADR NO decide

- **La confianza.** Hoy el motor asigna 100% fijo al régimen elegido
  (`C3_5_REGIME_ENGINE.py`, bloque de probabilidades). Mientras eso siga así, la
  **calibración** —uno de los tres números con los que se define "confiable"— no se
  puede medir. Va como ADR aparte.
- **El contador de fallos** que pide el ADR 008 §5 (que un fallo de escritura deje de
  ser un aviso mudo). Ya no pierde datos (H-24), pero el fallo sigue siendo invisible.
- **El score y el sesgo multi-TF**, congelados por el ADR 009.

## Consecuencias

**A favor**
- La regla tiene una tasa de error **medida** (3%) y no depende de la volatilidad del activo.
- El nivel se fija antes de mirar datos ⇒ no hay calibración sobre la muestra que después
  se usa para juzgar.
- **No infla etiquetas:** hoy da 0/12 TREND, igual que la regla actual. El cambio es
  conservador, no un generador de señales.
- Permite etiquetar una tendencia moderada en un activo calmo, que hoy es invisible.

**En contra / a vigilar**
- Con 720 velas el test es potente: puede llamar TREND a derivas económicamente
  irrelevantes. Hoy no ocurre (|t| máximo 1,8), pero **hay que vigilarlo con la
  persistencia y la calibración**, no con el t solo.
- El horizonte de 30/60 días no es el de la ventana operativa. Queda explícito, pero
  quien lea la etiqueta tiene que saberlo.
- Hay que **guardar el t y la σ** usados (columnas nuevas) o recalcularlos; si no, el
  próximo análisis no puede auditar la etiqueta.

**Riesgo si no se hace:** el motor sigue sin poder etiquetar tendencia moderada, y
cualquier desbalance de etiquetas que se use para el OOS estará determinado por la
volatilidad de cada activo, no por el mercado.

## Validador

Serie sintética de control, con semilla fija:

> **tendencia moderada en activo calmo**: deriva 1,2% por día con σ horaria 0,02%.

- Código viejo: 1,2 < 2,88 ⇒ **RANGE** (no ve la tendencia).
- Regla nueva: t muy por encima de 1,96 ⇒ **TREND**.

Falla antes, pasa después. Además se conservan como regresión las cuatro series de
control de `analisis/medir_regla_tendencia.py` (tendencia fuerte, paseo aleatorio,
reversión a la media, deriva chica con ruido).

## Alternativas descartadas

- **Bajar el umbral fijo** (por ejemplo a 0,5%/día). Descartado: sigue siendo un número
  absoluto ⇒ el mismo sesgo por volatilidad, sólo movido de lugar.
- **Deriva ÷ σ con k = 1.** Correcto en escala (0% de falsos positivos, medido) pero es
  un criterio de **magnitud económica** que necesita un k elegido por alguien. Se
  conserva como **magnitud informativa**, no como etiqueta.
- **t sobre la pendiente del precio** (camino 2 del handoff, literal). Descartado por
  medición: 88% de falsos positivos.
- **Seguir con 20 velas.** Descartado: el horizonte no coincide con el ADF (30/60 días)
  y 20 horas no es "macro".

## Relación

- **ADR 002** (fuente única del umbral ADF 0,05) sigue vigente: es el otro test.
- **ADR 008** (un test no puede dejar un default): mismo principio; este ADR no lo
  resuelve.
- **ADR 009** (congelar score y sesgo): no se toca.
- **ADR 012** (protocolo OOS): el cambio se declara **antes** de T₀ y las etiquetas
  anteriores no se recalculan (no hay σ guardada para hacerlo).
