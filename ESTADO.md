# ESTADO — MACRO2.1

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
- [x] **Backup local de la DB** en `Desktop\MACRO2.1_BACKUP\` (falta subirlo a Drive)

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
| **H-7a** | Backup de la DB solo en un disco | Hecho local (`Desktop\MACRO2.1_BACKUP\`), falta Drive | 🟡 **Falta subirlo a Drive** |
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

**Subí `C:\Users\MD\Desktop\MACRO2.1_BACKUP\` a Drive.** El backup
local ya está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`.
Es lo único del proyecto que **no** se recupera de GitHub.

---

## ➡️ SIGUIENTE PASO (uno solo)

**Cerrar H-9 y H-10: entender por qué el `bias` 1D/4H/1H sale `N/A` y qué pasó
el 19/10.**

Dos comandos que ya están pendientes:
```
findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\*.log
```
→ dice si el `N/A` es por pocas velas (Hyperliquid no devolvió 20) o por error.

**Pregunta para el usuario:** ¿qué cambió el 2026-10-19 en el pipeline? Candidatas:
(1) desplegaste v7.9.3, (2) cambiaste la ventana operativa o reiniciaste el
scheduler (→ el "Ojo B" del pendiente #4), (3) tocaste C3_MACRO / C3_DATA_QUALITY.

**Después**: métricas por etiqueta **dentro de cada día** (elimina el confound de
H-10) y, con el diagnóstico cerrado, un ADR para la rama del `ms_v2`.

**Herramienta:** `python analisis\rescore_umbral_v2.py` (ya tiene el corte
por día y el corte por subgrupo).

---

## 📌 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- Un cambio por sesión. Y un commit por cambio.
