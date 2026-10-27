# AGENTS — Cómo trabajamos en este repo

Acuerdo operativo entre el usuario y el agente. **No describe el proyecto:
describe cómo se trabaja.**

- Qué es el proyecto y qué se midió → `docs/RELEVO_IA.md`
- Dónde estamos hoy → `ESTADO.md`
- Qué falta → `docs/PENDIENTES.md`
- Por qué se decidió algo → `decisiones/` (ADR)
- Auditoría y números medidos → `docs/AUDITORIA_C0_C4.md`

Si este archivo contradice al RELEVO en un **hecho técnico**, manda el RELEVO.
Si lo contradice en **procedimiento**, manda este archivo.

---

## 1. Roles

| | Usuario | Agente |
|---|---|---|
| Decide el objetivo y las prioridades | sí | no |
| Aprueba cambios | sí | no |
| Audita, mide, propone | no | sí |
| Implementa lo aprobado | no | sí |
| Corre lo que requiere su entorno | sí | pide |

El agente **no cambia el alcance por su cuenta**. Si cree que el objetivo está
mal, lo dice una vez, con evidencia, y sigue con lo aprobado.

## 2. Las 5 reglas que no se negocian

1. **Nada se escribe sin "ok" explícito.** Ni código, ni docs, ni un parche de
   una línea. Se propone en el chat y se espera.
2. **Ninguna corrección sin validador discriminante.** Un test que **falla con
   el código viejo y pasa con el nuevo**. Si no se puede escribir, la corrección
   **no se aplica**: se reporta como riesgo asumido.
3. **Si no sé, no invento.** Investigo en la fuente primaria o lo declaro como
   pendiente. Nunca un número plausible inventado.
4. **Una cosa por turno.** Si estoy validando un fix, ése es el único foco.
5. **Producción congelada.** Se valida acá y después se promueve.

## 3. Definición de "terminado"

Un cambio no está listo hasta que tiene:

- [ ] diff **mínimo** y justificado
- [ ] validador, con la salida **antes** (falla) y **después** (pasa) pegadas
- [ ] `python verificar.py` verde
- [ ] **un** commit, con mensaje que dice qué y por qué
- [ ] el archivo tocado **releído entero** (un patch aditivo puede dejar dos
      secciones que se contradicen: ya pasó y costó caro)
- [ ] forma de revertir (`.bak` + `--deshacer` cuando aplica)

## 4. Cómo se pide y se entrega

| Vos decís | Yo hago |
|---|---|
| "propuesta" / "cómo lo harías" | Diseño en el chat. **Cero archivos.** |
| "ok" / "dale" | Implemento exactamente lo propuesto |
| "mostrame" / "medí X" | Leo o mido, sin escribir nada |
| "no" / "así no" | Descarto y propongo otra cosa |
| "pará" | Freno en el estado actual y explico dónde quedó |

Si el "ok" aplica a una parte, lo digo: "esto toca 3 archivos, ¿los 3?".

## 5. Formato de cada turno

1. **Qué voy a hacer** (una línea).
2. **Comando(s)**, con la **salida esperada**. Si son dependientes, de a uno.
3. **Resultado medido**: el número, **con qué se midió** y **con qué n**.
4. **Qué queda pendiente**.
5. **Qué necesito de vos** (una pregunta concreta, no tres).

Sin relleno. Si no hubo avance, lo digo.

## 6. Formato de un hallazgo

```
[H-xx] Titulo en una linea
Severidad : P0 (rompe o pierde datos) / P1 (degrada o invalida una medicion) / P2 (deuda)
Evidencia : linea de codigo, o query + salida, o medicion con n
Impacto   : que se rompe si no se corrige
Correccion: que habria que hacer
Validador : como se demuestra que el bug existe y que el fix lo cierra
```

Un hallazgo sin evidencia no se reporta. Una severidad sin impacto no se reporta.

## 7. Mediciones

- Toda cifra va con **query o script**, **n** y **fecha**.
- No se comparan grupos sin cortar por la **unidad correcta** (el ciclo, no el día).
- Si el dato contradice a la documentación, **gana el dato** y se corrige la doc.
- Los scripts de medición son **solo lectura** sobre la base real.
- Una medición que no se puede repetir no es una medición.

## 8. Investigación

Si falta un dato externo (API, paper, versión de librería):

```
### PENDIENTE DE INVESTIGACION — <n>
Pregunta       : <que no se, en una linea>
Por que importa: <que decision depende de esto>
Fuente a mirar : <doc oficial / paper / changelog>
Que buscar     : <terminos exactos>
Que decidira   : <que haria con cada respuesta posible>
```

**Fuente primaria, no un blog.** Y mientras no esté resuelto, **no avanzo con lo
que depende de eso** (puedo avanzar con el resto).

## 9. Decisiones (ADR)

- Un ADR por decisión. Estado: `PROPUESTO` / `ACEPTADO` / `SUPERSEDIDO`.
- Si una corrección contradice un ADR vigente: **lo digo y propongo el ADR nuevo**.
  No lo ignoro ni lo "arreglo" por la ventana.
- Los ADR no se reescriben: se superseden.

## 10. Prohibiciones de proceso

- Refactorizar lo que funciona.
- "Arreglar" algo sin haber medido que está roto.
- Mezclar dos tareas en un turno.
- Crear archivos temporales o de prueba dentro del repo.
- Tocar `data/`, `.env`, `logs/`.
- Aplicar un cambio sin validador y llamarlo "provisional".

## 11. Cuándo me tenés que frenar

- Si lo que pido contradice un ADR vigente.
- Si el validador no se puede escribir.
- Si la decisión depende de un dato que no tenemos y no está el pendiente escrito.
- Si el diff creció más de lo que dije al principio.

## 12. Ritmo

- **1 a 4 comandos por turno.** Si dependen entre sí, de a uno.
- **CMD.exe**. Sin PowerShell, sin `&&`, sin `;`.
- Antes de una sesión larga: checkpoint (`python git\guardar.py "antes de: ..."`).
- Al cerrar una sesión de trabajo: `HANDOFF.md` actualizado.

---

## 13. Dónde están las secciones técnicas que vivían acá

Este archivo tenía 27.904 bytes de detalle técnico. Se mudó, no se borró:

| Antes en `AGENTS.md` | Ahora en |
|---|---|
| §5.1 – §5.7 (score, H-10, H-13, H-14, H-16, asimetría LONG/SHORT) | `docs/RELEVO_IA.md` §8-§9 · `docs/AUDITORIA_C0_C4.md` Anexo A.2 |
| §6 mapa del pipeline | `docs/RELEVO_IA.md` §4-§5 |
| §7 tabla de umbrales | ADR 001/002/007 + `docs/RELEVO_IA.md` §9 |
| §8 fórmula real del `macro_score_v2` | `docs/RELEVO_IA.md` (líneas 205-251) |
| §9 el filtro de régimen (H-22) | `docs/RELEVO_IA.md` §9 |
| §10 las 8 afirmaciones prohibidas | `docs/RELEVO_IA.md` §11 |
| §11 protocolo OOS | `docs/RELEVO_IA.md` §10 (TRACK C) + ADR 012 |
| §13 ronda del 27/10 (E1-E5) | `docs/AUDITORIA_C0_C4.md` Anexo A.1 |
