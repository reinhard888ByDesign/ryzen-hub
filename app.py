#!/usr/bin/env python3
import asyncio
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, StreamingResponse)
from fastapi.templating import Jinja2Templates
from urllib.parse import urljoin
import re

# hub_auth liegt in dms-ap (AP08). Der Import stand frueher am Dateiende,
# weil installiere() die letzte Middleware registrieren muss — der Import
# selbst kann aber hier oben stehen. Nur hub_auth.installiere(app) bleibt
# am Ende (AP202).
import sys
sys.path.insert(0, "/home/reinhard/dms-ap")
import hub_auth

SKILLS = Path("/home/reinhard/.claude/skills")
RYZEN_IP = "192.168.86.195"


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
        id="kv", name="Krankenversicherung", url="http://127.0.0.1:8090",
        category="Dokumente & Abfragen", icon="💊",
        description="Leistungsabrechnungen Gothaer & HUK-Coburg",
        db_path=str(SKILLS / "leistungsabrechnung/kk_leistungen.db"),
        db_query="SELECT COUNT(*) FROM leistungen",
        db_label="Abrechnungen",
    ),
    Service(
        id="kfz", name="KFZ", url="http://127.0.0.1:8094",
        category="Dokumente & Abfragen", icon="🚗",
        description="Fahrzeuge, Versicherungen & Schäden",
        db_path=str(SKILLS / "kfz/kfz.db"),
        db_query="SELECT COUNT(*) FROM fahrzeuge WHERE aktiv=1",
        db_label="Fahrzeuge",
    ),
    Service(
        id="immobilien", name="Immobilien", url="http://127.0.0.1:8091",
        category="Dokumente & Abfragen", icon="🏠",
        description="Eigene und vermietete Objekte",
        db_path=str(SKILLS / "immobilien/immobilien.db"),
        # AP172: objekte.archiv ist seit AP158 das Kriterium. `aktiv_bis` blieb
        # bei den nachgetragenen Objekten leer und zaehlte die verkauften
        # Schevemoorer und Brinkum mit.
        db_query=(
            "SELECT COUNT(*) || ' aktiv · ' || "
            "COALESCE((SELECT printf('%+.0f €/M', SUM(cashflow_mtl)) "
            "          FROM v_immo_rendite "
            "          WHERE archiviert=0 AND nutzung='vermietet'), '—') "
            "FROM objekte WHERE archiv = 0"
        ),
        db_label="Objekte",
    ),
    Service(
        id="absender", name="Absender DB", url="http://127.0.0.1:8765",
        category="Dokumente & Abfragen", icon="📇",
        description="Absender-Konfiguration: Kategorie & Adressat-Zuordnung",
        iframe_path="/absender",
    ),
    Service(
        id="pipeline", name="Pipeline Live", url="http://127.0.0.1:8765/pipeline",
        category="Infrastruktur", icon="⚡",
        description="Live-Ansicht: Dokument-Verarbeitung in Echtzeit",
        iframe_path="",
    ),
    Service(
        id="pipeline-history", name="Pipeline History", url="http://127.0.0.1:8765/pipeline/history",
        category="Infrastruktur", icon="📋",
        description="Letzte 50 Verarbeitungen: Zeit, Kategorie, Status",
        iframe_path="",
    ),
    Service(
        id="batch", name="Batch Verarbeitung", url="http://127.0.0.1:8765/batch",
        category="Infrastruktur", icon="🧰",
        description="Batch-Rescan: PDFs neu OCR-scannen & klassifizieren",
        iframe_path="",
    ),
    Service(
        id="pipeline-debug", name="Pipeline Debugger", url="http://127.0.0.1:8765",
        category="Infrastruktur", icon="🔬",
        description="PDF-Upload: Pipeline simulieren, Override-Kaskade prüfen",
        iframe_path="/pipeline-debug",
    ),
    Service(
        id="altersvorsorge", name="Altersvorsorge", url="http://127.0.0.1:8092",
        category="Dokumente & Abfragen", icon="📈",
        description="Standmitteilungen & Rentenverträge",
        db_path=str(SKILLS / "altersvorsorge/altersvorsorge.db"),
        db_query="SELECT COUNT(*) FROM vertraege WHERE aktiv=1",
        db_label="Aktive Verträge",
    ),
    Service(
        id="sachversicherungen", name="Sachversicherungen", url="http://127.0.0.1:8093",
        category="Dokumente & Abfragen", icon="🛡️",
        description="Hausrat, Haftpflicht, Wohngebäude, Rechtsschutz",
        db_path=str(SKILLS / "sachversicherungen/sachversicherungen.db"),
        db_query="SELECT COUNT(*) FROM vertraege WHERE aktiv=1",
        db_label="Aktive Verträge",
    ),
    Service(
        id="finanzanalyse", name="Finanzanalyse", url="http://127.0.0.1:8097",
        category="Dokumente & Abfragen", icon="💰",
        description="Finanzanalyse — Transaktionen aus CSV-Import",
        health_path="/api/summary.json",
        db_path="/home/reinhard/finanzen/finanzen.db",
        db_query="SELECT CAST(ROUND(SUM(CASE WHEN betrag_eur>0 THEN betrag_eur ELSE 0 END) - SUM(CASE WHEN betrag_eur<0 THEN ABS(betrag_eur) ELSE 0 END)) AS INTEGER) || ' €' FROM transaktionen WHERE umbuchung=0",
        db_label="Netto-Saldo",
    ),
    Service(
        id="goldbestand", name="Goldbestand", url="http://127.0.0.1:8098",
        category="Dokumente & Abfragen", icon="🪙",
        description="Goldbarren & historische Muenzen — Depotwert zum Tageskurs",
        health_path="/api/summary.json",
        db_path=str(SKILLS / "goldbestand/goldbestand.db"),
        db_query=(
            "SELECT CAST(ROUND(("
            "(SELECT COALESCE(SUM(anzahl * gewicht_stueck_g),0) FROM barren WHERE aktiv=1)"
            " + "
            "(SELECT COALESCE(SUM(feingoldgehalt_standard_g),0) FROM muenzen WHERE aktiv=1)"
            ") * (SELECT preis_eur_je_gramm FROM goldpreis_cache ORDER BY id DESC LIMIT 1)"
            ") AS INTEGER) || ' €'"
        ),
        db_label="Materialwert",
    ),
    Service(
        id="medizinisches-bulletin", name="Medizinisches Bulletin", url="http://127.0.0.1:8100",
        category="Dokumente & Abfragen", icon="🩺",
        description="Laborwerte & Arztbriefe — Zeitreihen, Chronik, Einschätzung je Person",
        health_path="/api/status.json",
    ),
    Service(
        id="investor", name="Investor Reporting", url="http://127.0.0.1:8095",
        category="Dokumente & Abfragen", icon="📊",
        description="Investor-Reports: Wonderz, Xempus, Mate — KPIs & Exit-Strategien",
        db_path=str(SKILLS / "investor-reporting/investor.db"),
        db_query="SELECT COUNT(*) FROM reports WHERE processing_status='extracted'",
        db_label="Reports",
    ),
    Service(
        id="aufgaben", name="Aufgaben", url="http://127.0.0.1:8096",
        category="Haushalt", icon="📋",
        description="Aufgaben-Verwaltung — Anlegen, Bearbeiten, Erledigen",
        db_path="/home/reinhard/aufgaben/aufgaben.db",
        db_query="SELECT COUNT(*) FROM aufgaben WHERE status != 'erledigt'",
        db_label="Offen",
    ),
    Service(
        id="molly", name="Molly", url="http://127.0.0.1:8081",
        category="Haushalt", icon="🐾",
        description="Medikationsplan — Arthrose & Ohrentzündung, Librela-Tracking",
    ),
    Service(
        id="wilson-senders", name="Email-Absender", url="http://127.0.0.1:8771",
        category="Dokumente & Abfragen", icon="📧",
        description="Wilson Email-Absenderverwaltung & Kontaktdatenbank",
    ),
    Service(
        id="dispatcher", name="Dispatcher", url="http://127.0.0.1:8765",
        category="Infrastruktur", icon="📨",
        description="Dokument-Dispatcher & Klassifikations-Pipeline",
        health_path="/api/health",
    ),
    Service(
        id="cache-reader", name="Cache Reader", url="http://127.0.0.1:8501",
        category="Infrastruktur", icon="🗄️",
        description="Docling Workflow Cache-Viewer",
        health_path="/health",
    ),
    Service(
        id="syncthing", name="Syncthing", url="http://127.0.0.1:8384",
        category="Infrastruktur", icon="🔄",
        description="Datei-Synchronisation",
        health_path="/rest/noauth/health",
    ),
    Service(
        id="docling", name="Docling Serve", url="http://127.0.0.1:5001",
        category="Infrastruktur", icon="📄",
        description="PDF-Konvertierungs-API",
        health_path="/health",
        iframe_path="/docs",
    ),
    Service(
        id="open-webui", name="Open WebUI", url="http://127.0.0.1:3000",
        category="KI", icon="🤖",
        description="LLM-Chat-Interface (Ollama / Claude)",
        iframe_path="",
    ),
    Service(
        id="ollama", name="Ollama", url="http://127.0.0.1:11434",
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
        id="vault-integrity", name="Vault Integrity", url="http://127.0.0.1:8099",
        category="Infrastruktur", icon="🔍",
        description="Vault-Integritäts-Check — 6 Phasen: Duplikate, Links, Frontmatter, Kategorien, App-Routing, Inbox",
        health_path="/api/status",
        iframe_path="/vault",
    ),
]

