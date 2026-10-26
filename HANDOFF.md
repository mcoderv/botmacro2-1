# HANDOFF — MACRO2.1

> Estado al cierre de la sesión. La próxima IA debe leer:
> **`docs/RELEVO_IA.md`** (brief completo) → `AGENTS.md` → este archivo → `docs/PENDIENTES.md`.

```
Sesión     : 5  (cierre 2026-10-26)
Rama       : main
Último commit : 31e6cd3  (H-18 / H-10 / H-20 + ADR 007)
Pendiente de commit : gobierno H-22 (este paquete)
Producción  : botmacro — CONGELADA (DATA FREEZE), no tocar
Desarrollo  : botmacro2-1 — este repo
```

---

## ✅ Lo que se hizo en esta sesión

1. **H-9 cerrado CON EVIDENCIA** (no con intuición):
   `macro_score_v2` **no tiene poder predictivo demostrado** (NO-GO).
   ρ(ms2, pnl24) = +0,119 dentro de RANGE. El score no separa nada.
2. **5 scripts de análisis** corriendo contra la DB real:
   `diagnostico_h9.py` · `descomponer_score_v2.py` ·
   `poder_predictivo_score_v2.py` · `reconstruir_score_v2.py` ·
   `reconciliar_score_cero.py` (v2, 11 secciones).
3. **Corrección de semántica**: `p_value_adf < 0.05` = **ESTACIONARIO**, no momentum.
4. **768 de 914 con score 0.0 = PRE-DEPLOY** (13/10-19/10), **NO es un bug vigente**.
   146 reales = 19/10-23/10.
5. **El sesgo multi-TF SÍ funciona** (N/A sólo 5,6% / 5,8% / 0%).
6. **La zona horaria resuelta**: la DB guarda **hora local Caracas (UTC−4)**,
   confirmado con 3 pares epoch↔fecha. ⇒ El análisis por hora es en Caracas.
7. **Segunda opinión** recibida y revisada. Sus 3 errores corregidos (E1/E2/E3).
8. **H-22 (nuevo)**: el test de régimen **NO corrió en el 71%** de las señales
   (648 de 914 con `p=1.0` = el default del `except`) ⇒ la muestra está
   **seleccionada por éxito del test** ⇒ el OOS **tiene que ser prospectivo**.
9. **H-22 (nuevo)**: `rs` es un **ordinal de `rvd`**, no el CVD crudo ⇒
   ⛔ `d` NO es degenerado (contra la segunda opinión) y ⛔ el score NO está
   contaminado por escala.
10. **H-22 (nuevo)**: el filtro real de emisión es **`rvd` > 0,3** ⇒ la
    hipótesis de eficacia cabe en un solo número.
11. **Plan de reorientación** escrito: Track A (eficiencia) / B (eficacia,
    congelada) / C (protocolo OOS), con lista negativa de 8 afirmaciones.

---

## 📌 Lo que la próxima sesión tiene que hacer

**PRIMERO (manual, el usuario):** subir el backup de la DB a Drive.
**PRIMERO (código):** **A1 — rate limit.**

```cmd
python fixes\actualizar_gobierno_h22.py --aplicar
python verificar.py
python git\guardar.py "gobierno H-22: H-9 cerrado, H-22 (ADF falla 71%), ADR 008-012, RELEVO_IA"
git push origin main
```

**Después, en este orden:** A2 (`cycle_id`) → A3 (`data_quality`) →
A0 (test de régimen) → A4/A5/A6 → A9 → A7 (ventana 19 h) →
**H-21** → **H-18** → **H-13**.

**Track C (protocolo OOS) se escribe ANTES de T₀** (ADR 012).
**T₀ = fecha del deploy con el Track A listo.**

---

## ⚠️ Trampas documentadas (no repetirlas)

- **CMD.exe únicamente.** Sin PowerShell, sin `curl`/`wget` unix, sin `&&`, sin `;`.
- **`more` y `type` CUELGAN la consola** (el usuario tuvo que pegarle Ctrl+C y
  se le reinició el historial). Para volcar un archivo: `findstr /n "patron" archivo`
  o redirigir a un `.txt` y pegar ese.
- **UTF-8 en consola china/ANSI sale como mojibake** (`—` → `ÔÇö`).
  ⇒ En parches, anclar con **cadenas ASCII puras**.
- En Python, un `''` sin escaping dentro de un string SQL rompe todo
  (`no such column: senales_valADAS`, `no such column: ANTES`). Usar `?`.
- `findstr` con acentos no funciona en la consola ⇒ buscar por palabras ASCII.
- Los scripts de git **siempre en Python** (Windows).
- `git rm --cached <file>` para sacarlo del índice sin borrarlo del disco
  (se usó con `timing_real.json`).
- `verificar.py` es el **gate** antes de commitear. Si falla, no se avanza.

---

## 🎯 La pregunta abierta que define el proyecto

> **"¿`rvd` > 0,3 ⇒ el LONG rinde, y el régimen lo modula?"**

No "¿el score v2 predice?" — esa ya está contestada (NO-GO).
El OOS es **prospectivo**, la unidad es el **CICLO**, N y M se escriben antes,
el benchmark es aleatorio con el mismo perfil, BH-FDR + **t > 3,0**,
y si la expectativa neta ≤ 0 ⇒ **clausura definitiva**.

---

## 📂 Archivos clave

| Archivo | Qué es |
|---|---|
| `docs/RELEVO_IA.md` | ⭐ **El brief completo para esta u otra IA** |
| `AGENTS.md` | Reglas de la casa + §8 fórmula real + §10 lista negativa + §11 OOS |
| `ESTADO.md` | Dónde estoy hoy (se reescribe, no se acumula) |
| `HANDOFF.md` | Este archivo (cierre de sesión) |
| `docs/PENDIENTES.md` | Tracking oficial de lo que falta |
| `docs/INFORME_MACRO2.1.md` | Spec original — **NO editar** |
| `decisiones/00X-*.md` | Los 8 ADRs (por qué se decidió cada cosa) |
| `verificar.py` | Gate de 19 checks |
| `git/guardar.py` · `estado.py` · `deshacer.py` | Kit de git |
| `analisis/*.py` | Los 5 scripts de diagnóstico de H-9 + timing + H-10/H-18 |
| `fixes/*.py` | Parches de una vez (se archivan a `docs/local/`) |