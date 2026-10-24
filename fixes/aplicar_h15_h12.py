# -*- coding: utf-8 -*-
"""
aplicar_h15_h12.py  -  MACRO2.1
================================
Correccion de DOS problemas ya diagnosticados al 100%:

  H-15  La "curva de capital" NO es una curva de capital.
        `np.cumsum(pnls)` es una suma aritmetica de porcentajes, no capital
        compuesto. Con ~900 senales el "Max Drawdown" puede superar 100%
        (se observo 270.88% en report_validator.py) sin que exista tal perdida.
        Afecta a  report_validator.py  Y  C4_SENIAL_VALIDATOR.py
        -> Se reemplaza por capital compuesto (cumprod) y DD relativo al pico.
        -> Con compounding el Max DD SIEMPRE cae entre 0% y 100%.

  H-12  Hay DOS (y en realidad TRES) umbrales ADF huérfanos, y el valor que
        usa el motor puede caer silenciosamente a 0.02:
          (a) C1_5 literal  CENTRAL_PARAMS["validation"]["ADF_P_VALUE_THRESHOLD"] = 0.02
          (b) C1_5 defaults val_defaults["ADF_P_VALUE_THRESHOLD"] = 0.02
              -> se reinyecta en CADA corrida (el bloque `validation` existe en
                el JSON pero SIN esa key, entonces `if k not in val_sec` se
                cumple y mete 0.02 en memoria).
          (c) C3_MACRO      float(_get_macro_param("ADF_P_VALUE_THRESHOLD", 0.02))
              -> fallback 0.02 si la key no está en CENTRAL_PARAMS["macro"].
        La fuente UNICA real es  CENTRAL_PARAMS["macro"]["ADF_P_VALUE_THRESHOLD"] = 0.05
        (ADR 002). El JSON ya la tiene, pero el LITERAL del código NO -> si el
        JSON se regenera o no es compatible, C3_MACRO vuelve a 0.02 en silencio.
        -> Se agrega 0.05 al literal de `macro`, se borra de `validation` y de
          `val_defaults`, y el banner de C1_5 pasa a leer la fuente unica.

  H-16  (MEDIDO, NO APLICADO)  "ganancia" significa dos cosas distintas:
        hit_rate usa el umbral de break-even (0.05%) pero profit_factor y
        avg_win usan `p > 0`. Este script MIDE el impacto de unificarlo con
        el umbral, con datos reales de la DB, y NO cambia la metrica.
        La decision queda documentada en el ADR 004.

Archivos tocados:
  C4_SENIAL_VALIDATOR.py    (H-15)
  report_validator.py       (H-15)
  C1_5_PARAM_local.py       (H-12, 3 parches)
  C3_MACRO_local.py         (H-12, fallback 0.02 -> 0.05)   [opcional]
  decisiones/004-curva-de-capital-compuesta.md              (nuevo, ADR 004)

Uso (desde la raiz del proyecto):
  python fixes\\aplicar_h15_h12.py --simular     (default: no escribe nada)
  python fixes\\aplicar_h15_h12.py --aplicar     (escribe, con .bak)
  python fixes\\aplicar_h15_h12.py --deshacer    (restaura desde .bak)

NUNCA toca la DB. NUNCA toca produccion (botmacro).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

# ------------------------------------------------------------------------------
# RAÍZ DEL PROYECTO
# ------------------------------------------------------------------------------
def _buscar_raiz() -> Path:
    p = Path(__file__).resolve().parent
    for cand in [p, *p.parents]:
        if (cand / "data").is_dir() and (cand / "config").is_dir():
            return cand
    return p.parent


RAIZ = _buscar_raiz()
DB_PATH = RAIZ / "data" / "vault_v2.1.db"
BREAKEVEN = 0.05  # BREAKEVEN_THRESHOLD_PCT de C4_SENIAL_VALIDATOR.py

C = {
    "r": "\033[0m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m",
    "R": "\033[31m", "c": "\033[36m", "m": "\033[35m",
}



def _configurar_consola() -> None:
    """Evita UnicodeEncodeError en la consola de Windows (cp1252/cp437).
    Los caracteres no representables se sustituyen por '?' en vez de romper."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def p(t=""):
    """Imprime sanitizando a la codificacion de la consola (Windows cp1252/cp437).
    Caracteres no representables -> '?'. Nunca debe lanzar UnicodeEncodeError."""
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(t.encode(enc, errors="replace").decode(enc, errors="replace"))
    except Exception:
        print(t)


