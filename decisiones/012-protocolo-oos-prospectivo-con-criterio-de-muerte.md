# ADR 012 — Protocolo OOS prospectivo, con criterio de muerte

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