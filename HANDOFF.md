# HANDOFF — MACRO2.1

> **Cómo arranca la próxima sesión:** leer `AGENTS.md` (proceso) → este archivo
> (estado) → `docs/RELEVO_IA.md` sólo si hace falta detalle técnico.
> **No hace falta leer el historial de chats.** Todo lo que importa está acá.

```
Sesion      : 6  (cierre 2026-10-27)
Rama        : main
Produccion  : botmacro — CONGELADA, no tocar
Desarrollo  : botmacro2-1 — este repo
```

---

## 0. Estado en una línea

El bot **no está dando estimaciones de tendencia**: el motor de régimen dice
**RANGE el 100% de las veces** y **un tercio de las validaciones a 4 h son
falsas**. Los dos bugs están identificados y medidos, ninguno corregido.

---

## 1. El objetivo (decidido por el usuario)

Que el bot aporte **estimaciones confiables de la tendencia macro** y valide si
acierta. Ventana de mercado **8:00–16:00 Caracas**. Sin 24/7 (Render gratis).
Infraestructura: Render (web service) + UptimeRobot (keep-alive) + Cloudflare R2
(respaldo).

**"Confiable" se mide con tres números:** persistencia de la etiqueta, acierto
contra un baseline (precio sobre media de 200 / siempre-LONG), y calibración.
> Esto está **propuesto pero no escrito como ADR**. El ADR 013 quedó pendiente.

---

## 2. Números medidos (base real, 2026-10-23, sólo lectura)

**Volumen:** 914 señales · 907 resueltas a 4 h · 902 a 24 h · 182 ciclos con
señal · 253 ciclos auditados · 1.886 precios capturados · 23 tablas · 2,7 MB.
Última señal: **2026-10-23 15:51**.

**Calidad de las resoluciones a 4 h** (distancia entre el precio usado y el
momento que correspondía):

| Distancia | Señales | % |
|---|---|---|
| > 20 min | 504 | 55,6% |
| > 1 h | 385 | 42,4% |
| > 2 h | 299 | 33,0% |
| precio idéntico al de emisión | **72** | **7,9%** |

Mediana 28,8 min · p90 220 min · máximo 240 min.

**A 24 h** (más limpio): mediana 9,8 min · 17,4% > 2 h · 7,9% > 6 h.

**Resultado:**

| | 4 horas | 24 horas |
|---|---|---|
| Global | 31,8% (n=907) · PF 0,69 | — |
| Sin fabricadas | 34,5% (n=835) | — |
| LONG | 24,8% (n=439) · PnL −0,217% | 32,9% (n=435) · −0,456% |
| SHORT | 38,2% (n=468) · +0,028% | **56,3%** (n=467) · +0,157% |

**Régimen:** RANGE 875/914 (95,7%) · UNKNOWN 21 · TREND_DOWN 12 · TREND_UP 6.

**p-valor ADF en la auditoría:** 648/3.036 = 1,0 (21,3%), de los cuales **619
tienen `data_quality=ERROR`**; 0 filas tienen ERROR con p≠1,0 ⇒ los escribe la
misma rama de fallback.

**Horas de emisión:** 08:81 · 09:75 · 10:102 · 11:97 · 12:97 · 13:134 · 14:94 ·
15:95 · 16:91 · 17:9 · 19:7 · 20:25 · 21:7 ⇒ **48 señales (5,3%) fuera de [8,16)**.

---

## 3. Qué está PROBADO

- **El umbral de tendencia es imposible de pasar.** Hoy, 12/12 activos dieron
  RANGE con "confianza 100%"; las pendientes fueron **0,00002 a 0,00096** y el
  umbral es **0,0012**. Ningún activo puede salir TREND. Equivale a ~2,9%/día.
- **El resolvedor no tiene tolerancia de distancia.** Lo leí en el código: toma
  el precio más cercano sin límite. De ahí las 72 fabricadas.
- **El planificador duerme fuera de ventana** y no resuelve nada. Por eso había
  señales del 23/10 sin resolver; la prueba del 27/10 resolvió **7 de golpe** con
  precios a 4 días de distancia.
- **El ADF del score se corre sobre cierre−VWAP, no sobre FFD.** Verificado en
  código y con sonda: precio p=0,7045 · residuo contra VWAP p=0,0000 ·
  retornos p=0,0000 (5.000 velas de 1 h de BTC) ⇒ el residuo es estacionario por
  construcción, el test no distingue tendencia de no-tendencia.
- **C3.5 inventa un `cycle_id` nuevo** y actualiza el snapshot por `MAX(id)` sin
  filtrar por ciclo ⇒ C3 y C3.5 no se pueden unir (join = 0) y quedan 74 filas
  `PRE_REGIME` para siempre.
- **La última vela que devuelve `candleSnapshot` viene abierta** (T > ahora).
- **Un ciclo completo tarda 46–58 s** en la máquina del usuario, emite 4 señales,
  resuelve pendientes y captura 12 precios. Cabe en 15 min con margen.