def hdr(t):
    p(f"\n{C['b']}{'='*74}{C['r']}")
    p(f"{C['b']}  {t}{C['r']}")
    p(f"{C['b']}{'='*74}{C['r']}")


# ------------------------------------------------------------------------------
# LECTURA / ESCRITURA SEGUROS (preserva bytes no-UTF8 con surrogateescape)
# ------------------------------------------------------------------------------
def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8", errors="surrogateescape")


def escribir(ruta: Path, texto: str) -> None:
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(texto)


# ------------------------------------------------------------------------------
# MOTOR DE PARCHES POR BLOQUE
#   Tolera cualquier variante del archivo: no exige el texto EXACTO, busca la
#   clave dentro del bloque dict y la quita / la normaliza / la inserta.
# ------------------------------------------------------------------------------
def _ind(linea: str) -> int:
    return len(linea) - len(linea.lstrip())


def _encontrar_bloque(lineas, apertura: str):
    """Primer bloque dict que abre con `apertura` (comparado con .strip()).
    Prefiere el de indentacion 4 (literal CENTRAL_PARAMS de nivel superior).
    Devuelve (ini, fin) o (None, None)."""
    cands = []
    for i, l in enumerate(lineas):
        if l.strip() != apertura:
            continue
        nivel = 0
        fin = None
        for j in range(i, len(lineas)):
            nivel += lineas[j].count("{") - lineas[j].count("}")
            if nivel <= 0:
                fin = j
                break
        if fin is None:
            continue
        cands.append((i, fin))
    if not cands:
        return None, None
    for (i, f) in cands:
        if _ind(lineas[i]) == 4:
            return i, f
    return cands[0]


def _aplicar_op_bloque(lineas, op):
    """set / remove de una clave dentro de un bloque dict.
    Devuelve (lineas, mensaje_legible)."""
    ini, fin = _encontrar_bloque(lineas, op["apertura"])
    if ini is None:
        return lineas, f"bloque no encontrado: {op['apertura']}"
    clave = op["clave"]
    modo = op["modo"]
    comentario = op.get("comentario") or []

    if modo == "remove":
        idxs = [k for k in range(ini, fin + 1) if clave in lineas[k]]
        if not idxs:
            return lineas, "la clave no esta en el bloque (ya fixeado)"
        for k in reversed(idxs):
            del lineas[k]
        ini2, fin2 = _encontrar_bloque(lineas, op["apertura"])
        if ini2 is not None:
            for k in range(fin2 - 1, ini2 - 1, -1):
                s = lineas[k].strip()
                if not s or s.startswith("#"):
                    continue
                if s.endswith(","):
                    lineas[k] = lineas[k].rstrip()[:-1]
                break
        if comentario:
            ind = _ind(lineas[ini])
            for c in reversed(comentario):
                lineas.insert(ini, " " * ind + c)
        return lineas, f"clave eliminada ({len(idxs)} linea/s)"

    if modo == "set":
        idxs = [k for k in range(ini, fin + 1) if clave in lineas[k]]
        if idxs:
            k = idxs[0]
            nuevo = re.sub(r'("' + re.escape(clave) + r'"\s*:\s*)[0-9.]+',
                           r'\g<1>' + op["valor"], lineas[k])
            if not nuevo.rstrip().endswith(","):
                nuevo = nuevo.rstrip() + ","
            lineas[k] = nuevo
            for extra in reversed(idxs[1:]):
                del lineas[extra]
            return lineas, f"clave normalizada a {op['valor']}"
        ind = _ind(lineas[ini + 1]) if (ini + 1) <= fin else _ind(lineas[ini]) + 4
        for c in reversed(comentario):
            lineas.insert(ini + 1, " " * ind + c)
        lineas.insert(ini + 1 + len(comentario),
                      " " * ind + f'"{clave}": {op["valor"]},')
        return lineas, f"clave insertada = {op['valor']}"

    return lineas, f"modo desconocido: {modo}"


