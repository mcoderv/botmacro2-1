#!/bin/sh
set -e

echo "🦅 mercabot_qwen | Iniciando contenedor..."

# 1. Crear directorio de datos
mkdir -p /app/data

# 2. Restaurar DB desde R2 (si existe)
echo "📥 Restaurando DB desde R2..."
litestream restore -config /etc/litestream.yml /app/data/vault_v2.db || echo "⚠️ No había DB previa en R2. Continuando..."

# 3. Iniciar Litestream en background para replicación continua
echo "🔄 Iniciando replicación Litestream..."
litestream replicate -config /etc/litestream.yml /app/data/vault_v2.db &

# 4. Iniciar el scheduler en foreground (exec para manejar señales SIGTERM de Render)
echo "🚀 Iniciando scheduler..."
exec python scheduler.py