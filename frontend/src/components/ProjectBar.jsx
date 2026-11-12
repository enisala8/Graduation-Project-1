import { useRef } from 'react'
import { fmtDate } from '../labels'

const btn =
  'rounded-lg px-3.5 py-2 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 active:scale-[0.98] disabled:opacity-60'

export default function ProjectBar({ project, uploadError, busy, onUpload, onDemo }) {
  const fileRef = useRef(null)

  const picker = (
    <input
      ref={fileRef}
      type="file"
      accept=".xlsx"
      className="hidden"
      onChange={(e) => {
        const file = e.target.files[0]
        e.target.value = '' // aynı dosya tekrar seçilebilsin
        if (file) onUpload(file)
      }}
    />
  )

  const errors = uploadError && (
    <ul role="alert" className="mt-3 list-disc space-y-1 rounded-lg bg-red-500/10 p-3 pl-7 text-sm text-red-700 dark:text-red-300">
      {uploadError.split(' · ').map((p) => (
        <li key={p}>{p}</li>
      ))}
    </ul>
  )

  if (!project) {
    return (
      <section className="rounded-2xl border border-dashed border-zinc-300 bg-white p-8 text-center dark:border-zinc-700 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Önce proje planını yükle</h2>
        <p className="mx-auto mt-1 max-w-xl text-sm text-zinc-500">
          Ajan, e-postaları bu plana göre değerlendirir. Sütunlar: ID, Görev, Sorumlu_Mail, Başlangıç_Tarihi, Bitiş_Tarihi,
          Bağımlı_Olduğu_ID, Durum.
        </p>
        <button className={`${btn} mt-4 bg-indigo-600 text-white hover:bg-indigo-500`} disabled={busy} onClick={() => fileRef.current.click()}>
          {busy ? 'Yükleniyor…' : 'Excel dosyası seç (.xlsx)'}
        </button>
        {picker}
        <div className="mx-auto max-w-xl text-left">{errors}</div>
      </section>
    )
  }

  const people = new Set(project.tasks.map((t) => t.owner_email)).size
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{project.tasks.length} görev</span> · {people} kişi · plan
          bitişi {fmtDate(project.project_end ?? project.tasks.map((t) => t.end).sort().at(-1))}
        </p>
        <div className="flex gap-2">
          <button className={`${btn} border border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800`} disabled={busy} onClick={() => fileRef.current.click()}>
            Excel'i değiştir
          </button>
          <button className={`${btn} bg-indigo-600 text-white hover:bg-indigo-500`} disabled={busy} onClick={onDemo}>
            Demo mailleri yükle
          </button>
        </div>
      </div>
      {picker}
      {errors}
    </section>
  )
}