# ------------------------------------------------------------------------------
# LOS PARCHES
#   critico=True  -> si no matchea, se ABORTA todo (atomicidad)
#   critico=False -> si no matchea, se reporta y se sigue (puede estar ya fixeado)
# ------------------------------------------------------------------------------
PATCHES = [
    # -- H-15 * C4 ------------------------------------------------------------
    {
        "archivo": "C4_SENIAL_VALIDATOR.py",
        "titulo": "H-15 * Max Drawdown sobre capital compuesto (C4._calculate_metrics)",
        "critico": True,
        "viejo": """                cumulative = np.cumsum(pnls)
                peak = np.maximum.accumulate(cumulative)
                drawdown = peak - cumulative
                max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0
""",
        "nuevo": """                # ── H-15: curva de capital COMPUESTA (no suma aritmetica de %) --
                # np.cumsum(pnls) NO es una curva de capital: con ~900 senales el
                # "drawdown" puede superar 100% (se observo 270.88% en
                # report_validator.py) sin que exista tal perdida.
                # Con capital compuesto el Max DD SIEMPRE cae entre 0% y 100%.
                _pnl_arr = np.array(pnls, dtype=float)
                _equity = np.cumprod(1.0 + _pnl_arr / 100.0)
                _peak = np.maximum.accumulate(_equity)
                max_dd = float(np.max((1.0 - _equity / _peak) * 100.0)) if len(_equity) > 0 else 0.0
""",
    },
    # -- H-15 * report_validator ----------------------------------------------
    {
        "archivo": "report_validator.py",
        "titulo": "H-15 * Equity curve compuesta + Max DD relativo al pico",
        "critico": True,
        "viejo": """    # Equity Curve y Max Drawdown
    equity_curve = np.cumsum(pnls).tolist()
    if equity_curve:
        peak = np.maximum.accumulate(equity_curve)
        drawdown = peak - np.array(equity_curve)
        max_drawdown = float(np.max(drawdown))
    else:
        max_drawdown = 0.0
""",
        "nuevo": """    # ── H-15: curva de capital COMPUESTA (base 100) ──
    # np.cumsum(pnls) NO es una curva de capital: es una suma aritmetica de
    # porcentajes. Con ~900 senales el "drawdown" puede superar 100% (se vio
    # 270.88%) sin que exista tal perdida. Con compounding el Max DD siempre
    # cae entre 0% y 100%.  OJO: la curva ahora es un INDICE DE CAPITAL base
    # 100 -> revisar la etiqueta del eje Y del grafico (se reporta al final).
    if pnls:
        _pnl_arr = np.array(pnls, dtype=float)
        _equity = np.cumprod(1.0 + _pnl_arr / 100.0) * 100.0   # base 100
        _peak = np.maximum.accumulate(_equity)
        max_drawdown = float(np.max((1.0 - _equity / _peak) * 100.0))
        equity_curve = _equity.tolist()
    else:
        equity_curve = []
        max_drawdown = 0.0
""",
    },
    # -- H-12 * C1_5 * literal macro (AGREGA la fuente unica) -----------------
    {
        "archivo": "C1_5_PARAM_local.py",
        "titulo": "H-12 * literal: macro gana ADF_P_VALUE_THRESHOLD = 0.05 (fuente unica)",
        "critico": True,
        "op": {
            "apertura": '"macro": {',
            "clave": "ADF_P_VALUE_THRESHOLD",
            "valor": "0.05",
            "modo": "set",
            "comentario": [
                "# H-12: FUENTE UNICA del umbral ADF del sistema (ADR 002).",
                "# Debe coincidir con config/CONSOLIDADO/central_params.json ->",
                "# macro.ADF_P_VALUE_THRESHOLD. Si divergen o falta, C3_MACRO cae en",
                "# silencio a su fallback y el motor de regimen usa otro criterio.",
            ],
        },
    },
    # -- H-12 * C1_5 * literal validation (QUITA el 0.02) -------------------
    {
        "archivo": "C1_5_PARAM_local.py",
        "titulo": "H-12 * literal: se quita ADF_P_VALUE_THRESHOLD de validation",
        "critico": True,
        "op": {
            "apertura": '"validation": {',
            "clave": "ADF_P_VALUE_THRESHOLD",
            "modo": "remove",
            "comentario": [
                "# H-12: el umbral ADF NO vive aqui. La fuente unica es",
                '#   CENTRAL_PARAMS["macro"]["ADF_P_VALUE_THRESHOLD"] (= 0.05, ADR 002).',
            ],
        },
    },
    # -- H-12 * C1_5 * val_defaults (QUITA el 0.02 latente) ------------------
    {
        "archivo": "C1_5_PARAM_local.py",
        "titulo": "H-12 * defaults: se quita el 0.02 que se reinyectaba cada corrida",
        "critico": True,
        "op": {
            "apertura": "val_defaults: Dict[str, Any] = {",
            "clave": "ADF_P_VALUE_THRESHOLD",
            "modo": "remove",
            "comentario": [
                "# H-12: NO reintroducir ADF_P_VALUE_THRESHOLD aqui.",
                "# El UNICO umbral ADF del sistema es",
                '#   CENTRAL_PARAMS["macro"]["ADF_P_VALUE_THRESHOLD"]  (= 0.05, ADR 002)',
                "# que leen C3_MACRO y C3_5.  Mantener un segundo umbral aqui lo deja",
                "# latente (el `if k not in val_sec` lo reinyecta en cada corrida) y hace",
                "# que el banner del modulo muestre un valor distinto al del motor real.",
            ],
        },
    },
    # -- H-12 * C1_5 * banner (lee la fuente unica) --------------------------
    {
        "archivo": "C1_5_PARAM_local.py",
        "titulo": "H-12 * el banner lee el umbral ADF de la fuente unica",
        "critico": True,
        "viejo": """_all_assets = CENTRAL_PARAMS.get("macro", {}).get("ALL_ASSETS", [])
""",
        "nuevo": """_all_assets = CENTRAL_PARAMS.get("macro", {}).get("ALL_ASSETS", [])
# H-12: fuente UNICA del umbral ADF (ADR 002). Antes se leia de
# `validation.ADF_P_VALUE_THRESHOLD`, que no existe en el JSON -> el banner
# mostraba None mientras el motor real usaba 0.05.
_macro_adf_thr = CENTRAL_PARAMS.get("macro", {}).get("ADF_P_VALUE_THRESHOLD", "N/A")
""",
    },
    {
        "archivo": "C1_5_PARAM_local.py",
        "titulo": "H-12 * banner ADF_THR apunta a la fuente unica",
        "critico": True,
        "viejo": """    f"ADF_THR: {_val.get('ADF_P_VALUE_THRESHOLD')} | "
""",
        "nuevo": """    f"ADF_THR: {_macro_adf_thr} | "
""",
    },
    # -- H-12 * C3_MACRO * fallback 0.02 -> 0.05 (opcional) -----------------
    {
        "archivo": "C3_MACRO_local.py",
        "titulo": "H-12 * C3_MACRO: fallback del umbral ADF 0.02 -> 0.05",
        "critico": False,
        "viejo": """_get_macro_param("ADF_P_VALUE_THRESHOLD", 0.02)""",
        "nuevo": """_get_macro_param("ADF_P_VALUE_THRESHOLD", 0.05)""",
    },
]


