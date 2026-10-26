# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~110 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-26
Commit      : 31e6cd3 (H-18/H-10/H-20 + ADR 007) + commit de gobierno H-22
Repo        : botmacro2-1  (desarrollo, local, SIN Docker) | botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h) · zona horaria = CARACAS (UTC-4)
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre de punta a punta (`python main.py`), 8 celdas, sin excepciones
- [x] `data/vault_v2.1.db` con **914 señales (902 resueltas a 24h)**
- [x] **I-1** — Caja simétrica (`am` 0.5-2.0, `caja_p` ±2)
- [x] **ADR 002** — umbral ADF unificado en 0.05, fuente única `CENTRAL_PARAMS["macro"]`
- [x] **ADR 004** — Max DD con capital compuesto (H-15) + fuente única del ADF (H-12)
- [x] **ADR 006** — ventana operativa configurable (H-17): VENTANA/CONTINUO, cruce de medianoche, días, CLI
- [x] **H-3 / H-5** — carpetas `backups_v2.1`/`logs_v2.1` y `_migrar_v28` sobrescribe
- [x] **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso (verifica ADR 000-006)
- [x] **Sin Docker en 2.1** (ADR 003) — producción intacta
- [x] **H-9 CERRADO** — diagnóstico completo del `macro_score_v2` (5 scripts de análisis)
- [x] **Zona horaria resuelta** — la DB guarda hora local Caracas (UTC−4), 3 pares epoch↔fecha
- [x] **Segunda opinión** recibida, revisada y sus 3 errores corregidos (E1/E2/E3)
- [x] **Plan de reorientación** escrito (Track A / B / C) — `docs/RELEVO_IA.md` §10

---

## 📊 MÉTRICAS (24h, 877 resueltas del 23/10)

| Corte | n | HR | PF | avg |
|---|---|---|---|---|
| **GLOBAL** | 877 | 44.7% | 0.80 | −0.156% |
| LONG | 429 | 32.4% | **0.50** | −0.488% |
| SHORT | 448 | 56.5% | **1.28** | +0,163% |
| xyz:SILVER | 58 | 63.8% | 3.22 | +0,768% |
| xyz:GOLD | 93 | 51.6% | 2.64 | +0,309% |
| BTC | 64 | 23.4% | **0.30** | −0,630% |
| xyz:SP500 | 88 | 39.8% | **0.28** | −0,351% |

**LONG pierde plata, SHORT gana.** Problema estructural, no de umbral.
El k×σ (ADR 001) **no lo arregla**: el PF no depende del break-even.
Asimetría confirmada por 3 métodos: MFE/MAE (LONG payoff **−2,9:1** · SHORT **1,75x**) ·
movimiento contrario primero (LONG **54,0%** vs SHORT 34,3%) · PF por tipo (0,50 vs 1,28).

---

## 🧭 H-9 CERRADO — QUÉ ES REALMENTE MACRO2.1

**El score v2 NO tiene poder predictivo demostrado (NO-GO).**
ρ(ms2, pnl24) = **+0,119** dentro de RANGE. No separa nada.

**Lo que sí se midió (todo verificado contra la DB cruda):**

| Hallazgo | Dato | Dónde |
|---|---|---|
| `macro_score_v2 = 0.0` exacto | **768 de 914** = 13/10–19/10 = **PRE-DEPLOY, NO es bug vigente** | `data_quality_emision`=OK en las 768 |
| Score v2 real | **146** = 19/10–23/10 (4 días) | |
| El filtro de régimen **NO corrió** | **648 de 914 (71%)** tienen `p=1.0` = el DEFAULT del `except` | C3 líneas 1901-1925 |
| `p<0,05` significa | **ESTACIONARIO**, no momentum | |
| `riesgo_regime` real | NEUTRAL 83,4% / RISK_ON 13,0% / RISK_OFF 3,6% | |
| `bias` real (audit) | RANGO 62,3% / BULL 18,7% / BEAR 18,7% | |
| El sesgo multi-TF **SÍ funciona** | N/A sólo 5,6% (1D) · 5,8% (4H) · **0% (15m)** | |
| El grano correcto | **CICLO**, no día: 25 ciclos / 146 señales | 3 ciclos del 20/10 con HR 0% · 3 del 21/10 con HR 85-89% |
| El filtro real de emisión | **`rvd` > 0,3** (umbral legacy 2 ⇒ `rs=±2` alcanza solo) | C3 líneas 1500-1510, 260 |
| El score v2 vs legacy | v2 sube caja/fvg y **baja el flujo** ⇒ es una **regresión** | |

