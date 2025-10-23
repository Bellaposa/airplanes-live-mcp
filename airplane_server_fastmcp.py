"""
Airplane Live Tracking MCP Server - FastMCP Compatible
Provides real-time aircraft tracking via airplanes.live API
"""

import logging
import httpx
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("airplane-tracker")

# API Configuration
API_BASE_URL = "https://api.airplanes.live/v2"

def format_aircraft_data(ac_list):
    """Format aircraft data for display."""
    if not ac_list:
        return "No aircraft found"
    
    formatted = []
    for ac in ac_list:
        info = []
        if ac.get('callsign'):
            info.append(f"✈️ Callsign: {ac['callsign'].strip()}")
        if ac.get('reg'):
            info.append(f"📋 Registration: {ac['reg']}")
        if ac.get('type'):
            info.append(f"🛩️ Type: {ac['type']}")
        if ac.get('lat') is not None and ac.get('lon') is not None:
            info.append(f"📍 Position: {ac['lat']:.4f}, {ac['lon']:.4f}")
        if ac.get('alt_baro'):
            info.append(f"📏 Altitude: {ac['alt_baro']} ft")
        if ac.get('gs'):
            info.append(f"⚡ Ground Speed: {ac['gs']} knots")
        if ac.get('track'):
            info.append(f"🧭 Track: {ac['track']}°")
        if ac.get('hex'):
            info.append(f"🔢 Mode S Hex: {ac['hex']}")
        if ac.get('seen_pos'):
            info.append(f"👁️ Last Seen: {ac['seen_pos']} seconds ago")
        
        if info:
            formatted.append("\n".join(info))
    
    if not formatted:
        return "No aircraft data available"
    
    separator = "\n" + "─" * 50 + "\n"
    return separator.join(formatted)

async def make_api_request(endpoint):
    """Make HTTP request to airplane API."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{API_BASE_URL}{endpoint}"
            logger.info(f"Requesting: {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"API Error {e.response.status_code}: {e}")
        raise
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise

# === TOOLS ===

@mcp.tool()
async def aircraft_by_hex(hex_id: str) -> str:
    """Search for aircraft by Mode S hex ID (comma-separated for multiple).
    
    Args:
        hex_id: Mode S hex ID (e.g., "347695" or "347695,34554D")
    """
    if not hex_id.strip():
        return "❌ Error: Hex ID is required"
    
    data = await make_api_request(f"/hex/{hex_id}")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🔍 Found {count} aircraft:\n\n{formatted}"

@mcp.tool()
async def aircraft_by_callsign(callsign: str) -> str:
    """Search for aircraft by callsign (comma-separated for multiple).
    
    Args:
        callsign: Aircraft callsign (e.g., "VLG32QU" or "AFR1234,BAW456")
    """
    if not callsign.strip():
        return "❌ Error: Callsign is required"
    
    data = await make_api_request(f"/callsign/{callsign}")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🔍 Found {count} aircraft:\n\n{formatted}"

@mcp.tool()
async def aircraft_by_registration(reg: str) -> str:
    """Search for aircraft by registration/tail number (comma-separated for multiple).
    
    Args:
        reg: Aircraft registration/tail number (e.g., "N123AB" or "G-ABCD,D-EFGH")
    """
    if not reg.strip():
        return "❌ Error: Registration is required"
    
    data = await make_api_request(f"/reg/{reg}")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🔍 Found {count} aircraft:\n\n{formatted}"

@mcp.tool()
async def aircraft_by_type(icao_type: str) -> str:
    """Search for aircraft by ICAO type code.
    
    Args:
        icao_type: ICAO type code (e.g., "A321", "B738", "C172")
    """
    if not icao_type.strip():
        return "❌ Error: ICAO type code is required"
    
    data = await make_api_request(f"/type/{icao_type}")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🔍 Found {count} aircraft of type {icao_type.upper()}:\n\n{formatted}"

@mcp.tool()
async def aircraft_by_squawk(squawk_code: str) -> str:
    """Search for aircraft by squawk code.
    
    Args:
        squawk_code: 4-digit squawk code (e.g., "7700", "7600", "7500")
    """
    if not squawk_code.strip():
        return "❌ Error: Squawk code is required"
    
    data = await make_api_request(f"/squawk/{squawk_code}")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🚨 Found {count} aircraft squawking {squawk_code}:\n\n{formatted}"

@mcp.tool()
async def aircraft_near_position(latitude: float, longitude: float, radius: float = 250) -> str:
    """Search for aircraft within radius of a position in nautical miles (max 250 nm).
    
    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        radius: Search radius in nautical miles (default: 250, max: 250)
    """
    try:
        if not -90 <= latitude <= 90:
            return "❌ Error: Latitude must be between -90 and 90"
        if not -180 <= longitude <= 180:
            return "❌ Error: Longitude must be between -180 and 180"
        if radius > 250:
            return "❌ Error: Radius cannot exceed 250 nm"
        if radius <= 0:
            return "❌ Error: Radius must be positive"
        
        data = await make_api_request(f"/point/{latitude}/{longitude}/{radius}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"📍 Found {count} aircraft within {radius} nm of {latitude:.4f}, {longitude:.4f}:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def military_aircraft() -> str:
    """Retrieve all aircraft tagged as military."""
    data = await make_api_request("/mil")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🎖️ Found {count} military aircraft:\n\n{formatted}"

@mcp.tool()
async def ladd_aircraft() -> str:
    """Retrieve all aircraft tagged as LADD (Law Enforcement/Security)."""
    data = await make_api_request("/ladd")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🚁 Found {count} LADD aircraft:\n\n{formatted}"

@mcp.tool()
async def pia_aircraft() -> str:
    """Retrieve all aircraft tagged as PIA (Likely Military/Private/Interesting)."""
    data = await make_api_request("/pia")
    formatted = format_aircraft_data(data.get('ac', []))
    count = len(data.get('ac', []))
    return f"🛡️ Found {count} PIA aircraft:\n\n{formatted}"
