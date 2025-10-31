import asyncio
import json
import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
from typing import AsyncIterator
from datetime import datetime

app = FastAPI(title="Airplanes Live MCP SSE Wrapper")

# Variabile globale per memorizzare l'ultimo run del cron
cron_last_run = None
cron_run_count = 0
cron_task = None

# Configurazione CORS per Supergateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === GEOCODING UTILITY ===

async def geocode_city(city_name: str) -> tuple[float, float]:
    async with httpx.AsyncClient(timeout=10) as client:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "OZiUserAgent/1.0"
        }
        
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                raise HTTPException(status_code=404, detail=f"City '{city_name}' not found")
            
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
            
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Geocoding error: {str(e)}")

# === MCP WRAPPER ===

class MCPStdioWrapper:    
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.initialized = False
    
    async def start_mcp_server(self):
        python_path = os.environ.get("PYTHON_PATH", "python")
        script_path = os.environ.get("MCP_SCRIPT_PATH", "airplane_server.py")
        
        self.process = await asyncio.create_subprocess_exec(
            python_path,
            script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        return self.process
    
    async def send_request(self, method: str, params: dict = None) -> dict:
        """Invia una richiesta JSON-RPC al server MCP"""
        if not self.process or self.process.returncode is not None:
            await self.start_mcp_server()
            self.initialized = False
            
        # Inizializza il server MCP se non ancora fatto
        if not self.initialized:
            await self.initialize()
            self.initialized = True
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        # Aggiungi params solo se non sono vuoti
        if params:
            request["params"] = params
        
        # Invia la richiesta
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Leggi la risposta
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        return response
    
    async def initialize(self) -> dict:
        """Inizializza il server MCP"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "sse-wrapper",
                    "version": "1.0.0"
                }
            }
        }
        
        # Invia la richiesta di inizializzazione
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Leggi la risposta
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        # Invia il messaggio initialized per completare l'handshake
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        initialized_json = json.dumps(initialized_msg) + "\n"
        self.process.stdin.write(initialized_json.encode())
        await self.process.stdin.drain()
        
        return response
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Chiama un tool MCP"""
        return await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
    
    async def list_tools(self) -> dict:
        """Lista tutti i tool disponibili"""
        return await self.send_request("tools/list")
    
    async def cleanup(self):
        """Chiude il processo MCP"""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()


# Istanza globale del wrapper
mcp_wrapper = MCPStdioWrapper()


@app.on_event("startup")
async def startup_event():
    """Avvia il server MCP all'avvio"""
    await mcp_wrapper.start_mcp_server()
    print("✅ MCP Server started")


@app.on_event("shutdown")
async def shutdown_event():
    """Chiude il server MCP allo shutdown"""
    await mcp_wrapper.cleanup()
    print("🛑 MCP Server stopped")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "airplanes-live-mcp-sse-wrapper",
        "mcp_running": mcp_wrapper.process is not None
    }


