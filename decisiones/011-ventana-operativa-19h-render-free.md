# ADR 011 — Ventana operativa: 19 h en Render free (no 8-17, no 24/7)

- **Estado:** PROPUESTO (esperando decisión del usuario)
- **Fecha:** 2026-10-26
- **Alcance:** `C1_5_PARAM_local.py`, `central_params.json`, `ventana.py`.
- **Problema:** H-21 + la zona horaria resuelta.

## Contexto

### La zona horaria (resuelta el 26/10)

3 pares epoch↔`fecha_hora` de la propia DB:

```
1791894866 → 2026-10-13 08:35:03   offset −3,99 h
1792432869 → 2026-10-19 14:07:12   offset −3,90 h
1792799471 → 2026-10-23 19:51:11   offset −4,00 h
```

**⇒ La DB guarda HORA LOCAL CARACAS (UTC−4).** ⇒ El análisis por hora es en
Caracas. (La segunda opinión mezcló Caracas con UTC: su conclusión "migrar a
VPS por las 20:00" quedaba sin base.)

### El problema: el recorte quita la mejor franja

| Hora Caracas | HR 4h | n | ¿En 04:00-16:00? |
|---|---|---|---|
| 08:00 | 7,1% | 14 | **SÍ — y es la peor hora** |
| 09:00 | 40,0% | 10 | sí |
| 10:00 | 20,0% | 10 | sí |
| 13:00 | 23,5% | 17 | sí |
| 14:00 | 30,0% | 20 | sí |
| 15:00 | 55,6% | 18 | sí |
| 16:00 | 33,3% | 18 | no |
| **20:00** | **76,0%** | **25** | **NO — y es la mejor** |
| 21:00 | 0,0% | 7 | no |

**⇒ El recorte 04:00-16:00 conserva la peor hora y descarta la mejor.**

### El presupuesto de Render free

El free tier da **750 h/mes**. Con la ventana en minutos y el ciclo alineado a
la cuadrícula de 15 min:

| Opción | h/día | h/mes (31 d) | % del tier | ¿captura las 20:00? |
|---|---|---|---|---|
| 04:00-16:00 (12 h) | 12 | 360-372 | 48-50% | ❌ |
| **04:00-23:00 (19 h)** | **19** | **570-589** | **76-78%** | **✅** |
| 24/7 | 24 | 744 | **99,2%** ⚠️ | ✅ |

**⇒ ⭐ 24/7 en Render free es aritméticamente viable pero deja 6 h de margen
(sin margen si el mes tiene 31 días y hay reinicios). 19 h deja 21% de margen.**

**⇒ Y con el rate limit arreglado (A1), 19 h/día ⇒ ~60-80 corridas/día
(hoy 4-8) ⇒ el grano de ciclo se multiplica ⇒ el OOS se vuelve posible.**

## Decisión (PROPUESTA)

**Ventana por defecto: 04:00-23:00 Caracas (19 h)**, modo VENTANA.
CONTINUO queda disponible con 1 comando para VPS (ADR 006).

**⇒ Requiere H-21 primero**: `en_ventana()` hoy trabaja con **hora entera** ⇒
`VENTANA_FIN=16` corta el ciclo de las 16:00 y no permite expresar 03:40/16:20.
El fix es migrar a **minutos del día** (`"04:00"` / `"23:00"`).

## Consecuencias

**A favor:**
- Captura la franja de las 20:00 (HR 76%, n=25) ⇒ más ciclos por día ⇒ N más
  grande en el OOS.
- 78% del tier ⇒ margen para reinicios y para el auto-restore.
- Mismo modo CONTINUO para VPS (sin tocar código).

**En contra / a tener en cuenta:**
- **n por hora es 7-25 ⇒ NO alcanza para decidir nada.** La franja de las 20:00
  puede ser ruido ⇒ la ventana es un **parámetro a calibrar**, no una decisión
  final.
- A 19 h/día el consumo de horas sube ⇒ hay que vigilar el tier.
- Si el rate limit (A1) NO se arregla, 19 h/día **no** da 60-80 corridas/día
  ⇒ la hipótesis de la tabla se cae ⇒ **A1 es prerrequisito de esta ADR.**

## Alternativas descartadas

- **A) Mantener 04:00-16:00.** Descartado: descarta la mejor franja y conserva
  la peor, con el mismo consumo de horas que la opción de 19 h es más barata
  que 24/7.
- **B) 24/7 en Render free.** Descartado por ahora: 744 h/mes = 99,2% del
  tier ⇒ cualquier reinicio se come el margen. **Se revisita si A1 reduce el
  costo por ciclo Y el tier sube.**
- **C) VPS.** Descartado por ahora: no hace falta para el OOS si 19 h dan
  suficientes ciclos. Es la opción si A1+A7 no dan N suficiente.

## Relación

- **ADR 006** (ventana configurable) ya da el mecanismo.
- **H-21** es el prerrequisito técnico.
- **A1** es el prerrequisito de negocio.