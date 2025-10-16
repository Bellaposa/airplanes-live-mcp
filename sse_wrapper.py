import asyncio
import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
from typing import AsyncIterator

app = FastAPI(title="Airplanes Live MCP SSE Wrapper")

# Configurazione CORS per Supergateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MCPStdioWrapper:
    """Wrapper che converte comunicazioni stdio MCP in SSE"""
    
    def __init__(self):
        self.process = None
        self.request_id = 0
    
    async def start_mcp_server(self):
        """Avvia il processo del server MCP"""
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
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        # Invia la richiesta
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Leggi la risposta
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        return response
    
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
            tool_name = "search_aircraft_by_callsign"
            arguments = {"callsign": data["callsign"]}
        elif "flight_number" in data:
            tool_name = "search_aircraft_by_flight_number"
            arguments = {"flight_number": data["flight_number"]}
        elif "registration" in data:
            tool_name = "search_aircraft_by_registration"
            arguments = {"registration": data["registration"]}
        elif "airport_code" in data:
            tool_name = "search_aircraft_by_airport"
            arguments = {"airport_code": data["airport_code"]}
        else:
            return {"error": "Missing required parameter. Provide one of: callsign, flight_number, registration, airport_code"}
        
        # Chiama il tool MCP
        result = await mcp_wrapper.call_tool(tool_name, arguments)
        return result
        
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/callsign/{callsign}")
async def get_aircraft_by_callsign(callsign: str):
    """Ricerca aeromobile per callsign - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("search_aircraft_by_callsign", {"callsign": callsign})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/flight/{flight_number}")
async def get_aircraft_by_flight(flight_number: str):
    """Ricerca aeromobile per numero di volo - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("search_aircraft_by_flight_number", {"flight_number": flight_number})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/registration/{registration}")
async def get_aircraft_by_registration(registration: str):
    """Ricerca aeromobile per registrazione - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("search_aircraft_by_registration", {"registration": registration})
        return result
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/aircraft/airport/{airport_code}")
async def get_aircraft_by_airport(airport_code: str):
    """Ricerca aeromobili per aeroporto - endpoint GET per n8n"""
    try:
        result = await mcp_wrapper.call_tool("search_aircraft_by_airport", {"airport_code": airport_code})
        return result
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )