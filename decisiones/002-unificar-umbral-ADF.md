# ADR 002 — Unificar el umbral ADF

**Estado:** APLICADO (2026-10-23, commit `5361b4f`)

> Umbral unificado en **0.05**, fuente unica `CENTRAL_PARAMS["macro"]`.
> Tambien se corrigio H-3 (`backups_v2.1` / `logs_v2.1`) y H-5
> (`_migrar_v28` ahora sobreescribe el JSON guardado).
> `verificar.py` -> 19 ok / 0 fallas / 1 aviso.
> **Pendiente:** medir el efecto real (ver `docs/PENDIENTES.md` 7).
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
