Aquí tienes el listado puntual y actualizado de las correcciones que **faltan por implementar** en MACRO2.1, clasificadas por prioridad y archivo. 

*(Nota: Las Intervenciones I-1 [Caja simétrica] e I-2 [ADF real] ya están **completadas y validadas**).*

---

### 🔴 Pendientes de Código (MACRO2.1)

1. **`C4_SENIAL_VALIDATOR.py` (Etiquetas de calidad)**
   - **Problema:** Los umbrales legacy (14/8/4) son incompatibles con el `macro_score` que va de -5 a +5, haciendo que todo caiga en "RUIDO" o "BAJA".
   - **Corrección:** Recalibrar la lógica de etiquetado a: ALTA (≥4), MEDIA (≥3), BAJA (≥2), o eliminar las etiquetas y usar el score crudo directamente.

2. **`C4_SENIAL_VALIDATOR.py` (Umbral dinámico - ADR 001)**
   - **Problema:** El umbral fijo de 0.05% para WIN/LOSS/BREAKEVEN sesga los resultados (trivial para BTC, excesivo para xyz:EUR).
   - **Corrección:** Reemplazar el 0.05% fijo por `umbral = k * σ` (desviación estándar de retornos del activo). *Nota: Tú indicaste que si es muy complejo, se puede dejar como está por ahora. Confirmar si se implementa o se pospone.*

3. **`scheduler.py` (Puerto de Render)**
   - **Problema:** El health check puede fallar en Render porque usa un puerto fijo.
   - **Corrección:** Cambiar la definición del puerto para que lea la variable de entorno: `PORT = int(os.environ.get("PORT", 8080))`.

4. **`report_validator.py` (Bug de Max DD)**
   - **Problema:** Reporta un Max Drawdown de 270.88% (imposible en un solo segmento), lo que indica que está sumando drawdowns de múltiples segmentos o activos en lugar de calcularlo sobre la curva de equidad total.
   - **Corrección:** Revisar la fórmula de cálculo del Drawdown para que se base en el pico a valle de la curva de capital acumulada, no en la suma de segmentos.

5. **`ventana.py` / `scheduler.py` (Contaminación temporal)**
   - **Problema:** La ventana actual (08:00-17:00) deja los targets de 8h fuera de horario, causando el 84.2% de contaminación.
   - **Corrección:** Ampliar la ventana operativa a **04:00 - 16:00** (Caracas) e implementar la validación escalonada (4→8, 8→12, 12→16) para cerrar el ciclo diario sin datos faltantes. *(Pendiente de tu confirmación para generar el código)*.

---

### 🟡 Pendientes de Documentación / Configuración

6. **`ADR 000` / Documentación del Repo**
   - **Corrección:** Actualizar el nombre del bucket de Cloudflare R2 a `mercabot-qwen-db` (actualmente los docs dicen erróneamente `macrobot-vault`).

7. **`C1_5_PARAM_local.py` (Alineación de parámetros)**
   - **Corrección:** El banner muestra `ADF_THR: 0.02`, pero el nuevo motor de régimen (C3.5) usa `0.05` por defecto. Conviene actualizar el valor en el diccionario `validation` de `CENTRAL_PARAMS` a `0.05` para mantener la coherencia visual y lógica.

---

### ⚪ Descartados o en Monitoreo (No requieren código)

- **Eliminar cryptos del universo:** Descartado. Tú decidiste mantener los 12 activos y investigar su microestructura en su lugar.
- **Filtro v2 con pocas señales (22 señales):** Se resolverá orgánicamente con la acumulación de datos (tiempo).
- **MACRO2 (Producción en Render):** Sigue en **DATA FREEZE**. Ninguna de las correcciones anteriores debe tocarse allí hasta que sean validadas en MACRO2.1.

---

**¿Por cuál de estos puntos pendientes quieres que empecemos a trabajar?** (Te sugiero el **Punto 1** o el **Punto 5**, ya que tienen el mayor impacto inmediato en la calidad de los datos).