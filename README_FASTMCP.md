# Airplane Live Tracking MCP Server

Real-time aircraft tracking via [airplanes.live](https://airplanes.live) API using the Model Context Protocol (MCP).

## 🚀 Features

- **Multiple Search Methods**: Search by hex, callsign, registration, type, squawk, or position
- **Real-time Data**: Live aircraft positions, altitudes, speeds, and more
- **Special Categories**: Military, LADD (Law Enforcement), and PIA aircraft
- **FastMCP Compatible**: Modern MCP framework for easy deployment
- **Docker Ready**: Containerized for cloud deployment

## 📦 Installation

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
fastmcp dev airplane_server_fastmcp.py
```

### Docker Deployment

```bash
# Build the image
docker build -t airplane-mcp .

# Run the container
docker run -i airplane-mcp
```

## 🔧 Available Tools

### `aircraft_by_hex`
Search by Mode S hex ID (e.g., "347695")
```json
{
  "hex_id": "347695"
}
```

### `aircraft_by_callsign`
Search by callsign (e.g., "VLG32QU", "AFR1234")
```json
{
  "callsign": "VLG32QU"
}
```

### `aircraft_by_registration`
Search by tail number (e.g., "N123AB")
```json
{
  "reg": "N123AB"
}
```

### `aircraft_by_type`
Search by ICAO type code (e.g., "A321", "B738")
```json
{
  "icao_type": "A321"
}
```

### `aircraft_by_squawk`
Search by squawk code (e.g., "7700" for emergency)
```json
{
  "squawk_code": "7700"
}
```

### `aircraft_near_position`
Find aircraft within radius (nm) of coordinates
```json
{
  "latitude": 41.9028,
  "longitude": 12.4964,
  "radius": 100
}
```

### `military_aircraft`
Get all military aircraft

### `ladd_aircraft`
Get all law enforcement aircraft

### `pia_aircraft`
Get all "interesting" aircraft (military/private/VIP)

## 🌐 Cloud Deployment

### Railway
```bash
railway login
railway init
railway up
```

### Render
1. Connect your GitHub repo
2. Create new Web Service
3. Use Docker environment
4. Deploy!

### Fly.io
```bash
flyctl launch
flyctl deploy
```

## 📊 Data Source

Powered by [airplanes.live](https://airplanes.live) - a free, community-driven ADS-B aircraft tracking network.

## 🤝 Contributing

Contributions welcome! This server is part of the **AI Flight Delay SaaS** project.

## 📄 License

MIT License - feel free to use for your projects!

## 🔗 Related Projects

- **Telegram Aircraft Bot**: Instant aircraft lookups via Telegram
- **AI Flight Delay Predictor**: ML-powered delay predictions (coming soon!)

---

Made with ✈️ by the Airplane Live MCP community
