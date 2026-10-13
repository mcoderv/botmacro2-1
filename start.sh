#!/bin/sh
set -e

echo "🦅 mercabot_qwen | Iniciando contenedor..."

# 1. Crear directorio de datos
mkdir -p /app/data

# 2. Debug: verificar que las credenciales de R2 llegaron al contenedor
echo "🔍 DEBUG env vars:"
echo "   R2_BUCKET            = ${R2_BUCKET:-<VACIO>}"
echo "   R2_ENDPOINT          = ${R2_ENDPOINT:-<VACIO>}"
echo "   R2_ACCESS_KEY_ID     = ${R2_ACCESS_KEY_ID:+OK}"
echo "   R2_SECRET_ACCESS_KEY = ${R2_SECRET_ACCESS_KEY:+OK}"

# 3. Restaurar DB desde R2 (si existe backup previo)
#    NOTA: 'restore' SÍ acepta el path posicional — busca ese DB en el config
echo "📥 Restaurando DB desde R2..."
litestream restore -config /etc/litestream.yml /app/data/vault_v2.db \
  || echo "⚠️ Sin backup previo en R2 (primer deploy). Continuando..."

# 4. Iniciar replicación continua en background
#    CRÍTICO: NO pasar path posicional — si se pasa, Litestream ignora el config
#    y falla con "must specify at least one replica URL"
echo "🔄 Iniciando replicación Litestream..."
litestream replicate -config /etc/litestream.yml &

# 5. Iniciar el scheduler en foreground (exec para heredar señales SIGTERM de Render)
echo "🚀 Iniciando scheduler..."
exec python scheduler.py