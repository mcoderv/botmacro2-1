FROM python:3.12-slim

# Instalar dependencias del sistema para Litestream
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Instalar Litestream (binario de Go)
RUN curl -L https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.tar.gz -o litestream.tar.gz \
    && tar -xzf litestream.tar.gz -C /usr/local/bin \
    && rm litestream.tar.gz \
    && chmod +x /usr/local/bin/litestream

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del bot
COPY . .

# Copiar configuración de Litestream y script de inicio
COPY litestream.yml /etc/litestream.yml
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8080
CMD ["/app/start.sh"]