# Ryzen Hub

Zentrales Dashboard-Portal für alle lokalen Services auf dem Ryzen.

**Port:** 9000  
**Service:** `systemctl --user status ryzen-hub`

## Services

| Port | Name | Kategorie |
|------|------|-----------|
| 8090 | Krankenversicherung | Dokumente & Abfragen |
| 8094 | KFZ | Dokumente & Abfragen |
| 8091 | Immobilien | Dokumente & Abfragen |
| 8092 | Altersvorsorge | Dokumente & Abfragen |
| 8093 | Sachversicherungen | Dokumente & Abfragen |
| 8080 | Molly (Medikamente) | Haushalt |
| 8765 | Dispatcher | Infrastruktur |
| 8501 | Cache Reader | Infrastruktur |
| 8384 | Syncthing | Infrastruktur |
| 5001 | Docling Serve | Infrastruktur |
| 3000 | Open WebUI | KI |
| 11434 | Ollama | KI |

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

## Health API

`GET /api/status` — JSON mit Status aller Services (up/degraded/down/unknown),
Response-Zeit in ms, letztem Fehler und DB-Kennzahlen.
