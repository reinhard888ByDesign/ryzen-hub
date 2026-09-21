# Ryzen Hub — UI-Richtlinie

Verbindliche Design-Anweisung für alle Apps der Ryzen-Plattform.
Stand: 20.09.2026 · AP210 · Version 1.0

---

## 1. Zweck & Geltung

Diese Richtlinie macht aus 25 einzelnen Web-Oberflächen **eine Plattform**:
gleiche Farbwelt, gleiche Bausteine, gleiche Formate, gleiches Verhalten —
hell und dunkel, auf Desktop und iPhone.

Sie gilt:

- **verbindlich** für alle Hub-Seiten (Übersicht, Verwaltung, Anmeldung);
- **verbindlich** für jede App-Migration (Folge-Arbeitspakete, Reihenfolge
  in Abschnitt 11);
- **nicht** für Drittanbieter-Apps (`extern=True`: open-webui, syncthing,
  docling, ollama) — die bleiben unverändert und öffnen im neuen Tab.

## 2. Grundsätze

1. **Eine Quelle der Wahrheit.** Design und Verhalten kommen aus
   `/ui/hub-ui.css` und `/ui/hub-ui.js` — der Hub liefert beide aus.
   Apps referenzieren sie nur, sie kopieren sie nie.
2. **Die Shell kommt vom Hub.** Der Hub injiziert die Kopfzeile
   („⟨ Hub", App-Name, Status, Konto, Farbschema) in jede App-Seite.
   Apps rendern **keine eigene Kopfzeile, keine eigene Navigation,
   keine eigene Sidebar** — nur Inhalt.
3. **Token statt Literale.** Keine hartkodierten Farben (#hex) im
   App-Code; alles über CSS-Variablen. Ausnahme: die eine
   Domänen-Akzentfarbe (Abschnitt 8b).
4. **Farbe nie allein.** Status wird immer mit Icon **und** Text
   dargestellt — nie nur durch Farbe (Regel aus dem Medizinischen
   Bulletin, deckt sich mit den Dataviz-Vorgaben).
5. **System-Font-Stack.** `-apple-system, BlinkMacSystemFont, …` —
   kein Webfont-Download.
6. **Keine Chart-/JS-Bibliothek.** Das einzige Chart-Muster ist die
   SVG-Polyline (Sparkline, Abschnitt 7). Kein Chart.js/echarts/d3,
   kein CDN, kein jQuery.
7. **Deutsch.** Alle UI-Texte deutsch; englische KPI-Begriffe werden
   übersetzt (Ausnahme: feststehende Eigennamen).
8. **Mobile-Pflicht.** Jede Seite funktioniert bis 390 px Breite
   (Abschnitt 10).
9. **PFLICHT — sortier- und filterbare Listen.** Jede Listenansicht,
   die aus SQL-Datenbanken kommt, ist **pro Spalte sortierbar und
   filterbar** — über die gemeinsame HubTable-Referenz
   (Abschnitt 7, „Tabelle"). Keine App baut eigene Sortier- oder
   Filter-Logik; sie markiert nur das Markup.

## 3. Einbindung für Apps

Jede App-Seite bindet exakt einmal ein:

```html
<head>
  <script>try{var t=localStorage.getItem('hub-theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>
  <link rel="stylesheet" href="/ui/hub-ui.css">
  <script src="/ui/hub-ui.js" defer></script>
</head>
<body class="hub-ui">
```

Erläuterungen:

- Das kleine Script **vor** dem Stylesheet verhindert das Aufblitzen
  des falschen Farbschemas (FOUC). Es muss vor jedem `<link>` stehen.
- `class="hub-ui"` auf `<body>` aktiviert Reset + Komponenten.
- App-Inhalte liegen in `.container` — **feste Breite**
  (`width: 100%; max-width: 960 px; min-width: 0`, zentriert): alle
  Seiten einer App sind gleich breit, unabhängig vom Inhalt.
  `min-width: 0` ist Pflicht — ohne sie weitet die automatische
  Inhalts-Mindestbreite von Flex-Items den Container auf breiten
  Tabellenseiten über 960 px auf (AP223c/d).
- Der Hub ergänzt bei eigenen Apps (`rahmen=True`) automatisch Shell,
  Assets und den Pfad-Patcher — die App braucht sich darum nicht zu
  kümmern. Migrierte Apps lassen ihre eigene Einbindung trotzdem
  stehen (die Injection erkennt Dopplungen; der `__hubUi`-Guard in
  hub-ui.js verhindert Doppel-Init).

**Domänen-Akzent:** Wer eine eigene Akzentfarbe führen will, setzt
**eine** Variable im `<head>`-Style (z. B. `<style>body.hub-ui{--app-accent:#b8860b}</style>`)
und nutzt im Inhalt nur `var(--app-accent)`. Kern-Tokens dürfen nicht
überschrieben werden.

**App-eigenes CSS relativ referenzieren** (`static/app.css`): so lädt es
über das Hub-`<base>` im Proxy **und** direkt auf dem App-Port. Ein
root-relativer Pfad (`/static/…`) geht über den Proxy ins Leere (Lehre
AP220: Molly lief bis dahin ohne eigenes CSS). Die App mountet
`/static` auf ihr eigenes Verzeichnis und `/ui` auf das ryzen-hub-`static/ui`-Verzeichnis.

## 4. Design-Tokens

Alle Farben, Abstände, Radien und Schatten kommen aus `hub-ui.css`.
Auszug (vollständige Liste = Datei selbst, Abschnitt 1–2):

### Helles Schema

| Rolle | Token | Wert |
|---|---|---|
| Hintergrund | `--bg` | `#f5f5f7` |
| Karte | `--card` | `#ffffff` |
| Text 1/2/3 | `--text-1/-2/-3` | `#1d1d1f` / `#6e6e73` / `#aeaeb2` |
| Akzent (+hover/soft) | `--accent` | `#0071e3` (`#0077ed`, `rgba(0,113,227,.10)`) |
| Status grün / amber / rot / grau | `--green` / `--amber` / `--red` / `--gray` | `#34c759` / `#ff9500` / `#ff3b30` / `#8e8e93` (je + `-soft`-Hintergrund und `-text`-Textfarbe) |
| Rahmen | `--border` / `--border-light` | `rgba(0,0,0,.07)` / `rgba(0,0,0,.04)` |
| Radien | `--radius-sm/-radius/-radius-lg` | `8px` / `12px` / `16px` |

### Dunkles Schema

Dieselben Tokens, andere Werte: `--bg #161618`, `--card #1f1f21`,
**Text IMMER weiß** (`--text-1/-2/-3 = #ffffff` — Vorgabe: im
Dunkelmodus ist kein grauer Text erlaubt; Abstufung läuft über
Schriftgröße und -gewicht, nicht über Grautöne), Akzent `#0a84ff`,
Status `#30d158`/`#ff9f0a`/`#ff453a`/`#98989d`, Rahmen
weiß-transparent. `color-scheme` wird je Schema gesetzt (native
Controls, Scrollbars).

### Skalen

- **Abstände:** `--sp-1…--sp-6` = 4/8/12/16/24/32 px.
- **Typografie:** 11 (Labels) · 12 (Meta) · 13 (Fließtext) · 14.5
  (Kartentitel) · 20 (Widget-KPI) · 24 (Seitentitel) px.
- **Motion:** `--ease: cubic-bezier(.25,.46,.45,.94)`, Übergänge
  0,12–0,18 s, keine Animationen über 0,3 s.
- **Maße:** Sidebar 248 px, Shell-Höhe 46 px.

## 5. Status-Semantik

| Status | Anzeige | Farbe | Bedeutung |
|---|---|---|---|
| `up` | ● Online | `--green` | Health-Check HTTP < 500, Health-JSON ok |
| `degraded` | ◐ Beeinträchtigt | `--amber` | HTTP ≥ 500 oder Health-JSON „degraded" |
| `down` | × Offline | `--red` | Keine Antwort |
| `unknown` | … Prüfe… (pulsiert) | `--gray` | Noch kein Check (max. 30 s nach Neustart) |

Darstellung: Badge = Soft-Hintergrund (`-soft`) + Textfarbe (`-text`)
+ Icon + Label — **nie Farbe allein**. Der Punkt (`.dot`) ist die
Kompaktform in Listen, ersetzt aber nie das Label.

## 6. Seitenaufbau

**Hub-Seiten:** Sidebar (nur System: Übersicht, Verwaltung [Admin],
Konto, Farbschema, Abmelden) + Inhalt mit 32 px Rand; Alerts stehen
oben über dem Inhalt.

**App-Seiten:** Shell (kommt vom Hub) + `.container` mit App-Inhalt:

```
┌─────────────────────────────────────────────┐
│ ⟨ Hub   💊 KV   ● Online     reinhard  ☯    │  ← Shell (injiziert)
├─────────────────────────────────────────────┤
│  .container (max-width 960px, zentriert)    │
│  ┌───────────────┐  ┌───────────────┐       │
│  │ KPI-Karte     │  │ KPI-Karte     │       │
│  └───────────────┘  └───────────────┘       │
│  Tabelle (HubTable: sortierbar + filterbar) │
└─────────────────────────────────────────────┘
```

## 7. Komponenten-Katalog

Je Komponente: Zweck, Klassen, Zustände, Dos/Don'ts.

### Shell
`#hub-shell` — injiziert der Hub. Apps: **nichts tun**. Sticky oben,
Höhe `--shell-h`, enthält Zurück-Link, App-Icon+Name, Status-Badge
(pollt alle 30 s), Konto, Farbschema-Umschalter.

### Widget / KPI-Karte (Kommandozentrale)
Klasse `widget` (+ `widget--breit` = 2 Spalten). Aufbau: Icon, Name,
Beschreibung, Status-Badge, KPI-Wert + Label, Sparkline, Fußzeile.
Die KPI-Karte **in** einer App nutzt dieselben Klassen (`widget-kpi`,
`kpi-value`, `kpi-label`) ohne Verlinkung.

### Tabelle — PFLICHT für jede SQL-Liste
Deklaratives HubTable-Markup, Sortierung + Filter kommen automatisch
aus `hub-ui.js`:

```html
<div class="hub-table-wrap">
  <table class="hub-table" data-sort data-filter="Suchen…">
    <thead>
      <tr>
        <th data-sort data-sort-erste="1">Datum</th>       <!-- Vorsortierung -->
        <th data-sort data-sort-typ="text">Leistungserbringer</th>
        <th data-sort data-sort-typ="euro">Betrag</th>     <!-- 1.234,56 € -->
        <th data-sort data-sort-typ="datum">Belegdatum</th> <!-- DD.MM.YYYY -->
      </tr>
    </thead>
    <tbody>…</tbody>
  </table>
</div>
```

Regeln:

- **Sortier-Typen:** `text` (Standard), `zahl`, `euro`, `datum` —
  die Parser verstehen die deutschen Formate aus Abschnitt 8.
- Klick auf den Kopf toggelt auf/ab (Pfeil + `aria-sort`); leere
  Zellen sortieren immer ans Ende.
- `data-filter="Platzhaltertext"` erzeugt das Suchfeld über der
  Tabelle; gefiltert wird über den sichtbaren Text; null Treffer ⇒
  Leerzustand mit „Filter zurücksetzen".
- **Suchfeld-Position (AP223b, gilt für alle Listen):** Das
  HubTable-Suchfeld steht IMMER **rechtsbündig über der Tabelle**.
  Steht direkt davor ein Server-Filter (`.toolbar`, z. B.
  Fahrzeug-Auswahl), bilden beide **eine Zeile** (`.liste-kopf`):
  Filter links, Suchfeld rechts. hub-ui.js baut die Zeile
  automatisch — Apps rendern nur Toolbar + Tabelle in dieser
  Reihenfolge.
- Zahlen rechtsbündig mit `.num`, negativ zusätzlich `.num-neg`.
- Summenzeile: `<tr class="foot-row">` in einem zweiten `<tbody>`.
- Demo zum Ausprobieren: `/ui/demo.html`. Sortierung/Filter laufen
  clientseitig über die gerenderte Tabelle —
  ausreichend für die Größenordnungen aller Dashboards. Für sehr
  große Datenmengen (als dokumentierte Ausnahme): Server-Sortierung
  mit Query-Parametern `?sort=<spalte>&richtung=auf|ab&f=<text>`.

### Formular
`.v-form` (Spaltenlayout, 10 px Abstand), `.v-field` (Label +
Eingabefeld), Fokus: Akzentrahmen + `3px` Akzent-Soft-Schein.
Checkboxen mit `accent-color`. Fehlertext unter dem Feld in
`--err-text`, niemals nur roter Rahmen.

### Buttons
`.btn` (Standard), `.btn-primary` (eine Aktion pro Seite),
`.btn-danger` (nur zerstörende Aktionen, mit Rückfrage). Mindesthöhe
36 px, mobil 44 px.

### Badges / Status
`.badge` + `.badge-up/-degraded/-down/-unknown` (Abschnitt 5).
Domänen-Badges (z. B. Länder, Kassen) folgen demselben Muster:
Soft-Hintergrund + Textfarbe + kurzes Label.

### Alerts
`.alert-error` / `.alert-warn` / `.alert-ok` — Icon + aussagekräftiger
Text + optionale Aktion. Stehen am Seitenanfang über dem Inhalt.

### Leerzustand
`.empty-state`: Icon (48 px, gedämpft), Titel, erklärender Satz,
optionale Aktion. **Pflicht** für jede leere Liste — „0 Zeilen" ohne
Erklärung ist verboten.

### Fehlerzustand / Down
`.down-state`: Icon, „{App} ist nicht erreichbar", `last_error` in
Monospace, „↺ Erneut versuchen". Der Hub liefert diese Seite
automatisch (503), Apps müssen sie nicht selbst bauen.

### Dialog / Modal
Muster aus der Aufgaben-App: Overlay + Karte, schließen per Esc,
Klick aufs Overlay und Abbrechen-Button. Bestätigen heißt
„Löschen"/„Speichern", nie „OK".

### Navigation (Kacheln) — PFLICHT für alle Apps

**Verbindliche Regel für jede migrierte App** (Nutzer-Entscheidung
21.09.2026, AP222): Die KPI-Kacheln sind die **einzige** in-App-
Navigation — keine Menüleisten, keine Tabbars.

- Kacheln = `widget` als `<a>` mit Pfeil in der Fußzeile
  (Kommandozentralen-Muster); die Kachel-Zeile erscheint auf
  **jeder** Seite der App.
- Die Kachel des aktuellen Bereichs ist nicht klickbar
  (`<div class="widget widget-aktiv">`, Akzentrahmen).
- Die Kachel zur App-Startseite verlinkt auf **`./`** — ein
  `href="/"` führt über den Hub-Proxy zum Hub selbst, weil Hub-Pfade
  vom Patcher ausgenommen sind (AP210).
- Kachel-Werte (KPIs) werden serverseitig berechnet und sind auf
  allen Seiten identisch.
- Die `.tabbar`-Komponente bleibt nur für noch nicht migrierte Apps
  bestehen und wird bei deren Migration entfernt.

### Sparkline / Chart
Das **einzige** Chart-Muster: SVG-Polyline.

```html
<svg viewBox="0 0 120 28" preserveAspectRatio="none" aria-hidden="true">
  <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="…"/>
</svg>
```

Normalisierung min/max auf den Zeichenbereich (Vorlage: `_spark_punkte()`
in `ryzen-hub/app.py` und das Muster in altersvorsorge/dashboard.py).
Tooltips als SVG-`<title>`-Element. Keine Balken-`<div>`-Konstrukte
(finanzen), keine Bibliotheken.

## 8. Verbindliche Formate

| Was | Format | Beispiel |
|---|---|---|
| **EUR-Beträge** | **PFLICHT: 1000er-Punkt und IMMER genau zwei Nachkommastellen** — auch bei runden Beträgen | `1.234,56 €` · `1.234,00 €` |
| Stückzahlen | 1000er-Punkt, keine Nachkommastellen | `1.234` |
| Prozente | ein Dezimal-Komma | `4,2 %` |
| Datum | `DD.MM.YYYY` (zweistellig Tag/Monat) | `05.03.2026` |
| Uhrzeit | `HH:MM` | `14:05` |
| Antwortzeit | ganzzahlig | `42 ms` |
| Betragsfarben | negativ: `--err-text` **mit Minuszeichen**; positiv: normale Textfarbe. **Grün ist für Status reserviert — nie für Geld.** | `−123,45 €` |

Referenzfunktion (locale-unabhängig, in jede App übernehmbar):

```python
def format_euro(betrag: float) -> str:
    """EUR-Betrag: 1000er-Punkt, IMMER zwei Nachkommastellen."""
    vorzeichen = "-" if betrag < 0 else ""
    ganz, dez = f"{abs(betrag):,.2f}".split(".")
    tausender = ganz.replace(",", ".")
    return f"{vorzeichen}{tausender},{dez} €"
```

Beispiele: `format_euro(1234)` → `"1.234,00 €"`,
`format_euro(-42.5)` → `"-42,50 €"`.

## 8b. Farbwelt

**Eine Basis für alle, ein Akzent je Domäne** (Entscheidung 20.09.2026):

- Grundfarben (Hintergrund, Karten, Text, Rahmen, Schatten) und
  **Statusfarben** (grün/amber/rot/grau) sind überall identisch —
  nicht verhandelbar.
- Jede App darf **eine** Domänen-Akzentfarbe über `--app-accent`
  führen, aus dieser festen Zuordnung:

| Akzent | Wert | Apps |
|---|---|---|
| Blau | `#0071e3` | Standard: KV, KFZ, Immobilien, Altersvorsorge, Sachversicherungen, Absender, Pipeline-Gruppe, Vault Integrity, Aufgaben |
| Gold | `#b8860b` | Goldbestand |
| Teal | `#0d6e6e` | Medizinisches Bulletin, Molly |
| Violett | `#8b5cf6` | Finanzen, Investor Reporting |

Weitere Akzente sind nicht vorgesehen; neue Apps ordnen sich einer
bestehenden Farbe zu.

**Domänen-Badges:** Länder-Badges (DE/IT in kfz und
sachversicherungen) folgen dem Status-Badge-Muster (Soft-Hintergrund +
Textfarbe + Label). Konvention, festgelegt AP221: **DE = Blau**
(`--accent-soft`/`--accent`), **IT = Orange**
(`--amber-soft`/`--warn-text`).

**Personen-Badges** (festgelegt AP228): **Marion = Rosé** `#c7254e`
(Dunkelmodus `#ff7a95`), **Reinhard = Blau** (`--accent`). Als
App-Token `--person-marion` umsetzen, Text-Badge mit Namen — nie
Farbe allein. Gilt für leistungsabrechnung, altersvorsorge,
medizinisches-bulletin.

## 9. Theme (hell/dunkel)

- **Automatik** (`prefers-color-scheme`) ist der Standard; der
  Umschalter (Shell, Sidebar, Anmeldung) dreht dreistufig:
  Auto → Hell → Dunkel → Auto. Auswahl liegt in
  `localStorage['hub-theme']` (leer/`light`/`dark`) und steuert
  `data-theme` auf `<html>`.
- **Regeln für Apps:** alle Farben über Tokens (nie hartkodiert),
  beide Schemata testen, `color-scheme` nicht selbst setzen (kommt
  aus hub-ui.css).

## 10. Mobile-Pflicht

- Breakpoints **768 px** und **390 px**; Grids fallen auf 1 Spalte,
  breite Widgets auf volle Breite.
- **Tap-Ziele ≥ 44 px**; Tabellen bekommen horizontalen Scroll
  (`.hub-table-wrap`), Kernspalten zuerst.
- Shell im Kompaktmodus (Zurück, Name, Badge, Theme); die App selbst
  braucht **keine eigene mobile Navigation** — die kommt vom Hub.
- Jede neue Seite wird auf iPhone-Breite geprüft.

## 11. Migrations-Checkliste je App

Gemeinsam für alle („Sippe" = die 9 FastAPI-Apps mit Inline-CSS):

- Inline-`CSS = """…"""` und die kopierte `:root`-Zeile entfernen →
  `/ui/hub-ui.css` einbinden (Abschnitt 3).
- **Jede SQL-Tabelle** auf HubTable-Markup umstellen
  (`data-sort`/`data-filter`/`data-sort-typ`) — keine eigene
  Sortier-/Filter-Logik behalten.
- Alle EUR-Ausgaben über `format_euro()` (zwei Nachkommastellen!).
- Datumswerte auf `DD.MM.YYYY` bringen.
- Statusgrüns/-rots vereinheitlichen (`--green` etc.).
- Menüleiste/Tabbar entfernen → **KPI-Kacheln als Navigation auf
  jeder Seite** (Abschnitt 7 „Navigation"); Start-Kachel auf `./`.
- Mobile-Media-Queries ergänzen/prüfen.

Einzelbefunde (aus der UI-Inventur 09/2026):

| App (Port) | Befunde → zu tun |
|---|---|
| molly (8081) | ✅ **migriert (AP220, 21.09.2026)** — Shell statt Sidebar, Tokens + Teal-`--app-accent`, HubTable für Erledigte Tage + Librela-Historie, Mobile-Queries, Soll=0-Fix, relative Asset-Pfade |
| leistungsabrechnung (8090) | ✅ **migriert (AP228, 21.09.2026)** — 4 Kacheln, 6 HubTables (colspan/details raus), Marion-Token `#c7254e` (+Dark `#ff7a95`), `format_euro()` + DD.MM.YYYY, Kassen-Badges, Beleg-Existenz-Check |
| kfz (8094) | ✅ **migriert (AP221+AP222, 21.09.2026)** — alle 11 SQL-Tabellen → HubTable, `format_euro()` + DD.MM.YYYY, DE/IT-Badges auf Konvention (DE=blau/IT=orange), PDF-Viewer → Tokens, `/health`, Mobile-Queries, eigene Steuern-Seite, **Kachel-Navigation auf jeder Seite** (Referenz-Muster für alle Apps) |
| sachversicherungen (8093) | ✅ **migriert (AP228, 21.09.2026)** — 2 Kacheln, 3 HubTables, `.badge-land`-Tokens, `format_euro()`, /praemien-500er gefixt, 11 tote Quell-PDFs ohne Link |
| altersvorsorge (8092) | ✅ **migriert (AP228, 21.09.2026)** — 3 Kacheln (Verträge/Reinhard/Marion), Sparkline-Referenz beibehalten, Marion auf `#c7254e`, `format_euro()` |
| aufgaben (8096) | ✅ **migriert (AP228, 21.09.2026)** — 3 Kacheln (Aufgaben/Überfällig/Thema), Dialog-Referenzmuster erhalten, Bulk-Aktionen unverändert, Tabellen → HubTable |
| finanzen (8097) | ✅ **migriert (AP228, 21.09.2026)** — 6 Kacheln, 15 HubTables, Div-Balken → SVG-Sparkline, Violett-Akzent, `format_euro()`, Δ-Prozent-Fix bei negativer Basis |
| goldbestand (8098) | ✅ **migriert (AP228, 21.09.2026)** — 4 Kacheln, 4 HubTables, Gold-Akzent `--app-accent` |
| investor (8095) | ✅ **migriert (AP228, 21.09.2026)** — 5 Kacheln (je Gesellschaft + Exit-Radar), 20 HubTables, Labels deutsch, Gauge auf Tokens |
| immobilien (8091) | ✅ **migriert (AP228, 21.09.2026)** — 6 Kacheln, 19 HubTables, Kennzahlen als KPI + Sub-Label, NK-Drilldown als Server-Filter, 59 fehlende Vault-Dateien ohne Link |
| vault-integrity (8099) | ✅ **migriert (AP228, 21.09.2026)** — 4 Kacheln, 3 HubTables, Health-Ring-Spezial-Pattern behalten, Hartcodes → Tokens; Hinweis: stdlib-`http.server`, `/ui` aus Handler, Assets relativ |
| medizinisches-bulletin (8100) | ✅ **migriert (AP228, 21.09.2026)** — 2 Personen-Kacheln (ohne Daten-Leak), Markdown-Tabellen → HubTables (44/40), Teal-Akzent, Cookie-Check erhalten, Mobile ergänzt |

**Migrationsreihenfolge:** alle ✅ erledigt — ~~(1) molly~~ ✅ AP220 ·
~~(2) kfz~~ ✅ AP221 · (3–8) leistungsabrechnung, sachversicherungen,
altersvorsorge, finanzen, goldbestand, aufgaben, investor, immobilien,
vault-integrity, medizinisches-bulletin — ✅ **AP228 (21.09.2026):
alle 10 Apps migriert**. Offen: Browser-Tests durch den Nutzer.

## 12. Changelog

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 20.09.2026 | Erste Fassung (AP210): Kommandozentrale, Shell, Hell+Dunkel, HubTable-Pflicht, Formate, Farbwelt, Migrations-Checkliste |
| 1.1 | 21.09.2026 | AP221: `.tabbar`-Referenzkomponente, DE/IT-Badge-Konvention (DE=blau/IT=orange), relative App-CSS-Pfade festgeschrieben; kfz (8094) migriert |
| 1.2 | 21.09.2026 | AP222: Kachel-Navigation als Tabs-Alternative dokumentiert (§7); kfz: Steuern-Seite + Kachel-Navigation (Nutzer-Entscheidung) |
| 1.3 | 21.09.2026 | AP222b: Kachel-Navigation ist PFLICHT für alle Apps (§7, §11) — auf jeder Seite, aktive Kachel markiert, Start-Kachel auf `./`; kfz umgesetzt |
| 1.4 | 21.09.2026 | AP223: Layout-Fix — `body.hub-ui` als Flex-Spalte (Shell oben, Inhalt darunter); vorher standen Shell und App-Container nebeneinander (Inhalt zentriert im Restplatz, mobil zerquetscht) |
| 1.5 | 21.09.2026 | AP223b: Suchfeld-Regel für alle Listen — HubTable-Suchfeld rechtsbündig über der Tabelle, Server-Filter links, beide in einer Zeile (`.liste-kopf`, baut hub-ui.js automatisch) |
| 1.6 | 21.09.2026 | AP223c: `.container` mit fester Breite (`width:100%; max-width:960px`) — alle Seiten einer App gleich breit, unabhängig vom Inhalt |
| 1.7 | 21.09.2026 | AP223d: `min-width: 0` am `.container` — verhindert Aufweitung über 960 px durch die automatische Inhalts-Mindestbreite von Flex-Items (breite Tabellen) |
| 1.8 | 21.09.2026 | AP228: alle 10 verbleibenden Apps migriert (§11 komplett ✅) — Personen-Badge-Konvention (Marion Rosé `#c7254e`, Reinhard Blau) in §8b; alle Apps mit `/health` |
