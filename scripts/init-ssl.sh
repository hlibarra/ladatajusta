#!/bin/bash
set -e

# This script initializes SSL certificates using Let's Encrypt

if [ -z "$1" ]; then
    echo "Usage: ./init-ssl.sh your-domain.com your@email.com"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

echo "=== Initializing SSL for $DOMAIN ==="

# Create directories
mkdir -p certbot/www certbot/conf nginx/ssl

# Create temporary nginx config for certificate generation
cat > nginx/nginx-temp.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name DOMAIN_PLACEHOLDER;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 200 'OK';
            add_header Content-Type text/plain;
        }
    }
}
EOF

sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN www.$DOMAIN/g" nginx/nginx-temp.conf

# Start temporary nginx
docker run -d --name nginx-temp \
    -p 80:80 \
    -v $(pwd)/nginx/nginx-temp.conf:/etc/nginx/nginx.conf:ro \
    -v $(pwd)/certbot/www:/var/www/certbot \
    nginx:alpine

echo "Waiting for nginx to start..."
sleep 5

# Get certificates
docker run --rm \
    -v $(pwd)/certbot/www:/var/www/certbot \
    -v $(pwd)/certbot/conf:/etc/letsencrypt \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN

# Stop temporary nginx
docker stop nginx-temp
docker rm nginx-temp
rm nginx/nginx-temp.conf

echo "=== SSL certificates generated successfully! ==="
echo "You can now run: docker compose -f docker-compose.prod.yml up -d"
