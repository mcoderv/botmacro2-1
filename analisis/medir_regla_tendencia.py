#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
medir_regla_tendencia.py - SOLO LECTURA. Baja velas de la API y calcula.
No escribe nada: ni en data/, ni en el repo, ni en la base.

QUE MIDE
    El umbral de tendencia del motor de regimen. Hoy es un numero fijo: la
    pendiente por vela tiene que superar 0.0012 (= 2.88% por dia) para decir
    TREND. Medido el 27/10: 12 de 12 activos dieron RANGE y el que mas se
    movio llego al 63% de ese umbral.

    Este script compara CUATRO reglas sobre las MISMAS velas reales y sobre
    series sinteticas con propiedades conocidas:

      R1 ACTUAL    : |pendiente de las ultimas 20 velas| > 0.0012
                     (numero fijo, igual para todos los activos)
      R2 VOLATIL   : |deriva diaria| > k * sigma diaria del activo  (k=1)
      R3 T-NIVEL   : |t| de la pendiente del precio (HAC) > 1.96
      R4 T-RETORNO : |t| de la media de los retornos (HAC) > 1.96

    R3 y R4 preguntan casi lo mismo pero de forma distinta: R3 mide la
    pendiente SOBRE EL PRECIO (serie no estacionaria) y R4 mide la deriva
    SOBRE LOS RETORNOS. El control con paseos aleatorios demuestra cual de las
    dos tiene la tasa de falsos positivos que dice tener.

    Ademas mide la tasa de falsos positivos de cada regla sobre 200 paseos
    aleatorios, a TRES niveles de volatilidad, porque un umbral fijo castiga
    distinto a un activo que se mueve 0,1% por hora que a uno que se mueve 0,6%.

PARA QUE SIRVE
    Es el insumo del ADR 016 ("que es tendencia en este proyecto"): cuantos
    activos cambia cada regla, cual tiene la tasa de error que declara, y cual
    queda descartada por comportamiento absurdo. Sin esto, elegir k o alfa
    seria calibrar sobre la misma muestra que despues se usa para juzgar.

DE DONDE SACA LOS DATOS
    API publica de Hyperliquid (la misma que usa C3_5), velas de 1 h, mismos
    lookbacks que el motor: 30 dias cripto / 60 dias TradFi. Descarta la
    ultima vela si todavia no cerro (igual que el motor).

COMO SE CORRE
    python analisis\\medir_regla_tendencia.py
    python analisis\\medir_regla_tendencia.py --k 0.5      (otro nivel para R2)
    python analisis\\medir_regla_tendencia.py --sin-api    (solo controles)

SALIDA
    Texto ASCII corto con bloque FLAGS al final.
