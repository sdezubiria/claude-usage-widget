import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Limit, Snapshot, Usage } from '../types'

// Same data and thresholds as the Übersicht widget: reads usage_data.json,
// which fetch_usage.py (launchd) rewrites every 5 minutes. No network here.

const PANE = 'usage-meter'
const REFRESH_MS = 60_000

const snapshot = atom({ plugin: 'usage-meter', key: 'snapshot' } as const, null)
const problem = atom({ plugin: 'usage-meter', key: 'problem' } as const, null)

type Mood = { name: 'idle' | 'work' | 'hustle' | 'panic' | 'sleep'; label: string }

function moodFor(pct: number): Mood {
  if (pct >= 100) return { name: 'sleep', label: 'limit hit · resting' }
  if (pct >= 90) return { name: 'panic', label: 'panicking' }
  if (pct >= 75) return { name: 'hustle', label: 'hustling' }
  if (pct >= 25) return { name: 'work', label: 'working' }
  return { name: 'idle', label: 'idle' }
}

function barColor(pct: number) {
  if (pct >= 90) return 'error'
  if (pct >= 75) return 'warning'
  return 'suggestion'
}

function ago(ms: number) {
  const s = ms / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function statusLine(d: Usage) {
  const parts = [`Session ${d.session?.percent ?? 0}%`, `Weekly ${d.weekly?.percent ?? 0}%`]
  if (d.fable?.available) parts.push(`Fable ${d.fable.percent}%`)
  if (d.extra?.enabled) parts.push(`Extra $${d.extra.spent.toFixed(2)}/$${d.extra.limit.toFixed(0)}`)
  return parts.join(' · ')
}

// The widget's pixel mascot, as an SVG string. CSS animations need isInteractive.
function robotSvg(mood: Mood) {
  const c = '#E07050'
  const d = '#1C1E21'
  const r = (x: number, y: number, w: number, h: number, fill: string, cls = '') =>
    `<rect${cls ? ` class="${cls}"` : ''} x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}"/>`
  const css = `
    .b{overflow:visible;--bob:.8s;--walk:.4s;--swing:.8s}
    .b .bob{animation:bob var(--bob) steps(1) infinite}
    .b .legA{animation:up var(--walk) steps(1) infinite}
    .b .legB{animation:upB var(--walk) steps(1) infinite}
    .b .armL{animation:down var(--swing) steps(1) infinite}
    .b .armR{animation:downB var(--swing) steps(1) infinite}
    .b .eyes{animation:blink 4s steps(1) infinite;transform-box:fill-box;transform-origin:center}
    .b .sweat,.b .z{opacity:0}
    .idle{--bob:1.6s}
    .idle .legA,.idle .legB,.idle .armL,.idle .armR{animation:none}
    .hustle{--bob:.4s;--walk:.2s;--swing:.4s}
    .panic{--bob:.2s;--walk:.1s;--swing:.2s}
    .panic .shake{animation:shake .3s steps(1) infinite}
    .hustle .sweat{animation:sweat 1.2s steps(4) infinite}
    .panic .sweat{animation:sweat .6s steps(4) infinite}
    .sleep{--bob:2.4s}
    .sleep .legA,.sleep .legB,.sleep .armL,.sleep .armR{animation:none}
    .sleep .eyes{animation:none;transform:scaleY(.1)}
    .sleep .z{animation:zzz 2.4s steps(6) infinite}
    .sleep .z2{animation-delay:.8s}.sleep .z3{animation-delay:1.6s}
    @keyframes bob{0%{transform:translateY(0)}50%{transform:translateY(-1px)}}
    @keyframes up{0%{transform:translateY(0)}50%{transform:translateY(-1px)}}
    @keyframes upB{0%{transform:translateY(-1px)}50%{transform:translateY(0)}}
    @keyframes down{0%{transform:translateY(0)}50%{transform:translateY(1px)}}
    @keyframes downB{0%{transform:translateY(1px)}50%{transform:translateY(0)}}
    @keyframes blink{0%,94%{transform:scaleY(1)}95%,98%{transform:scaleY(.1)}}
    @keyframes shake{0%{transform:translateX(0)}25%{transform:translateX(-1px)}50%{transform:translateX(0)}75%{transform:translateX(1px)}}
    @keyframes sweat{0%{opacity:1;transform:translateY(0)}100%{opacity:0;transform:translateY(4px)}}
    @keyframes zzz{0%{opacity:0;transform:translate(0,0)}20%{opacity:1}100%{opacity:0;transform:translate(2px,-4px)}}
    @media (prefers-reduced-motion:reduce){.b *{animation:none!important}}`
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" class="b ${mood.name}" width="96" height="72" viewBox="-1 -2 16 12" shape-rendering="crispEdges">` +
    `<style>${css}</style>` +
    r(12, 1, 1, 1, '#7DD3FC', 'sweat') +
    r(13, 1, 1, 1, '#C8C9CA', 'z') +
    r(13, 1, 1, 1, '#C8C9CA', 'z z2') +
    r(13, 1, 1, 1, '#C8C9CA', 'z z3') +
    `<g class="shake"><g class="bob">` +
    r(3, 1, 8, 6, c) +
    `<g class="eyes">${r(4, 2, 1, 1, d)}${r(9, 2, 1, 1, d)}</g>` +
    r(1, 3, 2, 2, c, 'armL') +
    r(11, 3, 2, 2, c, 'armR') +
    `<g class="legA">${r(3, 7, 1, 2, c)}${r(8, 7, 1, 2, c)}</g>` +
    `<g class="legB">${r(5, 7, 1, 2, c)}${r(10, 7, 1, 2, c)}</g>` +
    `</g></g></svg>`
  )
}

