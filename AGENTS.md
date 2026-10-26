# AGENTS.md — MACRO2.1 (local, experimental)

> Este archivo lo lee la IA en CADA turno. Si es largo, lo skimmea.
> Mantenelo corto. Lo que la IA puede leer sola en el código, NO va acá.
> Lo que la IA NO puede adivinar, va acá.

---

## 0. QUÉ ES (Y QUÉ NO ES) ESTE PROYECTO

**MACRO2.1 NO ES UN BOT DE TRADING.** Es un **predictor + validador** de tendencia
macro. NO abre posiciones, NO tiene SL ni TP, NO calcula P&L de una cartera.

| | |
|---|---|
| Lo que hace | Calcula `macro_score_v2` (C3), **emite** una señal, y después **valida** si se equivocó (C4, a 4h/8h/24h) |
| Lo que NO hace | Abrir/cerrar posiciones. SL/TP. Dimensionar. Ejecutar órdenes |
| Quién ejecuta | **MACRO2** (producción, `botmacro`, capa C7). Congelada. |

**Consecuencia práctica:** cuando el análisis diga "43,8% de las señales tocan
el SL primero", eso es un diagnóstico de **TIMING** (¿cuándo se movió el precio?),
**no** un P&L perdido. No existe tal cosa como "SL" en este repo.
La ejecución con SL dinámico ATR que propone el GEM es de **MACRO2 (C7)**,
no de MACRO2.1.

**Y el score v2 no discrimina por cobertura, no por fórmula:** el score SÍ
ordena bien dentro de cada etiqueta (a 24h: FUERTE HR 93,8% > MODERADA 77,8%
> RUIDO 65,3%). El problema es que solo el **9,4%** de las señales son
FUERTE/MODERADA (ver H-9).

---

## 1. CONTACTO

- Soy **vibe coder**: no sé programar. Delego todo el código a IA.
- Hablame en **español**, sin jerga. Si usás un término técnico, explicámelo en una línea.
- **REGLA DURA:** NUNCA edites ni crees archivos sin mi **"ok, crealo"** explícito.
  Presentá el diseño en el chat primero, esperá el ok, recién ahí escribís.
- Cuando no estés seguro de algo, decilo ("no sé") en vez de inventar.

---

## 2. ENTORNO (obligatorio)