"""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request

import numpy as np

HL_URL = "https://api.hyperliquid.xyz/info"   # = CONFIG.HL_REST_URL (C1_CONFIG)
CRYPTO = ["BTC", "ETH", "SOL", "XRP", "AVAX", "HYPE"]
TRADFI = ["xyz:SP500", "xyz:XYZ100", "xyz:GOLD", "xyz:EUR", "xyz:SILVER", "xyz:CL"]
UMBRAL_ACTUAL = 0.0012          # TREND_SLOPE_THRESHOLD (C3_5_REGIME_ENGINE.py)
VELAS_PENDIENTE = 20            # ventana que usa hoy el motor
ALFA_T = 1.96                   # dos colas, 5%
N_SIM = 200
VOLS_PRUEBA = (0.001, 0.003, 0.006)   # sigma por hora

FLAGS = []


def flag(t):
    FLAGS.append(t)


def sec(t):
    print("")
    print("=" * 66)
    print(t)
    print("=" * 66)


# ──────────────────────────────────────────────────────────────────────────────
# 1. ESTADISTICA
# ──────────────────────────────────────────────────────────────────────────────
def pendiente(y):
    """OLS de y (log precio) contra el indice. Devuelve (pendiente, residuos)."""
    n = len(y)
    x = np.arange(n, dtype=float)
    xm = x.mean()
    ym = y.mean()
    sxx = float(((x - xm) ** 2).sum())
    if sxx <= 0:
        return 0.0, np.zeros(n)
    b = float(((x - xm) * (y - ym)).sum() / sxx)
    a = ym - b * xm
    return b, y - (a + b * x)


def _hac_var_media(x):
    """Varianza HAC (Bartlett) de la media de x."""
    n = len(x)
    if n < 30:
        return float("nan")
    e = x - x.mean()
    rezagos = int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    s = float((e ** 2).sum())
    for lag in range(1, rezagos + 1):
        w = 1.0 - lag / (rezagos + 1.0)
        s += 2.0 * w * float((e[lag:] * e[:-lag]).sum())
    return max(s / (n * n), 1e-30)


def t_hac_slope(y):
    """t de la pendiente del precio con errores Newey-West."""
    n = len(y)
    if n < 30:
        return 0.0
    X = np.column_stack([np.ones(n), np.arange(n, dtype=float)])
    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return 0.0
    b = xtx_inv @ X.T @ y
    e = y - X @ b
    rezagos = int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    S = np.zeros((2, 2))
    for t in range(n):
        xt = X[t][:, None]
        S += (e[t] ** 2) * (xt @ xt.T)
    for lag in range(1, rezagos + 1):
        w = 1.0 - lag / (rezagos + 1.0)
        for t in range(lag, n):
            xt = X[t][:, None]
            xtl = X[t - lag][:, None]
            A = (e[t] * e[t - lag]) * (xt @ xtl.T)
            S += w * (A + A.T)
    V = xtx_inv @ S @ xtx_inv
    se = math.sqrt(max(V[1, 1], 1e-30))
    return float(b[1] / se)


def t_hac_retornos(y):
    """t de la media de los retornos (deriva) con errores HAC."""
    r = np.diff(y)
    if len(r) < 30:
        return 0.0
    var = _hac_var_media(r)
    if not np.isfinite(var) or var <= 0:
        return 0.0
    return float(r.mean() / math.sqrt(var))


def metricas(log_p):
    """Todas las metricas que necesitan las cuatro reglas, para una serie."""
    ret = np.diff(log_p)
    sigma_d = float(np.std(ret)) * math.sqrt(24.0)
    b_full, _ = pendiente(log_p)
    b_20, _ = pendiente(log_p[-VELAS_PENDIENTE:])
    deriva_d = b_full * 24.0
    return {
        "n": len(log_p),
        "sigma_d": sigma_d,
        "b_full": b_full,
        "b_20": b_20,
        "deriva_d": deriva_d,
        "ratio": (deriva_d / sigma_d) if sigma_d > 0 else 0.0,
        "t_nivel": t_hac_slope(log_p),
        "t_ret": t_hac_retornos(log_p),
    }


def veredicto(m, k, alfa=ALFA_T):
    return {
        "R1_actual": abs(m["b_20"]) > UMBRAL_ACTUAL,
        "R2_volat": abs(m["deriva_d"]) > k * m["sigma_d"],
        "R3_tnivel": abs(m["t_nivel"]) > alfa,
        "R4_tret": abs(m["t_ret"]) > alfa,
    }


REGLAS = ("R1_actual", "R2_volat", "R3_tnivel", "R4_tret")


# ──────────────────────────────────────────────────────────────────────────────
# 2. CONTROLES SINTETICOS
# ──────────────────────────────────────────────────────────────────────────────
def serie(drift, sigma, n=720, phi=0.0, semilla=7):
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(0.0, sigma, n)
    if phi > 0:                       # AR(1): reversion a la media
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = phi * x[i - 1] + ruido[i]
        return x + 3.0
    return 3.0 + np.cumsum(ruido) + drift * np.arange(n)


CONTROLES = [
    ("tendencia fuerte", 0.0030, 0.0030, 0.0, "las 4 deberian decir TREND"),
    ("paseo aleatorio", 0.0000, 0.0030, 0.0, "las 4 deberian decir RANGE"),
    ("reversion a media", 0.0000, 0.0030, 0.90, "las 4 deberian decir RANGE"),
    ("deriva chica + ruido", 0.0002, 0.0060, 0.0, "trampa: R2 RANGE, R4 TREND"),
]


def probar_controles(k):
    sec("2. CONTROLES SINTETICOS (propiedades conocidas, semilla fija)")
    print("  %-21s %9s %8s %7s %7s %7s  %s"
          % ("serie", "deriva/d", "sigma/d", "ratio", "t_niv", "t_ret", "R1 R2 R3 R4"))
    for nombre, drift, sigma, phi, esperado in CONTROLES:
        m = metricas(serie(drift, sigma, phi=phi))
        v = veredicto(m, k)
        marcas = " ".join("T" if v[r] else "." for r in REGLAS)
        print("  %-21s %8.3f%% %7.3f%% %7.2f %7.1f %7.1f  %s"
              % (nombre, m["deriva_d"] * 100, m["sigma_d"] * 100, m["ratio"],
                 m["t_nivel"], m["t_ret"],
                 "  ".join(marcas.split())))

    print("")
    print("  Tasa de TREND sobre %d paseos aleatorios SIN deriva (falsos positivos):"
          % N_SIM)
    print("  %-10s %s" % ("sigma/h", "  ".join("%-10s" % r for r in REGLAS)))
    peor = {r: (0.0, 0.0) for r in REGLAS}
    for sigma in VOLS_PRUEBA:
        conteo = {r: 0 for r in REGLAS}
        for i in range(N_SIM):
            v = veredicto(metricas(serie(0.0, sigma, semilla=1000 + i)), k)
            for r in REGLAS:
                conteo[r] += 1 if v[r] else 0
        linea = "  ".join("%5d (%2.0f%%)" % (conteo[r], 100.0 * conteo[r] / N_SIM)
                          for r in REGLAS)
        print("  %-10s %s" % ("%.3f" % sigma, linea))
        for r in REGLAS:
            tasa = 100.0 * conteo[r] / N_SIM
            if tasa > peor[r][0]:
                peor[r] = (tasa, sigma)
    print("")
    for r in REGLAS:
        tasa, sigma = peor[r]
        if r == "R3_tnivel" and tasa > 15:
            flag("R3 (t sobre el PRECIO): hasta %.0f%% de falsos positivos (sigma "
                 "%.3f). El precio no es estacionario: ese t no es valido" % (tasa, sigma))
        if r == "R4_tret" and tasa > 8:
            flag("R4 (t sobre RETORNOS): %.0f%% de falsos positivos con sigma %.3f"
                 % (tasa, sigma))
        if r == "R1_actual" and tasa > 15:
            flag("R1 (umbral fijo): hasta %.0f%% de falsos positivos (sigma %.3f) "
                 "y 0%% con volatilidad baja: el mismo umbral falla distinto segun "
                 "el activo" % (tasa, sigma))


# ──────────────────────────────────────────────────────────────────────────────
# 3. API
# ──────────────────────────────────────────────────────────────────────────────
def bajar_velas(coin, dias, reintentos=3):
    ahora_ms = int(time.time() * 1000)
    payload = {"type": "candleSnapshot",
               "req": {"coin": coin, "interval": "1h",
                       "startTime": int((time.time() - 86400 * dias) * 1000)}}
    datos = json.dumps(payload).encode("utf-8")
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(
                HL_URL, data=datos,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                bruto = json.loads(resp.read().decode("utf-8"))
            if not isinstance(bruto, list) or len(bruto) < 50:
                return None, "respuesta corta (%s velas)" % (
                    len(bruto) if isinstance(bruto, list) else "?")
            cierres = []
            for v in bruto:
                if int(v["t"]) + 3600 * 1000 > ahora_ms:
                    continue
                cierres.append(float(v["c"]))
            if len(cierres) < 50:
                return None, "menos de 50 velas cerradas"
            return np.log(np.array(cierres)), None
        except urllib.error.HTTPError as e:
            if e.code == 429 and intento < reintentos - 1:
                time.sleep(2.0 * (intento + 1))
                continue
            return None, "HTTP %s" % e.code
        except Exception as e:
            if intento < reintentos - 1:
                time.sleep(1.5 * (intento + 1))
                continue
            return None, "%s: %s" % (type(e).__name__, e)
    return None, "sin respuesta"


def probar_api(k):
    sec("3. DATOS REALES (velas 1 h cerradas, API Hyperliquid)")
    print("  %-11s %4s %7s %9s %7s %7s  %s"
          % ("activo", "n", "sigma/d", "deriva/d", "ratio", "t_ret", "R1 R2 R3 R4"))
    filas = []
    for coin in CRYPTO + TRADFI:
        dias = 60 if coin.startswith("xyz:") else 30
        lp, err = bajar_velas(coin, dias)
        time.sleep(0.4)
        if lp is None:
            print("  %-11s  --  error: %s" % (coin, err))
            flag("%s no se pudo medir: %s" % (coin, err))
            continue
        m = metricas(lp)
        v = veredicto(m, k)
        filas.append((coin, m, v))
        marcas = "  ".join("T" if v[r] else "." for r in REGLAS)
        print("  %-11s %4d %6.2f%% %8.3f%% %7.2f %7.1f  %s"
              % (coin, m["n"], m["sigma_d"] * 100, m["deriva_d"] * 100,
                 m["ratio"], m["t_ret"], marcas))

    if not filas:
        flag("no se pudo medir ningun activo")
        return

    sec("4. CUANTOS ACTIVOS CAMBIAN DE ETIQUETA")
    total = len(filas)
    print("  activos medidos: %d | umbral R1 = %.4f por vela (%.2f%%/dia)"
          % (total, UMBRAL_ACTUAL, UMBRAL_ACTUAL * 24 * 100))
    print("  nivel R2: k = %.2f (deriva diaria > k * sigma diaria)" % k)
    print("")
    print("  %-12s %9s  %s" % ("regla", "TREND", "quienes"))
    for r in REGLAS:
        quienes = [c for c, m, v in filas if v[r]]
        print("  %-12s %5d/%-3d %s"
              % (r, len(quienes), total, ", ".join(quienes) if quienes else "(ninguno)"))

    ratios = [abs(m["ratio"]) for _, m, _ in filas]
    tret = [abs(m["t_ret"]) for _, m, _ in filas]
    print("")
    print("  |ratio| mediana %.2f  maximo %.2f   (cuanto tendria que bajar k)"
          % (float(np.median(ratios)), max(ratios)))
    print("  |t_ret| mediana %.1f  maximo %.1f" % (float(np.median(tret)), max(tret)))
    sigmas = [m["sigma_d"] for _, m, _ in filas]
    print("  sigma diaria: minima %.2f%%  mediana %.2f%%  maxima %.2f%%"
          % (min(sigmas) * 100, float(np.median(sigmas)) * 100, max(sigmas) * 100))
    if min(sigmas) > 0:
        print("  disparidad de volatilidad entre activos: %.1fx"
              % (max(sigmas) / min(sigmas)))
        if max(sigmas) / min(sigmas) > 5:
            flag("la volatilidad entre activos varia %.1fx: un umbral fijo en %% "
                 "castiga distinto a cada uno" % (max(sigmas) / min(sigmas)))
    if all(v["R3_tnivel"] for _, _, v in filas):
        flag("R3 declara TREND en TODOS los activos: con muchas velas el t sobre "
             "el precio no discrimina (misma conclusion que el control)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=1.0,
                    help="nivel de R2: deriva diaria en multiplos de sigma diaria")
    ap.add_argument("--sin-api", action="store_true", help="solo controles")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("MEDIR REGLA DE TENDENCIA - solo lectura")
    import datetime as dt
    print("fecha : %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("fuente: %s (velas 1h cerradas)" % HL_URL)
    print("nota  : no escribe nada; solo baja velas y calcula")

    sec("1. LAS CUATRO REGLAS QUE SE COMPARAN")
    print("  R1 actual   : |pendiente ultimas 20 velas| > %.4f  (= %.2f%%/dia fijo)"
          % (UMBRAL_ACTUAL, UMBRAL_ACTUAL * 24 * 100))
    print("  R2 volatil  : |deriva diaria| > k * sigma diaria del activo  (k=%.2f)"
          % args.k)
    print("  R3 t-nivel  : |t| de la pendiente del PRECIO (HAC) > %.2f" % ALFA_T)
    print("  R4 t-retorno: |t| de la media de los RETORNOS (HAC) > %.2f" % ALFA_T)

    probar_controles(args.k)
    if not args.sin_api:
        probar_api(args.k)

    sec("FLAGS")
    if not FLAGS:
        print("  (ninguno)")
    for f in FLAGS:
        print("  [F] %s" % f)
    print("")


if __name__ == "__main__":
    main()
