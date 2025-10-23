# 🚀 Deployment Guide - Airplane MCP Server

## ✅ Verifica Setup Completato

Il server FastMCP è **funzionante e testato**:
- ✅ 9 tools registrati correttamente
- ✅ Docker build success
- ✅ MCP Inspector attivo
- ✅ API airplanes.live integrata

## 🧪 Test Locale

### Metodo 1: FastMCP Dev Server (Consigliato per testing)
```bash
# Attiva virtual environment
source .venv/bin/activate

# Avvia server con UI Inspector
fastmcp dev airplane_server_fastmcp.py
```

Questo apre automaticamente il browser su `http://localhost:6274` dove puoi:
- Vedere tutti i 9 tools disponibili
- Testare ogni tool con parametri reali
- Vedere le risposte in tempo reale

### Metodo 2: Docker Locale
```bash
# Build
docker build -t airplane-mcp .

# Run
docker run -i airplane-mcp

# Con Docker Compose
docker-compose up
```

## 🌐 Deploy su Cloud

### Option 1: Railway.app (Più Semplice)

1. **Setup Repository**
```bash
git add .
git commit -m "FastMCP server ready for deployment"
git push origin fast-mcp-server
```

2. **Deploy su Railway**
- Vai su [railway.app](https://railway.app)
- Click "New Project" → "Deploy from GitHub repo"
- Seleziona `Bellaposa/airplanes-live-mcp`
- Railway rileva automaticamente il Dockerfile
- Click "Deploy Now"

3. **Configurazione**
- Railway assegna automaticamente un URL
- Il server risponde su stdin/stdout (MCP protocol)

**Costo**: ~$5/mese per hobby projects

### Option 2: Fly.io (Più Controllo)

1. **Install Fly CLI**
```bash
brew install flyctl
flyctl auth login
```

2. **Initialize & Deploy**
```bash
flyctl launch
# Seleziona region: Amsterdam (ams)
# Accetta le configurazioni default

flyctl deploy
```

3. **Verifica Deployment**
```bash
flyctl status
flyctl logs
```

**Costo**: ~$3/mese (Machines pricing)

### Option 3: Render.com (Free Tier)

1. **Connetti GitHub**
- Vai su [render.com](https://render.com)
- "New" → "Web Service"
- Connetti repo `airplanes-live-mcp`

2. **Configurazione**
- Name: `airplane-mcp-server`
- Environment: `Docker`
- Instance Type: `Free`

3. **Deploy**
- Click "Create Web Service"
- Render builda automaticamente dal Dockerfile

**Costo**: Free (con limitazioni: spin down dopo 15min inattività)

### Option 4: Google Cloud Run (Scalabile)

1. **Setup GCP**
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. **Deploy**
```bash
gcloud run deploy airplane-mcp \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

**Costo**: Pay-per-use (~$0.01 per 1000 requests)

## 🔌 Integrazione con Client MCP

### Claude Desktop
```json
{
  "mcpServers": {
    "airplane-tracker": {
      "command": "docker",
      "args": ["run", "-i", "airplane-mcp"]
    }
  }
}
```

### Cline (VS Code)
```json
{
  "mcpServers": {
    "airplane-tracker": {
      "command": "fastmcp",
      "args": ["run", "airplane_server_fastmcp.py"]
    }
  }
}
```

## 📊 Monitoring & Logs

### Docker Logs
```bash
docker logs -f airplane-mcp-server
```

### Railway Logs
```bash
railway logs
```

### Fly.io Logs
```bash
flyctl logs
```

## 🎯 Next Steps per AI Flight Delay SaaS

1. **Deploy questo MCP server** (base infrastruttura)
2. **Crea API Gateway** con FastAPI wrapper
3. **Aggiungi ML Engine** per predizioni ritardi
4. **Setup Billing** con Stripe
5. **Launch Website** con pricing

## 🐛 Troubleshooting

### Docker non si connette
```bash
# Verifica Docker è running
docker ps

# Restart Docker Desktop
open -a Docker
```

### FastMCP inspection fails
```bash
# Reinstalla dipendenze
pip install --upgrade fastmcp httpx

# Verifica sintassi
python -m py_compile airplane_server_fastmcp.py
```

### Tools non visibili nel Inspector
```bash
# Verifica decoratori @mcp.tool()
grep -n "@mcp.tool" airplane_server_fastmcp.py

# Dovrebbero essere 9 occorrenze
```

## 📞 Support

Issues? Apri un ticket su GitHub o contatta il team!

---

**Status**: ✅ Production Ready
**Version**: FastMCP 2.12.5
**Last Updated**: 23 Ottobre 2025