# ------------------------------------------------------------------------------
# ADR 004
# ------------------------------------------------------------------------------
ADR_004 = """# ADR 004 * Curva de capital compuesta para el Max Drawdown (H-15)

- **Estado:** ACEPTADO
- **Fecha:** 2026-10-24
- **Alcance:** `report_validator.py`, `C4_SENIAL_VALIDATOR.py`
- **Problema:** H-15 (y H-16, medido pero NO aplicado - ver abajo)
- **Fuera de alcance pero en el mismo script:** H-12 (fuente única del umbral
  ADF), que es la implementación de ADR 002 y no requiere un ADR propio.

## Contexto

`report_validator.py` y `C4_SENIAL_VALIDATOR._calculate_metrics()` construían la
curva de capital así:

```python
equity_curve = np.cumsum(pnls)
peak        = np.maximum.accumulate(equity_curve)
drawdown    = peak - equity_curve
max_dd      = float(np.max(drawdown))
```

`np.cumsum(pnls)` es una **suma aritmética de porcentajes**, no una curva de
capital. La estructura pico-valle es correcta; **la curva base es incorrecta**.

Consecuencia medida: con ~900 señales, el "Max Drawdown" reportado fue de
**270.88%**, un valor imposible para una pérdida real. Lo que ese número
representa es *cuánto se movió la suma acumulada de ~900 porcentajes*, no una
pérdida de capital.

**Lo que NO se ve afectado** (verificado en el código):
- `hit_rate` -> se calcula sobre PnL individuales
- `profit_factor` -> `sum(p>0) / abs(sum(p<0))` sobre PnL individuales
- `avg_pnl`, `max_win`, `max_loss`

**⇒ H-15 es un bug de *reporting*, no de métrica de señal.** Los HR/PF del
proyecto no se ven afectados.

## Decisión

La curva de capital se construye **compuesta**, indexada a base 100:

```python
_equity = np.cumprod(1.0 + np.array(pnls, dtype=float) / 100.0) * 100.0
_peak   = np.maximum.accumulate(_equity)
max_dd  = float(np.max((1.0 - _equity / _peak) * 100.0))
```

**Propiedad garantizada:** el Max Drawdown así calculado **siempre cae entre
0% y 100%**. Si alguna vez se vuelve a ver un Max DD > 100%, es un bug.

### Consecuencias aceptadas

1. **El gráfico de equity del reporte HTML cambia de semántica**: de "% PnL
   acumulado" a "índice de capital (base 100)". La etiqueta del eje Y debe
   actualizarse. El script reporta las líneas afectadas.
2. **Los valores históricos de `senales_metricas.max_drawdown_pct` quedan
   obsoletos**: fueron calculados con la suma aritmética. Se recalculan en la
   próxima corrida de C4. Hasta entonces, ese campo no debe usarse.
3. `report_validator.py` deja de exponer un "Max Drawdown" comparable con
   históricos previos.

## H-16 * MEDIDO, NO APLICADO (decisión diferida)

Se detectó que **"ganancia" significa dos cosas distintas** en el código:

| Métrica | Definición actual |
|---|---|
| `hit_rate`, `wins`, `losses` | `p > +0.05%` / `p < -0.05%` (umbral de break-even) |
| `profit_factor` (C4), `avg_win` / `expectancy` (report_validator) | `p > 0` |

Es decir: una señal con PnL `+0.03%` cuenta como **no-hit** en `hit_rate` pero
entra en `avg_win`, y el `expectancy` multiplica `win_rate` (definición A) por
`avg_win` (definición B). **Inconsistencia real.**

Unificar en el umbral de break-even cambia los PF históricos citados en los
documentos del proyecto. **No se aplica a ciegas:** el script
`aplicar_h15_h12.py` mide con datos reales de la DB la diferencia entre ambas
definiciones (cuántas señales caen en la banda de break-even y cuánto se mueve
el PF) y deja la decisión documentada aquí.

**Pendiente de decisión explícita** con esas cifras en la mano.

## H-12 * Implementación de ADR 002 (fuente única del umbral ADF)

Se приложен en el mismo script porque son la **misma decisión ya tomada**
(ADR 002: "fuente única 0.05"). Eran **tres** umbrales huérfanos:

| # | Dónde | Valor | Por qué era un problema |
|---|---|---|---|
| (a) | `C1_5` literal `validation` | 0.02 | Segundo umbral ADF vivo |
| (b) | `C1_5` `val_defaults` | 0.02 | `if k not in val_sec` -> se reinyectaba **en cada corrida** (el bloque `validation` existe en el JSON pero sin esa key) |
| (c) | `C3_MACRO` fallback | 0.02 | Si la key falta en `CENTRAL_PARAMS["macro"]`, el motor cae **en silencio** a 0.02 |

**El JSON sí tenía 0.05 en `macro`** (ADR 002 aplicado), pero el **literal del
código no** -> si el JSON se regenera o no es compatible por versión, el motor
volvía a 0.02 sin avisar. Por eso el fix **agrega** `ADF_P_VALUE_THRESHOLD:
0.05` al literal de `macro` y **quita** el 0.02 de los otros dos sitios.

## Impacto en el resto del proyecto

- El `verificar.py` no cambia en este ADR (la lista de ADRs se actualiza en el
  paso de gobierno).
- **No toca producción** (`botmacro`): el DATA FREEZE sigue vigente. Este ADR
  aplica únicamente al clon local `MACRO2.1`.
- Los ADR 001 (umbral k×σ) y 002 (fuente única ADF) no cambian.
"""


