import { useState } from 'react'
import { ACTION, CATEGORY, RISK, STATUS, fmtDate, fmtDateTime } from '../labels'
import Badge from './Badge'

const inputCls =
  'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100'

const splitAddresses = (text) => text.split(/[,;\s]+/).filter(Boolean)

function Skeleton() {
  return (
    <div className="mt-4 space-y-3" role="status" aria-label="Analiz ediliyor">
      <div className="shimmer h-4 w-3/4 rounded bg-zinc-200/60 dark:bg-zinc-800" />
      <div className="shimmer h-4 w-1/2 rounded bg-zinc-200/60 dark:bg-zinc-800" />
      <p className="text-sm text-zinc-500">Ajan maili proje planıyla karşılaştırıyor…</p>
    </div>
  )
}

function Impact({ impact, delayDays }) {
  const late = impact.project_end_delay_days
  return (
    <section className="mt-4 rounded-xl bg-zinc-50 p-4 dark:bg-zinc-950/60">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Zincirleme etki ({delayDays} gün gecikme)
        </h4>
        <Badge cls={late > 0 ? RISK.HIGH.cls : RISK.LOW.cls}>
          {late > 0 ? `Proje bitişi +${late} gün` : 'Proje bitişi etkilenmiyor'}
        </Badge>
      </div>
      {impact.affected.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Plandaki boşluk gecikmeyi emiyor; bağımlı görevler kaymıyor.</p>
      ) : (
        <ul className="mt-2 space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
          {impact.affected.map((t) => (
            <li key={t.task_id} className="flex flex-wrap justify-between gap-x-3">
              <span>
                <span className="font-mono text-xs text-zinc-500">#{t.task_id}</span> {t.name}
              </span>
              <span className="tabular-nums text-zinc-500">
                +{t.days_late} gün · yeni bitiş {fmtDate(t.new_end)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function CardItem({ card, task, onApprove, onReject, index }) {
  const { email, result, draft, status } = card
  const a = result?.analysis
  const pending = status === 'PENDING'

  const [to, setTo] = useState(draft?.to.join(', ') ?? '')
  const [subject, setSubject] = useState(draft?.subject ?? '')
  const [body, setBody] = useState(draft?.body ?? '')
  const [busy, setBusy] = useState(null) // 'approve' | 'reject' | null
  const [error, setError] = useState('')

  const isMeeting = draft?.action_type === 'SCHEDULE_MEETING'
  const warnings = [...(draft?.warnings ?? []), ...(result?.warnings ?? [])]

  async function run(kind, fn) {
    setBusy(kind)
    setError('')
    try {
      await fn()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  function approve() {
    const recipients = splitAddresses(to)
    const edit = {}
    if (recipients.join() !== draft.to.join()) edit.to = recipients
    if (subject !== draft.subject) edit.subject = subject
    if (body !== draft.body) edit.body = body
    return run('approve', () => onApprove(card.id, Object.keys(edit).length ? edit : undefined))
  }

  return (
    <article
      className="animate-rise rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {a && <Badge cls={CATEGORY[a.category].cls}>{CATEGORY[a.category].label}</Badge>}
          {a && <Badge cls={RISK[a.risk].cls}>{RISK[a.risk].label}</Badge>}
          {STATUS[status] && <Badge cls={STATUS[status].cls}>{STATUS[status].label}</Badge>}
          {status === 'PROCESSING' && <Badge cls="bg-indigo-500/10 text-indigo-700 ring-indigo-500/30 dark:text-indigo-300">Analiz ediliyor</Badge>}
        </div>
        <time className="text-xs text-zinc-500">{fmtDate(email.date)}</time>
      </header>

      <h3 className="mt-3 text-lg font-semibold text-zinc-900 dark:text-zinc-50">{email.subject}</h3>
      <p className="text-sm text-zinc-500">
        {email.sender} → {email.to.join(', ')}
      </p>
      <details className="group mt-2">
        <summary className="cursor-pointer text-sm text-indigo-600 hover:underline dark:text-indigo-400">E-postayı göster</summary>
        <p className="mt-2 whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 text-sm text-zinc-700 dark:bg-zinc-950/60 dark:text-zinc-300">{email.body}</p>
      </details>

      {status === 'PROCESSING' && <Skeleton />}

      {status === 'FAILED' && (
        <p role="alert" className="mt-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
          {card.error}
        </p>
      )}

      {a && (
        <section className="mt-4">
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{a.reasoning}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span>Güven %{Math.round(a.confidence * 100)}</span>
            {a.related_task_id && (
              <span className="rounded bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">
                Görev #{a.related_task_id}
                {task ? ` · ${task.name}` : ''}
              </span>
            )}
          </div>
        </section>
      )}

      {result?.impact && <Impact impact={result.impact} delayDays={a.delay_days} />}

      {draft && (
        <section className="mt-5 border-t border-zinc-200 pt-4 dark:border-zinc-800">
          <h4 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {ACTION[draft.action_type]} {pending ? '(düzenleyebilirsin)' : ''}
          </h4>
          {warnings.length > 0 && (
            <ul className="mb-3 space-y-1 rounded-lg bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
              {warnings.map((w) => (
                <li key={w}>⚠ {w}</li>
              ))}
            </ul>
          )}
          <div className="space-y-3">
            <label className="block text-xs font-medium text-zinc-500">
              {isMeeting ? 'Katılımcılar' : 'Alıcılar'}
              <input className={`${inputCls} mt-1`} value={to} onChange={(e) => setTo(e.target.value)} disabled={!pending} placeholder="ornek@sirket.com, ..." />
            </label>
            <label className="block text-xs font-medium text-zinc-500">
              {isMeeting ? 'Toplantı başlığı' : 'Konu'}
              <input className={`${inputCls} mt-1`} value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!pending} />
            </label>
            <label className="block text-xs font-medium text-zinc-500">
              {isMeeting ? 'Açıklama' : 'Metin'}
              <textarea className={`${inputCls} mt-1 min-h-28 resize-y`} value={body} onChange={(e) => setBody(e.target.value)} disabled={!pending} />
            </label>
          </div>
        </section>
      )}

      {error && (
        <p role="alert" className="mt-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}

      {pending && (
        <footer className="mt-4 flex flex-wrap gap-3">
          <button
            onClick={approve}
            disabled={busy !== null}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 active:scale-[0.98] disabled:opacity-60"
          >
            {busy === 'approve' ? 'Gönderiliyor…' : isMeeting ? 'Onayla ve davet oluştur' : 'Onayla ve gönder'}
          </button>
          <button
            onClick={() => run('reject', () => onReject(card.id))}
            disabled={busy !== null}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 active:scale-[0.98] disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            {busy === 'reject' ? 'Reddediliyor…' : 'Reddet'}
          </button>
        </footer>
      )}

      {card.decided_at && <p className="mt-3 text-xs text-zinc-500">Karar: {fmtDateTime(card.decided_at)}</p>}
    </article>
  )
}
