# Farm Fresh: Free Cloud Deployment Guide

This guide details how to launch your **Farm Fresh** e-commerce store live on the web with a **free HTTPS URL / domain** and a **free PostgreSQL database** at zero cost.

---

## Recommended Method: Render.com + Neon.tech (Zero Cost, Automatic CI/CD)

Whenever you edit code on your machine and run `git push`, Render automatically builds, migrates the database, and updates your live website in ~2 minutes.

### Step 1: Create a Free PostgreSQL Database on Neon (Takes 1 Minute)
1. Go to **[neon.tech](https://neon.tech)** and click **Sign Up** (Free, no credit card required).
2. Create a project named `farmstore`.
3. Neon will display your **Connection Details / Connection String**. It looks like:
   ```text
   postgres://username:password@ep-cool-sample-12345.us-east-2.aws.neon.tech/farmstore?sslmode=require
   ```
4. Copy this entire URL. That is your `DATABASE_URL`.

---

### Step 2: Push Your Project to GitHub
1. In your project terminal, initialize git (if not already initialized):
   ```bash
   git init
   git add .
   git commit -m "Production ready Farm Fresh with free deployment config"
   ```
2. Create a new repository on your **[github.com](https://github.com)** account named `farmstore`.
3. Link and push:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/farmstore.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 3: Launch on Render.com (Takes 2 Minutes)
1. Go to **[render.com](https://render.com)** and sign in with your GitHub account.
2. Click **New +** ➔ **Web Service**.
3. Select your `farmstore` repository.
4. Fill in the deployment details:
   - **Name**: `farmstore` (or any custom name you prefer)
   - **Region**: Choose the closest region (e.g., Singapore or Frankfurt or Oregon)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn config.wsgi:application`
   - **Instance Type**: **Free** ($0 / month)
5. Scroll down to **Environment Variables** and click **Add Environment Variable**:
   - `SECRET_KEY`: Enter a random secret string (e.g. `django-insecure-farm-prod-key-xyz123`)
   - `DEBUG`: `False`
   - `DATABASE_URL`: Paste your Neon connection string from Step 1
   - `WHATSAPP_PROVIDER`: `console` (keep free simulation mode or add Meta Cloud credentials later)
   - `ALLOWED_HOSTS`: `*` (or your specific `.onrender.com` domain)
6. Click **Create Web Service**.

Render will automatically run `./build.sh`, install packages, collect static CSS/JS, migrate the database tables, and give you your live URL:
```
https://farmstore.onrender.com
```

---

### Step 4: Create Farm Superuser / Admin on Render
Once the deployment status shows **Live**:
1. In the Render dashboard, click the **Shell** tab on the left menu.
2. Type:
   ```bash
   python manage.py createsuperuser
   ```
3. Follow the prompts to create your admin phone number and password.
4. You can now log into your live website at `https://farmstore.onrender.com/farmer/`!

---

### How to Update Your Code in Future
Whenever you want to modify features, update designs, or add products:
1. Make changes in your code locally and test them.
2. Commit and push:
   ```bash
   git add .
   git commit -m "Added new features"
   git push
   ```
3. Render automatically detects the push, rebuilds, runs migrations, and updates your live site with zero downtime!

---

## Alternative Method: PythonAnywhere (100% Free, Built for Python)

If you prefer PythonAnywhere:
1. Sign up for a free Beginner account at **[pythonanywhere.com](https://www.pythonanywhere.com)**.
2. Your live domain is automatically: `https://<yourusername>.pythonanywhere.com`.
3. Open a **Bash Console** in PythonAnywhere:
   ```bash
   git clone https://github.com/YOUR_USERNAME/farmstore.git
   cd farmstore
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. In your `.env` file or environment:
   - Set `DB_ENGINE=sqlite3` (for instant zero-setup SQLite database on the server).
   - Run `python manage.py migrate`.
   - Run `python manage.py collectstatic`.
5. In the **Web** tab of PythonAnywhere:
   - Point the Source Directory to `/home/<yourusername>/farmstore`.
   - Point the Virtualenv to `/home/<yourusername>/farmstore/venv`.
   - In the WSGI configuration file, point to `config.wsgi.application`.
   - Click **Reload**. Your site is instantly live!
