# ==============================================================================
# 🦅 mercabot_qwen | RUNNER LOCAL (reemplaza el kernel de Colab)
# Carga las celdas en orden compartiendo un único namespace (mismo efecto que
# ejecutar celdas 1 → 1.5 → 2 → ... en un notebook).
# ==============================================================================
"""
Uso desde terminal (con el venv activo):

  python main.py                  # corre C0 → C1 → C1.5 → C2 → C2.5 → C3 → C3.5 → C4
  python main.py --celdas 2       # corre solo hasta C2.5
  python main.py --solo-c3         # carga C0..C2.5 en silencio y corre C3 → C3.5 → C4

Variables de entorno reconocidas:
  GEM5_MODO_CAPTURA=true|false   (default: true)
  MACRO1_ROOT=/ruta/al/proyecto  (default: carpeta de este archivo)
"""
import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MACRO1_ROOT", str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))


def ejecutar_celda(path: Path, namespace: dict, label: str,
                   silent_banner: bool = False) -> None:
    """
    Ejecuta un archivo .py dentro del namespace compartido, MERGEANDO
    los cambios de vuelta al namespace del runner.

    Si el código tiene 'await' a nivel top-level (típico de celdas de
    Colab que hacen `await alguna_coroutine()` al final), hacemos una
    transformación AST previa: cada 'await FUNC(...)' a nivel top-level
    se reemplaza por 'asyncio.run(FUNC(...))'. Los awaits DENTRO de
    async def NO se tocan.

    Args:
        silent_banner: si True, NO imprime el banner '▶ Ejecutando ...'.
                       Útil cuando el caller ya puso su propio header.
    """
    if not path.exists():
        raise FileNotFoundError(f"❌ No se encontró {path}")

    if not silent_banner:
        print(f"\n{'='*70}\n▶ Ejecutando {label}: {path.name}\n{'='*70}")

    code = path.read_text(encoding="utf-8")
    namespace['__file__'] = str(path)
    namespace['__name__'] = f"__celda_{path.stem}__"

    # Detectar awaits a nivel top-level (dentro de try/except/if/while
    # top-level, NO dentro de async def). Heurística: parsear con AST
    # y preguntar si hay algún nodo top-level ejecutable (no def/class)
    # que contenga un await en su subárbol sin funciones anidadas.
    has_top_level_await = False
    if 'await ' in code:
        try:
            import ast as _ast_check
            _tree = _ast_check.parse(code)
            for _node in _tree.body:
                if isinstance(_node, (_ast_check.FunctionDef,
                                       _ast_check.AsyncFunctionDef,
                                       _ast_check.ClassDef)):
                    continue
                for _child in _ast_check.walk(_node):
                    if isinstance(_child, (_ast_check.FunctionDef,
                                            _ast_check.AsyncFunctionDef,
                                            _ast_check.ClassDef)):
                        continue
                    if isinstance(_child, _ast_check.Await):
                        has_top_level_await = True
                        break
                if has_top_level_await:
                    break
        except SyntaxError:
            # Si no se puede parsear, dejar False y que el exec directo
            # muestre el error real.
            has_top_level_await = False

    if not has_top_level_await:
        # Sin await top-level: exec directo
        try:
            exec(compile(code, str(path), "exec"), namespace, namespace)
        except Exception as e:
            print(f"{namespace.get('CLR', {}).get('R', '')}"
                  f"❌ Error en {label}: {type(e).__name__}: {e}"
                  f"{namespace.get('CLR', {}).get('rst', '')}")
            import traceback
            traceback.print_exc()
        return

    # Hay awaits top-level: transformar con AST
    import ast as _ast
    import asyncio as _aio
    namespace.setdefault('asyncio', _aio)

    try:
        tree = _ast.parse(code)
    except SyntaxError as e:
        print(f"{namespace.get('CLR', {}).get('R', '')}"
              f"❌ SyntaxError en código original de {label}: {e}"
              f"{namespace.get('CLR', {}).get('rst', '')}")
        return

    def _has_await_skipping_funcs(node):
        """True si el nodo tiene awaits, ignorando los que estén
        dentro de FunctionDef/AsyncFunctionDef/ClassDef."""
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            return False
        for child in _ast.walk(node):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                continue
            if isinstance(child, _ast.Await):
                return True
        return False

    def _first_await_value(node):
        """Devuelve la primera expresión 'awaited' encontrada, sin
        recursar en funciones anidadas."""
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            return None
        for child in _ast.walk(node):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                continue
            if isinstance(child, _ast.Await):
                return _ast.unparse(child.value)
        return None

    def _replace_awaits_in_list(stmts):
        """Procesa una lista de statements. Si un nodo top-level es un
        Try/Expr/If con await, lo transforma a 'asyncio.run(expr)'.
        Retorna la nueva lista. CRÍTICO: si un nodo se transforma, NO
        seguimos procesando sus hijos (ya están envueltos en asyncio.run).
        """
        out = []
        for st in stmts:
            if isinstance(st, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                out.append(st)
                continue

            if _has_await_skipping_funcs(st):
                src = _first_await_value(st)
                if src is None:
                    out.append(st)
                    continue

                if isinstance(st, _ast.Try):
                    # Reemplazar el body del try por 'asyncio.run(src)'
                    run_stmt = _ast.Expr(value=_ast.parse(
                        f"asyncio.run({src})", mode='eval').body)
                    _ast.copy_location(run_stmt, st.body[0] if st.body else st)
                    new_try = _ast.Try(
                        body=[run_stmt],
                        handlers=st.handlers,
                        orelse=st.orelse,
                        finalbody=st.finalbody,
                    )
                    _ast.copy_location(new_try, st)
                    out.append(new_try)

                elif isinstance(st, _ast.Expr) and isinstance(st.value, _ast.Await):
                    run_stmt = _ast.Expr(value=_ast.parse(
                        f"asyncio.run({src})", mode='eval').body)
                    _ast.copy_location(run_stmt, st)
                    out.append(run_stmt)

                elif isinstance(st, _ast.If):
                    # Procesar recursivamente el body y orelse
                    new_if = _ast.If(
                        test=st.test,
                        body=_replace_awaits_in_list(st.body),
                        orelse=_replace_awaits_in_list(st.orelse),
                    )
                    _ast.copy_location(new_if, st)
                    out.append(new_if)

                else:
                    out.append(st)
            else:
                out.append(st)
        return out

    new_body = _replace_awaits_in_list(tree.body)
    tree.body = new_body
    _ast.fix_missing_locations(tree)
    new_code = _ast.unparse(tree)

    if 'import asyncio' not in new_code and 'from asyncio' not in new_code:
        new_code = "import asyncio\n" + new_code

    try:
        exec(compile(new_code, str(path), "exec"), namespace, namespace)
    except Exception as e:
        print(f"{namespace.get('CLR', {}).get('R', '')}"
              f"❌ Error en {label}: {type(e).__name__}: {e}"
              f"{namespace.get('CLR', {}).get('rst', '')}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Runner local mercabot_qwen")
    parser.add_argument(
        "--celdas", type=int, default=3,
        help="Cantidad de celdas a ejecutar. Por defecto 3 (todo lo disponible: "
             "C0+C1+C1.5+C2+C2.5+C3+C3.5+C4). Pasá 2 para cortar antes de MACRO, "
             "1 para solo setup + CONFIG, 0 para solo setup."
    )
    parser.add_argument(
        "--skip-c0", action="store_true",
        help="Saltar C0 (útil si ya tenés las dependencias instaladas)"
    )
    parser.add_argument(
        "--solo-c3", action="store_true",
        help="Carga C0..C2.5 en silencio y corre SOLO la C3 → C3.5 → C4 (útil para "
             "iterar en la C3 sin volver a imprimir las celdas anteriores)."
    )
    parser.add_argument(
        "--reporte", action="store_true",
        help="Después de la C3, genera reportes/reporte_macro.html con la "
             "tabla y lo abre en el browser. Útil para vista humana sin "
             "tocar la C3. Combinable con --solo-c3."
    )
    args = parser.parse_args()

    # Namespace compartido: simula el globals() del kernel de Colab
    ns = {"__name__": "__main__"}

    # ── MODO --solo-c3: cargar C0..C2.5 silenciosamente, luego C3 → C3.5 → C4 ──
    if args.solo_c3:
        print(f"⚙️  MODO --solo-c3: cargando C0..C2.5 en silencio...")
        # Redirigir stdout a /dev/null (o NUL en Windows) con encoding utf-8
        # para que los emojis (▶, ✅, etc.) no rompan en cp1252.
        import contextlib, os as _os
        _devnull_path = 'NUL' if _os.name == 'nt' else '/dev/null'
        with contextlib.redirect_stdout(open(_devnull_path, 'w', encoding='utf-8')):
            c0 = PROJECT_ROOT / "C0_INICIO_local.py"
            if c0.exists():
                ejecutar_celda(c0, ns, "CELDA 0 (setup)", silent_banner=True)
            ejecutar_celda(PROJECT_ROOT / "C1_CONFIG_local.py", ns, "CELDA 1 (silencio)", silent_banner=True)
            ejecutar_celda(PROJECT_ROOT / "C1_5_PARAM_local.py", ns, "CELDA 1.5 (silencio)", silent_banner=True)
            ejecutar_celda(PROJECT_ROOT / "C2_BOVEDA_local.py", ns, "CELDA 2 (silencio)", silent_banner=True)
            c25 = PROJECT_ROOT / "C2_5_CONTEXTO_local.py"
            if c25.exists():
                ejecutar_celda(c25, ns, "CELDA 2.5 (silencio)", silent_banner=True)

        # Confirmar carga y correr C3 con output completo
        ok = all(k in ns for k in ('CONFIG', 'CENTRAL_PARAMS', '_boveda_conn'))
        if not ok:
            print(f"❌ No se pudo cargar el contexto. Faltan: "
                  f"{[k for k in ('CONFIG','CENTRAL_PARAMS','_boveda_conn') if k not in ns]}")
            return
        print(f"✅ Contexto cargado. Ejecutando C3...")
        print(f"{'='*70}")
        ejecutar_celda(PROJECT_ROOT / "C3_MACRO_local.py", ns, "C3",
                       silent_banner=True)

        # ── C3.5: REGIME ENGINE ──
        c35 = PROJECT_ROOT / "C3_5_REGIME_ENGINE.py"
        if c35.exists():
            print(f"\n{'='*70}")
            print(f"▶ Ejecutando C3.5 (REGIME ENGINE)...")
            print(f"{'='*70}")
            ejecutar_celda(c35, ns, "C3.5", silent_banner=True)
        else:
            print(f"⚠️ {c35.name} no encontrado, saltando C3.5.")

        # ── C4: VALIDADOR DE SEALES ──
        c4 = PROJECT_ROOT / "C4_SENIAL_VALIDATOR.py"
        if c4.exists():
            print(f"\n{'='*70}")
            print(f"▶ Ejecutando C4 (VALIDADOR SEALES)...")
            print(f"{'='*70}")
            ejecutar_celda(c4, ns, "C4", silent_banner=True)
        else:
            print(f"⚠️ {c4.name} no encontrado, saltando C4.")

        # Generar reporte HTML si --reporte
        if args.reporte:
            try:
                from reporter import mostrar_reporte
                mostrar_reporte(ns)
            except Exception as _rep_err:
                print(f"⚠️  No se pudo generar el reporte: {_rep_err}")

        print(f"\n{'='*70}")
        print(f"✅ --solo-c3 finalizado.")
        print(f"{'='*70}")
        return

    # ── CELDA 0: Setup (opcional) ──
    if not args.skip_c0 and args.celdas >= 0:
        c0 = PROJECT_ROOT / "C0_INICIO_local.py"
        if c0.exists():
            ejecutar_celda(c0, ns, "CELDA 0 (setup)")
        else:
            print(f"⚠️ {c0.name} no encontrado, saltando setup.")

    # ── CELDA 1: CONFIG ──
    if args.celdas >= 1:
        ejecutar_celda(PROJECT_ROOT / "C1_CONFIG_local.py", ns, "CELDA 1 (CONFIG)")

    # ── CELDA 1.5: CENTRAL_PARAMS ──
    if args.celdas >= 1:
        ejecutar_celda(PROJECT_ROOT / "C1_5_PARAM_local.py", ns, "CELDA 1.5 (CENTRAL_PARAMS)")

    # ── CELDA 2: BOVEDA ──
    if args.celdas >= 2:
        ejecutar_celda(PROJECT_ROOT / "C2_BOVEDA_local.py", ns, "CELDA 2 (BOVEDA)")

    # ── CELDA 2.5: CONTEXTO DERIVADOS (definición, no auto-ejecuta) ──
    if args.celdas >= 2:
        c25 = PROJECT_ROOT / "C2_5_CONTEXTO_local.py"
        if c25.exists():
            ejecutar_celda(c25, ns, "CELDA 2.5 (CONTEXTO DERIVADOS)")
        else:
            print(f"⚠️ {c25.name} no encontrado, saltando C2.5.")

    # ── CELDA 3: MACRO (Cartografo v7.8.1) + CELDA T (Tabla bajo demanda) ──
    if args.celdas >= 3:
        c3 = PROJECT_ROOT / "C3_MACRO_local.py"
        if c3.exists():
            ejecutar_celda(c3, ns, "CELDA 3 (MACRO + TABLA)")
        else:
            print(f"⚠️ {c3.name} no encontrado, saltando C3.")

        # ── CELDA 3.5: REGIME ENGINE ──
        c35 = PROJECT_ROOT / "C3_5_REGIME_ENGINE.py"
        if c35.exists():
            ejecutar_celda(c35, ns, "CELDA 3.5 (REGIME ENGINE)")
        else:
            print(f"⚠️ {c35.name} no encontrado, saltando C3.5.")

        # ── CELDA 4: VALIDADOR DE SEALES ──
        c4 = PROJECT_ROOT / "C4_SENIAL_VALIDATOR.py"
        if c4.exists():
            ejecutar_celda(c4, ns, "CELDA 4 (VALIDADOR SEALES)")
        else:
            print(f"⚠️ {c4.name} no encontrado, saltando C4.")

        # Generar reporte HTML si --reporte
        if args.reporte:
            try:
                from reporter import mostrar_reporte
                mostrar_reporte(ns)
            except Exception as _rep_err:
                print(f"⚠️  No se pudo generar el reporte: {_rep_err}")

    # Diagnóstico del estado final del namespace
    print(f"\n{'='*70}")
    print(f"✅ Runner finalizado. Celdas ejecutadas: {args.celdas}")
    print(f"{'─'*70}")
    print(f"📦 Estado del namespace compartido (módulo estilo Colab):")
    claves_interes = ['CONFIG', 'CENTRAL_PARAMS', 'PRESETS', 'DB_FILE',
                      'BACKUP_DIR', 'LOGS_DIR', '_boveda_conn',
                      'GEM_MACRO_CONTEXT', 'MACRO_CONCLUSION', 'MACRO_BIAS',
                      'GLOBAL_RISK_REGIME', 'GLOBAL_MARKOV_STATE',
                      'GLOBAL_FUNDING_STATE', 'ALL_ASSETS', 'ejecutar_analisis_macro',
                      'imprimir_tabla_macro', 'ejecutar_contexto_derivados',
                      'C25_CONFIG',
                      # C3.5: REGIME ENGINE
                      'REGIME_STATE', 'REGIME_GLOBAL', 'ejecutar_regime_engine',
                      # C4: VALIDADOR DE SEALES
                      'C4_RESULT', 'ejecutar_validador_senales',
                      'get_signal_summary', 'get_signals_by_regime']
    for k in claves_interes:
        if k in ns:
            v = ns[k]
            tipo = type(v).__name__
            extra = ""
            if hasattr(v, 'DB_FILE') and not callable(v):
                extra = f" → DB_FILE={v.DB_FILE}"
            elif hasattr(v, '__fspath__'):
                extra = f" → {v}"
            elif isinstance(v, dict) and v:
                extra = f" → {len(v)} keys"
            elif isinstance(v, list):
                extra = f" → {len(v)} items"
            elif callable(v):
                extra = " → <callable>"
            print(f"   • {k:<28} [{tipo}]{extra}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()