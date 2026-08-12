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
  const attention = data.attention || []
  const alertMin = data.wait_alert_min ?? 30
  const longest = tot.waiting_longest || 0
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <div className="page">
      <h1 className="page-title">{t('dashboard.title')}</h1>
      <p className="muted">{today}</p>

      {/* Priority band: what reception must act on now, then the attention list */}
      <div className="dash-top">
        <div className="hero-stats">
          <HeroStat
            value={tot.waiting}
            label={t('dashboard.waiting')}
            tone={tot.waiting > 0 ? 'wait' : 'calm'}
            onClick={() => navigate('/queue')}
          />
          <HeroStat
            value={longest > 0 ? longest : '—'}
            suffix={longest > 0 ? t('dashboard.minShort') : ''}
            label={t('dashboard.longestWait')}
            tone={longest >= alertMin ? 'alert' : longest > 0 ? 'wait' : 'calm'}
            onClick={() => navigate('/queue')}
          />
        </div>

        <AttentionPanel
          items={attention}
          alertMin={alertMin}
          onOpen={() => navigate('/queue')}
          t={t}
        />
      </div>

      {/* Secondary, lower-priority counts */}
      <div className="stat-grid secondary">
        <MiniStat icon="📋" value={tot.queue_total} label={t('dashboard.inQueue')} />
        <MiniStat icon="✓" value={tot.completed} label={t('dashboard.seenToday')} ok />
        <MiniStat icon="🆕" value={tot.registered_today} label={t('dashboard.registeredToday')} />
        <MiniStat icon="👥" value={tot.patients_total} label={t('dashboard.patientsTotal')} />
      </div>

      <h2 className="section-title">{t('dashboard.todayByDoctor')}</h2>
      <div className="doctor-grid">
        {data.doctors.map((d) => (
          <div className="card doctor-card compact" key={d.doctor_id} onClick={() => navigate('/queue')}>
            <div className="doctor-head">
              <div>
                <div className="doctor-name">{d.doctor_name}</div>
                <div className="doctor-spec muted">{t(`dashboard.spec.${d.specialty}`)}</div>
              </div>
              <span className={`session-pill ${d.session ? '' : 'off'}`}>
                {d.session ? `${hhmm(d.session.start_time)} – ${hhmm(d.session.end_time)}` : t('dashboard.noSession')}
              </span>
            </div>
            <div className="doctor-line">
              <DocStat n={d.counts.waiting} label={t('dashboard.waiting')} tone="wait" />
              <DocStat n={d.counts.in_consultation} label={t('dashboard.inConsult')} tone="accent" />
              <DocStat n={d.counts.completed} label={t('dashboard.done')} tone="ok" />
              <DocStat n={d.counts.booked} label={t('dashboard.booked')} />
              {d.counts.current_token != null && (
                <span className="doc-serving">
                  {t('dashboard.nowServing')} <strong>#{d.counts.current_token}</strong>
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HeroStat({ value, suffix, label, tone, onClick }) {
  return (
    <button type="button" className={`hero-stat tone-${tone}`} onClick={onClick}>
      <span className="hero-label">{label}</span>
      <span className="hero-value">
        {value}{suffix ? <span className="hero-suffix"> {suffix}</span> : null}
      </span>
    </button>
  )
}

function AttentionPanel({ items, alertMin, onOpen, t }) {
  const clear = items.length === 0
  return (
    <div className={`attention-panel${clear ? ' clear' : ''}`}>
      <div className="attention-head">
        <span className="attention-icon" aria-hidden="true">{clear ? '✓' : '⚠'}</span>
        <div>
          <div className="attention-title">
            {clear ? t('dashboard.allClear') : t('dashboard.attention')}
          </div>
          <div className="attention-sub">
            {clear
              ? t('dashboard.allClearHint', { min: alertMin })
              : t('dashboard.attentionCount', { n: items.length, min: alertMin })}
          </div>
        </div>
      </div>

      {!clear && (
        <>
          <ul className="attention-list">
            {items.slice(0, 4).map((a, i) => (
              <li key={i}>
                <span className="att-token">#{a.token_no ?? '—'}</span>
                <span className="att-name">{a.patient_name}</span>
                <span className="att-doc muted">{a.doctor_name}</span>
                <span className="att-wait">{t('dashboard.waitingFor', { n: a.wait_min })}</span>
              </li>
            ))}
          </ul>
          <button type="button" className="btn-ghost sm attention-cta" onClick={onOpen}>
            {t('dashboard.openQueue')} →
          </button>
        </>
      )}
    </div>
  )
}

function MiniStat({ icon, value, label, ok }) {
  return (
    <div className={`mini-stat${ok ? ' ok' : ''}`}>
      <span className="mini-icon">{icon}</span>
      <span className="mini-text">
        <span className="mini-value">{value}</span>
        <span className="mini-label">{label}</span>
      </span>
    </div>
  )
}

function DocStat({ n, label, tone }) {
  return (
    <span className={`doc-stat-inline${tone ? ' tone-' + tone : ''}`}>
      <span className="n">{n}</span>
      <span className="l">{label}</span>
    </span>
  )
}
