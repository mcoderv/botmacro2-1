# HANDOFF — MACRO2.1

> **Se reescribe en CADA cierre de sesión.** Es el archivo que reemplaza
> a `docs/chats_ant/` (los 7 chats viejos que venías guardando a mano).
>
> Cuando cambies de IA, el paquete de traspaso es:
> `AGENTS.md` (auto) + `ESTADO.md` + `HANDOFF.md` + `git log --oneline -20`
> + salida de `python verificar.py`.
> Con eso, la IA nueva arranca entendiendo el proyecto. Sin esto, arranca de cero.

```
Fecha    : 2026-10-23
Sesion   : 1
Repo     : botmacro2-1 (desarrollo)  —  NUNCA botmacro (produccion congelada)
Commit   : 1f2c5bb
```

---

## 1. Qué hice en esta sesión

- Se creó el repo `botmacro2-1` en GitHub y se migró el remoto `origin`
  a ese repo nuevo, dejando `origin-macro2` apuntando a `botmacro` (producción).
- Commit `1f2c5bb`: checkpoint con I-1 (caja simétrica), I-2 (ADF real),
  ADR 000/001/002, scripts de análisis y corrección del `.gitignore`.
- Se creó el kit de gestión: `AGENTS.md`, `ESTADO.md`, `HANDOFF.md`,
  `verificar.py` y los 4 scripts de `git/`.
- Se detectó y documentó el bug **H-1** (umbral ADF 0.02 vs 0.05) y **H-3**
  (C0 escribe en `backups/`, C2 lee de `backups_v2.1/`).

---

## 2. Qué NO hice (y por qué)

| No hice | Por qué |
|---|---|
| Mover `ADF_P_VALUE_THRESHOLD` a la sección `macro` | Requiere tocar `C1_5_PARAM` + `C3_MACRO` + `_migrar_v28`. Es el ADR 002, va con su propio commit. |
| Arreglar el bucket en `decisiones/000` | Es un cambio de doc, pero el ADR describe producción: necesita revisión aparte. |
| Extraer el ZIP de `docs/investigaciones/` | Requiere decidir dónde queda el contenido extraído. |
| Implementar `calidad_senal_v3` | Necesita la distribución real de `macro_score` de las 845 señales primero. |
| Mover/actualizar `main.py`, `scheduler.py`, `ventana.py` | No los revisé: no estaban en el material compartido. |
| Tocar producción (`botmacro`) | Está en DATA FREEZE. |

---

## 3. Qué creo que está frágil (opinión sin filtros)

1. **H-1 es lo más grave.** El motor de régimen dice 0.05 y el score dice 0.02.
   Con p=0.0485 (ejemplo real de BTC), C3_5 clasifica RANGE pero C3_MACRO
   aplica la rama de *momentum*. **Todas las cifras del informe técnico
   (HR 32.9%, PF 0.50, etc.) están medidas con esa incoherencia.**
   No sonWrong: son *inconsistentes*. Hay que re-medir después del fix.

2. **La migracion `_migrar_v28` no sobrescribe** (usa `if k not in val_sec`).
   Si cambiás el default en el código y el `central_params.json` ya guardado
   tiene el valor viejo, **no se aplica** y el banner va a mentir mostrando
   0.05 mientras el comportamiento sigue en 0.02.

3. **`C4` tiene dos criterios distintos**: el HR usa el umbral 0.05, el
   Profit Factor usa `p > 0` / `p < 0`. Cuando se implemente k×σ, **el PF
   no se va a mover**. Si la expectativa es "ver el PF subir al destrabar
   el umbral", no va a pasar.

4. **El filtro de entrada de `C4` es `|macro_score| >= 2`**
   (`STRONG_BIAS_THRESHOLD`). Con umbrales 4/3/2, la etiqueta "RUIDO" queda
   **vacía** → se pierde un nivel de la taxonomía.

5. **La ventana horaria 08:00-17:00 no vive en el pipeline**, vive en
   `ventana.py`/`scheduler.py`. Ampliarla a 04:00-16:00 cambia el régimen de
   muestreo → los datos nuevos no son comparables con las 845 señales viejas.

6. **Cero tests.** Un `assert` de una línea sobre el umbral ADF habría
   cazado H-1 hace semanas. `verificar.py` es el primer paso, no el final.

7. **Los chats viejos** (`docs/chats_ant/`) tienen información que no está
   en ningún otro lado. Están commiteados, así que no se pierden, pero
   quedan fuera del flujo: de acá en adelante, `HANDOFF.md` los reemplaza.

---

## 4. Qué chequear primero en la próxima sesión

1. `python verificar.py` → ver qué falla ahora mismo.
2. `python git\estado.py` → leer el "SIGUIENTE PASO" que sale del `ESTADO.md`.
3. Si el próximo paso es ADR 002: leer `decisiones/002-Unificar el umbral ADF`
   **y** `decisiones/001-umbral-dinamico-volatilidad-PENDIENTE.md`.

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

- ¿La DB de producción (Turso) usa las mismas 18 tablas que la local?
- ¿`main.py` ejecuta las celdas en el mismo orden que el runner de Render?
- ¿El `scheduler.py` local y el de Render comparten código o están duplicados?
  (39 KB cada uno de `scheduler.py` y `report_validator.py` sugiere duplicación)
- ¿El ZIP de `docs/investigaciones/` contiene algo que no esté en los .txt?
