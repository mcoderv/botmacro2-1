# PROMPT — DIAGNÓSTICO COMPLETO DEL PIPELINE C0→C4

> **Qué es esto:** el brief de trabajo para auditar el proyecto MACRO2.1
> celda por celda, de C0 a C4, con correcciones **validadas**.
>
> **Cómo usarlo:** pegá el bloque "EL BRIEF" de abajo (desde `## EL BRIEF`
> hasta el final) como primer mensaje de una sesión nueva de Cline, con la
> raíz del proyecto como working directory.
>
> **Fecha:** 2026-10-27 · **Sesión de referencia:** 5 (ver `HANDOFF.md`)

---

## EL BRIEF

Sos un ingeniero de software que audita un proyecto existente. No sos el
autor: **auditas, medís y corregís lo que encuentres, con pruebas.**

### 0. El proyecto en 30 segundos

**MACRO2.1 es un bot de PREDICCIÓN y VALIDACIÓN de tendencia macro para
Hyperliquid. NO es un bot de trading.** No tiene posiciones, SL ni TP: emite
una señal direccional (LONG/SHORT) con un score y después **valida** si el
precio hizo lo esperado (PnL a 4h/8h/24h, MAE/MFE, timing).
GEM (Gemini) produce las señales; MACRO2.1 las audita.

Stack: Python + SQLite + Hyperliquid API. Corre **local en Windows** (CMD) y
en **Render free** (Linux). Producción = repo `botmacro` = **CONGELADA, no
tocar**. Desarrollo = repo `botmacro2-1` = este.

**El pipeline:**
| Celda | Qué hace |
|---|---|
| C0 | Config / params / snapshot de mercado → `backups_v2.1` |
| C1 / C1_5 | Parámetros centralizados (`CENTRAL_PARAMS`) → `central_params.json` |
| C2 | Bóveda: migraciones de schema + auto-restore → `vault_v2.1.db` (23 tablas) |
| C2_5 | Contexto (⚠️ import con fallback silencioso) |
| C3 | Macro engine: ADF/FFD, POC/caja/FVG, score v2 → `macro_audit_log`, `gem_macro_snapshot` |
| C3_5 | Regime engine → `regime_state`, `regime_features` |
| C4 | Validador: emite, captura precios, resuelve a 4/8/24h → `senales_validadas`, `senales_metricas`, `price_snapshots`, `c4_execution_log` |
| `scheduler.py` | El loop de Render (orquesta + Telegram) |
| `ventana.py` | `en_ventana()` — la ventana operativa |

**Estado de la DB:** 914 señales, 902 resueltas a 24h. **Zona horaria: hora
local Caracas (UTC−4).**

### 1. Antes de tocar NADA, leé esto

En este orden (es autocontenido, no vas a necesitar contexto de nadie):

1. `docs/RELEVO_IA.md` — **el brief completo del proyecto** (18 secciones).
   Es la fuente de verdad del diagnóstico anterior: hallazgos H-1→H-22, la
   fórmula real del score, las 8 afirmaciones prohibidas y el plan.
2. `AGENTS.md` — las reglas + §8 (fórmula real) + §10 (lista negativa) +
   §11 (protocolo OOS) + §13 (la ronda del 27/10).
3. `ESTADO.md` — dónde estamos y qué está roto.
4. `docs/PENDIENTES.md` — el tracking oficial.
5. `decisiones/` — los 13 ADR. Cada corrección que propongas debe ser
   coherente con el ADR vigente; si lo contradice, **decilo y proponé el ADR
   nuevo** (no lo ignores).
6. `verificar.py` — el gate. Entendé qué chequea antes de tocarlo.

### 2. Las reglas de la casa (no negociables)

- **Producción (`botmacro`) está CONGELADA. No la tocas.**
- **Si algo funciona, no se toca sin un ADR.**
- **Nunca creás ni editás un archivo sin que el usuario diga "ok".** Presentás
  el diseño en el chat y esperás. Esto aplica a TODO: scripts, parches,
  docs, migraciones.
- **CMD.exe únicamente** (el usuario trabaja en Windows CMD): sin PowerShell,
  sin `curl`/`wget` de unix, sin `&&`, sin `;`.
- **1 a 4 comandos por turno.** Independientes o de solo lectura → juntos.
  Dependientes o que pueden fallar → de a uno, con **output esperado** y
  **"pegá la salida"**.
- **No mezcles tareas:** si estás validando un fix, ese es el ÚNICO foco del
  turno. Cerralo (self-test + commit) antes de abrir otra cosa.
- **Después de cada cambio: `python verificar.py`.** Si falla, no avanzás.
- **Un commit por cambio**, con `python git/guardar.py "mensaje"`.
- **Nunca comparás HR/PF entre etiquetas o ventanas sin cortar por día.**
  Y el grano correcto es el **CICLO**, no el día.
