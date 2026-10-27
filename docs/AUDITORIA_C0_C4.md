# AUDITORÍA C0 → C4 — FASE 0: baseline de medición

- **Fecha:** 2026-10-27
- **Estado:** Fase 0 cerrada (baseline). Fases 1-5 pendientes.
- **Alcance:** sólo lectura sobre `data/vault_v2.1.db` (`mode=ro`). Cero escrituras.
- **Herramienta:** `analisis/auditoria_c0_c4.py` (reproducible; `--seccion Mx`).
- **DB:** 914 señales · 902 resueltas a 24h · 23 tablas · `integrity_check ok` · 0 violaciones de FK.

Este documento **no reemplaza** a `docs/RELEVO_IA.md`. Reporta lo medido, con query y n.
Cuando un número medido contradice la doc de gobierno, se marca `FLAG` y se dice qué cambia.

---

## 0. Resumen: tres conclusiones del gobierno no se sostienen

| Afirmación vigente | Medición | Veredicto |
|---|---|---|
| "648 de 914 (71%) de las señales tienen `p=1.0`: el test de régimen no corrió" (AGENTS §9, ADR 008, ESTADO, PENDIENTES A10) | **11 de 914 (1,2%)** | ❌ **Error de denominador** |
| "`data_quality` siempre NULL" (PENDIENTES A3) | 0 NULL en 914 y en 3036; hay 619 `ERROR` | ❌ **Falso** |
| "16,2% de las señales fuera de ventana" (H-20, elevado a crítico en H-23) | **48 de 914 (5,3%)** | ❌ **No se reproduce** |

**Ninguna de las tres invalida el NO-GO del score** (ADR 009/012), pero sí cambian
su justificación y el tamaño de tres correcciones del Track A.

---

## 1. FLAG-1 (P0 de documentación): el "71%" es un error de denominador

### Medición

`macro_audit_log` tiene **3036 filas = 253 ciclos × 12 activos**. `senales_validadas`
tiene **914 filas = 182 ciclos** (promedio 5 señales por ciclo).

| Universo | n | p<0,02 | p<0,05 | p=1,0 exacto |
|---|---|---|---|---|
| Filas de `macro_audit_log` | 3036 | 2317 (76,3%) | 2388 (78,7%) | **648 (21,3%)** |
| **Señales** (join `cycle_id`+`coin`=`activo`) | **914** | **893 (97,7%)** | **903 (98,8%)** | **11 (1,2%)** |
| Señales con score real (`macro_score_v2 <> 0`) | 146 | — | **146 (100%)** | **0 (0%)** |

El join está verificado: **914 de 914** señales tienen su fila de auditoría
(`SIN_FILA = 0`), así que no es un artefacto de clave.

**⇒ El 71% sale de dividir 648 (filas de auditoría) por 914 (señales).**
648/3036 = 21,3% (correcto sobre filas); 648/914 = 70,9% (mezcla universos).

**⇒ Las 648 filas con `p=1.0` pertenecen a pares (ciclo, activo) que NO emitieron
señal** — por eso no aparecen en el numerador correcto. En las señales reales el
test falló 11 veces, no 648.

### La propia doc contiene el número correcto al lado del incorrecto

- `AGENTS.md` §5.1.c punto 2: *"856 de 877 señales tienen p < 0,02"* → 97,6%.
- `AGENTS.md` §9: *"648 de 914 filas (71%)"*.

Medido: **97,7%** con p<0,02. **El 97,6% era el bueno desde el principio.**

### Qué cambia

