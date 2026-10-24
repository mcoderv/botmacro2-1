#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
actualizar_gobierno.py — Reescribe el "gobierno" del proyecto MACRO2.1.

Escribe / actualiza:
    AGENTS.md                              (completo, reescrito)
    ESTADO.md                              (completo, reescrito)
    HANDOFF.md                             (completo, reescrito)
    docs/PENDIENTES.md                     (completo, reescrito)
    decisiones/003-macro21-local-sin-docker.md   (NUEVO)

Parchea (solo texto, con .bak):
    decisiones/002-unificar-umbral-ADF.md  (marca APLICADO)
    verificar.py                           (chequea ADR 003 + fix del check de duplicado)

    docs/INFORME_MACRO2.1.md               NO SE TOCA (queda como spec de referencia)

USO:
    python fixes\\actualizar_gobierno.py
    python fixes\\actualizar_gobierno.py --deshacer
"""
import shutil
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent


def _detectar_raiz():
    marcadores = ["C1_CONFIG_local.py", "scheduler.py", "requirements.txt", "verificar.py"]
    d = _AQUI
    for _ in range(6):
        if any((d / m).exists() for m in marcadores):
            return d
        if d.parent == d:
            break
        d = d.parent
    return _AQUI.parent


RAIZ = _detectar_raiz()
BAK = RAIZ / "fixes" / "_bak_gobierno"


# ═════════════════════════════════════════════════════════════════════════════
# AGENTS.md
# ═════════════════════════════════════════════════════════════════════════════
AGENTS_MD = """# AGENTS.md — MACRO2.1 (local, experimental)

> Este archivo lo lee la IA en CADA turno. Si es largo, lo skimmea.
> Mantenelo corto. Lo que la IA puede leer sola en el código, NO va acá.
> Lo que la IA NO puede adivinar, va acá.

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
| Entrega de archivos | Los archivos van **directo a la carpeta destino** del proyecto (`fixes\\`, `analisis\\`, etc.). **NO des comandos `copy` desde Descargas.** |

**Formato obligatorio de cada comando que me des:**

```
PASO N — [qué hace en una línea]

    <comando literal, listo para copiar, CMD>

✅ Deberías ver: [output esperado]
❌ Si falla: [qué significa + qué te pego]
📂 Desde: [carpeta exacta]
```

- **UN paso a la vez.** Nunca 3 comandos juntos.
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

**Herramienta: `python analisis\rescore_umbral_v2.py`** (reconstruye el score
sin tocar la DB, con auto-validaciones y corte temporal).

### 5.3 Lo que YA está hecho — no lo rehagas

| Tema | Estado real |
|---|---|
| `scheduler.py` lee `PORT` del entorno | ✅ **YA ESTÁ HECHO** (punto 3 del informe). Ya usa `HEALTH_PORT`/8080 como fallback. |
| Bucket R2 = `mercabot-qwen-db` | ✅ **YA ESTÁ HECHO** (punto 6 del informe). No lo "arregles" de nuevo. |
| Umbral ADF unificado en 0.05 | ✅ **APLICADO** (ADR 002, commit `5361b4f`). Fuente única: `CENTRAL_PARAMS["macro"]`. |
| Carpetas de backup `backups_v2.1` | ✅ Arreglado (H-3) en el mismo commit. |
| Sin Docker en 2.1 | ✅ Decidido (ADR 003). `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.sh` y `litestream.yml` fueron borrados del clon local. **Producción (`botmacro`) los sigue teniendo.** |

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
  `C:\\Users\\MD\\Desktop\\MACRO2.1_BACKUP\\`. **Falta subirlo a Drive** — hasta
  entonces sigue siendo un solo disco. Es el único recurso del proyecto que
  no se recupera de GitHub.

### 5.5 El régimen de mercado y `ms_v2` no se hablan

- `C3_5_REGIME_ENGINE.py` corre el ADF **sobre niveles**.
- `C3_MACRO_local.py` corre el ADF **sobre residuales FFD** (otro test).
- Los dos usan el mismo umbral (0.05) pero **son tests distintos**. El motor
  de régimen no mueve el conmutador de `ms_v2`.
- Decisión pendiente (ADR 001 / pending). **No los "unifiques" sin un ADR.**

---

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
| `ventana.py` | Ventana operativa 08:00-17:00 Caracas |
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
| `data/vault_v2.1.db` | ⭐ La DB. 907 señales (877 resueltas a 24h). **No tocar, no versionar** |

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
| `RESOLUTION_WINDOWS_HOURS` | 4, 8, 24 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `SCORE_V2_FUERTE` / `MODERADA` | 4.0 / 2.0 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `ALL_ASSETS` | 12 activos | C1_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |

**Regla de ADF:** el valor tiene que estar en `CENTRAL_PARAMS["macro"]` y
**todos** lo leen de ahí. `python verificar.py` compara C3_5 vs C3_MACRO vs el
JSON en disco y avisa si se desincronizan. (ADR 002 — ya aplicado.)

---

## 8. RITUAL GIT

Yo no sé git. Vos me das el comando literal.

