"""pages/downloader.py — Al-Kamel CSV browser, renamer and downloader."""

import streamlit as st
import streamlit.components.v1 as components


SERIES_CONFIG = {
    "FIA WEC": {
        "url": "https://fiawec.alkamelsystems.com/",
        "series_folder": "WEC",
        "hint": "Select a season and event, then click Scan for CSVs.",
    },
    "ELMS": {
        "url": "https://elms.alkamelsystems.com/",
        "series_folder": "ELMS",
        "hint": "Select a season and event, then click Scan for CSVs.",
    },
    "IMSA (up to 2024)": {
        "url": "http://imsa.alkamelsystems.com/",
        "series_folder": "IMSA",
        "hint": "Select a season and event, then click Scan for CSVs. IMSA 2025+ requires manual URL.",
    },
}


def show_downloader():
    st.subheader("Download Al-Kamel CSVs")

    st.info(
        "Al-Kamel's servers block downloads from cloud IPs (including this app's server). "
        "This page runs entirely in **your browser** — navigate to the event, scan for CSVs, "
        "and download them. Files are renamed and the target folder path is shown "
        "so you know exactly where to put them."
    )

    selected_series = st.selectbox("Series:", list(SERIES_CONFIG.keys()), key="dl_series")
    cfg = SERIES_CONFIG[selected_series]

    tab_browser, tab_manual = st.tabs(["Browse & Download", "Paste a URL directly"])

    with tab_browser:
        _show_browser_tab(cfg)

    with tab_manual:
        _show_manual_tab()


def _show_browser_tab(cfg: dict):
    base_url = cfg["url"]
    series_folder = cfg["series_folder"]

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: #1e1e1e; color: #e0e0e0; font-size: 13px; }}

#toolbar {{
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; background: #2b2b2b;
  border-bottom: 1px solid #444; flex-wrap: wrap;
}}
#url-bar {{
  flex: 1; min-width: 200px; padding: 5px 8px;
  background: #1a1a1a; color: #e0e0e0;
  border: 1px solid #555; border-radius: 4px; font-size: 13px;
}}
button {{
  padding: 5px 14px; border: none; border-radius: 4px;
  cursor: pointer; font-size: 13px; white-space: nowrap;
}}
#btn-go   {{ background: #555; color: #fff; }}
#btn-scan {{ background: #e05c00; color: #fff; font-weight: 600; }}
#btn-go:hover   {{ background: #666; }}
#btn-scan:hover {{ background: #c04a00; }}
#status {{ font-size: 12px; color: #888; }}

#frame-wrap {{ height: 380px; border-bottom: 1px solid #444; }}
#timing-frame {{ width: 100%; height: 100%; border: none; background: #fff; }}

#results {{ padding: 10px; max-height: 320px; overflow-y: auto; }}
#results p {{ color: #888; padding: 4px 0; }}

.section-head {{
  font-size: 12px; font-weight: 600; color: #aaa; text-transform: uppercase;
  letter-spacing: .05em; padding: 10px 0 4px; border-top: 1px solid #333;
  margin-top: 6px;
}}
.section-head:first-child {{ border-top: none; margin-top: 0; }}

