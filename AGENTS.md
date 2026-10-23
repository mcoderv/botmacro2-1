# AGENTS.md — MACRO2.1 (local)

## CONTACTO
Soy vibe coder. No sé código. Hablame en español, sin jerga.
NO edites archivos sin mi "ok, crealo" explícito.

## VERDAD ACTUAL
→ Leé ESTADO.md (dónde estoy) y decisiones/ (por qué). Son la fuente.
→ Para saber qué hace cada archivo: tabla abajo.

## REGLAS DURAS
1. Una celda por sesión. Un cambio por vez.
2. Si algo funciona, NO lo toques sin un ADR que lo justifique.
3. Import que falla → que se rompa. Prohibido degradar en silencio.
4. Un parámetro, UNA ruta de acceso. Si lo cambiás, cambiás su
   definición y verificás que TODOS los consumidores lo lean de ahí.
5. Tras cada cambio: corré `python verificar.py` y pegá la salida.
   Si falla, NO avances.
6. Nunca toques data/ ni la DB.

## MAPA (1 línea por archivo)
C0_INICIO   → setup, deps, dirs
C1_CONFIG   → rutas, DB, TZ, límites de portfolio
C1_5_PARAM  → CENTRAL_PARAMS (fuente de verdad) + presets
C2_BOVEDA   → SQLite: 18 tablas, backup, liveness
C2_5        → liquidez: ATR, wicks, fractales, OBI
C3_DQ       → calidad de datos (CLOSED/FORMING/STALE)
C3_MACRO    → cartógrafo v7.9.3, ms_v2, p_magnet
C3_5        → régimen ADF (TREND/RANGE/CHAOS)
C4          → registra señales, resuelve PnL 4/8/24h

## TABLA DE UMBRALES (fuente única de verdad)
| Parámetro | Valor | Quién lo lee | Dónde se define |
|---|---|---|---|
| ADF_P_VALUE_THRESHOLD | 0.05 | C3_5, C3_MACRO | CENTRAL_PARAMS["macro"] |
| STRONG_BIAS_THRESHOLD | 2 | C3_MACRO | CENTRAL_PARAMS["macro"] |
| BREAK_THRESHOLD_PCT | 0.05 | C4 | C4 (hardcoded) |
| RESOLUTION_WINDOWS_HOURS | 4,8,24 | C4 | C4 (hardcoded) |

## CONGELADO (no tocar sin ADR)
- data/vault_v2.1.db → 845 señales, 10 meses de validación
- C3_DATA_QUALITY.py → validado, 3 consumidores

## RITUAL GIT (obligatorio, cada sesión)

Yo NO sé usar git. Por eso, vos NUNCA me decís "guardá los cambios" ni
"revisá el estado". Me dáis el comando LITERAL, numerado, con el output
esperado.

FORMATO OBLIGATORIO de cada comando que me des:

    PASO N — [qué hace este paso en una línea]

        <comando literal, listo para copiar>

    ✅ Deberías ver: [output esperado, literal]
    ❌ Si falla: [qué significa + qué copio yo para que me ayudes]
    📂 Desde: [carpeta exacta desde donde corro]

REGLAS:
- UN paso a la vez. No me des 3 comandos juntos.
- SIEMPRE con output esperado. Yo no sé leer errores, necesito ver
  si salió bien.
- SIEMPRE terminá preguntándome: "¿lo corriste? pegá la salida".
- Si algo falló, NO me des el siguiente paso hasta ver la salida.
- NUNCA me digas "investiguá en git" ni "hacé un diff". Yo no sé.

ORDEN DE CADA SESIÓN (si me pides trabajar en código):

  1. INICIO:
     → Ejecutá: python git/estado.py
     → Decime en una línea: dónde estamos y cuál es el próximo paso.

  2. ANTES de pegarme código nuevo (checkpoint):
     → Ejecutá: python git/guardar.py "antes de: <qué me pediste>"
     → Avisame si salió "No hay cambios" (significa que ya está guardado).

  3. DESPUÉS de que yo pegue código (ANTES de ejecutar nada):
     → Ejecutá: python git/revisar_archivo.py <archivo>
     → Si da ❌ SINTAXIS ROTA → el paste quedó cortado. Decime
       "repetí el archivo desde la línea X" y NO avances.

  4. DESPUÉS de que todo funcione:
     → Ejecutá: python git/guardar.py "<qué cambió, en una frase>"

  5. SI ALGO SE ROMPIÓ:
     → Ejecutá: python git/deshacer.py
     → (me pide confirmación escribiendo SI)

INVESTIGACIÓN Y RESPUESTAS:
- Cuando me des una respuesta de investigación que valga guardar,
  pedime guardarla en notas/AAAA-MM-DD-titulo.md
- NUNCA tires una respuesta larga solo en el chat. Ofrecé el archivo.

DESCARGAS:
- Cuando bajes un archivo, que caiga en tmp/ y que lo verifique
  antes de moverlo a su lugar.