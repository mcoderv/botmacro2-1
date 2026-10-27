# HANDOFF — MACRO2.1

> **Cómo arranca la próxima sesión:** leer `AGENTS.md` (proceso) → este archivo
> (estado) → `docs/RELEVO_IA.md` sólo si hace falta detalle técnico.
> **No hace falta leer el historial de chats.** Todo lo que importa está acá.

```
Sesion       : 7  (cierre 2026-10-27 12:45)
Rama         : main
Ultimo commit: 8cfec15 (H-25, parte 3) · gate 19 ok / 0 fallas / 1 aviso
Produccion   : botmacro — CONGELADA, no tocar
Desarrollo   : botmacro2-1 — este repo
```

---

## 0. Estado en una línea

El motor de régimen **ya guarda** lo que calcula (H-24) y el lanzador **ya
arranca** (H-25), pero **sigue diciendo RANGE el 100% de las veces**: la regla de
tendencia es un umbral fijo que hoy ningún activo puede pasar. El **ADR 016 ya
decidió** cómo reemplazarla y **falta implementarlo**. El resolvedor sigue sin
tolerancia (B2): un tercio de las validaciones a 4 h siguen siendo falsas.

---

## 1. El objetivo (decidido por el usuario)

Que el bot aporte **estimaciones confiables de la tendencia macro** y valide si
acierta. Ventana de mercado **8:00–16:00 Caracas**. Sin 24/7 (Render gratis).
Infraestructura: Render (web service) + UptimeRobot (keep-alive) + Cloudflare R2
(respaldo).

**"Confiable" se mide con tres números:** persistencia de la etiqueta, acierto
contra un baseline (precio sobre media de 200 / siempre-LONG), y calibración.
> Sigue **pendiente el ADR 013** que lo escriba.

**⚠️ Discrepancia de ventana, sin resolver:** el objetivo declarado es
**8:00–16:00**; el archivo de configuración dice **04:00–16:00** y el scheduler
del 27/10 12:38 arrancó con esa ventana ("Ventana 04:00-16:00 — ACTIVA ahora").
La afirmación vieja (08:00–17:00, hallazgo E1) **quedó desactualizada**. No se
tocó: hay que decidir cuál es la correcta.

---

## 2. Números medidos

### 2.1 Volumen de la base (2026-10-23, sólo lectura)

914 señales · 907 resueltas a 4 h · 902 a 24 h · 182 ciclos con señal · 253
ciclos auditados · 1.886 precios capturados · 23 tablas · 2,7 MB.

### 2.2 Régimen (2026-10-27 12:39, `analisis/medir_ramas_regimen.py`)

`regime_state`: **2.496 filas**, de las cuales **24 tienen la rama** (2 ciclos ×
12 activos; las otras 2.472 son del motor viejo, `p_value IS NULL`, se excluyen
siempre).

| Dato | Valor |
|---|---|
| RANGE | 24 / 24 (**100%**) |
| RAMA A (estacionaria, p ≤ 0,05) | **0 (0%)** |
| RAMA B (deriva baja) | **24 (100%)** |
| p-valores observados | 0,0819 – 0,8964 (**ninguno ≤ 0,05**) |
| pendiente máxima | 1,822 %/día vs umbral 2,88 %/día = **63,2%** del umbral |

**⇒ El ADF nunca decide nada.** Toda la clasificación la hace el umbral fijo.

### 2.3 La regla de tendencia, medida (`analisis/medir_regla_tendencia.py`)

200 paseos aleatorios sin deriva × 3 volatilidades. Falsos positivos (decir TREND
sin que haya tendencia):

| σ por hora | R1 fijo 0,0012 | R2 deriva÷σ | R3 t sobre PRECIO | R4 t sobre RETORNOS |
|---|---|---|---|---|
| 0,001 | 0% | 0% | **88%** | 3% |
| 0,003 | 9% | 0% | **88%** | 3% |
| 0,006 | **43%** | 0% | **88%** | 3% |

Datos reales (12 activos, 720/1.440 velas): σ diaria **0,31% – 4,13%** (13,5×
entre activos) · deriva −0,83% a +0,14% por día · deriva÷σ máximo **0,27** ·
`|t|` sobre retornos máximo **1,8**. TREND: R1 **0/12** · R2 **0/12** ·
R3 **12/12** · R4 **0/12**.

### 2.4 Resoluciones a 4 h (2026-10-23)

| Distancia | Señales | % |
|---|---|---|
| > 20 min | 504 | 55,6% |
| > 2 h | 299 | 33,0% |
| precio idéntico al de emisión | 72 | 7,9% |

Mediana 28,8 min · p90 220 min. A 24 h es más limpio: mediana 9,8 min.

| | 4 horas | 24 horas |
|---|---|---|
| Global | 31,8% (n=907) · PF 0,69 | — |
| LONG | 24,8% · PnL −0,217% | 32,9% · −0,456% |
| SHORT | 38,2% · +0,028% | **56,3%** · +0,157% |

