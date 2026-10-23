# decisiones/001-umbral-dinamico-volatilidad.md — Umbral dinámico y reducción de universo

**ADR** — Architecture Decision Record. Documenta una decisión técnica de MACRO2 y sus consecuencias. NO se modifica retroactivamente.

**Estado:** Propuesto / Pendiente de implementación (Post-Freeze en MACRO2, activo en MACRO2.1).

## Contexto
El sistema actual utiliza un umbral fijo de ±0.05% para clasificar una señal resuelta como WIN, LOSS o BREAKEVEN. Este enfoque presenta dos limitaciones metodológicas críticas identificadas durante la validación OOS inicial:

1. **Sesgo por volatilidad:** Un umbral del 0.05% es trivial para activos como BTC (que se mueve >1% en 4h), convirtiendo casi todo en WIN/LOSS, pero es excesivo para activos estables como índices o divisas, generando demasiados BREAKEVEN artificiales (20.6% en 4h).
2. **Dilución de la muestra:** Evaluar 12 activos con perfiles de liquidez y volatilidad radicalmente distintos (desde HYPE hasta xyz:EUR) dispersa las señales, ralentizando la acumulación de muestras estadísticamente significativas por activo individual.

## Decisión
Una vez levantado el DATA FREEZE, se implementarán los siguientes cambios en el módulo de resolución de señales (C4) y evaluación:

### 1. Umbral dinámico por volatilidad
Reemplazar el 0.05% fijo por un umbral adaptativo calculado como:
`umbral_i,h = k × σ_i,h`

Donde:
- `σ_i,h` = Desviación estándar de los retornos absolutos del activo `i` en el horizonte `h` (4h, 8h, 24h), calculada sobre una ventana rodante histórica (ej. últimos 90 días).
- `k` = Multiplicador de sensibilidad (valor inicial propuesto: 0.15 a 0.25, a calibrar empíricamente).

**Regla:** `abs(retorno) < umbral` → BREAKEVEN; `retorno >= umbral` → WIN; `retorno <= -umbral` → LOSS.

### 2. ACTUALIZACIÓN 2026-10-21: Reducción del universo de activos
**DECISIÓN REVISADA:** El usuario decidió **MANTENER los 12 activos** en lugar de reducir a 2 (BTC + xyz:GOLD).
- **Razón:** Preservar la diversificación y capacidad de comparar el comportamiento del score en todos los activos, no solo en 2 representantes.
- **Consecuencia:** La implementación del umbral dinámico se aplicará a los 12 activos, no solo a 2.

## Consecuencias

### Positivas
- **Justicia estadística:** La clasificación de acierto/fallo se adapta a la realidad de cada mercado, evitando que la volatilidad inherente distorsione el Hit Rate.
- **Comparativa limpia:** Permite comparar directamente el rendimiento de `ms_v2` en activos de diferente volatilidad con umbrales justos.
- **Reducción de breakevens artificiales:** Se espera que los breakevens bajen del 20.6% actual (4h) a niveles más razonables (<10%).

### Negativas / Riesgos
- **Complejidad de implementación:** Requiere añadir una tabla o lógica de mantenimiento de `σ_i,h` histórica en la bóveda (C2/C3) sin introducir look-ahead bias.
- **Re-evaluación histórica:** Las métricas pre-T_0 y post-T_0 deberán recalcularse con la nueva fórmula, invalidando los reportes generados hasta la fecha del cambio.
- **Menor potencia estadística por activo:** Al mantener los 12 activos, se acumulan muestras más lentamente por activo individual (vs. concentrar en 2 activos).

## Alternativas consideradas
1. **Mantener 0.05% fijo:** Descartado, ya que sesga sistemáticamente los resultados a favor de activos volátiles y en contra de estables.
2. **Reducir a 2 activos (BTC + xyz:GOLD):** Descartado por decisión del usuario (2026-10-21). Se prefirió mantener los 12 activos.
3. **Reducir a 1 solo activo:** Descartado, porque necesitamos al menos dos puntos de datos (Crypto vs TradFi) para validar si el sesgo estructural observado en LONG es universal o específico de una clase de activo.
4. **Umbral basado en ATR en lugar de σ:** Descartado temporalmente por simplicidad; la desviación estándar de retornos (`σ`) es más directa para evaluar el resultado final de la señal, mientras que ATR es más útil para position sizing.

## Próximos pasos (MACRO2.1 - activo)
1. Implementar cálculo de `σ_i,h` rodante en C3 o C2.5.
2. Actualizar la lógica de resolución en C4 para usar `umbral_i,h`.
3. **Mantener los 12 activos en el universo (NO reducir a 2).**
4. Re-ejecutar `analisis_post_mortem.py` sobre toda la base de datos para establecer la nueva línea base con umbral dinámico.

## Referencias
- Análisis de queries del 2026-10-20 (desglose por clase de activo y tipo de señal).
- `docs/spec-ms-v2.md` §4 (Validación estadística).
- Ley Fundamental de la Gestión Activa (Grinold & Kahn) sobre la necesidad de muestras independientes por estrategia/activo.
- **Decisión del usuario (2026-10-21):** Mantener los 12 activos en lugar de reducir a 2.