# ADR 006 — La ventana operativa es un valor de configuración

- **Estado:** ACEPTADO
- **Fecha:** 2026-10-24
- **Alcance:** `ventana.py`, `scheduler.py`, `C1_5_PARAM_local.py`,
  `config/CONSOLIDADO/central_params.json`.
- **Problema:** H-17.

## Contexto

La ventana operativa estaba **hardcodeada en tres lugares**:
`ventana.py` (`VENTANA_INICIO = 8`, `VENTANA_FIN = 17`), el *fallback* del
`try/except ImportError` de `scheduler.py`, y el log de arranque. Cambiarla
significaba editar código y reiniciar.

Eso era un problema por dos motivos:

1. **El 24/7 era imposible.** El modo CONTINUO existía *de facto* (por el
   fallback sin `ventana.py`), pero no se podía activar a propósito. Con la
   estructura de la ventana (8-17) y una resolución de 8h, el **lag mediano era
   de 4,03h** y **735 de 914 señales** quedaban con lag > 1h: la ventana de 8h
   era inservible.
2. **El bug H-17.** El bloque de resúmenes de Telegram estaba **dentro** de
   `if not en_ventana():`. En modo CONTINUO el resumen de las 17:00 nunca se
   enviaba y las banderas nunca se reseteaban a la medianoche. En el modo
   VENTANA 8-17, el **resumen de las 8:30 AM nunca se enviaba** (a esa hora se
   está dentro de ventana, así que el bloque no se ejecutaba).

## Decisión

**La ventana operativa pasa a ser un valor de configuración**, en la sección
`ventana_operativa` de `CENTRAL_PARAMS`:

```json
"ventana_operativa": {
  "MODO": "VENTANA",
  "HORA_INICIO": 8,
  "HORA_FIN": 17,
  "INTERVALO_SEGUNDOS": 900,
  "DIAS_SEMANA": [0, 1, 2, 3, 4, 5, 6],
  "TZ": "America/Caracas"
}
```

Reglas de implementación:

- `ventana.py` lee el **JSON**, no las constantes. **NO** importa
  `C1_5_PARAM_local`, porque al importarse ese módulo **reescribe** el JSON
  (y se pisaría a sí mismo).
- `MODO`: `VENTANA` (rango horario) | `CONTINUO` (24/7, siempre dentro).
- Se soporta el **cruce de medianoche** (p.ej. 20:00 → 04:00): antes
  `en_ventana()` comparaba `INICIO <= hora < FIN` y una ventana invertida
  quedaba **siempre fuera**.
- `DIAS_SEMANA` (0 = lunes) permite operar solo algunos días.
- La **duración no tiene que ser múltiplo de 4h**. Los múltiplos de 4
  (4/8/12/16/20/24) son **presets sugeridos** porque encajan con las ventanas
  de resolución de C4 (`RESOLUTION_WINDOWS_HOURS = [4, 8, 24]`); si la duración
  no lo es, el CLI **avisa** pero acepta. *(El usuario operaba 8-17 = 9h.)*
- El fallback `except ImportError` de `scheduler.py` **se mantiene** como red
  de seguridad (24/7).
- **El bloque de resúmenes diarios se mueve FUERA del `if not en_ventana()`**:
  los resúmenes de Telegram y el reset de banderas a medianoche deben
  ejecutarse en cada ciclo, esté dentro o fuera de ventana.

### CLI

```cmd
python ventana.py --ver                    :: muestra la ventana actual
python ventana.py --continuo               :: 24/7
python ventana.py --inicio 4 --fin 16      :: ventana de 4h a 16h
python ventana.py --inicio 20 --fin 4      :: cruza la medianoche
python ventana.py --dias 0,1,2,3,4         :: solo lunes a viernes
python ventana.py --intervalo 900          :: segundos entre ciclos
```

La ventana **es un valor libre**: el CLI no impone nada, solo avisa.

## Consecuencias

**A favor:**
- Cambiar el horario es **un comando**, sin editar código y sin buscar en 3 archivos.
- El **24/7 se puede activar a propósito** (no por accidente).
- Con 24/7: el lag de la resolución de 8h **deja de ser 4h**, el
  *confirmation filter* (emitir → confirmar → resolver) aplica al **100%** en
  vez del 67%, y desaparece el sesgo de régimen horario en las muestras.
- El bug de los resúmenes queda cerrado.
- Las ventanas que cruzan medianoche funcionan.

**En contra / a tener en cuenta:**
- **Cambiar la ventana cambia el régimen de muestreo** ⇒ los datos nuevos **no
  son comparables** con los viejos. Con H-10 abierto, esto puede ser justo la
  causa del corte del 19/10. **Coordinar antes de tocar la ventana** y, cuando
  se toque, **cortar por día** en todo análisis.
- `ventana.py` ahora depende del JSON en disco: si el JSON se corrompe, la
  ventana cae a los `_DEFAULTS` (8-17). Es el comportamiento deseado, pero
  hay que saberlo.
- El JSON lo regenera `C1_5_PARAM_local` al importarse ⇒ **el literal y el JSON
  tienen que coincidir**. Por eso la sección está en los dos y
  `verificar.py` debería compararlos.

**No toca producción** (`botmacro`). El DATA FREEZE sigue vigente. La
ventana 08:00-17:00 de `decisiones/000-render-litestream-r2.md` describe la
**producción** y no cambia.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Seguir con constantes hardcodeadas | La ventana iba a cambiar (free → pago) y eso no puede requerir editar 3 archivos |
| Dejar la ventana solo en variables de entorno | No se versiona, no se ve en `verificar.py`, y no sobrevive a un reinicio sin `.env` |
| Importar `C1_5_PARAM_local` desde `ventana.py` | Al importarse **reescribe el JSON**: se pisa a sí mismo y genera una carrera |
| Imponer duraciones múltiplo de 4h | Contradice el uso real (8-17 = 9h) y la regla de que la ventana es un valor libre |
| Quitar el fallback `except ImportError` de `scheduler.py` | Es la red de seguridad que mantiene vivo al scheduler si `ventana.py` falta |

## Cómo se verifica

```cmd
python ventana.py --ver
```
⇒ debe mostrar MODO, rango, duración, intervalo, días y la ruta del JSON.

```cmd
python verificar.py
```
⇒ 19 ok / 0 fallas / 1 aviso.

```cmd
python fixesplicar_ventana_config.py --deshacer
```
⇒ restaura `ventana.py`, `scheduler.py`, `C1_5_PARAM_local.py` y el JSON desde
los `.bak`.

## Referencias

- `AGENTS.md` §5.3 y §6.
- `docs/PENDIENTES.md` §3.
- `decisiones/000-render-litestream-r2.md` (la ventana de **producción**).