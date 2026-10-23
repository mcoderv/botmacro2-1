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

`ms_v2` (el score multi-timeframe) se agregó en **v7.9.3**. Las señales
anteriores a esa versión tienen `macro_score_v2 = 0.0` en la DB.

Medición real (2026-10-23, 877 señales resueltas a 24h). La clave es si el
`ms_v2` guardado **se explica con los componentes** (`poc + caja + fvg + rs`
+ un `s_mtf` implícito dentro de [-0.65, +0.65]):

| Grupo | n | Qué significa |
|---|---|---|
| `ms_v2 >= 2` (FUERTE 20 + MODERADA 38) | **58** | Score v2 real y coherente |
| `ms_v2 < 2` pero coherente | **70** | Coherente (score bajo, o 0 legítimo) |
| `ms_v2` **incoherente** con los componentes | **749** (85%) | ❌ **No fue computado** |

⚠️ **El 85% del histórico no tiene score v2 reconstruible.** No es un fallback
roto: es antigüedad (v7.9.3 es reciente). No lo trates como bug.

**Consecuencia para medir cosas:** el conjunto de trabajo es de **128 señales
reconstruibles** (58 + 70), NO 877. Con 128 los cortes por etiqueta quedan en
20-40 señales → **leelo como ruido estadístico, no como resultado.**

### 5.2 El re-score de umbral ADF v1 dio FALSOS POSITIVOS

`analisis/rescore_umbral.py` (v1) re-scoreó **todas** las señales, incluidas
las 749 sin score v2 computado. De sus "10 señales que cambian de rama", 9
eran HYPE con `ms_v2 = 0.00` → **falsas**.

La **v2** (mismo archivo, reescrito) corrige esto: clasifica cada señal en
reconstruible / no reconstruible, re-scorea **solo** las reconstruibles,
aborta si la auto-validación 1 no da ≥90%, y reporta el corte temporal
(¿hay señales posteriores a la existencia del v2 sin score? eso sí sería un bug).

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
| `fixes/` | ⭐ `actualizar_gobierno.py` — reescribe AGENTS/ESTADO/HANDOFF/PENDIENTES + ADRs. **Correlo al cierre de cada sesión.** |
| `analisis/` | Herramientas de análisis vivas: post-mortem, MAE/MFE, `rescore_umbral_v2.py` |
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

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~70 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-23
Commit      : 5e0c481 (Docker fuera + docs reordenadas)
Repo        : botmacro2-1  (desarrollo, local, SIN Docker)  |  botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre
- [x] `data/vault_v2.1.db` con **907 señales (877 resueltas a 24h)**
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2)
- [x] **I-2** — Motor de régimen ADF real
- [x] **ADR 002 aplicado** — umbral ADF unificado en 0.05, fuente única `CENTRAL_PARAMS["macro"]`
- [x] **H-3 arreglado** — C0 y C2 usan `backups_v2.1` / `logs_v2.1`
- [x] **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py` (no dependo de saber git)
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso. Correlo SIEMPRE después de cada cambio.
- [x] **Repos separados** — `botmacro2-1` (dev) y `botmacro` (prod congelada)
- [x] **Sin Docker en 2.1** (ADR 003) — el clon local corre con `python` directo
- [x] **`.env` nunca commiteado**
- [x] **`docs/` ordenada** — `docs/local/` fuera de GitHub, `docs/LEEME.md` con las reglas

---

## 📊 MÉTRICAS REALES (24h, 877 señales)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| **GLOBAL** | 877 | 44.7% | 0.80 | −0.156% |
| LONG | 429 | 32.4% | **0.50** | −0.488% |
| SHORT | 448 | 56.5% | **1.28** | +0.163% |
| xyz:SILVER | 58 | 63.8% | 3.22 | +0.768% |
| xyz:GOLD | 93 | 51.6% | 2.64 | +0.309% |
| BTC | 64 | 23.4% | **0.30** | −0.630% |
| xyz:SP500 | 88 | 39.8% | **0.28** | −0.351% |

**LONG pierde plata, SHORT gana.** El problema es estructural, no de umbral.
No lo arregla el k×σ (el PF no depende del break-even).

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | **Backup de la DB solo en un disco** | Hecho local (`Desktop\\MACRO2.1_BACKUP\\`), falta Drive | 🟡 **Falta subirlo a Drive** |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | 🟡 Pendiente → matar fallbacks |
| **H-2** | Dos ADF distintos (niveles en C3_5 vs residuales FFD en C3_MACRO) | El régimen no mueve el conmutador de `ms_v2` | 🟡 Pendiente de decisión |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo | Sesga HR (no el PF). Trivial en BTC, excesivo en EUR | 🟡 Pendiente → ADR 001 |
| **H-6** | `SCORE_ALTA=14` / `SCORE_MEDIA=8` con `macro_score` máximo 6 | Código muerto. Todo cae en BAJA o RUIDO | 🟡 Pendiente → `calidad_senal_v3` |
| **H-8** | 6 cripto pierden (BTC PF 0.30) mientras TradFi gana | Estructural, no de umbral | 🟡 En investigación |
| **H-5** | `_migrar_v28` no sobrescribía el JSON guardado | El default del código no se aplicaba | ✅ **RESUELTO** (ADR 002) |
| **H-1** | Umbral ADF 0.02 en C3_MACRO vs 0.05 en C3_5 | El régimen y el `ms_v2` se contradecían | ✅ **RESUELTO** (ADR 002) |
| **H-3** | `C0` escribía en `backups/`, `C2` leía de `backups_v2.1/` | El auto-restore no encontraba nada | ✅ **RESUELTO** |

---

## ⏰ ANTES DE CUALQUIER COSA

**Subí `C:\\Users\\MD\\Desktop\\MACRO2.1_BACKUP\\` a Drive.** El backup local ya
está hecho (23/10): `vault_v2.1.db` (907 señales) + `env_respaldo.txt`.
Es lo único del proyecto que **no** se recupera de GitHub.

---

## ➡️ SIGUIENTE PASO (uno solo)

**Arreglar `analisis\\rescore_umbral.py` y medir el efecto real del ADR 002.**

- La v1 re-scoreó señales con `ms_v2 = 0` (placeholder) → dio falsos positivos
  (9 de los 10 "cambios" eran HYPE con `ms_v2 = 0.00`).
- La v2 tiene que: (a) clasificar cada señal en **reconstruible / no
  reconstruible** (auto-validación 2), (b) re-scorear **solo** las
  reconstruibles (**128 de 877**), (c) abortar si la auto-validación 1 no da
  ≥90%, (d) reportar el corte temporal (señales post-v2 sin score = bug real).
- **Con 58 señales los cortes por etiqueta son de 20-40 → ruido estadístico.**
  El objetivo NO es "demostrar que el umbral 0.05 mejora el HR" (no lo va a
  hacer: el HR y el PF no cambian con el umbral). El objetivo es **cuantificar
  cuántas señales cambian de rama** y dejarlo documentado.

Después de eso, el backlog de código está en `docs/PENDIENTES.md`.

---

## 📌 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- **Un cambio por sesión.** Y un commit por cambio.
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
Fecha    : 2026-10-23
Sesion   : 2
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : 5e0c481
```

