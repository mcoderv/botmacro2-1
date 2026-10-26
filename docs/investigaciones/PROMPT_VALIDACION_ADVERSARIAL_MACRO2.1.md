<!-- MACRO2.1:AVISO-INVESTIGACION -->
> # ⚠️ DOCUMENTO DE TRABAJO — LEÉ ESTO PRIMERO
>
> **Este prompt (v3) YA SE EJECUTÓ.** Su resultado es el informe de la segunda
> opinión, que tiene sus 3 errores corregidos en `docs/RELEVO_IA.md` §9.
>
> **La fuente de verdad del proyecto es `docs/RELEVO_IA.md`.**
> Si te mandan a releer este prompt, no lo re-ejecutes contra el estado actual:
> el diagnóstico ya está cerrado (H-9) y el plan ya existe (§10).


```text
[SYSTEM ROLE]

Eres un Analista de Investigación Senior y Arquitecto de Soluciones con SESGO ADVERSARIAL
explícito. Tu misión no es describir un sistema: es intentar REFUTAR una tesis técnica
concreta, con evidencia publicada, y entregar un veredicto accionable.

Perfil: conocimiento sólido de microestructura de mercados, order flow, econometría de
series de tiempo, diseño de backtests y diseño de software de Collecting de datos en
APIs con rate limits.

Tono: técnico, denso, sin generalidades. Nada de "depende del contexto" sin un número
detrás. Si no tenés evidencia para una afirmación, decilo explícitamente.

────────────────────────────────────────────────────────────────────────────
[INTERACTION PROTOCOL: STEP 1 — AMBIGUITY CHECK]

El tema y las subdivisiones vienen embebidos abajo y están definidos con precisión.
→ Ve directo al Paso 2.
→ Sólo hacé como máximo 2 preguntas si detectás que falta un BLOQUE ESENCIAL de
  contexto (p. ej. si no queda claro qué decisiones están en juego o qué restricciones tiene
  el sistema en producción). No preguntes porPreferences de formato.

────────────────────────────────────────────────────────────────────────────
[INTERACTION PROTOCOL: STEP 2 — STRUCTURAL ANALYSIS]

1. Analizá las 8 subdivisiones embebidas.
2. OBLIGATORIO: añadí "dimensiones emergentes" si detectás vacíos técnicos o teóricos
   esenciales que las 8 no cubren. Cada dimensión emergente debe justificarse en una
   línea y numerarse 9, 10, 11...
3. Para cada subdivisión, decidí si el bloque de evidencia embebido alcanza para
   responderla o si hace falta dato nuevo (y de qué tipo: paper, dataset, código,
   medición propia).

────────────────────────────────────────────────────────────────────────────
[INTERACTION PROTOCOL: STEP 3 — FINAL TECHNICAL REPORT]

Generá el reporte con esta estructura decimal EXACTA:

# [TÍTULO TÉCNICO]

## 1. Resumen Ejecutivo
   - Síntesis del estado del sistema y de la evidencia disponible.
   - Tesis central tal como la formuló el equipo (la que hay que validar).
   - Veredicto preliminar en una línea.

## 2. [Subdivisión N: Nombre]
   ### 2.1. Arquitectura y Fundamentos Técnicos
   ### 2.2. Ecosistema y Madurez Operativa
   ### 2.3. Análisis de Limitaciones y Puntos de Falla
   ### 2.4. Referencias y Evidencia Técnica
   (repetir 2.1–2.4 para cada subdivisión, incluidas las emergentes)

## 3. Conclusiones Proyectivas y Roadmap
   - Hallazgos críticos.
   - Impacto a 2–5 años y tendencias que cambian la decisión.
   - Recomendación estratégica ACCIONABLE, ordenada por (impacto × esfuerzo × riesgo).

────────────────────────────────────────────────────────────────────────────
[PROTOCOLO ANTI-CONFIRMACIÓN — ES LA PARTE MÁS IMPORTANTE]

Tu trabajo principal es REFUTAR. Si no lográs refutar, recién entonces buscá confirmar.

REGLAS DURAS:
1. Cada objeción debe traer CUATRO campos:
   (a) MECANISMO CAUSAL — por qué el efecto existiría o por qué fallaría, en el
       contexto exacto de MACRO2.1 (no en general).
   (b) EVIDENCIA — paper, autor, año, dataset, o métrica. Con URL.
   (c) APLICABILIDAD — qué parte de la evidencia embebida toca o contradice.
   (d) CORRECCIÓN — qué habría que cambiar en la propuesta, o por qué no hay que
       cambiar nada.
2. CLASIFICÁ cada objeción:
   (E) Refutación empírica — un dato/resultado published la contradice.
   (G) Refutación por generalización — el dato es cierto pero el ámbito no aplica.
   (D) Refutación de diseño — el experimento/medición del equipo está mal
       construido y por eso mide lo que no cree medir.
   (E2) Refutación de diseño experimental externo — el paper que se cita tiene
       problemas de diseño que invalidan su conclusión.
   (O) Opinión — marcá como opinión, sin presentarla como evidencia.
3. Prohibido "refutar" con el hecho de que el sample es chico. Eso YA LO SABEMOS y
   está en el bloque de evidencia. Si igual es tu única objeción, decí que la
   evidencia no alcanza para el veredicto y seguí.
4. Prohibido presentar una objeción sin el campo (b). Si no tenés fuente, va como
   (O) y se descuenta.
5. Si un dato del bloque de evidencia embebido contradice la tesis central,
   DECILO explícitamente y en la primera página. El error más caro de esta revisión
   es no corregir un dato propio.
6. No repitas la lista de fuentes ya verificadas como si fueran hallazgos nuevos.
   Al menos 8 de tus citas deben ser FUENTES NUEVAS no incluidas abajo.
7. Si tu conclusión honesta es "no se puede decidir con esta evidencia", esa es una
   respuesta VÁLIDA y útil — pero debés añadir: (a) qué dato falta, (b) qué decisión
   desbloquea, (c) cómo se obtiene ese dato, (d) cuánto cuesta en tiempo/llamadas.
8. No propongas reescribir el producto por estética. Cada recorte o rediseño que
   propongas debe justificarse por evidencia, no por gusto arquitectónico.
9. Formato de veredicto por subdivisión: SEMÁFORO
   🟢 VERDE  = la tesis sobrevive en este punto.
   🟡 AMARILLO= sobrevive con recorte (decí cuál).
   🔴 ROJO   = la tesis es incorrecta aquí (decí en qué y con qué evidencia).

────────────────────────────────────────────────────────────────────────────
[OUTPUT CONSTRAINTS]

- TERMINOLOGÍA: idioma técnico de industria (latencia, resiliencia, semántica,
  escalabilidad, look-ahead bias, poder estadístico, multiple testing, half-life, IC).
  En español.
- CITAS: específicas y verificables [1], [2]... con autor, año y URL.
- VISUALIZACIÓN: usá tablas comparativas cuando una subdivisión compare
  estándares, herramientas o alternativas. En la §2.4 de cada subdivisión,
  incluí una tabla "Afirmación del equipo | Veredicto | Evidencia | Corrección".
- LONGITUD: denso. Sin relleno. Si una subdivisión no tiene evidencia, decilo
  en una línea y seguí.
- El bloque final "VEREDICTO OPERATIVO" es obligatorio y tiene que ser accionable
  sin contexto adicional.

────────────────────────────────────────────────────────────────────────────
[BLOQUE 1 — CONTEXTO DEL PROYECTO]

PROYECTO: MACRO2.1
Es un bot de PREDICCIÓN Y VALIDACIÓN de tendencia macro sobre Hyperliquid.
NO es un bot de trading: no tiene posiciones, ni SL, ni TP. Emite señales, las valida
contra el resultado futuro y guarda evidencia. El trading lo hace otro sistema externo.

Stack: Python, SQLite (una sola DB local: data/vault_v2.1.db), scheduling propio en
un ciclo de 15 minutos, 12 activos: 6 cripto perps nativos (AVAX, BTC, ETH, HYPE, SOL,
XRP) y 6 índices como perps HIP-3 (xyz:CL, xyz:EUR, xyz:GOLD, xyz:SILVER, xyz:SP500,
xyz:XYZ100).

Pipeline:
  C1_5  — config central (JSON + literal en código)
  C2    — boveda: crea/migra el esquema SQLite
  C3    — macro: por ciclo y activo calcula el score macro, el régimen y el sesgo
          multi-timeframe; escribe gem_macro_snapshot + macro_audit_log
  C3.5  — completes el regime/cycle_id del snapshot
  C4    — validador: registra las señales emitidas y las resuelve a +4h / +8h / +24h
          contra price_snapshots; escribe senales_validadas

Horizontes de resolución actuales (hardcoded en C4, línea 56): [4, 8, 24].

Modelos de datos relevantes:
  senales_validadas (914 filas, 35 columnas) — una fila por señal emitida
  macro_audit_log  (3036 filas, 30 columnas) — un renglón por ciclo × activo
  gem_macro_snapshot (2402 filas, 17 columnas) — un renglón por ciclo × activo
  c4_execution_log (204 filas) — un renglón por corrida de C4
  price_snapshots (1886 filas) — precio capturado cada 15 min

────────────────────────────────────────────────────────────────────────────
[BLOQUE 2 — EL CÓDIGO QUE GENERA EL SCORE (C3_MACRO_local.py, líneas 1588-1661)]

def _calculate_ms_v2(zonas, coin) -> float:
    try:
        desglose = zonas.get("score_desglose", {})
        if not isinstance(desglose, dict):
            return 0.0                      # <-- ruta silenciosa 1

        poc_score = int(desglose.get("poc", 0))
        caja_p    = int(desglose.get("caja", 0))
        fvg       = int(desglose.get("fvg", 0))
        rs        = int(desglose.get("cvd_crud", 0))

        p_value_adf = float(zonas.get("p_value_adf", 1.0))
        is_stationary = p_value_adf < ADF_P_VALUE_THRESHOLD   # 0.05

        if is_stationary:                   # rama "reversión a la media" (78,7% de los casos)
            s_base = 0.5*poc_score + 1.5*caja_p + 1.5*fvg + 0.5*rs
        else:                               # rama "momentum"
            s_base = 0.5*poc_score + 0.5*caja_p + 0.5*fvg + 2.0*rs

        # sesgo multi-timeframe: 1h, 4h, 1d  (NO 15m)
        bias_1h_num = _bias_to_num(zonas.get("bias_1h", "RANGO"))   # BULL=+1 BEAR=-1 RANGO=0
        bias_4h_num = _bias_to_num(zonas.get("bias_4h", "RANGO"))
        bias_1d_num = _bias_to_num(zonas.get("bias_1d", "RANGO"))
        s_mtf = 0.30*bias_1h_num + 0.20*bias_4h_num + 0.15*bias_1d_num

        # término de divergencia precio/flujo
        d = 0.0
        if poc_score == 1 and rs <= -1:      d = -2.0
        elif poc_score == -1 and rs >= 1:    d =  2.0

        ms_v2 = s_base + s_mtf + d
        return round(ms_v2, 2)
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.debug(f"_calculate_ms_v2 {coin}: {exc}")   # <-- ruta silenciosa 2
        return 0.0

Y lo que REALMENTE se guarda en el desglose (C3_MACRO_local.py, líneas 1544-1552):
    "score_desglose": {
        "poc": poc_score,          # entero, {-1,+1}
        "caja": caja_p,            # entero, {-2..2}
        "caja_raw": caja,          # valor crudo (no el ordinal)
        "atr_multiplier": round(am, 3),
        "fvg": fvg,                # entero, {-1,0,+1}
        "cvd_crud": rs,            # CVD CRUDO (entero, escala ABSOLUTA por activo)
        "rvd_ultimo": round(rvd, 4),   # NORMALIZADO, grilla 1/9 -- el que va a la DB
    },
⭐ "cvd_crud" y "rvd_ultimo" son variables DISTINTAS. El score usa la primera
   (CVD crudo, no comparable entre activos); la auditoría guarda la segunda.

Y en C4_SENIAL_VALIDATOR.py (líneas 56-97):
    RESOLUTION_WINDOWS_HOURS = [4, 8, 24]
    BREAKEVEN_THRESHOLD_PCT = 0.05
    SCORE_ALTA = 14 ; SCORE_MEDIA = 8 ; SCORE_BAJA = 4        # legacy, escala muerta
    SCORE_V2_FUERTE = 4.0 ; SCORE_V2_MODERADA = 2.0
    def _classify_signal_quality_v2(score):
        a = abs(score)                      # <-- el signo se destruye
        if a >= 4.0:      return "FUERTE"
        elif a >= 2.0:    return "MODERADA"
        else:             return "RUIDO"

Consumo en C3 (línea 2319): score_v2 = z.get("macro_score_v2", 0.0)
Consumo en C4 (línea 290):  macro_score_v2 = z.get("macro_score_v2", 0.0)
Persistencia: gem_macro_snapshot.macro_score_v2 (DEFAULT 0.0) y
               senales_validadas.macro_score_v2 (DEFAULT 0.0)

PESOS TEÓRICOS DEL SCORE: 0.5 (poc) + 1.5 (caja) + 1.5 (fvg) + 0.5 o 2.0 (rs)
+ 0.65 (s_mtf, los 3 TF) + 2.0 (d).
  ⇒ s_mtf (dirección macro) = 14% del peso. d (divergencia) = 33%.

────────────────────────────────────────────────────────────────────────────
[BLOQUE 3 — EVIDENCIA MEDIDA (por el equipo, sobre la DB real)]

A) POBLACIÓN Y ALCANCE
 - 914 señales emitidas. macro_score_v2 == 0.0 EXACTO: 768. Con score real: 146.
 - Reparto por día (senales_validadas, confirmado con lectura directa de la DB):
     13/10: 138 → 138 con 0.0 | 14/10:  73 →  73 con 0.0 | 15/10:  45 →  45 con 0.0
     16/10: 156 → 156 con 0.0 | 17/10: 119 → 119 con 0.0 | 18/10: 143 → 143 con 0.0
     19/10: 142 →  94 con 0.0,  48 REAL (día mixto)
     20/10:  29 →   0 con 0.0,  29 REAL | 21/10: 32 → 32 REAL
     22/10:  25 →  25 REAL | 23/10: 12 → 12 REAL
 - ⭐ INTERPRETACIÓN: el score v2 NO SE CALCULABA antes del 19/10. El bloque de 768
   es HISTÓRICO PRE-DEPLOY, no un bug vigente. Coincide con el hecho histórico
   "v7.9.3 con macro_score_v2 real" del deploy del 19/10.
 - data_quality_emision = "OK" en las 768 ⇒ NO era degradación de datos: la feature
   no existía. c4_execution_log.signals_registered por día = EXACTAMENTE el nº de
   señales de ese día ⇒ C4 registró todo 1:1, sin señales huérfanas ni duplicadas.
 - 3036 auditorías = 12 activos × 253 ciclos. gem_macro_snapshot: 2402 filas, de las
   cuales 279 con score real (el filtro de emisión descarta ~48% de los snapshots).
 - 302 señales de las 914 tienen estado PENDIENTE (las del 23/10); el resto RESUELTA.
   resuelto_4h 907/914 (99,2%) | resuelto_8h 907/914 | resuelto_24h 902/914 (98,7%).

B) DESGLOSE DIARIO (las 146 con score real) — con n por día MUY PEQUEÑO
   24h: 19/10 n=48 HR 77,1% PF 4,52 | 20/10 n=29 HR 31,0% PF 0,41
        | 21/10 n=32 HR 84,4% PF 20,05 | 22/10 n=25 HR 60,0% PF 2,67
        →  TOTAL n=134 HR 65,7% PF 3,04
   4h : 19/10 n=48 HR 43,8% PF 0,55 | 20/10 n=29 HR 24,1% PF 0,45
        | 21/10 n=32 HR 59,4% PF 7,02 | 22/10 n=25 HR 20,0% PF 0,17
        | 23/10 n=5 HR 0,0% PF 0,00  →  TOTAL n=139 HR 37,4% PF 0,49

B2) ⭐⭐ RITMO DEL BOT: CAMBIÓ EN EL DEPLOY (c4_execution_log)
   corridas/día: 13/10: 21 | 14/10: 26 | 15/10: 33 | 16/10: 26 | 17/10: 27
                  18/10: 27 | 19/10: 26 | 20/10: 8 | 21/10: 4 | 22/10: 4 | 23/10: 2
   señales/día:   138 · 73 · 45 · 156 · 119 · 143 · 142 | 29 · 32 · 25 · 12
   ⇒ de ~25-30 corridas/día a 4-8. El "HR 84,4% del 21/10" puede provenir de 1-2
     corridas de un total de 4. El desglose por DÍA es en realidad desglose por
     (día, corrida) en grano fino, y eso NO está controlado.

B3) ⭐⭐⭐ REGIMEN: EL SCORE v2 REAL APARECE CUANDO EL RÉGIMEN DETECTA TENDENCIA
   regime_state de las señales:
     score = 0.0 (n=768, pre-deploy):  RANGE 747 (97,3%) · UNKNOWN 21 (2,7%)
     score REAL  (n=146, post-deploy): RANGE 128 (87,7%) · TREND_DOWN 12 · TREND_UP 6
   ⇒ el score v2 real se asocia a señales con TREND (12,3% vs 2,7%).
   ⇒⇒⇒ CONSECUENCIA: la diferencia de HR entre el bloque pre-score (LONG 35,6%)
     y el post-score (LONG 73,7%) PUEDE SER CAMBIO DE RÉGIMEN DE MERCADO, no efecto
     del score. Con 4 días no se puede separar. Este es el argumento más fuerte
     contra la tesis del equipo y debe ser testeado, no asumido.

C) SCORE POR CUARTIL
   24h: Q1 60,6% PF 1,46 | Q2 50,0% PF 1,09 | Q3 84,8% PF 13,87 | Q4 67,6% PF 10,79
   4h : Q1 29,4% PF 0,08 | Q2 51,4% PF 0,15 | Q3 42,9% PF 3,69 | Q4 25,7% PF 2,23
        (baseline HR a 4h = 37,4%)

D) SPEARMAN (n=139)
   macro_score_v2 vs pnl24 +0,163 | vs pnl4 +0,133
   caja +0,149 / +0,139 | fvg +0,107 / +0,130 | macro_score legacy +0,142 / +0,076
   rvd_ultimo +0,071 / −0,016 | delta_d −0,136 / −0,262

E) SENTIDO (la dirección la define el sesgo multi-TF; 0 contradicciones en 902 resueltas)
   score real (146, 4 días): LONG+BULL n=57 HR 73,7% PF 9,24 | SHORT+BEAR n=77 HR 59,7% PF 1,87
   todas (914, 10-11 días):   LONG+BULL n=435 HR 35,6% PF 0,52 | SHORT+BEAR n=467 HR 57,8% PF 1,27
   4h score real:             LONG+BULL HR 34,4% PF 3,25 | SHORT+BEAR HR 39,7% PF 0,12
   ⇒ el comportamiento del LONG se INVIERTE entre las dos poblaciones (4 días vs 10 días).

F) DISTRIBUCIONES DE LOS INPUTS
   macro_audit_log.p_value_adf: p<0.05 en 78,7% | p=1 exacto en 21,3% | p<0.001 en 59,6%
   macro_audit_log.ambos_estacionarios: 1 en 76,3% (es 1 = estacionario)
   macro_audit_log.bias (multi-TF): RANGO 62,3% | BULL 18,7% | BEAR 18,7% | N/A 0,2%
   macro_audit_log.riesgo_regime: NEUTRAL 83,4% | RISK_ON 13,0% | RISK_OFF 3,6%
   gem_macro_snapshot.bias_1d: RANGO 1847 | BEAR 324 | N/A 135 | BULL 96   (2402 filas)
   gem_macro_snapshot.bias_4h: RANGO 1926 | BEAR 284 | N/A 139 | BULL 53
   gem_macro_snapshot.bias_15m: BEAR 1149 | RANGO 881 | BULL 372  (sin N/A)
   gem_macro_snapshot.regime: RANGE 2196 | UNKNOWN 99 | None 74 | TREND_DOWN 25 | TREND_UP 8
   ⭐ en las 146 con score real, p_value_adf ∈ {0, 0.0001, 0.0002, 0.0003, 0.0005, 0.0009}
     ⇒ TODAS con ADF maximally estacionario.

G) ESCALAS REALES DE LOS COMPONENTES
   poc_score ∈ {−1, +1}            (binario: es un SIGNO, no un score)
   caja_score ∈ {−2,−1,0,1,2}      (conteo ordinal)
   fvg_score ∈ {−1, 0, +1}
   rvd_ultimo: grilla de 1/9, rango [−0.5556, +0.8889], nunca 0
   macro_score_v2 real: 40 valores distintos, rango [−6.5, +5.8]
   residual (score − fórmula declarada con rvd_ultimo): grilla EXACTA de 1/180
   ⭐ el residual de 1/180 = LCM(1/18 del 0.5·rvd, 1/20 del s_mtf, d=2) ⇒ la
     fórmula de arriba es correcta, pero ese test NO discrimina si el `rs` real es
     el CVD crudo o el rvd normalizado (ambos caen en 1/180).

G2) ⭐⭐⭐ HALLAZGO DE CÓDIGO QUE CONTAMINA EL SCORE POR ESCALA
   El score usa `rs = int(desglose["cvd_crud"])` = CVD CRUDO, un entero ABSOLUTO
   cuya magnitud escala con el volumen del activo. Y el término `d` compara
   `rs` contra ±1, es decir `d` es LITERALMENTE UN TEST DE VOLUMEN.
   Reparto del peso del score:
     poc 0,5 (sin volumen) · caja 1,5 (sin volumen) · fvg 1,5 (sin volumen)
     rs 0,5 (estacionario) / 2,0 (momentum)  → ESCALA POR VOLUMEN
     d  2,0                               → ESCALA POR VOLUMEN (compara rs vs ±1)
     s_mtf 0,65 (sin volumen)
   ⇒ entre el 38% (rama estacionario: 2,5/6,65) y el 65% (rama momentum: 4,0/6,15)
     del score es "el activo movió mucho volumen".
   ⇒ HIPÓTESIS DEL EQUIPO: por eso el score NO ordena dentro de un activo, por eso
     el cuartil cross-sectional mezcla activos incomparables, y por eso el término
     `d` se activa en unos activos y en otros no según su liquidez típica.
   ⇒ FIX PROPUESTO (1 línea + re-derivar `d` en la escala nueva): usar
     `desglose["rvd_ultimo"]` (ya se calcula y ya se guarda, línea 1551, escala 1/9)
     en lugar del CVD crudo. PERO: con rvd (máx 0,89) el umbral ±1 del término `d`
     NUNCA se cumpliría ⇒ hay que re-derivar el umbral de `d` en la escala 1/9.
     Eso es un cambio de semántica (ADR), no un parche.

G3) 🔴 BUG DE AUDITORÍA: EL JOIN `senales_validadas` ↔ `gem_macro_snapshot` NO FUNCIONA
   0 de 914 señales matchean por (cycle_id, activo). El cycle_id de las señales tiene
   formato MACRO_<epoch>_<hash> (ej. MACRO_1792432869_056d13) y C3 inserta el snapshot
   con cycle_id = "PRE_REGIME" (línea 2045) confiando en que "C3.5 lo completa"
   (comentario del propio código). El campo correcto (`macro_cycle_id`) SÍ existe en
   `zonas` (línea 1534) ⇒ el bug está localizado en C3.5.
   ⇒ El snapshot es INAUDITABLE: no se puede linkear una señal con su contexto macro.
   ⇒ En cambio `macro_audit_log` SÍ tiene el cycle_id correcto (join 914/914) ⇒ la
     ruta de auditoría viable es macro_audit_log, no gem_macro_snapshot.
   ⇒ Dato menor asociado: `zonas["data_quality"]` es un dict con clave "estado", pero
     el snapshot graba `gctx.get("data_quality_status")` (línea 2054), clave que no
     existe ⇒ data_quality del snapshot siempre queda None.

H2) ⭐⭐⭐ RESULTADO DEL EXPERIMENTO INTERNO (el que el revisor debe atacar)
   H2.1 · ¿RÉGIMEN O SCORE? — las 768 PRE-deploy (sin score v2), por p_value_adf:
     24h:  p<0,01 (estac. fuerte)  n=715  HR 45,2%  PF 0,66  E −0,264
           0,01-0,05 (estac.)      n= 42  HR 11,9%  PF 0,13  E −1,626
           p>=0,50 (NO estac.)     n= 11  HR 81,8%  PF 8,68  E +1,087
     4h :  p<0,01  n=715 HR 41,5% | 0,01-0,05 n=42 HR 26,2% | p>=0,50 n=11 HR 54,5% PF 5,49
   H2.2 · ¿RÉGIMEN O SCORE? — las 146 CON score real, por regime_state:
     24h:  RANGE       n=118 (81%)  HR 66,1%  PF 2,91   E +0,855   ρ(ms2,pnl) +0,119
           TREND_DOWN  n= 11        HR 45,5%  PF 0,70   E −0,163   ρ −0,137
           TREND_UP    n=  5        HR 100%   PF inf    E +4,135   (n=5 ⇒ no es evidencia)
     4h :  RANGE n=123 HR 38,2% | TREND_DOWN n=11 HR 9,1% | TREND_UP n=5 HR 80,0%
     ⭐ RANGE rinde MEJOR que TREND_DOWN ⇒ el score NO es un subconjunto de régimen.
   H2.3 · DENTRO de RANGE, el score NO separa (cuartiles, 24h):
     Q1 [−6,5..−2,7] n=29 HR 65,5% | Q2 n=30 HR 53,3% | Q3 [−1,0..2,5] n=29 HR 82,8%
     PF 10,93 | Q4 [2,5..5,8] n=30 HR 63,3%    ρ(ms2,pnl24) dentro de RANGE = +0,119
   H2.4 · GRANO DE CICLO (25 ciclos para 146 señales; mediana 6 señales por ciclo):
     peores: 3 ciclos del 20/10 con HR 0,0% (n=4, 5, 5) → E −2,12 / −2,21 / −2,24
     mejores: 3 ciclos del 21/10 con HR 85-89% (n=9, 7, 8) → E +2,60 a +2,90
     ⇒ dentro de la misma tarde hay ciclos con 88,9% y con 0,0%.
   H2.5 · ¿EL SCORE ES VOLUMEN? ρ(|ms_v2|, |cvd_raw_ultimo|) = +0,015 (≈0).
     |cvd| medio por activo: BTC 3.220 · xyz:GOLD 1.800 · xyz:SP500 4.969 ·
     ETH 35.475 · xyz:XYZ100 1.920 · SOL 120.143 · xyz:SILVER 140.918 ·
     xyz:CL 155.397 · AVAX 80.252 · xyz:EUR 811.669 · HYPE 507.996 · XRP 4.457.653
     ms2 medio por activo: −3,5 a +2,26  ⇒ el rs que entra YA está normalizado.
     Score parcial con rs=cvd_raw: ρ +0,154 | con rs=rvd_ultimo: ρ +0,144 (casi igual).
     Término `d`: se activa en 134/134 señales con CVD crudo; en 0/134 con rvd_ultimo
     ⇒ el término `d` (peso 2,0 = 33% del score) es DEGENERADO.
   H2.6 · TEST DE P1 — percentil por activo vs score absoluto (n=134, 24h):
     score ABSOLUTO:        ρ +0,163 | Q1 60,6% PF 1,46 | Q2 50,0% PF 1,09
                            Q3 84,8% PF 13,87 | Q4 67,6% PF 10,79   ← NO monótono
     PERCENTIL POR ACTIVO:  ρ +0,192 | Q1 51,5% PF 1,54 | Q2 64,7% PF 1,70
                            Q3 69,7% PF 7,88 | Q4 76,5% PF 18,98   ← MONÓTONO
     ρ(ms2,pnl24) DENTRO de cada activo (n=9-14, ninguno significativo):
       AVAX +0,10 | BTC +0,56 | ETH +0,28 | HYPE +0,43 | SOL +0,37 | XRP −0,34
       xyz:CL +0,65 | xyz:EUR +0,56 | xyz:GOLD −0,30 | xyz:SILVER −0,44
       xyz:SP500 −0,42 | xyz:XYZ100 −0,44

H) OPERACIONAL
   c4_execution_log: 204 corridas. duration_seconds media 0,06 s, máx 0,63 s (el campo
     NO mide la duración real de C4). snapshots_captured media 9,01 de 12, min 0.
     signals_resolved: 39 corridas con 0. Las 22 corridas con 0 snapshots resolvieron
     268 señales (12 de media) ⇒ "sin snapshots" NO impide resolver.
   logs_v2.1: 39 líneas (se sobreescribe) → 18 ocurrencias de HTTP 429 "rate limited"
     en el RegimeEngine. Sin historial ⇒ imposible diagnosticar el N/A por logs.
   resuelto_4h 907/914 (99,2%) | resuelto_8h 907/914 | resuelto_24h 902/914 (98,7%)
   calidad_senal_v2: RUIDO 828 | MODERADA 46 | FUERTE 40
     HR 24h por etiqueta: FUERTE 64,7% (n=34) | MODERADA 59,1% (n=44) |
                          RUIDO 71,4% (n=56)  ⇒ la etiqueta está INVERTIDA
   calidad_senal legacy: RUIDO 685 | BAJA 229 | 0 ALTA | 0 MEDIA  ⇒ escala 14/8/4 muerta
   HR 4h por hora de emisión: 8h → 7,1% PF 0,00 E −1,373 (n=14) | 9h 40,0% | 10h 20,0%
     (PF 16,96) | 13h 23,5% | 14h 30,0% | 15h 55,6% | 16h 33,3% | 20h 76,0% PF 7,02 (n=25)
     | 21h 0,0% (n=7)

────────────────────────────────────────────────────────────────────────────
[BLOQUE 4 — FUENTES YA VERIFICADAS POR EL EQUIPO (no las repitas como hallazgo nuevo;
usalas como base y citá OTRAS)]

Hyperliquid
 - https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits
     REST: 1200 request-weight/min/IP; info requests weight 20; candleSnapshot weight
     +1 por cada 60 items devueltos; "when rate limited, an address is allowed one
     request every 10 seconds"; WS: 10 conexiones, 1000 suscripciones, 2000 msg/min.
 - https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint
     candleSnapshot: sólo los 5.000 candles más recientes por mercado e intervalo.
     Intervalos 1m..1M. Los HIP-3 requieren prefijo de dex ("xyz:XYZ100").
 - https://www.dwellir.com/blog/hyperliquid-historical-data-for-backtesting
     5.000 velas ⇒ ~3,5 días en 1m. s3://hyperliquid-archive: L2 snapshots mensuales
     "with no completeness guarantee". HIP-3: trades desde 13-oct-2025, L2/funding/OI
     desde 16-feb-2026.
 - https://docs.bitquery.io/docs/perpetuals/hyperliquid/  (ventanas rodantes ~30 días)

Orden flow / microestructura
 - https://arxiv.org/abs/1011.6402  (Cont, Kukanov, Stoikov — OFI → Δprecio lineal,
     R²~65%, β ∝ 1/profundidad, válido entre 50 ms y 5 minutos)
 - https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12413  (horizonte efectivo ≈
     2 cambios de precio promedio)
 - https://dl.acm.org/doi/abs/10.1145/3604237.3626874  (Decomposed OFI, forward-looking)

Estacionariedad
 - https://pdfs.semanticscholar.org/0ba5/e4d604641a8c982fd08932600b6fd157a682.pdf
     (niveles de cripto NO estacionarios; los que ADF marca estacionarios, KPSS los marca
     NO estacionarios)
 - https://www.quantt.co.uk/resources/mean-reversion-testing
     (ADF: mínimo ~500 obs; Hurst: 1000+; microestructura genera anti-persistencia
     ESPURIA en horizontes cortos; Bonferroni/FDR por múltiples tests;
     Zivot-Andrews / Bai-Perron para rupturas)
 - https://pure.jgu.edu.in/id/eprint/10088/1/Does%20Price%20Discovery%20Process%20Hold%20...pdf
     (Bitcoin I(1): no estacionario en niveles, estacionario en diferencias)

SMC / price action
 - https://thortradecopier.com/blog/does-ict-smart-money-concepts-work
     (83,4% de FVG revisitados en 20 barras vs 83,5% de niveles aleatorios ⇒ el
     "fill rate" no prueba nada; liquidity sweeps predicen CONTINUACIÓN en 65/66 folds)
 - https://indicatoredge.io/smart-money-research
     (54 variantes de reglas FVG sobre 2.553.973 barras EURUSD 1m: mejor win rate
     56,3%, 0/54 rentables tras costes; las kill zones están replicadas)
 - https://statoasis.com/overfit/research/ict-backtest-what-survives  (648 backtests)
 - https://quantzee.com/smart-money-concepts-audited-which-smc-ideas-survive-rule-test/

────────────────────────────────────────────────────────────────────────────
[BLOQUE 5 — LA PROPUESTA QUE HAY QUE VALIDAR (tesis del equipo)]

TESIS CENTRAL A VALIDAR (v2 — revisada DESPUÉS del experimento interno):
"El macro_score_v2 NO tiene poder predictivo demostrado. Todo el efecto observado
 (HR 65,7% · PF 3,04 · n=134 a 24h) es RÉGIMEN + TIEMPO + GRANO DE CICLO, no score:
 (a) RÉGIMEN: en el histórico PRE-deploy (768 señales, sin score v2), las señales en
     p_value_adf >= 0,50 (no estacionario = tendencia) rindieron HR 81,8% · PF 8,68 ·
     E +1,087% (n=11), mientras el bucket p<0,01 (estacionario fuerte) rindió
     HR 45,2% · E −0,264% (n=715). El efecto PRECEDE al score.
 (b) DENTRO de las 146 con score real, el grupo regime_state=RANGE (n=118, 81%)
     rindió MEJOR (HR 66,1%) que TREND_DOWN (n=11, HR 45,5%). O sea el score NO es un
     subconjunto de régimen.
 (c) Y PEOR: el score v2 SÓLO SE CALCULA en el régimen estacionario fuerte (las 146
     tienen todas p_value_adf < 0,001) — que es justamente el bucket donde el bot
     pierde. El score existe donde no funciona.
 (d) GRANO: dentro de la misma tarde hay ciclos con HR 88,9% (n=9) y ciclos con
     HR 0,0% (n=4, 5, 5). Ningún score explica eso.
 CONCLUSIÓN DE PRODUCTO PROPUESTA: NO-GO del score como predictor, y reorientar
 MACRO2.1 hacia el ÚNICO hallazgo con señal: 'señales emitidas en régimen no
 estacionario rinden +1,087% de expectativa a 24h' — que es un INPUT (el régimen),
 no un score. Y el único fix del score con evidencia: el PERCENTIL POR ACTIVO
 (ρ +0,192 monótono vs +0,163 no monótono del score absoluto)."

PROPUESTAS CONCRETAS A REFUTAR O CONFIRMAR:
 P1  (REVISADA) Normalizar el score POR ACTIVO (percentile within asset) en vez de
    usar el número absoluto cross-sectional. EVIDENCIA A FAVOR: el percentil ordena
    de forma MONOTÓNICA (Q1 51,5% → Q2 64,7% → Q3 69,7% → Q4 76,5%) mientras el
    absoluto NO (Q1 60,6% → Q2 50,0% → Q3 84,8% → Q4 67,6%); ρ +0,192 vs +0,163.
    CONTRA: 5 de 12 activos tienen ρ NEGATIVO (XRP −0,34, GOLD −0,30, SILVER −0,44,
    SP500 −0,42, XYZ100 −0,44) con n=9-14 por activo.
 P1b (NUEVA, y es lo que la evidencia SÍ sostiene) El término `d` (peso 2,0) se
    activa en 134/134 señales ⇒ es un término DEGENERADO (compone rs contra ±1 con
    un rs que siempre lo supera), no un test de divergencia. Debería eliminarse,
    re-escalarse o reformularse. ¿Qué pasa con el score si se quita el 33% de su
    peso?
 P1c (CORRECCIÓN) La hipótesis de que el score esté "contaminado por volumen
    absoluto" FUE REFUTADA por la medición: ρ(|ms_v2|, |cvd_raw_ultimo|) = +0,015
    (≈0) y |cvd| medio varía 2476× entre activos (BTC 3.220 … XRP 4.457.653) mient
    ras ms2 medio va de −3,5 a +2,26 ⇒ el `rs` que entra al score YA está
    normalizado. La hipótese de que el CVD crudo no es comparable entre activos
    sigue siendo cierta en la DB, pero NO llega al score.
 P2  (REFUTADA en su forma actual) "Invertir el score de reversión a continuación".
    Los datos no lo apoyan: dentro de las 146, RANGE (HR 66,1%) rindió mejor que
    TREND_DOWN (HR 45,5%), y el HR alto estaba en las señales NO estacionarias
    (p>=0,50) tanto antes como después del deploy. ¿Qué queda de esta propuesta?
 P3  El fix prioritario NO es la fórmula: es la recolección de datos. 12 activos × 4 TF
    = 48 candleSnapshot por ciclo ≈ 1344 de peso > 1200/min ⇒ el 429 es aritmética.
    Fix: cache + batch + WS + backoff exponencial + reducir TFs por ciclo + hacer
    visible el 0.0 con un sentinel (aunque el 0.0 histórico sea pre-deploy, no bug).
 P4  La rama del score no debe depender de un solo test: contrastar ADF con KPSS/PP/
    variance ratio + Hurst + half-life + FDR, y con mínimo de 500 observaciones.
    CONTEXTO NUEVO: el score v2 se calcula SÓLO con p_value_adf < 0,001, o sea
    SÓLO en la serie más estacionaria. Si el ADF es de baja potencia y además se
    aplica sobre una muestra corta, la rama del score no es una decisión, es ruido.
 P5  El criterio de salida del OOS debe ser explícito y escrito: con 4 días el score
    no está ni validado ni refutado. Se necesita N señales en M días distintos, con
    N y M definidos, y un test contra baseline aleatorio para cada patrón. Y ADEMÁS
    el grano debe ser (ciclo, activo), no (día): el bot pasó de ~25 a 4-8 corridas
    por día en el deploy y dentro de una misma tarde hay ciclos con 88,9% y con 0,0%.
 P6  La ventana operativa 04:00–16:00 (Render free, 12 h) se apoya en la evidencia de
    que las kill zones / patrones de volatilidad por sesión están replicados — pero
    los datos internos dicen 8:00 → HR 7,1% y 20:00 → HR 76,0%, lo que contradice
    parcialmente esa ventana.
 P7  Normalizar el score POR ACTIVO y arreglar la auditoría: `macro_audit_log` debe
    ser la fuente de verdad (tiene el cycle_id correcto), o C3.5 debe completar el
    cycle_id del snapshot (hoy queda "PRE_REGIME" ⇒ 0 de 914 señales matchean).
 P8  🆕 REDEFINICIÓN DE PRODUCTO: si el score no predice y el régimen sí (n=11), ¿qué
    debería ser MACRO2.1? ¿Un detector de régimen (que enciende cuando
    p_value_adf > umbral y se apaga en estacionario) en vez de un score? ¿Con qué
    criterio Go/No-Go numérico se decide, y qué resultado NEGATIVO aceptable
    obligaría a abandonar también esa hipótesis?

────────────────────────────────────────────────────────────────────────────
[BLOQUE 6 — PREGUNTAS CONCRETAS A RESPONDER (priorizadas)]

Q1  El 768 con score 0.0 EXACTO es histórico PRE-DEPLOY (data_quality OK, C4 registró
    todo 1:1) ⇒ no es un bug vigente. Pero: (a) ¿el rate limit actual sigue siendo un
    riesgo real dado que el bot pasó de ~25 a 4-8 corridas/día y ahora pide 12 activos
    × 4 TF = 48 candleSnapshot por ciclo ≈ 1344 de peso > 1200/min? (b) ¿hay alguna
    otra razón por la que `_calculate_ms_v2` devuelva 0.0 (las dos rutas silenciosas:
    score_desglose ausente, y excepción tragada con logger.debug)? (c) ¿qué evidencia
    distinguiría una de otra sin otro deploy?
Q2  Con la escala corregida, el score queda así: poc 0,5 + caja 1,5 + fvg 1,5 (sin
    volumen) · rs 0,5/2,0 (CVD CRUDO) · d 2,0 (test de volumen) · s_mtf 0,65 (dirección
    macro). Es decir: entre el 38% y el 65% es volumen absoluto, y sólo el 14% es
    dirección macro. ¿Tiene sentido un score así? ¿O eso ya es una respuesta a la
    pregunta del producto?
Q3  El gap-fill de FVG es indistinguible del azar (83,4% vs 83,5%) según una simulación
    random walk. ¿Qué queda del score si se eliminan FVG y caja como pesos principales?
    ¿Qué input con evidencia real podría ocupar ese peso en horizontes de 4 h–24 h en
    perps de Hyperliquid? Si no existe, ¿debe MACRO2.1 dejar de pretender predecir
    dirección?
Q4  ⭐⭐⭐ (LA MÁS IMPORTANTE) ATACÁ EL DISEÑO DEL EXPERIMENTO, NO LO REHAGAS.
    Ya corrimos el experimento (ver H2 en el Bloque 3) y su resultado es:
    NO-GO del score como predictor; el efecto es régimen/tiempo/grano de ciclo.
    Tu trabajo: (a) ¿el diseño de esos controles realmente separa "efecto del score"
    de "efecto del régimen", o hay un confound que no se controló? Enumerá los
    confounds que veas (selección de supervivientes, survivorship del filtro de
    emisión, granularidad, no-independencia de las señales del mismo ciclo,
    Regresión a la media por el filtro p_value_adf < 0,001, etc.).
    (b) ¿es un no-go LEGÍTIMO o estamos descartando una señal real por un diseño
    malo? (c) ¿el HR 81,8% con n=11 y 3 días es evidencia, o es ruido? ¿Con qué
    n mínimo lo aceptarías? (d) Si el no-go es legítimo, ¿cuál es el producto
    mínimo que SÍ tiene sentido con esta evidencia?
Q5  ¿Qué peso y qué horizonte debería tener el order flow (OFI/CVD/OBI) en un score
    de 4 h–24 h? Cite el límite de horizonte de la literatura y diga si hay excepción
    documentada para perps cripto.
Q6  El score real sólo existe cuando p_value_adf < 0,001. ¿Es una coincidencia
    estructural del pipeline o evidencia de que el score está condicionando a un
    subconjunto de régimen? ¿Qué pérdida de potencia provoca?
Q7  ⭐⭐⭐ (NUEVA, AHORA ES LA CENTRAL) Si el score es NO-GO y lo que tiene señal es
    el RÉGIMEN (p_value_adf alto ⇒ +1,087% de expectativa a 24h, n=11), ¿qué es
    MACRO2.1 a partir de ahí? Diseñá el producto mínimo (un detector de régimen que
    enciende/apaga, no un score), con: criterio Go/No-Go numérico, n y M mínimos,
    grano de evaluación (ciclo, no día), y el resultado NEGATIVO aceptable que
    obligaría a abandonar también esa hipótesis. Y decidí qué se hace con el score
    v2: ¿se borra, se congela, se recalibra con percentil por activo, o queda como
    segunda etapa dentro de un subconjunto?
Q8  ¿Qué falta en el diseño de la evidencia actual para que un resultado positivo
    sea creíble? Enumerá los sesgos concretos (más allá del tamaño de muestra) que
    siguen presentes: supervivencia, look-ahead, selección de activos, leakage
    entre el score y el sesgo, reuse de la misma muestra para decidir y para evaluar.
Q9  🆕 Si entre el 38% y el 65% del score es volumen absoluto del activo, ¿el score
    es siquiera una unidad? ¿Cómo debería normalizarse (por activo, por ATR, por
    volumen relativo, por rank cross-sectional)? ¿Hay precedente publicado de un
    "score de confluencia" que se normalice así, y qué problema tiene?
Q10 🆕 El término `d` (peso 2,0) es un test de volumen disfrazado de divergencia
     precio/flujo. ¿Debería eliminarse, re-escalarse, o reformularse como divergencia
     real (precio vs volumen relativo)? ¿Qué dice la literatura sobre divergencias
     CVD/precio como señal, y a qué horizonte?

────────────────────────────────────────────────────────────────────────────
[BLOQUE 7 — FORMATO DE SALIDA OBLIGATORIO]

1. Reporte con la estructura decimal del Paso 3.
2. Tabla por subdivisión: "Afirmación | Veredicto 🟢🟡🔴 | Tipo (E/G/D/E2/O) | Fuente | Corrección".
3. Sección final OBLIGATORIA: "VEREDICTO OPERATIVO", con exactamente:
   3.1  Las 3 objeciones más fuertes (tipo, mecanismo, evidencia, corrección)
   3.2  Qué queda de la P1–P6 sin cambios
   3.3  Qué se cae o se reescribe
   3.4  El experimento que hay que correr para decidir (con diseño, muestra mínima,
        métrica, y decisión Go/No-Go numérica)
   3.5  La lista de "no-go" del proyecto: qué affirmaciones del equipo NO deben
        quedar escritas en el gobierno del proyecto como hechos
``` 