- Los parches siguen el patrón del proyecto: `.bak` + `--deshacer` +
  **self-test** que falla si el cambio no quedó bien.

### 3. ⭐ REGLA 1 — NINGUNA CORRECCIÓN SIN VALIDADOR

**Este es el punto central del encargo. No lo saltees.**

Una "corrección" sin validador **no se aplica**. Se reporta y se explica por
qué no se pudo validadar.

**Qué es un validador aceptable:**

| ✅ Aceptable | ❌ NO aceptable |
|---|---|
| Un test que **falla con el código viejo** y **pasa con el nuevo** | "Revisé el código y parece correcto" |
| Un script que compara el estado ANTES vs DESPUÉS (con y sin el fix) sobre la DB real | "La documentación dice que debería ser así" |
| Un `PRAGMA table_info` / `PRAGMA integrity_check` que demuestra el schema esperado | "Es un patrón conocido" |
| `verificar.py` extendido con un check nuevo que falla antes del fix | Un print de un valor sin comparar contra nada |
| Un contador A/B sobre la DB real | Razonamiento theoretical |
| Un test de la API real (request real, respuesta real) contra un mock | Un test que mockea el comportamiento a verificar |

**El validador tiene que cumplir 4 cosas:**
1. **Ejecutable** — se corre con un comando y devuelve un resultado.
2. **PASS/FAIL explícito** — no "parece que anda". Un exit code o un `OK`/`XX`.
3. **Discriminante** — **demonstra el bug ANTES** de aplicar el fix. Si el
   validador pasa con el código viejo, **no sirve**: no prueba nada.
4. **Repetible** — se puede volver a correr después y sigue diciendo lo mismo.

**Si no podés escribir un validador discriminante para una corrección, NO la
aplicás.** La reportás como "riesgo asumido" con el motivo. Eso es una
respuesta profesional, no una falla.

**Cada corrección que entregues va con:**
- el validador (código),
- **la salida del validador ANTES del fix** (que debe fallar y por qué),
- **la salida DESPUÉS del fix** (que debe pasar),
- y el `.bak` + `--deshacer` para poder revertir.

**Trampa conocida del proyecto:** el self-test de un patch verifica que lo
*nuevo* esté presente, **no que no rompa lo viejo**. Un parche aditivo sobre
un documento que no se releyó entero dejó dos secciones contradictorias
(`AGENTS.md` §5.1.c vs §9, ambos escritos por nosotros). **Después de cada
patch, releé el archivo ENTERO y buscá contradicciones.**

### 4. ⭐ REGLA 2 — SI NO SABÉS, INVESTIGALO EN INTERNET

**No inventés.** Ni un número, ni el comportamiento de una API, ni una fórmula.

Cuando te falte un dato para poder corregir algo:

1. **Buscalo en la fuente primaria** (docs oficiales, spec, RFC, paper, código
   fuente del proyecto). Si hay que usar búsqueda web, buscá la fuente
   primaria, no un blog.
2. **Registralo** con este formato exacto:

```
### PENDIENTE DE INVESTIGACIÓN — <número>
Pregunta      : <qué no sabés, en una línea>
Por qué importa: <qué corrección o decisión depende de esto>
Fuente a mirar: <URL o nombre del doc oficial>
Qué buscar    : <términos exactos / endpoint / parámetro>
Qué decidirá  : <qué harías con cada respuesta posible>
```

3. **Decíselo al usuario al final del informe**, en una sección
   **"PENDIENTE DE INVESTIGACIÓN (para el usuario)"**. El usuario las busca.
   Mientras tanto, **no avanzás con la corrección que depende de eso** (podés
   avanzar con las demás).

**Casos donde esto aplica siempre:**
- Cómo se comporta un endpoint de Hyperliquid (rate limits, pesos, límites de
  velas, WS) ⇒ **docs oficiales de Hyperliquid**.
- Qué significa un p-value, un test, un criterio de significancia ⇒ **paper
  original o libro**, no Wikipedia.
- Cómo se comporta una fórmula de un paper ⇒ **el paper**.
- Cualquier versión de una librería ⇒ **su changelog/release notes**.

**Ejemplo de cómo se aplicó en este proyecto (27/10):** una IA externa usó
`arXiv:2607.09230` (Jeon, U. Korea, 10-jul-2026) diciendo que validaba el
diseño del bot. Al verificarlo, el paper trata transiciones de estado
L2→1-5 min, **no** precios a 4h-24h. Su tesis real ("state-first") sí
respalda el NO-GO estructuralmente, pero **el uso que se le dio estaba mal**.
⇒ Ese tipo de error se evita verificando la fuente primaria.

### 5. ⭐ REGLA 3 — LAS 8 AFIRMACIONES PROHIBIDAS

**Si una de estas aparece en tu informe, está mal.** Están en `AGENTS.md` §10.
No las repitas, no las contradigas y no las des por buenas:

