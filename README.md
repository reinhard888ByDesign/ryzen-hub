# Ryzen Hub

Zentrales Dashboard-Portal für alle lokalen Services auf dem Ryzen.

**Port:** 9000  
**Service:** `systemctl --user status ryzen-hub`

Der Hub proxy't alle Dashboards unter `/p/<service-id>/` — die Dashboards
selbst lauschen nur auf `127.0.0.1` (AP07-Zonentrennung).

## Services

| Port | Name | Kategorie |
|------|------|-----------|
| 127.0.0.1:8090 | Krankenversicherung | Dokumente & Abfragen |
| 127.0.0.1:8094 | KFZ | Dokumente & Abfragen |
| 127.0.0.1:8091 | Immobilien | Dokumente & Abfragen |
| 127.0.0.1:8765 | Absender DB | Dokumente & Abfragen |
| 127.0.0.1:8092 | Altersvorsorge | Dokumente & Abfragen |
| 127.0.0.1:8093 | Sachversicherungen | Dokumente & Abfragen |
| 127.0.0.1:8097 | Finanzanalyse | Dokumente & Abfragen |
| 127.0.0.1:8098 | Goldbestand | Dokumente & Abfragen |
| 127.0.0.1:8100 | Medizinisches Bulletin | Dokumente & Abfragen |
| 127.0.0.1:8095 | Investor Reporting | Dokumente & Abfragen |
| 127.0.0.1:8771 | Email-Absender | Dokumente & Abfragen |
| 127.0.0.1:8096 | Aufgaben | Haushalt |
| 127.0.0.1:8081 | Molly | Haushalt |
| 127.0.0.1:8765 | Dispatcher | Infrastruktur |
| 127.0.0.1:8765/pipeline | Pipeline Live | Infrastruktur |
| 127.0.0.1:8765/pipeline/history | Pipeline History | Infrastruktur |
| 127.0.0.1:8765/batch | Batch Verarbeitung | Infrastruktur |
| 127.0.0.1:8765 | Pipeline Debugger | Infrastruktur |
| 127.0.0.1:8501 | Cache Reader | Infrastruktur |
| 127.0.0.1:8384 | Syncthing | Infrastruktur |
| 127.0.0.1:5001 | Docling Serve | Infrastruktur |
| 127.0.0.1:8099 | Vault Integrity | Infrastruktur |
| 127.0.0.1:3000 | Open WebUI | KI |
| 127.0.0.1:11434 | Ollama | KI |
| Wilson Pi :8095 | openclaw · Wilson | KI |

## Anmeldung & Benutzerverwaltung (AP202)

Der Hub verlangt eine Anmeldung (signiertes Sitzungs-Cookie, Passwörter
als scrypt-Hash in `~/.config/ryzen-hub/auth.json`). Von außen liegt
zusätzlich Cloudflare Access (Google-Login) davor.

- **`/verwaltung`** — Konten anlegen/bearbeiten/löschen und App-Freigaben
  per Haken setzen. Nur für Admin-Konten (Sidebar „⚙️ Verwaltung").
- Freigaben wirken am Hub: ohne Freigabe liefern Dienst-Pfade 404.
- Der letzte Admin kann weder gelöscht noch zurückgestuft werden.
- „Alle Dienste" (`"*"`) umfasst zusätzlich `/vault-file` und `/pdf/` —
  diese Pfade gehören zu keinem einzelnen Dienst.

Befehlszeile (Alternative zur Web-Oberfläche): `dms-ap/hub_auth.py`
(`--passwort-setzen`, `--dienste-setzen`, `--admin-setzen`, `--liste`,
`--loeschen`). Details: `dms-ap/KONTEN_HUB.md` und `dms-ap/AP202_ERGEBNIS.md`.

## Kommandozentrale & Design-System (AP210)

Die Startseite ist ein Live-Betriebs-Dashboard: ein Widget je Dienst
(Status-Badge, Kennzahl, Sparkline), gruppiert nach Kategorie, mit
Suche und Alert-Streifen. Die Widgets sind die einzige Navigation zu
den Apps; die Seitenleiste führt nur System-Einträge.

- **Globaler Rahmen:** Der Hub injiziert eine schlanke Kopfzeile
  („⟨ Hub", App-Name, Status, Konto, Farbschema) in jede eigene App —
  Apps öffnen im selben Tab. Drittanbieter (`extern=True`) öffnen im
  neuen Tab.
- **Hell + Dunkel:** automatisch nach Systemeinstellung, mit
  dreistufigem Umschalter (Auto/Hell/Dunkel).
- **Gemeinsame Assets:** `/ui/hub-ui.css` + `/ui/hub-ui.js`
  (Design-Tokens, Shell, HubTable: sortier- und filterbare Tabellen).
- **HubTable live ansehen:** `/ui/demo.html` — sortier- und
  filterbare Beispieltabelle.
- **Verbindliche Regeln für alle Apps:** `UI-RICHTLINIE.md` —
  Design-Tokens, Komponenten, Formate (EUR immer mit 1000er-Punkt
  und zwei Nachkommastellen), Status-Semantik, Migrations-Checkliste.

## Starten / Stoppen

```bash
systemctl --user start ryzen-hub
systemctl --user stop ryzen-hub
systemctl --user restart ryzen-hub
```

## Entwicklung

```bash
cd /home/reinhard/ryzen-hub
uvicorn app:app --host 0.0.0.0 --port 9000 --reload
```

Tests: `python3 /home/reinhard/dms-ap/test_hub_verwaltung.py`
(Anmeldung + Verwaltung; läuft gegen ein Wegwerf-Verzeichnis).

## Health API

- `GET /health` — frei zugänglich, gibt nur `{"status": "ok"}` (für
  Überwachung von außen).
- `GET /api/status` — hinter der Anmeldung, gefiltert auf die
  Freigaben des Kontos: Status aller Dienste (up/degraded/down/unknown),
  Response-Zeit in ms, letzter Fehler, DB-Kennzahlen und Sparkline-Werte.
- `/ui/…` — statische Design-Assets (hub-ui.css, hub-ui.js), frei.

Der Healthcheck (`~/.local/bin/ryzen-hub-healthcheck.sh`, Cron alle
15 Min) meldet sich als Monitor-Konto an; das Passwort liegt in
`~/.config/ryzen-hub/monitor-passwort` (0600).