---

## 1. Qué hice en esta sesión

- **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`.
  Ahora no dependo de saber git.
- **ADR 002 aplicado** (commit `5361b4f`): umbral ADF unificado en **0.05**,
  fuente única `CENTRAL_PARAMS["macro"]`. Se corrigió también **H-3**
  (`backups_v2.1` / `logs_v2.1`) y **H-5** (`_migrar_v28` ahora sobrescribe).
- **`verificar.py`** — 19 ok / 0 fallas / 1 aviso. Es el contrato ejecutable
  del proyecto: lo que él chequea, no se rompe en silencio.
- **Re-score del umbral ADF** (`analisis/rescore_umbral.py`) — primera medición
  real del efecto de ADR 002. **Dio falsos positivos** (ver §3.1).
- **Docker eliminado de MACRO2.1** (ADR 003, commit `5e0c481`): `Dockerfile`,
  `docker-compose.yml`, `.dockerignore`, `start.sh`, `litestream.yml`.
  **Producción (`botmacro`) intacta.**
- **`docs/` reordenada** — una sola carpeta con reglas claras:
  `docs/INFORME_MACRO2.1.md` (spec), `docs/PENDIENTES.md` (tracking),
  `docs/info/`, `docs/investigaciones/` (+`PLANTILLA.md`), `docs/local/`
  (fuera de GitHub). `textos/` desapareció.

---

## 2. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Arreglar `rescore_umbral.py` v1 | Re-scoreó placeholders (ms_v2=0) → falsos positivos. La v2 es el siguiente paso. |
| `calidad_senal_v3` (etiquetas) | Necesita la distribución real de `macro_score`. Con 58 señales de v2, hay que ver si alcanza. |
| ADR 001 (k×σ) | Es un cambio de un solo archivo (`C4`), pero **el PF no se va a mover**. Decidir si vale. |
| Max DD de `report_validator.py` | No tengo el archivo para auditarlo. Pedirlo. |
| Ventana 04:00-16:00 | Cambia el régimen de muestreo → los datos nuevos no son comparables con los viejos. Decisión de negocio. |
| Backup externo de la DB | Es una acción manual tuya (copiar a Drive/disco). **Es la prioridad #1.** |
| Borrar los 4 archivos "Nivel C" | `evaluar_nube.py`, `test_telegram.py`, `verificar_progreso.bat`, `diagnostico_bat.py` — siguen sin respuesta. No son dañinos. |
| Tocar producción (`botmacro`) | DATA FREEZE. |

---

## 3. Qué creo que está frágil (opinión sin filtros)

1. **El 85% de las señales NO tiene score v2 reconstruible — y NO es un bug.**
   `ms_v2` se agregó en v7.9.3 (reciente); lo anterior quedó en 0. De 877
   señales: **58** con `ms_v2 >= 2`, **70** con score bajo pero coherente,
   **749 incoherentes** (no computadas). El grupo de trabajo real es de
   **128 señales**. Cualquier estadística del v2 sobre 877 es basura.

2. **El re-score v1 dio falsos positivos.** Re-scoreó las señales con
   `ms_v2 = 0` como si tuvieran un score. De sus "10 que cambian de rama", 9
   eran HYPE con `ms_v2 = 0.00` → inventadas. La auto-validación 2 (coherencia
   de `s_mtf`) saltó: solo 128/877 (14.6%) cuadraban. **Ese script no se usa
   hasta que excluya los placeholders.**

3. **5 imports con fallback silencioso.** Es el riesgo #1 del proyecto. Si
   cambiás la firma de una función, el pipeline **se degrupa en silencio** y
   no falla. Ya lo dice el aviso de `verificar.py`, pero nadie lo arregló.

4. **El PF no depende del umbral de break-even.** `C4` usa el 0.05% solo para
   el HR; el PF usa `p > 0` / `p < 0`. Si la expectativa con ADR 001 es "ver el
   PF subir al destrabar el umbral", **eso no va a pasar**. El ADR 001 solo
   mueve el HR.

5. **LONG pierde, SHORT gana** (PF 0.50 vs 1.28). Y dentro de los cripto,
   BTC PF 0.30 y SP500 PF 0.28. Eso no lo arregla ningún umbral: es
   microestructura o la lógica de entrada. `xyz:SILVER` (PF 3.22) y
   `xyz:GOLD` (2.64) sí funcionan. **Copiar el patrón de los que ganan
   probablemente vale más que recalibrar umbrales.**

6. **Cero tests.** `verificar.py` es el primer paso, no el final. Un `assert`
   de una línea sobre el umbral ADF habría cazado H-1 hace semanas.

7. **La DB no tiene backup fuera del disco.** Es lo único no recuperable de
   GitHub. 10 meses de evidencia en un solo archivo.

---

## 4. Qué chequear primero en la próxima sesión

1. `python verificar.py` → tiene que dar 19 ok / 0 fallas.
2. `python git\\estado.py` → leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `docs/PENDIENTES.md` → la lista de trabajo.
4. Si tocás el v2: leer `AGENTS.md` §5.1 y §5.2 **antes** de medir nada.

---

## 5. Cómo verificar que no rompí nada

```cmd
python verificar.py
python git\\revisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 6. Cosas pendientes de confirmación (preguntas abiertas)

