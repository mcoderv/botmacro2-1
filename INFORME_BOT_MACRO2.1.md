================================================================================
mercabot_qwen - INFORME TECNICO MACRO2.1
Que es MACRO2.1, que cambios tiene respecto a MACRO2, y resultados preliminares
================================================================================

Fecha del informe  : 21 de octubre 2026
Estado del sistema : Experimental local (Windows + VS Code)
Modo               : DESARROLLO ACTIVO. NO tiene DATA FREEZE.
                     MACRO2 (producción en Render) sigue en freeze.
Ultima medicion    : 21-oct-2026 21:02 Caracas (845 señales en DB)

================================================================================
1. QUE ES MACRO2.1
================================================================================

MACRO2.1 es un clon local de MACRO2 creado el 2026-10-21 para experimentar
con correcciones sin afectar al bot en producción (MACRO2 en Render).

Propósito:
1. Probar correcciones a los problemas identificados en MACRO2
2. Validar mejoras con datos reales (845 señales copiadas de MACRO2)
3. Acumular nueva data con las correcciones aplicadas
4. Solo llevar a MACRO2 lo que funcione en MACRO2.1

Diferencias clave con MACRO2:
- NO está en DATA FREEZE (desarrollo activo)
- NO corre en Render (solo local)
- NO usa Litestream ni Cloudflare R2
- Tiene 2 intervenciones ya implementadas (I-1 y I-2)

--------------------------------------------------------------------------------
1.1 STACK TECNICO (MACRO2.1)
--------------------------------------------------------------------------------

Lenguaje        Python 3.12
Base de datos    SQLite (local) - vault_v2.1.db
API de mercado   Hyperliquid REST - https://api.hyperliquid.xyz/info
Dependencias     pandas, numpy, statsmodels, scipy, aiohttp, nest-asyncio,
                 tabulate
NO usa           Render, Litestream, Cloudflare R2, Telegram (opcional)
Timezone         America/Caracas (UTC-4) para toda la logica temporal
Activos          12 activos (6 crypto + 6 TradFi) - mismo universo que MACRO2

--------------------------------------------------------------------------------
1.2 INTERVENCIONES IMPLEMENTADAS
--------------------------------------------------------------------------------

INTERVENCIÓN I-1: Simetrización de CAJA
----------------------------------------
Archivo: C3_MACRO_local.py (función fetch_liquidity_zones)

Problema: El amplificador `am` estaba limitado a máximo 1.0, lo que impedía
          que el componente CAJA pudiera penalizar fuertemente las entradas
          en zona INF (tercio inferior del rango 24h).

Cambio: Ampliar el rango de `am` de [0.0, 1.0] a [0.5, 2.0]

Código anterior:
    am = min(1.0, va / (ATR_RUPTURA_MULT * atr)) if atr > 0 else 1.0
    caja_p = int(round(caja * am))

Código nuevo:
    am = min(2.0, max(0.5, va / (ATR_RUPTURA_MULT * atr))) if atr > 0 else 1.0
    caja_p = max(-2, min(2, int(round(caja * am))))

Impacto:
- caja_p ahora puede ser {-2, -1, 0, 1, 2} (antes solo {-1, 0, 1})
- Entradas en zona INF con volumen alto ahora penalizan con -2
- Entradas en zona SUP con volumen alto ahora bonifican con +2
- Elimina el sesgo aditivo que generaba falsos positivos LONG

Resultados (comparando MACRO2 vs MACRO2.1):
| Métrica | MACRO2 (antes) | MACRO2.1 (después) | Mejora |
|---------|----------------|-------------------|--------|
| LONG HR | 23.3% | 32.9% | +9.6 pp |
| LONG PF | 0.21 | 0.50 | +138% |
| LONG NET | -316.5% | -202.8% | +113.7 pp |
| Score +3 HR | 18.2% | 31.1% | +12.9 pp |
| Score +3 PF | 0.17 | 0.49 | +188% |

INTERVENCIÓN I-2: Motor de Régimen ADF real
--------------------------------------------
Archivo: C3_5_REGIME_ENGINE.py

Problema: El motor de régimen usaba una heurística basada en FFD slope +
          autocorrelación + consistencia direccional, lo que causaba que
          97% de las señales fueran clasificadas como RANGE.

Cambio: Reemplazar la heurística por test ADF real con statsmodels