**⇒ ⭐ MACRO2.1 HOY ES UN DETECTOR DE FLUJO CON CONFLUENCIA, no un detector de
tendencia macro. Y su sesgo (BULL/BEAR) es el MISMO número que el tipo de señal
(LONG/SHORT) ⇒ no son dos señales, son una.**

**⇒ El único dato de eficacia es INCONSISTENTE** (LONG+BULL: pre-deploy HR
35,6% PF 0,52 · post-deploy HR 73,7% PF 9,24) ⇒ se resuelve SOLO con n suficiente.

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Impacto | Estado |
|---|---|---|---|
| **H-7a** | Backup de la DB solo en un disco | Hecho local, **falta Drive** | ❗ **PRIORIDAD #1 (manual)** |
| **H-22** | **El test de régimen falla en el 71%** y deja `p=1.0` (indistinguible de un resultado) | La muestra de "señales con score" está **seleccionada por éxito del test** | 🔴 **NUEVO —>#1 técnico** |
| **H-9** | `macro_score_v2` sin poder predictivo demostrado | NO-GO cerrado | ✅ **CERRADO (evidencia)** |
| **H-10** | Las etiquetas no son comparables entre sí (19/10 = 1er deploy) | Confound temporal | ✅ RESUELTO |
| **H-20** | La ventana no se respeta al 100% (16,2% fuera) | Los cortes por hora no son exactos | ⬜ Nuevo |
| **H-21** | `en_ventana()` trabaja con **hora entera** | `VENTANA_FIN=16` corta el ciclo de las 16:00; no se puede expresar 03:40/16:20 | 🔴 **NUEVO — bloquea H-18/H-13** |
| **H-18** | `RESOLUTION_WINDOWS_HOURS=[4,8,24]` hardcoded | Sin cortes intermedios ⇒ no se mide timing temprano | ⬜ PROPUESTO (ADR 007) — default acordado **[4, 24]** |
| **H-13** | `senales_metricas` no agrega por `calidad_senal_v2`; escala legacy 14/8/4 muerta | Métricas por etiqueta salen de una escala inalcanzable | ❗ Pendiente |
| **H-14** | `_get_price_at_time` puede tomar precio posterior | 52% cambian de PnL, sesgo neto <1% | ❗ Pendiente |
| **H-16** | "ganancia" con 2 definiciones | Impacto <1% en PF | ⏸️ Medido y diferido (ADR 004) |
| **H-11** | `main.py` corre 8 celdas, no 9 | Cosmético, el mapa de AGENTS.md miente | ❗ Nuevo |
| **H-12** | C2 dice "Sin backups previos" ⇒ el auto-restore nunca restauró nada | Nunca probado de verdad | ❗ Nuevo |
| **H-4** | `BREAKEVEN_THRESHOLD_PCT=0.05` fijo (≡ k=0,044σ) | Sesga HR (no el PF) | ❗ Pendente → ADR 001 |
| **H-6** | `SCORE_ALTA=14`/`MEDIA=8` con `macro_score` máx 6 | Código muerto | ❗ Pendiente |
| **H-8** | 6 cripto pierden (BTC PF 0,30) mientras TradFi gana | Estructural | ❗ En investigación |
| **H-2** | Dos ADF distintos (niveles C3_5 vs residuales FFD C3) | El régimen no mueve el conmutador | ❗ Pendiente |
| **H-7b** | 5 imports con fallback silencioso | Una regresión se degrupa sin avisar | ❗ Pendiente |
| — | Rate limit de Hyperliquid | 1344 req/min > 1200 ⇒ **429**; ritmo 25-30 → **4-8 corridas/día** | 🔴 **Track A / A1** |
| — | Logs sobrescritos | 39 líneas ⇒ el motivo de los 648 fallos del ADF se perdió | 🔴 **Track A / A4** |
| — | `cycle_id` roto | join señales↔snapshot = **0/914** ⇒ auditoría rota | 🔴 **Track A / A2** |
| — | `data_quality` siempre NULL | El dict real es `zonas["data_quality"]["estado"]` | 🔴 **Track A / A3** |
| — | `duration_seconds` no es duración | No se puede medir el costo por ciclo | 🔴 **Track A / A5** |
| — | `_classify_signal_quality_v2` usa `abs()` | Etiqueta invertida (RUIDO 71,4% > FUERTE 64,7%) | ⬜ **Track B / B3** |
| — | `score_desglose["cvd_crud"]` mal nombrado | Ya produjo un error de análisis externo | ⬜ **Track A / A9** |

