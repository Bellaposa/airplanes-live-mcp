#!/usr/bin/env python3
"""
Airplane Live Tracking MCP Server - Real-time aircraft tracking and information
"""

import asyncio
import os
import sys
import logging
import json
from datetime import datetime, timezone
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("airplane-server")

# Initialize MCP server
server = Server("airplane-tracker")

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
            info.append(f"� Mode S Hex: {ac['hex']}")
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

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="aircraft_by_hex",
            description="Search for aircraft by Mode S hex ID (comma-separated for multiple)",
            inputSchema={
                "type": "object",
                "properties": {
                    "hex_id": {
                        "type": "string",
                        "description": "Mode S hex ID"
                    }
                },
                "required": ["hex_id"]
            }
        ),
        Tool(
            name="aircraft_by_callsign",
            description="Search for aircraft by callsign (comma-separated for multiple)",
            inputSchema={
                "type": "object",
                "properties": {
                    "callsign": {
                        "type": "string",
                        "description": "Aircraft callsign"
                    }
                },
                "required": ["callsign"]
            }
        ),
        Tool(
            name="aircraft_by_registration",
            description="Search for aircraft by registration/tail number (comma-separated for multiple)",
            inputSchema={
                "type": "object",
                "properties": {
                    "reg": {
                        "type": "string",
                        "description": "Aircraft registration/tail number"
                    }
                },
                "required": ["reg"]
            }
        ),
        Tool(
            name="aircraft_by_type",
            description="Search for aircraft by ICAO type code (e.g., A321, B738, C172)",
            inputSchema={
                "type": "object",
                "properties": {
                    "icao_type": {
                        "type": "string",
                        "description": "ICAO type code"
                    }
                },
                "required": ["icao_type"]
            }
        ),
        Tool(
            name="aircraft_by_squawk",
            description="Search for aircraft by squawk code",
            inputSchema={
                "type": "object",
                "properties": {
                    "squawk_code": {
                        "type": "string",
                        "description": "Squawk code"
                    }
                },
                "required": ["squawk_code"]
            }
        ),
        Tool(
            name="aircraft_near_position",
            description="Search for aircraft within radius of a position in nautical miles (max 250 nm)",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "string",
                        "description": "Latitude coordinate"
                    },
                    "longitude": {
                        "type": "string",
                        "description": "Longitude coordinate"
                    },
                    "radius": {
                        "type": "string",
                        "description": "Search radius in nautical miles (default: 250)",
                        "default": "250"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        Tool(
            name="military_aircraft",
            description="Retrieve all aircraft tagged as military",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="ladd_aircraft",
            description="Retrieve all aircraft tagged as LADD (Law Enforcement/Security)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="pia_aircraft",
            description="Retrieve all aircraft tagged as PIA (Likely Military/Private/Interesting)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}
    
    try:
        if name == "aircraft_by_hex":
            hex_id = arguments.get("hex_id", "")
            if not hex_id.strip():
                return [TextContent(type="text", text="❌ Error: Hex ID is required")]
            
            data = await make_api_request(f"/hex/{hex_id}")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🔍 Found {count} aircraft:\n\n{formatted}"
            
        elif name == "aircraft_by_callsign":
            callsign = arguments.get("callsign", "")
            if not callsign.strip():
                return [TextContent(type="text", text="❌ Error: Callsign is required")]
            
            data = await make_api_request(f"/callsign/{callsign}")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🔍 Found {count} aircraft:\n\n{formatted}"
            
        elif name == "aircraft_by_registration":
            reg = arguments.get("reg", "")
            if not reg.strip():
                return [TextContent(type="text", text="❌ Error: Registration is required")]
            
            data = await make_api_request(f"/reg/{reg}")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🔍 Found {count} aircraft:\n\n{formatted}"
            
        elif name == "aircraft_by_type":
            icao_type = arguments.get("icao_type", "")
            if not icao_type.strip():
                return [TextContent(type="text", text="❌ Error: ICAO type code is required")]
            
            data = await make_api_request(f"/type/{icao_type}")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"� Found {count} aircraft of type {icao_type.upper()}:\n\n{formatted}"
            
        elif name == "aircraft_by_squawk":
            squawk_code = arguments.get("squawk_code", "")
            if not squawk_code.strip():
                return [TextContent(type="text", text="❌ Error: Squawk code is required")]
            
            data = await make_api_request(f"/squawk/{squawk_code}")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"� Found {count} aircraft squawking {squawk_code}:\n\n{formatted}"
            
        elif name == "aircraft_near_position":
            latitude = arguments.get("latitude", "")
            longitude = arguments.get("longitude", "")
            radius = arguments.get("radius", "250")
            
            if not latitude.strip() or not longitude.strip():
                return [TextContent(type="text", text="❌ Error: Latitude and longitude are required")]
            
            try:
                lat_val = float(latitude)
                lon_val = float(longitude)
                radius_val = float(radius) if radius.strip() else 250
                
                if not -90 <= lat_val <= 90:
                    return [TextContent(type="text", text="❌ Error: Latitude must be between -90 and 90")]
                if not -180 <= lon_val <= 180:
                    return [TextContent(type="text", text="❌ Error: Longitude must be between -180 and 180")]
                if radius_val > 250:
                    return [TextContent(type="text", text="❌ Error: Radius cannot exceed 250 nm")]
                if radius_val <= 0:
                    return [TextContent(type="text", text="❌ Error: Radius must be positive")]
                
                data = await make_api_request(f"/point/{lat_val}/{lon_val}/{radius_val}")
                formatted = format_aircraft_data(data.get('ac', []))
                count = len(data.get('ac', []))
                result = f"📍 Found {count} aircraft within {radius_val} nm of {lat_val:.4f}, {lon_val:.4f}:\n\n{formatted}"
            except ValueError as e:
                return [TextContent(type="text", text=f"❌ Error: Invalid coordinate format - {str(e)}")]
            
        elif name == "military_aircraft":
            data = await make_api_request("/mil")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🎖️ Found {count} military aircraft:\n\n{formatted}"
            
        elif name == "ladd_aircraft":
            data = await make_api_request("/ladd")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🚁 Found {count} LADD aircraft:\n\n{formatted}"
            
        elif name == "pia_aircraft":
            data = await make_api_request("/pia")
            formatted = format_aircraft_data(data.get('ac', []))
            count = len(data.get('ac', []))
            result = f"🛡️ Found {count} PIA aircraft:\n\n{formatted}"
            
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
            
        return [TextContent(type="text", text=result)]
        
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def main():
    """Run the MCP server."""
    logger.info("Starting Airplane Live Tracking MCP server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)