# ------------------------------------------------------------------------------
# IMPACTO MEDIDO EN LA DB (solo lectura)
# ------------------------------------------------------------------------------
def _max_dd_cumsum(pnls):
    """Metodo viejo (buggy): suma aritmetica de porcentajes."""
    if not pnls:
        return 0.0
    acc = 0.0
    peak = 0.0
    worst = 0.0
    for x in pnls:
        acc += x
        if acc > peak:
            peak = acc
        d = peak - acc
        if d > worst:
            worst = d
    return worst


def _max_dd_compuesto(pnls):
    """Metodo nuevo (ADR 004): capital compuesto."""
    if not pnls:
        return 0.0
    eq = 1.0
    peak = 1.0
    worst = 0.0
    for x in pnls:
        eq *= (1.0 + x / 100.0)
        if eq > peak:
            peak = eq
        d = (1.0 - eq / peak) * 100.0
        if d > worst:
            worst = d
    return worst


def medir_db():
    """Devuelve (filas, existe_db). No escribe nada."""
    filas = []
    if not DB_PATH.exists():
        return filas, False
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    except sqlite3.Error:
        return filas, False
    try:
        for v in (4, 8, 24):
            try:
                rows = con.execute(
                    f"SELECT pnl_pct_{v}h, hit_{v}h FROM senales_validadas "
                    f"WHERE resuelto_{v}h = 1"
                ).fetchall()
            except sqlite3.Error:
                continue
            pnls = [r[0] for r in rows if r[0] is not None]
            if not pnls:
                continue
            n_be = sum(1 for x in pnls if abs(x) <= BREAKEVEN)
            pf_raw = sum(x for x in pnls if x > 0) / max(
                abs(sum(x for x in pnls if x < 0)), 1e-12
            )
            gp_be = sum(x for x in pnls if x > BREAKEVEN)
            gl_be = abs(sum(x for x in pnls if x < -BREAKEVEN))
            pf_be = gp_be / gl_be if gl_be > 0 else (float("inf") if gp_be > 0 else 0.0)
            filas.append({
                "ventana": f"{v}h",
                "n": len(pnls),
                "n_be": n_be,
                "pct_be": 100.0 * n_be / len(pnls),
                "pf_raw": pf_raw,
                "pf_be": pf_be,
                "dd_viejo": _max_dd_cumsum(pnls),
                "dd_nuevo": _max_dd_compuesto(pnls),
            })
    finally:
        con.close()
    return filas, True


