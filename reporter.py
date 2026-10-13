# ==============================================================================
# mercabot_qwen | REPORTER v3.0 — Panel Trader + Panel IA
# ------------------------------------------------------------------------------
# v3.0: Rediseño completo con dos paneles diferenciados:
#   - PANEL TRADER: Decisión rápida (5 segundos), fuente 18px, TOP 3-5
#   - PANEL IA: Contexto completo en Markdown para análisis profundo
#   - Dark mode persistente
#   - Genera reporte_macro.html y lo abre en browser
#
# Uso desde main.py:
#     from reporter import mostrar_reporte
#     mostrar_reporte(ns)  # genera HTML y abre browser
# ==============================================================================
"""
Funciones exportadas:
    mostrar_reporte(ns) -> str   # ruta del HTML generado (o None si falla)
"""
import os
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# -----------------------------------------------------------------------------
# Configuración: dónde guardar el HTML
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTE_DIR = PROJECT_ROOT / "reportes"
REPORTE_PATH = REPORTE_DIR / "reporte_macro.html"

# Umbrales para clasificar activos
SCORE_MIN_CONFIRMACION = 14
SCORE_MAX_CONFIRMACION = 20
FUNDING_EXTREMO_PCT = 0.05  # 0.05% = extremo
FUNDING_SEGURO_PCT = 0.03   # 0.03% = seguro


# -----------------------------------------------------------------------------
# Helpers de clasificación
# -----------------------------------------------------------------------------
def _classify_bias(value: str) -> str:
    """Clase CSS según el bias para colorear en HTML."""
    v = (value or "").upper().strip()
    if v in ("BULL", "BUY", "STRONG BULLISH", "SANA_UP"):
        return "bull"
    if v in ("BEAR", "SELL", "STRONG BEARISH", "SANA_DN"):
        return "bear"
    if v in ("RANGO", "EN RANGO", "NOISE", "NEUTRO", "NEUTRAL"):
        return "rango"
    if v.startswith("SQZ"):
        return "squeeze"
    if v in ("ACUM", "ACUMULANDO", "—", "-"):
        return "neutral"
    return ""


def _classify_quality(value: str) -> str:
    """Clase CSS según data quality."""
    v = (value or "").upper().strip()
    if v == "OK":
        return "bull"
    if v in ("DEGRADED", "FORMING", "INSUFFICIENT"):
        return "rango"
    if v in ("STALE",):
        return "squeeze"
    if v in ("ERROR", "UNKNOWN", ""):
        return "bear"
    return ""


def _classify_html(value: str) -> str:
    """Devuelve el value con un emoji indicador para el header."""
    v = (value or "N/A").upper()
    if v in ("BULL", "BUY", "RISK_ON"):
        return f"🟢 {value}"
    if v in ("BEAR", "SELL", "RISK_OFF"):
        return f"🔴 {value}"
    if v in ("RANGO", "EN RANGO", "NEUTRAL", "N/A"):
        return f"🟡 {value}"
    return f"⚪ {value}"


def _bias_or_dash(value: str) -> str:
    """Si el bias es N/A, devuelve — (más neutral)."""
    v = (value or "").upper().strip()
    if v in ("N/A", "", "—", "-", "NONE"):
        return "—"
    return value


