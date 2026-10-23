# ESTADO — MACRO2.1

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
| **H-7a** | **DB sin backup fuera del disco** | Se pierde 10 meses de evidencia y no se recupera de GitHub | 🔴 **PENDIENTE — resolver YA** |
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

**Hacé el backup externo de `data\vault_v2.1.db` y `.env`** (a Drive, disco
externo o donde sea). Es lo único del proyecto que **no** se recupera de
GitHub. 907 señales = 10 meses de evidencia.

---

## ➡️ SIGUIENTE PASO (uno solo)

**Arreglar `analisis\rescore_umbral.py` y medir el efecto real del ADR 002.**

- La v1 re-scoreó señales con `ms_v2 = 0` (placeholder) → dio falsos positivos
  (9 de los 10 "cambios" eran HYPE con `ms_v2 = 0.00`).
- La v2 tiene que: (a) **excluir** las señales con `macro_score_v2 == 0`,
  (b) quedarse solo con las **58** que tienen score real, (c) reportar
  auto-validación y cobertura.
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
