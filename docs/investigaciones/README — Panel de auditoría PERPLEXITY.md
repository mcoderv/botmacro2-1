<!-- MACRO2.1:AVISO-INVESTIGACION -->
> # ⚠️ DOCUMENTO DE TRABAJO — LEÉ ESTO PRIMERO
>
> **La fuente de verdad del proyecto es `docs/RELEVO_IA.md`** (brief completo),
> seguido de `AGENTS.md` → `ESTADO.md` → `docs/PENDIENTES.md`.
> Este archivo es material de trabajo, no gobierno. Si contradice al RELEVO,
> **manda el RELEVO**.


# Panel de auditoría de rendimiento — bot de predicción macro

Panel en Python (Streamlit) que audita la **calidad direccional** de las señales de tu bot:
precisión direccional, matriz de confusión, falsos positivos y tasas de acierto en
**movimientos bajistas**, con métricas detalladas y gráficos de rendimiento histórico.

> El panel mide si el bot acierta o falla la dirección. No mide rentabilidad (eso
> exigiría definir ejecución, exposición y costos).

## Archivos

| Archivo | Qué hace |
|---|---|
| `panel_auditoria.py` | El panel (Streamlit). Ejecutar y abrir en el navegador. |
| `auditoria.py` | Módulo de cálculo: métricas, matriz de confusión, histórico, calibración. |
| `test_auditoria.py` | Pruebas del cálculo (caso de referencia, pendientes, CSV inválido, etc.). |
| `generar_datos_demo.py` | Genera `predicciones_demo.csv` (900 señales sintéticas) para explorar el panel. |
| `requirements.txt` | Dependencias. |

## Puesta en marcha

```bash
pip install -r requirements.txt
python generar_datos_demo.py        # solo si quieres datos de ejemplo
streamlit run panel_auditoria.py
```

Sin cargar un CSV, el panel arranca en **modo demostración** con datos sintéticos
(claramente identificados). Sube el historial de tu bot en la barra lateral para
auditar sus resultados reales.

## Formato del CSV de tu bot

| Columna | Obligatoria | Descripción |
|---|---|---|
| `fecha_prediccion` | sí | Fecha en que el bot emitió la señal |
| `fecha_objetivo` | sí | Fecha del resultado que se predijo |
| `activo` | sí | Instrumento (BTCUSDT, SP500, ...) |
| `direccion_predicha` | sí | `alcista` / `neutral` / `bajista` |
| `direccion_real` | sí* | `alcista` / `neutral` / `bajista` — **vacía si aún no vence** |
| `horizonte` | no | Etiqueta del horizonte (`1d`, `1w`, ...) |
| `prob_bajista` | no | Probabilidad de bajada emitida (0–1), habilita la pestaña de calibración |

También se aceptan sinónimos comunes (`bull/bear/flat/short/long`, con o sin tildes).
Cada fila con `direccion_real` vacía (o cuya fecha objetivo aún no vence) cuenta como
**pendiente**: no es acierto ni error, y queda fuera de las métricas.

## Qué audita el panel

**Resumen general**
- Exactitud direccional (aciertos / señales evaluadas)
- Exactitud balanceada (promedio del recall por clase)
- Referencia trivial: acierto de predecir siempre la clase mayoritaria
- Contadores de evaluadas / pendientes / excluidas

**Auditoría bajista (clase positiva = bajista)**
- TP: predijo bajista y bajó · FP: predijo bajista y no bajó (falso positivo)
- FN: no predijo bajista y bajó (bajada no detectada) · TN: no predijo bajista y no bajó
- Precisión bajista TP/(TP+FP), detección de bajadas TP/(TP+FN),
  tasa de falsos positivos FP/(FP+TN), F1
- Métricas por clase (precision / recall / F1 / soporte)

**Matriz de confusión**
- Conteos y versión normalizada por dirección real (heatmap interactivo)

**Histórico (usa la fecha del resultado)**
- Exactitud mensual y acumulada, con línea de referencia mayoritaria
- Precisión bajista y detección de bajadas por mes
- Falsos positivos bajistas y volumen de observaciones por mes
- Exactitud móvil con ventana configurable (5–100 señales)

**Calibración (opcional)**
- Si el CSV trae `prob_bajista`: probabilidad emitida vs. bajada real por bin

**Filtros**: rango de fechas objetivo, activo y horizonte. **Descargas**: métricas
por clase, métricas por mes y señales evaluadas en CSV.

## Pruebas

```bash
python test_auditoria.py
```

Incluye el caso de referencia TP=3, FP=1, FN=2, TN=4 → exactitud 70 %,
precisión bajista 75 %, recall 60 %, tasa de falsos positivos 20 %; además de
clases ausentes, señales pendientes, CSV inválido, filtros vacíos y calibración.

## Uso programático (sin panel)

```python
import pandas as pd
import auditoria as au

datos = au.cargar_predicciones("historial_bot.csv")
m = au.calcular_metricas(datos.evaluadas)
print(m.exactitud_direccional, m.bajista.precision, m.bajista.fp)
```

## Notas

- Denominadores en cero se muestran como **N/D**, nunca como 0 %. El F1 es 0 % cuando
  hay errores y ningún acierto.
- La exactitud acumulada histórica está **ponderada por observaciones** (un mes con
  1 señal no pesa igual que uno con 100).
- Las filas duplicadas (misma señal repetida, incluyendo el horizonte) se descartan y
  se reportan; las filas inválidas se conservan con su motivo en la columna
  `motivo_invalida`.
- Las señales cuya `fecha_objetivo` aún no venció quedan como **pendientes**, aunque
  ya traigan resultado. La fecha de corte es el momento exacto de la auditoría (una
  señal con objetivo hoy a las 15:00 auditada a las 16:00 ya es vencida; otra con
  objetivo a las 17:00 queda pendiente), configurable vía
  `cargar_predicciones(..., fecha_corte=...)`.
- Se excluyen filas con `fecha_prediccion` posterior a `fecha_objetivo`.
- La `direccion_real` se define típicamente con una regla de umbral (p. ej. ±0.5 %
  para alcista/bajista, dentro de la banda = neutral); esa regla la fija tu bot.
