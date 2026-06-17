# Production Deployment Guide

## Prerequisites

- Python 3.9+
- PostgreSQL database
- Gunicorn (WSGI server)
- Nginx (recommended for reverse proxy)
- SSL certificate (Let's Encrypt recommended)

## Step 1: Server Setup

### Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib nginx
```

**For WeasyPrint PDF generation:**
```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libjpeg-dev libgif-dev librsvg2-dev
```

## Step 2: Clone and Configure

```bash
git clone <your-repo-url> /var/www/school
cd /var/www/school
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

## Step 3: Environment Configuration

Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set the generated key in `.env`:
```env
FLASK_SECRET_KEY=<your-generated-secret-key>
SUPERADMIN_SECRET_KEY=<another-generated-secret-key>
FLASK_DEBUG=false
```

Configure PostgreSQL connection:
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=school_prod
```

## Step 4: Database Setup

Create PostgreSQL database:
```bash
sudo -u postgres psql
CREATE DATABASE school_prod;
CREATE USER school_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE school_prod TO school_user;
\q
```

## Step 5: Systemd Service Files

### Main Application Service

Create `/etc/systemd/system/school.service`:
```ini
[Unit]
Description=School Management System
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/school
Environment="PATH=/var/www/school/.venv/bin"
EnvironmentFile=/var/www/school/.env
ExecStart=/var/www/school/.venv/bin/gunicorn wsgi.py:application -c gunicorn_config.py

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Super Admin Service

Create `/etc/systemd/system/school-admin.service`:
```ini
[Unit]
Description=School Management System - Admin Portal
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/school
Environment="PATH=/var/www/school/.venv/bin"
EnvironmentFile=/var/www/school/.env
ExecStart=/var/www/school/.venv/bin/gunicorn wsgi_superadmin.py:application -c gunicorn_superadmin_config.py

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Step 6: Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable school
sudo systemctl enable school-admin
sudo systemctl start school
sudo systemctl start school-admin
```

Check status:
```bash
sudo systemctl status school
sudo systemctl status school-admin
```

## Step 7: Nginx Configuration

### Main Application

Create `/etc/nginx/sites-available/school`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/school/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Admin Portal

Create `/etc/nginx/sites-available/school-admin`:
```nginx
server {
    listen 80;
    server_name admin.your-domain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/school/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable sites:
```bash
sudo ln -s /etc/nginx/sites-available/school /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/school-admin /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 8: SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d admin.your-domain.com
```

## Step 9: Firewall Configuration

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## Monitoring

View application logs:
```bash
sudo journalctl -u school -f
sudo journalctl -u school-admin -f
```

## Security Checklist

- [ ] `FLASK_DEBUG=false` in production
- [ ] Strong `FLASK_SECRET_KEY` and `SUPERADMIN_SECRET_KEY` set
- [ ] PostgreSQL credentials are secure and database user has minimal permissions
- [ ] File upload directory is not accessible via web browser
- [ ] SSL certificate installed and HTTPS enforced
- [ ] Firewall configured to only allow necessary ports
- [ ] Regular PostgreSQL backups configured
- [ ] Sensitive files (`.env`) have proper permissions (600)

## Troubleshooting

Service won't start:
```bash
sudo journalctl -u school -n 50
```

PDF generation issues:
Ensure system dependencies for WeasyPrint are installed:
```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libjpeg-dev libgif-dev librsvg2-dev
```
