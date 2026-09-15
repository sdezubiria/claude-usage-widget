// Claude Code Usage Widget for Übersicht
// Lives on the desktop, reads usage_data.json written by fetch_usage.py

// Full path to usage_data.json in your clone of the repo — edit this.
const DATA_FILE = "$HOME/claude-usage-widget/usage_data.json"

export const command = `cat "${DATA_FILE}" 2>/dev/null || echo '{}'`

export const refreshFrequency = 60000 // 1 min — reads local file only, no network call

export const className = `
  bottom: 700px;
  left: 32px;
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 11px;
  color: #C8C9CA;
  -webkit-user-select: none;
`

// Name shown under the mascot. Leave empty to hide it.
const SIGNATURE = "Simón De Zubiría"

// pixel robot — redrawn from Claude Code reference screenshot
// 16×16 grid, color #E07050 matches the warm coral in the UI
// Animation: steps() timing keeps the motion chunky like pixel art.
// The mood class (set from session usage) changes speed and adds effects:
//   idle   <25%   slow breathing, standing still
//   work   25-74  walks in place, swings arms
//   hustle 75-89  double speed + sweat drop
//   panic  90-99  frantic + shaking + sweat
//   sleep  100%   eyes shut, slow breathing, floating z's
var robotCss = `
  .cc-bot { overflow: visible; --bob: 0.8s; --walk: 0.4s; --swing: 0.8s; }

  .cc-bot .bob   { animation: cc-bob var(--bob) steps(1) infinite; }
  .cc-bot .legA  { animation: cc-up var(--walk) steps(1) infinite; }
  .cc-bot .legB  { animation: cc-upB var(--walk) steps(1) infinite; }
  .cc-bot .armL  { animation: cc-down var(--swing) steps(1) infinite; }
  .cc-bot .armR  { animation: cc-downB var(--swing) steps(1) infinite; }
  .cc-bot .eyes  { animation: cc-blink 4s steps(1) infinite;
                   transform-box: fill-box; transform-origin: center; }
  .cc-bot .sweat, .cc-bot .z { opacity: 0; }

  .mood-idle   { --bob: 1.6s; }
  .mood-idle .legA, .mood-idle .legB, .mood-idle .armL, .mood-idle .armR { animation: none; }

  .mood-hustle { --bob: 0.4s; --walk: 0.2s; --swing: 0.4s; }
  .mood-panic  { --bob: 0.2s; --walk: 0.1s; --swing: 0.2s; }
  .mood-panic .shake { animation: cc-shake 0.3s steps(1) infinite; }
  .mood-hustle .sweat { animation: cc-sweat 1.2s steps(4) infinite; }
  .mood-panic  .sweat { animation: cc-sweat 0.6s steps(4) infinite; }

  .mood-sleep  { --bob: 2.4s; }
  .mood-sleep .legA, .mood-sleep .legB, .mood-sleep .armL, .mood-sleep .armR { animation: none; }
  .mood-sleep .eyes { animation: none; transform: scaleY(0.1); }
  .mood-sleep .z  { animation: cc-zzz 2.4s steps(6) infinite; }
  .mood-sleep .z2 { animation-delay: 0.8s; }
  .mood-sleep .z3 { animation-delay: 1.6s; }

  @keyframes cc-bob   { 0% { transform: translateY(0) }  50% { transform: translateY(-1px) } }
  @keyframes cc-up    { 0% { transform: translateY(0) }  50% { transform: translateY(-1px) } }
  @keyframes cc-upB   { 0% { transform: translateY(-1px) } 50% { transform: translateY(0) } }
  @keyframes cc-down  { 0% { transform: translateY(0) }  50% { transform: translateY(1px) } }
  @keyframes cc-downB { 0% { transform: translateY(1px) } 50% { transform: translateY(0) } }
  @keyframes cc-blink { 0%, 94% { transform: scaleY(1) } 95%, 98% { transform: scaleY(0.1) } }
  @keyframes cc-shake { 0% { transform: translateX(0) } 25% { transform: translateX(-1px) }
                        50% { transform: translateX(0) } 75% { transform: translateX(1px) } }
  @keyframes cc-sweat { 0% { opacity: 1; transform: translateY(0) }
                        100% { opacity: 0; transform: translateY(4px) } }
  @keyframes cc-zzz   { 0% { opacity: 0; transform: translate(0, 0) }
                        20% { opacity: 1 }
                        100% { opacity: 0; transform: translate(2px, -4px) } }

  @media (prefers-reduced-motion: reduce) {
    .cc-bot * { animation: none !important; }
  }
`

