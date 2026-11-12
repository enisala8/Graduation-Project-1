import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import CardItem from './components/CardItem'
import ProjectBar from './components/ProjectBar'

const TABS = [
  { id: 'pending', label: 'Bekleyen', match: (c) => c.status === 'PENDING' || c.status === 'PROCESSING' },
  { id: 'done', label: 'Karara bağlanan', match: (c) => c.status === 'APPROVED' || c.status === 'REJECTED' },
  { id: 'info', label: 'Aksiyon gerekmeyen', match: (c) => c.status === 'NO_ACTION' },
  { id: 'failed', label: 'Hatalı', match: (c) => c.status === 'FAILED' },
]

function setTheme(dark) {
  document.documentElement.classList.toggle('dark', dark)
  try {
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  } catch {
    /* depolama kapalı olabilir */
  }
}

export default function App() {
  const [cards, setCards] = useState([])
  const [project, setProject] = useState(undefined) // undefined: yükleniyor, null: yok
  const [offline, setOffline] = useState(false)
  const [tab, setTab] = useState('pending')
  const [busy, setBusy] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [notice, setNotice] = useState('')
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))

  const refresh = useCallback(async () => {
    try {
      const [list, proj] = await Promise.all([api.listCards(), api.getProject()])
      setCards(list)
      setProject(proj)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Analiz sürerken sık, değilken seyrek yokla.
  const processing = cards.some((c) => c.status === 'PROCESSING')
  useEffect(() => {
    const id = setInterval(refresh, processing ? 3000 : 15000)
    return () => clearInterval(id)
  }, [refresh, processing])

  const tasksById = useMemo(() => Object.fromEntries((project?.tasks ?? []).map((t) => [t.id, t])), [project])
  const replaceCard = (card) => setCards((cs) => cs.map((c) => (c.id === card.id ? card : c)))

  async function upload(file) {
    setBusy(true)
    setUploadError('')
    try {
      setProject(await api.uploadProject(file))
    } catch (e) {
      setUploadError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function loadDemo() {
    setBusy(true)
    try {
      const r = await api.loadDemo()
      setNotice(r.queued ? `${r.queued} mail analize alındı` : 'Demo mailler zaten yüklü')
      setTab('pending')
      await refresh()
    } catch (e) {
      setNotice(e.message)
    } finally {
      setBusy(false)
    }
  }

  const counts = Object.fromEntries(TABS.map((t) => [t.id, cards.filter(t.match).length]))
  const visible = cards.filter(TABS.find((t) => t.id === tab).match)
  const highRisk = cards.filter((c) => c.status === 'PENDING' && c.result?.analysis?.risk === 'HIGH').length

  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 transition-colors dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <header className="mb-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="size-9 rounded-lg" />
            <div>
              <h1 className="text-xl font-bold tracking-tight">Chronos Agent</h1>
              <p className="text-sm text-zinc-500">Ajan önerir, sen karar verirsin</p>
            </div>
          </div>
          <button
            onClick={() => {
              setTheme(!dark)
              setDark(!dark)
            }}
            aria-label={dark ? 'Açık temaya geç' : 'Koyu temaya geç'}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {dark ? '☀ Açık' : '☾ Koyu'}
          </button>
        </header>

        {offline && (
          <p role="alert" className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
            Sunucuya ulaşılamıyor. Backend çalışıyor mu? (<code>uv run uvicorn app.main:app</code>)
          </p>
        )}

        {project !== undefined && (
          <ProjectBar project={project} uploadError={uploadError} busy={busy} onUpload={upload} onDemo={loadDemo} />
        )}
        {notice && (
          <p role="status" className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            {notice}
          </p>
        )}

        {project && (
          <>
            <dl className="mt-6 grid grid-cols-3 gap-3 text-center">
              {[
                ['Bekleyen karar', counts.pending, 'text-indigo-600 dark:text-indigo-400'],
                ['Yüksek risk', highRisk, highRisk ? 'text-red-600 dark:text-red-400' : 'text-zinc-400'],
                ['Karara bağlanan', counts.done, 'text-emerald-600 dark:text-emerald-400'],
              ].map(([label, n, color]) => (
                <div key={label} className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
                  <dd className={`text-3xl font-bold tabular-nums ${color}`}>{n}</dd>
                  <dt className="mt-1 text-xs text-zinc-500">{label}</dt>
                </div>
              ))}
            </dl>

            <nav className="mt-6 flex gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-800" aria-label="Kart filtreleri">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  aria-current={tab === t.id ? 'page' : undefined}
                  className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition ${
                    tab === t.id
                      ? 'border-indigo-600 text-indigo-700 dark:border-indigo-400 dark:text-indigo-300'
                      : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                  }`}
                >
                  {t.label} <span className="ml-1 text-xs tabular-nums opacity-70">{counts[t.id]}</span>
                </button>
              ))}
            </nav>

            <main className="mt-5 space-y-4">
              {visible.length === 0 && (
                <p className="rounded-2xl border border-dashed border-zinc-300 p-10 text-center text-sm text-zinc-500 dark:border-zinc-700">
                  {cards.length === 0 ? 'Henüz mail yok. "Demo mailleri yükle" ile başlayabilirsin.' : 'Bu sekmede kart yok.'}
                </p>
              )}
              {visible.map((card, i) => (
                <CardItem
                  key={`${card.id}-${card.status}`}
                  card={card}
                  index={i}
                  task={tasksById[card.result?.analysis?.related_task_id]}
                  onApprove={async (id, edit) => replaceCard(await api.approve(id, edit))}
                  onReject={async (id) => replaceCard(await api.reject(id))}
                />
              ))}
            </main>
          </>
        )}
      </div>
    </div>
  )
}
