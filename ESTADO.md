# ESTADO — MACRO2.1
Actualizado: 2026-10-23 | Commit: <hash> | Tag: v2.1-I2-ok
FASE: 2 (intervenciones) | Última: I-2 ADF real — OK, validada

## FUNCIONA (verificado por verificar.py)
[x] Pipeline C0→C4 corre
[x] 845 señales en DB
[x] I-1 caja simétrica
[x] I-2 ADF real

## RIESGOS CONOCIDOS
[!] H-1: umbral ADF 0.02 vs 0.05 → fix en decisiones/002
[!] C0 escribe backups/, C2 lee backups_v2.1/ → auto-restore inoperante
[!] Sin tests. Backups de DB no automáticos.

## SIGUIENTE PASO (uno solo)
1. Aplicar ADR 002 + agregar verificar.py