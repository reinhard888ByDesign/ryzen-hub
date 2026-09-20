/* ============================================================
   Ryzen Hub UI — gemeinsames Verhalten (AP210)

   Drei Module, eine Datei (siehe UI-RICHTLINIE.md):
     HubTheme  — Farbschema Auto/Hell/Dunkel (localStorage 'hub-theme')
     HubShell  — globaler Rahmen, vom Hub per data-app injiziert
     HubTable  — Sortierung pro Spalte + Filter fuer SQL-Listen

   Wird vom Hub in proxied Apps injiziert UND von den Hub-Seiten
   selbst eingebunden. Guard gegen Doppel-Init.
   ============================================================ */
(function () {
  'use strict';
  if (window.__hubUi) return;
  window.__hubUi = true;

  /* ── HubTheme ────────────────────────────────────────────────── */

  var LS_KEY = 'hub-theme';           // '' = Auto, 'light', 'dark'
  var THEME_LABEL = { '': '☯ Auto', light: '☀ Hell', dark: '🌙 Dunkel' };

  function themeLesen() {
    try { return localStorage.getItem(LS_KEY) || ''; } catch (e) { return ''; }
  }

  function themeAnwenden() {
    var t = themeLesen();
    if (t === '') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', t);
    return t;
  }

  function themeUmschalten() {
    var reihe = ['', 'light', 'dark'];
    var t = themeLesen();
    var naechste = reihe[(reihe.indexOf(t) + 1) % reihe.length];
    try {
      if (naechste === '') localStorage.removeItem(LS_KEY);
      else localStorage.setItem(LS_KEY, naechste);
    } catch (e) {}
    themeAnwenden();
    var knoepfe = document.querySelectorAll('.hub-theme-btn');
    for (var i = 0; i < knoepfe.length; i++) themeKnopfBeschriften(knoepfe[i]);
  }

  function themeKnopfBeschriften(btn) {
    btn.textContent = THEME_LABEL[themeLesen()] || THEME_LABEL[''];
    btn.title = 'Farbschema umschalten (Auto → Hell → Dunkel)';
  }

  function themeKnopf(btn) {
    if (!btn || btn.dataset.hubThemeAngebunden) return;
    btn.dataset.hubThemeAngebunden = '1';
    btn.classList.add('hub-theme-btn');
    btn.addEventListener('click', themeUmschalten);
    themeKnopfBeschriften(btn);
  }

  window.HubTheme = {
    anwenden: themeAnwenden,
    umschalten: themeUmschalten,
    knopf: themeKnopf
  };

  /* ── HubShell ────────────────────────────────────────────────── */

  var STATUS_LABEL = {
    up: 'Online', degraded: 'Beeinträchtigt',
    down: 'Offline', unknown: 'Prüfe…'
  };

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = String(s == null ? '' : s);
    return d.innerHTML;
  }

  function badgeHtml(status) {
    var s = STATUS_LABEL[status] ? status : 'unknown';
    return '<span class="badge badge-' + s + ' hub-shell-badge">' +
           '<span class="dot dot-' + s + '"></span>' +
           esc(STATUS_LABEL[s]) + '</span>';
  }

  function shellRendern() {
    var root = document.getElementById('hub-shell');
    if (!root || root.dataset.gerendert) return;
    root.dataset.gerendert = '1';
    var meta = {};
    try { meta = JSON.parse(root.dataset.app || '{}'); } catch (e) {}

    var html =
      '<a href="/" class="hub-shell-back" title="Zurück zum Hub">⟨ Hub</a>' +
      '<span class="hub-shell-title">' + esc(meta.icon || '') + ' ' +
        esc(meta.name || '') + '</span>' +
      badgeHtml(meta.status) +
      '<span class="hub-shell-spacer"></span>';
    if (meta.nutzer) {
      html += '<span class="hub-shell-user">' + esc(meta.nutzer) +
              (meta.ist_admin ? ' · Admin' : '') + '</span>';
    }
    html += '<button type="button" class="hub-theme-btn" aria-label="Farbschema"></button>';
    root.innerHTML = html;
    themeKnopf(root.querySelector('.hub-theme-btn'));

    if (meta.id) {
      var poll = function () {
        fetch('/api/status').then(function (r) {
          if (!r.ok) throw new Error('status ' + r.status);
          return r.json();
        }).then(function (daten) {
          var s = daten && daten[meta.id] ? daten[meta.id].status : 'unknown';
          var b = root.querySelector('.hub-shell-badge');
          if (b) b.outerHTML = badgeHtml(s);
        }).catch(function () { /* still */ });
      };
      setInterval(poll, 30000);
    }
  }

  window.HubShell = { rendern: shellRendern };

  /* ── HubTable ────────────────────────────────────────────────── */

  // Deutsche Formate: "1.234,56", "1,234.56", "12.345", "4.321" — best effort.
  function parseZahl(s) {
    s = String(s).replace(/[^\d,.\-]/g, '');
    if (!s) return NaN;
    var minus = s.charAt(0) === '-';
    s = s.replace(/-/g, '');
    var hatKomma = s.indexOf(',') !== -1;
    var hatPunkt = s.indexOf('.') !== -1;
    if (hatKomma && hatPunkt) {
      if (s.lastIndexOf(',') > s.lastIndexOf('.')) {
        s = s.replace(/\./g, '').replace(',', '.');
      } else {
        s = s.replace(/,/g, '');
      }
    } else if (hatKomma) {
      s = s.replace(',', '.');
    }
    var w = parseFloat(s);
    return minus ? -w : w;
  }

  function parseDatum(s) {
    var m = String(s).match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/);
    return m ? new Date(+m[3], +m[2] - 1, +m[1]).getTime() : NaN;
  }

  var SORT_FN = {
    text: function (s) { return String(s).toLowerCase(); },
    zahl: parseZahl,
    euro: parseZahl,
    datum: parseDatum
  };

  function tabelleSortieren(tbody, spalte, richtung, typ) {
    var fn = SORT_FN[typ] || SORT_FN.text;
    var zeilen = Array.prototype.slice.call(tbody.rows);
    zeilen.forEach(function (r) {
      r._hubV = r.cells[spalte] ? fn(r.cells[spalte].textContent) : null;
    });
    zeilen.sort(function (a, b) {
      var av = a._hubV, bv = b._hubV;
      var aNan = av === null || (typeof av === 'number' && isNaN(av));
      var bNan = bv === null || (typeof bv === 'number' && isNaN(bv));
      if (aNan && bNan) return 0;
      if (aNan) return 1;    // leere Zellen immer ans Ende
      if (bNan) return -1;
      if (av < bv) return -richtung;
      if (av > bv) return richtung;
      return 0;
    });
    zeilen.forEach(function (r) { tbody.appendChild(r); });
  }

  function tabelleSortInit(table) {
    var koepfe = Array.prototype.slice.call(table.querySelectorAll('th[data-sort]'));
    var tbody = table.tBodies && table.tBodies[0];
    if (!koepfe.length || !tbody) return;
    var spalte = -1, richtung = 1;

    function pfeil(th, text) {
      var p = th.querySelector('.sort-arrow');
      if (p) p.textContent = text || '';
    }

    function aktualisiere(th, i, richt) {
      spalte = i; richtung = richt;
      koepfe.forEach(function (t) {
        t.removeAttribute('aria-sort');
        pfeil(t, '');
      });
      th.setAttribute('aria-sort', richt === 1 ? 'ascending' : 'descending');
      pfeil(th, richt === 1 ? '▲' : '▼');
      tabelleSortieren(tbody, th.cellIndex, richtung,
                       th.getAttribute('data-sort-typ') || 'text');
    }

    koepfe.forEach(function (th, i) {
      if (!th.querySelector('.sort-arrow')) {
        var p = document.createElement('span');
        p.className = 'sort-arrow';
        p.setAttribute('aria-hidden', 'true');
        th.appendChild(p);
      }
      th.addEventListener('click', function () {
        if (spalte === i) aktualisiere(th, i, -richtung);
        else aktualisiere(th, i, 1);
      });
      if (th.getAttribute('data-sort-erste') === '1') aktualisiere(th, i, 1);
    });
  }

  function tabelleFilterInit(table) {
    var ph = table.getAttribute('data-filter');
    if (!ph) return;
    var wrap = document.createElement('div');
    wrap.className = 'hub-table-filter';
    wrap.innerHTML = '<span class="lupe" aria-hidden="true">⌕</span>';
    var input = document.createElement('input');
    input.type = 'search';
    input.placeholder = ph;
    input.setAttribute('aria-label', ph);
    wrap.appendChild(input);
    table.parentNode.insertBefore(wrap, table);

    var leer = document.createElement('div');
    leer.className = 'hub-table-leer';
    leer.style.display = 'none';
    leer.innerHTML =
      '<div class="empty-icon">🔍</div>' +
      '<div class="empty-title">Keine Einträge gefunden</div>' +
      '<div class="empty-text">Der Filter liefert keine Treffer.</div>' +
      '<button type="button" class="btn">Filter zurücksetzen</button>';
    table.parentNode.insertBefore(leer, table.nextSibling);
    leer.querySelector('button').addEventListener('click', function () {
      input.value = '';
      anwenden();
      input.focus();
    });

    function anwenden() {
      var q = input.value.trim().toLowerCase();
      var sichtbar = 0;
      var tbody = table.tBodies && table.tBodies[0];
      if (tbody) {
        for (var i = 0; i < tbody.rows.length; i++) {
          var passt = !q || tbody.rows[i].textContent.toLowerCase().indexOf(q) !== -1;
          tbody.rows[i].style.display = passt ? '' : 'none';
          if (passt) sichtbar++;
        }
      }
      leer.style.display = (q && sichtbar === 0) ? '' : 'none';
    }

    input.addEventListener('input', anwenden);
  }

  function tabellenInit(wurzel) {
    var root = wurzel || document;
    var tabellen = root.querySelectorAll('table.hub-table');
    for (var i = 0; i < tabellen.length; i++) {
      if (tabellen[i].hasAttribute('data-sort')) tabelleSortInit(tabellen[i]);
      if (tabellen[i].hasAttribute('data-filter')) tabelleFilterInit(tabellen[i]);
    }
  }

  window.HubTable = { init: tabellenInit };

  /* ── Init ────────────────────────────────────────────────────── */

  function init() {
    themeAnwenden();
    shellRendern();
    tabellenInit(document);
    var knoepfe = document.querySelectorAll('[data-hub-theme]');
    for (var i = 0; i < knoepfe.length; i++) themeKnopf(knoepfe[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