- **¿La DB de producción (Turso) usa las mismas 22 tablas que la local?**
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
  (39 KB cada uno de `scheduler.py` y `report_validator.py` lo sugiere)
- ¿Los 4 archivos "Nivel C" (`evaluar_nube.py`, `test_telegram.py`,
  `verificar_progreso.bat`, `diagnostico_bat.py`) se borran o se quedan?
- **¿La `GUIA DE USO.txt` sigue al día?** Ahora está versionada en `docs/`.
- **¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?**
"""


# ═════════════════════════════════════════════════════════════════════════════
# docs/PENDIENTES.md
# ═════════════════════════════════════════════════════════════════════════════
PENDIENTES_MD = """# PENDIENTES — MACRO2.1

> **Este archivo es el tracking oficial.** Si algo está pendiente, va acá.
> `docs/INFORME_MACRO2.1.md` es la **spec de referencia** (no se edita);
> este archivo es el que dice **qué falta y qué se hizo**.
>
> Actualizado: 2026-10-23

---

## ✅ HECHOS (cerrados)

| # | Qué | Dónde |
|---|---|---|
| 1 | Umbral ADF unificado en **0.05**, fuente única `CENTRAL_PARAMS["macro"]` | ADR 002, commit `5361b4f` |
| 2 | `C0`/`C2` usan `backups_v2.1` / `logs_v2.1` (auto-restore operativo) | H-3, commit `5361b4f` |
| 3 | `_migrar_v28` **sobrescribe** el `central_params.json` guardado | H-5, commit `5361b4f` |
| 4 | **`scheduler.py` ya lee `PORT`** del entorno (fallback `HEALTH_PORT`/8080) | Ya estaba, commit `5e0c481` lo confirmó |
| 5 | Bucket R2 = `mercabot-qwen-db` (no `macrobot-vault`) | Ya estaba |
| 6 | Sin Docker en MACRO2.1 | ADR 003, commit `5e0c481` |
| 7 | `docs/` reordenada, `textos/` eliminada, `docs/local/` fuera de GitHub | commit `5e0c481` |