| Momento | Comando |
|---|---|
| Ver dónde estoy | `python git\\estado.py` |
| Checkpoint antes de tocar | `python git\\guardar.py "antes de: <qué>"` |
| Verificar un paste | `python git\\revisar_archivo.py <archivo>` |
| Guardar el cambio | `python git\\guardar.py "<qué cambiaste>"` |
| Subir a desarrollo | `git push origin main` |
| Deshacer | `python git\\deshacer.py` |
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
"""


# ═════════════════════════════════════════════════════════════════════════════
# ESTADO.md
# ═════════════════════════════════════════════════════════════════════════════
ESTADO_MD = """# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~75 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-24
Commit      : 23efea4 (limpieza fixes/ y analisis/)
Repo        : botmacro2-1  (desarrollo, local, SIN Docker)  |  botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h)
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre de punta a punta (`python main.py`), 8 celdas, sin excepciones
- [x] `data/vault_v2.1.db` con **914 señales (902 resueltas a 24h)** — la última corrida registró +7
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2)
- [x] **I-2** — Motor de régimen ADF real
- [x] **ADR 002 aplicado** — umbral ADF unificado en 0.05, fuente única `CENTRAL_PARAMS["macro"]`
- [x] **H-3 y H-5 corregidos** — carpetas `backups_v2.1`/`logs_v2.1` y `_migrar_v28` sobrescribe
- [x] **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso
- [x] **Sin Docker en 2.1** (ADR 003) — producción intacta
- [x] **`docs/` ordenada** — `docs/local/` fuera de GitHub, `docs/LEEME.md` con las reglas
- [x] **Backup local de la DB** en `Desktop\\MACRO2.1_BACKUP\\` (falta subirlo a Drive)

---

## 📊 MÉTRICAS (24h, snapshot de 877 resueltas del 23/10)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| **GLOBAL** | 877 | 44.7% | 0.80 | −0.156% |
| LONG | 429 | 32.4% | **0.50** | −0.488% |
| SHORT | 448 | 56.5% | **1.28** | +0.163% |
| xyz:SILVER | 58 | 63.8% | 3.22 | +0.768% |
| xyz:GOLD | 93 | 51.6% | 2.64 | +0.309% |
| BTC | 64 | 23.4% | **0.30** | −0.630% |
| xyz:SP500 | 88 | 39.8% | **0.28** | −0.351% |

**LONG pierde plata, SHORT gana.** Problema estructural, no de umbral.
El k×σ (ADR 001) **no lo arregla**: el PF no depende del break-even.

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | Backup de la DB solo en un disco | Hecho local (`Desktop\\MACRO2.1_BACKUP\\`), falta Drive | 🟡 **Falta subirlo a Drive** |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | 🟡 Pendiente → matar fallbacks |
| **H-9** | **`ms_v2` con `s_mtf = 0`** (bias 1D/4H/1H sale N/A en 7 de 12 activos) y **la rama momentum casi nunca se activa** (856 de 877 señales con p < 0.02) | El score v2 no tiene su componente multi-TF y `rs` (el flujo) pesa 0.5 en vez de 2.0. **El v2 no discrimina** | 🔴 **NUEVO — MAXIMA prioridad** |
| **H-10** | **Las etiquetas NO son comparables entre sí**: la distribución cambió por completo el 19/10 (0 FUERTE → 1 → 9 → 10) | Cualquier HR/PF por etiqueta es un confound temporal | 🔴 **NUEVO** |
| **H-11** | `main.py` corre **8 celdas, no 9** (falta `C3_DATA_QUALITY` como celda) y el runner dice "Celdas ejecutadas: 3" | Cosmético, pero el mapa de `AGENTS.md` miente | 🟡 Nuevo |
| **H-12** | C2 dice "Sin backups previos" → el auto-restore nunca tuvo nada que restaurar. Y la nota operativa apunta a `GEM5_INSTITUTIONAL_VAULT.db` (nombre inexistente) | El auto-restore nunca se probó de verdad | 🟡 Nuevo |
| **H-2** | Dos ADF distintos (niveles en C3_5 vs residuales FFD en C3_MACRO) | El régimen no mueve el conmutador de `ms_v2` | 🟡 Pendiente de decisión |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo | Sesga HR (no el PF) | 🟡 Pendiente → ADR 001 |
| **H-6** | `SCORE_ALTA=14` / `SCORE_MEDIA=8` con `macro_score` máximo 6 | Código muerto. Todo cae en BAJA o RUIDO | 🟡 Pendiente → `calidad_senal_v3` |
| **H-8** | 6 cripto pierden (BTC PF 0.30) mientras TradFi gana | Estructural, no de umbral | 🟡 En investigación |
| **H-5** | `_migrar_v28` no sobrescribía el JSON guardado | El default del código no se aplicaba | ✅ RESUELTO |
| **H-1** | Umbral ADF 0.02 en C3_MACRO vs 0.05 en C3_5 | El régimen y el `ms_v2` se contradecían | ✅ RESUELTO |
| **H-3** | `C0` escribía en `backups/`, `C2` leía de `backups_v2.1/` | El auto-restore no encontraba nada | ✅ RESUELTO |

