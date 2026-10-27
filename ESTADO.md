# ESTADO — MACRO2.1

> **Este archivo se REESCRIBE, no se acumula.** Si tiene más de ~120 líneas, está mal.
> Debe responder "¿dónde estoy?" en 20 segundos.
> Un ESTADO desactualizado es PEOR que ninguno: miente.

```
Actualizado : 2026-10-27  (sesion 7, 12:45)
Commit      : 8cfec15 (H-25) · gate 19 ok / 0 fallas / 1 aviso
Repo        : botmacro2-1  (desarrollo, local, SIN Docker) | botmacro = PRODUCCION (congelada)
FASE        : 2 — intervenciones
DB          : 914 señales (902 resueltas a 24h) · regime_state 2.496 filas (24 con la rama)
VENTANA     : 04:00-16:00 Caracas, ciclo cada 15 min  (config + log del 27/10 12:38)
SCHEDULER   : corriendo desde 12:38 — el lanzador ya arranca (H-25 cerrado)
```

---

## ✅ FUNCIONA (verificado)

- [x] Pipeline completo C0 → C4 corre de punta a punta (`python main.py`)
- [x] `data/vault_v2.1.db` con **914 señales (902 resueltas a 24h)**
- [x] **H-24 CERRADO** — el motor de régimen **guarda** lo que calcula (antes fallaba
      en silencio y se perdieron ~144 filas entre el 20/10 y el 27/10)
- [x] **H-25 CERRADO** — los dos `.bat` corren: era un `|` sin escapar (CMD lo toma
      como cañería) más finales de línea Unix. Probado: ciclo #1 completo en 55 s
- [x] **ADR 016 escrito** — define qué es "tendencia" (falta implementarlo)
- [x] **ADR 002** — umbral ADF unificado en 0.05 (fuente única)
- [x] **I-1** caja simétrica · **ADR 004** Max DD · **ADR 006** ventana configurable
- [x] **Kit de git** — `guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`
- [x] **`verificar.py`** — 19 ok / 0 fallas / 1 aviso (valida 13 ADRs con lista fija: B6)
- [x] **Sin Docker en 2.1** (ADR 003) · **zona horaria** = hora local Caracas (UTC−4)
- [x] **H-9 / H-10** cerrados con evidencia (score v2 sin poder predictivo; etiquetas comparables)

---

## 📊 LO QUE MIDE HOY EL RÉGIMEN (27/10, n = 24 filas = 2 ciclos × 12 activos)

| Dato | Valor |
|---|---|
| RANGE | **24 / 24 (100%)** |
| RAMA A (estacionaria, p ≤ 0,05) | **0 (0%)** |
| RAMA B (deriva baja) | **24 (100%)** |
| p-valores | 0,0819 – 0,8964 (ninguno ≤ 0,05) |
| pendiente máxima | 1,822 %/día vs umbral 2,88 %/día = **63,2%** |

**⇒ El ADF nunca decide; decide el umbral fijo de 0,0012.** Y ese umbral, medido,
falla distinto según el activo: **0% de falsos positivos en un activo calmo y 43%
en uno volátil** (la volatilidad entre los 12 activos varía **13,5×**).
El test sobre el **precio** da 88% de falsos positivos (inválido); el de
**retornos**, 3%.

**⇒ Hoy ningún activo está en tendencia de verdad** (deriva ÷ σ ≤ 0,27). El
"100% RANGE" actual es correcto; el bug es que la regla **no podría** decir TREND
aunque hubiera una tendencia moderada.

---

## 📊 ASIMETRÍA LONG / SHORT (24h, n=877 del 23/10)

| Corte | n | HR | PF |
|---|---|---|---|
| GLOBAL | 877 | 44,7% | 0,80 |
| LONG | 429 | 32,4% | **0,50** |
| SHORT | 448 | 56,5% | **1,28** |

**LONG pierde plata, SHORT gana.** Confirmado por 3 métodos (MFE/MAE, movimiento
contrario primero, PF por tipo). El k×σ (ADR 001) **no lo arregla**.

---

## 🔴 LOS 3 PROBLEMAS QUE MANDAN HOY

| # | Qué | Consecuencia |
|---|---|---|
| **B1** | La regla de tendencia es un umbral fijo inalcanzable | 100% RANGE ⇒ no hay etiqueta de tendencia que validar. **El ADR 016 ya decidió el reemplazo; falta implementarlo** |
| **B2** | El resolvedor no tiene tolerancia de distancia | **33%** de las validaciones a 4 h usan un precio a más de 2 h; **72 (7,9%)** son el precio de emisión ⇒ un tercio de las métricas a 4 h es dudoso |
| **H-20** | **16,2% de las señales se emiten fuera de la ventana** (19–21 h) | Es **la franja con el HR más alto medido** (20:00 → 76%) ⇒ **el "edge" puede ser un artefacto de este bug** |

---

## ⚠️ RIESGOS CONOCIDOS

| # | Riesgo | Estado |
|---|---|---|
| **H-7a** | Backup de la DB sólo en un disco (**falta subirlo a Drive**) | ❗ prioridad manual #1 |
| **E2 / H-12** | 5 scripts leen `data/vault_v2.db`, que no existe ⇒ reportes vacíos y el resumen de la mañana **nunca se envió** | 🔴 abierto |
| **H-22** | El test de régimen falla en el 71% y deja `p=1.0` por defecto | 🔴 abierto |
| **B4** | Render gratis borra el disco: 2.1 no tiene Litestream/R2 | 🔴 abierto |
| **Rate limit HL** | 1.344 req/min > 1.200 ⇒ 429; ritmo actual 25–30 ⇒ **4–8 corridas/día** | 🔴 Track A |
| **B3** | `cycle_id` roto: join señales↔snapshot = 0 | 🔴 abierto |
| **B5** | El pipeline reescribe `central_params.json` en cada corrida ⇒ ensucia git | 🟡 P2 |
| **B6** | `verificar.py` no mira los ADR 014 y 016 | 🟡 P2 |
| **B7** | `.gitignore` oculta `diagnostico_*.py` | 🟡 P2 |
| **H-21** | `en_ventana()` trabaja con hora entera | ⏸️ bloquea H-18/H-13 |
| **H-18 / H-13 / H-14 / H-2 / H-4 / H-6 / H-8 / H-7b** | Detalle en `HANDOFF.md` y `docs/PENDIENTES.md` | ⏸️ diferidos |

---

## 🎯 SIGUIENTE PASO

**1 · Implementar el ADR 016** (lo que cierra B1). Hoy está en estado PROPUESTO:
hay que pasarlo a ACEPTADO y después tocar el motor — retirar el umbral 0,0012,
poner el test sobre los **retornos** (HAC, α=0,05 fijado antes), guardar `t` y `σ`
con su migración, y validarlo con la serie sintética "tendencia moderada en activo
calmo" (el código viejo dice RANGE; la regla nueva, TREND).

**2 · B2** (tolerancia de 30 min en el resolvedor) → **3 · B4** (Litestream) →
**4 ·** los 30 días de datos con el protocolo OOS escrito **antes** de T₀ (ADR 012).

**Pendiente transversal: ADR 013** — qué significa "confiable" (persistencia,
acierto contra baseline, calibración). Mientras no exista, la `confidence` del
motor es un **100 fijo** y la calibración no se puede medir.

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
- **Después de un patch aditivo, releer el documento ENTERO.**
