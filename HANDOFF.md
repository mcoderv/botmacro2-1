# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a los chats viejos que venías guardando a mano.
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `docs/PENDIENTES.md`
> + `git log --oneline -20` + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-23
Sesion   : 2
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : 5e0c481
```

---

## 1. Qué hice en esta sesión

- **Kit de git** — `git/guardar.py`, `estado.py`, `deshacer.py`, `revisar_archivo.py`.
  Ahora no dependo de saber git.
- **ADR 002 aplicado** (commit `5361b4f`): umbral ADF unificado en **0.05**,
  fuente única `CENTRAL_PARAMS["macro"]`. Se corrigió también **H-3**
  (`backups_v2.1` / `logs_v2.1`) y **H-5** (`_migrar_v28` ahora sobrescribe).
- **`verificar.py`** — 19 ok / 0 fallas / 1 aviso. Es el contrato ejecutable
  del proyecto: lo que él chequea, no se rompe en silencio.
- **Re-score del umbral ADF** (`analisis/rescore_umbral.py`) — primera medición
  real del efecto de ADR 002. **Dio falsos positivos** (ver §3.1).
- **Docker eliminado de MACRO2.1** (ADR 003, commit `5e0c481`): `Dockerfile`,
  `docker-compose.yml`, `.dockerignore`, `start.sh`, `litestream.yml`.
  **Producción (`botmacro`) intacta.**
- **`docs/` reordenada** — una sola carpeta con reglas claras:
  `docs/INFORME_MACRO2.1.md` (spec), `docs/PENDIENTES.md` (tracking),
  `docs/info/`, `docs/investigaciones/` (+`PLANTILLA.md`), `docs/local/`
  (fuera de GitHub). `textos/` desapareció.

---

## 2. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Arreglar `rescore_umbral.py` v1 | Re-scoreó placeholders (ms_v2=0) → falsos positivos. La v2 es el siguiente paso. |
| `calidad_senal_v3` (etiquetas) | Necesita la distribución real de `macro_score`. Con 58 señales de v2, hay que ver si alcanza. |
| ADR 001 (k×σ) | Es un cambio de un solo archivo (`C4`), pero **el PF no se va a mover**. Decidir si vale. |
| Max DD de `report_validator.py` | No tengo el archivo para auditarlo. Pedirlo. |
| Ventana 04:00-16:00 | Cambia el régimen de muestreo → los datos nuevos no son comparables con los viejos. Decisión de negocio. |
| Backup externo de la DB | Es una acción manual tuya (copiar a Drive/disco). **Es la prioridad #1.** |
| Borrar los 4 archivos "Nivel C" | `evaluar_nube.py`, `test_telegram.py`, `verificar_progreso.bat`, `diagnostico_bat.py` — siguen sin respuesta. No son dañinos. |
| Tocar producción (`botmacro`) | DATA FREEZE. |

---

## 3. Qué creo que está frágil (opinión sin filtros)

1. **El 85% de las señales NO tiene score v2 reconstruible — y NO es un bug.**
   `ms_v2` se agregó en v7.9.3 (reciente); lo anterior quedó en 0. De 877
   señales: **58** con `ms_v2 >= 2`, **70** con score bajo pero coherente,
   **749 incoherentes** (no computadas). El grupo de trabajo real es de
   **128 señales**. Cualquier estadística del v2 sobre 877 es basura.

2. **El re-score v1 dio falsos positivos.** Re-scoreó las señales con
   `ms_v2 = 0` como si tuvieran un score. De sus "10 que cambian de rama", 9
   eran HYPE con `ms_v2 = 0.00` → inventadas. La auto-validación 2 (coherencia
   de `s_mtf`) saltó: solo 128/877 (14.6%) cuadraban. **Ese script no se usa
   hasta que excluya los placeholders.**

3. **5 imports con fallback silencioso.** Es el riesgo #1 del proyecto. Si
   cambiás la firma de una función, el pipeline **se degrupa en silencio** y
   no falla. Ya lo dice el aviso de `verificar.py`, pero nadie lo arregló.

4. **El PF no depende del umbral de break-even.** `C4` usa el 0.05% solo para
   el HR; el PF usa `p > 0` / `p < 0`. Si la expectativa con ADR 001 es "ver el
   PF subir al destrabar el umbral", **eso no va a pasar**. El ADR 001 solo
   mueve el HR.

5. **LONG pierde, SHORT gana** (PF 0.50 vs 1.28). Y dentro de los cripto,
   BTC PF 0.30 y SP500 PF 0.28. Eso no lo arregla ningún umbral: es
   microestructura o la lógica de entrada. `xyz:SILVER` (PF 3.22) y
   `xyz:GOLD` (2.64) sí funcionan. **Copiar el patrón de los que ganan
   probablemente vale más que recalibrar umbrales.**

6. **Cero tests.** `verificar.py` es el primer paso, no el final. Un `assert`
   de una línea sobre el umbral ADF habría cazado H-1 hace semanas.

7. **La DB no tiene backup fuera del disco.** Es lo único no recuperable de
   GitHub. 10 meses de evidencia en un solo archivo.

---

## 4. Qué chequear primero en la próxima sesión

1. `python verificar.py` → tiene que dar 19 ok / 0 fallas.
2. `python git\estado.py` → leer el "SIGUIENTE PASO" del `ESTADO.md`.
3. `docs/PENDIENTES.md` → la lista de trabajo.
4. Si tocás el v2: leer `AGENTS.md` §5.1 y §5.2 **antes** de medir nada.

---

## 5. Cómo verificar que no rompí nada

```cmd
python verificar.py
python git\revisar_archivo.py <archivo_modificado>
```

Criterio de aceptación: `verificar.py` sin FALLAS, y el diff del commit
solo toca lo que el ADR dice que tiene que tocar.

---

## 6. Cosas pendientes de confirmación (preguntas abiertas)

- **¿La DB de producción (Turso) usa las mismas 22 tablas que la local?**
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
  (39 KB cada uno de `scheduler.py` y `report_validator.py` lo sugiere)
- ¿Los 4 archivos "Nivel C" (`evaluar_nube.py`, `test_telegram.py`,
  `verificar_progreso.bat`, `diagnostico_bat.py`) se borran o se quedan?
- **¿La `GUIA DE USO.txt` sigue al día?** Ahora está versionada en `docs/`.
- **¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?**