---

## ⏰ ANTES DE CUALQUIER COSA

**Subí `C:\\Users\\MD\\Desktop\\MACRO2.1_BACKUP\\` a Drive.** El backup
local ya está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`.
Es lo único del proyecto que **no** se recupera de GitHub.

---

## ➡️ SIGUIENTE PASO (uno solo)

**Cerrar H-9 y H-10: entender por qué el `bias` 1D/4H/1H sale `N/A` y qué pasó
el 19/10.**

Dos comandos que ya están pendientes:
```
findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\\*.log
```
→ dice si el `N/A` es por pocas velas (Hyperliquid no devolvió 20) o por error.

**Pregunta para el usuario:** ¿qué cambió el 2026-10-19 en el pipeline? Candidatas:
(1) desplegaste v7.9.3, (2) cambiaste la ventana operativa o reiniciaste el
scheduler (→ el "Ojo B" del pendiente #4), (3) tocaste C3_MACRO / C3_DATA_QUALITY.

**Después**: métricas por etiqueta **dentro de cada día** (elimina el confound de
H-10) y, con el diagnóstico cerrado, un ADR para la rama del `ms_v2`.

**Herramienta:** `python analisis\\rescore_umbral_v2.py` (ya tiene el corte
por día y el corte por subgrupo).

---

## 📌 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- Un cambio por sesión. Y un commit por cambio.
"""


# ═════════════════════════════════════════════════════════════════════════════
# HANDOFF.md
# ═════════════════════════════════════════════════════════════════════════════
HANDOFF_MD = """# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a los chats viejos que venías guardando a mano.
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `docs/PENDIENTES.md`
> + `git log --oneline -20` + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-24
Sesion   : 3
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : 23efea4
DB       : 914 señales (902 resueltas a 24h)
```

---

## 1. Qué hice en esta sesión

- **Docker eliminado de MACRO2.1** (ADR 003): `Dockerfile`, `docker-compose.yml`,
  `.dockerignore`, `start.sh`, `litestream.yml`. **Producción (`botmacro`) intacta.**
- **`docs/` reordenada**: `docs/INFORME_MACRO2.1.md` (spec, intacta),
  `docs/PENDIENTES.md` (tracking), `docs/info/`, `docs/investigaciones/` (+`PLANTILLA.md`),
  `docs/local/` (fuera de GitHub). `textos/` eliminada.
- **Gobierno reescrito**: `AGENTS.md`, `ESTADO.md`, `HANDOFF.md`, `docs/PENDIENTES.md`
  + ADR 003. `verificar.py` ahora chequea los 4 ADRs.
- **`rescore_umbral.py` v2**: el v1 re-scoreó placeholders (ms_v2 = 0) y dio falsos
  positivos. La v2 clasifica reconstruible / no reconstruible, re-scorea solo las
  reconstruibles, aborta si la auto-validación 1 no da ≥90%, y reporta el corte temporal.
- **Pipeline verificado de punta a punta**: `python main.py` corre las 8 celdas sin
  excepciones y registró +7 señales (907 → 914).
- **Backup local de la DB** en `Desktop\\MACRO2.1_BACKUP\\` (falta Drive).

---

## 2. Los hallazgos importantes (léelos antes de tocar el score)

### 2.1 El ADR 002 es INMEDIBLE con los datos actuales

- **0 señales cambian de etiqueta** al pasar de 0.02 a 0.05.
- Motivo: de las 10 que cambian de rama, 9 son placeholders y 1 ya estaba en 0.05.
  **Solo 1 señal se generó con el umbral nuevo.**
- No significa que el ADR sea inútil: significa que **no hay historia con umbral
  viejo Y score v2 a la vez**. Necesita ~30 días más de datos.

### 2.2 El `ms_v2` opera con dos inputs degradados (H-9)

1. **`s_mtf` = 0 en 7 de 12 activos.** El bias 1D/4H/1H sale `N/A`.
2. **La rama momentum casi nunca se activa.** `P-v4.2` < 0.001 en los 12 activos de
   la última corrida; en el histórico **856 de 877 señales tienen p < 0.02**.

→ El score v2 es siempre `0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs + 0 + d`.
El flujo (`rs`), que es el componente que mejor predice la dirección, pesa **0.5**
en vez de 2.0.

**Consecuencia medida:** `(poc=±1, rs=±2, caja+fvg=∓1)` → `s_base = 0 EXACTO` en
estacionario y `±4` en momentum. Esos breakouts con flujo fuerte quedan con
`ms_v2 = 0` → etiqueta RUIDO. Hecho de fórmula, verificable sin datos.

### 2.3 Las etiquetas NO son comparables entre sí (H-10)

La distribución cambió por completo el 19/10: 0 FUERTE → 1 → 9 → 10.
**Comparar HR/PF entre etiquetas = comparar días distintos.** El "RUIDO tiene
PF 4.43" NO es evidencia.

**Siempre cortar por día (o por ventana) antes de comparar etiquetas.**

### 2.4 Cuántas señales tienen score v2 REAL: 111 (no 129)

