"""Auto-discovery recon helpers (Layer 2).

First-pass, breadth-over-depth mapping of a web target across five dimensions:
functionality, UI, accessibility, performance, and security. Deliberately NOT a
full audit — just enough signal to prove value and point QA where to go deeper.

Each function returns a human-readable, structured string in the same PASS /
WARN / FAIL idiom the rest of qa-execution uses, so the output reads well both
to a person and to an LLM orchestrating a recon run.

Web dimensions run against a live Playwright `Page`; the security check runs a
standalone httpx request so it works even before a browser is started.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

# --------------------------------------------------------------------------- #
# Navigation that survives single-page apps
# --------------------------------------------------------------------------- #


async def navigate_and_settle(page: Any, url: str, settle_ms: int = 2500) -> str:
    """Navigate to `url` and give a client-rendered (SPA) page time to paint.

    `goto` returns on the 'load' event, but React/Vue/Angular apps render most
    of their real surface *after* that. We then wait — best-effort — for the
    network to go idle so discovery/a11y see the hydrated DOM, not an empty
    shell. Pages that poll forever never go idle; that's expected, so the wait
    timing out is not an error. Returns the final URL (post-redirect).
    """
    await page.goto(url)
    try:
        await page.wait_for_load_state("networkidle", timeout=settle_ms)
    except Exception:
        # Never-idle page (polling/websockets) or slow tail — proceed with
        # whatever has rendered so far rather than failing the whole recon.
        pass
    return page.url


# --------------------------------------------------------------------------- #
# Functionality + UI discovery
# --------------------------------------------------------------------------- #

_DISCOVER_JS = r"""
(limit) => {
  const abs = (h) => { try { return new URL(h, location.href).href; } catch { return null; } };
  const origin = location.origin;
  const rawLinks = Array.from(document.querySelectorAll('a[href]'))
    .map(a => abs(a.getAttribute('href')))
    .filter(Boolean)
    .filter(u => u.startsWith('http'));
  const internal = [...new Set(rawLinks.filter(u => u.startsWith(origin)))];
  const external = [...new Set(rawLinks.filter(u => !u.startsWith(origin)))];

  const forms = Array.from(document.querySelectorAll('form')).map(f => ({
    action: f.getAttribute('action') || '(submits to current URL)',
    method: (f.getAttribute('method') || 'get').toUpperCase(),
    fields: Array.from(f.querySelectorAll('input, select, textarea'))
      .map(i => (i.getAttribute('name') || i.getAttribute('id') || i.getAttribute('type') || i.tagName.toLowerCase()))
      .slice(0, 25),
  }));

  const nav = [...new Set(
    Array.from(document.querySelectorAll('nav a, [role="navigation"] a'))
      .map(a => (a.innerText || '').trim())
      .filter(Boolean)
  )].slice(0, 25);

  const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]').length;
  const media = {
    images: document.querySelectorAll('img').length,
    videos: document.querySelectorAll('video').length,
    iframes: document.querySelectorAll('iframe').length,
  };

  return {
    title: document.title,
    origin,
    internalCount: internal.length,
    externalCount: external.length,
    internal: internal.slice(0, limit),
    external: external.slice(0, limit),
    forms,
    nav,
    buttons,
    media,
  };
}
"""


async def discover(page: Any, limit: int = 30) -> str:
    """Map the current page's surface: links, forms, nav, interactive counts.

    This is the 'what flows exist here' pass — the raw material an orchestrator
    uses to decide which main flows to walk.
    """
    data = await page.evaluate(_DISCOVER_JS, limit)
    lines = [
        "=== DISCOVERY (functionality surface) ===",
        f"Title: {data['title']}",
        f"Origin: {data['origin']}",
        f"Links: {data['internalCount']} internal, {data['externalCount']} external",
        f"Interactive: {data['buttons']} buttons/submits, {len(data['forms'])} forms",
        f"Media: {data['media']['images']} img, {data['media']['videos']} video, "
        f"{data['media']['iframes']} iframe",
    ]

    if data["nav"]:
        lines.append("Primary nav: " + ", ".join(data["nav"]))

    if data["forms"]:
        lines.append(f"\nForms ({len(data['forms'])}) — candidate main flows:")
        for i, f in enumerate(data["forms"], 1):
            fields = ", ".join(f["fields"]) if f["fields"] else "(no named fields)"
            lines.append(f"  [{i}] {f['method']} {f['action']}  fields: {fields}")

    if data["internal"]:
        lines.append(f"\nInternal links (first {len(data['internal'])}):")
        for u in data["internal"]:
            lines.append(f"  {u}")

    if data["external"]:
        lines.append(f"\nExternal links (first {len(data['external'])}):")
        for u in data["external"]:
            lines.append(f"  {u}")

    lines.append(
        "\nGo deeper: pick the highest-risk form/flow above and walk it with "
        "web_navigate + web_type + web_click + web_assert_*."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Accessibility (first-pass, structural — no external axe dependency)
# --------------------------------------------------------------------------- #

_A11Y_JS = r"""
(limit) => {
  const acc = (el) => (
    (el.getAttribute('aria-label') || '').trim() ||
    (el.getAttribute('title') || '').trim() ||
    (el.innerText || el.value || '').trim()
  );
  const brief = (el) => {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string')
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return (tag + id + cls).slice(0, 80);
  };

  const findings = [];
  const push = (sev, rule, detail, examples) =>
    findings.push({ sev, rule, detail, examples: (examples || []).slice(0, limit) });

  // Document-level
  const lang = document.documentElement.getAttribute('lang');
  if (!lang) push('FAIL', 'html-has-lang', '<html> has no lang attribute', []);
  if (!document.title || !document.title.trim())
    push('FAIL', 'document-title', 'Document has no <title>', []);
  if (!document.querySelector('meta[name="viewport"]'))
    push('WARN', 'meta-viewport', 'No responsive viewport meta tag', []);

  // Images without alt
  const imgs = Array.from(document.querySelectorAll('img'))
    .filter(i => !i.hasAttribute('alt'));
  if (imgs.length)
    push('FAIL', 'image-alt', imgs.length + ' <img> without alt attribute',
         imgs.map(brief));

  // Inputs without an accessible label
  const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
    .filter(i => !['hidden', 'submit', 'button', 'reset'].includes(i.type));
  const unlabeled = inputs.filter(i => {
    if (i.getAttribute('aria-label') || i.getAttribute('aria-labelledby')) return false;
    if (i.id && document.querySelector('label[for="' + CSS.escape(i.id) + '"]')) return false;
    if (i.closest('label')) return false;
    if ((i.getAttribute('placeholder') || '').trim()) return false; // weak, but counts
    return true;
  });
  if (unlabeled.length)
    push('FAIL', 'form-label', unlabeled.length + ' form field(s) with no accessible label',
         unlabeled.map(brief));

  // Buttons / links with no accessible name
  const controls = Array.from(document.querySelectorAll('button, a[href], [role="button"]'));
  const nameless = controls.filter(c => !acc(c) && !c.querySelector('img[alt]'));
  if (nameless.length)
    push('FAIL', 'control-name', nameless.length + ' button/link(s) with no accessible name',
         nameless.map(brief));

  // Headings
  const h1s = document.querySelectorAll('h1').length;
  if (h1s === 0) push('WARN', 'page-has-h1', 'No <h1> on the page', []);
  if (h1s > 1) push('WARN', 'single-h1', h1s + ' <h1> elements (expected 1)', []);
  const levels = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .map(h => parseInt(h.tagName[1], 10));
  let skipped = 0, prev = 0;
  for (const l of levels) { if (prev && l > prev + 1) skipped++; prev = l; }
  if (skipped) push('WARN', 'heading-order', skipped + ' heading level jump(s) (e.g. h2 → h4)', []);

  // Landmarks
  const landmarks = ['main', 'nav', 'header', 'footer']
    .filter(t => !document.querySelector(t + ', [role="' + (t === 'main' ? 'main' : t) + '"]'));
  if (!document.querySelector('main, [role="main"]'))
    push('WARN', 'landmark-main', 'No <main> / role="main" landmark', []);

  // Positive tabindex (anti-pattern)
  const posTab = Array.from(document.querySelectorAll('[tabindex]'))
    .filter(e => parseInt(e.getAttribute('tabindex'), 10) > 0);
  if (posTab.length)
    push('WARN', 'tabindex', posTab.length + ' element(s) with positive tabindex (disrupts tab order)',
         posTab.map(brief));

  return {
    findings,
    counts: {
      images: document.querySelectorAll('img').length,
      inputs: inputs.length,
      controls: controls.length,
      headings: levels.length,
    },
  };
}
"""


async def a11y_audit(page: Any, limit: int = 8) -> str:
    """First-pass structural accessibility scan (no color-contrast — needs a real lib).

    Covers the cheap, high-signal WCAG failures: missing alt, unlabeled fields,
    nameless controls, lang, headings, landmarks, tabindex.
    """
    data = await page.evaluate(_A11Y_JS, limit)
    findings = data["findings"]
    c = data["counts"]
    fails = sum(1 for f in findings if f["sev"] == "FAIL")
    warns = sum(1 for f in findings if f["sev"] == "WARN")

    lines = [
        "=== ACCESSIBILITY (first-pass, structural) ===",
        f"Scanned: {c['images']} images, {c['inputs']} fields, "
        f"{c['controls']} controls, {c['headings']} headings",
        f"Result: {fails} FAIL, {warns} WARN",
    ]
    if not findings:
        lines.append("No structural a11y issues in the checked rules. (Contrast not checked.)")
    for f in findings:
        lines.append(f"  {f['sev']} [{f['rule']}] {f['detail']}")
        for ex in f["examples"]:
            lines.append(f"        e.g. {ex}")
    lines.append(
        "\nScope note: structural checks only — color contrast, focus-visible, "
        "and screen-reader flow are NOT covered. Go deeper with axe-core or a "
        "manual VoiceOver/TalkBack pass on the flagged screens."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Performance snapshot (Navigation + Paint + Resource timing)
# --------------------------------------------------------------------------- #

_PERF_JS = r"""
() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paints = {};
  for (const p of performance.getEntriesByType('paint')) paints[p.name] = Math.round(p.startTime);

  const res = performance.getEntriesByType('resource');
  let transfer = 0;
  const byType = {};
  const largest = [];
  for (const r of res) {
    const size = r.transferSize || 0;
    transfer += size;
    byType[r.initiatorType] = (byType[r.initiatorType] || 0) + 1;
    largest.push({ url: r.name, size, type: r.initiatorType });
  }
  largest.sort((a, b) => b.size - a.size);

  return {
    ttfb: nav.responseStart ? Math.round(nav.responseStart) : null,
    domContentLoaded: nav.domContentLoadedEventEnd ? Math.round(nav.domContentLoadedEventEnd) : null,
    load: nav.loadEventEnd ? Math.round(nav.loadEventEnd) : null,
    fcp: paints['first-contentful-paint'] || null,
    transferBytes: transfer,
    resourceCount: res.length,
    byType,
    domNodes: document.getElementsByTagName('*').length,
    largest: largest.slice(0, 5),
  };
}
"""


def _band(value: int | None, good: int, poor: int) -> str:
    if value is None:
        return "n/a"
    if value <= good:
        return "GOOD"
    if value <= poor:
        return "NEEDS-WORK"
    return "POOR"


def _kb(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


async def perf_snapshot(page: Any) -> str:
    """Single-page performance snapshot from the browser's own timing APIs.

    Reports TTFB, FCP, DOMContentLoaded, load, transfer weight, request count,
    and DOM size with rough Web-Vitals-style bands. First-pass, single load —
    not a lab benchmark (no throttling, cold cache not guaranteed).
    """
    d = await page.evaluate(_PERF_JS)
    lines = [
        "=== PERFORMANCE (first-pass, single load) ===",
        f"TTFB:              {d['ttfb']} ms",
        f"First Contentful Paint: {d['fcp']} ms   [{_band(d['fcp'], 1800, 3000)}]",
        f"DOMContentLoaded:  {d['domContentLoaded']} ms",
        f"Load:              {d['load']} ms   [{_band(d['load'], 2500, 5000)}]",
        f"Transfer weight:   {_kb(d['transferBytes'])} across {d['resourceCount']} requests"
        f"   [{_band(d['transferBytes'], 1_500_000, 4_000_000)}]",
        f"DOM nodes:         {d['domNodes']}   [{_band(d['domNodes'], 1500, 3000)}]",
    ]
    if d["byType"]:
        breakdown = ", ".join(f"{k}={v}" for k, v in d["byType"].items())
        lines.append(f"Requests by type:  {breakdown}")
    if d["largest"] and any(r["size"] for r in d["largest"]):
        lines.append("Heaviest resources:")
        for r in d["largest"]:
            if r["size"]:
                lines.append(f"  {_kb(r['size'])}  ({r['type']})  {r['url'][:90]}")
    lines.append(
        "\nNote: transferSize reads 0 for cross-origin resources without "
        "Timing-Allow-Origin, so weight can be understated. Go deeper with a "
        "throttled Lighthouse run or k6 for server-side load."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Security headers (first-pass — surface hygiene, NOT a pentest)
# --------------------------------------------------------------------------- #

_SEC_HEADERS = {
    "strict-transport-security": ("HSTS", "FAIL"),
    "content-security-policy": ("Content-Security-Policy", "FAIL"),
    "x-content-type-options": ("X-Content-Type-Options", "WARN"),
    "x-frame-options": ("X-Frame-Options / frame-ancestors", "WARN"),
    "referrer-policy": ("Referrer-Policy", "WARN"),
    "permissions-policy": ("Permissions-Policy", "WARN"),
}
_DISCLOSURE_HEADERS = ["server", "x-powered-by", "x-aspnet-version"]


async def security_headers(url: str) -> str:
    """First-pass transport/header security hygiene for a URL.

    Checks HTTPS upgrade, the standard security headers, cookie flags, and
    version-disclosure headers. Explicitly NOT a penetration test — no auth,
    injection, or logic testing. Enough to flag obvious gaps and decide whether
    a real security pass is warranted.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"FAIL: url must start with http:// or https:// (got {url!r})"

    lines = ["=== SECURITY (first-pass — transport & headers only) ==="]
    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, verify=True
        ) as client:
            resp = await client.get(url)
    except Exception as e:
        return f"REQUEST ERROR: {type(e).__name__}: {e}"

    final = str(resp.url)
    lines.append(f"Requested: {url}")
    lines.append(f"Final URL: {final}  (status {resp.status_code})")

    # HTTPS
    if urlparse(final).scheme == "https":
        upgraded = parsed.scheme == "http"
        lines.append(f"  PASS [https] Served over HTTPS{' (upgraded from HTTP)' if upgraded else ''}")
    else:
        lines.append("  FAIL [https] Final response is not HTTPS")

    headers = {k.lower(): v for k, v in resp.headers.items()}

    # Standard security headers
    for key, (label, sev) in _SEC_HEADERS.items():
        if key in headers:
            lines.append(f"  PASS [{key}] {label}: {headers[key][:80]}")
        else:
            lines.append(f"  {sev} [{key}] {label} missing")

    # Cookie flags
    raw_cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    if raw_cookies:
        for c in raw_cookies:
            name = c.split("=", 1)[0]
            flags = c.lower()
            missing = [
                f for f in ("secure", "httponly", "samesite")
                if f not in flags
            ]
            if missing:
                lines.append(f"  WARN [cookie] {name}: missing {', '.join(missing)}")
            else:
                lines.append(f"  PASS [cookie] {name}: Secure + HttpOnly + SameSite set")

    # Version disclosure
    disclosed = [(h, headers[h]) for h in _DISCLOSURE_HEADERS if h in headers]
    for h, v in disclosed:
        lines.append(f"  WARN [disclosure] {h}: {v[:60]} (reveals stack/version)")

    lines.append(
        "\nScope note: this is surface hygiene only — no auth, injection, "
        "access-control, or dependency testing. Go deeper with OWASP ZAP or a "
        "dedicated security review before trusting these results."
    )
    return "\n".join(lines)