1. "El `macro_score_v2` tiene poder predictivo." (ρ = +0,119 · NO-GO)
2. "El sesgo multi-TF no funciona." (N/A sólo 5,6% / 5,8% / 0% ⇒ funciona)
3. "El score se calcula en régimen estacionario fuerte." (se calcula donde el
   test **no falló**; en el 71% no corrió)
4. "El score v2 está contaminado por la escala del volumen." (ya normalizado)
5. "El término `d` es degenerado / hay que eliminarlo." (es divergencia real)
6. "El score v2 es una regresión por usar `cvd_crud` en vez de `rvd_ultimo`."
   (`rs` ya es un ordinal de `rvd`)
7. "MACRO2.1 es un bot de trading." (es predictor + validador)
8. "Se puede comparar HR/PF entre etiquetas o ventanas sin cortar por día."
   (el grano correcto es el ciclo)

### 6. Qué auditar, celda por celda

Para **cada** celda de la lista: `C0`, `C1`, `C1_5`, `C2`, `C2_5`, `C3`, `C3_5`,
`C4`, `scheduler.py`, `ventana.py`, `main.py`.

**Para cada una, entrega:**

1. **Qué hace realmente** — verificado en el código, con **nº de línea**.
   No lo que dice la doc; lo que hace el código.
2. **Qué escribe y dónde** — tabla, columnas, archivos.
3. **Fallos encontrados** — con **evidencia**: cita de línea, o salida de un
   comando, o un número medido sobre la DB.
4. **Severidad** — `P0` (rompe algo o pierde datos) / `P1` (degrada o
   invalida una medición) / `P2` (higiene o deuda).
5. **Corrección propuesta** + **su validador** (Regla 1) + el impacto de no
   corregirla.

**Temas que ya sabemos que están mal — verificálos, no los repitas de memoria:**
`vault_v2.db` vs `vault_v2.1.db` (5 archivos) · la ventana real 8-17 vs la que
dice el gobierno · H-20 (16,2% de señales fuera de la ventana) · el test de
régimen que falla en el 71% · `cycle_id` en 0/914 · `data_quality` siempre NULL ·
logs sobrescritos · rate limit 1344 vs 1200 req/min · `en_ventana()` con hora
entera · los 5 imports con fallback silencioso · `main.py` con 8 celdas y no 9.

**Y buscá los que NO sabemos que están mal — ese es el valor de este encargo.**

### 7. Sobre la base de datos

- `data/vault_v2.1.db` — **leer sí, escribir NO.** Es la única fuente de verdad
  y `data/` está gitignored (no está en GitHub ⇒ **hacé un backup antes de
  tocar nada**, y recordá al usuario que lo suba a Drive).
- Para medir, **copiá la DB a un scratch** y trabajá sobre la copia, o abrila
  en modo read-only. **Nunca** `UPDATE`/`DELETE`/`DROP` sobre la original.
- Toda medición debe decir **cómo se midió** (query o script) y **con qué n**.

### 8. Entregables

**A · Un informe** en Markdown, una sección por celda, con los 5 puntos de §6.
Guardalo donde el usuario te lo pida (por defecto `analisis/` o `docs/`).

**B · Una lista de correcciones** al final, ordenada por severidad, con:
| # | Corrección | Archivos | Severidad | Validador | ¿Aplicable ya? |

**C · Una sección "PENDIENTE DE INVESTIGACIÓN (para el usuario)"** con lo que
tenés que buscar (Regla 2).

**D · Tu veredicto de una línea:** ¿el pipeline está en condiciones de
sostener un OOS de 30 días, sí o no? Y si no, **qué falta**.

### 9. Lo primero que hacés

**No escribas código todavía.** En el **primer turno**:

1. Leé los 6 documentos de §1.
2. Corré `python verificar.py` y pegá la salida.
3. Corré `git log --oneline -10` y pegá la salida.
4. Entregame un **plan de auditoría**: en qué orden vas a atacar las celdas,
   qué medirías primero, y qué contradicciones ya te aparecen entre lo que
   dice la doc y lo que hace el código.
5. Preguntame lo que falte para arrancar.

**Después de ese plan y mi "ok", recién ahí proponés correcciones, una por
turno, con su validador.**

### 10. Lo que NO hacés

- No tocás la producción ni el repo `botmacro`.
- No reescribís el `macro_score_v2` (congelado, ADR 009) ni su rama.
- No tocás `docs/INFORME_MACRO2.1.md` (es la spec de referencia).
- No creás ADR sin que lo pidamos.
- No aplicás una corrección sin validador discriminante.
- No inventás números, ni fuentes, ni comportamientos de APIs.
- No reformateás código que funciona (el diff tiene que ser **mínimo y
  justificado**).
- No hacés las 11 correcciones en un turno: **una por turno**, con su
  self-test y su commit.