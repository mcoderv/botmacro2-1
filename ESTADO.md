# ESTADO.md — Estado actual de MACRO2
La verdad más reciente del proyecto en 1 página. Se reescribe (no se appenda) en cada hito importante. Si pasa de 1 página, hay detalle que se ha colado y debe moverse a `decisiones/` o a `docs/`.

## Identificación
- **Proyecto**: MACRO2 (mercabot_qwen)
- **Carpeta local**: `C:\Users\MD\Desktop\VSCODE\MACRO2`
- **Repositorio**: https://github.com/mcoderv/botmacro
- **Entorno**: Render Free (Web Service) + Cloudflare R2 (vía Litestream) + UptimeRobot
- **Modo**: CAPTURA / Validación OOS ciega
- **Versiones activas**: C1 v1.3 / C1.5 v2.8 / C2 v8.5 / C2.5 v2.3 / C3 v7.9.3 / C3.5 v1.5 / C3_DATA_QUALITY v1.2 / C4 v1.3 / Scheduler v2.0
- **Última actualización**: 2026-10-19
- **Próxima revisión**: Al cambiar de fase o cerrar un ADR

## Fase y freeze
- **FASE 2+** — DATA FREEZE activo (validación OOS ciega).
- **T_0**: 2026-10-19 18:00 UTC
- **Duración objetivo**: 30 días mínimo, ~155 días ideal
- **Regla dura**: NO modificar código durante el freeze. Solo bug fixes que NO cambien la lógica del score.

## Hito más reciente
Inicio de validación OOS ciega con `ms_v2` corriendo en paralelo al score legacy. Warm-up previo de 6.1 días, 721 señales registradas, 567 resueltas a 24h. Scheduler v2.0 activo con reportes de Telegram a las 8 AM y 5 PM (Caracas).

## Lo que funciona
- ✅ Pipeline C0→C4 cada 15 min (local y Render)
- ✅ Scheduler en producción + Telegram reportes 8 AM y 5 PM Caracas
- ✅ Litestream replica DB a R2 (`mercabot-qwen-db`); health endpoint OK
- ✅ Score dual legacy + v2 registrado en `senales_validadas`
- ✅ `gem_macro_snapshot` poblándose cada ciclo (incluye `macro_score_v2`)
- ✅ Migraciones aditivas de C2 v8.5 aplicadas y validadas

## Lo que NO funciona o está bloqueado
- *(Vacío al inicio del freeze)*

## Próximo objetivo (1 sola cosa)
No tocar nada durante 30 días mínimo. Acumular muestras efectivas para validar `ms_v2` con significancia estadística.

## Criterios de adopción de `ms_v2` (post-validación)
Adoptar si TODAS se cumplen:
1. `ICIR(ms_v2) > ICIR(legacy)`
2. `HR_direccional (FUERTE v2, 24h) > 55%`
3. `Profit_Factor (FUERTE v2, 24h) > 1.2`
- **Tamaño objetivo**: ≥ 3,134 muestras efectivas (~155 días con correlaciones crypto ρ≈0.75).

## Decisiones pendientes
- *(Ninguna — la decisión de adoptar `ms_v2` está congelada hasta tener muestra suficiente)*

## Investigación abierta
1. **Sesgo estructural del legacy en LONG**: HR 26.9%, PF 0.21 en 13-19 Oct vs SHORT 73.3% HR. ¿Coyuntural (mercado bajista) o estructural?
2. **Funding N/A → 0**: diluye score cuando un TF viene nulo. Limitación conocida, no corregida por freeze.

## Cómo continuar (para próxima sesión o agente)
1. Lee este archivo entero (es la verdad actual).
2. Lee `decisiones/` para entender el porqué.
3. Lee `docs/spec-ms-v2.md` para la metodología OOS.
4. Lee `docs/data-lineage.md` para qué dato viene de dónde.
5. **NO modifiques código sin un ADR nuevo y mi OK explícito.**
6. Si hay duda, pregunta antes de tocar.