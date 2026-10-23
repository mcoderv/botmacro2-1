# AGENTS.md — MACRO2.1 (local, experimental)

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

Medición real (2026-10-23, 877 señales resueltas a 24h):

| Grupo | n | ms_v2 |
|---|---|---|
| Con score v2 real | **58** (6.6%) | != 0 |
| Sin score v2 (histórico) | **819** (93.4%) | = 0 |

⚠️ **El 93% en cero es antigüedad, NO un fallback roto.** Es normal y es
esperado. No lo trates como bug.

**Consecuencia para medir cosas:** cualquier análisis del v2 tiene que correr
sobre las 58 señales con score real, NO sobre las 877. Con 58 los cortes por
etiqueta son de 20-40 señales → **interpretá esos números como ruido
estadístico, no como resultado.**

### 5.2 El re-score de umbral ADF v1 dio FALSOS POSITIVOS

`analisis/rescore_umbral.py` (v1) re-scoreó **también** las señales con
`ms_v2 = 0`, inventándoles un score. De sus "10 señales que cambian de rama",
9 son HYPE con `ms_v2 = 0.00` → **falsas**.

Antes de usar ese script: tiene que **excluir** las señales con
`macro_score_v2 == 0` y quedarse solo con las 58 reconstruibles.

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
- **La DB no tiene backup fuera del disco.** Es el único recurso del proyecto
  que no se recupera de GitHub. **Prioridad de backup: alta.**

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
