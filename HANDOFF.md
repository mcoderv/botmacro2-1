# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a los chats viejos que venías guardando a mano.
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `docs/PENDIENTES.md`
> + `git log --oneline -20` + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-24
Sesion   : 3
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : 23efea4
DB       : 914 señales (902 resueltas a 24h)
```

---

## 1. Qué hice en esta sesión

- **Docker eliminado de MACRO2.1** (ADR 003): `Dockerfile`, `docker-compose.yml`,
  `.dockerignore`, `start.sh`, `litestream.yml`. **Producción (`botmacro`) intacta.**
- **`docs/` reordenada**: `docs/INFORME_MACRO2.1.md` (spec, intacta),
  `docs/PENDIENTES.md` (tracking), `docs/info/`, `docs/investigaciones/` (+`PLANTILLA.md`),
  `docs/local/` (fuera de GitHub). `textos/` eliminada.
- **Gobierno reescrito**: `AGENTS.md`, `ESTADO.md`, `HANDOFF.md`, `docs/PENDIENTES.md`
  + ADR 003. `verificar.py` ahora chequea los 4 ADRs.
- **`rescore_umbral.py` v2**: el v1 re-scoreó placeholders (ms_v2 = 0) y dio falsos
  positivos. La v2 clasifica reconstruible / no reconstruible, re-scorea solo las
  reconstruibles, aborta si la auto-validación 1 no da ≥90%, y reporta el corte temporal.
- **Pipeline verificado de punta a punta**: `python main.py` corre las 8 celdas sin
  excepciones y registró +7 señales (907 → 914).
- **Backup local de la DB** en `Desktop\MACRO2.1_BACKUP\` (falta Drive).

---

## 2. Los hallazgos importantes (léelos antes de tocar el score)

### 2.1 El ADR 002 es INMEDIBLE con los datos actuales

- **0 señales cambian de etiqueta** al pasar de 0.02 a 0.05.
- Motivo: de las 10 que cambian de rama, 9 son placeholders y 1 ya estaba en 0.05.
  **Solo 1 señal se generó con el umbral nuevo.**
- No significa que el ADR sea inútil: significa que **no hay historia con umbral
  viejo Y score v2 a la vez**. Necesita ~30 días más de datos.

### 2.2 El `ms_v2` opera con dos inputs degradados (H-9)

1. **`s_mtf` = 0 en 7 de 12 activos.** El bias 1D/4H/1H sale `N/A`.
2. **La rama momentum casi nunca se activa.** `P-v4.2` < 0.001 en los 12 activos de
   la última corrida; en el histórico **856 de 877 señales tienen p < 0.02**.

→ El score v2 es siempre `0.5·poc + 1.5·caja + 1.5·fvg + 0.5·rs + 0 + d`.
El flujo (`rs`), que es el componente que mejor predice la dirección, pesa **0.5**
en vez de 2.0.

**Consecuencia medida:** `(poc=±1, rs=±2, caja+fvg=∓1)` → `s_base = 0 EXACTO` en
estacionario y `±4` en momentum. Esos breakouts con flujo fuerte quedan con
`ms_v2 = 0` → etiqueta RUIDO. Hecho de fórmula, verificable sin datos.

### 2.3 Las etiquetas NO son comparables entre sí (H-10)

La distribución cambió por completo el 19/10: 0 FUERTE → 1 → 9 → 10.
**Comparar HR/PF entre etiquetas = comparar días distintos.** El "RUIDO tiene
PF 4.43" NO es evidencia.

**Siempre cortar por día (o por ventana) antes de comparar etiquetas.**

### 2.4 Cuántas señales tienen score v2 REAL: 111 (no 129)

| Grupo | n |
|---|---|
| `ms_v2 >= 2` (FUERTE 20 + MODERADA 38) | 58 |
| `ms_v2 < 2` coherente | 53 |
| Placeholders casualmente coherentes (13-18/10) | 18 ⚠️ NO son score real |
| Placeholders incoherentes | 748 |

**Con 111 señales, cualquier corte por etiqueta es ruido.**

---

## 3. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Arreglar el `s_mtf = 0` / la rama del `ms_v2` | Es un cambio al scoring → necesita ADR, y el diagnóstico del `N/A` no está cerrado. |
| Métricas por etiqueta dentro de cada día | Es el próximo corte, pero con n=5-28 por celda va a ser ruido. Primero el diagnóstico. |
| `calidad_senal_v3` (etiquetas 14/8/4) | Es sobre el `macro_score` **legacy**, otro problema. |
| ADR 001 (k×σ) | Mueve el HR, no el PF. Decidir si vale. |
| Max DD de `report_validator.py` | Confirmado que `C4` lo calcula bien; el bug está aislado en `report_validator.py`. Hace falta el archivo. |
| Ventana 04:00-16:00 | Changes el régimen de muestreo → invalidaría la comparabilidad otra vez. Coordinar con H-10. |
| Matar los 5 fallbacks silenciosos | Toca 4 módulos. Sesión propia. |
| Backup a Drive | **Es una acción manual tuya.** Es la prioridad #1 y no la puedo hacer yo. |

---

## 4. Qué creo que está frágil (opinión sin filtros)

1. **El score v2 no puede discriminar** (H-9). Sin el término multi-timeframe y
   siempre en la misma rama, es ruido con nombre bonito. **Arreglar esto tiene
   más impacto que recalibrar cualquier umbral.**
2. **Cualquier análisis del v2 sobre las 877 señales es basura.** El grupo real
   son 111 (3 días). Y aun esas están confundidas por fecha.
3. **Los 5 fallbacks silenciosos** siguen siendo el riesgo #1 latente. Hoy no
  aroni (verificado línea por línea), pero el día que uno se dispare, el
   pipeline se degrupa y no dice nada.
4. **`main.py` corre 8 celdas, no 9**, y el runner reporta "Celdas ejecutadas: 3".
   Cosmético, pero el mapa de `AGENTS.md` miente.
5. **El auto-restore nunca se probó**: C2 dice "Sin backups previos". Si mañana
   corrompés la DB, no hay de dónde restaurar.
6. **LONG pierde, SHORT gana** (PF 0.50 vs 1.28). Y dentro de los cripto, BTC
   PF 0.30 y SP500 PF 0.28. Eso no lo arregla ningún umbral: es microestructura
   o lógica de entrada. `xyz:SILVER` (PF 3.22) y `xyz:GOLD` (2.64) sí funcionan.
   **Copiar el patrón de los que ganan vale más que recalibrar umbrales.**
7. **Cero tests.** `verificar.py` es el primer paso, no el final.

---

## 5. Qué chequear primero en la próxima sesión

1. `python verificar.py` → tiene que dar 19 ok / 0 fallas.
2. `python git\estado.py` → leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `AGENTS.md` §5.1, §5.1.b y §5.1.c — son los hallazgos de hoy.
4. Si tocás el v2: leer `AGENTS.md` §5.1.b ANTES de comparar etiquetas.

---

## 6. Cómo verificar que no rompí nada

```cmd
python verificar.py
python gitevisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 7. Cosas pendientes de confirmación (preguntas abiertas)

- **¿Qué cambió el 2026-10-19 en el pipeline?** (desplegue de v7.9.3 / cambio
  de ventana / cambio en C3_MACRO / cambio de mercado). Define si H-10 es un
  artefacto de despliegue o de diseño.
- **¿Por qué el `bias` 1D/4H/1H sale `N/A`?** El motivo está en
  `logs_v2.1\*.log` (`no_data_or_too_few` / `INSUFFICIENT` / `exception:`).
- ¿Los 4 archivos "Nivel C" se borran o se quedan?
- ¿La DB de producción (Turso) usa las mismas 22 tablas que la local?
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
- ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