function moodFor(pct) {
  if (pct >= 100) return { name: "sleep",  label: "limit hit · resting", color: "#EF4444" }
  if (pct >= 90)  return { name: "panic",  label: "panicking",  color: "#EF4444" }
  if (pct >= 75)  return { name: "hustle", label: "hustling",   color: "#F59E0B" }
  if (pct >= 25)  return { name: "work",   label: "working",    color: "#C8C9CA" }
  return                 { name: "idle",   label: "idle",       color: "#4A5568" }
}

function Robot({ mood }) {
  mood = mood || moodFor(0)
  var c = "#E07050"   // body colour
  var d = "#1C1E21"   // dark (eyes, mouth)
  var s = { imageRendering: "pixelated", display: "block", margin: "0 auto 8px", shapeRendering: "crispEdges" }
  return (
    <svg className={"cc-bot mood-" + mood.name} width="144" height="108" viewBox="-1 -2 16 12" style={s}>
      <style>{robotCss}</style>
      {/* effects — only visible in hustle/panic (sweat) and sleep (z's) */}
      <rect className="sweat" x="12" y="1" width="1" height="1" fill="#7DD3FC" />
      <rect className="z"    x="13" y="1" width="1" height="1" fill="#C8C9CA" />
      <rect className="z z2" x="13" y="1" width="1" height="1" fill="#C8C9CA" />
      <rect className="z z3" x="13" y="1" width="1" height="1" fill="#C8C9CA" />
      <g className="shake">
      <g className="bob">
        {/* head */}
        <rect x="3"  y="1"  width="8" height="6" fill={c} />
        {/* eyes */}
        <g className="eyes">
          <rect x="4"  y="2"  width="1"  height="1" fill={d} />
          <rect x="9"  y="2"  width="1"  height="1" fill={d} />
        </g>
        {/* mouth / expression line */}
        <rect x="5"  y="7"  width="6"  height="1" fill={d} />
        {/* arms */}
        <rect className="armL" x="1"  y="3"  width="2"  height="2" fill={c} />
        <rect className="armR" x="11" y="3"  width="2"  height="2" fill={c} />
        {/* legs — alternating pairs lift (tucking under the head) to walk in place */}
        <g className="legA">
          <rect x="3"  y="7" width="1"  height="2" fill={c} />
          <rect x="8"  y="7" width="1"  height="2" fill={c} />
        </g>
        <g className="legB">
          <rect x="5"  y="7" width="1"  height="2" fill={c} />
          <rect x="10" y="7" width="1"  height="2" fill={c} />
        </g>
      </g>
      </g>
    </svg>
  )
}

// ASCII block progress bar
function Bar({ pct }) {
  var total  = 22
  var filled = Math.round((Math.min(pct || 0, 100) / 100) * total)
  var empty  = total - filled
  var color  = (pct >= 90) ? "#EF4444" : (pct >= 75) ? "#F59E0B" : "#3B82F6"
  var blocks = ""
  var voids  = ""
  for (var i = 0; i < filled; i++) blocks += "█"
  for (var j = 0; j < empty;  j++) voids  += "░"
  return (
    <span style={{ letterSpacing: "0px" }}>
      <span style={{ color: color }}>{blocks}</span>
      <span style={{ color: "#2A2D35" }}>{voids}</span>
    </span>
  )
}

function UsageRow({ label, pct, sub, extraRight }) {
  return (
    <div style={{ marginBottom: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "5px" }}>
        <span style={{ color: "#E8714A", fontWeight: "bold", fontSize: "10px", letterSpacing: "1px" }}>
          {label}
        </span>
        {extraRight}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <Bar pct={pct} />
        <span style={{ color: "#C8C9CA", fontSize: "10px", minWidth: "52px" }}>
          {pct || 0}% used
        </span>
      </div>
      <div style={{ color: "#4A5568", marginTop: "4px", fontSize: "10px" }}>{sub}</div>
    </div>
  )
}