// Folders added with `claude plugin marketplace add <folder>`: installing from a
// clone makes the clone one, and the session may run a cache copy of the mod.
async function marketplaceFolders($: EngineInterface, home: string) {
  try {
    const known = JSON.parse(await $.fs.read(`${home}/.claude/plugins/known_marketplaces.json`)) as Record<
      string,
      { source?: { source?: string; path?: string } }
    >
    return Object.values(known)
      .filter(m => m.source?.source === 'directory' && m.source.path)
      .map(m => m.source!.path!)
  } catch {
    return []
  }
}

// The setting when given. Otherwise the repo this mod ships in: beside the mod
// when it runs from the clone, else the clone it was installed from; then the
// README's default clone location.
async function findDataFile($: EngineInterface, configured: string) {
  if (configured) return configured
  const home = await $.env.get('HOME')
  const candidates = [`${$.plugin.root}/../usage_data.json`]
  if (home) {
    for (const folder of await marketplaceFolders($, home)) candidates.push(`${folder}/usage_data.json`)
    candidates.push(`${home}/claude-usage-widget/usage_data.json`)
  }
  for (const path of candidates) {
    if (await $.fs.exists(path)) return path
  }
  return candidates[candidates.length - 1] ?? candidates[0]!
}

// Reads the file into state and pins the one-line summary under the prompt;
// answers what went wrong, or null.
async function refresh($: EngineInterface, configured: string): Promise<string | null> {
  const dataFile = await findDataFile($, configured)
  try {
    const [text, stat, now] = await Promise.all([
      $.fs.read(dataFile),
      $.fs.stat(dataFile),
      $.clock.now(),
    ])
    const data = JSON.parse(text) as Usage
    await update($, snapshot, () => ({ data, updatedMs: stat.mtimeMs, checkedMs: now }))
    await update($, problem, () => null)
    $.ui.status(statusLine(data))
    return null
  } catch {
    await update($, problem, () => `Can't read ${dataFile}. Set its path with /plugin configure usage-meter@usage-widget.`)
    $.ui.status(undefined)
    return `Can't read ${dataFile}`
  }
}

export const register: Register = (on, options) => {
  const dataFile = String(options.dataFile ?? '')

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'usage-pane',
      description: 'Show your claude.ai plan limits (session, weekly, Fable, extra usage)',
    })
    await refresh($, dataFile)
    $.clock.every(REFRESH_MS, () => void refresh($, dataFile))
    void $.ui.open({ id: PANE, title: 'Usage' })

    return next(e)
  })

  on('command.run', { command: 'usage-pane' }, async $ => {
    const failed = await refresh($, dataFile)
    await $.ui.open({ id: PANE, title: 'Usage' })

    return { text: failed ?? 'Usage pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const { Box, Text } = els
    const snap = await read($, snapshot)
    const err = await read($, problem)

    if (snap === null) {
      return (
        <Box flexDirection="column">
          <Text color="error">{err ?? 'Loading…'}</Text>
          <Text dimColor>Run fetch_usage.py --setup in the widget repo.</Text>
        </Box>
      )
    }

    const d = snap.data
    const session = d.session ?? { percent: 0, resets_in: '—' }
    const weekly = d.weekly ?? { percent: 0, resets_in: '—' }
    const extra = d.extra
    const mood = moodFor(session.percent)
    const cols = Math.max(12, e.props.bodyColumns)
    const barWidth = Math.max(6, Math.min(30, cols - 11))

    const Row = (label: string, limit: Limit, sub: string, right?: JSX.Element) => {
      const pct = Math.min(Math.max(limit.percent || 0, 0), 100)
      const filled = Math.round((pct / 100) * barWidth)
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Box justifyContent="space-between">
            <Text color="claude" bold>{label}</Text>
            {right ?? <Text> </Text>}
          </Box>
          <Text>
            <Text color={barColor(pct)}>{'█'.repeat(filled)}</Text>
            <Text color="subtle">{'░'.repeat(barWidth - filled)}</Text>
            <Text> {String(limit.percent || 0).padStart(3)}%</Text>
          </Text>
          <Text dimColor wrap="truncate-end">{sub}</Text>
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        <Box justifyContent="space-between" marginBottom={1}>
          <Text color="claude" bold>Claude usage</Text>
          <Text dimColor>{d.plan ?? '—'}</Text>
        </Box>
        {e.surface !== 'terminal' && 'Svg' in els && (
          <Box flexDirection="column" alignItems="center" marginBottom={1}>
            <els.Svg source={robotSvg(mood)} alt={`Mascot: ${mood.label}`} width={96} height={72} isInteractive />
            <Text dimColor>{mood.label}</Text>
          </Box>
        )}
        {Row('SESSION', session, `Resets in ${session.resets_in}`)}
        {Row('WEEKLY', weekly, `Resets in ${weekly.resets_in}`)}
        {d.fable?.available && Row('FABLE', d.fable, `Weekly · Resets in ${d.fable.resets_in}`)}
        {extra &&
          Row(
            'EXTRA USAGE',
            { percent: extra.percent, resets_in: extra.resets },
            `$${extra.spent.toFixed(2)} of $${extra.limit.toFixed(0)} monthly · Resets ${extra.resets}`,
            <Text color={extra.enabled ? 'success' : 'subtle'}>{extra.enabled ? '● ON' : '○ OFF'}</Text>,
          )}
        <Text dimColor>
          ↻ updated {ago(snap.checkedMs - snap.updatedMs)}
          {err ? ` · ${err}` : ''}
        </Text>
      </Box>
    )
  })
}