CATEGORY_ORDER = ["Dokumente & Abfragen", "Haushalt", "Infrastruktur", "KI"]


def by_id(service_id: str) -> Optional[Service]:
    return next((s for s in REGISTRY if s.id == service_id), None)


def _sichtbar() -> list:
    """REGISTRY, beschraenkt auf die Freigaben des angemeldeten Kontos.

    AP08d. Faellt hub_auth aus, wird nichts gefiltert — der Hub bleibt
    bedienbar. Das ist vertretbar, weil der Zugriffsschutz selbst in
    der Middleware sitzt und nicht hier: diese Funktion bestimmt nur,
    was angezeigt wird.
    """
    try:
        import hub_auth
        erlaubt = hub_auth.erlaubte(hub_auth.AKTUELLER_NUTZER.get())
    except Exception:
        return list(REGISTRY)
    if erlaubt == "*":
        return list(REGISTRY)
    return [s for s in REGISTRY if s.id in erlaubt]


def grouped() -> dict[str, list[Service]]:
    sichtbar = _sichtbar()
    result: dict[str, list[Service]] = {}
    for cat in CATEGORY_ORDER:
        treffer = [s for s in sichtbar if s.category == cat]
        # Leere Rubriken weglassen, sonst stehen bei einem Konto mit
        # einer einzigen Freigabe zehn leere Ueberschriften auf der Seite.
        if treffer:
            result[cat] = treffer
    return result


