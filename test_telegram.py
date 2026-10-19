#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba local para la notificación de Telegram.
v2.0: Doble envío diario (8 AM y 5 PM) + métricas de salud + desgloses v2
- Métricas de rendimiento completas (PF, PnL, Expectancy, DD)
- Desglose LONG/SHORT
- Validación v2 (OOS) por tipo de señal
- Desglose por clase de activo (Crypto vs TradFi)
- Comparación legacy vs v2
- Métricas de salud del sistema (errores, señales inválidas, régimen desconocido)
No modifica nada, solo lee la DB local y envía un mensaje.
"""
import os
import sqlite3
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path
from datetime import datetime

# 1. Cargar variables del archivo .env manualmente (sin dependencias extra)
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"\'')

PROJECT_ROOT = Path(__file__).resolve().parent
DB_FILE = PROJECT_ROOT / "data" / "vault_v2.db"


def test_telegram_notification():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ ERROR: Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en el archivo .env")
        return
    
    if not DB_FILE.exists():
        print(f"❌ ERROR: No se encuentra la base de datos en {DB_FILE}")
        print("   Ejecuta 'python main.py --celdas 4' primero para generar datos.")
        return
    
    try:
        print("🔌 Conectando a la base de datos local...")
        conn = sqlite3.connect(str(DB_FILE), timeout=5.0)
        
        # ─── 1. Conteos básicos ───
        total_senales = conn.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
        resueltas_4h = conn.execute("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_4h = 1").fetchone()[0]
        resueltas_24h = conn.execute("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_24h = 1").fetchone()[0]
        snapshots = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        
        try:
            regimenes = conn.execute("SELECT COUNT(*) FROM gem_macro_snapshot").fetchone()[0]
        except sqlite3.OperationalError:
            regimenes = 0
        
        # ─── 2. Hit Rates ───
        hr_4h_data = conn.execute(
            "SELECT SUM(hit_4h), COUNT(*) FROM senales_validadas WHERE resuelto_4h = 1"
        ).fetchone()
        hr_4h = (hr_4h_data[0] / hr_4h_data[1] * 100) if hr_4h_data[1] and hr_4h_data[1] > 0 else 0.0
        wins_4h = hr_4h_data[0] or 0
        
        hr_24h_data = conn.execute(
            "SELECT SUM(hit_24h), COUNT(*) FROM senales_validadas WHERE resuelto_24h = 1"
        ).fetchone()
        hr_24h = (hr_24h_data[0] / hr_24h_data[1] * 100) if hr_24h_data[1] and hr_24h_data[1] > 0 else 0.0
        wins_24h = hr_24h_data[0] or 0
        
        # ─── 3. Métricas de rentabilidad (24h) ───
        pnl_data = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        
        if pnl_data:
            pnls = [row[0] for row in pnl_data]
            avg_pnl = sum(pnls) / len(pnls)
            
            # Profit Factor
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
                float("inf") if gross_profit > 0 else 0.0
            )
            if profit_factor == float("inf"):
                profit_factor = 999.0
            
            # Expectancy
            expectancy = avg_pnl * (hr_24h / 100)
            
            # Max Drawdown (simplificado)
            cumulative = []
            running_sum = 0
            for p in pnls:
                running_sum += p
                cumulative.append(running_sum)
            
            if cumulative:
                peak = cumulative[0]
                max_dd = 0
                for val in cumulative:
                    if val > peak:
                        peak = val
                    dd = peak - val
                    if dd > max_dd:
                        max_dd = dd
            else:
                max_dd = 0
        else:
            avg_pnl = 0.0
            profit_factor = 0.0
            expectancy = 0.0
            max_dd = 0.0
        
        # ─── 4. Desglose LONG vs SHORT (24h) ───
        long_data = conn.execute(
            """
            SELECT COUNT(*), SUM(hit_24h)
            FROM senales_validadas
            WHERE resuelto_24h = 1 AND tipo_senal = 'LONG'
            """
        ).fetchone()
        
        short_data = conn.execute(
            """
            SELECT COUNT(*), SUM(hit_24h)
            FROM senales_validadas
            WHERE resuelto_24h = 1 AND tipo_senal = 'SHORT'
            """
        ).fetchone()
        
        # LONG metrics
        long_total = long_data[0] if long_data and long_data[0] else 0
        long_hits = long_data[1] if long_data and long_data[1] else 0
        long_hr = (long_hits / long_total * 100) if long_total > 0 else 0.0
        
        long_pnls = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND tipo_senal = 'LONG' AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        
        if long_pnls:
            long_gp = sum(row[0] for row in long_pnls if row[0] > 0)
            long_gl = abs(sum(row[0] for row in long_pnls if row[0] < 0))
            long_pf = long_gp / long_gl if long_gl > 0 else (999.0 if long_gp > 0 else 0.0)
        else:
            long_pf = 0.0
        
        # SHORT metrics
        short_total = short_data[0] if short_data and short_data[0] else 0
        short_hits = short_data[1] if short_data and short_data[1] else 0
        short_hr = (short_hits / short_total * 100) if short_total > 0 else 0.0
        
        short_pnls = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND tipo_senal = 'SHORT' AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        
        if short_pnls:
            short_gp = sum(row[0] for row in short_pnls if row[0] > 0)
            short_gl = abs(sum(row[0] for row in short_pnls if row[0] < 0))
            short_pf = short_gp / short_gl if short_gl > 0 else (999.0 if short_gp > 0 else 0.0)
        else:
            short_pf = 0.0
        
        # ─── 5. Validación v2 (OOS) por tipo de señal (24h) ───
        try:
            # FUERTE LONG
            fuerte_long = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE' AND tipo_senal = 'LONG'"""
            ).fetchone()
            fuerte_long_total = fuerte_long[0] if fuerte_long and fuerte_long[0] else 0
            fuerte_long_hits = fuerte_long[1] if fuerte_long and fuerte_long[1] else 0
            fuerte_long_hr = (fuerte_long_hits / fuerte_long_total * 100) if fuerte_long_total > 0 else 0.0
            
            fuerte_long_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE' AND tipo_senal = 'LONG' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if fuerte_long_pnls:
                fl_gp = sum(r[0] for r in fuerte_long_pnls if r[0] > 0)
                fl_gl = abs(sum(r[0] for r in fuerte_long_pnls if r[0] < 0))
                fuerte_long_pf = fl_gp / fl_gl if fl_gl > 0 else (999.0 if fl_gp > 0 else 0.0)
            else:
                fuerte_long_pf = 0.0
            
            # FUERTE SHORT
            fuerte_short = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE' AND tipo_senal = 'SHORT'"""
            ).fetchone()
            fuerte_short_total = fuerte_short[0] if fuerte_short and fuerte_short[0] else 0
            fuerte_short_hits = fuerte_short[1] if fuerte_short and fuerte_short[1] else 0
            fuerte_short_hr = (fuerte_short_hits / fuerte_short_total * 100) if fuerte_short_total > 0 else 0.0
            
            fuerte_short_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE' AND tipo_senal = 'SHORT' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if fuerte_short_pnls:
                fs_gp = sum(r[0] for r in fuerte_short_pnls if r[0] > 0)
                fs_gl = abs(sum(r[0] for r in fuerte_short_pnls if r[0] < 0))
                fuerte_short_pf = fs_gp / fs_gl if fs_gl > 0 else (999.0 if fs_gp > 0 else 0.0)
            else:
                fuerte_short_pf = 0.0
            
            # MODERADA LONG
            moderada_long = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'MODERADA' AND tipo_senal = 'LONG'"""
            ).fetchone()
            moderada_long_total = moderada_long[0] if moderada_long and moderada_long[0] else 0
            moderada_long_hits = moderada_long[1] if moderada_long and moderada_long[1] else 0
            moderada_long_hr = (moderada_long_hits / moderada_long_total * 100) if moderada_long_total > 0 else 0.0
            
            moderada_long_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'MODERADA' AND tipo_senal = 'LONG' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if moderada_long_pnls:
                ml_gp = sum(r[0] for r in moderada_long_pnls if r[0] > 0)
                ml_gl = abs(sum(r[0] for r in moderada_long_pnls if r[0] < 0))
                moderada_long_pf = ml_gp / ml_gl if ml_gl > 0 else (999.0 if ml_gp > 0 else 0.0)
            else:
                moderada_long_pf = 0.0
            
            # MODERADA SHORT
            moderada_short = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'MODERADA' AND tipo_senal = 'SHORT'"""
            ).fetchone()
            moderada_short_total = moderada_short[0] if moderada_short and moderada_short[0] else 0
            moderada_short_hits = moderada_short[1] if moderada_short and moderada_short[1] else 0
            moderada_short_hr = (moderada_short_hits / moderada_short_total * 100) if moderada_short_total > 0 else 0.0
            
            moderada_short_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'MODERADA' AND tipo_senal = 'SHORT' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if moderada_short_pnls:
                ms_gp = sum(r[0] for r in moderada_short_pnls if r[0] > 0)
                ms_gl = abs(sum(r[0] for r in moderada_short_pnls if r[0] < 0))
                moderada_short_pf = ms_gp / ms_gl if ms_gl > 0 else (999.0 if ms_gp > 0 else 0.0)
            else:
                moderada_short_pf = 0.0
            
        except sqlite3.OperationalError:
            # Fallback si las columnas v2 no existen
            fuerte_long_total = fuerte_long_hr = fuerte_long_pf = 0
            fuerte_short_total = fuerte_short_hr = fuerte_short_pf = 0
            moderada_long_total = moderada_long_hr = moderada_long_pf = 0
            moderada_short_total = moderada_short_hr = moderada_short_pf = 0
        
        # ─── 6. v2 por clase de activo (24h) ───
        try:
            # Crypto
            crypto_data = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND activo NOT LIKE 'xyz:%'"""
            ).fetchone()
            crypto_total = crypto_data[0] if crypto_data and crypto_data[0] else 0
            crypto_hits = crypto_data[1] if crypto_data and crypto_data[1] else 0
            crypto_hr = (crypto_hits / crypto_total * 100) if crypto_total > 0 else 0.0
            
            crypto_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND activo NOT LIKE 'xyz:%' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if crypto_pnls:
                c_gp = sum(r[0] for r in crypto_pnls if r[0] > 0)
                c_gl = abs(sum(r[0] for r in crypto_pnls if r[0] < 0))
                crypto_pf = c_gp / c_gl if c_gl > 0 else (999.0 if c_gp > 0 else 0.0)
            else:
                crypto_pf = 0.0
            
            # TradFi
            tradfi_data = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND activo LIKE 'xyz:%'"""
            ).fetchone()
            tradfi_total = tradfi_data[0] if tradfi_data and tradfi_data[0] else 0
            tradfi_hits = tradfi_data[1] if tradfi_data and tradfi_data[1] else 0
            tradfi_hr = (tradfi_hits / tradfi_total * 100) if tradfi_total > 0 else 0.0
            
            tradfi_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND activo LIKE 'xyz:%' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if tradfi_pnls:
                t_gp = sum(r[0] for r in tradfi_pnls if r[0] > 0)
                t_gl = abs(sum(r[0] for r in tradfi_pnls if r[0] < 0))
                tradfi_pf = t_gp / t_gl if t_gl > 0 else (999.0 if t_gp > 0 else 0.0)
            else:
                tradfi_pf = 0.0
            
        except sqlite3.OperationalError:
            crypto_total = crypto_hr = crypto_pf = 0
            tradfi_total = tradfi_hr = tradfi_pf = 0
        
        # ─── 7. Comparación legacy vs v2 (24h) ───
        try:
            # Legacy ALTA/BAJA
            legacy_data = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal IN ('ALTA', 'BAJA')"""
            ).fetchone()
            legacy_total = legacy_data[0] if legacy_data and legacy_data[0] else 0
            legacy_hits = legacy_data[1] if legacy_data and legacy_data[1] else 0
            legacy_hr = (legacy_hits / legacy_total * 100) if legacy_total > 0 else 0.0
            
            legacy_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal IN ('ALTA', 'BAJA') AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if legacy_pnls:
                l_gp = sum(r[0] for r in legacy_pnls if r[0] > 0)
                l_gl = abs(sum(r[0] for r in legacy_pnls if r[0] < 0))
                legacy_pf = l_gp / l_gl if l_gl > 0 else (999.0 if l_gp > 0 else 0.0)
            else:
                legacy_pf = 0.0
            
            # v2 FUERTE
            v2_fuerte_data = conn.execute(
                """SELECT COUNT(*), SUM(hit_24h) FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE'"""
            ).fetchone()
            v2_fuerte_total = v2_fuerte_data[0] if v2_fuerte_data and v2_fuerte_data[0] else 0
            v2_fuerte_hits = v2_fuerte_data[1] if v2_fuerte_data and v2_fuerte_data[1] else 0
            v2_fuerte_hr = (v2_fuerte_hits / v2_fuerte_total * 100) if v2_fuerte_total > 0 else 0.0
            
            v2_fuerte_pnls = conn.execute(
                """SELECT pnl_pct_24h FROM senales_validadas 
                   WHERE resuelto_24h = 1 AND calidad_senal_v2 = 'FUERTE' AND pnl_pct_24h IS NOT NULL"""
            ).fetchall()
            if v2_fuerte_pnls:
                v2_gp = sum(r[0] for r in v2_fuerte_pnls if r[0] > 0)
                v2_gl = abs(sum(r[0] for r in v2_fuerte_pnls if r[0] < 0))
                v2_fuerte_pf = v2_gp / v2_gl if v2_gl > 0 else (999.0 if v2_gp > 0 else 0.0)
            else:
                v2_fuerte_pf = 0.0
            
        except sqlite3.OperationalError:
            legacy_total = legacy_hr = legacy_pf = 0
            v2_fuerte_total = v2_fuerte_hr = v2_fuerte_pf = 0
        
        # ─── 8. Métricas de salud del sistema (24h) ───
        ahora_unix = int(time.time())
        hace_24h = ahora_unix - 86400
        
        # Errores en últimas 24h
        try:
            errores_24h = conn.execute(
                "SELECT COUNT(*) FROM logs_errores WHERE timestamp_unix > ?",
                (hace_24h,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            errores_24h = 0
        
        # Señales v2 inválidas (últimas 24h)
        try:
            v2_invalidas = conn.execute(
                """SELECT COUNT(*) FROM senales_validadas 
                   WHERE timestamp_emision > ? 
                   AND (macro_score_v2 IS NULL OR macro_score_v2 = 0.0)""",
                (hace_24h,)
            ).fetchone()[0]
            
            v2_total_24h = conn.execute(
                "SELECT COUNT(*) FROM senales_validadas WHERE timestamp_emision > ?",
                (hace_24h,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            v2_invalidas = 0
            v2_total_24h = 0
        
        # Régimen desconocido (últimas 24h)
        try:
            regimen_unknown = conn.execute(
                """SELECT COUNT(*) FROM senales_validadas 
                   WHERE timestamp_emision > ? AND regime_state = 'UNKNOWN'""",
                (hace_24h,)
            ).fetchone()[0]
            
            total_24h = conn.execute(
                "SELECT COUNT(*) FROM senales_validadas WHERE timestamp_emision > ?",
                (hace_24h,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            regimen_unknown = 0
            total_24h = 0
        
        # Edad de la última señal
        try:
            ultima_senal_ts = conn.execute(
                "SELECT MAX(timestamp_emision) FROM senales_validadas"
            ).fetchone()[0]
            edad_ultima_senal = (ahora_unix - ultima_senal_ts) / 3600 if ultima_senal_ts else 999
        except sqlite3.OperationalError:
            edad_ultima_senal = 999
        
        conn.close()
        
        # ─── 9. Formatear mensaje ───
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        mensaje = (
        f"🦅 *mercabot_qwen* | Resumen de PRUEBA LOCAL\n"
        f"📅 {ahora} Caracas\n\n"
        f"📊 *Datos acumulados:*\n"
        f"• Señales registradas: {total_senales}\n"
        f"• Señales resueltas (4h): {resueltas_4h}\n"
        f"• Señales resueltas (24h): {resueltas_24h}\n"
        f"• Snapshots de precio: {snapshots:,}\n"
        f"• Estados de régimen: {regimenes:,}\n\n"
        f"🎯 *Hit rate (resueltas):*\n"
        f"• Ventana 4h: {hr_4h:.1f}% ({wins_4h}/{resueltas_4h})\n"
        f"• Ventana 24h: {hr_24h:.1f}% ({wins_24h}/{resueltas_24h})\n\n"
        f"💰 *Rentabilidad (24h):*\n"
        f"• Profit Factor: {profit_factor:.2f}\n"
        f"• PnL promedio: {avg_pnl:.2f}%\n"
        f"• Expectancy: {expectancy:.2f}% por trade\n"
        f"• Max Drawdown: {max_dd:.2f}%\n\n"
        f"📈 *Desglose LONG vs SHORT (24h):*\n"
        f"• LONG: HR {long_hr:.1f}% | PF {long_pf:.2f} | {long_total} señales\n"
        f"• SHORT: HR {short_hr:.1f}% | PF {short_pf:.2f} | {short_total} señales\n\n"
        f"🧪 *Validación v2 (OOS - 24h):*\n"
        f"• FUERTE LONG: HR {fuerte_long_hr:.1f}% | PF {fuerte_long_pf:.2f} | {fuerte_long_total} señales\n"
        f"• FUERTE SHORT: HR {fuerte_short_hr:.1f}% | PF {fuerte_short_pf:.2f} | {fuerte_short_total} señales\n"
        f"• MODERADA LONG: HR {moderada_long_hr:.1f}% | PF {moderada_long_pf:.2f} | {moderada_long_total} señales\n"
        f"• MODERADA SHORT: HR {moderada_short_hr:.1f}% | PF {moderada_short_pf:.2f} | {moderada_short_total} señales\n\n"
        f"🌍 *v2 por clase de activo (24h):*\n"
        f"• Crypto: HR {crypto_hr:.1f}% | PF {crypto_pf:.2f} | {crypto_total} señales\n"
        f"• TradFi: HR {tradfi_hr:.1f}% | PF {tradfi_pf:.2f} | {tradfi_total} señales\n\n"
        f"⚔️ *Legacy vs v2 (24h):*\n"
        f"• Legacy ALTA/BAJA: HR {legacy_hr:.1f}% | PF {legacy_pf:.2f} | {legacy_total} señales\n"
        f"• v2 FUERTE: HR {v2_fuerte_hr:.1f}% | PF {v2_fuerte_pf:.2f} | {v2_fuerte_total} señales\n\n"
        f"🏥 *Salud del sistema (24h):*\n"
        f"• Errores: {errores_24h}\n"
        f"• Señales v2 inválidas: {v2_invalidas} / {v2_total_24h}\n"
        f"• Régimen desconocido: {regimen_unknown} / {total_24h} señales\n"
        f"• Última señal: hace {edad_ultima_senal:.1f}h\n\n"
        f"✅ _Prueba local exitosa. Listo para Render._"
    )
        
        # ─── 10. Enviar a Telegram ───
        print("📤 Enviando mensaje a Telegram...")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                print("✅ ¡ÉXITO! El mensaje fue enviado a Telegram correctamente.")
                print("   Revisa tu aplicación de Telegram ahora mismo.")
            else:
                print(f"❌ ERROR DE TELEGRAM: {result}")
    
    except Exception as exc:
        print(f"❌ FALLO CRÍTICO: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_telegram_notification()