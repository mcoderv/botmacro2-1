#!/bin/sh
set -e

echo "🦅 mercabot_qwen | Iniciando contenedor..."

mkdir -p /app/data

# Verificar que las credenciales llegaron al contenedor (no imprime secretos)
echo "🔍 DEBUG env vars:"
echo "   R2_BUCKET            = ${R2_BUCKET:-<VACIO>}"
echo "   R2_ENDPOINT          = ${R2_ENDPOINT:-<VACIO>}"
echo "   R2_ACCESS_KEY_ID     = ${R2_ACCESS_KEY_ID:+OK}"
echo "   R2_SECRET_ACCESS_KEY = ${R2_SECRET_ACCESS_KEY:+OK}"

# Restore: SÍ lleva el path posicional (busca ese DB dentro del config)
echo "📥 Restaurando DB desde R2..."
litestream restore -config /etc/litestream.yml /app/data/vault_v2.db \
  || echo "⚠️ Sin backup previo en R2 (primer deploy). Continuando..."

# Replicate: SIN path posicional (crítico — si se pasa, ignora el config)
echo "🔄 Iniciando replicación Litestream..."
litestream replicate -config /etc/litestream.yml &

echo "🚀 Iniciando scheduler..."
exec python scheduler.py