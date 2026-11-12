const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// FastAPI hata gövdesi: {"detail": "metin"} ya da {"detail": {"problems": [...]}}
function messageFrom(detail) {
  if (typeof detail === 'string') return detail
  if (detail?.problems) return detail.problems.join(' · ')
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(' · ')
  return 'Beklenmeyen hata'
}

async function request(path, options) {
  let res
  try {
    res = await fetch(BASE + path, options)
  } catch {
    throw new ApiError('Sunucuya ulaşılamıyor', 0)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(messageFrom(body.detail), res.status)
  }
  return res.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  getProject: () => request('/project').catch((e) => (e.status === 404 ? null : Promise.reject(e))),
  uploadProject(file) {
    const form = new FormData()
    form.append('file', file)
    return request('/project', { method: 'POST', body: form })
  },
  listCards: () => request('/cards'),
  approve: (id, edit) => request(`/cards/${id}/approve`, json('POST', edit)),
  reject: (id) => request(`/cards/${id}/reject`, json('POST')),
  loadDemo: () => request('/demo/emails', json('POST')),
}