def _escape(s: str) -> str:
    """Escapa HTML básico."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("—", "&mdash;")
    )


# -----------------------------------------------------------------------------
# Cálculo de confianza para el Panel Trader
# -----------------------------------------------------------------------------
def _calculate_confidence(z: Dict[str, Any]) -> Tuple[int, str, str]:
    """
    Calcula confianza (0-100), acción recomendada y razón clave.
    
    Args:
        z: Datos de GEM_MACRO_CONTEXT para un activo.
    
    Returns:
        (confianza_pct, accion, razon)
    """
    score = z.get("macro_score", 0)
    bias_visual = z.get("bias_visual", "RANGO")
    
    # Alineación multi-timeframe
    b1d = _bias_or_dash(z.get("bias_1d", "N/A")).upper()
    b4h = _bias_or_dash(z.get("bias_4h", "N/A")).upper()
    b1h = _bias_or_dash(z.get("bias_1h", "N/A")).upper()
    
    biases = [b for b in [b1d, b4h, b1h] if b not in ("N/A", "—", "")]
    bullish_count = sum(1 for b in biases if b in ("BULL", "BUY", "STRONG BULLISH"))
    bearish_count = sum(1 for b in biases if b in ("BEAR", "SELL", "STRONG BEARISH"))
    
    # Calidad de datos
    dq = z.get("data_quality_status", "UNKNOWN").upper()
    
    # Funding
    fmap = z.get("funding", {}) or {}
    funding_pct = fmap.get("funding_pct", 0.0)
    funding_extremo = abs(funding_pct) > FUNDING_EXTREMO_PCT
    
    # OBI (si disponible)
    obi_pressure = z.get("ctx25_obi_pressure", "")
    
    # Calcular confianza
    confianza = 50  # base
    
    # Alineación TF: +15 por cada TF alineado con bias
    if bias_visual == "BULL":
        confianza += bullish_count * 15
    elif bias_visual == "BEAR":
        confianza += bearish_count * 15
    
    # Score: +2 por punto sobre 14
    if score >= SCORE_MIN_CONFIRMACION:
        confianza += (score - SCORE_MIN_CONFIRMACION) * 2
    
    # Calidad de datos
    if dq == "OK":
        confianza += 10
    elif dq == "DEGRADED":
        confianza -= 10
    elif dq in ("STALE", "ERROR"):
        confianza -= 25
    
    # Funding extremo penaliza
    if funding_extremo:
        confianza -= 20
    
    # OBI confirma
    if obi_pressure == "COMPRA" and bias_visual == "BULL":
        confianza += 10
    elif obi_pressure == "VENTA" and bias_visual == "BEAR":
        confianza += 10
    
    # Clamp 0-100
    confianza = max(0, min(100, confianza))
    
    # Acción recomendada
    if bias_visual == "BULL" and confianza >= 70:
        accion = "COMPRAR"
    elif bias_visual == "BEAR" and confianza >= 70:
        accion = "VENDER"
    elif confianza >= 60:
        accion = "ESPERAR" if bias_visual == "RANGO" else "COMPRAR" if bias_visual == "BULL" else "VENDER"
    else:
        accion = "ESPERAR"
    
    # Razón clave (máximo 6-8 palabras)
    razones = []
    if bullish_count >= 2 and bias_visual == "BULL":
        razones.append(f"{bullish_count} TFs alineados")
    elif bearish_count >= 2 and bias_visual == "BEAR":
        razones.append(f"{bearish_count} TFs alineados")
    
    if funding_extremo:
        razones.append(f"Funding {funding_pct:+.3f}%")
    
    if obi_pressure in ("COMPRA", "VENTA"):
        razones.append(f"OBI {obi_pressure}")
    
    if score >= 16:
        razones.append(f"Score {score}/20")
    
    if not razones:
        razones.append("Sin confirmación")
    
    razon = " · ".join(razones[:2])
    
    return confianza, accion, razon


# -----------------------------------------------------------------------------
# Generación de niveles clave para Panel IA
# -----------------------------------------------------------------------------
def _generate_key_levels(z: Dict[str, Any]) -> List[str]:
    """
    Genera niveles clave justificados para el Panel IA.
    
    Returns:
        Lista de strings con niveles formateados.
    """
    levels = []
    
    precio = z.get("precio_ejecucion", 0.0)
    poc = z.get("poc", 0.0)
    vwap = z.get("vwap", 0.0)
    atr = z.get("atr_5m", 0.0)
    midpoint = z.get("midpoint_24h", 0.0)
    
    # Fractales 4H
    erl_highs = z.get("erl_swing_highs", [])
    erl_lows = z.get("erl_swing_lows", [])
    
    if poc > 0:
        levels.append(f"- Soporte inmediato: ${poc:,.2f} (POC 24h)")
    
    if erl_highs:
        nearest_high = erl_highs[0]
        levels.append(f"- Resistencia: ${nearest_high['price']:,.2f} (fractal 4H no-mitigado)")
    
    if erl_lows:
        nearest_low = erl_lows[0]
        levels.append(f"- Soporte clave: ${nearest_low['price']:,.2f} (swing low 4H)")
    
    if atr > 0 and precio > 0:
        target = precio + 1.8 * atr
        stop = precio - 1.0 * atr
        levels.append(f"- Target alcista: ${target:,.2f} (1.8× ATR desde entrada)")
        levels.append(f"- Stop loss: ${stop:,.2f} (1.0× ATR)")
    
    if vwap > 0:
        levels.append(f"- VWAP 24h: ${vwap:,.2f}")
    
    return levels


# -----------------------------------------------------------------------------
# Panel Trader
# -----------------------------------------------------------------------------
def _build_trader_panel(
    activos: List[str],
    gem: Dict[str, Dict[str, Any]],
    regimen: str,
    crypto: str,
    tradfi: str,
    quality_summary: str,
    timestamp: str,
) -> str:
    """
    Genera el HTML del Panel Trader (decisión rápida).
    """
    # Calcular confianza y acción para cada activo
    activos_evaluados = []
    for coin in activos:
        z = gem.get(coin, {}) or {}
        if not z or z.get("precio_ejecucion", 0) == 0:
            continue
        
        confianza, accion, razon = _calculate_confidence(z)
        activos_evaluados.append({
            "coin": coin,
            "precio": z.get("precio_ejecucion", 0.0),
            "score": z.get("macro_score", 0),
            "bias": z.get("bias_visual", "RANGO"),
            "confianza": confianza,
            "accion": accion,
            "razon": razon,
            "b1d": _bias_or_dash(z.get("bias_1d", "N/A")),
            "b4h": _bias_or_dash(z.get("bias_4h", "N/A")),
            "b1h": _bias_or_dash(z.get("bias_1h", "N/A")),
            "b15m": z.get("bias_15m", "RANGO"),
        })
    
    # Ordenar por confianza descendente
    activos_evaluados.sort(key=lambda x: x["confianza"], reverse=True)
    
    # TOP 5 con señales activas (confianza >= 60)
    top_activos = [a for a in activos_evaluados if a["confianza"] >= 60][:5]
    
    # Acciones inmediatas
    acciones_html = []
    for a in top_activos:
        accion = a["accion"]
        if accion == "COMPRAR":
            icon = "✅"
            cls = "bull"
        elif accion == "VENDER":
            icon = "❌"
            cls = "bear"
        else:
            icon = "⚠️"
            cls = "rango"
        
        acciones_html.append(
            f'<div class="accion {cls}">'
            f'{icon} {accion} {a["coin"]} '
            f'<span class="confianza">(confianza: {a["confianza"]}%)</span>'
            f'<div class="razon">• {a["razon"]}</div>'
            f'</div>'
        )
    
    if not acciones_html:
        acciones_html.append('<div class="accion rango">⚠️ ESPERAR — Sin señales activas</div>')
    
    # Tabla TOP oportunidades
    table_rows = []
    for a in top_activos:
        bias_cls = _classify_bias(a["bias"])
        row_cls = ""
        if a["accion"] == "COMPRAR":
            row_cls = "row-bull"
        elif a["accion"] == "VENDER":
            row_cls = "row-bear"
        
        table_rows.append(f"""
        <tr class="{row_cls}">
            <td><strong>{a['coin']}</strong></td>
            <td>${a['precio']:,.2f}</td>
            <td class="score">{a['score']}/20</td>
            <td class="{bias_cls}">{a['bias']}</td>
            <td>{a['b1d']} · {a['b4h']} · {a['b1h']}</td>
            <td>{a['razon']}</td>
            <td class="confianza-cell">{a['confianza']}%</td>
        </tr>
        """)
    
    table_html = ""
    if table_rows:
        table_html = f"""
        <table class="trader-table">
            <thead>
                <tr>
                    <th>Activo</th>
                    <th>Precio</th>
                    <th>Score</th>
                    <th>Bias</th>
                    <th>Alineación TF</th>
                    <th>Razón clave</th>
                    <th>Confianza</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
        """
    else:
        table_html = '<p class="no-data">Sin oportunidades activas en este momento.</p>'
    
    return f"""
    <div class="panel-trader">
        <div class="panel-header">
            <h1>🦅 DECISIÓN RÁPIDA</h1>
            <div class="timestamp">{timestamp}</div>
        </div>
        
        <div class="regimen-bar">
            <span class="regimen-item">RÉGIMEN: {_classify_html(regimen)}</span>
            <span class="regimen-item">CRYPTO: {_classify_html(crypto)}</span>
            <span class="regimen-item">TRADFI: {_classify_html(tradfi)}</span>
            <span class="regimen-item">CALIDAD: {quality_summary}</span>
        </div>
        
        <div class="acciones-section">
            <h2>🎯 ACCIÓN INMEDIATA:</h2>
            {''.join(acciones_html)}
        </div>
        
        <div class="tabla-section">
            <h2>TOP {len(top_activos)} OPORTUNIDADES:</h2>
            {table_html}
        </div>
        
        <div class="notas-trader">
            <p>⚠️ <strong>NOTAS:</strong></p>
            <ul>
                <li>Confianza ≥70% = señal fuerte · 60-69% = señal moderada · &lt;60% = esperar</li>
                <li>Alineación TF: 1D · 4H · 1H (— = no disponible)</li>
                <li>Score: 14-20 válido · &lt;14 = ruido</li>
                <li>Funding extremo (&gt;0.05%) penaliza confianza</li>
            </ul>
        </div>
    </div>
    """


# -----------------------------------------------------------------------------
# Panel IA
# -----------------------------------------------------------------------------
def _build_ia_panel(
    activos: List[str],
    gem: Dict[str, Dict[str, Any]],
    regimen: str,
    crypto: str,
    tradfi: str,
    timestamp: str,
) -> str:
    """
    Genera el contenido del Panel IA (Markdown estructurado).
    """
    lines = []
    lines.append(f"# CONTEXTO MACRO — {timestamp}")
    lines.append("")
    
    # Régimen global
    lines.append("## RÉGIMEN GLOBAL")
    lines.append(f"- Risk regime: {regimen}")
    lines.append(f"- Crypto bias: {crypto} | TradFi bias: {tradfi}")
    
    # Markov si disponible
    markov = gem.get("__markov__", {})
    if markov:
        p_caos = markov.get("p_caos_max", 0)
        lines.append(f"- Markov p_caos: {p_caos:.2f} (probabilidad caos: {'ALTA' if p_caos > 0.5 else 'BAJA'})")
    
    lines.append("")
    
    # Clasificar activos
    senales_activas = []
    en_espera = []
    alertas_riesgo = []
    
    for coin in activos:
        z = gem.get(coin, {}) or {}
        if not z:
            continue
        
        confianza, accion, razon = _calculate_confidence(z)
        bias = z.get("bias_visual", "RANGO")
        score = z.get("macro_score", 0)
        
        # Verificar alertas de riesgo
        fmap = z.get("funding", {}) or {}
        funding_pct = fmap.get("funding_pct", 0.0)
        obi_pressure = z.get("ctx25_obi_pressure", "")
        
        if abs(funding_pct) > FUNDING_EXTREMO_PCT or (bias == "BEAR" and obi_pressure == "VENTA"):
            alertas_riesgo.append((coin, z, confianza))
        elif confianza >= 60 and bias in ("BULL", "BEAR"):
            senales_activas.append((coin, z, confianza, accion))
        else:
            en_espera.append((coin, z))
    
    # Señales activas
    if senales_activas:
        lines.append("## ACTIVOS CON SEÑAL ACTIVA")
        lines.append("")
        
        for coin, z, confianza, accion in senales_activas:
            direccion = "LONG" if z.get("bias_visual") == "BULL" else "SHORT"
            lines.append(f"### {coin} ({direccion} - confianza {confianza}%)")
            lines.append("")
            
            # Multi-timeframe
            lines.append("**Multi-timeframe:**")
            b1d = _bias_or_dash(z.get("bias_1d", "N/A"))
            b4h = _bias_or_dash(z.get("bias_4h", "N/A"))
            b1h = _bias_or_dash(z.get("bias_1h", "N/A"))
            b15m = z.get("bias_15m", "RANGO")
            fuerza = z.get("fuerza_15m", 0)
            
            lines.append(f"- 1D: {b1d}")
            lines.append(f"- 4H: {b4h}")
            lines.append(f"- 1H: {b1h}")
            lines.append(f"- 15m: {b15m} (fuerza: {fuerza}/3)")
            lines.append("")
            
            # Microestructura
            lines.append("**Microestructura:**")
            fmap = z.get("funding", {}) or {}
            funding_pct = fmap.get("funding_pct", 0.0)
            oi = fmap.get("open_interest", 0)
            obi = z.get("ctx25_obi_100")
            delta_oi = z.get("ctx25_delta_oi_pct")
            poc = z.get("poc", 0.0)
            vwap = z.get("vwap", 0.0)
            
            if obi is not None:
                lines.append(f"- OBI: {obi:.0f}/100 ({z.get('ctx25_obi_pressure', 'N/A')})")
            if funding_pct != 0:
                lines.append(f"- Funding: {funding_pct:+.4f}% ({'extremo' if abs(funding_pct) > FUNDING_EXTREMO_PCT else 'normal'})")
            if delta_oi is not None:
                lines.append(f"- Delta OI: {delta_oi:+.2f}%")
            if oi > 0:
                lines.append(f"- Open Interest: {oi:,.0f}")
            if poc > 0:
                lines.append(f"- POC 24h: ${poc:,.2f} | VWAP: ${vwap:,.2f}")
            lines.append("")
            
            # Niveles clave
            key_levels = _generate_key_levels(z)
            if key_levels:
                lines.append("**Niveles clave:**")
                lines.extend(key_levels)
                lines.append("")
            
            # Calidad datos
            dq = z.get("data_quality_status", "UNKNOWN")
            lines.append(f"**Calidad datos:** {'✅' if dq == 'OK' else '⚠️'} {dq}")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # En espera
    if en_espera:
        lines.append("## ACTIVOS EN ESPERA (RANGO)")
        for coin, z in en_espera:
            precio = z.get("precio_ejecucion", 0.0)
            poc = z.get("poc", 0.0)
            vwap = z.get("vwap", 0.0)
            fmap = z.get("funding", {}) or {}
            funding_pct = fmap.get("funding_pct", 0.0)
            
            reason = "RANGO" if z.get("bias_visual") == "RANGO" else "Sin confirmación suficiente"
            if abs(funding_pct) > FUNDING_SEGURO_PCT:
                reason = f"Funding {funding_pct:+.4f}% (evitar)"
            
            lines.append(f"- {coin}: ${precio:,.2f} — {reason}")
        lines.append("")
    
    # Alertas de riesgo
    if alertas_riesgo:
        lines.append("## ACTIVOS CON ALERTA DE RIESGO")
        for coin, z, confianza in alertas_riesgo:
            fmap = z.get("funding", {}) or {}
            funding_pct = fmap.get("funding_pct", 0.0)
            obi = z.get("ctx25_obi_100")
            
            alertas = []
            if abs(funding_pct) > FUNDING_EXTREMO_PCT:
                alertas.append(f"Funding extremo {funding_pct:+.4f}%")
            if z.get("bias_visual") == "BEAR" and z.get("ctx25_obi_pressure") == "VENTA":
                alertas.append("OBI venta + bias BEAR → posible dump")
            
            lines.append(f"- {coin}: {' + '.join(alertas)}")
        lines.append("")
    
    # Preguntas sugeridas
    lines.append("## PREGUNTAS SUGERIDAS PARA IA:")
    lines.append("1. ¿El régimen global actual favorece operaciones de tendencia o rango?")
    
    if senales_activas:
        top_coin = senales_activas[0][0]
        lines.append(f"2. ¿{top_coin} puede sostener el movimiento con funding actual?")
    
    lines.append("3. ¿Hay divergencias entre crypto y TradFi que alerten riesgo sistémico?")
    lines.append("")
    
    # Convertir a HTML con formato pre
    markdown_html = "<br>".join(_escape(line) if line else "&nbsp;" for line in lines)
    
    return f"""
    <div class="panel-ia">
        <div class="panel-header">
            <h1>📋 ANÁLISIS COMPLETO (para IA)</h1>
            <p class="subtitle">Copiar contenido para análisis con IA</p>
        </div>
        <div class="markdown-content">
            <pre>{markdown_html}</pre>
        </div>
    </div>
    """


# -----------------------------------------------------------------------------
# Calidad de datos (resumen simplificado)
# -----------------------------------------------------------------------------
def _aggregate_meta(activos: list, macro_tf_meta: dict, liq_zones_meta: dict) -> Tuple[Dict, List[str]]:
    """Agrega _MACRO_TF_META y _LIQ_ZONES_META en una vista unificada por activo."""
    per_asset: Dict[str, Dict] = {}
    warnings_list: List[str] = []

    for coin in activos:
        coin_data: Dict[str, Any] = {"warnings": []}

        for (c, tf), meta in (macro_tf_meta or {}).items():
            if c != coin:
                continue
            if not isinstance(meta, dict):
                continue
            coin_data[tf] = meta
            w = meta.get("warning")
            if w and w not in coin_data["warnings"]:
                coin_data["warnings"].append(w)

        meta_5m = (liq_zones_meta or {}).get(coin)
        if isinstance(meta_5m, dict):
            coin_data["5m"] = meta_5m
            w = meta_5m.get("warning")
            if w and w not in coin_data["warnings"]:
                coin_data["warnings"].append(w)

        per_asset[coin] = coin_data

        for w in coin_data["warnings"]:
            entry = f"{coin}: {w}"
            if entry not in warnings_list:
                warnings_list.append(entry)

    return per_asset, warnings_list


def _classify_meta_status(meta: Dict) -> str:
    """Devuelve el peor estado entre data_quality y candle_status."""
    if not isinstance(meta, dict):
        return "UNKNOWN"
    dq = (meta.get("data_quality") or "").upper()
    cs = (meta.get("candle_status") or "").upper()
    if dq == "ERROR" or cs == "ERROR":
        return "ERROR"
    if dq == "STALE":
        return "STALE"
    if dq == "DEGRADED" or cs in ("DEGRADED", "INSUFFICIENT", "FORMING"):
        return "DEGRADED"
    if dq == "OK" or cs in ("CLOSED", "OK"):
        return "OK"
    if dq or cs:
        return dq or cs
    return "UNKNOWN"


def _build_quality_summary(per_asset: Dict) -> str:
    """Construye resumen de calidad de 1 línea."""
    counts = {"OK": 0, "DEGRADED": 0, "STALE": 0, "ERROR": 0, "UNKNOWN": 0}
    SEVERITY = {"ERROR": 0, "STALE": 1, "DEGRADED": 2, "OK": 3, "UNKNOWN": 4, "": 4}

    for coin, data in per_asset.items():
        worst_idx = 99
        worst_label = "UNKNOWN"
        for tf, meta in data.items():
            if tf == "warnings":
                continue
            if not isinstance(meta, dict):
                continue
            status = _classify_meta_status(meta)
            idx = SEVERITY.get(status, 4)
            if idx < worst_idx:
                worst_idx = idx
                worst_label = status
        if worst_label in counts:
            counts[worst_label] += 1
        else:
            counts["UNKNOWN"] += 1

    if counts["ERROR"] > 0:
        return f"❌ ERROR ({counts['ERROR']})"
    if counts["STALE"] > 0:
        return f"⚠️ STALE ({counts['STALE']})"
    if counts["DEGRADED"] > 0:
        return f"⚠️ DEGRADED ({counts['DEGRADED']})"
    if counts["OK"] > 0:
        return f"✅ OK ({counts['OK']})"
    return "⚪ UNKNOWN"


# -----------------------------------------------------------------------------
# Template HTML principal
# -----------------------------------------------------------------------------
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦅 mercabot_qwen — Reporte Macro v3.0</title>
    <style>
        :root {{
            --bg: #f5f5f5;
            --fg: #1a1a1a;
            --panel-bg: #ffffff;
            --border: #ddd;
            --bull: #d4edda;
            --bull-text: #155724;
            --bear: #f8d7da;
            --bear-text: #721c24;
            --rango: #fff3cd;
            --rango-text: #856404;
            --neutral: #e2e3e5;
        }}
        
        [data-theme="dark"] {{
            --bg: #1a1a2e;
            --fg: #eaeaea;
            --panel-bg: #16213e;
            --border: #444;
            --bull: #1b4332;
            --bull-text: #95d5b2;
            --bear: #461220;
            --bear-text: #f8d7da;
            --rango: #4a4000;
            --rango-text: #ffd700;
            --neutral: #333;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            font-size: 18px;
            line-height: 1.6;
            background: var(--bg);
            color: var(--fg);
            padding: 2em;
        }}
        
        .panel-trader, .panel-ia {{
            background: var(--panel-bg);
            border-radius: 12px;
            padding: 2em;
            margin-bottom: 3em;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5em;
            padding-bottom: 0.5em;
            border-bottom: 2px solid var(--border);
        }}
        
        .panel-header h1 {{
            font-size: 1.8em;
            font-weight: 700;
        }}
        
        .timestamp {{
            font-size: 0.9em;
            opacity: 0.7;
        }}
        
        .regimen-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5em;
            margin-bottom: 1.5em;
            font-size: 1.1em;
            font-weight: 600;
        }}
        
        .regimen-item {{
            padding: 0.3em 0.8em;
            border-radius: 6px;
            background: var(--neutral);
        }}
        
        .acciones-section h2, .tabla-section h2 {{
            font-size: 1.3em;
            margin-bottom: 0.8em;
        }}
        
        .accion {{
            font-size: 1.2em;
            font-weight: 700;
            padding: 0.8em 1em;
            margin-bottom: 0.5em;
            border-radius: 8px;
        }}
        
        .accion.bull {{ background: var(--bull); color: var(--bull-text); }}
        .accion.bear {{ background: var(--bear); color: var(--bear-text); }}
        .accion.rango {{ background: var(--rango); color: var(--rango-text); }}
        
        .accion .confianza {{
            font-weight: 400;
            font-size: 0.9em;
            opacity: 0.8;
        }}
        
        .accion .razon {{
            font-size: 0.85em;
            font-weight: 400;
            margin-top: 0.3em;
            opacity: 0.7;
        }}
        
        .trader-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 1em;
        }}
        
        .trader-table th {{
            background: var(--neutral);
            padding: 0.8em;
            text-align: left;
            font-weight: 700;
            border-bottom: 2px solid var(--border);
        }}
        
        .trader-table td {{
            padding: 0.8em;
            border-bottom: 1px solid var(--border);
        }}
        
        .trader-table .score {{
            font-weight: 700;
            font-size: 1.1em;
        }}
        
        .trader-table .confianza-cell {{
            font-weight: 700;
            font-size: 1.1em;
        }}
        
        .row-bull {{ background: var(--bull); }}
        .row-bear {{ background: var(--bear); }}
        
        .bull {{ color: var(--bull-text); font-weight: 700; }}
        .bear {{ color: var(--bear-text); font-weight: 700; }}
        .rango {{ color: var(--rango-text); font-weight: 700; }}
        .neutral {{ opacity: 0.6; }}
        .squeeze {{ color: #ff6b35; font-weight: 700; }}
        
        .notas-trader {{
            margin-top: 1.5em;
            padding: 1em;
            background: var(--neutral);
            border-radius: 8px;
            font-size: 0.9em;
        }}
        
        .notas-trader ul {{
            margin-left: 1.5em;
            margin-top: 0.5em;
        }}
        
        .panel-ia .subtitle {{
            font-size: 0.9em;
            opacity: 0.6;
        }}
        
        .markdown-content {{
            background: var(--neutral);
            padding: 1.5em;
            border-radius: 8px;
            overflow-x: auto;
        }}
        
        .markdown-content pre {{
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.95em;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        
        .no-data {{
            padding: 1em;
            text-align: center;
            opacity: 0.6;
        }}
        
        .theme-toggle {{
            position: fixed;
            top: 1em;
            right: 1em;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.5em 1em;
            cursor: pointer;
            font-size: 1.2em;
            z-index: 100;
        }}
        
        hr {{
            border: none;
            border-top: 3px solid var(--border);
            margin: 3em 0;
        }}
        
        .footer {{
            text-align: center;
            font-size: 0.85em;
            opacity: 0.6;
            margin-top: 2em;
        }}
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
    
    {panel_trader}

    <hr>

    {panel_ia}

    <hr>

    <div class="panel-ia">
        <div class="panel-header">
            <h1>📜 EVOLUCIÓN DEL MACRO (snapshot por ciclo)</h1>
            <p class="subtitle">Último contexto macro registrado por activo</p>
        </div>
        <div class="markdown-content">
            <pre>{EVOLUCION_MACRO_HTML}</pre>
        </div>
    </div>

    <div class="footer">
        Reporte generado por reporter.py v3.0 · Click en 🌓 para alternar tema.
    </div>
    
    <script>
        function toggleTheme() {{
            const body = document.body;
            const current = body.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            body.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        }}
        
        // Restaurar tema guardado
        const saved = localStorage.getItem('theme');
        if (saved) {{
            document.body.setAttribute('data-theme', saved);
        }} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {{
            document.body.setAttribute('data-theme', 'dark');
        }}
    </script>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def mostrar_reporte(ns: dict) -> Optional[str]:
    """
    Genera `reporte_macro.html` con Panel Trader + Panel IA.
    Lo abre en el browser default.

    Returns:
        Path al HTML generado, o None si faltan datos.
    """
    gem = ns.get("GEM_MACRO_CONTEXT", {}) or {}
    cp = ns.get("CENTRAL_PARAMS", {}) or {}
    activos = ns.get("ALL_ASSETS", []) or list(gem.keys())

    if not gem:
        print("⚠️  reporter: GEM_MACRO_CONTEXT está vacío. ¿Corrió la C3?")
        return None

    # Metadata
    config = ns.get("CONFIG")
    tz_name = getattr(config, "TZ_NAME", "UTC") if config else "UTC"
    try:
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Conclusión y régimen
    conclusion = ns.get("MACRO_CONCLUSION", {}) or {}
    tradfi = conclusion.get("TRADFI", "N/A")
    crypto = conclusion.get("CRYPTO", "N/A")
    regimen = ns.get("GLOBAL_RISK_REGIME", "N/A")
    
    # Markov para panel IA
    markov = ns.get("GLOBAL_MARKOV_STATE", {}) or {}
    if markov:
        gem["__markov__"] = markov

    # Calidad de datos
    macro_tf_meta = ns.get("_MACRO_TF_META", {}) or {}
    liq_zones_meta = ns.get("_LIQ_ZONES_META", {}) or {}
    per_asset, warnings_list = _aggregate_meta(activos, macro_tf_meta, liq_zones_meta)
    quality_summary = _build_quality_summary(per_asset)

    # Generar paneles
    panel_trader = _build_trader_panel(
        activos=activos,
        gem=gem,
        regimen=regimen,
        crypto=crypto,
        tradfi=tradfi,
        quality_summary=quality_summary,
        timestamp=ts,
    )
    
    panel_ia = _build_ia_panel(
        activos=activos,
        gem=gem,
        regimen=regimen,
        crypto=crypto,
        tradfi=tradfi,
        timestamp=ts,
    )

    # Generar tabla de evolución del macro (snapshot por activo del último ciclo)
    evolucion_html = "<b>Último snapshot registrado:</b>\n\n"
    try:
        import sqlite3 as _sqlite3
        _db_path = PROJECT_ROOT / "data" / "vault_v2.db"
        if _db_path.exists():
            _conn = _sqlite3.connect(str(_db_path), timeout=5.0)
            try:
                _rows = _conn.execute(
                    """SELECT coin, bias_visual, regime, regime_confidence, macro_score, funding_pct, data_quality
                       FROM gem_macro_snapshot
                       WHERE id IN (SELECT MAX(id) FROM gem_macro_snapshot WHERE cycle_id != 'PRE_REGIME' GROUP BY coin)
                       ORDER BY coin"""
                ).fetchall()
                if _rows:
                    evolucion_html += f"{'ACTIVO':<10} {'BIAS':<8} {'REGIMEN':<14} {'CONF':>6} {'SCORE':>6} {'FUNDING':>10} {'DQ':<10}\n"
                    evolucion_html += f"{'-'*10} {'-'*8} {'-'*14} {'-'*6} {'-'*6} {'-'*10} {'-'*10}\n"
                    for _coin, _bv, _rg, _cf, _sc, _fp, _dq in _rows:
                        evolucion_html += (
                            f"{_coin:<10} "
                            f"{(_bv or '—'):<8} "
                            f"{(_rg or '—'):<14} "
                            f"{(f'{_cf:.1f}' if _cf else '—'):>6} "
                            f"{(_sc if _sc is not None else '—'):>6} "
                            f"{(f'{_fp:+.4f}%' if _fp is not None else '—'):>10} "
                            f"{(_dq or '—'):<10}\n"
                        )
                else:
                    evolucion_html += "\n(Sin datos todavía — el snapshot se llena con cada ciclo)\n"
            finally:
                _conn.close()
        else:
            evolucion_html += "\n(DB no encontrada)\n"
    except Exception as _e:
        evolucion_html += f"\n(Error leyendo gem_macro_snapshot: {_e})\n"

    # Renderizar HTML final
    html = _HTML_TEMPLATE.format(
        panel_trader=panel_trader,
        panel_ia=panel_ia,
        EVOLUCION_MACRO_HTML=evolucion_html,
    )

    # Guardar
    try:
        REPORTE_DIR.mkdir(parents=True, exist_ok=True)
        with open(REPORTE_PATH, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError as e:
        print(f"❌ reporter: no se pudo escribir {REPORTE_PATH}: {e}")
        return None

    # Abrir en el browser
    url = f"file:///{REPORTE_PATH.as_posix()}"
    try:
        opened = webbrowser.open(url)
        if opened:
            print(f"✅ Reporte v3.0 generado: {REPORTE_PATH}")
            print(f"   🌐 Abierto en el browser: {url}")
        else:
            print(f"✅ Reporte v3.0 generado: {REPORTE_PATH}")
            print(f"   ⚠️  No se pudo abrir el browser automáticamente.")
            print(f"   👉 Abrí manualmente: {url}")
    except Exception as e:
        print(f"✅ Reporte v3.0 generado: {REPORTE_PATH}")
        print(f"   ❌ Error abriendo browser: {e}")
        print(f"   👉 Abrí manualmente: {url}")

    return str(REPORTE_PATH)


# -----------------------------------------------------------------------------
# Auto-test si se ejecuta directamente
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("reporter.py es un módulo. Usalo desde main.py con --reporte.")
    print("Para probar: python main.py --solo-c3 --reporte")