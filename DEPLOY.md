# Veriframe AI — Cloud VPS & Server Deployment Guide

This guide walks you through deploying **Veriframe AI** to any Linux Cloud VPS (AWS EC2, DigitalOcean Droplet, Hetzner, Linode, Google Compute Engine, etc.) using Docker Compose.

---

## Architecture Overview

```
               Internet (Clients / Browsers)
                            │
               Ports 80 / 443 (HTTP / HTTPS)
                            ▼
              ┌───────────────────────────┐
              │      Caddy Web Server     │  <── Automatic Let's Encrypt SSL
              │  (Reverse Proxy / Gateway)│
              └─────────────┬─────────────┘
                            │
             ┌──────────────┴──────────────┐
             │                             │
    handle /* (Pages/UI)          handle /api/* (REST/SSE)
             ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │  Next.js App    │           │  FastAPI Backend│
    │ (frontend:3000) │           │   (api:8000)    │
    └─────────────────┘           └────────┬────────┘
                                           │
                                  ┌────────┴────────┐
                                  │ Persistent Data │
                                  │ (analysis-data) │
                                  └─────────────────┘
```

- **Frontend**: Next.js 16 (React 19, TypeScript)
- **Backend**: FastAPI with Python 3.12, PyTorch, FFmpeg for video forensics
- **Reverse Proxy**: Caddy 2 (Automatic TLS certificates for your domain, no manual certbot required)
- **Data Persistence**: Docker named volume for SQLite reports & results

---

## Recommended Server Sizing
- **OS**: Ubuntu 22.04 LTS or Ubuntu 24.04 LTS (recommended)
- **CPU**: 2+ vCPUs
- **RAM**: 
  - **2 GB minimum** (add 2-4 GB swap file)
  - **4 GB+ recommended** (for smooth image & video AI model inference)
- **Disk**: 20 GB+ SSD

---

## Phase 1: Push Your Local Code to GitHub

From your local machine (PowerShell / terminal in this project root):

1. **Check git status and commit your changes**:
   ```powershell
   git add .
   git commit -m "feat: add production docker compose and caddy setup"
   ```

2. **Link your GitHub repository** (replace `<YOUR_GITHUB_REPO_URL>` with your repo URL):
   ```powershell
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   ```
   *(If `origin` already exists, update it with `git remote set-url origin <URL>`)*

3. **Push your branch to GitHub**:
   ```powershell
   git push -u origin hackathon-upgrade
   ```
   *(Or merge into `main` and run `git push -u origin main`)*

---

## Phase 2: VPS Server Setup

### 1. Connect to your VPS via SSH
```bash
ssh root@<YOUR_VPS_IP>
```

### 2. Configure a Swap File (Recommended if VPS has 2-4GB RAM)
PyTorch and model packages require memory during Docker builds. A 2GB-4GB swap prevents out-of-memory errors:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. Open Firewall Ports
Allow SSH, HTTP, and HTTPS:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Phase 3: Clone & Deploy Veriframe AI

### 1. Clone the repository on your server
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git veriframe
cd veriframe
git checkout hackathon-upgrade # or main
```

### 2. Create and configure `.env`
```bash
cp .env.example .env
nano .env
```

Configure the following key settings:
- **`SERVER_NAME`**:
  - If you have a custom domain pointed to this server: `SERVER_NAME=veriframe.yourdomain.com` (Caddy will **automatically provision free HTTPS SSL**!).
  - If you are testing with the server's raw IP address: `SERVER_NAME=:80`
- **`NVIDIA_API_KEY` / `OPENAI_API_KEY`**: Paste your API keys for reasoning & models.
- **`NEXT_PUBLIC_API_URL`**: Leave blank if using Caddy (Caddy proxies `/api/*` directly on the same domain without CORS issues).

Save and exit `nano` (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 3. Launch Deployment

You can use the automated deployment script:
```bash
chmod +x deploy.sh
./deploy.sh
```

**Or run Docker Compose directly**:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Phase 4: DNS Configuration (For Custom Domain & SSL)

If using a custom domain (e.g., `veriframe.yourdomain.com`):
1. Go to your DNS provider (Namecheap, GoDaddy, Cloudflare, AWS Route 53, etc.).
2. Add an **A Record**:
   - **Type**: `A`
   - **Name / Host**: `@` (or `veriframe` for subdomain)
   - **Value / IPv4**: `<YOUR_VPS_IP>`
   - **TTL**: Auto / 5 minutes
3. Make sure `SERVER_NAME=yourdomain.com` in your VPS `.env`.
4. Run `docker compose -f docker-compose.prod.yml restart caddy`.
5. Open `https://yourdomain.com` in your browser. Caddy will automatically negotiate HTTPS with Let's Encrypt!

---

## Management & Operations

### View live logs
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service (backend or frontend or caddy)
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f caddy
```

### Check service health status
```bash
docker compose -f docker-compose.prod.yml ps
curl -i http://localhost/health
```

### Update to the latest code
When you push new changes to GitHub, update the live server with:
```bash
cd veriframe
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Restart or Stop
```bash
# Restart
docker compose -f docker-compose.prod.yml restart

# Stop
docker compose -f docker-compose.prod.yml down
```

---

## Alternative: Direct Port Mode (Without Caddy)
If you prefer exposing raw ports directly (Frontend on `:3000` and API on `:8000`):
1. In `.env`, set:
   ```env
   NEXT_PUBLIC_API_URL=http://<YOUR_VPS_IP>:8000
   ```
2. Open ports on VPS firewall:
   ```bash
   sudo ufw allow 3000/tcp
   sudo ufw allow 8000/tcp
   ```
3. Run standard docker compose:
   ```bash
   docker compose up -d --build
   ```
4. Access the web app at `http://<YOUR_VPS_IP>:3000`.
