import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getDayReport } from '../lib/reports'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function fmtDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
}
function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function Reports() {
  const { t } = useTranslation()
  const [day, setDay] = useState(todayISO())
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setData(null); setError('')
    getDayReport(day).then(setData).catch((e) => setError(e.message))
  }, [day])

  return (
    <div className="page report-page">
      <div className="page-header no-print">
        <h1 className="page-title">{t('reports.title')}</h1>
        <div className="header-actions">
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
          <button className="btn-primary inline" disabled={!data} onClick={() => window.print()}>
            {t('reports.print')}
          </button>
        </div>
      </div>

      {error && <div className="alert error no-print">{error}</div>}
      {!data && !error && <p className="muted no-print">{t('common.loading')}</p>}

      {data && (
        <div className="report">
          <div className="report-header">
            <div className="report-hospital">{t('app.title')} · {t('app.subtitle')}</div>
            <div className="report-sub">{t('reports.dayBook')} — {fmtDate(data.date)}</div>
          </div>

          <div className="report-stats">
            <Stat n={data.registrations.count} label={t('reports.newPatients')} />
            <Stat n={data.opd.totals.completed} label={t('reports.opdSeen')} />
            <Stat n={data.ot.totals.completed} label={t('reports.otDone')} />
            <Stat n={data.encounters.count} label={t('reports.notes')} />
          </div>

          {/* OPD */}
          <section className="report-section">
            <h2>{t('reports.opd')}</h2>
            {data.opd.by_doctor.length === 0 ? (
              <p className="muted">{t('reports.noOpd')}</p>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>{t('reports.doctor')}</th>
                    <th>{t('reports.booked')}</th>
                    <th>{t('reports.waiting')}</th>
                    <th>{t('reports.inConsult')}</th>
                    <th>{t('reports.seen')}</th>
                    <th>{t('reports.noShow')}</th>
                    <th>{t('reports.total')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.opd.by_doctor.map((d) => (
                    <tr key={d.doctor_id}>
                      <td>{d.doctor_name} <span className="muted">· {t(`dashboard.spec.${d.specialty}`)}</span></td>
                      <td>{d.booked}</td><td>{d.waiting}</td><td>{d.in_consultation}</td>
                      <td><strong>{d.completed}</strong></td><td>{d.no_show}</td>
                      <td><strong>{d.total}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* OT */}
          <section className="report-section">
            <h2>{t('reports.ot')} <span className="muted">({data.ot.totals.completed}/{data.ot.totals.total} {t('reports.done')})</span></h2>
            {data.ot.cases.length === 0 ? (
              <p className="muted">{t('reports.noOt')}</p>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>{t('reports.theatre')}</th><th>#</th>
                    <th>{t('reports.patient')}</th><th>{t('reports.surgeon')}</th>
                    <th>{t('reports.procedure')}</th><th>{t('reports.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ot.cases.map((c, i) => (
                    <tr key={i}>
                      <td>{c.theatre_name}</td><td>{c.position}</td>
                      <td>{c.patient_name} <span className="mono muted">{c.patient_uhid}</span></td>
                      <td>{c.surgeon_name}</td><td>{c.procedure}</td>
                      <td>{t(`ot.status.${c.status}`)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* Registrations */}
          <section className="report-section">
            <h2>{t('reports.registrations')} <span className="muted">({data.registrations.count})</span></h2>
            {data.registrations.items.length === 0 ? (
              <p className="muted">{t('reports.noReg')}</p>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>{t('reports.uhid')}</th><th>{t('reports.name')}</th>
                    <th>{t('reports.phone')}</th><th>{t('reports.time')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.registrations.items.map((r) => (
                    <tr key={r.uhid}>
                      <td className="mono">{r.uhid}</td><td>{r.name}</td>
                      <td>{r.phone}</td><td>{fmtTime(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="report-foot">{t('reports.generated')} {new Date().toLocaleString()}</div>
        </div>
      )}
    </div>
  )
}

function Stat({ n, label }) {
  return (
    <div className="report-stat">
      <div className="report-stat-n">{n}</div>
      <div className="report-stat-l">{label}</div>
    </div>
  )
}
