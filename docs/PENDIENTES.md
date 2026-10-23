# PENDIENTES — MACRO2.1

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
- `data\vault_v2.1.db` (907 señales) y `.env`.
- Es lo único que **no** se recupera de GitHub.
- Copiar a Drive / disco externo. Verificar que abre bien.

### 7. `rescore_umbral.py` v2
- La v1 re-scoreó placeholders (`ms_v2 = 0`) → falsos positivos.
- La v2 tiene que excluir `macro_score_v2 == 0` y trabajar sobre las **58** señales reales.
- Ver `AGENTS.md` §5.1 y §5.2.

---

## ⚪ DESCARTADOS / EN MONITOREO

- **Eliminar los cripto del universo** → descartado. Se mantienen los 12.
- **Filtro v2 con pocas señales** → se resuelve con acumulación de datos. Ojo:
  solo 58 señales tienen `ms_v2` real, y 20 de ellas son FUERTE. Con 20 señales
  cualquier comparación de HR es ruido.
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
