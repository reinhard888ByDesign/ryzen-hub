#!/usr/bin/env python3
import asyncio
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

SKILLS = Path("/home/reinhard/.claude/skills")


@dataclass
class Service:
    id: str
    name: str
    url: str
    category: str
    icon: str
    description: str = ""
    db_path: Optional[str] = None
    db_query: Optional[str] = None
    db_label: Optional[str] = None
    health_path: str = "/"
    # runtime state
    status: str = "unknown"
    response_ms: Optional[int] = None
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    stat_value: Optional[str] = None


REGISTRY: list[Service] = [
    Service(
        id="kv", name="Krankenversicherung", url="http://localhost:8090",
        category="Dokumente & Abfragen", icon="💊",
        description="Leistungsabrechnungen Gothaer & HUK-Coburg",
        db_path=str(SKILLS / "leistungsabrechnung/kk_leistungen.db"),
        db_query="SELECT COUNT(*) FROM leistungen",
        db_label="Abrechnungen",
    ),
    Service(
        id="kfz", name="KFZ", url="http://localhost:8094",
        category="Dokumente & Abfragen", icon="🚗",
        description="Fahrzeuge, Versicherungen & Schäden",
        db_path=str(SKILLS / "kfz/kfz.db"),
        db_query="SELECT COUNT(*) FROM fahrzeuge WHERE aktiv=1",
        db_label="Fahrzeuge",
    ),
    Service(
        id="immobilien", name="Immobilien", url="http://localhost:8091",
        category="Dokumente & Abfragen", icon="🏠",
        description="Eigene und vermietete Objekte",
        db_path=str(SKILLS / "immobilien/immobilien.db"),
        db_query="SELECT COUNT(*) FROM objekte WHERE aktiv_bis IS NULL",
        db_label="Aktive Objekte",
    ),
    Service(
        id="altersvorsorge", name="Altersvorsorge", url="http://localhost:8092",
        category="Dokumente & Abfragen", icon="📈",
        description="Standmitteilungen & Rentenverträge",
        db_path=str(SKILLS / "altersvorsorge/altersvorsorge.db"),
        db_query="SELECT COUNT(*) FROM vertraege WHERE aktiv=1",
        db_label="Aktive Verträge",
    ),
    Service(
        id="sachversicherungen", name="Sachversicherungen", url="http://localhost:8093",
        category="Dokumente & Abfragen", icon="🛡️",
        description="Hausrat, Haftpflicht, Wohngebäude, Rechtsschutz",
        db_path=str(SKILLS / "sachversicherungen/sachversicherungen.db"),
        db_query="SELECT COUNT(*) FROM vertraege WHERE aktiv=1",
        db_label="Aktive Verträge",
    ),
    Service(
        id="aufgaben", name="Aufgaben", url="http://localhost:8096",
        category="Haushalt", icon="📋",
        description="Aufgaben-Verwaltung — Anlegen, Bearbeiten, Erledigen",
        db_path="/home/reinhard/aufgaben/aufgaben.db",
        db_query="SELECT COUNT(*) FROM aufgaben WHERE status != 'erledigt'",
        db_label="Offen",
    ),
    Service(
        id="molly", name="Molly", url="http://localhost:8080",
        category="Haushalt", icon="🐾",
        description="Medikamenteneingabe & Protokollierung",
    ),
    Service(
        id="wilson-senders", name="Email-Absender", url="http://localhost:8771",
        category="Dokumente & Abfragen", icon="📧",
        description="Wilson Email-Absenderverwaltung & Kontaktdatenbank",
    ),
    Service(
        id="dispatcher", name="Dispatcher", url="http://localhost:8765",
        category="Infrastruktur", icon="📨",
        description="Dokument-Dispatcher & Klassifikations-Pipeline",
    ),
    Service(
        id="cache-reader", name="Cache Reader", url="http://localhost:8501",
        category="Infrastruktur", icon="🗄️",
        description="Docling Workflow Cache-Viewer",
    ),
    Service(
        id="syncthing", name="Syncthing", url="http://localhost:8384",
        category="Infrastruktur", icon="🔄",
        description="Datei-Synchronisation",
        health_path="/rest/noauth/health",
    ),
    Service(
        id="docling", name="Docling Serve", url="http://localhost:5001",
        category="Infrastruktur", icon="📄",
        description="PDF-Konvertierungs-API",
        health_path="/health",
    ),
    Service(
        id="open-webui", name="Open WebUI", url="http://localhost:3000",
        category="KI", icon="🤖",
        description="LLM-Chat-Interface (Ollama / Claude)",
    ),
    Service(
        id="ollama", name="Ollama", url="http://localhost:11434",
        category="KI", icon="🧠",
        description="Lokale LLM-Inference (ROCm / AMD)",
        health_path="/api/tags",
    ),
    Service(
        id="openclaw", name="openclaw · Wilson", url="http://192.168.3.124:8095",
        category="KI", icon="🦞",
        description="KI-Agent auf Wilson Pi 5 — Services, Memory, Heartbeat",
        health_path="/health",
    ),
]