---

## 🔴 CÓDIGO (pendientes del informe técnico)

### 1. Etiquetas de calidad → `calidad_senal_v3`
- **Problema:** umbrales legacy (14/8/4) incompatibles con `macro_score` (máx real 6). Todo cae en RUIDO/BAJA.
- **Corrección:** recalibrar a ALTA (≥4) / MEDIA (≥3) / BAJA (≥2), o usar el score crudo.
- **Ojo:** con solo 58 señales que tienen `ms_v2` real, los cortes por etiqueta
  quedan en 20-40 señales. **Riesgo alto de sobreajuste.** Considerar
  `calidad_senal_v3` como **columna nueva**, sin mutar la legacy.

### 2. Umbral dinámico k×σ → ADR 001
- **Problema:** `BREAKEVEN_THRESHOLD_PCT = 0.05` fijo. Trivial para BTC, excesivo para `xyz:EUR`.
- **Corrección:** `umbral = k * σ` (σ de los retornos del activo), en **columna nueva**, con baseline recalculado.
- **Realidad:** mueve el **HR**, **no el PF** (`C4` calcula el PF con `p > 0` / `p < 0`).
- **Decisión pendiente:** ¿se implementa o se pospone? (El informe decía "si es complejo, se puede dejar".)

### 3. `report_validator.py` → Max DD
- **Problema:** reporta Max DD de 270.88% (imposible en un solo segmento) → está sumando drawdowns de segmentos/activos.
- **Corrección:** calcularlo sobre la **curva de capital acumulada** (pico a valle), no sumando segmentos.
- **Bloqueante:** hace falta el archivo para auditarlo.

### 4. `ventana.py` / `scheduler.py` → ventana 04:00-16:00
- **Problema:** la ventana 08:00-17:00 deja los targets de 8h fuera de horario → 84.2% de contaminación.
- **Corrección:** ampliar a **04:00-16:00** (Caracas) + validación escalonada 4→8→12→16.
- **Ojo A:** `C4_SENIAL_VALIDATOR.py` tiene `RESOLUTION_WINDOWS_HOURS = [4, 8, 24]` hardcodeado. La escalonada 4→8→12→16 **contradice** eso. Hay que elegir.
- **Ojo B:** cambiar la ventana cambia el régimen de muestreo → **los datos nuevos no son comparables con los viejos**.

### 5. Matar los 5 fallbacks silenciosos de import
- `C2_5_CONTEXTO_local.py:78`, `C3_MACRO_local.py:42`, `:51`, `:126`, `C3_5_REGIME_ENGINE.py:60`
- Deben fallar fuerte, o tener un flag explícito. Es el riesgo #1 del proyecto.

---

## 🟡 INFRAESTRUCTURA

### 6. Backup externo de la DB  ← **PRIORIDAD #1**
- `data\\vault_v2.1.db` (907 señales) y `.env`.
- Es lo único que **no** se recupera de GitHub.
- Copiar a Drive / disco externo. Verificar que abre bien.

### 7. `rescore_umbral.py` v2
- La v1 re-scoreó placeholders (`ms_v2 = 0`) → falsos positivos.
- La v2 tiene que clasificar cada señal en **reconstruible / no reconstruible**
  (auto-validación 2) y re-scorear **solo las 128 reconstruibles** de 877.
- Debe abortar si la auto-validación 1 no da ≥90%, y reportar el corte temporal
  (¿hay señales posteriores a la existencia del v2 sin score? eso sí sería un bug).
- Ver `AGENTS.md` §5.1 y §5.2.

---

## ⚪ DESCARTADOS / EN MONITOREO

- **Eliminar los cripto del universo** → descartado. Se mantienen los 12.
- **Filtro v2 con pocas señales** → se resuelve con acumulación de datos. Ojo:
  solo 128 señales son reconstruibles (58 con `ms_v2 >= 2`, de las cuales 20 son
  FUERTE). Con 20 señales cualquier comparación de HR es ruido.
- **MACRO2 (producción en Render)** → **DATA FREEZE**. Ninguna corrección de
  esta lista se toca ahí hasta que se valide en MACRO2.1.

---

## ❓ PREGUNTAS ABIERTAS (sin respuesta del usuario)

1. ¿Los 4 archivos "Nivel C" se borran o se quedan?
   (`evaluar_nube.py` 15 KB, `test_telegram.py` 22 KB,
   `verificar_progreso.bat` 2.5 KB, `diagnostico_bat.py` 6.6 KB)
2. ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
3. ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
4. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
5. ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
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
