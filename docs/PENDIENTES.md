# PENDIENTES — MACRO2.1

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
| 13 | **Backup local de la DB** en `Desktop\MACRO2.1_BACKUP\` | 2026-10-23 |

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
  → `findstr /i /c:"no_data_or_too_few" /c:"INSUFFICIENT" /c:"no disponible" logs_v2.1\*.log`
- **Posibles fixes (todas necesitan ADR):** (A) guardar ambas ramas en columnas
  separadas; (B) decidir la rama por detección de breakout en vez del ADF; (C)
  piso al `rs` en la rama estacionario.
- **Ojo:** `AGENTS.md` §5.1.c

### 2. El score v2 no se puede evaluar todavía (H-10)
- **Problema:** la distribución de etiquetas cambió por completo el 19/10
  (0 FUERTE → 1 → 9 → 10). Comparar HR/PF entre etiquetas = comparar días distintos.
- **Pendiente:** (a) saber qué cambió el 19/10; (b) medir por día antes de comparar.
- **Herramienta:** `python analisis\rescore_umbral_v2.py` (ya corta por día y por subgrupo).

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
- `data\vault_v2.1.db` (914 señales) y `.env`.
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
2. **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en `logs_v2.1\*.log`)
3. ¿Los 4 archivos "Nivel C" se borran o se quedan?
4. ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
5. ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
6. ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
7. ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