@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    Endpoint SSE per Supergateway
    Mantiene la connessione aperta e gestisce le richieste MCP
    """
    async def event_generator() -> AsyncIterator[str]:
        # Evento di connessione iniziale
        yield f"data: {json.dumps({'event': 'connected', 'server': 'airplanes-live-mcp'})}\n\n"
        
        try:
            # Lista dei tools disponibili
            tools_response = await mcp_wrapper.send_request("tools/list")
            yield f"event: tools\ndata: {json.dumps(tools_response)}\n\n"
            
            # Mantieni la connessione aperta
            while True:
                if await request.is_disconnected():
                    break
                
                # Heartbeat ogni 30 secondi
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': asyncio.get_event_loop().time()})}\n\n"
                
                await asyncio.sleep(30)
                
        except Exception as e:
            error_data = {"error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/mcp/tools/call")
async def call_tool(request: Request):
    """
    Endpoint per chiamare tools MCP
    Body: {"name": "tool_name", "arguments": {...}}
    """
    try:
        body = await request.json()
        tool_name = body.get("name")
        arguments = body.get("arguments", {})
        
        response = await mcp_wrapper.send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments}
        )
        
        return response
        
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/mcp/tools/list")
async def list_tools():
    """Elenca tutti i tools MCP disponibili"""
    try:
        response = await mcp_wrapper.send_request("tools/list")
        return response
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/")
async def root():
    return {
        "service": "Airplanes Live MCP SSE Wrapper",
        "version": "1.0.0",
        "endpoints": {
            "sse": "/sse",
            "health": "/health",
            "tools_list": "/mcp/tools/list",
            "call_tool": "/mcp/tools/call"
        },
        "repository": "https://github.com/Bellaposa/airplanes-live-mcp",
        "usage": "Connect Supergateway to /sse endpoint"
    }


# Endpoint semplificati per n8n
@app.post("/api/aircraft/search")
async def search_aircraft(request: Request):
    """Endpoint unificato per la ricerca di aeromobili - ottimizzato per n8n"""
    try:
        data = await request.json()
        
                # Determina il tipo di ricerca basato sui parametri forniti
        if "callsign" in data:
            tool_name = "aircraft_by_callsign"
            arguments = {"callsign": data["callsign"]}
        elif "flight_number" in data:
            tool_name = "aircraft_by_callsign"  # flight_number è lo stesso di callsign
            arguments = {"callsign": data["flight_number"]}
        elif "registration" in data:
            tool_name = "aircraft_by_registration"
            arguments = {"reg": data["registration"]}
        elif "airport_code" in data:
            # Non esiste un tool specifico per aeroporto, usiamo posizione
            return {"error": "Airport search not available. Use aircraft_near_position instead."}
        elif "hex_id" in data:
            tool_name = "aircraft_by_hex"
            arguments = {"hex_id": data["hex_id"]}
        elif "icao_type" in data:
            tool_name = "aircraft_by_type"
            arguments = {"icao_type": data["icao_type"]}
        elif "squawk_code" in data:
            tool_name = "aircraft_by_squawk"
            arguments = {"squawk_code": data["squawk_code"]}
        elif "latitude" in data and "longitude" in data:
            tool_name = "aircraft_near_position"
            arguments = {
                "latitude": str(data["latitude"]),
                "longitude": str(data["longitude"]),
                "radius": str(data.get("radius", "250"))
            }
        else:
            return {"error": "Missing required parameter. Provide one of: callsign, flight_number, registration, hex_id, icao_type, squawk_code, or latitude+longitude"}
        
        # Chiama il tool MCP
        result = await mcp_wrapper.call_tool(tool_name, arguments)
        return result
        
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/callsign/{callsign}")
async def get_aircraft_by_callsign(callsign: str):
    """Ricerca aeromobile per callsign - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_callsign", {"callsign": callsign})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/flight/{flight_number}")
async def get_aircraft_by_flight(flight_number: str):
    """Ricerca aeromobile per numero di volo - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_callsign", {"callsign": flight_number})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/registration/{registration}")
async def get_aircraft_by_registration(registration: str):
    """Ricerca aeromobile per registrazione - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_registration", {"reg": registration})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/hex/{hex_id}")
async def get_aircraft_by_hex(hex_id: str):
    """Ricerca aeromobile per hex ID - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_hex", {"hex_id": hex_id})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/type/{icao_type}")
async def get_aircraft_by_type(icao_type: str):
    """Ricerca aeromobili per tipo ICAO - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_type", {"icao_type": icao_type})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/squawk/{squawk_code}")
async def get_aircraft_by_squawk(squawk_code: str):
    """Ricerca aeromobili per codice squawk - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_by_squawk", {"squawk_code": squawk_code})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/military")
async def get_military_aircraft():
    """Ricerca aeromobili militari - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("military_aircraft", {})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/near/{latitude}/{longitude}")
async def get_aircraft_near_position(latitude: float, longitude: float, radius: int = 250):
    """Ricerca aeromobili vicini a una posizione - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_near_position", {
            "latitude": str(latitude),
            "longitude": str(longitude), 
            "radius": str(radius)
        })
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/near/{latitude}/{longitude}/{radius}")
async def get_aircraft_near_position_with_radius(latitude: float, longitude: float, radius: int):
    """Ricerca aeromobili vicini a una posizione con raggio nel path - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("aircraft_near_position", {
            "latitude": str(latitude),
            "longitude": str(longitude), 
            "radius": str(radius)
        })
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/near/city/{city_name}")
async def get_aircraft_near_city(city_name: str, radius: int = 50):
    """
    Ricerca aeromobili vicini a una città specificata per nome
    
    Esempi:
    - /api/aircraft/near/city/Rome
    - /api/aircraft/near/city/New York?radius=100
    - /api/aircraft/near/city/London?radius=75
    
    Il sistema converte automaticamente il nome della città in coordinate GPS
    """
    try:
        # Geocode city name to coordinates
        lat, lon = await geocode_city(city_name)
        
        # Call MCP tool with coordinates
        result = await mcp_wrapper.call_tool("aircraft_near_position", {
            "latitude": str(lat),
            "longitude": str(lon), 
            "radius": str(radius)
        })
        
        # Add geocoding info to response
        if "result" in result:
            result["geocoding"] = {
                "city": city_name,
                "latitude": lat,
                "longitude": lon
            }
        
        return result
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/airport/{airport_code}")
async def get_aircraft_by_airport(airport_code: str):
    """Ricerca aeromobili per aeroporto - endpoint GET per n8n (deprecato)"""
    return {"error": "Airport search not available. Use /api/aircraft/near/{lat}/{lon} instead."}


