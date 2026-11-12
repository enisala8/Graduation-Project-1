// Rozet etiketleri ve renkleri (açık + koyu tema). Renk tek başına anlam taşımasın diye hep metin de var.
export const CATEGORY = {
  BLOCKER: { label: 'Engel', cls: 'bg-red-500/10 text-red-700 ring-red-500/30 dark:text-red-300' },
  SCOPE_CREEP: { label: 'Kapsam kayması', cls: 'bg-amber-500/10 text-amber-800 ring-amber-500/30 dark:text-amber-300' },
  RESOURCE: { label: 'Kaynak', cls: 'bg-violet-500/10 text-violet-700 ring-violet-500/30 dark:text-violet-300' },
  STATUS_UPDATE: { label: 'Bilgilendirme', cls: 'bg-slate-500/10 text-slate-700 ring-slate-500/30 dark:text-slate-300' },
}

export const RISK = {
  LOW: { label: 'Düşük risk', cls: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300' },
  MEDIUM: { label: 'Orta risk', cls: 'bg-amber-500/10 text-amber-800 ring-amber-500/30 dark:text-amber-300' },
  HIGH: { label: 'Yüksek risk', cls: 'bg-red-500/15 text-red-700 ring-red-500/40 dark:text-red-300' },
}

export const ACTION = {
  SEND_EMAIL: 'Mail taslağı',
  SCHEDULE_MEETING: 'Toplantı daveti',
}

export const STATUS = {
  APPROVED: { label: 'Onaylandı', cls: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300' },
  REJECTED: { label: 'Reddedildi', cls: 'bg-zinc-500/10 text-zinc-700 ring-zinc-500/30 dark:text-zinc-300' },
  NO_ACTION: { label: 'Aksiyon gerekmiyor', cls: 'bg-zinc-500/10 text-zinc-700 ring-zinc-500/30 dark:text-zinc-300' },
  FAILED: { label: 'Analiz başarısız', cls: 'bg-red-500/10 text-red-700 ring-red-500/30 dark:text-red-300' },
}

export const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' })

// Sunucu saati UTC "YYYY-MM-DD HH:MM:SS" verir.
export const fmtDateTime = (sql) =>
  new Date(sql.replace(' ', 'T') + 'Z').toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: 'short' })