| | |
|---|---|
| Sistema | **Windows 10/11 + VS Code**. No asumas Linux ni Mac. |
| Terminal | **CMD.exe** |
| ⛔ | **NUNCA uses PowerShell.** Me da problemas. |
| ⛔ | **NUNCA des comandos bash, ni `curl`/`wget` unix, ni `&&`, ni `;`** |
| Python | venv activo (`(.venv)` en el prompt). `python` y `pip` funcionan. |
| Git | Instalado y configurado. **Pero yo no sé git** → nunca digas "hacé un commit", dá el comando literal. |
| Idioma | Todo en español, **incluidos los mensajes de commit**. |
| Datasets | Datos de Hyperliquid, 12 activos (6 cripto + 6 TradFi), TZ America/Caracas. |
| ⛔ | **Sin Docker.** MACRO2.1 corre directo con `python` en Windows. No lo reintroduzcas. |
| Entrega de archivos | Los archivos van **directo a la carpeta destino** del proyecto (`fixes\`, `analisis\`, etc.). **NO des comandos `copy` desde Descargas.** |

**Formato obligatorio de cada comando que me des:**

```
PASO N — [qué hace en una línea]

    <comando literal, listo para copiar, CMD>

✅ Deberías ver: [output esperado]
❌ Si falla: [qué significa + qué te pego]
📂 Desde: [carpeta exacta]
```

- **Ritmo: 1 a 4 comandos por turno.**
  - Si son **independientes o de solo lectura** -> van juntos (1 mensaje = 1 ida y vuelta = menos tokens).
  - Si uno **depende del anterior**, o el anterior puede fallar -> de a uno, con output esperado y que hacer si falla.
  - Nunca mas de 4, y nunca una cadena de 6 pasos para encadenar analisis.
  - **No mezcles tareas.** Cuando estemos validando un script, un fix o un
    analisis, ese es el UNICO foco del turno: cerralo (self-test + commit) y
    recien ahi pasar a responder preguntas abiertas o definir el trabajo
    siguiente. **No agregues preguntas ni ordenes extra al mismo turno de
    validacion.**
  - (El "output esperado" y el "pegá la salida" siguen siendo obligatorios.)
- **Siempre** con output esperado. No sé leer errores.
- **Siempre** terminá con: *"¿lo corriste? pegá la salida"*.
- Si algo falló, **no me des el siguiente paso** hasta ver la salida.

---

## 3. VERDAD ACTUAL

| Quiero saber... | Leé |
|---|---|
| ¿Dónde estamos? ¿Qué sigue? | `ESTADO.md` |
| ¿Por qué se decidió algo? | `decisiones/` (ADR) |
| ¿Qué hace cada archivo? | tabla de abajo |
| ¿Está sano el proyecto? | `python verificar.py` |
| ¿Qué hice en la sesión anterior? | `HANDOFF.md` |
| ¿Qué falta? | `docs/PENDIENTES.md` |
| ¿Dónde va un archivo nuevo? | `docs/LEEME.md` |

---

## 4. REGLAS DURAS

1. **Un cambio por sesión.** Una celda por vez. No toques dos módulos juntos.
2. **Si algo funciona, NO lo toques** sin un ADR que lo justifique.
3. **Import que falla → que se rompa.** Prohibido degradar en silencio
   (no `except ImportError: AVAILABLE = False`). Un cambio de firma tiene
   que romper el arranque, no escondido.
4. **Un parámetro, UNA ruta de acceso.** Si lo cambiás, cambiás su definición
   y verificás que TODOS los consumidores lo lean de ahí.
5. **Después de cada cambio:** `python verificar.py` y pegá la salida.
   Si hay fallas, no avances.
6. **Nunca toques** `data/`, `.env`, ni `logs/`.
7. **Nunca borres** `docs/local/chats/` (los chats viejos que venías guardando
   a mano) ni commits ya publicados.
8. **Producción está congelada.** `botmacro` = MACRO2 = Render + Docker + Litestream.
   No se toca hasta que algo se valide en 2.1. `botmacro2-1` = desarrollo, local, sin Docker.
9. **No toques `docs/INFORME_MACRO2.1.md`** sin que te lo pida: es la spec de
   referencia, y el tracking de pendientes vive en `docs/PENDIENTES.md`.

---

## 5. HECHOS QUE NO ESTÁN EN EL CÓDIGO

> Esto no se deduce leyendo el repo. Si no está acá, se pierde.
> Leelo antes de tocar nada.

### 5.1 `macro_score_v2` es RECIENTE — no arregles un bug que no existe

`ms_v2` (el score multi-timeframe) se agregó en **v7.9.3** (desplegado el
**2026-10-19 14:06**). Las señales anteriores tienen `macro_score_v2 = 0.0`.

Medición real (2026-10-23, 877 señales resueltas a 24h). La clave es si el
`ms_v2` guardado **se explica con los componentes** (`poc + caja + fvg + rs`
+ un `s_mtf` implícito dentro de [-0.65, +0.65]):

| Grupo | n | Qué significa |
|---|---|---|
| `ms_v2 >= 2` (FUERTE 20 + MODERADA 38) | **58** | Score v2 real y coherente |
| `ms_v2 < 2` pero coherente | **53** | Coherente (score bajo, o 0 legítimo) |
| `ms_v2` incoherente con los componentes | **748** (85%) | ❌ No fue computado (placeholder) |
| Placeholders que *casualmente* son coherentes | **18** | ⚠️ Coherentes por casualidad, **NO son score real** |

**Con score v2 REAL: 111 señales** (58 + 53). Las otras 766 tienen `ms_v2 = 0`
de relleno. De las 129 "reconstruibles", **18 son placeholders** (13-18/10).

⚠️ **El 85% del histórico no tiene score v2.** No es un fallback roto: es
antigüedad. No lo trates como bug.

### 5.1.b ⛔ TRAMPA CONFIRMADA: las etiquetas NO son comparables entre sí

La distribución de etiquetas **cambió por completo el 19/10**:

| Fecha | FUERTE | MODERADA | RUIDO | total |
|---|---|---|---|---|
| 13-18/10 | 0 | 0 | 18 | 18 (placeholders) |
| 19/10 | 1 | 21 | 28 | 50 |
| 20/10 | 9 | 12 | 8 | 29 |
| 21/10 | 10 | 5 | 17 | 32 |

**Comparar HR/PF entre etiquetas = comparar días distintos.** El "RUIDO tiene
PF 4.43" NO es evidencia: es que el grupo RUIDO abarca más días.
**Siempre cortar por día (o por ventana) antes de comparar etiquetas.**
Con n=5-28 por celda es ruido, pero al menos NO está confundido por fecha.

### 5.1.c El `ms_v2` está operando con dos inputs degradados

De la corrida del 2026-10-23 (`python main.py`):

1. **`s_mtf` = 0 en 7 de 12 activos.** El bias 1D/4H/1H sale `N/A` → el
   término multi-timeframe (0.30·1h + 0.20·4h + 0.15·1d) **no aporta nada**.
   El "multi-timeframe" del nombre no está multi-timeframe.
2. **La rama momentum casi nunca se activa.** El p-value del residual FFD
   (`P-v4.2`) salió < 0.001 en los 12 activos de esa corrida, y en el histórico
   **856 de 877 señales tienen p < 0.02** → todas toman la rama estacionario.

Consecuencia: `ms_v2 = 0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs + s_mtf + d`,
donde `s_mtf = 0` y `rs` (el flujo, el componente que mejor predice la
dirección) pesa **0.5** en vez de 2.0.

**Consecuencia medida:** el patrón `(poc=±1, rs=±2, caja+fvg=∓1)` da
`s_base = 0 EXACTO` en la rama estacionario y `±4` en la momentum. Esas
señales (breakouts con flujo fuerte) quedan con `ms_v2 = 0` → etiqueta RUIDO.
Es un hecho de la fórmula, verificable sin datos.

### 5.2 El re-score de umbral ADF v1 dio FALSOS POSITIVOS

`analisis/rescore_umbral.py` (v1) re-scoreó **todas** las señales, incluidas
las 749 sin score v2 computado. De sus "10 señales que cambian de rama", 9
eran HYPE con `ms_v2 = 0.00` → **falsas**.

La **v2** (mismo archivo, reescrito) corrige esto: clasifica cada señal en
reconstruible / no reconstruible, re-scorea **solo** las reconstruibles,
aborta si la auto-validación 1 no da ≥90%, y reporta el corte temporal.

**Resultado de la v2 (2026-10-23):**
- **0 señales cambian de etiqueta** al pasar de 0.02 a 0.05.
- Motivo: de las 10 que cambian de rama, 9 son placeholders y 1 ya estaba en
  0.05. **Solo 1 señal en toda la DB se generó con el umbral nuevo.**
- **VEREDICTO: el ADR 002 es INMEDIBLE con los datos actuales.** No es que sea
  inútil: es que no hay historia con el umbral viejo Y score v2 a la vez.
  **Necesita ~30 días más de datos para evaluarse.**

**Herramienta: `python analisis
`rescore_umbral_v2.py`** (reconstruye el score
sin tocar la DB, con auto-validaciones y corte temporal).

### 5.3 Lo que YA está hecho — no lo rehagas

| Tema | Estado real |
|---|---|
| `scheduler.py` lee `PORT` del entorno | ✅ **YA ESTÁ HECHO** (punto 3 del informe). Ya usa `HEALTH_PORT`/8080 como fallback. |
| Bucket R2 = `mercabot-qwen-db` | ✅ **YA ESTÁ HECHO** (punto 6 del informe). No lo "arregles" de nuevo. |
| Umbral ADF unificado en 0.05 | ✅ **APLICADO** (ADR 002, commit `5361b4f`). Fuente única: `CENTRAL_PARAMS["macro"]`. |
| Carpetas de backup `backups_v2.1` | ✅ Arreglado (H-3) en el mismo commit. |
| Sin Docker en 2.1 | ✅ Decidido (ADR 003). `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.sh` y `litestream.yml` fueron borrados del clon local. **Producción (`botmacro`) los sigue teniendo.** |
| **Max DD con capital compuesto** | ✅ **ADR 004** (H-15). Antes `np.cumsum` (suma aritmética de %) daba DD de 270% — imposible. Ahora `np.cumprod` sobre índice base 1.0. El DD **siempre cae entre 0% y 100%**. Si ves DD > 100%, es un bug. |
| **Fuente única del umbral ADF** | ✅ **H-12** (implementación del ADR 002). El 0.02 huérfano salió del literal `validation`, de `val_defaults` y del fallback de C3_MACRO. El banner lee la fuente real. |
| **Ventana operativa configurable** | ✅ **ADR 006** (H-17). La ventana sale del JSON (`ventana_operativa`), no de constantes. `python ventana.py --ver / --continuo / --inicio X --fin Y`. Los resúmenes de Telegram ya no están atrapados dentro del `if not en_ventana()`. |

### 5.4 Lo que el pipeline hace MAL y hay que saber

- **5 fallbacks silenciosos de import.** Si cambiás la firma de una función,
  el pipeline **se degrupa sin avisar**. Es el riesgo #1 del proyecto.
  Ubicaciones: `C2_5_CONTEXTO_local.py:78`, `C3_MACRO_local.py:42`,
  `C3_MACRO_local.py:51`, `C3_MACRO_local.py:126`, `C3_5_REGIME_ENGINE.py:60`.
- **El Profit Factor no depende del umbral de break-even.** `C4` usa
  `BREAKEVEN_THRESHOLD_PCT = 0.05` solo para el HR. El PF usa `p > 0` / `p < 0`.
  → Cuando se implemente k×σ (ADR 001), **el PF no se va a mover.**
- **Cero tests.** `verificar.py` es el primer paso, no el final.
- **Backup de la DB:** hecho localmente el 2026-10-23 en
  `C:\Users\MD\Desktop\MACRO2.1_BACKUP\`. **Falta subirlo a Drive** — hasta
  entonces sigue siendo un solo disco. Es el único recurso del proyecto que
  no se recupera de GitHub.

### 5.4.b Bugs de métrica conocidos (NO los re-descubrir)

| # | Bug | Dónde | Efecto | Estado |
|---|---|---|---|---|
| **H-13** | `senales_metricas` **no agrega por `calidad_senal_v2`** | `C4_SENIAL_VALIDATOR` | Las métricas por etiqueta salen de la escala **legacy** (14/8/4), que es inalcanzable porque `macro_score` máximo real es 6 | ⬜ Pendiente |
| **H-14** | `_get_price_at_time()` usa `ORDER BY ABS(timestamp_unix - ?) ASC LIMIT 1` | `C4_SENIAL_VALIDATOR` | Puede tomar el precio **posterior** al horizonte. Medido: 472 de 914 señales (52%) cambian de PnL, pero el sesgo neto en HR/PF es **< 1%** ⇒ los números se sostienen, el método no | ⬜ Pendiente (fix: `WHERE timestamp_unix <= ? ORDER BY timestamp_unix DESC LIMIT 1`) |
| **H-16** | "ganancia" significa 2 cosas: `hit_rate`/`wins`/`losses` usan `p > ±0.05%`; `profit_factor` (C4) y `avg_win`/`expectancy` usan `p > 0` | C4 + `report_validator` | Inconsistencia real, pero medida: **impacto < 1% en PF** ⇒ **diferido**, no aplicado | ⏸️ Diferido (ADR 004) |

### 5.5 El r

- `C3_5_REGIME_ENGINE.py` corre el ADF **sobre niveles**.
- `C3_MACRO_local.py` corre el ADF **sobre residuales FFD** (otro test).
- Los dos usan el mismo umbral (0.05) pero **son tests distintos**. El motor
  de régimen no mueve el conmutador de `ms_v2`.
- Decisión pendiente (ADR 001 / pending). **No los "unifiques" sin un ADR.**

---

### 5.6 La asimetría LONG/SHORT es el hallazgo MÁS SÓLIDO (no lo percas)

**MACRO2.1 hace más señales SHORT que LONG, y las SHORT funcionan mejor.**
Confirmado por **3 métodos independientes** (n=443 LONG / 471 SHORT):

| Método | LONG | SHORT |
|---|---|---|
| PF a 24h | **0,50** | **1,28** |
| MFE/MAE real | MFE +0,84% vs MAE 2,46% ⇒ **payoff −2,9:1** | MFE +2,84% vs MAE 1,62% ⇒ **1,75x** |
| Movimiento contrario primero | **54,0%** | 34,3% |

**Interpretación correcta:** el 54% de "SL primero" en LONG es un dato de
**timing** (el precio se movió en contra antes que a favor), **no** de P&L.
⇒ **ADR 005 (caja simétrica) PROPUESTO**, no aplicado.

**Ojo:** esto **NO lo arregla ningún umbral** (el PF no depende del break-even).
Es microestructura o lógica de entrada. Copiar el patrón de los que ganan
(`xyz:SILVER` PF 3,22 · `xyz:GOLD` PF 2,64) vale más que recalibrar umbrales.

### 5.7 El timing tiene look-ahead PARCIAL (no lo uses como feature todavía)

El timing actual se calcula sobre la trayectoria **completa** hasta el horizonte
⇒ correlaciona con el PnL final por construcción. No es 100% tautológico
(FAVOR a 24h tiene HR 67,2%, no 100%), pero la prueba limpia es **timing
temprano (1h) con PnL medido desde t+1h**. Falta el flag `--timing-h`.

**Aviso metodológico (obligatorio):** la distribución de etiquetas cambió por
completo el 19/10 (H-10). **Nunca comparar HR/PF entre etiquetas sin cortar por
día o por ventana.**

## 6. MAPA DEL PROYECTO

### Pipeline (9 celdas, se ejecutan en orden, comparten estado global)
| Archivo | Qué hace |
|---|---|
| `C0_INICIO_local.py` | Setup: dirs, deps, test de escritura |
| `C1_CONFIG_local.py` | Rutas, DB, TZ, límites de portfolio |
| `C1_5_PARAM_local.py` | `CENTRAL_PARAMS` (**fuente de verdad**) + presets |
| `C2_BOVEDA_local.py` | SQLite: 22 tablas, backup, liveness, errores |
| `C2_5_CONTEXTO_local.py` | Liquidez: ATR, wicks, fractales, volume profile, OBI |
| `C3_DATA_QUALITY.py` | Calidad de datos: CLOSED/FORMING/STALE/DEGRADED |
| `C3_MACRO_local.py` | Cartógrafo v7.9.3: multi-TF, `ms_v2`, p_magnet, FFD |
| `C3_5_REGIME_ENGINE.py` | Régimen ADF: TREND_UP/DOWN/RANGE/CHAOS |
| `C4_SENIAL_VALIDATOR.py` | Registra señales, resuelve PnL 4/8/24h, métricas |

### Orquestación (local, sin Docker)
| Archivo | Qué hace |
|---|---|
| `main.py` | Runner de celdas |
| `scheduler.py` / `scheduler.bat` | Scheduler (local; en Render corre el de producción) |
| `ventana.py` | **Ventana operativa CONFIGURABLE** (JSON `ventana_operativa`). `python ventana.py --ver` / `--continuo` / `--inicio X --fin Y` |
| `iniciar_macro21.bat` | Lanzador local |
| `reporter.py` / `report_validator.py` | Reportes HTML/JSON |

### Control
| Archivo | Qué hace |
|---|---|
| `verificar.py` | ⭐ Chequeos de salud del proyecto. Correlo siempre. |
| `git/guardar.py`, `git/estado.py`, `git/deshacer.py`, `git/revisar_archivo.py` | Scripts de git (no sé git → usá estos) |
| `fixes/` | Scripts de patch, uno por intervención. Todos con `--deshacer`. |
| `analisis/` | Scripts de análisis de datos (post-mortem, MAE/MFE, re-score) |
| `config/CONSOLIDADO/central_params.json` | ⭐ Config real en disco (la que se usa) |
(902 resueltas a 24h). 914 señales

### Docs
| Archivo | Qué es |
|---|---|
| `docs/INFORME_MACRO2.1.md` | **La spec vigente.** Referencia. No se edita sin que te lo pidan. |
| `docs/PENDIENTES.md` | ⭐ La lista de trabajo. Acá va el tracking. |
| `docs/info/` | Specs de referencia: `data-lineage.md`, `spec-ms-v2-MACRO2.md` |
| `docs/investigaciones/` | ⭐ Tus investigaciones, con fuentes. Usar `PLANTILLA.md`. |
| `docs/LEEME.md` | Las reglas de `docs/`. Decime dónde va cada cosa nueva. |
| `docs/GUIA DE USO.txt` | Guía de uso del bot |
| `docs/prompt_inicial.md` | El prompt con el que arrancó el proyecto |
| `docs/local/` | ⛔ **NO versionado.** Chats de IA, borradores, material viejo. |
| `decisiones/` | ADRs: por qué se decidió cada cosa |

---

## 7. TABLA DE UMBRALES (fuente única de verdad)

> Si tocás un valor acá, actualizá esta tabla también.

| Parámetro | Valor | Quién lo lee | Dónde se define |
|---|---|---|---|
| `ADF_P_VALUE_THRESHOLD` | **0.05** | C3_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |
| `TREND_SLOPE_THRESHOLD` | 0.0012 | C3_5 | `C3_5_REGIME_ENGINE.py` (hardcoded) |
| `STRONG_BIAS_THRESHOLD` | 2 | C3_MACRO | `CENTRAL_PARAMS["macro"]` |
| `BREAKEVEN_THRESHOLD_PCT` | 0.05 | C4 (solo HR) | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `RESOLUTION_WINDOWS_HOURS` | 4, 8, 24 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded). **ADR 007 PROPUESTO**: hacerlo config `[4,8,12,16,20,24]` (requiere +25 columnas) |
| `SCORE_V2_FUERTE` / `MODERADA` | 4.0 / 2.0 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `ALL_ASSETS` | 12 activos | C1_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |
| `ventana_operativa` | MODO + HORA_INICIO/FIN | `ventana.py`, `scheduler.py` | `config/CONSOLIDADO/central_params.json` → `CENTRAL_PARAMS["ventana_operativa"]` |

**Regla de ADF:** el valor tiene que estar en `CENTRAL_PARAMS["macro"]` y
**todos** lo leen de ahí. `python verificar.py` compara C3_5 vs C3_MACRO vs el
JSON en disco y avisa si se desincronizan. (ADR 002 — ya aplicado.)

---

## 8. RITUAL GIT

Yo no sé git. Vos me das el comando literal.

| Momento | Comando |
|---|---|
| Ver dónde estoy | `python git\estado.py` |
| Checkpoint antes de tocar | `python git\guardar.py "antes de: <qué>"` |
| Verificar un paste | `python git\revisar_archivo.py <archivo>` |
| Guardar el cambio | `python git\guardar.py "<qué cambiaste>"` |
| Subir a desarrollo | `git push origin main` |
| Deshacer | `python git\deshacer.py` |
| Mandar a producción (solo si corresponde) | `git push origin-macro2 main` |

**Remotos:**
- `origin` → `botmacro2-1` = **desarrollo**. Subí siempre acá.
- `origin-macro2` → `botmacro` = **PRODUCCIÓN (Render + Docker, congelado)**.

---

## 9. CONGELADO (no tocar sin ADR)

- `data/vault_v2.1.db` → las señales. **Activo principal del proyecto.**
- `.env` → claves de API.
- `C3_DATA_QUALITY.py` → validado, lo consumen 3 módulos.
- `decisiones/000-render-litestream-r2.md` → configuración de **producción**
  (Render + Docker + Litestream + R2). MACRO2.1 no lo usa.
- `docs/INFORME_MACRO2.1.md` → la spec de referencia.
- Todo lo que esté en `botmacro` (producción) hasta que se valide en 2.1.

<!-- H-22:GOB-IQ -->
---

## 8. LA FÓRMULA REAL DE `macro_score_v2` (verificada en código, 26/10)

> `AGENTS.md` §5.1.c **no reproduce** el score real (0/914). Esta es la versión
> correcta, leída de `C3_MACRO_local.py` líneas 1484-1661. **Fuente de verdad.**

### 8.1 Semántica del ADF (error histórico, ya corregido)

`p_value_adf < 0.05` significa **ESTACIONARIO**, NO momentum.
La rama momentum (p ≥ 0.05) se activa cuando la serie **NO** es estacionaria.

### 8.2 Las piezas (`_calculate_ms_v2`, líneas 1588-1661)

| Pieza | Origen | Rango |
|---|---|---|
| `poc_score` | POC de la caja | {-1, +1} |
| `caja_p` | caja amplificada por volumen/ATR (`am` 0.5-2.0, línea 1495-1496) | {-2..+2} |
| `fvg` | FVG | {-1, 0, +1} |
| `rs` | **ordinal de `rvd`**, NO el CVD crudo (línea 1487) | {-2,-1,0,+1,+2} |
| `d` | divergencia POC/FLUJO (ver 8.4) | {−2, 0, +2} |

```python
# línea 1487  <-- CLAVE: rs es un ORDINAL de rvd, no el CVD crudo
rs = 2 if rvd > 0.3 else (1 if rvd > 0.1 else (-2 if rvd < -0.3 else (-1 if rvd < -0.1 else 0)))
```

### 8.3 Las dos ramas

```python
if is_stationary:      # p_value_adf < 0.05
    ms_v2 = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
else:                  # rama momentum
    ms_v2 = 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs

s_mtf = 0.30*bias_1h + 0.20*bias_4h + 0.15*bias_1d
d = -2.0 if (poc == 1 and rs <= -1) else (+2.0 if (poc == -1 and rs >= 1) else 0.0)
macro_score_v2 = round(ms_v2 + s_mtf + d, 2)
```

### 8.4 `d` NO es degenerado (refutado el 26/10)

`d` se activa cuando `|rvd| > 0.1` **y el POC está del lado opuesto al flujo**
⇒ es una **divergencia precio/flujo real**, con umbral FIJO (sin calibrar).
**No se elimina.** (Una revisión externa lo marcó como degenerado por leer el
nombre de la variable `score_desglose["cvd_crud"]`, que es engañoso.)

### 8.5 `score_desglose` real (líneas 1544-1552)

```
poc · caja · caja_raw · atr_multiplier · fvg · cvd_crud(=rs ordinal) · rvd_ultimo
```

### 8.6 Dos rutas silenciosas que devuelven 0.0

- línea 1603-1605: `if not isinstance(desglose, dict): return 0.0`
- línea 1659-1661: `except(...): logger.debug(...); return 0.0`

### 8.7 El score LEGACY (el que tiene el sesgo)

```python
# línea 1500
ms = poc_score + caja_p + fvg + rs          # pesos 1,1,1,1
# línea 1502-1510
if abs(ms) >= STRONG_BIAS_THRESHOLD and rs == 0:  bv, bi = "RANGO", "NOISE"
```

`STRONG_BIAS_THRESHOLD = 2` (línea 260).
**⇒ El filtro real de emisión es `|ms| >= 2` Y `rs != 0` ⇔ `|rvd| > 0.1`.**
**⇒ Y como `rs` pesa 1, `rs = ±2` (rvd > 0.3) ya alcanza el umbral solo
⇒ en la práctica el filtro es "`rvd` > 0,3" (o < −0,3).**

**⇒ `bias_visual` (BULL/BEAR/RANGO) y el tipo de señal (LONG/SHORT) salen del
MISMO número `ms`. Por eso coinciden en el 100% de las señales.**

---

## 9. EL FILTRO DE RÉGIMEN NO FUNCIONA (H-22, 26/10)

```python
# C3_MACRO_local.py 1901-1925
p42 = 1.0     # default
p50 = 1.0     # default
try:
    p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
    p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
except _C3_EXC as exc:
    logger.warning(f"C3 ADF/FFD fallback {coin}: {exc}")
# línea 2331
dual = "si" if (p42 <= _T_ADF_THR and p50 <= _T_ADF_THR) else "no"
```

**⇒ Los `p_value_adf = 1.0` EXACTOS (648 de 914 filas = 71%) NO son un p-value:
son el DEFAULT de la línea 1901 cuando la función lanza excepción.**
**⇒ En el 71% de las señales NO SE CORRIÓ NINGÚN TEST DE RÉGIMEN.**

### 9.1 Consecuencia fatal para el análisis

> "El score v2 se calcula sólo en régimen estacionario fuerte (p<0,001)" → **FALSO**.
> Es "en los casos donde el ADF **NO falló** y además dio p<0,001".

**⇒ Las señales con score real son un SUBMUESTRO SELECCIONADO POR ÉXITO DEL TEST.**
**⇒ NO se puede "activar/desactivar" el score a posteriori.**
**⇒ El OOS tiene que ser PROSPECTIVO: emitir siempre, registrar el score, decidir después.**

### 9.2 Regla para código nuevo

**Un test que falla NO puede dejar un valor por defecto indistinguible de un
resultado.** Si el ADF falla ⇒ `p_value_adf = NULL` + `regimen_test_ok = 0`.
Nunca `1.0`. (ADR 008)

---

## 10. AFIRMACIONES PROHIBIDAS (la lista negativa del gobierno)

**Si una de estas aparece en un análisis, en un chat o en un commit, está mal.
No se acepta sin volver a la fuente.**

1. ❌ **"El `macro_score_v2` tiene poder predictivo."** — No lo tiene demostrado.
   ρ(ms2, pnl24) = +0,119 dentro de RANGE. NO-GO cerrado el 26/10.
2. ❌ **"El sesgo multi-TF no funciona."** — FALSO. `gem_macro_snapshot` da
   N/A sólo 5,6% (1D), 5,8% (4H), 0% (15m). Funciona.
3. ❌ **"El score se calcula en régimen estacionario fuerte."** — FALSO.
   Se calcula donde el test NO FALLÓ (71% de las veces no corrió). Ver §9.
4. ❌ **"El score v2 está contaminado por la escala del volumen."** — FALSO.
   `caja_p` ya se normaliza por ATR (`am` 0.5-2.0) y `rs` es un ordinal acotado.
   El score ES comparable entre activos.
5. ❌ **"El término `d` es degenerado / hay que eliminarlo."** — FALSO.
   Es una divergencia precio/flujo real con umbral fijo sin calibrar.
6. ❌ **"El score v2 es una regresión por usar `cvd_crud` en vez de `rvd_ultimo`."**
   — FALSO: `rs` YA es un ordinal de `rvd`. El problema es otro: el v2 sube el
   peso de caja/fvg y baja el del flujo, que es lo único con evidencia.
7. ❌ **"MACRO2.1 es un bot de trading."** — NO. Es un **predictor + validador**
   de tendencia macro. No tiene posiciones, SL ni TP. El MAE/MFE es
   diagnóstico de TIMING, no P&L.
8. ❌ **"Se puede comparar HR/PF entre etiquetas o ventanas sin cortar por día."**
   — Y el grano correcto es el **CICLO**, no el día (25 ciclos para 146 señales;
   3 ciclos del 20/10 con HR 0% y 3 del 21/10 con HR 85-89%).

---

## 11. PROTOCOLO OOS (Track C) — se escribe ANTES de empezar

**Unidad de evaluación: el CICLO**, no la señal.
(25 ciclos para 146 señales; la mediana es 6 señales por ciclo ⇒ cortar por día
mezcla poblaciones distintas.)

| Elemento | Regla |
|---|---|
| **N** | nº de señales independientes, escrito ANTES |
| **M** | nº de días naturales distintos, escrito ANTES |
| **Benchmark** | aleatorio, con el MISMO perfil de señales (n, tipo, hora) |
| **Corrección** | Benjamini-Hochberg FDR + **t > 3,0** (Harvey-Liu-Zhu 2016, RFS 29(1):5-68) |
| **Expectativa** | se compara contra el benchmark, no contra 0 pelado |
| **T₀** | fecha del deploy con Track A listo |
| **Ventana** | 30 días |
| **NO-GO** | si la expectativa neta ≤ 0 ⇒ **CLAUSURA DEFINITIVA del proyecto** |

**⇒ "Si el score v2 predice" NO es la pregunta del OOS.**
**⇒ La pregunta es: _"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"_**

### 11.1 La segunda opinión (26/10) y sus 3 correcciones

La revisión externa concluyó con **NO-GO del score como predictor** y propuso:
agrupar por ciclo, t>3,0, lista negativa de gobierno y criterio de muerte.
**Sus 3 errores, ya corregidos:**

- **E1** — mezcló **Caracas con UTC**. La ventana acordada es 04:00-16:00
  **Caracas (UTC−4)** (confirmado con 3 pares epoch↔fecha de la DB).
  Su conclusión "migrar a VPS por las 20:00" queda sin base…
  **PERO:** la franja de las 20:00 Caracas (HR 76%, n=25) está FUERA de la
  ventana 04:00-16:00, y la de las 08:00 (HR 7,1%, n=14) está DENTRO.
  ⇒ El recorte quita la mejor franja y conserva la peor ⇒ **ADR 011**.
- **E2** — usó `cvd_crud` como si fuera el CVD crudo. **Resuelto el 26/10:**
  `rs` es un ordinal de `rvd` (línea 1487). Mi medición (ρ ≈ 0 con
  `cvd_raw_ultimo`) era la correcta.
- **E3** — usó `arXiv:2607.09230` (Jeon, U. Korea, 10-jul-2026) al revés: el
  paper es real pero trata transiciones de estado L2→1-5 min, NO precios a
  4h-24h. Su tesis real es **"state-first"** (el estado es el predictor de
  primer orden; cada capa sólo se acredita si aporta incremental), que sí
  respalda el NO-GO estructuralmente. **Su diseño (OOS enrollado, event-clustered,
  blocked permutation tests) es el que hay que montar.**

---

## 12. DÓNDE ESTÁ TODO (mapa para la IA que toma el control)

| Necesito | Archivo |
|---|---|
| **Brief completo para una IA nueva** | `docs/RELEVO_IA.md` ← **leé esto primero** |
| Reglas + mapa del pipeline | `AGENTS.md` (este archivo) |
| Dónde estoy hoy | `ESTADO.md` |
| Qué falta | `docs/PENDIENTES.md` |
| Qué se decidió y por qué | `decisiones/00X-*.md` (8 ADRs) |
| Spec original (NO editar) | `docs/INFORME_MACRO2.1.md` |
| Gate antes de commitear | `python verificar.py` |
| Historial de cambios | `python git/estado.py` · `git/guardar.py` · `git/deshacer.py` |

**⇒ Antes de tocar código: leé `docs/RELEVO_IA.md` + `ESTADO.md` + el ADR
vigente. Después: escribí el diseño en el chat y ESPERÁ el "ok".**