# ADR 003 — MACRO2.1 es un clon local, sin Docker

**Estado:** ACEPTADO
**Fecha:** 2026-10-23
**Decide:** `botmacro2-1` (desarrollo) se ejecuta directo con Python en Windows.
**NO decide:** nada sobre `botmacro` (producción), que sigue igual.

---

## Contexto

`botmacro2-1` nació como clon de `botmacro` (MACRO2), que corre en Render como
Web Service con Docker. Al clonar, se copiaron también los artefactos de
despliegue: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `start.sh`
y `litestream.yml`.

Pero MACRO2.1 **nunca se ha desplegado**. Corre local, en Windows, con el
venv. Ningún `.py` del pipeline depende de Docker: la auditoría del 2026-10-23
encontró cero referencias a `docker`, `litestream` o `/app` en `main.py`,
`scheduler.py`, `ventana.py` y `report_validator.py`.

El único código que quedó acoplado era un chequeo inerte en `C1_CONFIG_local.py`:

```python
is_container = (os.name != "nt") and Path("/app").exists()
```

En Windows `os.name == "nt"` → **siempre False**. Código muerto.

Mantener esos archivos era ruido con riesgo real: cualquier IA que los leyera
podía "arreglar" el despliegue, instalar Docker, o meter `start.sh` en el
flujo local.

## Decisión

**MACRO2.1 es un proyecto local, sin Docker.**

Se eliminan de `botmacro2-1`: `Dockerfile`, `docker-compose.yml`,
`.dockerignore`, `start.sh`, `litestream.yml`.

**`botmacro` (producción) NO se toca.** Sigue con su `Dockerfile`, su
`start.sh` y su `litestream.yml` → R2. Los repos son separados: no hay
ninguna intersección. El DATA FREEZE sigue intacto.

## Consecuencias

**A favor:**
- El repo local refleja lo que realmente se ejecuta. Cero archivos mentirosos.
- Menos superficie: nadie puede deployar por accidente.
- La IA deja de intentar "reparar" un despliegue que no existe.
- Se separa el "stack de producción" (ADR 000) del "clon de trabajo" (este ADR).

**En contra / a tener en cuenta:**
- **No hay réplica a Cloudflare R2 desde 2.1.** El backup de 2.1 es local
  (`C2_BOVEDA` → `backups_v2.1/`). Para respaldar la DB de 2.1 hay que
  copiarla a mano a Drive o disco externo.
  → Esto **Eleva** la prioridad del backup externo (ver `docs/PENDIENTES.md` §6).
- Si algún día 2.1 se quiere desplegar, hay que recuperar los archivos:
  `git checkout 5e0c481 -- Dockerfile docker-compose.yml start.sh litestream.yml .dockerignore`
  o copiar los de `botmacro`.
- `C1_CONFIG_local.py` conserva el chequeo `is_container` (inerte en Windows)
  con el comentario aclarado. Se deja así a propósito: `botmacro` tiene su
  propia copia de ese archivo y el bloque sigue siendo necesario allá.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Borrar Docker también de `botmacro` | Rompe producción. Fuera de alcance (DATA FREEZE). |
| Dejar los archivos, "por si acaso" | Son la causa de la confusión. El historial de git los conserva. |
| Borrar el bloque `is_container` de `C1_CONFIG` | No cambia el comportamiento en Windows (siempre False) y obliga a tocar un archivo central. El comentario aclarado alcanza. |
| Instalar Docker localmente | No hace falta para nada del pipeline. |

## Cómo se verifica

```cmd
dir /a Dockerfile docker-compose.yml start.sh litestream.yml .dockerignore
```
→ "No se encuentra el archivo" en los 5.

```cmd
python verificar.py
```
→ 19 ok / 0 fallas / 1 aviso (el aviso es el de los 5 fallbacks silenciosos).

```cmd
git status
```
→ en el repo `botmacro`, ningún cambio.