1. **ADR 008 sigue siendo correcto como principio** ("un test que falla no puede
   dejar un default indistinguible"), pero su justificación cuantitativa cae:
   afecta a **11 señales**, no a 648. Sigue recomendándose `regimen_test_ok`,
   con otra prioridad (P2, no P0).
2. **Se cae el argumento del "submuestreo seleccionado por éxito del test"**
   (ADR 008 §Consecuencia). Las 146 señales con score real tienen **146/146**
   test válido con p<0,05.
3. **A10 baja de prioridad**: el fallo **ya está registrado** en
   `data_quality='ERROR'` (medición M2b: 619 de las 648 filas con p=1,0 son
   `ERROR`, y **0 filas tienen `ERROR` con p≠1,0**). No hace falta migración para
   saber cuándo falló; hace falta leer la columna correcta.
4. **NO dice** que el score prediga nada. El NO-GO se sostiene por ρ=+0,119.

### Lo que sí queda como problema (y es más grave)

El ADF de C3 corre sobre **residuales FFD**, que son estacionarios por
construcción. Por eso rechaza en el 98,8% de las señales (p<0,05) y el
conmutador de rama queda **fijo** en la rama estacionaria
(`0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs`).

**⇒ "El score se adapta al régimen" es falso, pero no porque el test no corra:
es porque el test no puede dar otra cosa.** Esto hay que verificarlo leyendo
`calcular_residuos_v42` / `calcular_residuos_v50_ffd` (Fase 1).

---

## 2. FLAG-2 (P2): `data_quality` nunca fue NULL

| Tabla.columna | Valores |
|---|---|
| `senales_validadas.data_quality_emision` | OK 913 · STALE 1 |
| `macro_audit_log.data_quality` | OK 2038 · **ERROR 619** · UNKNOWN 372 · STALE 7 |
| `gem_macro_snapshot.data_quality` | OK 1773 · **ERROR 627** · STALE 2 |

No existe la columna `data_quality_status` en ninguna tabla (verificado con
`pragma table_info`). Si alguna rama la lee, lee `None` — pero **el valor se
persiste igual** por otra vía.

**⇒ A3 tal como está escrito ("siempre NULL") es falso.** Antes de tocarlo hay
que ver qué escribe cada rama: si `ERROR` significa "ADF falló" (correlación
619/648) o "vela en mal estado". **No lo sé todavía** → Fase 1.

---

## 3. FLAG-3 (P1): H-20 no es 16,2%

`ventana.py:120` → `VENTANA_INICIO <= hora < VENTANA_FIN`. **Las 17:00 ya están
fuera** (por eso el `[8,17)` es la semántica correcta, y tu duda 3 queda resuelta
por código, no por convención).

| Corte | n |
|---|---|
| Dentro [8,17) | 866 |
| **Fuera** | **48 (5,3%)** |
| A las 17:00 (borde) | 9 |
| 19-21 h | 39 |

Por día, la salida está concentrada:

| Día | señales | fuera |
|---|---|---|
| 2026-10-18 | 143 | 9 |
| **2026-10-21** | **32** | **32 (100%)** |
| 2026-10-23 | 12 | 7 |
| resto | 727 | 0 |

**⇒ El "cluster 19-21 h" existe (39 señales) y el 20:00 tiene exactamente 25
—coincide con el `n=25` del HR 76%—, pero el 16,2% no.** El 21/10 es un día
entero fuera de ventana (config o scheduler), no un goteo.

**Qué cambia:** H-20 sigue siendo real, pero su magnitud es 5,3% y su forma es
"3 días puntuales", no "16% sistemático". ADR 011 sigue sin base (el argumento
era capturar la franja de las 20:00, que es mayormente el 21/10 fuera de ventana).

---

## 4. FLAG-4 (P1): A2 está mal diagnosticado

`PENDIENTES.md:48` dice que C3.5 "no completa" el `cycle_id`. Medido:

| Tabla | Namespaces |
|---|---|
| `senales_validadas` | `MACRO_*` 914 (182 distintos) |
| `macro_audit_log` | `MACRO_*` 3036 (253 distintos) |
| `gem_macro_snapshot` | **`REGIME_*` 2328 (194)** + `PRE_REGIME` 74 |

`PRE_REGIME` es **sólo el 3%**. El 97% restante fue **renombrado** por C3.5 de
`MACRO_<epoch>_<hex>` a `REGIME_<epoch>_<hex>`. JOIN señales↔snapshot = **0**.

**⇒ Reemplazar el literal `"PRE_REGIME"` deja el join en 0 igual.** El fix tiene
que tocar la reescritura de C3.5 (que además cambia el prefijo). A2 sigue siendo
P1 y sigue bloqueando "¿el régimen modula?" del OOS.

---

## 5. Etiqueta `calidad_senal_v2` (B3): invertida entre las señales con score real

Restringido a `macro_score_v2 <> 0` y resuelto a 24h (n=134):

| Etiqueta | n | wins | HR |
|---|---|---|---|
| FUERTE | 34 | 21 | 61,8% |
| MODERADA | 44 | 25 | 56,8% |
| **RUIDO** | **56** | **39** | **69,6%** |

Con el universo completo (incluyendo 768 pre-deploy con score=0 legítimo),
RUIDO baja a 43,7% (n=824) porque se le cargan las señales sin score.

**⇒ La inversión que reporta `PENDIENTES.md` B3 (RUIDO 71,4% > FUERTE 64,7%) se
reproduce con el corte correcto (score≠0), no con el global.** Pero por día se
da vuelta:

| Día | RUIDO | MODERADA | FUERTE |
|---|---|---|---|
| 10-19 | 69,2% (26) | 81,0% (21) | 100% (1) |
| 10-20 | 37,5% (8) | 16,7% (12) | 33,3% (9) |
| 10-21 | **94,1% (17)** | 80,0% (5) | 70,0% (10) |
| 10-22 | 40,0% (5) | 33,3% (6) | **71,4% (14)** |

**⇒ Con n=5-26 por celda y signo distinto según el día, esto es ruido.** No
sostiene ni "está invertida" ni "funciona". **No se puede citar en ninguna
dirección** (regla 8).

---

## 6. Los tres "regímenes" que conviven (y ninguno manda en el score)

| Dónde | Distribución |
|---|---|
| `senales.regime_state` | **RANGE 875 (95,7%)** · UNKNOWN 21 · TREND_DOWN 12 · TREND_UP 6 |
| `senales.bias_regimen` | idéntica a la anterior (misma fuente) |
| `macro_audit_log.riesgo_regime` | NEUTRAL 2532 (83,4%) · RISK_ON 396 · RISK_OFF 108 |
| `gem_macro_snapshot.regime` | RANGE 2196 (94,3%) · UNKNOWN 99 · NULL 74 · TREND 33 |

**⇒ C3.5 sigue etiquetando ~95% RANGE.** La crítica de la investigación de
régimen ("el clasificador colapsa en RANGE") **sigue vigente después del cambio
a ADF**. Y RANGE mezcla dos estados (I(0) estacionario y I(1) de deriva baja,
`C3_5:166-201`), así que el label no es una unidad de análisis.

---

## 7. Tablas muertas y embudo

Vacías: `registro_senales`, `senales_aprobadas`, `velas_1m`, `velas_5m`,
`regime_transitions`, `trade_lifecycle_events`, `walkforward_results`,
`historial_trades`, `heartbeat_loop`, `logs_errores`.

**⇒ El embudo `registro_senales → senales_aprobadas → senales_validadas` no se
usa: las dos primeras están en 0 y las 914 están en la tercera.** Eso es
relevante para H-11 (la guarda de "señal duplicada"): hay que ver dónde escribe.

---

## 8. Resolución y métricas

| Ventana | resueltas | resueltas sin PnL | PnL sin marcar resuelta |
|---|---|---|---|
| +4h | 907 | 0 | 0 |
| +8h | 907 | 0 | 0 |
| +24h | 902 | 0 | 0 |

`macro_score_v2`: **768 exactamente 0.0** (13-18/10, pre-deploy) · 146 ≠ 0
(19-23/10) · 0 NULL. Coherente con H-10.

`senales_metricas`: 1450 filas (24h 475 · 8h 482 · 4h 493). **No tiene columna
`calidad_senal_v2`** (sólo `calidad_senal` legacy) ⇒ H-13 confirmado
estructuralmente: la tabla no *puede* agrupar por la etiqueta v2.

Etiquetas legacy: RUIDO 685 · BAJA 229 · ALTA 0 (la escala 14/8/4 es inalcanzable).

---

## 9. `price_snapshots`: el hueco que hace peligroso a H-14

1886 filas · 12 activos · 11 días · ~14 snapshots/día/activo.

| Hueco entre snapshots del mismo activo | Horas |
|---|---|
| mediana | 0,35 |
| p90 | 1,43 |
| **máximo** | **33,84** |

**⇒ Normalmente el snapshot más cercano está a ~21 min, pero hay huecos de hasta
34 h.** Con `ORDER BY ABS(...)` (H-14) eso significa que en esos huecos la
resolución puede tomar un precio hasta 34 h fuera del horizonte. El "sesgo neto
< 1%" se midió sobre el promedio; el caso peor no está acotado.

---

## 10. Logs

`logs_v2.1/mercabot_qwen.log`: **1 archivo, 38 líneas**. A4 confirmado: no hay
historial. El motivo de los 648 fallos del ADF, si alguna vez se escribió, no está.

---

## 11. Lo que esta fase NO mide (y va en la Fase 1)

1. Si `p_value_adf` sale de residuales FFD (y por eso es 98,8% estacionario).
2. Qué escribe `data_quality='ERROR'`: estado de la vela o fallo del ADF.
3. Dónde y cómo C3.5 reescribe el `cycle_id` (para el fix de A2).
4. Replicar H-14 (`ABS` vs `<=`) señal por señal.
5. `senales_metricas`: por qué 1450 filas y qué agrega cada una.
6. Los 5 fallbacks silenciosos: si alguno se dispara hoy.

---

## 12. Próximo paso

**Fase 1: C3 + C3_5.** Es donde está la pregunta del OOS. Entregable: una sección
por celda con los 5 puntos del encargo, cada corrección con su validador
discriminante.