- **La ventana es configurable** y `ventana.py` la escribe bien (hoy quedó en
  04–16; ver §5).

---

## 4. Qué NO está probado (incógnitas)

- **Cuánto tarda un ciclo en Render con 0,1 CPU.** 46 s locales pueden ser 5–20×
  más lento. Si pasa de 15 min, hay que subir el intervalo y baja la muestra.
- **Si la asimetría LONG/SHORT es del bot o del mercado.** El período pudo ser
  bajista. No se puede separar porque el régimen no distingue nada.
- **Si arreglar el régimen hace que la señal prediga algo.** Nadie lo probó.
- **Si 30 días alcanzan** para |t| > 3,0 con la unidad correcta (el ciclo).

---

## 5. Bugs abiertos

| # | Sev | Qué | Evidencia |
|---|---|---|---|
| **B1** | **P0** | Umbral de tendencia 0,0012 ⇒ 100% RANGE | 12/12 activos hoy, pendientes 0,00002–0,00096 |
| **B2** | **P0** | Resolvedor sin tolerancia + planificador dormido ⇒ 72 fabricadas (7,9%) y 55,6% a >20 min | Medido en la base |
| **B3** | P1 | `cycle_id`: C3.5 lo renombra y actualiza por `MAX(id)` | Join C3↔C3.5 = 0; 74 `PRE_REGIME` |
| **B4** | **P1** | Render gratis borra el disco: 2.1 **no tiene Litestream/R2** | ADR 003 los sacó a propósito |
| **B5** | P2 | El pipeline reescribe `central_params.json` en cada corrida (fechas, acentos escapados, sin salto de línea final) ⇒ ensucia git | Visto en commit `d4ea32c` |
| **B6** | P2 | `verificar.py` valida 13 ADRs con lista fija: el ADR 014 no lo mira | Gate en verde con 14 ADRs en disco |
| **B7** | P2 | `.gitignore` oculta `diagnostico_*.py` (se agregó excepción sólo para el nuevo) | Commit perdido y recuperado |

---

## 6. Herramientas que ya existen

```cmd
python analisis\diagnostico_estado.py      REM reporte solo lectura + FLAGS
python analisis\probar_ciclo.py            REM cronometra un ciclo y RESTAURA la base
python analisis\auditoria_c0_c4.py --seccion M4
python ventana.py --ver
python verificar.py                        REM gate: 19 ok / 0 fallas / 1 aviso
python git\guardar.py "mensaje"
```

`diagnostico_estado.py` es el que hay que correr **primero** en cualquier sesión
nueva: da el estado completo en 60 líneas.

---

## 7. Próximo paso recomendado

**Arreglar B1 antes de gastar 30 días de datos.** Con el umbral actual los 30
días no dirían nada sobre tendencia.

Hace falta un **ADR 016** que defina qué es "tendencia" en este proyecto. Dos
caminos, y hay que elegir uno antes de tocar código:

1. **Umbral relativo a la volatilidad** (pendiente dividida por la desviación de
   los retornos de la ventana) — sigue siendo una regla simple, pero se adapta.
2. **Test estadístico sobre la pendiente** (t con errores HAC / Newey-West) —
   más honesto, más caro, y hay que fijar el nivel antes de mirar los datos.

Después: **B2** (tolerancia de 30 min) → **B4** (Litestream) → recién ahí los 30
días con el protocolo OOS escrito antes de T₀.

---

## 8. Trampas (no repetirlas)

- **CMD.exe**, sin `&&`, sin `;`. El usuario **no lee código**: darle comandos
  completos y explicar el porqué (AGENTS §4.1).
- **`more` y `type` cuelgan la consola.** Volcar con `findstr /n` o con Python.
- **Acentos:** `chcp 65001` antes de imprimir, y en Python `sys.stdout.reconfigure`.
  `findstr` no busca con acentos.
- **Lanzar `main.py` desde un script** requiere `PYTHONIOENCODING=utf-8`, si no
  muere con `UnicodeEncodeError` al imprimir emojis.
- **`git show --stat HEAD`** es la forma más rápida de verificar qué se guardó.
- Si un commit no incluye un archivo, revisar `.gitignore` **antes** de repetir.

---

## 9. Archivos clave

| Archivo | Qué es |
|---|---|
| `AGENTS.md` | Cómo se trabaja (proceso, no proyecto) |
| `HANDOFF.md` | Este archivo |
| `docs/AUDITORIA_C0_C4.md` | Auditoría medida + Anexo A (bugs migrados) |
| `docs/RELEVO_IA.md` | Brief técnico completo (fórmula, OOS, conceptos verificados) |
| `decisiones/` | 14 ADRs |
| `ESTADO.md` | Foto del estado (se reescribe, no se acumula) |
| `docs/PENDIENTES.md` | Tracking — **parcialmente desactualizado**, contrastar con este archivo |
