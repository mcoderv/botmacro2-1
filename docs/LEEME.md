# docs/ — qué va dónde

## Las 3 categorías

| Carpeta | Qué es | ¿Sube a GitHub? |
|---------|--------|-----------------|
| `docs/` (raíz) | La spec vigente + la lista de trabajo | Sí |
| `docs/info/` | Specs de referencia y linaje de datos | Sí |
| `docs/investigaciones/` | Tus investigaciones, con fuentes | Sí |
| `docs/local/` | Chats de IA, borradores, material viejo | **No** (está en `.gitignore`) |

## La regla, en una línea

> Si **la próxima IA necesita leerlo** → versionado.
> Si **es soporte tuyo** (chats, borradores, material viejo) → `docs/local/`.

## Flujo de investigación

Cuando una IA no sepa algo:

1. **Buscar primero** en `docs/investigaciones/` — puede estar ya resuelto.
2. Si no está: investigar y guardar en `docs/investigaciones/` usando `PLANTILLA.md`.
3. Si el hallazgo **cambia una decisión** del proyecto → crear un ADR en `decisiones/`.

## Chats de IA

Van a `docs/local/chats/`. **No se versionan a propósito**: el valor de un chat
está en lo que se extrajo de él, no en el chat en sí. Si algo de un chat
importa, se destila a una investigación o a un ADR.

Los chats viejos (`chats_ant/`) quedaron en `docs/local/chats/chats_ant/`.
La `GUIA DE USO` y el `prompt_inicial` si quedan versionados en `docs/`.