| Grupo | n |
|---|---|
| `ms_v2 >= 2` (FUERTE 20 + MODERADA 38) | 58 |
| `ms_v2 < 2` coherente | 53 |
| Placeholders casualmente coherentes (13-18/10) | 18 ⚠️ NO son score real |
| Placeholders incoherentes | 748 |

**Con 111 señales, cualquier corte por etiqueta es ruido.**

---

## 3. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Arreglar el `s_mtf = 0` / la rama del `ms_v2` | Es un cambio al scoring → necesita ADR, y el diagnóstico del `N/A` no está cerrado. |
| Métricas por etiqueta dentro de cada día | Es el próximo corte, pero con n=5-28 por celda va a ser ruido. Primero el diagnóstico. |
| `calidad_senal_v3` (etiquetas 14/8/4) | Es sobre el `macro_score` **legacy**, otro problema. |
| ADR 001 (k×σ) | Mueve el HR, no el PF. Decidir si vale. |
| Max DD de `report_validator.py` | Confirmado que `C4` lo calcula bien; el bug está aislado en `report_validator.py`. Hace falta el archivo. |
| Ventana 04:00-16:00 | Changes el régimen de muestreo → invalidaría la comparabilidad otra vez. Coordinar con H-10. |
| Matar los 5 fallbacks silenciosos | Toca 4 módulos. Sesión propia. |
| Backup a Drive | **Es una acción manual tuya.** Es la prioridad #1 y no la puedo hacer yo. |

---

## 4. Qué creo que está frágil (opinión sin filtros)

1. **El score v2 no puede discriminar** (H-9). Sin el término multi-timeframe y
   siempre en la misma rama, es ruido con nombre bonito. **Arreglar esto tiene
   más impacto que recalibrar cualquier umbral.**
2. **Cualquier análisis del v2 sobre las 877 señales es basura.** El grupo real
   son 111 (3 días). Y aun esas están confundidas por fecha.
3. **Los 5 fallbacks silenciosos** siguen siendo el riesgo #1 latente. Hoy no
  aroni (verificado línea por línea), pero el día que uno se dispare, el
   pipeline se degrupa y no dice nada.
4. **`main.py` corre 8 celdas, no 9**, y el runner reporta "Celdas ejecutadas: 3".
   Cosmético, pero el mapa de `AGENTS.md` miente.
5. **El auto-restore nunca se probó**: C2 dice "Sin backups previos". Si mañana
   corrompés la DB, no hay de dónde restaurar.
6. **LONG pierde, SHORT gana** (PF 0.50 vs 1.28). Y dentro de los cripto, BTC
   PF 0.30 y SP500 PF 0.28. Eso no lo arregla ningún umbral: es microestructura
   o lógica de entrada. `xyz:SILVER` (PF 3.22) y `xyz:GOLD` (2.64) sí funcionan.
   **Copiar el patrón de los que ganan vale más que recalibrar umbrales.**
7. **Cero tests.** `verificar.py` es el primer paso, no el final.

---

## 5. Qué chequear primero en la próxima sesión

1. `python verificar.py` → tiene que dar 19 ok / 0 fallas.
2. `python git\estado.py` → leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `AGENTS.md` §5.1, §5.1.b y §5.1.c — son los hallazgos de hoy.
4. Si tocás el v2: leer `AGENTS.md` §5.1.b ANTES de comparar etiquetas.

---

## 6. Cómo verificar que no rompí nada

