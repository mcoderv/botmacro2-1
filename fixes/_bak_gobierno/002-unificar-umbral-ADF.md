# ADR 002 — Unificar el umbral ADF
Fecha: 2026-10-23 | Estado: Propuesto

## Contexto
C3_5 tiene 0.05 hardcodeado. C3_MACRO lee 0.02 porque
_get_macro_param busca en la sección "macro" y la clave no está
→ cae al default. Resultado: el régimen y el score se contradicen.

## Decisión
Mover ADF_P_VALUE_THRESHOLD a CENTRAL_PARAMS["macro"] = 0.05
y forzar la sobrescritura en _migrar_v28 (no setdefault).

## Alternativas descartadas
- Cambiar solo "validation" → NO funciona, C3_MACRO no lee esa sección.
- Dejar 0.02 → conserva la contradicción.

## Consecuencia
Cambia la rama del conmutador ms_v2. Hay que re-medir HR/PF.

## Cómo verificar
python verificar.py --check-umbrales