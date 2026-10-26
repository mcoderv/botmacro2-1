# ADR 008 — Un test que falla no puede dejar un valor por defecto

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