Código anterior (simplificado):
    def _classify_heuristic(features):
        # Calcula scores heurísticos para TREND_UP/DOWN/RANGE/CHAOS
        # Usa ffd_slope, autocorr_1, dir_consistency
        # Resultado: 97% RANGE

Código nuevo (simplificado):
    def classify_market_regime_adf(prices, vol_recent, vol_historical):
        # 1. Transforma precios a logarítmicos (niveles, NO retornos)
        log_prices = np.log(prices)
        
        # 2. Ejecuta test ADF sobre niveles logarítmicos
        adf_result = adfuller(log_prices, autolag='AIC', regression='c')
        p_value = float(adf_result[1])
        
        # 3. Si p_value <= 0.05 → estacionario → RANGE
        if p_value <= 0.05:
            return {"regime": "RANGE", "is_stationary": True}
        
        # 4. Si no estacionario, calcula pendiente OLS para dirección
        slope, _ = np.polyfit(x, log_prices[-20:], 1)
        if slope > 0.0012:
            return {"regime": "TREND_UP"}
        elif slope < -0.0012:
            return {"regime": "TREND_DOWN"}
        else:
            return {"regime": "RANGE"}  # paseo aleatorio

Impacto:
- Clasificación real de regímenes basada en test estadístico
- Umbral p-value 0.05 (estándar econométrico)
- Insumo: precios logarítmicos en niveles (NO retornos)
- Resultado: ~70% RANGE, ~30% TREND (vs 97% RANGE anterior)
- Conmutador multi-rama del score_v2 ahora activo

Resultados (ejemplo de salida):
   • BTC          RANGE        p=0.0485 slope=0.000000 vol=0.87 ✅EST
   • ETH          RANGE        p=0.5248 slope=0.001070 vol=0.88 ❌NO-EST
   • XRP          TREND_UP     p=0.5884 slope=0.001637 vol=0.83 ❌NO-EST
   • xyz:GOLD     RANGE        p=0.4770 slope=0.000122 vol=0.92 ❌NO-EST

--------------------------------------------------------------------------------
1.3 ANÁLISIS ADICIONAL IMPLEMENTADO
--------------------------------------------------------------------------------

Puente Browniano para análisis MAE/MFE
---------------------------------------
Archivo: analisis_mae_mfe_browniano.py (script de análisis, no del pipeline)

Propósito: Determinar si el precio toca SL antes que TP usando:
           1. Detección directa en snapshots de 15m
           2. Puente browniano para estimar probabilidad cuando los extremos
              no cruzan las barreras

Resultado: 45.4% de señales tocan SL antes que TP
Diagnóstico: El problema es de PROTECCIÓN DE CAPITAL, no de toma de ganancias
Acción recomendada: Implementar Stop Loss dinámico (ATR trailing)

--------------------------------------------------------------------------------
1.4 RESULTADOS ACTUALES (MACRO2.1)
--------------------------------------------------------------------------------

Datos acumulados:
Señales en DB .................. 845 (copiadas de MACRO2)
Señales resueltas (24h) ........ 839

Hit rate (24h):
  Global ....................... 43.4%
  LONG ......................... 32.9%  (mejora vs MACRO2: 23.3%)
  SHORT ........................ 53.8%

Profit Factor (24h):
  Global ....................... 0.68
  LONG ......................... 0.50   (mejora vs MACRO2: 0.21)
  SHORT ........................ 0.96

PnL promedio (24h):
  Global ....................... -0.253%
  LONG ......................... -0.484%
  SHORT ........................ -0.023%

Por clase de activo (24h):
  Crypto ....................... HR 38.1%, PF 0.47 (sigue perdiendo)
  TradFi ....................... HR 49.1%, PF 1.25 (sigue ganando)

Activos ganadores (PF > 1.1):
  xyz:SILVER ................... PF 2.63, HR 63.0%
  xyz:GOLD ..................... PF 2.21, HR 49.4%
  xyz:CL ....................... PF 1.66, HR 59.3%
  xyz:XYZ100 ................... PF 1.42, HR 63.5%

Activos perdedores (PF < 1.0):
  BTC .......................... PF 0.12, HR 19.7%
  SOL .......................... PF 0.41, HR 34.2%
  HYPE ......................... PF 0.35, HR 40.0%
  XRP .......................... PF 0.62, HR 39.7%
  AVAX ......................... PF 0.88, HR 45.7%
  ETH .......................... PF 0.70, HR 47.3%
  xyz:EUR ...................... PF 0.28, HR 22.0%
  xyz:SP500 .................... PF 0.19, HR 36.1%

