// Claude Usage Widget — background script
// Runs inside Zen Browser, fetches usage from claude.ai (same-origin, no CORS),
// and POSTs it to the local Python server at localhost:8765.

const SERVER = "http://localhost:8765/data";

function resetsIn(iso) {
  if (!iso) return "\u2014";
  const diff = Math.max(0, new Date(iso) - Date.now());
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0 && m > 0) return h + "h " + m + "m";
  if (h > 0) return h + "h";
  return m + "m";
}

async function fetchAndPost() {
  try {
    // 1. get org id
    const orgsRes = await fetch("https://claude.ai/api/organizations", { credentials: "include" });
    if (!orgsRes.ok) { console.warn("[widget] orgs:", orgsRes.status); return; }
    const orgs = await orgsRes.json();
    const org  = Array.isArray(orgs) ? orgs[0] : null;
    if (!org) { console.warn("[widget] no org"); return; }
    const orgId = org.uuid || org.id;

    // 2. get usage
    const usageRes = await fetch(`https://claude.ai/api/organizations/${orgId}/usage`, { credentials: "include" });
    if (!usageRes.ok) { console.warn("[widget] usage:", usageRes.status); return; }
    const d = await usageRes.json();

    const payload = {
      five_hour:      d.five_hour      || null,
      seven_day:      d.seven_day      || null,
      extra_usage:    d.extra_usage    || null,
      resets_session: resetsIn(d.five_hour  && d.five_hour.resets_at),
      resets_weekly:  resetsIn(d.seven_day  && d.seven_day.resets_at),
    };

    // 3. post to local widget server
    await fetch(SERVER, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    const fh = d.five_hour  || {};
    const sd = d.seven_day  || {};
    console.log(
      "[widget] updated — session", Math.round(fh.utilization || 0) + "%",
      "weekly", Math.round(sd.utilization || 0) + "%"
    );
  } catch (e) {
    console.warn("[widget] fetch error:", e.message);
  }
}

// run on install / browser startup
browser.runtime.onInstalled.addListener(fetchAndPost);
browser.runtime.onStartup.addListener(fetchAndPost);

// run every 5 minutes
browser.alarms.create("fetch-usage", { periodInMinutes: 5 });
browser.alarms.onAlarm.addListener(() => fetchAndPost());
