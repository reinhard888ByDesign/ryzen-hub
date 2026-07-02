#!/usr/bin/env python3
import asyncio
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urljoin
import re

SKILLS = Path("/home/reinhard/.claude/skills")


def is_mobile_device(user_agent: str) -> bool:
    """Erkennt mobile Geräte (iPhone, Android Phones) am User-Agent."""
    if not user_agent:
        return False
    return bool(re.search(r'iphone|android.*mobile|ipod', user_agent.lower()))


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
    iframe_path: str = "/"
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
        id="absender", name="Absender DB", url="http://localhost:8765",
        category="Dokumente & Abfragen", icon="📇",
        description="Absender-Konfiguration: Kategorie & Adressat-Zuordnung",
        iframe_path="/absender",
    ),
    Service(
        id="pipeline-debug", name="Pipeline Debugger", url="http://localhost:8765",
        category="Infrastruktur", icon="🔬",
        description="PDF-Upload: Pipeline simulieren, Override-Kaskade prüfen",
        iframe_path="/pipeline-debug",
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
        id="finanzanalyse", name="Finanzanalyse", url="http://localhost:8097",
        category="Dokumente & Abfragen", icon="💰",
        description="Finanzanalyse — Transaktionen aus CSV-Import",
        health_path="/api/summary.json",
        db_path="/home/reinhard/finanzen/finanzen.db",
        db_query="SELECT CAST(ROUND(SUM(CASE WHEN betrag_eur>0 THEN betrag_eur ELSE 0 END) - SUM(CASE WHEN betrag_eur<0 THEN ABS(betrag_eur) ELSE 0 END)) AS INTEGER) || ' €' FROM transaktionen WHERE umbuchung=0",
        db_label="Netto-Saldo",
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
        health_path="/api/health",
    ),
    Service(
        id="cache-reader", name="Cache Reader", url="http://localhost:8501",
        category="Infrastruktur", icon="🗄️",
        description="Docling Workflow Cache-Viewer",
        health_path="/health",
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
        iframe_path="/docs",
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
    Service(
        id="vault-integrity", name="Vault Integrity", url="http://localhost:8099",
        category="Infrastruktur", icon="🔍",
        description="Vault-Integritäts-Check — 6 Phasen: Duplikate, Links, Frontmatter, Kategorien, App-Routing, Inbox",
        health_path="/api/status",
        iframe_path="/vault",
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


def _parse_health_json(response) -> str:
    """Parse a health-check JSON body and return 'ok', 'degraded', or 'down'.
    Returns 'ok' for non-JSON or unrecognised bodies (fall back to HTTP status)."""
    try:
        body = response.json()
    except (ValueError, AttributeError):
        return "ok"  # Not JSON — trust HTTP status

    # Wilson-style: {"status": "degraded", "services_up": 0, "services_total": 6, ...}
    status = body.get("status", "")
    if status in ("degraded", "down", "error"):
        return status

    # services_up / services_total check (Wilson health endpoint)
    # Prüfe "down" zuerst (0 services), dann "degraded" (teilweise)
    if "services_up" in body and "services_total" in body:
        if body["services_up"] == 0 and body["services_total"] > 0:
            return "down"
        if body["services_up"] < body["services_total"]:
            return "degraded"

    return "ok"


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
                        # Parse JSON body for health status where available
                        # (e.g., Wilson health endpoint returns {"status":"degraded",...})
                        body_status = _parse_health_json(r)
                        if body_status in ("degraded", "error"):
                            svc.status = "degraded"
                            svc.last_error = f"Service reports {body_status}"
                        elif body_status == "down":
                            svc.status = "down"
                            svc.last_error = "Service reports down"
                        else:
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


def _inject_base_tag(html_bytes: bytes, service_id: str) -> bytes:
    """Injiziert <base> und fetch/XHR-Patcher in HTML-Antworten,
    damit absolute Pfade im iframe korrekt aufgeloest werden."""
    try:
        html = html_bytes.decode('utf-8', errors='replace')
        if '<base ' not in html[:2000]:
            base_tag = f'<base href="/p/{service_id}/">'
            html = html.replace('<head>', f'<head>{base_tag}', 1)

        # Inject fetch/XHR interceptor (nur einmal pro Seite, vor existierenden scripts)
        interceptor = f"""<script>
(function(){{
  if (window.__hubPatched) return;
  window.__hubPatched = true;
  var prefix = '/p/{service_id}';
  function rewrite(u) {{
    if (typeof u === 'string' && u.startsWith('/') && !u.startsWith('/p/') && !u.startsWith('/service/') && u !== '/api/status') {{
      return prefix + u;
    }}
    return u;
  }}
  // fetch & XHR
  var _fetch = window.fetch;
  window.fetch = function(url, opts) {{
    if (typeof url === 'string') url = rewrite(url);
    else if (url instanceof Request) {{
      var rw = rewrite(url.url);
      if (rw !== url.url) url = new Request(rw, url);
    }}
    return _fetch.call(this, url, opts);
  }};
  var _open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {{
    arguments[1] = rewrite(url) || url;
    return _open.apply(this, arguments);
  }};
  // <a href> clicks: prevent default, navigate via proxy
  document.addEventListener('click', function(e) {{
    var a = e.target.closest('a');
    if (!a) return;
    var h = a.getAttribute('href');
    if (!h || h.startsWith('http') || h.startsWith('#')) return;
    var rw = rewrite(h);
    if (rw !== h) {{
      e.preventDefault();
      e.stopPropagation();
      // target="_blank" → neuen Tab öffnen (sonst blockiert Chrome PDF/Download
      // aus sandboxed iframe heraus). window.location.href würde das iframe selbst
      // navigieren, was Chrome bei Mixed Content (HTTPS→HTTP) ablehnt.
      if (a.getAttribute('target') === '_blank') {{
        window.open(rw, '_blank');
      }} else {{
        window.location.href = rw;
      }}
    }}
  }}, true);
}})();
</script>"""
        html = html.replace('<head>', f'<head>{interceptor}', 1)
        return html.encode('utf-8')
    except Exception:
        return html_bytes


@app.api_route("/p/{service_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_to_service(request: Request, service_id: str, path: str):
    """Reverse-proxy zu einem Sub-Dashboard.
    Leitet /p/<service_id>/... an localhost:<port>/... weiter.
    """
    svc = by_id(service_id)
    if not svc:
        return JSONResponse({"error": f"Unknown service: {service_id}"}, status_code=404)

    target_base = svc.url.rstrip("/")
    target_url = f"{target_base}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Request body (for POST/PUT/PATCH)
    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    # Headers to forward (strip host, origin)
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "transfer-encoding", "content-length")}

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0), follow_redirects=True) as client:
        try:
            r = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Proxy error: {e}"}, status_code=502)

    # Response headers to forward (strip hop-by-hop)
    resp_headers = {k: v for k, v in r.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-length", "content-encoding")}

    content_type = r.headers.get("content-type", "")
    if "text/html" in content_type:
        # HTML-Antwort: base-Tag injizieren für korrekte relative Links im iframe
        body = await r.aread()
        body = _inject_base_tag(body, service_id)
        return HTMLResponse(content=body.decode('utf-8', errors='replace'),
                           status_code=r.status_code, headers=resp_headers)
    return StreamingResponse(
        r.aiter_bytes(),
        status_code=r.status_code,
        headers=resp_headers,
        media_type=content_type,
    )


@app.get("/p/{service_id}")
async def proxy_root(request: Request, service_id: str):
    """Proxy root path /p/<service_id>/ → localhost:<port>/"""
    svc = by_id(service_id)
    if not svc:
        return JSONResponse({"error": f"Unknown service: {service_id}"}, status_code=404)

    target_url = svc.url.rstrip("/") + "/"
    if request.url.query:
        target_url += f"?{request.url.query}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0), follow_redirects=True) as client:
        try:
            r = await client.get(target_url, headers={
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "transfer-encoding")
            })
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Proxy error: {e}"}, status_code=502)

    resp_headers = {k: v for k, v in r.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-length", "content-encoding")}

    content_type = r.headers.get("content-type", "")
    if "text/html" in content_type:
        body = await r.aread()
        body = _inject_base_tag(body, service_id)
        return HTMLResponse(content=body.decode('utf-8', errors='replace'),
                           status_code=r.status_code, headers=resp_headers)
    return StreamingResponse(
        r.aiter_bytes(),
        status_code=r.status_code,
        headers=resp_headers,
        media_type=content_type,
    )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_api(request: Request, path: str):
    """Fängt /api/... Aufrufe aus iframes ab und leitet sie an den
    richtigen Backend-Service weiter. Ermittelt den Ziel-Service aus
    dem Referer-Header. Fallback: Dispatcher (für dessen eigenes iframe).
    """
    # Hub-eigene Endpunkte nicht proxieren
    if path == "status":
        return await api_status()

    # Prüfe Referer: Aus welchem Service-iframe kommt der Request?
    referer = request.headers.get("referer", "")
    m = re.search(r'/p/([a-z0-9_-]+)/', referer)
    svc = by_id(m.group(1)) if m else None

    # Fallback: Dispatcher (für dessen /api/logs, /api/documents etc.)
    if not svc:
        svc = by_id("dispatcher")
    if not svc:
        return JSONResponse({"error": "No service configured"}, status_code=502)

    target_url = f"{svc.url.rstrip('/')}/api/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "transfer-encoding", "content-length")}

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0), follow_redirects=True) as client:
        try:
            r = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Proxy error: {e}"}, status_code=502)

    resp_headers = {k: v for k, v in r.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-length", "content-encoding")}

    return StreamingResponse(
        r.aiter_bytes(),
        status_code=r.status_code,
        headers=resp_headers,
        media_type=r.headers.get("content-type", "text/html"),
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    down = [s for s in REGISTRY if s.status == "down"]
    mobile = is_mobile_device(request.headers.get("user-agent", ""))
    return templates.TemplateResponse(request, "index.html", {
        "registry": REGISTRY,
        "groups": grouped(),
        "active": None,
        "down_services": down,
        "total": len(REGISTRY),
        "up_count": sum(1 for s in REGISTRY if s.status == "up"),
        "is_mobile": mobile,
    })


@app.get("/service/{service_id}", response_class=HTMLResponse)
async def service_detail(request: Request, service_id: str):
    svc = by_id(service_id)
    if not svc:
        return HTMLResponse("Service not found", status_code=404)
    mobile = is_mobile_device(request.headers.get("user-agent", ""))
    iframe_url = f"/p/{service_id}/{svc.iframe_path.lstrip('/')}"
    return templates.TemplateResponse(request, "service.html", {
        "svc": svc,
        "groups": grouped(),
        "active": service_id,
        "iframe_url": iframe_url,
        "is_mobile": mobile,
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


# ── Vault-Dateizugriff ─────────────────────────────────────────────────────────

VAULT_ROOT = Path("/home/reinhard/docker/RYZEN - docling-workflow/syncthing/data/reinhards-vault")


@app.get("/vault-file")
async def serve_vault_file(path: str = ""):
    """Liefert eine Datei aus dem Vault (PDF, MD, etc.) — fuer alle Dashboards."""
    from fastapi.responses import FileResponse
    if not path or ".." in path:
        return JSONResponse({"error": "Ungültiger Pfad"}, status_code=400)
    full = VAULT_ROOT / path
    if not full.exists() or not full.is_file():
        return JSONResponse({"error": f"Datei nicht gefunden: {path}"}, status_code=404)
    try:
        full.resolve().relative_to(VAULT_ROOT.resolve())
    except ValueError:
        return JSONResponse({"error": "Path traversal blockiert"}, status_code=400)
    media = "application/pdf" if full.suffix.lower() == ".pdf" else "text/markdown"
    return FileResponse(str(full), media_type=media, content_disposition_type="inline")


@app.get("/pdf/{filename:path}")
async def serve_pdf_from_anlagen(filename: str):
    """Liefert ein PDF aus dem Anlagen/ Ordner des Vaults."""
    from fastapi.responses import FileResponse
    basename = Path(filename).name
    full = VAULT_ROOT / "Anlagen" / basename
    if not full.exists() or not full.is_file():
        return JSONResponse({"error": f"PDF nicht gefunden: {basename}"}, status_code=404)
    return FileResponse(str(full), media_type="application/pdf", content_disposition_type="inline")


# ── Middleware: Requests aus iframes an den richtigen Service weiterleiten ─────
# Dashboards im iframe machen fetch('/api/...') und <a href="/..."> mit
# absolutem Pfad. Der <base> Tag greift nur bei relativen URLs. Diese Middleware
# fängt alle Requests ab, deren Referer auf /p/<service_id>/ zeigt, und proxyed
# sie an den korrekten Backend-Service.
# Ausnahme: /p/*, /service/*, /api/status (Hub-eigene Routes).

@app.middleware("http")
async def iframe_proxy_middleware(request: Request, call_next):
    """Proxy für iframe-Requests: Referer→Service-Mapping."""
    path = request.url.path

    # Hub-eigene Pfade nicht proxieren
    if path.startswith("/p/") or path.startswith("/service/") or path == "/api/status":
        return await call_next(request)

    referer = request.headers.get("referer", "")
    m = re.search(r'/p/([a-z0-9_-]+)/', referer)
    if not m:
        return await call_next(request)

    svc = by_id(m.group(1))
    if not svc:
        return await call_next(request)

    # /api/* wird bereits von proxy_api() behandelt — doppeltes Proxying vermeiden
    if path.startswith("/api/"):
        return await call_next(request)

    target_url = f"{svc.url.rstrip('/')}{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "transfer-encoding", "content-length", "referer")}

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0), follow_redirects=True) as client:
        try:
            r = await client.request(
                method=request.method, url=target_url, headers=headers, content=body)
        except httpx.RequestError as e:
            return JSONResponse(status_code=502, content={"error": f"Proxy error: {e}"})

    resp_headers = {k: v for k, v in r.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-length", "content-encoding")}
    content_type = r.headers.get("content-type", "")

    if "text/html" in content_type:
        body_bytes = await r.aread()
        body_bytes = _inject_base_tag(body_bytes, m.group(1))
        return HTMLResponse(content=body_bytes.decode('utf-8', errors='replace'),
                           status_code=r.status_code, headers=resp_headers)
    return StreamingResponse(
        r.aiter_bytes(), status_code=r.status_code, headers=resp_headers, media_type=content_type)
