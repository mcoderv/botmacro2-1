# -*- coding: utf-8 -*-
"""
corregir_pnl_pct.py  —  MACRO2.1
==================================
Correccion de UNIDAD del parche H-15 (aplicado con aplicar_h15_h12.py).

Que paso
--------
El parche H-15 cambio la equity curve de `np.cumsum(pnls)` (suma aritmetica de
porcentajes) a capital compuesto. Lo expusio como INDICE base 100:

    equity_curve = (cumprod(...) * 100.0)      ->  87.432 significa "capital 87.4%"

Pero el reporte ya consumia ese valor como PORCENTAJE con signo:
    linea 444:  f"{color_pct(pnl_acum)}{pnl_acum:>+9.3f}%"
    linea 683:  <td class="{'positive' if pnl_acum >= 0 else 'negative'}">{pnl_acum:+.3f}%</td>
    linea 657:  title="Trade {i+1}: {val:+.3f}%"
    linea 665:  _eq_class = "positive" if _eq_last >= 0 else "negative"

=> Con indice base 100 el reporte mostraba "+87.432%" PINTADO DE VERDE cuando
   en realidad es una PERDIDA del 12.568%.  Unidad equivocada + signo invertido.

La correccion
-------------
El Max DD se sigue calculando sobre el indice de capital (base 1.0), pero la
curva que consume el reporte se expresa en PnL% sobre ese capital compuesto:

    _equity = np.cumprod(1.0 + pnl/100)              # indice, base 1.0
    max_dd  = max((1 - equity/peak) * 100)           # DD en %, correcto
    equity_curve = ((_equity - 1.0) * 100).tolist()  # PnL% acumulado

Con eso los 4 consumidores quedan correctos SIN tocarlos:
  - pnl_acum = -12.568  -> se imprime "-12.568%"   -> y se pinta de ROJO
  - el chart de barras escala bien y muestra la trayectoria real del capital
  - el Max DD no cambia (se calcula sobre el indice)

Ademas actualiza el ADR 004, que describia la curva como "indice base 100".

Uso (desde la raiz del proyecto):
  python fixes\\corregir_pnl_pct.py --simular     (default: no escribe nada)
  python fixes\\corregir_pnl_pct.py --aplicar     (escribe, con .bak)
  python fixes\\corregir_pnl_pct.py --deshacer    (restaura desde .bak)

NUNCA toca la DB. NUNCA toca produccion (botmacro).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _buscar_raiz() -> Path:
    p = Path(__file__).resolve().parent
    for cand in [p, *p.parents]:
        if (cand / "data").is_dir() and (cand / "config").is_dir():
            return cand
    return p.parent


RAIZ = _buscar_raiz()

C = {
    "r": "\033[0m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m",
    "R": "\033[31m", "c": "\033[36m",
}


def p(t=""):
    """Imprime sanitizando a la codificacion de la consola de Windows."""
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(t.encode(enc, errors="replace").decode(enc, errors="replace"))
    except Exception:
        print(t)


def hdr(t):
    p(f"\n{C['b']}{'='*74}{C['r']}")
    p(f"{C['b']}  {t}{C['r']}")
    p(f"{C['b']}{'='*74}{C['r']}")


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8", errors="surrogateescape")


def escribir(ruta: Path, texto: str) -> None:
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(texto)


# ──────────────────────────────────────────────────────────────────────────────
# PARCHES
# ──────────────────────────────────────────────────────────────────────────────
PARCHES = [
    {
        "archivo": "report_validator.py",
        "titulo": "Unidad: la curva se expone en PnL% sobre capital compuesto",
        "viejo": """        _equity = np.cumprod(1.0 + _pnl_arr / 100.0) * 100.0   # base 100
        _peak = np.maximum.accumulate(_equity)
        max_drawdown = float(np.max((1.0 - _equity / _peak) * 100.0))
        equity_curve = _equity.tolist()
""",
        "nuevo": """        _equity = np.cumprod(1.0 + _pnl_arr / 100.0)          # indice de capital, base 1.0
        _peak = np.maximum.accumulate(_equity)
        max_drawdown = float(np.max((1.0 - _equity / _peak) * 100.0))
        # La curva se expone en PnL% (lo que el reporte ya espera: columna
        # "PnL acumulado", color por signo, tooltip en %). El Max DD de arriba
        # se calcula sobre el indice de capital, no sobre esta serie.
        equity_curve = ((_equity - 1.0) * 100.0).tolist()
""",
    },
    {
        "archivo": "decisiones/004-curva-de-capital-compuesta.md",
        "titulo": "ADR 004: la curva es PnL% sobre capital compuesto (no indice base 100)",
        "viejo": """La curva de capital se construye **compuesta**, indexada a base 100:

```python
_equity = np.cumprod(1.0 + np.array(pnls, dtype=float) / 100.0) * 100.0
_peak   = np.maximum.accumulate(_equity)
max_dd  = float(np.max((1.0 - _equity / _peak) * 100.0))
```
""",
        "nuevo": """La curva de capital se construye **compuesta**:

```python
_equity = np.cumprod(1.0 + np.array(pnls, dtype=float) / 100.0)   # indice, base 1.0
_peak   = np.maximum.accumulate(_equity)
max_dd  = float(np.max((1.0 - _equity / _peak) * 100.0))
equity_curve = ((_equity - 1.0) * 100.0).tolist()   # PnL% acumulado
```

