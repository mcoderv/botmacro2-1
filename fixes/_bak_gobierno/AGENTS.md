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
7. **Nunca borres** `docs/chats_ant/` (archivo histórico) ni commits ya publicados.
8. **Producción está congelada.** `botmacro` = MACRO2 = Render. No se toca
   hasta que algo se valide en 2.1. `botmacro2-1` = desarrollo.

---

## 5. MAPA DEL PROYECTO

### Pipeline (9 celdas, se ejecutan en orden, comparten estado global)
| Archivo | Qué hace |
|---|---|
| `C0_INICIO_local.py` | Setup: dirs, deps, test de escritura |
| `C1_CONFIG_local.py` | Rutas, DB, TZ, límites de portfolio |
| `C1_5_PARAM_local.py` | `CENTRAL_PARAMS` (**fuente de verdad**) + presets |
| `C2_BOVEDA_local.py` | SQLite: 18 tablas, backup, liveness, errores |
| `C2_5_CONTEXTO_local.py` | Liquidez: ATR, wicks, fractales, volume profile, OBI |
| `C3_DATA_QUALITY.py` | Calidad de datos: CLOSED/FORMING/STALE/DEGRADED |
| `C3_MACRO_local.py` | Cartógrafo v7.9.3: multi-TF, `ms_v2`, p_magnet, FFD |
| `C3_5_REGIME_ENGINE.py` | Régimen ADF: TREND_UP/DOWN/RANGE/CHAOS |
| `C4_SENIAL_VALIDATOR.py` | Registra señales, resuelve PnL 4/8/24h, métricas |

### Orquestación
| Archivo | Qué hace |
|---|---|
| `main.py` | Runner de celdas |
| `scheduler.py` / `scheduler.bat` | Scheduler (Render + local) |
| `ventana.py` | Ventana operativa 08:00-17:00 Caracas |
| `iniciar_macro21.bat` | Lanzador local |
| `reporter.py` / `report_validator.py` | Reportes HTML/JSON |

### Control
| Archivo | Qué hace |
|---|---|
| `verificar.py` | ⭐ Chequeos de salud del proyecto. Correlo siempre. |
| `validar_gem_macro.py`, `validar_ventana.py`, `diagnostico_bat.py` | Validadores existentes |
| `config/CONSOLIDADO/central_params.json` | ⭐ Config real en disco (la que se usa) |
| `data/vault_v2.1.db` | ⭐ La DB. 845+ señales. **No tocar, no versionar** |

---

## 6. TABLA DE UMBRALES (fuente única de verdad)

> Si tocás un valor acá, actualizá esta tabla también.

| Parámetro | Valor | Quién lo lee | Dónde se define |
|---|---|---|---|
| `ADF_P_VALUE_THRESHOLD` | **0.05** | C3_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |
| `TREND_SLOPE_THRESHOLD` | 0.0012 | C3_5 | `C3_5_REGIME_ENGINE.py` (hardcoded) |
| `STRONG_BIAS_THRESHOLD` | 2 | C3_MACRO | `CENTRAL_PARAMS["macro"]` |
| `BREAKEVEN_THRESHOLD_PCT` | 0.05 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `RESOLUTION_WINDOWS_HOURS` | 4, 8, 24 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `SCORE_V2_FUERTE` / `MODERADA` | 4.0 / 2.0 | C4 | `C4_SENIAL_VALIDATOR.py` (hardcoded) |
| `ALL_ASSETS` | 12 activos | C1_5, C3_MACRO | `CENTRAL_PARAMS["macro"]` |

**Regla de ADF:** el valor tiene que estar en `CENTRAL_PARAMS["macro"]`.
C3_5 lo tiene hardcodeado en 0.05 → ambos deben coincidir.
`python verificar.py` lo compara y te avisa si se desincronizan.

---

## 7. RITUAL GIT

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
- `origin-macro2` → `botmacro` = **PRODUCCIÓN (Render, congelado)**.

---

## 8. CONGELADO (no tocar sin ADR)

- `data/vault_v2.1.db` → las señales. **Activo principal del proyecto.**
- `.env` → claves de API.
- `C3_DATA_QUALITY.py` → validado, lo consumen 3 módulos.
- `decisiones/000-render-litestream-r2.md` → configuración de producción.
- Todo lo que esté en `botmacro` (producción) hasta que se valide en 2.1.

---

## Donde va cada cosa (docs/)

- `docs/INFORME_MACRO2.1.md` — la spec vigente del bot. Leer primero.
- `docs/PENDIENTES.md` — lista de trabajo abierta.
- `docs/info/` — specs de referencia y linaje de datos.
- `docs/investigaciones/` — investigaciones con fuentes (usar `PLANTILLA.md`).
- `docs/local/` — soporte personal (chats de IA, borradores). **NO versionado.**
- `docs/LEEME.md` — las reglas de esta carpeta.

**Regla**: si la proxima IA necesita leerlo, va versionado. Si es soporte
del usuario, va a `docs/local/` y no se sube a GitHub.