export function render({ output }) {
  var d = {}
  try { d = JSON.parse(output || "{}") } catch (e) { d = {} }

  var session = d.session || { percent: 0, resets_in: "\u2014" }
  var weekly  = d.weekly  || { percent: 0, resets_in: "\u2014" }
  var fable   = d.fable   || { percent: 0, resets_in: "\u2014", available: false }
  var extra   = d.extra   || { percent: 0, spent: 0, limit: 20, resets: "\u2014", enabled: false }
  var plan    = d.plan    || "\u2014"
  var mood    = moodFor(session.percent || 0)
  var spent   = parseFloat(extra.spent || 0).toFixed(2)
  var limit   = parseFloat(extra.limit || 20).toFixed(0)

  var ago = "no data \u00b7 run fetch_usage.py"
  if (d.updated) {
    try {
      var diff = (Date.now() - new Date(d.updated).getTime()) / 1000
      if (diff < 60)   ago = "just now"
      else if (diff < 3600) ago = Math.floor(diff / 60) + "m ago"
      else ago = Math.floor(diff / 3600) + "h ago"
    } catch (e) { ago = "\u2014" }
  }

  var extraLabel = (
    <span style={{ color: extra.enabled ? "#10B981" : "#4A5568", fontSize: "9px" }}>
      {extra.enabled ? "\u25cf ON" : "\u25cb OFF"}
    </span>
  )

  return (
    <div style={{
      background: "#1C1E21",
      border: "1px solid #E8714A",
      borderRadius: "4px",
      width: "620px",
      overflow: "hidden",
    }}>

      {/* title bar */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "7px 14px",
        borderBottom: "1px solid #E8714A",
        background: "#17191C",
      }}>
        <span style={{ color: "#E8714A", fontWeight: "bold", fontSize: "11px" }}>Claude Code</span>
        <span style={{ color: "#4A5568", fontSize: "10px" }}>usage monitor</span>
        <div style={{ flex: 1, height: "1px", background: "#E8714A", opacity: "0.35" }} />
        <span style={{ color: "#4A5568", fontSize: "10px" }}>{plan}</span>
      </div>

      {/* body: two columns */}
      <div style={{ display: "flex" }}>

        {/* left: robot + info */}
        <div style={{
          width: "175px",
          flexShrink: "0",
          padding: "20px 14px",
          borderRight: "1px solid #252830",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        }}>
          <Robot mood={mood} />
          <div style={{ color: mood.color, fontSize: "9px", letterSpacing: "1px" }}>
            {mood.label}
          </div>
          {SIGNATURE && (
            <div style={{
              color: "#E8714A",
              fontSize: "11px",
              fontWeight: "bold",
              letterSpacing: "1px",
              marginTop: "12px",
              paddingTop: "8px",
              borderTop: "1px solid #252830",
              alignSelf: "stretch",
            }}>
              <span style={{ color: "#4A5568", fontWeight: "normal" }}>by </span>{SIGNATURE}
            </div>
          )}
        </div>

        {/* right: usage bars */}
        <div style={{ flex: 1, padding: "18px 18px 4px 18px" }}>
          <UsageRow
            label="SESSION"
            pct={session.percent}
            sub={"Resets in " + session.resets_in}
          />
          <UsageRow
            label="WEEKLY"
            pct={weekly.percent}
            sub={"Resets in " + weekly.resets_in}
          />
          {fable.available && (
            <UsageRow
              label="FABLE"
              pct={fable.percent}
              sub={"Weekly · Resets in " + fable.resets_in}
            />
          )}
          <UsageRow
            label="EXTRA USAGE"
            pct={extra.percent}
            sub={"$" + spent + " of $" + limit + " monthly \u00b7 Resets " + extra.resets}
            extraRight={extraLabel}
          />
        </div>
      </div>

      {/* footer */}
      <div style={{
        padding: "5px 14px",
        borderTop: "1px solid #252830",
        color: "#303540",
        fontSize: "9px",
        display: "flex",
        justifyContent: "space-between",
      }}>
        <span>{"\u21bb updated " + ago}</span>
      </div>
    </div>
  )
}
