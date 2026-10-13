export type Limit = { percent: number; resets_in: string; available?: boolean }

export type Extra = {
  enabled: boolean
  spent: number
  percent: number
  limit: number
  resets: string
}

export type Usage = {
  plan?: string
  session?: Limit
  weekly?: Limit
  fable?: Limit
  extra?: Extra
}

// What the pane draws: the file's contents, when it was written, and when it was last read.
export type Snapshot = { data: Usage; updatedMs: number; checkedMs: number }

declare module 'claude-code' {
  interface PluginState {
    'usage-meter': { snapshot: Snapshot | null; problem: string | null }
  }
}