def _basis_kontext(request: Request, active):
    """Gemeinsamer Template-Kontext aller Hub-Seiten (AP202).

    groups + active braucht jede Seite, die base.html erbt (Sidebar).
    nutzer/ist_admin sind in Jinja falsy, wenn sie fehlen — Seiten
    bleiben also auch ohne diese Variablen bedienbar.
    """
    nutzer = getattr(request.state, "nutzer", None)
    return {"groups": grouped(), "active": active,
            "nutzer": nutzer or "", "ist_admin": hub_auth.ist_admin(nutzer)}


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


def _entschaerfe_header(resp_headers: dict, svc) -> dict:
    """Interne Adressen aus Antwortkoepfen entfernen (AP08b).

    Betrifft vor allem Location. httpx folgt Weiterleitungen selbst,
    aber ist die letzte Antwort eine, ginge http://127.0.0.1:<port>
    unveraendert an den Browser.

    Nimmt den Dienst, nicht seine Kennung: proxy_api und
    iframe_proxy_middleware ermitteln ihn ueber den Referer und haben
    kein service_id im Gueltigkeitsbereich. Ein erster Entwurf setzte
    dort service_id ein — ast.parse fand das nicht, weil undefinierte
    Namen erst zur Laufzeit auffallen. Zwei der vier Proxy-Stellen
    waeren mit NameError abgestuerzt.
    """
    if not svc:
        return resp_headers
    service_id = svc.id
    basis = svc.url.rstrip("/")
    port = basis.rsplit(":", 1)[-1]
    for kopf in ("location", "content-location"):
        for k in list(resp_headers):
            if k.lower() == kopf:
                resp_headers[k] = (resp_headers[k]
                                   .replace(basis, f"/p/{service_id}")
                                   .replace(f"http://{RYZEN_IP}:{port}",
                                            f"/p/{service_id}"))
    return resp_headers


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

        # AP08b: absolute Backend-Adressen auf den Proxy-Pfad umbiegen.
        # Molly & Co. bauen Links aus request.base_url. Der Hub entfernt
        # den Host-Kopf, httpx setzt daraufhin 127.0.0.1:<port> - und
        # genau das landet im HTML. Der Skript-Einschub oben fasst
        # absolute URLs nicht an, er kann es also nicht auffangen.
        svc = by_id(service_id)
        if svc:
            basis = svc.url.rstrip('/')
            html = html.replace(basis, f'/p/{service_id}')
            # Der Altbestand kann noch die LAN-Adresse enthalten. Die war
            # vom Browser aus erreichbar - der Klick landete am Hub vorbei
            # direkt auf dem Dashboard und umginge seit AP08 die Anmeldung.
            port = basis.rsplit(':', 1)[-1]
            html = html.replace(f'http://{RYZEN_IP}:{port}', f'/p/{service_id}')
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
    resp_headers = _entschaerfe_header(resp_headers, svc)

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
    resp_headers = _entschaerfe_header(resp_headers, svc)

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
    resp_headers = _entschaerfe_header(resp_headers, svc)

    return StreamingResponse(
        r.aiter_bytes(),
        status_code=r.status_code,
        headers=resp_headers,
        media_type=r.headers.get("content-type", "text/html"),
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # AP202: Health-Bar und Down-Banner bekommen die GEFILTERTE Liste.
    # Vorher stand hier REGISTRY — ein Konto mit einer einzigen Freigabe
    # sah damit trotzdem alle Dienstnamen und Zustandswerte.
    sichtbar = _sichtbar()
    down = [s for s in sichtbar if s.status == "down"]
    mobile = is_mobile_device(request.headers.get("user-agent", ""))
    ctx = _basis_kontext(request, None)
    ctx.update({
        "registry": sichtbar,
        "down_services": down,
        "total": len(sichtbar),
        "up_count": sum(1 for s in sichtbar if s.status == "up"),
        "is_mobile": mobile,
    })
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/service/{service_id}", response_class=HTMLResponse)
async def service_detail(request: Request, service_id: str):
    svc = by_id(service_id)
    if not svc:
        return HTMLResponse("Service not found", status_code=404)
    mobile = is_mobile_device(request.headers.get("user-agent", ""))
    iframe_url = f"/p/{service_id}/{svc.iframe_path.lstrip('/')}"
    ctx = _basis_kontext(request, service_id)
    ctx.update({
        "svc": svc,
        "iframe_url": iframe_url,
        "is_mobile": mobile,
    })
    return templates.TemplateResponse(request, "service.html", ctx)


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
        for svc in _sichtbar()   # AP08d
    }


# ── Verwaltung (AP202) ────────────────────────────────────────────────
# Benutzerverwaltung mit App-Freigaben. Nur fuer Admin-Konten — alle
# anderen bekommen 404 (wer keinen Zugriff hat, soll nicht erfahren,
# dass es die Seite gibt, wie bei den Diensten auch). Die Freigaben
# selbst erzwingt die _anmeldung-Middleware aus hub_auth; hier werden
# sie nur gesetzt.
#
# Schreibsequenz und Event-Loop: zwischen den Vorpruefungen und dem
# Schreiben liegt kein await — die Sequenz laeuft am Stueck, keine
# andere Anfrage kommt dazwischen. Deshalb ist kein Datei-Lock noetig.
# scrypt blockiert dabei ~0,1 s; bei wenigen Konten vertretbar (das
# Login macht es genauso). run_in_executor wuerde das Race-Fenster
# wieder aufreissen.

MELDUNGEN = {
    "angelegt": ("ok", "Konto angelegt."),
    "gespeichert": ("ok", "Konto gespeichert."),
    "geloescht": ("ok", "Konto gelöscht."),
    "passwort_kurz": ("fehler", "Passwort: mindestens 8 Zeichen."),
    "name_ungueltig": ("fehler", "Ungültiger Nutzername (leer oder '|')."),
    "name_vergeben": ("fehler", "Dieser Name ist bereits vergeben."),
    "dienst_unbekannt": ("fehler", "Unbekannte Dienst-Kennung — "
                                  "nichts gespeichert."),
    "letzter_admin": ("fehler", "Der letzte Admin kann nicht entfernt "
                                "werden."),
    "letzter_nutzer": ("fehler", "Der letzte Nutzer kann nicht gelöscht "
                                 "werden."),
    "unbekannt": ("fehler", "Unbekannter Nutzer."),
}


