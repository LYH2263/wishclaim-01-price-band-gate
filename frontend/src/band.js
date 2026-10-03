// 价位带枚举文案的唯一来源。
// 后端只落枚举码（OVER_SOFT_CAP / HARD_CAP_EXCEEDED …），
// 墙卡角标、详情 band、规则页写入带三处一律经这里翻译，禁止各自写自由文本。

export const WARNING_TEXT = {
  OVER_SOFT_CAP: '估价超出软上限 · 已落库提醒',
}

export const ERROR_TEXT = {
  HARD_CAP_EXCEEDED: '估价超出硬上限，整单未发布',
  INVALID_PRICE: '估价必须是大于 0 的数字',
  INVALID_BAND_MODE: '门禁模式不合法（仅 soft/hard）',
  DIRTY_WISH: '标题不能为空',
}

export const MODE_TEXT = { soft: '软门禁', hard: '硬门禁' }

export function warningText(code) {
  if (!code) return ''
  return WARNING_TEXT[code] || code
}

export function errorText(codeOrMessage) {
  return ERROR_TEXT[codeOrMessage] || codeOrMessage
}

export function modeText(mode) {
  return MODE_TEXT[mode] || mode || '—'
}

// 三路共用的带描述：无快照（未填估价）返回 null
export function describeBand(band) {
  if (!band) return null
  return {
    price: band.price,
    mode: band.mode,
    modeLabel: modeText(band.mode),
    cap: band.cap,
    over: band.verdict === 'warn',
    warning: band.warning,
    warningLabel: warningText(band.warning),
  }
}