```cmd
python verificar.py
python git\revisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 7. Cosas pendientes de confirmación (preguntas abiertas)

- **¿Qué cambió el 2026-10-19 en el pipeline?** (desplegue de v7.9.3 / cambio
  de ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es un
  artefacto de despliegue o de diseño.
- **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** El motivo está en
  `logs_v2.1\\*.log` (`no_data_or_too_few` / `INSUFFICIENT` / `exception:`).
- ¿Los 4 archivos "Nivel C" se borran o se quedan?
- ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
- ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
"""


# ═════════════════════════════════════════════════════════════════════════════
# docs/PENDIENTES.md
# ═════════════════════════════════════════════════════════════════════════════
PENDIENTES_MD = """# PENDIENTES — MACRO2.1

> **Este archivo es el tracking oficial.** Si algo está pendiente, va acá.
> `docs/INFORME_MACRO2.1.md` es la **spec de referencia** (no se edita);
> este archivo es el que dice **qué falta y qué se hizo**.
>
> Actualizado: 2026-10-24

---

## ✅ HECHOS (cerrados)

| # | Qué | Dónde |
|---|---|---|
| 1 | Umbral ADF unificado en **0.05**, fuente única `CENTRAL_PARAMS["macro"]` | ADR 002, commit `5361b4f` |
| 2 | `C0`/`C2` usan `backups_v2.1` / `logs_v2.1` | H-3, commit `5361b4f` |
| 3 | `_migrar_v28` **sobrescribe** el `central_params.json` guardado | H-5, commit `5361b4f` |
| 4 | **`scheduler.py` ya lee `PORT`** del entorno | Ya estaba, confirmado en `5e0c481` |
| 5 | Bucket R2 = `mercabot-qwen-db` (no `macrobot-vault`) | Ya estaba |
| 6 | Sin Docker en MACRO2.1 | ADR 003, commit `5e0c481` |
| 7 | `docs/` reordenada, `textos/` eliminada, `docs/local/` fuera de GitHub | commit `5e0c481` |
| 8 | Kit de git (`guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`) | commit `5361b4f` |
| 9 | `verificar.py` con 19 checks, incluidos los 4 ADRs | commit `da0ad11` |
| 10 | `rescore_umbral.py` v2 (solo reconstruibles, aborta si AV1 < 90%) | `analisis/` |
| 11 | `fixes/` y `analisis/` limpios (parches de una vez → `docs/local/`) | commit `23efea4` |
| 12 | **Pipeline verificado de punta a punta** (`python main.py`, 8 celdas, +7 señales) | 2026-10-23 |
| 13 | **Backup local de la DB** en `Desktop\\MACRO2.1_BACKUP\\` | 2026-10-23 |

---

## 🔴 CÓDIGO (pendientes del informe técnico)

### 1. `ms_v2`: `s_mtf = 0` + rama momentum inactiva  ← **AHORA ES EL #1**
- **Problema (H-9):** el bias 1D/4H/1H sale `N/A` en 7 de 12 activos → `s_mtf = 0`.
  Y el p del residual FFD sale < 0.02 en 856 de 877 señales → **la rama momentum
  casi nunca se activa**. El score v2 queda siempre en
  `0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs + 0 + d`.
- **Consecuencia:** el flujo (`rs`), que mejor predice la dirección, pesa 0.5 en
  vez de 2.0. Las señales `(poc=±1, rs=±2, caja+fvg=∓1)` dan `s_base = 0 EXACTO`
  → quedan como RUIDO.
- **Bloqueante:** no se sabe todavía por qué el bias sale `N/A`.
  → `findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\\*.log`
- **Posibles fixes (todas necesitan ADR):** (A) guardar ambas ramas en columnas
  separadas; (B) decidir la rama por detección de breakout en vez del ADF; (C)
  piso al `rs` en la rama estacionario.
- **Ojo:** `AGENTS.md` §5.1.c

### 2. El score v2 no se puede evaluar todavía (H-10)
- **Problema:** la distribución de etiquetas cambió por completo el 19/10
  (0 FUERTE → 1 → 9 → 10). Comparar HR/PF entre etiquetas = comparar días distintos.
- **Pendiente:** (a) saber qué cambió el 19/10; (b) medir por día antes de comparar.
- **Herramienta:** `python analisis\\rescore_umbral_v2.py` (ya corta por día y por subgrupo).

### 3. Etiquetas de calidad → `calidad_senal_v3`
- **Problema (H-6):** umbrales legacy (14/8/4) incompatibles con `macro_score` (máx real 6).
- **Corrección:** recalibrar a ALTA (≥4) / MEDIA (≥3) / BAJA (≥2), o usar el score crudo.
- **Ojo:** es sobre el `macro_score` **legacy**, otro problema distinto del v2.
  Con 111 señales reales, los cortes quedan en 20-40 → **riesgo alto de
  sobreajuste.** Considerar **columna nueva**, sin mutar la legacy.

### 4. Umbral dinámico k×σ → ADR 001
- **Problema (H-4):** `BREAKEVEN_THRESHOLD_PCT = 0.05` fijo. Trivial para BTC, excesivo para `xyz:EUR`.
- **Corrección:** `umbral = k * σ`, en **columna nueva**, con baseline recalculado.
- **Realidad:** mueve el **HR**, **no el PF** (`C4` calcula el PF con `p > 0` / `p < 0`).
- **Decisión pendiente:** ¿se implementa o se pospone?

### 5. `report_validator.py` → Max DD
- **Problema:** reporta Max DD de 270.88% → está sumando drawdowns de segmentos.
- **Confirmado:** `C4_SENIAL_VALIDATOR._calculate_metrics` lo calcula **bien**
  (`np.cumsum` → pico-valle). El bug está **aislado** en `report_validator.py`.
- **Bloqueante:** hace falta el archivo para auditarlo.

### 6. `ventana.py` / `scheduler.py` → ventana 04:00-16:00
- **Problema:** la ventana 08:00-17:00 deja los targets de 8h fuera → 84.2% de contaminación.
- **Corrección:** ampliar a **04:00-16:00** (Caracas) + validación escalonada 4→8→12→16.
- **Ojo A:** `C4_SENIAL_VALIDATOR.py` tiene `RESOLUTION_WINDOWS_HOURS = [4, 8, 24]` hardcodeado. Hay que elegir.
- **Ojo B:** cambiar la ventana **cambia el régimen de muestreo → los datos nuevos no
  son comparables con los viejos.** Con H-10 abierto, esto puede ser la causa
  del corte del 19/10. **Coordinar antes de tocar.**

### 7. Matar los 5 fallbacks silenciosos de import  ← **riesgo #1 latente**
- `C2_5_CONTEXTO_local.py:78`, `C3_MACRO_local.py:42`, `:51`, `:126`, `C3_5_REGIME_ENGINE.py:60`
- Deben fallar fuerte, o tener un flag explícito.
- **Verificado el 23/10 que hoy ninguno se dispara.** El día que uno se dispare,
  el pipeline se degrupa sin avisar.

### 8. `main.py` corre 8 celdas, no 9
- Falta `C3_DATA_QUALITY` como celda (sí se importa). **Sin efectos a nivel de
  módulo → no rompe nada**, pero el mapa de `AGENTS.md` miente.
- El runner reporta "Celdas ejecutadas: 3" cuando corrieron 8.

### 9. C2: "Sin backups previos" + nombre de archivo equivocado
- El auto-restore **nunca ha tenido nada que restaurar**. Si mañana corrompés la DB,
  no hay de dónde recuperar.
- La nota operativa apunta a `GEM5_INSTITUTIONAL_VAULT.db`, que no existe
  (el real es `vault_v2.1.db`).

---

## 🟡 INFRAESTRUCTURA

### 10. Backup externo de la DB  ← **PRIORIDAD #1**
- `data\\vault_v2.1.db` (914 señales) y `.env`.
- Es lo único que **no** se recupera de GitHub.
- Copiar a Drive. Verificar que abre bien.

---

## ⚪ DESCARTADOS / EN MONITOREO

- **Eliminar los cripto del universo** → descartado. Se mantienen los 12.
- **Filtro v2 con pocas señales** → se resuelve con acumulación de datos. Ojo:
  solo **111 señales tienen score v2 real** (58 con `ms_v2 >= 2`, de las cuales 20
  son FUERTE). Con 20 señales cualquier comparación de HR es ruido.
- **MACRO2 (producción en Render)** → **DATA FREEZE**.

---

## ❓ PREGUNTAS ABIERTAS (sin respuesta del usuario)

1. **¿Qué cambió el 2026-10-19 en el pipeline?** (despliegue v7.9.3 / cambio de
   ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es
   artefacto de despliegue o de diseño.
2. **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en `logs_v2.1\\*.log`)
3. ¿Los 4 archivos "Nivel C" se borran o se quedan?
4. ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
5. ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
6. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
7. ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
"""


# ═════════════════════════════════════════════════════════════════════════════
# decisiones/003-macro21-local-sin-docker.md
# ═════════════════════════════════════════════════════════════════════════════
ADR003_MD = """# ADR 003 — MACRO2.1 es un clon local, sin Docker

**Estado:** ACEPTADO
**Fecha:** 2026-10-23
**Decide:** `botmacro2-1` (desarrollo) se ejecuta directo con Python en Windows.
**NO decide:** nada sobre `botmacro` (producción), que sigue igual.

---

## Contexto

`botmacro2-1` nació como clon de `botmacro` (MACRO2), que corre en Render como
Web Service con Docker. Al clonar, se copiaron también los artefactos de
despliegue: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.sh`
y `litestream.yml`.