---

## 🔒 ANTES DE CUALQUIER COSA

**Subí `C:\Users\MD\Desktop\MACRO2.1_BACKUP\` a Drive.** El backup local ya
está hecho (23/10): `vault_v2.1.db` + `env_respaldo.txt`. Es lo único del
proyecto que **no** se recupera de GitHub. **`data/` está gitignored.**

---

## 🎯 SIGUIENTE PASO (Track A, en este orden)

1. **A1 — Rate limit.** 1344 req/min > 1200 ⇒ 429 ⇒ 4-8 corridas/día.
   Cache de velas (TTL > 15 min) + WS + backoff + reducir TFs.
   **Objetivo: 0 × 429 y ≥ 60 corridas/día.**
2. **A2 — `cycle_id`.** C3.5 debe escribir `zonas["macro_cycle_id"]`.
   **Objetivo: 100% de match.**
3. **A3 — `data_quality`.** `zonas["data_quality"]["estado"]` ⇒ no NULL.
4. **A0 — Test de régimen.** `p=NULL` + `regimen_test_ok` en vez de `p=1.0`.
   Recalibrar la longitud de ventana del ADF (n ≈ 42 es insuficiente).
5. **A4 / A5 / A6** — logs acumulativos · `duration_seconds` real ·
   red de seguridad del score (`logger.warning` + contador).
6. **A9** — renombrar `score_desglose["cvd_crud"]` → `rs_ordinal`.
7. **A7 — Ventana** (ADR 011): 19 h (04:00-23:00) = 570-589 h/mes = 76-78% del
   free tier, y captura la franja de las 20:00 (HR 76%, n=25).
8. **H-21** (ventana en minutos) → **H-18** (`[4,24]`) → **H-13**.

**⇒ Track C (protocolo OOS) se escribe ANTES de T₀** (ADR 012).
**⇒ T₀ = fecha del deploy con el Track A listo.**
**⇒ Track B (B1/B3) se aplica SOLO en T₀, prospectivo. B4 (limpiar el score)
solo DESPUÉS del veredicto.**

---

## 🏠 REGLAS DE LA CASA

- Producción (`botmacro`) está **congelada**. Todo se valida acá primero.
- Si algo funciona, no se toca sin ADR.
- Después de cada cambio: `python verificar.py`, y si falla, no se avanza.
- Un cambio por sesión. Un commit por cambio. `git/guardar.py` para commitear.
- Los chats no se archivan a mano: cada sesión cierra con `HANDOFF.md`.
- **1 a 4 comandos por turno.** Si uno depende del anterior, de a uno.
- **No mezcles tareas:** cerrar el trabajo en curso antes de abrir el siguiente.
- **Nunca escribir archivos sin "ok" explícito del usuario.**