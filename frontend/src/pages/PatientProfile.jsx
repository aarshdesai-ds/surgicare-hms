import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getPatient } from '../lib/patients'
import { listEncounters } from '../lib/encounters'
import { listPrescriptions } from '../lib/prescriptions'
import { listDoctors } from '../lib/queue'
import ConsultationModal from '../components/ConsultationModal'

function fmtDateTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function PatientProfile() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()

  const [patient, setPatient] = useState(null)
  const [encounters, setEncounters] = useState([])
  const [prescriptions, setPrescriptions] = useState([])
  const [doctors, setDoctors] = useState([])
  const [showConsult, setShowConsult] = useState(false)
  const [error, setError] = useState('')

  const loadEncounters = useCallback(() => {
    listEncounters(id).then((r) => setEncounters(r.items)).catch(() => {})
  }, [id])
  const loadRx = useCallback(() => {
    listPrescriptions(id).then((r) => setPrescriptions(r.items)).catch(() => {})
  }, [id])

  useEffect(() => {
    getPatient(id).then(setPatient).catch((e) => setError(e.message))
    listDoctors().then(setDoctors).catch(() => {})
    loadEncounters()
    loadRx()
  }, [id, loadEncounters, loadRx])

  if (error) return <div className="page"><div className="alert error">{error}</div></div>
  if (!patient) return <div className="page"><p className="muted">{t('common.loading')}</p></div>

  const genderLabel = { M: t('patients.male'), F: t('patients.female'), O: t('patients.other') }
  const fullName = `${patient.first_name} ${patient.last_name || ''}`.trim()

  return (
    <div className="page">
      <button className="btn-ghost back-link" onClick={() => navigate('/patients')}>
        ‹ {t('patients.title')}
      </button>

      <div className="page-header">
        <div>
          <h1 className="page-title">{fullName}</h1>
          <span className="mono muted">{patient.uhid}</span>
        </div>
        <div className="header-actions">
          <button className="btn-ghost" onClick={() => setShowConsult(true)}>
            + {t('consult.addNote')}
          </button>
          <button className="btn-primary inline" onClick={() => navigate(`/patients/${id}/edit`)}>
            {t('common.edit')}
          </button>
        </div>
      </div>

      <div className="card">
        <dl className="detail-grid">
          <Row label={t('patients.phone')} value={patient.phone} />
          <Row label={t('patients.altPhone')} value={patient.alt_phone} />
          <Row label={t('patients.gender')} value={genderLabel[patient.gender]} />
          <Row label={t('patients.dob')} value={patient.dob} />
          <Row label={t('patients.bloodGroup')} value={patient.blood_group} />
          <Row label={t('patients.abha')} value={patient.abha_number} />
          <Row label={t('patients.address')} value={patient.address} wide />
          <Row label={t('patients.allergies')} value={patient.allergies} wide highlight />
        </dl>
      </div>

      <section className="visit-history">
        <h2 className="section-title">{t('consult.history')}</h2>
        {encounters.length === 0 ? (
          <div className="card empty-day">{t('consult.noHistory')}</div>
        ) : (
          encounters.map((e) => <VisitCard key={e.id} e={e} t={t} />)
        )}
      </section>

      <section className="visit-history">
        <h2 className="section-title">{t('rx.history')}</h2>
        {prescriptions.length === 0 ? (
          <div className="card empty-day">{t('rx.none')}</div>
        ) : (
          prescriptions.map((r) => <RxCard key={r.id} r={r} t={t} />)
        )}
      </section>

      {showConsult && (
        <ConsultationModal
          patientId={Number(id)}
          patientLabel={`${fullName} · ${patient.uhid}`}
          doctors={doctors}
          onClose={() => setShowConsult(false)}
          onSaved={() => { setShowConsult(false); loadEncounters(); loadRx() }}
        />
      )}
    </div>
  )
}

function VisitCard({ e, t }) {
  return (
    <div className="visit-card">
      <div className="visit-head">
        <span className="visit-date">{fmtDateTime(e.occurred_at)}</span>
        {e.doctor_name && <span className="visit-doctor">{e.doctor_name}</span>}
      </div>
      {e.diagnosis && <div className="visit-dx"><strong>{t('consult.diagnosis')}:</strong> {e.diagnosis}</div>}
      {e.complaints && <div className="visit-line"><b>{t('consult.complaints')}:</b> {e.complaints}</div>}
      {e.vitals && Object.keys(e.vitals).length > 0 && (
        <div className="vitals-chips">
          {Object.entries(e.vitals).map(([k, val]) => (
            <span className="vchip" key={k}>{k.toUpperCase()}: {val}</span>
          ))}
        </div>
      )}
      {e.notes && <div className="visit-line"><b>{t('consult.notes')}:</b> {e.notes}</div>}
    </div>
  )
}

function RxCard({ r, t }) {
  return (
    <div className="visit-card">
      <div className="visit-head">
        <span className="visit-date">{fmtDateTime(r.created_at)}</span>
        {r.doctor_name && <span className="visit-doctor">{r.doctor_name}</span>}
        {r.pharmacy_status && (
          <span className={`badge rx-${r.pharmacy_status}`}>{t(`rx.status_${r.pharmacy_status}`)}</span>
        )}
      </div>
      <ul className="rx-list">
        {r.items.map((it, i) => (
          <li key={i}>
            <strong>{it.drug_name}</strong>
            {it.strength ? ` ${it.strength}` : ''}
            {it.frequency ? ` · ${it.frequency}` : ''}
            {it.duration ? ` · ${it.duration}` : ''}
            {it.quantity ? ` · ${t('rx.qty')} ${it.quantity}` : ''}
            {it.instructions ? ` — ${it.instructions}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Row({ label, value, wide, highlight }) {
  return (
    <div className={`detail-row${wide ? ' wide' : ''}`}>
      <dt>{label}</dt>
      <dd className={highlight && value ? 'highlight' : ''}>{value || '—'}</dd>
    </div>
  )
}
