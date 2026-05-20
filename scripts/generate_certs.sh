#!/usr/bin/env bash
# Generate self-signed SSL certificate for development
set -e

CERT_DIR="$(cd "$(dirname "$0")/../certs" && pwd)"
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    echo "Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 \
        -keyout "$CERT_DIR/key.pem" \
        -out "$CERT_DIR/cert.pem" \
        -days 365 -nodes \
        -subj "/CN=ostonecufar.local"
    echo "Certificate generated: $CERT_DIR"
else
    echo "Certificate already exists: $CERT_DIR"
fi
