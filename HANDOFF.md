# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a los chats viejos que venís guardando a mano.
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `docs/PENDIENTES.md`
> + `git log --oneline -20` + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-24
Sesion   : 4
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : a78726b (H-17) + el commit de este gobierno
DB       : 914 señales (902 resueltas a 24h)
```

---

## 1. Qué hice en esta sesión

### A. ADR 004 — Max DD con capital compuesto (H-15) + fuente única del ADF (H-12)
- `report_validator.py` y `C4_SENIAL_VALIDATOR._calculate_metrics()` usaban
  `np.cumsum(pnls)` (suma aritmética de %) ⇒ Max DD de **270,88%**, imposible.
  Ahora `np.cumprod` sobre índice base 1.0 ⇒ **siempre entre 0% y 100%**.
- La curva que consume el reporte se expone en **PnL%** sobre el capital
  compuesto (`((_equity - 1.0) * 100.0)`): antes mostraba "+87,432%" en verde
  cuando era **−12,568%** de pérdida (unidad equivocada + signo invertido).
- **Medido en la DB real:** 4h DD 83,94%→**58,21%** · 8h 137,25%→**75,80%** ·
  24h 270,74%→**94,06%**. El PF se movió **< 1%** ⇒ H-16 queda **diferido**.
- **H-12:** el 0.02 huérfano del umbral ADF salió del literal `validation`, de
  `val_defaults` y del fallback de C3_MACRO. El banner lee la fuente real.

### B. ADR 006 — Ventana operativa configurable (H-17)
- La ventana sale del JSON (`CENTRAL_PARAMS["ventana_operativa"]`), no de
  constantes en 3 archivos. **NO** se importa `C1_5_PARAM_local` desde
  `ventana.py` (al importarse reescribe ese JSON).
- Nuevos modos: `VENTANA` (rango horario) y `CONTINUO` (24/7). Soporta
  **cruce de medianoche** (p.ej. 20:00→04:00) y `DIAS_SEMANA`.
- CLI: `python ventana.py --ver / --continuo / --inicio X --fin Y / --dias ... / --intervalo N`.
  La duración **no** tiene que ser múltiplo de 4h (solo avisa).
- **Bug corregido (H-17):** el bloque de resúmenes de Telegram estaba
  **dentro** de `if not en_ventana():` ⇒ en 24/7 el resumen de las 17:00 nunca
  se enviaba y las banderas nunca se reseteaban a medianoche. En el modo
  VENTANA 8-17, el **resumen de las 8:30 AM nunca se enviaba**.
- Ventana restaurada a **8-17** (el default del script era 8-16 y quitaba 1h).

### C. Análisis de timing y MAE/MFE reales (`analisis/analisis_timing_real.py`)
- **Timing (914 señales):** FAVOR 363 / CONTRA 512 / NEUTRO 39.
  HR por timing a 24h: FAVOR **67,2%** (PF 3,24) vs CONTRA **27,5%** (PF 0,26).
  A 4h: FAVOR 54,0% vs CONTRA 18,8%. A 8h: 53,4% vs 16,6%.
- **Bug del timing 100% CONTRA diagnosticado y corregido:** 908 de 914 señales
  tienen un snapshot con `ts == ts_emision` exacto ⇒ `dt=0` ⇒ el movimiento 0
  cumplía ambos criterios ⇒ el desempate daba CONTRA. Fix: excluir `dt <= 0`
  + `favor == contra → NEUTRO`.
- **MAE/MFE reales (902 señales):** LONG MFE +0,84% / MAE 2,46% ⇒ payoff
  **−2,9:1**; SHORT MFE +2,84% / MAE 1,62% ⇒ **1,75x**. movement contrario
  primero: LONG 54,0% vs SHORT 34,3%.
- **σ por señal:** mediana **1,1458%**, rango 0,318%–3,014% ⇒ el umbral fijo
  0,05% ≡ **k = 0,044σ** (22× más severo en el activo más volátil).
  **⇒ ADR 001 queda justificado con números.**
- **H-14 medido:** 472 de 914 señales (52%) cambian de PnL con la corrección,
  pero el sesgo neto en HR/PF es **< 1%** ⇒ los números se sostienen.
- **La resolución de 8h es inservible hoy:** lag mediano **4,03h** y
  **735/914 señales con lag > 1h** (la ventana 8-17 no tiene snapshots a
  las 20:00). **Con 24/7 el lag baja a ~21 min.**

### D. Gobierno
- `AGENTS.md`: §0 (MACRO2.1 NO es un bot de trading), §5.4.b (H-13/14/16),
  §5.6 (asimetría), §5.7 (aviso de look-ahead), ADR 004/005/006, ventana
  configurable, fixes de formato, 914 señales.
- `ESTADO.md`, `HANDOFF.md`, `docs/PENDIENTES.md`: reescritos.
- **ADR 005** (caja simétrica) PROPUESTO · **ADR 006** (ventana) ACEPTADO ·
  ADR 001 append con k = 0,044σ.

---

## 2. Los hallazgos importantes (léelos antes de tocar el score)

### 2.1 MACRO2.1 NO es un bot de trading
Calcula score, emite señal, valida. **No abre posiciones, no tiene SL ni TP.**
El "43,8% toca SL primero" del GEM es de **MACRO2 (C7, producción)**. En 2.1
esa cifra es **timing**, no P&L.

### 2.2 El score v2 SÍ discrimina — el problema es la COBERTURA
A 24h: FUERTE FAVOR HR **93,8%** (PF 25,65) · MODERADA **77,8%** · RUIDO
**65,3%**. Pero solo **86 de 914 señales (9,4%)** son FUERTE o MODERADA.
**H-9 manda.** Recalibrar umbrales sobre un score sin multi-TF es calibrar
sobre ruido.

### 2.3 La asimetría LONG/SHORT es el hallazgo más sólido
3 métodos independientes (ver `AGENTS.md` §5.6). **ADR 005 propuesto.**

### 2.4 H-10 sigue feroz (confound temporal)
21/10 HR 84,4% PF 20,05 · 23/10 HR 16,7% · 18/10 HR 25,9% PF 0,229.
**Un solo día mueve el PF de 0,23 a 20,05.** Nunca comparar etiquetas sin
cortar por día.

### 2.5 El timing actual tiene look-ahead parcial
Se calcula sobre la trayectoria completa hasta el horizonte. La prueba limpia
es **timing temprano (1h) con PnL medido desde t+1h** (`--timing-h`, falta).

---

## 3. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Activar el 24/7 | Depende de si el hosting es free o pago. **Decisión del usuario.** |
| Arreglar `s_mtf = 0` / la rama del `ms_v2` | Es un cambio al scoring ⇒ necesita ADR, y el diagnóstico del `N/A` no está cerrado. |
| Mover el timing a 1h (`--timing-h`) | Requiere v3 del script de análisis. |
| H-13 / H-14 / H-16 | Impacto medido bajo (< 1% en PF). Van después del diagnóstico de H-9. |
| ADR 001 (k×σ) implementado | La fórmula está justificada (k = 0,044σ) pero el PF no depende del break-even ⇒ no mueve el PF. |
| Matar los 5 fallbacks silenciosos | Toca 4 módulos. Sesión propia. |
| Actualizar `verificar.py` a 6 ADRs | Requiere ver el archivo. Pendiente. |
| Backup a Drive | **Es una acción manual tuya.** Es la prioridad #1 y no la puedo hacer yo. |

---

## 4. Qué creo que está frágil (opinión sin filtros)

1. **El score v2 no puede discriminar** (H-9). Arreglar esto tiene más impacto
   que recalibrar cualquier umbral.
2. **Cualquier análisis del v2 sobre las 877 señales es basura.** El grupo real
   son 111 (3 días), y aun esas están confundidas por fecha.
3. **Los 5 fallbacks silenciosos** siguen siendo el riesgo #1 latente.
4. **La ventana de 8h hoy no sirve** (lag mediano 4,03h). Con 24/7 se arregla
   sola; con 8-17 no.
5. **El auto-restore nunca se probó**: C2 dice "Sin backups previos".
6. **LONG pierde, SHORT gana.** Y dentro de los cripto, BTC PF 0.30 y SP500
   PF 0.28. Eso no lo arregla ningún umbral.
7. **Cero tests.** `verificar.py` es el primer paso, no el final.

---

## 5. Qué chequear primero en la próxima sesión

1. `python verificar.py` ⇒ tiene que dar **19 ok / 0 fallas**.
2. `python git\estado.py` ⇒ leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `AGENTS.md` §0, §5.1.b, §5.1.c, §5.6 ⇒ los hallazgos de hoy.
4. Si tocás el v2: leer `AGENTS.md` §5.1.b **ANTES** de comparar etiquetas.

---

## 6. Cómo verificar que no rompiste nada

```cmd
python verificar.py
python gitevisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 7. Cosas pendientes de confirmación (preguntas abiertas)

- **¿Render free o de pago?** Define si el 24/7 se activa ya. (Si es free y
  el proceso se cae, corré el bot en local: los 30 días para el OOS del 21/11
  se collecting igual.)
- **¿Qué cambió el 2026-10-19 en el pipeline?** (despliegue v7.9.3 / cambio de
  ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es un
  artefacto de despliegue o de diseño.
- **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** (el motivo está en
  `logs_v2.1\*.log`).
- ¿Los 4 archivos "Nivel C" se borran o se quedan?
- ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?