#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
guardar.py — "Saca una foto" de tu proyecto (commit).
Escribe solo lo que YA existe en la carpeta. No modifica ningun archivo.

USO:
    python git\\guardar.py "I-3: trailing stop ATR"
    python git\\guardar.py "I-3: trailing stop ATR" --tag v2.1-I3-ok

El "--tag" opcional crea una etiqueta con nombre (para marcar "esto funciona").
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def run(args, check=True):
    """Ejecuta git y devuelve (stdout, stderr, codigo)."""
    p = subprocess.run(
        ["git"] + args,
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and p.returncode != 0:
        print("[ERROR] El comando fallo: git " + " ".join(args))
        print((p.stdout or "").strip())
        print((p.stderr or "").strip())
        sys.exit(1)
    return p.stdout, p.stderr, p.returncode


def main():
    if len(sys.argv) < 2:
        print('Uso: python git\\guardar.py "mensaje" [--tag nombre]')
        print()
        print('  Ejemplo: python git\\guardar.py "I-3: trailing stop ATR en C4"')
        sys.exit(1)

    mensaje = sys.argv[1].strip()
    etiqueta = None
    if "--tag" in sys.argv:
        i = sys.argv.index("--tag")
        if i + 1 < len(sys.argv):
            etiqueta = sys.argv[i + 1]

    if not (RAIZ / ".git").exists():
        print("[ERROR] Esta carpeta no es un repo de git.")
        print("       Corré esto primero:  git init")
        sys.exit(1)

    # --- Seguridad: .env jamas puede entrar al commit ---
    _, _, code = run(["ls-files", "--error-unmatch", ".env"], check=False)
    if code == 0:
        print("[AVISO] .env estaba versionado. Lo saco del indice (el archivo queda en tu disco).")
        run(["rm", "--cached", ".env"])

    # --- Identidad ---
    salida_cfg, _, code_cfg = run(["config", "user.email"], check=False)
    if code_cfg != 0 or not salida_cfg.strip():
        print("[AVISO] No hay user.email configurado. Uso un fallback local.")
        run(["config", "user.email", "mcoderv@localhost"])
        run(["config", "user.name", "mcoderv"])

    # --- Preparar ---
    run(["add", "-A"])
    salida = run(["diff", "--cached", "--name-only"])[0].strip()

    if not salida:
        print("[OK] No hay cambios nuevos. Todo esta igual que el ultimo guardado.")
        print()
        run(["log", "--oneline", "-1"])
        print()
        print("Siguiente paso: python git\\estado.py")
        return

    archivos = salida.splitlines()
    print("Archivos a guardar (%d):" % len(archivos))
    for a in archivos[:30]:
        print("   - " + a)
    if len(archivos) > 30:
        print("   ... y %d mas" % (len(archivos) - 30))
    print()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    run(["commit", "-q", "-m", "[%s] %s" % (ts, mensaje)])

    if etiqueta:
        run(["tag", etiqueta])
        print("[OK] Etiqueta creada: %s" % etiqueta)

    print("[OK] Guardado.")
    print()
    run(["log", "--oneline", "-1"])
    print()
    print("Para subirlo a GitHub (repo de desarrollo):")
    print("   git push origin main")
    print()
    print("Para subirlo a PRODUCCION (repo congelado) solo cuando corresponda:")
    print("   git push origin-macro2 main")
    print()
    print("Siguiente paso: python git\\estado.py")


if __name__ == "__main__":
    main()
