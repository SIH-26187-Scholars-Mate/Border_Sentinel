export function cameraCode(cameraOrNumber) {
  const number = typeof cameraOrNumber === 'object' ? cameraOrNumber?.camera_number : cameraOrNumber
  return `CAM-${String(Number(number) || 0).padStart(3, '0')}`
}

export function formatAlertType(value = '') {
  return String(value).replace(/_/g, ' ')
}

export function severityClass(severity = 'low') {
  return {
    low: 'border-slate-700 bg-slate-800 text-slate-300',
    medium: 'border-amber-900/70 bg-amber-950/50 text-amber-300',
    high: 'border-orange-900/70 bg-orange-950/50 text-orange-300',
    critical: 'border-red-900/70 bg-red-950/50 text-red-300',
  }[severity] || 'border-slate-700 bg-slate-800 text-slate-300'
}
