# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~60 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-23
Commit      : 1f2c5bb (checkpoint I-1/I-2)
Repo        : botmacro2-1  (desarrollo)  |  botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre
- [x] `data/vault_v2.1.db` con las señales acumuladas (conteo vivo: `python verificar.py`)
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2) → LONG HR 23.3% → 32.9%
- [x] **I-2** — Motor de régimen ADF real → 97% RANGE → ~70% RANGE / ~30% TREND
- [x] Repos separados: `botmacro2-1` (dev) y `botmacro` (prod congelada)
- [x] `.env` nunca commiteado
- [x] `AGENTS.md` / `ESTADO.md` / `HANDOFF.md` / `decisiones/` / `verificar.py` en la repo

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-1** | Umbral ADF 0.02 en C3_MACRO vs 0.05 en C3_5 | El régimen y el `ms_v2` se contradicen. Las métricas medidas están contaminadas | **PENDIENTE** → `decisiones/002` |
| **H-2** | Dos ADF distintos (niveles en C3_5 vs residuales FFD en C3_MACRO), umbrales distintos, no se cruzan | El conmutador de `ms_v2` no lo mueve el motor de régimen | Pendiente de decisión |
| **H-3** | `C0` escribe en `backups/`, `C2` lee de `backups_v2.1/` | El auto-restore nunca encuentra los backups | **PENDIENTE** (1 línea) |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo | Sesga HR (no el PF). Trivial en BTC, excesivo en EUR | Pendiente → ADR 001 |
| **H-5** | `_migrar_v28` usa `if k not in val_sec` | Cambiar el default en el código NO sobrescribe el `central_params.json` ya guardado | **PENDIENTE** (parte de ADR 002) |
| **H-6** | `SCORE_ALTA=14` / `SCORE_MEDIA=8` con `macro_score` máximo 6 | Son código muerto. Todo cae en BAJA o RUIDO | Pendiente → `calidad_senal_v3` |
| **H-7** | Sin tests. DB sin backup automático fuera del disco | Una regresión silenciosa tarda días en notarse | **PENDIENTE** → `verificar.py` (parcial) |
| **H-8** | 6 cripto pierden (BTC PF 0.12) mientras TradFi gana (PF 1.25) | Estructural, no de umbral | En investigación |

---

## 📋 PENDIENTES (del informe técnico)

**Código**
1. Etiquetas de calidad → `calidad_senal_v3` con umbrales calibrados sobre la distribucion real
2. Umbral dinámico k×σ (ADR 001) → en columna nueva, con baseline recalculado
3. `scheduler.py` → `PORT = int(os.environ.get("PORT") or 8080)`
4. `report_validator.py` → corregir el Max DD (calcula sobre la curva de capital, no sumando segmentos)
5. `ventana.py` / `scheduler.py` → ventana 04:00-16:00 + validación escalonada 4→8→12→16

**Docs/config**
6. `decisiones/000-render-litestream-r2.md` → bucket `macrobot-vault` → `mercabot-qwen-db`
7. `CENTRAL_PARAMS` → `ADF_P_VALUE_THRESHOLD` a la sección `macro`, valor 0.05, y `_migrar_v28` que sobrescriba

**Descartado / en monitoreo**
- Eliminar cryptos del universo → **descartado** (se mantienen los 12)
- Filtro v2 con 22 señales → se resuelve con acumulación de datos
- MACRO2 (producción) → **DATA FREEZE**, no se toca

---

## ➡️ SIGUIENTE PASO (uno solo)

**1. Aplicar ADR 002** — unificar el umbral de ADF:
   - mover `ADF_P_VALUE_THRESHOLD: 0.05` a `CENTRAL_PARAMS["macro"]`
   - quitarlo de la sección `validation`
   - hacer que `_migrar_v28` **sobrescriba** (no `setdefault`) el valor guardado
   - renombrar `decisiones/002-Unificar el umbral ADF` → `002-unificar-umbral-ADF.md`
   - **verificar con:** `python verificar.py` → el check `[H-1]` tiene que dar OK

   Después: re-medir HR/PF con el umbral unificado, porque las cifras actuales
   están contaminadas por la incoherencia.

---

## 📌 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