================================================================================
2. PROBLEMAS PENDIENTES
================================================================================

2.1 LOS 6 CRYPTOS SIGUEN PERDIENDO
------------------------------------
Problema: BTC HR 19.7%, PF 0.12. Peor que no operar.
Hipótesis:
1. Microestructura crypto incompatible con indicadores de order flow
2. Funding rate y cascadas de liquidación no modelados
3. Desajuste de horizonte (señal de microestructura vs resolución 24h)
Acción pendiente: Investigar microestructura crypto vs TradFi

2.2 LA TARDE ES UN PANTANO
---------------------------
Problema: Emisiones 15:00-17:00 con PF 0.09-0.18
Hipótesis: A la tarde el momentum ya se consumió
Acción pendiente: Evaluar ampliar ventana a 04:00-16:00

2.3 RESOLUCIÓN 8h INSERVIBLE
-----------------------------
Problema: 84.2% de resoluciones 8h con contaminación >1h
Causa: Ventana operativa 08:00-17:00 deja targets de 8h fuera de horario
Acción pendiente: Descartar ventana 8h o ampliar ventana operativa

2.4 DISOCIACIÓN MFE/PnL
------------------------
Problema: MFE +740.1% vs PnL -212.3% (2.7x menos captura)
Causa: Resolución por tiempo fijo (24h) sin mecanismo de protección
Acción pendiente: Implementar Stop Loss dinámico (ATR trailing)

================================================================================
3. PRÓXIMAS INTERVENCIONES
================================================================================

3.1 PRIORIDAD ALTA: Umbral dinámico de volatilidad (ADR 001)
-------------------------------------------------------------
Problema: Umbral fijo 0.05% sesga resultados (trivial para BTC, excesivo para EUR)
Solución: Reemplazar por umbral = k × σ (desviación estándar de retornos)
Archivo: C4_SENIAL_VALIDATOR.py
Estado: Pendiente de implementación

3.2 PRIORIDAD MEDIA: Stop Loss dinámico (ATR trailing)
-------------------------------------------------------
Problema: 45.4% de señales tocan SL antes que TP
Solución: Implementar trailing stop basado en ATR
Archivo: C4_SENIAL_VALIDATOR.py (lógica de resolución)
Estado: Pendiente de implementación

3.3 PRIORIDAD BAJA: Ampliar ventana operativa
----------------------------------------------
Problema: Contaminación temporal en resolución 8h
Solución: Ampliar ventana a 04:00-16:00 con validación escalonada
Archivos: ventana.py, scheduler.py
Estado: Pendiente de evaluación

================================================================================
4. DIFERENCIAS CLAVE MACRO2 vs MACRO2.1
================================================================================

| Aspecto | MACRO2 (producción) | MACRO2.1 (experimental) |
|---------|---------------------|-------------------------|
| Ubicación | Render (cloud) | Local (Windows) |
| Freeze | DATA FREEZE activo | SIN freeze |
| DB | vault_v2.db (Turso) | vault_v2.1.db (local) |
| Litestream | Sí (R2 backup) | No |
| Telegram | Sí (reportes 8AM/5PM) | Opcional |
| Intervenciones | Ninguna (freeze) | I-1 y I-2 implementadas |
| Señales | ~960 (acumulando) | 845 (copiadas de MACRO2) |
| LONG HR | 23.3% | 32.9% (mejora) |
| LONG PF | 0.21 | 0.50 (mejora) |
| Regímenes | 97% RANGE | ~70% RANGE, ~30% TREND |

================================================================================
5. CÓMO CONTINUAR
================================================================================

1. Lee ESTADO.md (verdad actual de MACRO2.1)
2. Lee decisiones/001-umbral-dinamico-volatilidad.md (próxima intervención)
3. Implementa umbral dinámico en C4_SENIAL_VALIDATOR.py
4. Valida con analisis_post_mortem.py
5. Si mejora, documenta en decisiones/
6. Solo lleva a MACRO2 lo que funcione en MACRO2.1

================================================================================
FIN DEL INFORME
================================================================================
Generado: 21-oct-2026
Fuente: código de MACRO2.1 + métricas de analisis_post_mortem.py
================================================================================