### 2.5 Datos perdidos por H-24 (ya corregido)

Entre el **2026-10-20 10:25** y el **2026-10-27 11:14**: **12 corridas** sin
poder guardar el régimen (≈144 filas), con **69 señales** emitidas en el medio.
El error estaba en el log: `table regime_state has no column named p_value`.

---

## 3. Qué está PROBADO

- **El umbral fijo no tiene una tasa de error, tiene una por activo:** 0% en un
  activo calmo y 43% en uno volátil (medido, n=200 × 3 σ). La volatilidad entre
  los 12 activos varía **13,5×**.
- **El test sobre el precio es inválido:** 88% de falsos positivos, siempre
  (regresión espuria). **El test sobre los retornos tiene la tasa que declara:**
  3% con nivel 5%.
- **El ADF del régimen no aporta:** 0 de 24 filas salieron por la rama
  estacionaria; 12 de 12 activos, por la rama de deriva baja.
- **Hoy ningún activo está en tendencia:** la deriva más grande es un cuarto del
  ruido diario (deriva÷σ ≤ 0,27). Por eso **"12/12 RANGE" no prueba el bug por sí
  solo**: el bug está en la regla, no en la etiqueta de hoy.
- **El resolvedor no tiene tolerancia de distancia:** toma el precio más cercano
  sin límite (leído en código). De ahí las 72 fabricadas.
- **El planificador duerme fuera de ventana** y no resuelve nada.
- **El ADF del score se corre sobre cierre−VWAP, no sobre FFD:** precio p=0,7045 ·
  residuo contra VWAP p=0,0000 · retornos p=0,0000 (5.000 velas de BTC) ⇒ el
  residuo es estacionario por construcción.
- **C3.5 inventa un `cycle_id` nuevo** y actualiza por `MAX(id)` sin filtrar ⇒
  join C3↔C3.5 = 0.
- **La última vela de `candleSnapshot` viene abierta** (T > ahora): hay que
  descartarla en cualquier medición.
- **Un ciclo tarda 46–58 s** local, emite ~4 señales, resuelve pendientes y
  captura 12 precios. Entra en 15 min con margen.
- **Los `.bat` con `|` sin escapar no corren** (CMD lo toma como cañería) y con
  finales de línea Unix tampoco (parte los bloques). Las dos cosas medidas.

---

## 4. Qué NO está probado (incógnitas)

- **Cuánto tarda un ciclo en Render con 0,1 CPU.** 46 s locales pueden ser 5–20×
  más. Si pasa de 15 min, sube el intervalo y baja la muestra.
- **Si la asimetría LONG/SHORT es del bot o del mercado.** El período pudo ser
  bajista. No se puede separar porque el régimen no distingue nada.
- **Si con la regla nueva (ADR 016) aparece tendencia cuando exista.** El test es
  potente con n=720: puede llamar TREND a derivas económicamente irrelevantes.
  Hoy no ocurre (`|t|` máx 1,8) pero hay que vigilarlo con la calibración.
- **Si 30 días alcanzan** para |t| > 3,0 con la unidad correcta (el ciclo).

---

## 5. Bugs

### 5.1 Abiertos

| # | Sev | Qué | Evidencia |
|---|---|---|---|
| **B1** | **P0** | Umbral de tendencia 0,0012 ⇒ 100% RANGE | ADR 016 escrito; **falta implementar** |
| **B2** | **P0** | Resolvedor sin tolerancia + planificador dormido ⇒ 72 fabricadas (7,9%) y 55,6% a >20 min | Medido en la base |
| **B3** | P1 | `cycle_id`: C3.5 lo renombra y actualiza por `MAX(id)` | Join C3↔C3.5 = 0; 74 `PRE_REGIME` |
| **B4** | **P1** | Render gratis borra el disco: 2.1 **no tiene Litestream/R2** | ADR 003 los sacó a propósito |
| **B5** | P2 | El pipeline reescribe `central_params.json` en cada corrida (2 fechas) ⇒ `git add -A` lo arrastra a cualquier commit | Visto el 27/10 en el commit del ADR 016 |
| **B6** | P2 | `verificar.py` valida 13 ADRs con lista fija: el 014 y el 016 no los mira | Gate en verde con 16 ADRs en disco |
| **B7** | P2 | `.gitignore` oculta `diagnostico_*.py` | Commit perdido y recuperado |

### 5.2 Cerrados en la sesión 7

| # | Qué se hizo |
|---|---|
| **H-24** | Migración aditiva de `regime_state` (5 columnas) y `regime_features` (3). Validador `fixes/probar_h24.py` (reconstruye el esquema **en memoria**, no toca la base real). Commit `d37c4c8`. Ya aplicada a la base real. |
| **H-25** | Los dos `.bat`: finales de línea Unix **y** un `|` sin escapar en el cartel (dos síntomas del mismo y otro bug). Validador `fixes/probar_bats.py` (detecta las dos clases; `--aplicar` / `--deshacer`). `.gitattributes` con `eol=crlf`. Commits `2cf644c`, `8cfec15`. **Probado: el lanzador arrancó y el ciclo #1 completó en 55 s.** |

