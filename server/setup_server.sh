#!/usr/bin/env bash
# setup_server.sh — Установка сервера базы контактов на Ubuntu 22.04
set -e

SERVER_IP="155.212.139.151"
BAZA_DIR="/opt/baza"
DATA_DIR="$BAZA_DIR/data"
SSL_DIR="$BAZA_DIR/ssl"
VENV="$BAZA_DIR/venv"
SERVICE="baza-api"

echo "=== [1/7] Обновление системы ==="
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv openssl

echo "=== [2/7] Создание директорий ==="
mkdir -p "$DATA_DIR" "$SSL_DIR"
useradd --system --no-create-home --shell /usr/sbin/nologin baza 2>/dev/null || true
chown -R baza:baza "$BAZA_DIR"

echo "=== [3/7] Виртуальное окружение Python ==="
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$BAZA_DIR/requirements.txt"

echo "=== [4/7] Генерация SSL-сертификата (самоподписанный, 10 лет) ==="
if [ ! -f "$SSL_DIR/cert.pem" ]; then
    openssl req -x509 -newkey rsa:4096 \
        -keyout "$SSL_DIR/key.pem" \
        -out    "$SSL_DIR/cert.pem" \
        -days 3650 -nodes \
        -subj "/C=RU/O=Baza/CN=$SERVER_IP" \
        -addext "subjectAltName=IP:$SERVER_IP"
    chmod 640 "$SSL_DIR/key.pem"
    chown baza:baza "$SSL_DIR/key.pem" "$SSL_DIR/cert.pem"
    echo "  Сертификат создан: $SSL_DIR/cert.pem"
else
    echo "  Сертификат уже существует, пропускаем."
fi

echo "=== [5/7] Systemd-сервис ==="
cat > /etc/systemd/system/$SERVICE.service << 'EOF'
[Unit]
Description=Baza Contacts API Server
After=network.target

[Service]
Type=simple
User=baza
WorkingDirectory=/opt/baza
Environment="BAZA_DATA_DIR=/opt/baza/data"
Environment="BAZA_SSL_DIR=/opt/baza/ssl"
ExecStart=/opt/baza/venv/bin/python server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE

echo "=== [6/7] Настройка firewall ==="
ufw allow 8443/tcp comment "Baza API" 2>/dev/null || iptables -I INPUT -p tcp --dport 8443 -j ACCEPT 2>/dev/null || true

echo "=== [7/7] Запуск сервиса ==="
systemctl restart $SERVICE
sleep 2
systemctl status $SERVICE --no-pager

echo ""
echo "✓ Сервер запущен на https://$SERVER_IP:8443"
echo ""
echo "Следующий шаг — скопировать baza.db и baza.key в $DATA_DIR:"
echo "  scp /путь/к/baza.db root@$SERVER_IP:$DATA_DIR/"
echo "  scp /путь/к/baza.key root@$SERVER_IP:$DATA_DIR/"
echo "  systemctl restart $SERVICE"
echo ""
echo "Скачать сертификат для клиента:"
echo "  scp root@$SERVER_IP:$SSL_DIR/cert.pem ./"