table {{ width: 100%; border-collapse: collapse; }}
th {{
  text-align: left; padding: 5px 8px; background: #2b2b2b; color: #bbb;
  position: sticky; top: 0; font-size: 12px;
}}
td {{ padding: 4px 8px; border-bottom: 1px solid #2a2a2a; vertical-align: top; }}
tr:hover td {{ background: #252525; }}

.fname {{ color: #e0e0e0; font-weight: 500; }}
.fpath {{ color: #888; font-size: 11px; font-family: monospace; margin-top: 2px; }}
.badge {{
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 11px; font-weight: 600;
}}
.badge-race    {{ background: #7a2020; color: #ffaaaa; }}
.badge-prac    {{ background: #1a4a2a; color: #88ffaa; }}
.badge-qual    {{ background: #1a3060; color: #88aaff; }}
.badge-other   {{ background: #333; color: #aaa; }}

.dl-btn {{
  display: inline-block; padding: 3px 10px;
  background: #e05c00; color: #fff !important;
  text-decoration: none; border-radius: 3px;
  font-size: 12px; white-space: nowrap;
}}
.dl-btn:hover {{ background: #c04a00; }}

#help {{
  padding: 8px 10px; background: #232323; font-size: 12px; color: #888;
  border-top: 1px solid #333;
}}
#help strong {{ color: #ccc; }}
</style>
</head>
<body>

<div id="toolbar">
  <input id="url-bar" type="text" value="{base_url}" />
  <button id="btn-go">Go</button>
  <button id="btn-scan">⬇ Scan for CSVs</button>
  <span id="status"></span>
</div>

<div id="frame-wrap">
  <iframe id="timing-frame" src="{base_url}"
    sandbox="allow-scripts allow-same-origin allow-forms allow-popups">
  </iframe>
</div>

<div id="results">
  <p>{cfg['hint']} Files will be renamed automatically.</p>
</div>

<div id="help">
  <strong>After downloading:</strong>
  place each file at the path shown under the filename, then push to GitHub.
  The app will pick them up automatically.
</div>

<script>
const SERIES = "{series_folder}";
const frame   = document.getElementById('timing-frame');
const urlBar  = document.getElementById('url-bar');
const btnGo   = document.getElementById('btn-go');
const btnScan = document.getElementById('btn-scan');
const results = document.getElementById('results');
const status  = document.getElementById('status');

frame.addEventListener('load', () => {{
  try {{ urlBar.value = frame.contentWindow.location.href; }} catch(e) {{}}
}});
btnGo.addEventListener('click', () => {{ if (urlBar.value.trim()) frame.src = urlBar.value.trim(); }});
urlBar.addEventListener('keydown', e => {{ if (e.key === 'Enter') btnGo.click(); }});

// ── Slug helpers ────────────────────────────────────────────────────────────
function slugify(s) {{
  return s.toLowerCase()
    .replace(/\\s+/g, '-')
    .replace(/[^a-z0-9\\-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}}

function stripPrefix(s) {{
  // strip leading NN_ or YYYYMMDDHHNN_ prefix
  return s.replace(/^\\d{{12}}_/, '').replace(/^\\d{{2}}_/, '').trim();
}}

// ── Classify session ─────────────────────────────────────────────────────────
function classify(sessionName, subSession) {{
  const combined = (sessionName + ' ' + (subSession || '')).toLowerCase();
  if (combined.includes('hyperpole')) return 'qualifying';
  if (combined.includes('qualifying')) return 'qualifying';
  if (combined.includes('race') && !combined.includes('practice')) return 'race';
  if (combined.includes('practice') || combined.includes('test')) return 'practice';
  return 'other';
}}

// ── Generate a clean filename ─────────────────────────────────────────────────
function makeFilename(sessionName, subSession, type, dateStr) {{
  const sn = sessionName.toLowerCase();
  const sub = (subSession || '').toLowerCase();
  const dateSuffix = (dateStr && type === 'race') ? `_${{dateStr}}` : '';

  if (type === 'race') {{
    if (sub.match(/hour/)) {{
      const m = sub.match(/hour\\s*(\\d+)/);
      return m ? `race_hour${{m[1]}}${{dateSuffix}}.csv` : `race${{dateSuffix}}.csv`;
    }}
    return `race${{dateSuffix}}.csv`;
  }}

  if (type === 'qualifying') {{
    const base = sn
      .replace('qualifying', 'qualifying')
      .replace('hyperpole', 'hyperpole')
      .replace(/\\s+/g, '_')
      .replace(/[^a-z0-9_]/g, '');
    return base + '.csv';
  }}

  if (type === 'practice') {{
    const m = sn.match(/(\\d+)/);
    if (m) return `practice${{m[1]}}.csv`;
    const clean = sn
      .replace(/free\\s*/g, '')
      .replace(/practice\\s*/g, 'practice_')
      .replace(/\\s+/g, '_')
      .replace(/[^a-z0-9_]/g, '');
    return clean.replace(/_+/g, '_').replace(/^_|_$/g, '') + '.csv';
  }}

  return slugify(sn).replace(/-/g, '_') + '.csv';
}}

// ── Build suggested path ──────────────────────────────────────────────────────
function makePath(year, round, type, filename) {{
  return `${{SERIES}}/${{year}}/${{round}}/${{type}}/${{filename}}`;
}}

// ── Main scan ─────────────────────────────────────────────────────────────────
btnScan.addEventListener('click', async () => {{
  let pageUrl, pageHtml;

  try {{
    const iframeDoc = frame.contentDocument || frame.contentWindow.document;
    pageUrl = frame.contentWindow.location.href;
    pageHtml = iframeDoc.documentElement.outerHTML;
  }} catch(e) {{
    pageUrl = urlBar.value.trim();
  }}

  if (!pageHtml) {{
    status.textContent = 'Fetching...';
    try {{
      const r = await fetch(pageUrl, {{credentials: 'include'}});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      pageHtml = await r.text();
    }} catch(err) {{
      status.textContent = 'Could not fetch: ' + err.message;
      results.innerHTML = '<p style="color:#e05c00">Could not read the page. Navigate to an event first.</p>';
      return;
    }}
  }}

  status.textContent = 'Scanning...';

  const parser = new DOMParser();
  const doc = parser.parseFromString(pageHtml, 'text/html');
  const links = Array.from(doc.querySelectorAll('a[href]'));

  const csvLinks = [...new Set(
    links
      .map(a => a.href || a.getAttribute('href'))
      .filter(h => h && h.toUpperCase().endsWith('.CSV'))
      .map(h => {{
        if (h.startsWith('http')) return h;
        try {{ return new URL(h, pageUrl).href; }} catch(e) {{ return h; }}
      }})
  )];

  if (!csvLinks.length) {{
    status.textContent = 'No CSVs found.';
    results.innerHTML = '<p>No CSV files found. Make sure you have selected an event on the left panel.</p>';
    return;
  }}

  // Parse each URL into metadata
  const rows = csvLinks.map(url => {{
    const decoded = decodeURIComponent(url);
    const parts = decoded.split('/');

    // Find "Results" index
    const ri = parts.indexOf('Results');
    if (ri < 0) return null;

    const seasonPart  = parts[ri + 1] || '';   // e.g. "15_2026"
    const roundPart   = parts[ri + 2] || '';   // e.g. "02_SPA FRANCORCHAMPS"
    // parts[ri+3] is championship, skip it
    const sessionPart = parts[ri + 4] || '';   // e.g. "202605071100_Free Practice 1"
    const maybeSubSes = parts[ri + 5] || '';   // e.g. "06_Hour 6" or filename
    const filename    = parts[parts.length - 1];

    // Only keep Analysis / Results CSVs
    const isAnalysis = filename.includes('23_Analysis') || filename.includes('03_Results');
    if (!isAnalysis) return null;

    const year        = seasonPart.replace(/^\\d+_/, '');
    const roundName   = stripPrefix(roundPart);
    const round       = slugify(roundName);
    const sessionName = stripPrefix(sessionPart);

    // Sub-session? Only if the 2nd-to-last path part isn't the filename
    const subSession  = (maybeSubSes && !maybeSubSes.toUpperCase().endsWith('.CSV'))
                        ? stripPrefix(maybeSubSes) : '';

    // Extract YYYYMMDD from the session folder timestamp prefix
    const dateStr = (sessionPart.length >= 8 && /^\\d{{8}}/.test(sessionPart))
                    ? sessionPart.slice(0, 8) : '';

    const type     = classify(sessionName, subSession);
    const newName  = makeFilename(sessionName, subSession, type, dateStr);
    const path     = makePath(year, round, type, newName);
    const label    = sessionName + (subSession ? ' / ' + subSession : '');

    return {{ url, year, round: roundName, label, type, newName, path }};
  }}).filter(Boolean);

  if (!rows.length) {{
    status.textContent = 'No Analysis CSVs found.';
    results.innerHTML = '<p>Found CSV files but none matched the Analysis/Results pattern. Try a different event.</p>';
    return;
  }}

  // Group by session type for display
  const groups = {{}};
  const order = ['race', 'practice', 'qualifying', 'other'];
  for (const r of rows) {{
    (groups[r.type] = groups[r.type] || []).push(r);
  }}

  const badgeMap = {{
    race:      ['badge-race',  'Race'],
    practice:  ['badge-prac',  'Practice'],
    qualifying:['badge-qual',  'Qualifying'],
    other:     ['badge-other', 'Other'],
  }};

  status.textContent = `Found ${{rows.length}} Analysis CSV(s).`;

  let html = '<table><thead><tr><th>File / Suggested path</th><th>Type</th><th>Download</th></tr></thead><tbody>';

  for (const type of order) {{
    if (!groups[type]) continue;
    for (const r of groups[type]) {{
      const [cls, label] = badgeMap[type] || badgeMap.other;
      html += `
        <tr>
          <td>
            <div class="fname">${{r.newName}}</div>
            <div class="fpath">data/${{r.path}}</div>
          </td>
          <td><span class="badge ${{cls}}">${{label}}</span></td>
          <td><a class="dl-btn" href="${{r.url}}" download="${{r.newName}}" target="_blank">Download</a></td>
        </tr>`;
    }}
  }}

  html += '</tbody></table>';
  results.innerHTML = html;
}});
</script>
</body>
</html>"""

    components.html(html, height=780, scrolling=False)


def _show_manual_tab():
    st.markdown(
        "Paste a direct CSV URL here. The app will try to fetch it server-side. "
        "If that's blocked (HTTP 403), use the Browse tab instead."
    )
    url = st.text_input(
        "CSV URL:",
        placeholder="https://fiawec.alkamelsystems.com/Results/…/23_Analysis_Race_Hour 6.CSV",
        key="dl_manual_url",
    )
    if st.button("Fetch CSV", key="dl_fetch_btn") and url:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": url.split("/Results/")[0] + "/" if "/Results/" in url else url,
        }
        try:
            with st.spinner("Fetching…"):
                resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                filename = url.split("/")[-1]
                st.success(f"Fetched {filename} ({len(resp.content):,} bytes)")
                st.download_button(
                    label=f"⬇ Save {filename}",
                    data=resp.content,
                    file_name=filename,
                    mime="text/csv",
                )
            elif resp.status_code == 403:
                st.warning(
                    "Blocked by Al-Kamel (HTTP 403 — cloud IP not in allowlist). "
                    "Use the Browse & Download tab — that runs in your browser, which isn't blocked."
                )
            else:
                st.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            st.error(f"Request failed: {e}")
