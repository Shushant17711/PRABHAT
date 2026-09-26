const BASE = ''

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${path}`)
  return r.json()
}

export const api = {
  cases: () => get('/v1/cases'),
  userClasses: () => get('/v1/user-classes'),
  status: () => get('/v1/status'),
  tubes: (caseId) => get(`/v1/tubes?case=${encodeURIComponent(caseId)}`),
  gate: (tubeId) => get(`/v1/tubes/${encodeURIComponent(tubeId)}/gate`),
  analogues: (tubeId) => get(`/v1/tubes/${encodeURIComponent(tubeId)}/analogues`),
  exceedance: (tubeId) => get(`/v1/tubes/${encodeURIComponent(tubeId)}/exceedance`),
  efi: (tubeId) => get(`/v1/tubes/${encodeURIComponent(tubeId)}/efi`),
  alerts: (caseId, userClass) => {
    const q = new URLSearchParams({ case: caseId })
    if (userClass) q.set('user_class', userClass)
    return get(`/v1/alerts?${q}`)
  },
  ledger: () => get('/v1/ledger/summary'),
  churn: (caseId) => get(`/v1/churn?case=${encodeURIComponent(caseId)}`),
  capUrl: (alertId) => `${BASE}/v1/cap/${encodeURIComponent(alertId)}.xml`,
}

/* Categorical identity per user class — fixed order, never cycled.
   Validated against this page's light surface (#faf9f6); see styles.css. */
export const SERIES = {
  farmer_smallholder: 'var(--series-1)',
  district_dm: 'var(--series-2)',
  logistics_operator: 'var(--series-3)',
}

/* Reserved status colours for the gate verdict. Icon + label always present,
   so the colour never carries the meaning by itself. */
export const VERDICT = {
  PASS: { color: 'var(--good)', icon: '✓', label: 'published at 5 km' },
  DEGRADE: { color: 'var(--warning)', icon: '▲', label: 'coarse only, low confidence' },
  SUPPRESS: { color: 'var(--critical)', icon: '✕', label: 'nothing published at 5 km' },
}

/* Diverging ramp for the Extreme Forecast Index, which runs -1..+1.
   Two hues with a NEUTRAL GREY MIDPOINT, not a rainbow and not a single hue:
   EFI encodes polarity (unusually cold vs unusually hot), and the midpoint
   must read as "nothing unusual". Blue<->red rather than blue<->aqua, because
   two cool hues do not read as opposites. On the light surface the poles run
   dark-saturated -> pale -> dark-saturated so the extremes still pop off
   white; the midpoint is a warm grey, not a light one, so it doesn't just
   vanish into the paper. */
export const EFI_RAMP = [
  '#0d366b', '#2a78d6', '#9ec5f4', '#c9c1b0', '#f5a545', '#c25a1e', '#8f3d17',
]

/* Sequential ramp for exceedance probability: one hue, monotonic lightness,
   light -> dark so a low reading recedes into the paper and a high one reads
   as solid, saturated ink. */
const RAMP = ['#fde8d2', '#fbc994', '#f5a545', '#e07b2a', '#c25a1e', '#8f3d17']

export function probColor(p) {
  if (p <= 0.02) return null
  const i = Math.min(RAMP.length - 1, Math.floor(p * RAMP.length))
  return RAMP[i]
}
export { RAMP }