Pero MACRO2.1 **nunca se ha desplegado**. Corre local, en Windows, con el
venv. Ningún `.py` del pipeline depende de Docker: la auditoría del 2026-10-23
encontró cero referencias a `docker`, `litestream` o `/app` en `main.py`,
`scheduler.py`, `ventana.py` y `report_validator.py`.

El único código que quedó acoplado era un chequeo inerte en `C1_CONFIG_local.py`:

```python
is_container = (os.name != "nt") and Path("/app").exists()
```

En Windows `os.name == "nt"` → **siempre False**. Código muerto.

Mantener esos archivos era ruido con riesgo real: cualquier IA que los leyera
podía "arreglar" el despliegue, instalar Docker, o meter `start.sh` en el
flujo local.

## Decisión

**MACRO2.1 es un proyecto local, sin Docker.**

Se eliminan de `botmacro2-1`: `Dockerfile`, `docker-compose.yml`,
`.dockerignore`, `start.sh`, `litestream.yml`.

**`botmacro` (producción) NO se toca.** Sigue con su `Dockerfile`, su
`start.sh` y su `litestream.yml` → R2. Los repos son separados: no hay
ninguna intersección. El DATA FREEZE sigue intacto.

## Consecuencias

**A favor:**
- El repo local refleja lo que realmente se ejecuta. Cero archivos mentirosos.
- Menos superficie: nadie puede deployar por accidente.
- La IA deja de intentar "reparar" un despliegue que no existe.
- Se separa el "stack de producción" (ADR 000) del "clon de trabajo" (este ADR).

**En contra / a tener en cuenta:**
- **No hay réplica a Cloudflare R2 desde 2.1.** El backup de 2.1 es local
  (`C2_BOVEDA` → `backups_v2.1/`). Para respaldar la DB de 2.1 hay que
  copiarla a mano a Drive o disco externo.
  → Esto **Eleva** la prioridad del backup externo (ver `docs/PENDIENTES.md` §6).
- Si algún día 2.1 se quiere desplegar, hay que recuperar los archivos:
  `git checkout 5e0c481 -- Dockerfile docker-compose.yml start.sh litestream.yml .dockerignore`
  o copiar los de `botmacro`.