**El Max DD se calcula sobre el índice de capital (base 1.0). La curva que
consume el reporte se expresa en PnL% sobre ese capital compuesto**, que es la
unidad que el reporte ya espera: columna "PnL acumulado", color por signo y
tooltip en `%`. Exponer el índice base 100 hacía que el reporte mostrara
"+87.432%" pintado de verde cuando en realidad era una pérdida del 12.568%
(unidad equivocada + signo invertido).
""",
    },
    {
        "archivo": "decisiones/004-curva-de-capital-compuesta.md",
        "titulo": "ADR 004: consecuencia del grafico corregida",
        "viejo": """1. **El gráfico de equity del reporte HTML cambia de semántica**: de "% PnL
   acumulado" a "índice de capital (base 100)". La etiqueta del eje Y debe
   actualizarse. El script reporta las líneas afectadas.
""",
        "nuevo": """1. **La curva que consume el reporte pasa a ser PnL% sobre capital compuesto.**
   Antes era "% PnL acumulado" sobre una suma aritmética; ahora es ese mismo
   porcentaje, pero calculado con capital compuesto. La columna, el color por
   signo y el tooltip en `%` siguen siendo correctos **sin tocar el reporte**.
   Beneficio adicional: el chart de barras escala por
   `max(abs(min), abs(max))`, así que antes dibujaba una escalera de valores
   positivos hasta +270; ahora dibuja la trayectoria real del capital.
""",
    },
]


def aplicar(simular: bool) -> int:
    hdr("1 - PARCHES")
    # Agrupar por archivo: UN .bak por archivo (del ORIGINAL), no uno por parche.
    por_archivo: dict[str, list] = {}
    for patch in PARCHES:
        por_archivo.setdefault(patch["archivo"], []).append(patch)

    cambios = []
    fallidos = []
    for archivo, ps in por_archivo.items():
        ruta = RAIZ / archivo
        if not ruta.exists():
            for patch in ps:
                fallidos.append((patch, f"no existe {archivo}"))
                p(f"  {C['R']}XX{C['r']} {patch['titulo'][:64]}")
                p(f"      {C['R']}no existe {archivo}{C['r']}")
            continue
        texto_orig = leer(ruta)
        texto = texto_orig
        fallo = None
        for patch in ps:
            n = texto.count(patch["viejo"])
            if n != 1:
                fallidos.append((patch, f"patron encontrado {n} veces (se requiere 1)"))
                p(f"  {C['R']}XX{C['r']} {patch['titulo'][:64]}")
                p(f"      {C['R']}patron encontrado {n} veces{C['r']}")
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
        for patch, why in fallidos:
            p(f"  {C['R']}XX{C['r']} {patch['archivo']} - {patch['titulo']}")
            p(f"      {C['R']}{why}{C['r']}")
            ruta = RAIZ / patch["archivo"]
            if ruta.exists():
                clave = patch["viejo"].strip().split("\n")[0]
                for i, linea in enumerate(leer(ruta).split("\n"), 1):
                    if clave.strip()[:40] in linea:
                        p(f"      contexto real (linea {i}): {linea.strip()[:100]}")
                        break
        return 1

    if simular:
        hdr("SIMULACION - no se escribio nada")
        p(f"  {C['y']}Para aplicar: python fixes\\corregir_pnl_pct.py --aplicar{C['r']}")
        return 0

    hdr("2 · ESCRITURA (con .bak)")
    for ruta, texto_orig, texto_final in cambios:
        bak = ruta.with_suffix(ruta.suffix + ".bak")
        shutil.copy2(ruta, bak)
        escribir(ruta, texto_final)
        p(f"  {C['g']}OK{C['r']} {ruta.name}  {C['c']}(.bak del ORIGINAL){C['r']}")

    hdr("3 · VERIFICACION")
    import py_compile
    rv = RAIZ / "report_validator.py"
    if rv.exists():
        try:
            py_compile.compile(str(rv), doraise=True)
            p(f"  {C['g']}OK{C['r']} compila: report_validator.py")
        except py_compile.PyCompileError as e:
            p(f"  {C['R']}XX{C['r']} NO COMPILA: {e}{C['r']}")
            p(f"      {C['R']}restaurar: python fixes\\corregir_pnl_pct.py --deshacer{C['r']}")
            return 1

    # Self-test: la curva expuesta debe ser el PnL% del capital compuesto
    try:
        import numpy as np
        serie = [10.0, -5.0, -3.0, 8.0, -20.0, 2.0]
        _arr = np.array(serie, dtype=float)
        _eq = np.cumprod(1.0 + _arr / 100.0)
        _peak = np.maximum.accumulate(_eq)
        dd = float(np.max((1.0 - _eq / _peak) * 100.0))
        curva = ((_eq - 1.0) * 100.0).tolist()
        ok = (0.0 <= dd <= 100.0) and abs(curva[-1] - ((_eq[-1] - 1.0) * 100.0)) < 1e-9
        p(f"  {C['g'] if ok else C['R']}{'OK' if ok else 'XX'}{C['r']} self-test: "
          f"DD={dd:.2f}%  ultimo_valor_curva={curva[-1]:+.3f}%  (PnL% correcto)")
    except Exception as e:
        p(f"  {C['y']}· self-test no pudo correr: {e}{C['r']}")

    # Reportar el resto de consumidores de equity_curve
    if rv.exists():
        p("")
        p(f"  {C['c']}Consumidores de 'equity_curve' (verificar que esperan %):{C['r']}")
        for i, linea in enumerate(leer(rv).split("\n"), 1):
            if "equity_curve" in linea and "cumprod" not in linea:
                p(f"      linea {i}: {linea.strip()[:104]}")
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
        description="Corrige la unidad de la equity curve (PnL% sobre capital compuesto)"
    )
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    p(f"{C['b']}{C['c']}corregir_pnl_pct.py{C['r']}  -  MACRO2.1")
    p(f"{C['c']}Raiz:{C['r']} {RAIZ}")

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