CATEGORY_ORDER = ["Dokumente & Abfragen", "Haushalt", "Infrastruktur", "KI"]


def by_id(service_id: str) -> Optional[Service]:
    return next((s for s in REGISTRY if s.id == service_id), None)


def grouped() -> dict[str, list[Service]]:
    result: dict[str, list[Service]] = {}
    for cat in CATEGORY_ORDER:
        result[cat] = [s for s in REGISTRY if s.category == cat]
    return result


def load_db_stat(svc: Service) -> Optional[str]:
    if not svc.db_path or not svc.db_query:
        return None
    try:
        path = Path(svc.db_path)
        if not path.exists():
            return None
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        val = con.execute(svc.db_query).fetchone()[0]
        con.close()
        return f"{val}"
    except Exception:
        return None


app = FastAPI(title="Ryzen Hub")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def on_startup():
    for svc in REGISTRY:
        svc.stat_value = load_db_stat(svc)
    asyncio.create_task(health_loop())


async def health_loop():
    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
        while True:
            for svc in REGISTRY:
                url = svc.url.rstrip("/") + svc.health_path
                try:
                    t0 = asyncio.get_event_loop().time()
                    r = await client.get(url, follow_redirects=True)
                    ms = int((asyncio.get_event_loop().time() - t0) * 1000)
                    svc.response_ms = ms
                    svc.last_check = datetime.now()
                    if r.status_code < 500:
                        svc.status = "up"
                        svc.last_error = None
                    else:
                        svc.status = "degraded"
                        svc.last_error = f"HTTP {r.status_code}"
                except Exception as e:
                    svc.status = "down"
                    svc.last_error = str(e)[:100]
                    svc.last_check = datetime.now()
            for svc in REGISTRY:
                fresh = load_db_stat(svc)
                if fresh is not None:
                    svc.stat_value = fresh
            await asyncio.sleep(30)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    down = [s for s in REGISTRY if s.status == "down"]
    return templates.TemplateResponse(request, "index.html", {
        "registry": REGISTRY,
        "groups": grouped(),
        "active": None,
        "down_services": down,
        "total": len(REGISTRY),
        "up_count": sum(1 for s in REGISTRY if s.status == "up"),
    })


@app.get("/service/{service_id}", response_class=HTMLResponse)
async def service_detail(request: Request, service_id: str):
    svc = by_id(service_id)
    if not svc:
        return HTMLResponse("Service not found", status_code=404)
    host = request.headers.get("host", "localhost").split(":")[0]
    iframe_url = svc.url.replace("localhost", host).replace("127.0.0.1", host)
    return templates.TemplateResponse(request, "service.html", {
        "svc": svc,
        "groups": grouped(),
        "active": service_id,
        "iframe_url": iframe_url,
    })


@app.get("/api/status")
async def api_status():
    return {
        svc.id: {
            "status": svc.status,
            "response_ms": svc.response_ms,
            "last_check": svc.last_check.isoformat() if svc.last_check else None,
            "last_error": svc.last_error,
            "stat_value": svc.stat_value,
        }
        for svc in REGISTRY
    }
