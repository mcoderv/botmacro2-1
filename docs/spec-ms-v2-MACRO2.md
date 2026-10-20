# docs/spec-ms-v2.md — Spec canónico de MACRO2
Spec oficial de la metodología OOS. Si algo entra en conflicto con el código o con `docs/investigaciones/`, gana este archivo. La investigación original completa está en `docs/investigaciones/DESIGN_AND_VALIDATION.txt` (o nombre equivalente) para quien quiera el detalle.

**Estado**: congelado desde T_0 = 2026-10-19 18:00 UTC. NO modificar durante el periodo de validación OOS.

## 1. Arquitectura de `ms_v2` (multi-timeframe)
### 1.1 Tratamiento de contradicciones multi-TF
Modular, no vetar. Cuando el TF bajo contradice el alto, se reduce el score hacia neutralidad. El vetado discreto censura observaciones y destruye la monotonicidad que necesita el IC de Spearman.

### 1.2 Esquema de combinación
Suma ponderada lineal. No gating, no multiplicación, no votación. La suma preserva estructura y minimiza el overfitting con muestras pequeñas.

### 1.3 Ponderación por defecto
`w = [w_5m = 0.35, w_1h = 0.30, w_4h = 0.20, w_1d = 0.15]`
Decaimiento por frecuencia. Ajustable solo con justificación + ADR.

## 2. Componentes del score base
### 2.1 Estacionariedad (ADF/FFD) como conmutador de régimen
- Si `p_adf < 0.05` (estacionario / reversión):  
  `S_base = 1.5·caja_p + 1.5·fvg + 0.5·rs + 0.5·poc_score`
- Si `p_adf ≥ 0.05` (no estacionario / tendencia):  
  `S_base = 0.5·caja_p + 0.5·fvg + 2.0·rs + 0.5·poc_score`
- **ADF threshold**: 0.02 (no 0.05). Reduce falsos positivos por ventanas rodantes cortas.

### 2.2 Divergencia precio/flujo
Término de interacción explícito. Si `poc_score = +1` y `rs ≤ -1` → bonificación bajista `D_bear = -2`. Si `poc_score = -1` y `rs ≥ +1` → bonificación alcista `D_bull = +2`. En otro caso: 0.  
**Score final**: `S_final = S_base + D + S_MTF`

### 2.3 Componentes secundarios
- **Excluir**: `fuerza_15m` (decaimiento < 1h, irrelevante para 4h-24h).
- **Incluir**: `p_magnet` (atractor de liquidez en ciclo diario).
- **Incluir**: `funding_pct` solo en crypto. **NO** en TradFi sintético.
- `poc_score`: incluido con peso reducido 0.5 para mitigar colinealidad con `caja_p`.

## 3. Normalización y escala
### 3.1 Volatilidad (ATR)
No normalizar el score macro. Multiplicar por ATR confunde certeza de dirección con magnitud esperada. La normalización va en position sizing, no en la señal alfa.

### 3.2 Escala del score
Rango continuo o `[-10, +10]`. La escala no altera el IC de Spearman (correlación de rangos es invariable ante transformaciones monotónicas estrictas). Usar winsorization en las colas empíricas.

## 4. Validación estadística
### 4.1 Métrica principal
IC de Spearman transversal por ciclo:  
`IC_t = ρ_Spearman(S_t, R_{t→t+H})` donde N=12 activos, H ∈ {4h, 8h, 24h}  
Consistencia: media de `IC̄` y `ICIR = IC̄ / σ(IC_t)`.

| IC̄ | Interpretación |
|---|---|
| 0.00-0.02 | Ruido |
| 0.03-0.05 | Alfa marginal |
| 0.06-0.10 | Alfa alto |
| > 0.15 | Probable look-ahead bias |

### 4.2 Tamaño de muestra
Para IC = 0.05 con p<0.05 y potencia 80%:  
3,134 muestras independientes requeridas.  
Factor de traslape L = 24h / 15min = 96.  
`N_efectivo ≈ N_total / L`.  
Con ~80 señales/día y ρ_crypto ≈ 0.75: ~155 días operativos.  
Ajustar errores estándar con Newey-West, lag = L-1.

### 4.3 Protocolo OOS ciego
- `T_0` registrado en DB (2026-10-19 18:00 UTC).
- Ejecución paralela desacoplada: `macro_score` (legacy) y `macro_score_v2` se calculan y registran en columnas independientes en cada ciclo.
- Aislamiento muestral: pre-T_0 = IS. Post-T_0 = OOS. Prohibido modificar ponderaciones durante OOS.
- Prueba de hipótesis comparativa: t pareada sobre ICs diarios con Newey-West. H_0: `IC̄_v2 - IC̄_legacy ≤ 0`. Rechazo si t_NW > 1.96.

## 5. Umbrales de calidad (recalibración)
### 5.1 Percentiles empíricos (NO absolutos)
Umbrales fijos descalibrados. Usar percentiles rodantes sobre |S|:
| Nivel | Rango | Población aprox. |
|---|---|---|
| RUIDO | |S| < P_50 | ~50% |
| MODERADA | P_50 ≤ |S| < P_85 | ~35% |
| FUERTE | |S| ≥ P_85 | ~15% |
Ventana móvil: últimos 30 días. Adapta la sensibilidad a cambios de régimen sin recalibrar manualmente.

### 5.2 Granularidad
3 niveles (no 4) mientras N < 1,000 muestras. Subir granularidad solo cuando se tenga muestra estadísticamente robusta.

## 6. Criterios de adopción de `ms_v2` (post-validación)
Adoptar `ms_v2` como score principal si TODAS se cumplen:
1. `ICIR(ms_v2) > ICIR(legacy)`
2. `HR_direccional (FUERTE v2, 24h) > 55%`
3. `Profit_Factor (FUERTE v2, 24h) > 1.2`

## 7. Riesgos conocidos (no corregibles durante el freeze)
- **Funding N/A → 0**: cuando un TF devuelve N/A, se convierte a 0 (neutro), lo que diluye el score. Limitación conocida.
- **Sesgo coyuntural vs. estructural del legacy**: 13-19 Oct el legacy tuvo HR 26.9% en LONG y 73.3% en SHORT. Responder post-validación, no durante.
- **ADF en ventanas rodantes**: alternancias frecuentes de régimen pueden inducir variabilidad extrema en el score. Vigilar `regime_confidence` y los UNKNOWN en régimen.

## 8. Queries de referencia
```sql
-- IC de Spearman transversal por ciclo (H=24h)
SELECT cycle_id,
       spearman_rank_correlation(macro_score, realized_return_24h) AS ic_legacy_24h,
       spearman_rank_correlation(macro_score_v2, realized_return_24h) AS ic_v2_24h
FROM senales_validadas s
JOIN gem_macro_snapshot m USING (coin, cycle_id)
WHERE s.timestamp_emision >= '2026-10-19 18:00'
GROUP BY cycle_id;

-- HR y PF de señales FUERTE v2
SELECT COUNT(*) AS n,
       AVG(CASE WHEN realized_return_24h > 0 THEN 1 ELSE 0 END) AS hr,
       SUM(GREATEST(realized_return_24h, 0)) / NULLIF(SUM(GREATEST(-realized_return_24h, 0)), 0) AS pf
FROM senales_validadas
WHERE calidad_senal_v2 = 'FUERTE'
  AND resuelto_24h = 1
  AND timestamp_emision >= '2026-10-19 18:00';