@app.get("/debug/mcp")
async def debug_mcp():
    """Debug endpoint per testare la comunicazione MCP"""
    try:
        # Test semplice - lista dei tool
        result = await mcp_wrapper.list_tools()
        return {"debug": "MCP communication", "result": result}
    except Exception as e:
        return {"error": f"Debug failed: {str(e)}"}


@app.get("/debug/tool/{tool_name}")
async def debug_tool_call(tool_name: str):
    """Debug endpoint per testare una chiamata specifica"""
    try:
        # Test con parametri semplici
        if tool_name == "aircraft_by_callsign":
            arguments = {"callsign": "UAL123"}
        elif tool_name == "military_aircraft":
            arguments = {}
        else:
            arguments = {}
            
        result = await mcp_wrapper.call_tool(tool_name, arguments)
        return {
            "debug": f"Tool call: {tool_name}",
            "arguments": arguments,
            "result": result
        }
    except Exception as e:
        return {"error": f"Debug tool call failed: {str(e)}"}


# === CRON INTERNO ===

async def cron_job_task():
    global cron_last_run, cron_run_count
    
    while True:
        try:
            # Attendi 14 minuti (840 secondi)
            await asyncio.sleep(840)
            
            # Esegui il lavoro
            current_time = datetime.now()
            cron_run_count += 1
            cron_last_run = current_time.isoformat()
            
            # Chiama l'endpoint health per mantenere il servizio attivo
            print(f"[CRON] Esecuzione #{cron_run_count} alle {cron_last_run}")
            health_response = await health_check()
            print(f"[CRON] Health check: {health_response.get('status', 'unknown')}")
            print(f"[CRON] Task completato con successo")
                
        except asyncio.CancelledError:
            print("[CRON] Task cancellato")
            break
        except Exception as e:
            print(f"[CRON] Errore critico: {e}")
            await asyncio.sleep(60)  # Riprova dopo 1 minuto in caso di errore


@app.on_event("startup")
async def startup_event():
    """Avvia il cron job all'avvio dell'applicazione"""
    global cron_task, cron_last_run
    
    cron_last_run = datetime.now().isoformat()
    print(f"[CRON] Avvio task periodico (ogni 14 minuti) - Start time: {cron_last_run}")
    
    # Crea il task in background
    cron_task = asyncio.create_task(cron_job_task())


@app.on_event("shutdown")
async def shutdown_event():
    """Ferma il cron job quando l'app viene chiusa"""
    global cron_task
    
    if cron_task:
        print("[CRON] Arresto task periodico")
        cron_task.cancel()
        try:
            await cron_task
        except asyncio.CancelledError:
            pass


@app.get("/api/cron/status")
async def get_cron_status():
    """Endpoint per controllare lo stato del cron job"""
    return JSONResponse({
        "active": cron_task is not None and not cron_task.done(),
        "last_run": cron_last_run,
        "run_count": cron_run_count,
        "interval_minutes": 14,
        "next_run_in_seconds": 840 if cron_last_run else None
    })


@app.post("/api/cron/trigger")
async def trigger_cron_manually():
    """Endpoint per triggare manualmente il cron job (per testing)"""
    global cron_last_run, cron_run_count
    
    try:
        current_time = datetime.now()
        cron_run_count += 1
        cron_last_run = current_time.isoformat()
        
        # Chiama l'endpoint health
        health_response = await health_check()
        
        return JSONResponse({
            "status": "success",
            "triggered_at": cron_last_run,
            "run_count": cron_run_count,
            "health_check": health_response
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cron trigger failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )