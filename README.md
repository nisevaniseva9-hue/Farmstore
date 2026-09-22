# Farm Fresh — Farm-to-Customer E-commerce (Django)

A traditional, server-rendered Django application for a single-farmer
fruit/vegetable/dairy e-commerce store. No SPA framework, no Node.js
build tooling, minimal JavaScript. Built for low disk/resource usage on Linux.

**Stack:** Python 3, Django, PostgreSQL, Django Templates, Bootstrap 5, Gunicorn, Nginx (production).

---

## Project status: Phase 1 of 9

This repo is built incrementally, phase by phase (see `PHASES.md` conceptually
below). Phase 1 delivers: project skeleton, PostgreSQL config, base template +
Bootstrap, authentication, customer/farmer roles, environment config, and a
health/home page.

| Phase | Contents | Status |
|---|---|---|
| 1 | Project setup, auth, roles, base template | ✅ Done & verified |
| 2 | Categories, products, product images, farmer CRUD | ✅ Done & verified |
| 3 | Inventory, stock transactions, overselling prevention | ✅ Done & verified |
| 4 | Product browsing, cart | ✅ Done & verified |
| 5 | Checkout, addresses, orders | ✅ Done & verified |
| 6 | Farmer dashboard, delivery scheduling | ✅ Done & verified |
| 7 | UPI payment (manual verification) | ✅ Done & verified |
| 8 | WhatsApp notifications | ✅ Done & verified |
| 9 | Production hardening (Nginx/Gunicorn/security) | ✅ Done & verified |

---

## 1. Prerequisites (Linux)

```bash
python3 --version        # 3.10+
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip postgresql postgresql-contrib
```

## 2. PostgreSQL setup

```bash
sudo -u postgres psql
```

Then, inside the `psql` prompt, run:

```sql
CREATE USER farmstore_user WITH PASSWORD 'devpassword123';
CREATE DATABASE farmstore_dev OWNER farmstore_user;
ALTER ROLE farmstore_user SET client_encoding TO 'utf8';
ALTER ROLE farmstore_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE farmstore_user SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE farmstore_dev TO farmstore_user;
-- Needed so `manage.py test` can create/drop its own test database:
ALTER USER farmstore_user CREATEDB;
\q
```

> Change `devpassword123` to a real password, and update `.env` to match
> (see below). Never commit real credentials.

## 3. Python environment & installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Environment configuration

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `SECRET_KEY` — generate one with:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- `DB_PASSWORD` — matching the password you set in step 2
- `DEBUG=True` for local development

## 5. Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## 6. Create the farmer/admin account

```bash
python manage.py createsuperuser
```

After creating it, promote the account to the Farmer role either via
`/admin/` (Users → select user → Role → Farmer/Admin) or the Django shell:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='YOUR_USERNAME')
u.role = User.Role.FARMER
u.save()
"
```

## 7. Run tests

```bash
python manage.py test
```

## 8. Run the development server

```bash
python manage.py runserver
```

Visit:
- `http://127.0.0.1:8000/` — homepage
- `http://127.0.0.1:8000/health/` — health check (returns `OK`)
- `http://127.0.0.1:8000/account/register/` — customer registration
- `http://127.0.0.1:8000/account/login/` — login
- `http://127.0.0.1:8000/admin/` — Django admin (farmer/superuser only)
- `http://127.0.0.1:8000/farmer/` — custom farmer dashboard (Phase 2+)

---

## Project structure

```
farmstore/
├── manage.py
├── config/                  # settings, root urls, wsgi/asgi, context processors
├── apps/
│   ├── accounts/            # custom User, CustomerProfile, Address, auth views
│   └── catalog/             # Category, Product, ProductImage, farmer CRUD (Phase 2)
├── templates/
│   ├── base.html, partials/, accounts/, catalog/, farmer/
├── static/
│   ├── css/site.css, js/site.js
├── media/                   # uploaded product images (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Design notes

- **Custom `User` model** (`apps.accounts.models.User`) with a `role` field
  (`customer` / `farmer`) instead of relying only on `is_staff`/`is_superuser`,
  so business logic can cleanly branch on role.
- **PostgreSQL only.** SQLite is intentionally not supported, per project requirements.
- **No SPA.** All pages are server-rendered Django templates with Bootstrap 5.
  JavaScript is limited to small enhancements (see `static/js/site.js`).
- **Environment-based config** via `python-decouple`. No secrets in source.

## Production deployment (Nginx + Gunicorn)

Target stack: **Linux + Nginx + Gunicorn + Django + PostgreSQL**, no Docker.

All deployment files live under `deploy/`:

```
deploy/
├── nginx/farmstore.conf              # Nginx server block template
├── systemd/farmstore-gunicorn.service # systemd unit for Gunicorn
└── scripts/
    ├── backup_db.sh                  # pg_dump -> gzip, keeps 14 days
    └── restore_db.sh                 # restores a backup (drops + recreates DB)
```

### 1. Server prep

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip postgresql nginx certbot python3-certbot-nginx
sudo adduser --system --group deploy   # dedicated non-root user to run the app
```

### 2. Get the code onto the server and set up the environment

```bash
# as the deploy user, e.g. /home/deploy/farmstore
git clone <your-repo-url> farmstore   # or scp/rsync the project up
cd farmstore
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   DEBUG=False
#   SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
#   ALLOWED_HOSTS=yourfarmdomain.com,www.yourfarmdomain.com
#   CSRF_TRUSTED_ORIGINS=https://yourfarmdomain.com,https://www.yourfarmdomain.com
#   DB_* -> your production PostgreSQL credentials (see PostgreSQL setup above)
#   SECURE_SSL_REDIRECT=True   (leave True once HTTPS is live -- see step 5)
```

### 3. Database and static files

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
mkdir -p logs
```

### 4. Gunicorn as a systemd service

Edit `deploy/systemd/farmstore-gunicorn.service` first: set `User`/`Group` to
your deploy user, and fix `WorkingDirectory`/`ExecStart` paths to match
where you actually deployed the project.

```bash
sudo cp deploy/systemd/farmstore-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now farmstore-gunicorn
sudo systemctl status farmstore-gunicorn
sudo journalctl -u farmstore-gunicorn -f   # tail logs
```

### 5. Nginx + HTTPS

Edit `deploy/nginx/farmstore.conf` first: set `server_name` to your real
domain and fix the `alias` paths for `/static/` and `/media/` to match your
deployment path.

```bash
sudo cp deploy/nginx/farmstore.conf /etc/nginx/sites-available/farmstore
sudo ln -s /etc/nginx/sites-available/farmstore /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# Once the site is reachable over plain HTTP on your domain, get a free
# certificate and let certbot wire up the HTTPS server block + redirect:
sudo certbot --nginx -d yourfarmdomain.com -d www.yourfarmdomain.com
```

After certbot runs, confirm `.env` has `SECURE_SSL_REDIRECT=True` and
restart Gunicorn (`sudo systemctl restart farmstore-gunicorn`) so Django
also starts enforcing HTTPS at the application level (HSTS, secure
cookies, etc — see `config/settings.py`).

### 6. Deploying an update later

```bash
cd /home/deploy/farmstore
git pull   # or however you sync new code
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart farmstore-gunicorn
```

### 7. Backups

```bash
chmod +x deploy/scripts/backup_db.sh deploy/scripts/restore_db.sh
./deploy/scripts/backup_db.sh          # writes to ~/backups by default
```

Add it to cron for nightly backups:

```bash
crontab -e
# add:
0 2 * * * /home/deploy/farmstore/deploy/scripts/backup_db.sh >> /home/deploy/backups/backup.log 2>&1
```

To restore: `./deploy/scripts/restore_db.sh /path/to/backup.sql.gz` (this
drops and recreates the database, so double-check the filename first).

### Production security checklist

Verify before going live:

- [ ] `DEBUG=False` in `.env`
- [ ] `SECRET_KEY` is a real random value, not the placeholder
- [ ] `ALLOWED_HOSTS` lists your actual domain(s) only
- [ ] `CSRF_TRUSTED_ORIGINS` lists your `https://` domain(s)
- [ ] `python manage.py check --deploy` reports no issues (run this after
      setting the above — it's the single command that verifies most of
      this list automatically)
- [ ] HTTPS is live (certbot) and `SECURE_SSL_REDIRECT=True`
- [ ] PostgreSQL password is strong and not reused elsewhere
- [ ] `.env` is not committed to git (`.gitignore` already covers this)
      and is only readable by the deploy user (`chmod 600 .env`)
- [ ] Nightly DB backups are running (cron entry above) and you've tested
      a restore at least once
- [ ] The farmer/admin account uses a strong password, and no test
      accounts with default passwords remain
