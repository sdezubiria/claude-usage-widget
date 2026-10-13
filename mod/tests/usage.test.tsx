import { expect, test } from 'claude-code/testing'

const DATA = {
  plan: 'Max',
  session: { percent: 92, resets_in: '2h 41m' },
  weekly: { percent: 6, resets_in: '8h 41m' },
  fable: { percent: 0, resets_in: '8h 41m', available: true },
  extra: { enabled: true, spent: 3.5, percent: 29, limit: 12, resets: '1st of month' },
}

test('draws every limit from usage_data.json on each surface', async ($, on) => {
  const reads: string[] = []
  on('fs.read', ($, e) => {
    reads.push(e.path)
    if (e.path.endsWith('known_marketplaces.json')) {
      return { value: JSON.stringify({ mine: { source: { source: 'directory', path: '/clone' } } }) }
    }
    return { value: JSON.stringify(DATA) }
  })
  on('fs.stat', () => ({ value: { kind: 'file', size: 1, mtimeMs: 0, isLink: false } }))
  on('env.get', () => ({ value: '/Users/someone' }))
  on('fs.exists', ($, e) => ({ value: e.path === '/clone/usage_data.json' }))
  on('clock.now', () => ({ value: 120_000 }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  const statuses: (string | undefined)[] = []
  on('ui.status', ($, e) => {
    statuses.push(e.text)
    return { value: undefined }
  })
  await $.command.run({ command: 'usage-pane', args: '' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({
      plugin: 'usage-meter',
      surface,
      component: 'Pane',
      requestId: 'usage-meter',
      props: { title: 'Usage', isFocused: false, bodyColumns: 40, placement: 'dock' } as never,
    })
    for (const label of ['SESSION', 'WEEKLY', 'FABLE', 'EXTRA USAGE']) {
      expect(await ui.find({ type: 'Text', text: label })).toBeDefined()
    }
    expect(await ui.find({ type: 'Text', text: /\$3\.50 of \$12 monthly/ })).toBeDefined()
    await ui.unmount()
  }
  expect(reads).toContain('/clone/usage_data.json')
  expect(statuses.at(-1)).toBe('Session 92% · Weekly 6% · Fable 0% · Extra $3.50/$12')
})