- `C1_CONFIG_local.py` conserva el chequeo `is_container` (inerte en Windows)
  con el comentario aclarado. Se deja así a propósito: `botmacro` tiene su
  propia copia de ese archivo y el bloque sigue siendo necesario allá.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Borrar Docker también de `botmacro` | Rompe producción. Fuera de alcance (DATA FREEZE). |
| Dejar los archivos, "por si acaso" | Son la causa de la confusión. El historial de git los conserva. |
| Borrar el bloque `is_container` de `C1_CONFIG` | No cambia el comportamiento en Windows (siempre False) y obliga a tocar un archivo central. El comentario aclarado alcanza. |
| Instalar Docker localmente | No hace falta para nada del pipeline. |

## Cómo se verifica

```cmd
dir /a Dockerfile docker-compose.yml start.sh litestream.yml .dockerignore
```
→ "No se encuentra el archivo" en los 5.

```cmd
python verificar.py
```
→ 19 ok / 0 fallas / 1 aviso (el aviso es el de los 5 fallbacks silenciosos).

```cmd
git status
```
→ en el repo `botmacro`, ningún cambio.
"""


# ═════════════════════════════════════════════════════════════════════════════
# EJECUCIÓN
# ═════════════════════════════════════════════════════════════════════════════
def _backup(ruta):
    if not ruta.exists():
        return False
    BAK.mkdir(parents=True, exist_ok=True)
    destino = BAK / ruta.name
    if not destino.exists():
        shutil.copy2(str(ruta), str(destino))
    return True


def _escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


def _parchear(ruta, pares, etiqueta):
    """Sustituye pares (viejo, nuevo). Devuelve (ok, detalle)."""
    if not ruta.exists():
        return False, "no existe: %s" % ruta
    txt = ruta.read_text(encoding="utf-8", errors="replace")
    original = txt
    aplicados, fallidos = [], []
    for viejo, nuevo in pares:
        if viejo in txt:
            txt = txt.replace(viejo, nuevo, 1)
            aplicados.append(True)
        else:
            fallidos.append(viejo[:60])
    if txt == original:
        return False, "%s: nada que cambiar (puede que ya este actualizado)" % etiqueta
    _backup(ruta)
    ruta.write_text(txt, encoding="utf-8")
    return True, "%s: OK (%d cambios)" % (etiqueta, len(aplicados))


def aplicar():
    print()
    print("#" * 68)
    print("#  ACTUALIZAR EL GOBIERNO DEL PROYECTO")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 68)
    print()

    # ---------- 1. ESCRIBIR LOS 4 ARCHIVOS ----------
    print("=" * 68)
    print(" 1. ESCRIBIR DOCUMENTOS")
    print("=" * 68)
    documentos = [
        ("AGENTS.md", AGENTS_MD),
        ("ESTADO.md", ESTADO_MD),
        ("HANDOFF.md", HANDOFF_MD),
        ("docs/PENDIENTES.md", PENDIENTES_MD),
        ("decisiones/003-macro21-local-sin-docker.md", ADR003_MD),
    ]
    for rel, contenido in documentos:
        ruta = RAIZ / rel
        _backup(ruta)
        _escribir(ruta, contenido)
        print("   [OK] Escrito: %-45s (%d bytes)" % (rel, len(contenido)))
    print()
    print("   Backup de los anteriores en: fixes/_bak_gobierno/")
    print()

    # ---------- 2. PARCHEAR ADR 002 ----------
    print("=" * 68)
    print(" 2. MARCAR ADR 002 COMO APLICADO")
    print("=" * 68)
    adr2 = RAIZ / "decisiones" / "002-unificar-umbral-ADF.md"
    if not adr2.exists():
        print("   [AVISO] No se encontro decisiones/002-unificar-umbral-ADF.md")
    else:
        txt = adr2.read_text(encoding="utf-8", errors="replace")
        if "APLICADO" in txt.upper():
            print("   [OK] ADR 002 ya dice APLICADO. No se toca.")
        else:
            lineas = txt.splitlines()
            bloque = [
                "",
                "**Estado:** APLICADO (2026-10-23, commit `5361b4f`)",
                "",
                "> Umbral unificado en **0.05**, fuente unica `CENTRAL_PARAMS[\"macro\"]`.",
                "> Tambien se corrigio H-3 (`backups_v2.1` / `logs_v2.1`) y H-5",
                "> (`_migrar_v28` ahora sobreescribe el JSON guardado).",
                "> `verificar.py` -> 19 ok / 0 fallas / 1 aviso.",
                "> **Pendiente:** medir el efecto real (ver `docs/PENDIENTES.md` 7).",
            ]
            # insertar despues de la primera linea de titulo
            corte = 0
            for i, l in enumerate(lineas):
                if l.startswith("#"):
                    corte = i + 1
                    break
            lineas[corte:corte] = bloque
            _backup(adr2)
            adr2.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            print("   [OK] ADR 002 marcado como APLICADO")
    print()

    # ---------- 3. PARCHEAR verificar.py ----------
    print("=" * 68)
    print(" 3. ACTUALIZAR verificar.py (chequear ADR 003)")
    print("=" * 68)
    ver = RAIZ / "verificar.py"
    if not ver.exists():
        print("   [AVISO] No se encontro verificar.py")
    else:
        pares = [
            (
                '        ("decisiones/002-unificar-umbral-ADF.md", "ADR 002 (umbral ADF, con .md)"),\n',
                '        ("decisiones/002-unificar-umbral-ADF.md", "ADR 002 (umbral ADF, con .md)"),\n'
                '        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),\n',
            ),
            (
                'ok("[ADRS] Los 3 ADRs estan presentes con nombre correcto")',
                'ok("[ADRS] Los 4 ADRs estan presentes con nombre correcto")',
            ),
            (
                '    raiz_inf = RAIZ / "INFORME_BOT_MACRO2.1.md"\n'
                '    textos_inf = RAIZ / "textos" / "INFORME_BOT_MACRO2.1.md"\n'
                '    if raiz_inf.exists() and textos_inf.exists():\n'
                '        aviso("[DOCS] INFORME_BOT_MACRO2.1.md esta DUPLICADO (raiz y textos/)",\n'
                '              "Borra el de la raiz: python fixes\\\\aplicar_fixes.py")\n',
                '    raiz_inf = RAIZ / "INFORME_BOT_MACRO2.1.md"\n'
                '    textos_inf = RAIZ / "textos" / "INFORME_BOT_MACRO2.1.md"\n'
                '    docs_inf = RAIZ / "docs" / "INFORME_MACRO2.1.md"\n'
                '    if textos_inf.exists() and docs_inf.exists():\n'
                '        aviso("[DOCS] INFORME_BOT_MACRO2.1.md DUPLICADO (textos/ y docs/)",\n'
                '              "Borra el de textos/: python fixes\\\\ordenar_docs.py --deshacer")\n'
                '    if raiz_inf.exists() and (textos_inf.exists() or docs_inf.exists()):\n'
                '        aviso("[DOCS] INFORME_BOT_MACRO2.1.md esta DUPLICADO (raiz y otra carpeta)",\n'
                '              "Dejalo solo en docs/")\n',
            ),
        ]
        ok, detalle = _parchear(ver, pares, "verificar.py")
        print("   [%s] %s" % ("OK" if ok else "--", detalle))
        if ok:
            import py_compile
            try:
                py_compile.compile(str(ver), doraise=True)
                print("   [OK] verificar.py sigue compilando")
            except Exception as e:
                print("   [FALLA] verificar.py no compila: %s" % e)
                print("          Restaura con: copy fixes\\_bak_gobierno\\verificar.py verificar.py")
    print()

    # ---------- 4. RESUMEN ----------
    print("=" * 68)
    print(" 4. QUE SE ESCRIBIO")
    print("=" * 68)
    for rel, _ in documentos:
        print("   - %s" % rel)
    print("   - decisiones/002-unificar-umbral-ADF.md  (marcado APLICADO)")
    print("   - verificar.py  (chequea ADR 003)")
    print()
    print("   NO se toco:  docs/INFORME_MACRO2.1.md  (queda como spec de referencia)")
    print()
    print("=" * 68)
    print(" 5. SIGUIENTE PASO")
    print("=" * 68)
    print("   python verificar.py    -> debe seguir 19 ok / 0 fallas / 1 aviso")
    print("   y despues commit:")
    print('   python git\\guardar.py "docs: actualiza AGENTS/ESTADO/HANDOFF/PENDIENTES y agrega ADR 003"')
    print("   git push origin main")
    print()
    print("   Deshacer: python fixes\\actualizar_gobierno.py --deshacer")
    print("=" * 68)
    print()
    return 0


def deshacer():
    print()
    print("#" * 68)
    print("#  DESHACER: restaurar los documentos anteriores")
    print("#" * 68)
    print()
    if not BAK.exists():
        print("   [AVISO] No hay carpeta de backup: fixes/_bak_gobierno/")
        print()
        return 1
    for bak in sorted(BAK.iterdir()):
        destino = RAIZ / bak.name
        if bak.name == "002-unificar-umbral-ADF.md":
            destino = RAIZ / "decisiones" / bak.name
        if bak.name == "verificar.py":
            destino = RAIZ / "verificar.py"
        if bak.name == "PENDIENTES.md":
            destino = RAIZ / "docs" / "PENDIENTES.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(bak), str(destino))
        print("   [OK] Restaurado: %s" % destino.relative_to(RAIZ))
    # el ADR 003 no existed antes
    adr3 = RAIZ / "decisiones" / "003-macro21-local-sin-docker.md"
    if adr3.exists():
        adr3.unlink()
        print("   [OK] Borrado: decisiones/003-macro21-local-sin-docker.md (era nuevo)")
    print()
    print("   Las carpetas vacias que se crearon (docs/local/, etc.) quedan.")
    print()
    return 0


if __name__ == "__main__":
    if "--deshacer" in sys.argv:
        sys.exit(deshacer())
    sys.exit(aplicar())
