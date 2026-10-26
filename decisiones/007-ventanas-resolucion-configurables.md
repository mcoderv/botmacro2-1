# ADR 007 — Ventanas de resolución configurables (H-18)

- **Estado:** PROPUESTO (no aplicado)
- **Fecha:** 2026-10-26
- **Alcance:** `C4_SENIAL_VALIDATOR.py`, `C1_5_PARAM_local.py`,
  `config/CONSOLIDADO/central_params.json`, y la migración de
  `senales_validadas`.
- **Problema:** H-18.

## Contexto

`C4_SENIAL_VALIDATOR.py:56` tiene:

```python
RESOLUTION_WINDOWS_HOURS: List[int] = [4, 8, 24]
```

Cada señal se resuelve (mide su PnL) a **3 horizontes**: 4h, 8h y 24h.

**Por qué es un problema:** con 3 cortes no se ve la **trayectoria** del
precio después de la señal. No se puede saber *cuándo* se movió a favor o en
contra ⇒ **no se puede medir el timing temprano**, que es justamente lo que
hace falta para matar el look-ahead del análisis actual (el timing se calcula
sobre la trayectoria completa hasta el horizonte ⇒ correlaciona con el PnL
final por construcción).

El GEM ya lo propuso como *"validación escalonada (4→8, 12→16)"*.

## Estado real medido (diagnóstico del 24/10)

El almacenamiento **NO es uniforme**:

| Dónde | Cómo persiste | ¿Genérico? |
|---|---|---|
| `senales_metricas` | columna `ventana TEXT` + el valor `f"{ventana}h"` | ✅ **SÍ** |
| `senales_validadas` | **columnas fijas**: `precio/pnl_pct/resultado/hit/resuelto_4h`, `_8h`, `_24h` = **15 columnas** | ❌ **NO** |

**⇒ Pasar de 3 a 6 ventanas exige +25 columnas en `senales_validadas` y una
migración de schema.** (Las métricas no necesitan nada: ya son genéricas.)

El proyecto es **schema-less con migraciones aditivas e idempotentes**
(documentadas en el banner de cada celda, ej. `C2_BOVEDA_local.py` v8.5), así
que la migración es viable — pero hay que hacerla bien: `ALTER TABLE ... ADD
COLUMN` por cada columna nueva, en el `CREATE`/`_migrar` de C2.

## Decisión (PROPUESTA)

1. `RESOLUTION_WINDOWS_HOURS` deja de ser una constante y pasa a leerse de
   `CENTRAL_PARAMS["validation"]["RESOLUTION_WINDOWS_HOURS"]`, con default
   `[4, 8, 12, 16, 20, 24]`.
2. `C4` genera las columnas dinámicamente a partir de esa lista
   (`f"pnl_pct_{ventana}h"`), como ya hace con las métricas.
3. La migración de `senales_validadas` añade las columnas de 12h/16h/20h
   (5 columnas × 3 ventanas) de forma **aditiva e idempotente**.
4. `estado = 'RESUELTA'` sigue mandando la **última** ventana (24h), que es
   la de mayor horizonte.

## Consecuencias

**A favor:**
- 6 puntos de trayectoria por señal ⇒ se puede medir el timing a 1h, 2h, 3h…
  ⇒ **el look-ahead se puede eliminar** y el ADR 005 queda evaluable.
- Coherente con el ADR 006 (todo configurable, sin hardcodes dispersos).
- 6 cortes cada 4h cubren las 24h ⇒ con la ventana operativa en 24/7, cada
  señal tiene su trayectoria completa.

**En contra / a tener en cuenta:**
- **Migración de schema** (25 columnas nuevas) ⇒ hay que hacerla bien y
  documentarla. Riesgo de romper C2/C4.
- **3× más resoluciones por señal** ⇒ más trabajo de C4 y más filas en
  `senales_metricas` (1450 filas ahora).
- **Sin backfill:** las 914 señales actuales SOLO tienen 4/8/24. Los snapshots
  de precio viejos ya no existen en `price_snapshots` ⇒ **12/16/20 arrancan en
  cero** desde el día que se active. Eso no es un bug: es la línea base.
- **Cambia el régimen de datos otra vez** ⇒ igual que con la ventana operativa,
  hay que **cortar por fecha** en todo análisis posterior.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Dejar `[4, 8, 24]` y medir el timing de otra forma | El timing temprano necesita snapshots intermedios; con 3 cortes solo hay 2 puntos previos al horizonte. |
| Agregar solo 12h y 20h (5 cortes) | Arbitrario. 6 cortes a 4h de espaciado cubren las 24h simétricamente. |
| Una tabla nueva `senales_resoluciones` en vez de columnas | El schema es **schema-less con columnas**, no relacional. Una tabla nueva obligaría a reescribir todo el consumo de métricas y reportes. Inconsistente con el resto del proyecto. |
| Hardcodear `[4, 8, 12, 16, 20, 24]` en C4 | Reintroduce un hardcode disperso, que es exactamente lo que el ADR 006 vino a eliminar. |

## Cómo se verifica

```cmd
python verificar.py
```
⇒ 19 ok / 0 fallas / 1 aviso, **y** un check nuevo que confirma que las
ventanas del JSON coinciden con las de C4.

```cmd
python -c "import sqlite3;c=sqlite3.connect('data/vault_v2.1.db');print([r[1] for r in c.execute('PRAGMA table_info(senales_validadas)')])"
```
⇒ deben aparecer `pnl_pct_12h`, `pnl_pct_16h`, `pnl_pct_20h` y sus columnas.

## Referencias

- `analisis/diagnostico_h10_h18.py` (schema + cómo persiste C4).
- ADR 006 (ventana operativa configurable).
- `AGENTS.md` §7 (tabla de umbrales).