async def _nur_admin(request: Request):
    """404 fuer alle, die kein Admin sind — konsistent zum
    'Dienst nicht verraten'-Prinzip (AP08)."""
    nutzer = getattr(request.state, "nutzer", None)
    if not nutzer or not hub_auth.ist_admin(nutzer):
        raise HTTPException(status_code=404)


def _dienste_je_kategorie() -> dict[str, list[Service]]:
    """REGISTRY nach Kategorien gruppiert, CATEGORY_ORDER zuerst."""
    ergebnis: dict[str, list[Service]] = {}
    for svc in REGISTRY:
        ergebnis.setdefault(svc.category, []).append(svc)
    geordnet = {c: ergebnis.pop(c) for c in CATEGORY_ORDER if c in ergebnis}
    geordnet.update(ergebnis)
    return geordnet


def _pruefe_eingaben(nutzer: str, passwort: str | None, alle: bool,
                     dienste: list[str]) -> str | None:
    """Gemeinsame Vorpruefungen von anlegen/bearbeiten.

    Gibt einen MELDUNGEN-Schluessel zurueck oder None, wenn alles passt.
    passwort=None heisst beim Bearbeiten: unveraendert, nicht pruefen.
    """
    if not nutzer or "|" in nutzer or len(nutzer) > 64:
        return "name_ungueltig"
    if passwort is not None and len(passwort) < 8:
        return "passwort_kurz"
    if not alle:
        for sid in dienste:
            if not by_id(sid):
                return "dienst_unbekannt"
    return None


@app.get("/verwaltung", dependencies=[Depends(_nur_admin)],
         response_class=HTMLResponse)
async def verwaltung(request: Request,
                     bearbeiten: str = "",
                     msg: str = "",
                     fehler: str = ""):
    konten = hub_auth.konten()
    ziel = konten.get(bearbeiten)
    meldung = MELDUNGEN.get(msg or fehler)
    ctx = _basis_kontext(request, "verwaltung")
    ctx.update({
        "konten": konten,
        "dienste_je_kategorie": _dienste_je_kategorie(),
        "ziel_name": bearbeiten if ziel else "",
        "ziel_admin": ziel["admin"] if ziel else False,
        "ausgewaehlte": (ziel["dienste"] if ziel and isinstance(
            ziel["dienste"], list) else []),
        "ist_alle": ziel is not None and ziel["dienste"] == "*",
        "meldung": meldung,
    })
    return templates.TemplateResponse(request, "verwaltung.html", ctx)


@app.post("/verwaltung/anlegen", dependencies=[Depends(_nur_admin)])
async def verwaltung_anlegen(request: Request,
                             nutzer: str = Form(""),
                             passwort: str = Form(""),
                             admin: str = Form(""),
                             alle: str = Form(""),
                             dienste: list[str] = Form(default=[])):
    nutzer = nutzer.strip()
    fehler = _pruefe_eingaben(nutzer, passwort, bool(alle), dienste)
    if fehler:
        return RedirectResponse(f"/verwaltung?fehler={fehler}",
                                status_code=303)
    if nutzer in hub_auth.konten():
        return RedirectResponse("/verwaltung?fehler=name_vergeben",
                                status_code=303)
    try:
        hub_auth.setze_passwort(passwort, nutzer,
                                dienste=("*" if alle else dienste))
        if admin:
            hub_auth.setze_admin(nutzer, True)
    except ValueError:
        return RedirectResponse("/verwaltung?fehler=unbekannt",
                                status_code=303)
    return RedirectResponse(f"/verwaltung?msg=angelegt&bearbeiten={nutzer}",
                            status_code=303)


