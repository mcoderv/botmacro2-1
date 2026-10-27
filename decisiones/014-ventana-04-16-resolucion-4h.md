# ADR 014 — Ventana 04:00–16:00 Caracas, resolución cada 4 h, y la ventana gobierna la emisión pero NO la resolución

- **Estado:** ACEPTADO (2026-10-27, decisión del usuario)
- **Supersede:** ADR 011 (ventana 19 h, 04:00–23:00)
- **Ajusta:** ADR 007 (ventanas de resolución configurables)
- **Relacionado:** ADR 006 (ventana configurable), ADR 012 (protocolo OOS)

## Contexto

Hasta hoy la ventana que corría en disco era **08:00–17:00 Caracas** (HORA_INICIO=8,
HORA_FIN=17 en `config/CONSOLIDADO/central_params.json`), y `ventana.py:120`
compara `VENTANA_INICIO <= hora < VENTANA_FIN` (las 17:00 ya quedan fuera).

ADR 011 proponía ampliar a **04:00–23:00** para "capturar la franja de las 20:00".
Esa franja resultó ser en gran parte el bug H-20 (el 21/10 tuvo **32 de 32**
señales fuera de ventana), así que **ADR 011 perdió su justificación**.

El usuario decide una ventana distinta, pensada para el ciclo de validación:

> "La ventana del bot que correrá en Render será de 4 am a 16 hora de Venezuela,
> sin embargo esto es configurable, ya que el bot se debe adaptar a que también
> funcione 24/7 si es el caso. En primera fase: si hay una señal de tendencia a
> las 4 am se valida si acertó a las 8 am; a las 8 am hay otra señal, se valida
> a las 12 m; etc."

## Decisión

1. **Ventana operativa por defecto: 04:00–16:00 America/Caracas** (UTC−4), 12 h.
   Sigue siendo **configurable** por `central_params.json` vía
   `python ventana.py --inicio 4 --fin 16` (ADR 006 manda).
2. **El modo `CONTINUO` (24/7) debe seguir funcionando.** La ventana es una
   política de emisión, no una limitación técnica del pipeline.
3. **Resolución primaria: +4 h**, alineada a los slots de emisión
   (04 → 08, 08 → 12, 12 → 16, …). Cada ciclo resuelve lo que vence y emite lo
   nuevo. `RESOLUTION_WINDOWS_HOURS` pasa a incluir `4` como ventana principal;
   `8` y `24` quedan como **secundarias** (no se borran: ya hay 914 señales
   medidas con ellas).
4. **La ventana gobierna la EMISIÓN, no la RESOLUCIÓN.** C4 debe resolver aunque
   esté fuera de ventana. Es un requisito, no una preferencia: con ventana 04–16
   y resolución +4 h, las señales emitidas entre 12:00 y 15:45 vencen entre
   16:00 y 19:45, es decir **fuera de la ventana**. Si el loop se duerme a las
   16:00, esas señales **nunca se resuelven** y el OOS pierde justo el tramo
   final del día.

## Consecuencias

**A favor:**
- El ciclo de validación coincide con el ritmo de emisión: cada 4 h se cierra
  una cohorte y se abre otra. Es el grano correcto para el OOS (ADR 012).
- Alinea la ventana con las 4 h del ciclo, sin bordes raros.
- Deja de arrastrar la ventana de 9 h que se había fijado por el free tier de
  Render (ADR 011 ya no aplica).

**En contra / a tener en cuenta:**
- **48 ciclos/día** (12 h × 4). Hoy corren 4–8 (por el rate limit): esto
  **multiplica por ~6 la carga**, y A1 (rate limit) pasa a ser **P0**.
- Con ~5 señales por ciclo son **~240 señales/día**. El OOS de 30 días llega a
  ~7.000 señales, pero **agrupadas en 1.440 ciclos**: la unidad de evaluación
  sigue siendo el ciclo (ADR 012), no la señal.
- La DB crece más rápido. `data/` es el único activo no recuperable de GitHub.
- Requiere separar el loop de emisión del de resolución (punto 4). Es el único
  cambio de código grande que implica este ADR.
- H-21 (`en_ventana` compara hora entera) **no molesta** con 4 y 16 enteros.

## Cómo se valida (cuando se implemente)

1. `python ventana.py --ver` muestra `04:00–16:00` y `MODO=VENTANA`.
2. `python ventana.py --continuo` y `--ver` muestran `CONTINUO` (24/7 soportado).
3. Una señal emitida a las **15:45** queda `resuelto_4h = 0` en el ciclo de las
   16:00 y pasa a `1` en el ciclo de las **19:45**, con `pnl_pct_4h` no nulo.
   **Ese es el validador discriminante**: hoy falla (el loop duerme), después
   del fix pasa.
4. `RESOLUTION_WINDOWS_HOURS` contiene `4`, y las columnas `precio_4h`,
   `pnl_pct_4h`, `resultado_4h`, `hit_4h`, `resuelto_4h` existen (ya existen).

## Alternativas descartadas

- **A) Mantener 08–17 y resolver +8 h.** Descartada: el usuario define el ciclo
  de 4 h y es el que quiere operar.
- **B) Ventana 04–23 (ADR 011).** Descartada: su justificación era la franja de
  las 20:00, que es el bug H-20.
- **C) Emitir 24/7 y no tener ventana.** Descartada por ahora: el usuario la
  quiere configurable y con default 04–16. `CONTINUO` queda disponible.
- **D) Resolver solo dentro de la ventana.** Descartada: pierde 25% de las
  señales del día (las de 12:00–15:45).