---

## 6. Herramientas que ya existen

```cmd
python analisis\diagnostico_estado.py        REM reporte solo lectura + FLAGS
python analisis\medir_ramas_regimen.py       REM RAMA A vs B, p-valores, pendientes
python analisis\medir_regla_tendencia.py     REM 4 reglas vs paseos aleatorios (usa la API)
python fixes\probar_h24.py                   REM valida la migracion del regimen
python fixes\probar_bats.py                  REM valida los .bat (--aplicar / --deshacer)
python analisis\probar_ciclo.py              REM cronometra un ciclo y RESTAURA la base
python ventana.py --ver
python verificar.py                          REM gate: 19 ok / 0 fallas / 1 aviso
python git\guardar.py "mensaje"
```

`diagnostico_estado.py` es el que hay que correr **primero** en una sesión nueva.
`medir_regla_tendencia.py` acepta `--sin-api` (sólo controles sintéticos).

---

## 7. Próximo paso recomendado

**1 · Implementar el ADR 016** (`decisiones/016-definicion-de-tendencia.md`, hoy
en estado PROPUESTO). Es lo que cierra B1:

- Retirar el umbral fijo `0,0012`; el TREND pasa a ser "la deriva es
  estadísticamente distinguible de cero" sobre los **retornos**, con errores HAC
  y α=0,05 fijado antes.
- Guardar `t` y `σ` usados (dos columnas nuevas ⇒ migración con el mismo patrón
  de H-24; el validador `probar_h24.py` sirve de molde).
- Validador: **tendencia moderada en activo calmo** (deriva 1,2%/día, σ horaria
  0,02%) ⇒ el código viejo dice RANGE, la regla nueva dice TREND.

**2 · B2** (tolerancia de 30 min en el resolvedor) → **3 · B4** (Litestream) →
**4 ·** los 30 días con el protocolo OOS escrito antes de T₀ (ADR 012).

En paralelo queda pendiente el **ADR 013**: qué significa "confiable" (los tres
números). Sin eso no se puede juzgar la persistencia ni la calibración, y la
`confidence` del motor sigue siendo un **100 fijo**.

---

## 8. Trampas (no repetirlas)

- **CMD.exe**, sin `&&`, sin `;`. El usuario **no lee código**: comandos completos
  y explicar el porqué (AGENTS §4.1).
- **`more` y `type` cuelgan la consola.** Volcar con `findstr /n` o con Python.
- **Acentos:** `chcp 65001` antes de imprimir, y en Python
  `sys.stdout.reconfigure`. `findstr` no busca con acentos.
- **Lanzar `main.py` desde un script** requiere `PYTHONIOENCODING=utf-8`.
- **`.bat`:** un `|` sin escapar es una cañería; los paréntesis sin escapar dentro
  de un `if (...)` cierran el bloque antes de tiempo; los emojis son un riesgo.
  Finales de línea **CRLF** siempre. Validar con `fixes\probar_bats.py`.
- **`git add -A` arrastra `central_params.json`** (el pipeline lo reescribe en
  cada corrida). Revisar `git show --stat HEAD` después de cada commit y, si
  entró, rehacerlo: `git reset --soft HEAD~1`, restaurar ese archivo, commitear
  de nuevo.
- **Fin de línea y git:** con `core.autocrlf=true`, convertir un archivo en el
  disco **no genera commit** (git ya lo tenía normalizado). Lo que manda es
  `.gitattributes`.
- **No crear archivos de prueba dentro del repo** (AGENTS §10) y **no contar con
  escribir en `%TEMP%` desde la consola**: el sandbox lo niega. Los validadores
  se hacen reconstruyendo **en memoria**.
- **Citas y comillas:** los comandos con comillas dobles anidadas se rompen.
  Preferir scripts en archivo antes que `python -c "..."`.
- **`git show --stat HEAD`** es la forma más rápida de verificar qué se guardó.
- Si un commit no incluye un archivo, revisar `.gitignore` **y** `git check-ignore`
  **antes** de repetir.

---

## 9. Archivos clave

| Archivo | Qué es |
|---|---|
| `AGENTS.md` | Cómo se trabaja (proceso, no proyecto) |
| `HANDOFF.md` | Este archivo |
| `docs/AUDITORIA_C0_C4.md` | Auditoría medida + Anexo A (bugs migrados) |
| `docs/RELEVO_IA.md` | Brief técnico completo (fórmula, OOS, conceptos verificados) |
| `decisiones/` | **16 ADRs** — el 016 define qué es "tendencia" |
| `ESTADO.md` | Foto del estado (se reescribe, no se acumula) |
| `docs/PENDIENTES.md` | Tracking — **parcialmente desactualizado**, contrastar con este archivo |