# ------------------------------------------------------------------------------
# APLICACIÓN
# ------------------------------------------------------------------------------
def _self_test():
    """(ok, detalle). Verifica la invariante 0..100 y el caso que reproduce
    el bug original (>100% con el metodo viejo)."""
    caso1 = [10.0, -5.0, -3.0, 8.0, -20.0, 2.0]
    dd1 = _max_dd_compuesto(caso1)
    ok1 = 0.0 <= dd1 <= 100.0
    # Serie larga: el metodo viejo supera 100%, el compuesto no.
    caso2 = [0.5] * 300 + [-2.0] * 100
    dd2v = _max_dd_cumsum(caso2)
    dd2n = _max_dd_compuesto(caso2)
    ok2 = (dd2v > 100.0) and (0.0 <= dd2n <= 100.0)
    return ok1, ok2, dd1, dd2v, dd2n


def aplicar(simular: bool) -> int:
    hdr("1 * IMPACTO MEDIDO EN LA DB (solo lectura) - H-15 y H-16")
    filas, existe = medir_db()
    if not existe:
        p(f"  {C['y']}  No se encontro {DB_PATH}{C['r']}")
        p(f"  {C['y']}  Se aplicaran los parches igual, pero sin cifras de impacto.{C['r']}")
    else:
        p(f"  {C['c']}Base:{C['r']} {DB_PATH}")
        p("")
        p(f"  {C['b']}{'ventana':<8}{'n':>6}{'n_be':>8}{'%_be':>8}"
          f"{'DD_viejo':>12}{'DD_nuevo':>12}{'PF(>0)':>10}{'PF(>be)':>10}")
        p(f"  {C['b']}{'-'*74}{C['r']}")
        for f_ in filas:
            p(f"  {f_['ventana']:<8}{f_['n']:>6}{f_['n_be']:>8}{f_['pct_be']:>7.1f}%"
              f"{f_['dd_viejo']:>11.2f}%{f_['dd_nuevo']:>11.2f}%"
              f"{f_['pf_raw']:>10.3f}{f_['pf_be']:>10.3f}")
        p("")
        p(f"  {C['b']}H-15{C['r']}  DD viejo > 100% = suma aritmetica, no perdida real.")
        p(f"  {C['b']}H-16{C['r']}  'n_be' = senales en la banda de break-even "
          f"(|PnL| <= {BREAKEVEN}%).")
        p(f"       PF(>0) vs PF(>be) = impacto de unificar la definicion de ganancia.")
        p(f"       {C['y']}NO se aplica H-16 en este script: queda para decision "
          f"documentada en el ADR 004.{C['r']}")

    # -- Agrupar parches por archivo (un .bak por archivo, NO por parche) --
    hdr("2 * PARCHES")
    por_archivo: dict[str, list] = {}
    for patch in PATCHES:
        por_archivo.setdefault(patch["archivo"], []).append(patch)

    cambios = []      # (ruta, texto_original, texto_final)
    fallidos = []     # criticos
    omitidos = []     # opcionales no encontrados
    for archivo, ps in por_archivo.items():
        ruta = RAIZ / archivo
        if not ruta.exists():
            for patch in ps:
                msg = f"archivo no encontrado: {archivo}"
                (fallidos if patch["critico"] else omitidos).append((patch, msg))
                p(f"  {C['R']}XX{C['r']} {patch['titulo'][:64]}")
                p(f"      {C['R']}{msg}{C['r']}")
            continue
        texto_orig = leer(ruta)
        texto = texto_orig
        fallo = None
        for patch in ps:
            if "op" in patch:
                lineas = texto.split("\n")
                lineas, msg = _aplicar_op_bloque(lineas, patch["op"])
                if msg.startswith("bloque no encontrado"):
                    (fallidos if patch["critico"] else omitidos).append((patch, msg))
                    p(f"  {C['R'] if patch['critico'] else C['y']}"
                      f"{'XX' if patch['critico'] else '*'}{C['r']} {patch['titulo'][:64]}")
                    p(f"      {C['R'] if patch['critico'] else C['y']}{msg}{C['r']}")
                    if patch["critico"]:
                        fallo = patch
                    continue
                texto = "\n".join(lineas)
                p(f"  {C['g']}OK{C['r']} {patch['titulo'][:64]}")
                p(f"      {C['c']}{archivo}{C['r']}  {msg}")
                continue
            n = texto.count(patch["viejo"])
            if n != 1:
                msg = f"patron encontrado {n} veces (se requiere exactamente 1)"
                (fallidos if patch["critico"] else omitidos).append((patch, msg))
                p(f"  {C['R'] if patch['critico'] else C['y']}"
                  f"{'XX' if patch['critico'] else '*'}{C['r']} {patch['titulo'][:64]}")
                p(f"      {C['R'] if patch['critico'] else C['y']}{msg}{C['r']}")
                if patch["critico"]:
                    fallo = patch
                continue
            texto = texto.replace(patch["viejo"], patch["nuevo"])
            p(f"  {C['g']}OK{C['r']} {patch['titulo'][:64]}")
            p(f"      {C['c']}{archivo}{C['r']}")
        if fallo is not None:
            continue
        if texto != texto_orig:
            cambios.append((ruta, texto_orig, texto))

    if fallidos:
        hdr("ABORTADO - no se escribio NADA")
        p(f"  {C['R']}{len(fallidos)} parche(s) criticos no aplicaron.{C['r']} Cada patron")
        p("  debe aparecer EXACTAMENTE una vez. Pega este informe a la IA.")
        p("")
        for patch, why in fallidos:
            p(f"  {C['R']}XX{C['r']} {patch['archivo']} - {patch['titulo']}")
            p(f"      {C['R']}{why}{C['r']}")
            ruta = RAIZ / patch["archivo"]
            if ruta.exists() and "viejo" in patch:
                clave = patch["viejo"].strip().split("\n")[0]
                for i, linea in enumerate(leer(ruta).split("\n"), 1):
                    if clave.strip()[:40] in linea:
                        p(f"      contexto real (linea {i}): {linea.strip()[:100]}")
                        break
        p("")
        p(f"  {C['y']}Los parches que SI aplicaron tambien se descartaron "
          f"(atomicidad).{C['r']}")
        return 1

    if omitidos:
        p("")
        p(f"  {C['y']}{len(omitidos)} parche(s) opcionales no aplicaron "
          f"(pueden estar ya fixeados):{C['r']}")
        for patch, why in omitidos:
            p(f"      {C['y']}*{C['r']} {patch['archivo']} - {why}")

    if simular:
        hdr("SIMULACION - no se escribio nada")
        p(f"  {C['y']}Para aplicar de verdad:{C['r']} "
          f"python fixes\\aplicar_h15_h12.py --aplicar")
        return 0

    hdr("3 * ESCRITURA (un .bak por archivo)")
    for ruta, texto_orig, texto_final in cambios:
        bak = ruta.with_suffix(ruta.suffix + ".bak")
        shutil.copy2(ruta, bak)
        escribir(ruta, texto_final)
        p(f"  {C['g']}OK{C['r']} {ruta.name}  {C['c']}(.bak del ORIGINAL){C['r']}")

    # ADR 004
    adr_dir = RAIZ / "decisiones"
    adr_dir.mkdir(exist_ok=True)
    adr_path = adr_dir / "004-curva-de-capital-compuesta.md"
    if adr_path.exists():
        p(f"  {C['y']}* ADR 004 ya existe, no se sobreescribe{C['r']}")
    else:
        with open(adr_path, "w", encoding="utf-8") as f:
            f.write(ADR_004)
        p(f"  {C['g']}OK{C['r']} decisiones\\004-curva-de-capital-compuesta.md  {C['c']}(nuevo){C['r']}")

    hdr("4 * VERIFICACIÓN")
    import py_compile
    for ruta, _, _ in cambios:
        try:
            py_compile.compile(str(ruta), doraise=True)
            p(f"  {C['g']}OK{C['r']} compila: {ruta.name}")
        except py_compile.PyCompileError as e:
            p(f"  {C['R']}XX{C['r']} NO COMPILA: {ruta.name} -> {e}{C['r']}")
            p(f"      {C['R']}restaurar con: python fixes\\aplicar_h15_h12.py --deshacer{C['r']}")
            return 1

    ok1, ok2, dd1, dd2v, dd2n = _self_test()
    p(f"  {C['g'] if ok1 else C['R']}{'OK' if ok1 else 'XX'}{C['r']} self-test A: "
      f"DD compuesto dentro de 0..100  ({dd1:.2f}%)")
    p(f"  {C['g'] if ok2 else C['R']}{'OK' if ok2 else 'XX'}{C['r']} self-test B: "
      f"serie donde el metodo viejo da {dd2v:.1f}% y el compuesto {dd2n:.1f}%")

    # Verificar que el 0.02 huerfano desaparecio
    print()
    for nombre in ("C1_5_PARAM_local.py", "C3_MACRO_local.py"):
        f_ = RAIZ / nombre
        if not f_.exists():
            continue
        txt = leer(f_)
        huerfanos = [
            (i, l.strip()) for i, l in enumerate(txt.split("\n"), 1)
            if "ADF_P_VALUE_THRESHOLD" in l and "0.02" in l
        ]
        if huerfanos:
            p(f"  {C['R']}XX{C['r']} {nombre} todavia tiene {len(huerfanos)} "
              f"referencia(s) a 0.02:")
            for i, l in huerfanos:
                p(f"      linea {i}: {l[:100]}")
        else:
            p(f"  {C['g']}OK{C['r']} {nombre}: sin umbrales ADF huerfanos en 0.02")

    # Reportar el resto de usos de equity_curve (etiqueta del grafico)
    rv = RAIZ / "report_validator.py"
    if rv.exists():
        p("")
        p(f"  {C['c']}Usos de 'equity_curve' en report_validator.py "
          f"(revisar etiqueta del eje Y):{C['r']}")
        for i, linea in enumerate(leer(rv).split("\n"), 1):
            if "equity_curve" in linea and "cumprod" not in linea:
                p(f"      linea {i}: {linea.strip()[:110]}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    baks = sorted(RAIZ.glob("*.bak")) + sorted(RAIZ.glob("*/*.bak"))
    if not baks:
        p(f"  {C['y']}No hay archivos .bak{C['r']}")
        return 1
    for bak in baks:
        orig = bak.with_suffix("")
        if not orig.exists():
            p(f"  {C['R']}XX{C['r']} {orig.name} no existe (solo queda el .bak)")
            continue
        shutil.copy2(bak, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {orig.relative_to(RAIZ)}")
    p("")
    p(f"  {C['c']}Los .bak se conservan.{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Aplica H-15 (curva compuesta) y H-12 (fuente unica ADF) - MACRO2.1"
    )
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    p(f"{C['b']}{C['c']}aplicar_h15_h12.py{C['r']}  *  MACRO2.1")
    p(f"{C['c']}Raiz:{C['r']} {RAIZ}")

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
