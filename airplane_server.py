#!/usr/bin/env python3
"""
Airplane Live Tracking MCP Server - Real-time aircraft tracking and information
"""

import os
import sys
import logging
import json
from datetime import datetime, timezone
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("airplane-server")

# Initialize MCP server
mcp = FastMCP("airplane-tracker")

# Configuration
API_BASE_URL = "https://api.airplanes.live/v2"

# === UTILITY FUNCTIONS ===

def format_aircraft_data(aircraft_data):
    """Format aircraft data for display."""
    if isinstance(aircraft_data, dict):
        ac_list = [aircraft_data] if aircraft_data else []
    elif isinstance(aircraft_data, list):
        ac_list = aircraft_data
    else:
        return "No aircraft data"
    
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
            info.append(f"🔖 Mode S Hex: {ac['hex']}")
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

# === MCP TOOLS ===

@mcp.tool()
async def aircraft_by_hex(hex_id: str = "") -> str:
    """Search for aircraft by Mode S hex ID (comma-separated for multiple)."""
    if not hex_id.strip():
        return "❌ Error: Hex ID is required"
    
    try:
        data = await make_api_request(f"/hex/{hex_id}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🔍 Found {count} aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def aircraft_by_callsign(callsign: str = "") -> str:
    """Search for aircraft by callsign (comma-separated for multiple)."""
    if not callsign.strip():
        return "❌ Error: Callsign is required"
    
    try:
        data = await make_api_request(f"/callsign/{callsign}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🔍 Found {count} aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def aircraft_by_registration(reg: str = "") -> str:
    """Search for aircraft by registration/tail number (comma-separated for multiple)."""
    if not reg.strip():
        return "❌ Error: Registration is required"
    
    try:
        data = await make_api_request(f"/reg/{reg}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🔍 Found {count} aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def aircraft_by_type(icao_type: str = "") -> str:
    """Search for aircraft by ICAO type code (e.g., A321, B738, C172)."""
    if not icao_type.strip():
        return "❌ Error: ICAO type code is required"
    
    try:
        data = await make_api_request(f"/type/{icao_type}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🔍 Found {count} aircraft of type {icao_type.upper()}:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def aircraft_by_squawk(squawk_code: str = "") -> str:
    """Search for aircraft by squawk code."""
    if not squawk_code.strip():
        return "❌ Error: Squawk code is required"
    
    try:
        data = await make_api_request(f"/squawk/{squawk_code}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🔍 Found {count} aircraft squawking {squawk_code}:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def aircraft_near_position(latitude: str = "", longitude: str = "", radius: str = "250") -> str:
    """Search for aircraft within radius of a position in nautical miles (max 250 nm)."""
    if not latitude.strip() or not longitude.strip():
        return "❌ Error: Latitude and longitude are required"
    
    try:
        lat_val = float(latitude)
        lon_val = float(longitude)
        radius_val = float(radius) if radius.strip() else 250
        
        if not -90 <= lat_val <= 90:
            return f"❌ Error: Latitude must be between -90 and 90"
        if not -180 <= lon_val <= 180:
            return f"❌ Error: Longitude must be between -180 and 180"
        if radius_val > 250:
            return "❌ Error: Radius cannot exceed 250 nm"
        if radius_val <= 0:
            return "❌ Error: Radius must be positive"
        
        data = await make_api_request(f"/point/{lat_val}/{lon_val}/{radius_val}")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"📍 Found {count} aircraft within {radius_val} nm of {lat_val:.4f}, {lon_val:.4f}:\n\n{formatted}"
    except ValueError as e:
        return f"❌ Error: Invalid coordinate format - {str(e)}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def military_aircraft() -> str:
    """Retrieve all aircraft tagged as military."""
    try:
        data = await make_api_request("/mil")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🎖️ Found {count} military aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def ladd_aircraft() -> str:
    """Retrieve all aircraft tagged as LADD (Law Enforcement/Security)."""
    try:
        data = await make_api_request("/ladd")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🚁 Found {count} LADD aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def pia_aircraft() -> str:
    """Retrieve all aircraft tagged as PIA (Likely Military/Private/Interesting)."""
    try:
        data = await make_api_request("/pia")
        formatted = format_aircraft_data(data.get('ac', []))
        count = len(data.get('ac', []))
        return f"🛡️ Found {count} PIA aircraft:\n\n{formatted}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# === SERVER STARTUP ===

if __name__ == "__main__":
    logger.info("Starting Airplane Live Tracking MCP server...")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)