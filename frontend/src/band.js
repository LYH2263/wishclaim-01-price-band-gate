// Shared band projection for wall badge / detail / rules page.
// Warnings are persisted as enum codes; this map is the single place that
// turns them into human text, so all three surfaces stay identical.

export const SOFT = 'soft'
export const HARD = 'hard'

const WARNING_TEXT = {
  PRICE_OVER_SOFT_CAP: '估价超过软上限：仍已写入，并标记提醒',
  PRICE_OVER_HARD_CAP: '估价超过硬上限：整单拒绝，未写入',
}

export function warningText(code) {
  return WARNING_TEXT[code] || code
}

export function modeText(mode) {
  if (mode === HARD) return '硬门禁'
  if (mode === SOFT) return '软门禁'
  return '—'
}

export function formatPrice(v) {
  return v == null ? '—' : '¥' + Number(v)
}