@app.post("/verwaltung/bearbeiten", dependencies=[Depends(_nur_admin)])
async def verwaltung_bearbeiten(request: Request,
                                nutzer_alt: str = Form(""),
                                nutzer: str = Form(""),
                                passwort: str = Form(""),
                                admin: str = Form(""),
                                alle: str = Form(""),
                                dienste: list[str] = Form(default=[])):
    konten = hub_auth.konten()
    if nutzer_alt not in konten:
        return RedirectResponse("/verwaltung?fehler=unbekannt",
                                status_code=303)
    nutzer = nutzer.strip()
    # Alle Vorpruefungen VOR dem ersten Schreiben — sonst bleibt bei
    # einem Fehler ein halb geaendertes Konto zurueck.
    fehler = _pruefe_eingaben(nutzer, passwort or None, bool(alle), dienste)
    if fehler:
        return RedirectResponse(f"/verwaltung?fehler={fehler}",
                                status_code=303)
    if nutzer != nutzer_alt and nutzer in konten:
        return RedirectResponse("/verwaltung?fehler=name_vergeben",
                                status_code=303)
    admins = [n for n, k in konten.items() if k["admin"]]
    if not admin and nutzer_alt in admins and len(admins) == 1:
        return RedirectResponse("/verwaltung?fehler=letzter_admin",
                                status_code=303)
    try:
        if nutzer != nutzer_alt:
            hub_auth.benenne_um(nutzer_alt, nutzer)
        if passwort:
            hub_auth.setze_passwort(passwort, nutzer)
        hub_auth.setze_admin(nutzer, bool(admin))
        hub_auth.setze_dienste(nutzer, "*" if alle else dienste)
    except ValueError:
        return RedirectResponse("/verwaltung?fehler=unbekannt",
                                status_code=303)
    return RedirectResponse(f"/verwaltung?msg=gespeichert&bearbeiten={nutzer}",
                            status_code=303)


@app.post("/verwaltung/loeschen", dependencies=[Depends(_nur_admin)])
async def verwaltung_loeschen(request: Request, nutzer: str = Form("")):
    # Vorpruefungen spiegeln die Schutzregeln aus hub_auth — hub_auth
    # bleibt die Instanz, die die Datei schreibt, und wacht noch einmal.
    konten = hub_auth.konten()
    if nutzer not in konten:
        return RedirectResponse("/verwaltung?fehler=unbekannt",
                                status_code=303)
    admins = [n for n, k in konten.items() if k["admin"]]
    if konten[nutzer]["admin"] and len(admins) == 1:
        return RedirectResponse("/verwaltung?fehler=letzter_admin",
                                status_code=303)
    if len(konten) == 1:
        return RedirectResponse("/verwaltung?fehler=letzter_nutzer",
                                status_code=303)
    try:
        hub_auth.loesche_nutzer(nutzer)
    except ValueError:
        return RedirectResponse("/verwaltung?fehler=unbekannt",
                                status_code=303)
    return RedirectResponse("/verwaltung?msg=geloescht", status_code=303)


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

    # Hub-eigene Pfade nicht proxieren. /verwaltung gehoert seit AP202
    # dazu: mit einem gefaelschten Referer /p/<id>/ wuerden sonst
    # Verwaltungs-POSTs an ein Dashboard weitergereicht statt an die
    # Hub-Routen (und deren Admin-Gate).
    if (path.startswith("/p/") or path.startswith("/service/")
            or path == "/api/status" or path.startswith("/vault-file")
            or path.startswith("/pdf/") or path.startswith("/verwaltung")):
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
    resp_headers = _entschaerfe_header(resp_headers, svc)
    content_type = r.headers.get("content-type", "")

    if "text/html" in content_type:
        body_bytes = await r.aread()
        body_bytes = _inject_base_tag(body_bytes, m.group(1))
        return HTMLResponse(content=body_bytes.decode('utf-8', errors='replace'),
                           status_code=r.status_code, headers=resp_headers)
    return StreamingResponse(
        r.aiter_bytes(), status_code=r.status_code, headers=resp_headers, media_type=content_type)

# ── AP08: Anmeldung ───────────────────────────────────────────────────
# Bewusst am Dateiende. Starlette macht die zuletzt registrierte
# Middleware zur aeussersten. Die iframe_proxy_middleware oben reicht
# bei passendem Referer direkt an ein Dashboard weiter, ohne call_next
# aufzurufen — laege die Anmeldung darunter, genuegte ein gefaelschter
# Referer, um sie zu umgehen.
#
# Der Import selbst steht seit AP202 am Dateianfang; hier bleibt nur
# noch der installiere()-Aufruf.
hub_auth.installiere(app)
