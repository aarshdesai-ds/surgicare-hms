import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getDashboard } from '../lib/dashboard'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const hhmm = (t) => (t ? t.slice(0, 5) : '')

export default function Dashboard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getDashboard(todayISO()).then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="page"><div className="alert error">{error}</div></div>
  if (!data) return <div className="page"><p className="muted">{t('common.loading')}</p></div>

  const tot = data.totals
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <div className="page">
      <h1 className="page-title">{t('dashboard.title')}</h1>
      <p className="muted">{today}</p>

      <div className="stat-grid">
        <StatCard icon="👥" value={tot.patients_total} label={t('dashboard.patientsTotal')} />
        <StatCard icon="🆕" value={tot.registered_today} label={t('dashboard.registeredToday')} accent />
        <StatCard icon="📋" value={tot.queue_total} label={t('dashboard.inQueue')} />
        <StatCard icon="⏳" value={tot.waiting} label={t('dashboard.waiting')} />
        <StatCard icon="✓" value={tot.completed} label={t('dashboard.seenToday')} ok />
      </div>

      <h2 className="section-title">{t('dashboard.todayByDoctor')}</h2>
      <div className="doctor-grid">
        {data.doctors.map((d) => (
          <div className="card doctor-card" key={d.doctor_id} onClick={() => navigate('/queue')}>
            <div className="doctor-head">
              <div>
                <div className="doctor-name">{d.doctor_name}</div>
                <div className="doctor-spec muted">{t(`dashboard.spec.${d.specialty}`)}</div>
              </div>
              <span className={`session-pill ${d.session ? '' : 'off'}`}>
                {d.session ? `${hhmm(d.session.start_time)} – ${hhmm(d.session.end_time)}` : t('dashboard.noSession')}
              </span>
            </div>
            <div className="doctor-stats">
              <DocStat n={d.counts.waiting} label={t('dashboard.waiting')} />
              <DocStat n={d.counts.in_consultation} label={t('dashboard.inConsult')} accent />
              <DocStat n={d.counts.completed} label={t('dashboard.done')} ok />
              <DocStat n={d.counts.booked} label={t('dashboard.booked')} />
            </div>
            {d.counts.current_token != null && (
              <div className="now-serving">
                {t('dashboard.nowServing')}: <strong>#{d.counts.current_token}</strong>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function StatCard({ icon, value, label, accent, ok }) {
  return (
    <div className={`stat-card${accent ? ' accent' : ''}${ok ? ' ok' : ''}`}>
      <span className="stat-chip">{icon}</span>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function DocStat({ n, label, accent, ok }) {
  return (
    <div className={`doc-stat${accent ? ' accent' : ''}${ok ? ' ok' : ''}`}>
      <div className="n">{n}</div>
      <div className="l">{label}</div>
    </div>
  )
}
