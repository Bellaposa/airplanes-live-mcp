from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import logging

import airplane_server

logger = logging.getLogger("http-wrapper")
app = FastAPI(title="Airplanes Live MCP HTTP Wrapper")


class HexQuery(BaseModel):
    hex_id: str


class CallsignQuery(BaseModel):
    callsign: str


class RegQuery(BaseModel):
    reg: str


class TypeQuery(BaseModel):
    icao_type: str


class SquawkQuery(BaseModel):
    squawk_code: str


class PointQuery(BaseModel):
    latitude: float
    longitude: float
    radius: float = 250.0


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/aircraft/hex")
async def aircraft_by_hex(q: HexQuery):
    try:
        data = await airplane_server.make_api_request(f"/hex/{q.hex_id}")
        return data
    except Exception as e:
        logger.error("aircraft_by_hex error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/aircraft/callsign")
async def aircraft_by_callsign(q: CallsignQuery):
    try:
        data = await airplane_server.make_api_request(f"/callsign/{q.callsign}")
        return data
    except Exception as e:
        logger.error("aircraft_by_callsign error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/aircraft/reg")
async def aircraft_by_reg(q: RegQuery):
    try:
        data = await airplane_server.make_api_request(f"/reg/{q.reg}")
        return data
    except Exception as e:
        logger.error("aircraft_by_reg error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/aircraft/type")
async def aircraft_by_type(q: TypeQuery):
    try:
        data = await airplane_server.make_api_request(f"/type/{q.icao_type}")
        return data
    except Exception as e:
        logger.error("aircraft_by_type error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/aircraft/squawk")
async def aircraft_by_squawk(q: SquawkQuery):
    try:
        data = await airplane_server.make_api_request(f"/squawk/{q.squawk_code}")
        return data
    except Exception as e:
        logger.error("aircraft_by_squawk error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/aircraft/point")
async def aircraft_by_point(q: PointQuery):
    try:
        data = await airplane_server.make_api_request(f"/point/{q.latitude}/{q.longitude}/{q.radius}")
        return data
    except Exception as e:
        logger.error("aircraft_by_point error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
