import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import PatientPicker from '../components/PatientPicker'
import { listDoctors } from '../lib/queue'
import { listBeds, admitPatient, transferAdmission, dischargeAdmission } from '../lib/beds'

const WARD_ORDER = ['special', 'semi_special', 'general']

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export default function Beds() {
  const { t } = useTranslation()
  const [beds, setBeds] = useState([])
  const [doctors, setDoctors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [admitBed, setAdmitBed] = useState(null)
  const [transferAdm, setTransferAdm] = useState(null)
  const [dischargeAdm, setDischargeAdm] = useState(null)

  const load = useCallback(() => {
    setLoading(true); setError('')
    listBeds().then((r) => setBeds(r.items)).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])
  useEffect(() => {
    load()
    listDoctors().then(setDoctors).catch(() => {})
  }, [load])

  const occupied = beds.filter((b) => b.status === 'occupied').length
  const freeBeds = beds.filter((b) => b.status === 'available')

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('beds.title')}</h1>
        {!loading && (
          <span className="occupancy-pill">
            {t('beds.occupancy', { occupied, total: beds.length })}
          </span>
        )}
      </div>

      {error && <div className="alert error">{error}</div>}
      {loading ? <p className="muted">{t('common.loading')}</p> : (
        <div className="bed-wards">
          {WARD_ORDER.map((ward) => {
            const group = beds.filter((b) => b.ward_type === ward)
            if (group.length === 0) return null
            return (
              <section key={ward}>
                <h3 className="section-title">{t(`beds.ward_${ward}`)} <span className="muted">({group.length})</span></h3>
                <div className="bed-grid">
                  {group.map((b) => (
                    <BedCard key={b.id} b={b} t={t}
                      onAdmit={() => setAdmitBed(b)}
                      onTransfer={() => setTransferAdm(b)}
                      onDischarge={() => setDischargeAdm(b)} />
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}

      {admitBed && (
        <AdmitModal t={t} bed={admitBed} doctors={doctors}
          onClose={() => setAdmitBed(null)}
          onDone={() => { setAdmitBed(null); load() }} onError={setError} />
      )}
      {transferAdm && (
        <TransferModal t={t} bed={transferAdm} freeBeds={freeBeds}
          onClose={() => setTransferAdm(null)}
          onDone={() => { setTransferAdm(null); load() }} onError={setError} />
      )}
      {dischargeAdm && (
        <DischargeModal t={t} bed={dischargeAdm}
          onClose={() => setDischargeAdm(null)}
          onDone={() => { setDischargeAdm(null); load() }} onError={setError} />
      )}
    </div>
  )
}

function BedCard({ b, t, onAdmit, onTransfer, onDischarge }) {
  return (
    <div className={`bed-card status-${b.status}`}>
      <div className="bed-label">{b.bed_label}</div>
      {b.status === 'occupied' ? (
        <>
          <div className="bed-patient">{b.patient_name} <span className="mono muted">{b.patient_uhid}</span></div>
          <div className="bed-meta">
            {t('beds.admitted')} {fmtDate(b.admitted_at)}
            {b.doctor_name ? ` · ${b.doctor_name}` : ''}
          </div>
          <div className="bed-actions">
            <button className="btn-ghost sm" onClick={onTransfer}>{t('beds.transfer')}</button>
            <button className="btn-primary inline sm" onClick={onDischarge}>{t('beds.discharge')}</button>
          </div>
        </>
      ) : b.status === 'available' ? (
        <>
          <div className="bed-status-free">{t('beds.available')}</div>
          <div className="bed-actions">
            <button className="btn-primary inline sm" onClick={onAdmit}>{t('beds.admit')}</button>
          </div>
        </>
      ) : (
        <div className="bed-meta">{t(`beds.status_${b.status}`)}</div>
      )}
    </div>
  )
}

function AdmitModal({ t, bed, doctors, onClose, onDone, onError }) {
  const [patient, setPatient] = useState(null)
  const [doctorId, setDoctorId] = useState('')
  const [diagnosis, setDiagnosis] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function submit() {
    if (!patient) { setErr(t('beds.pickPatient')); return }
    setBusy(true); setErr('')
    try {
      await admitPatient({
        patient_id: patient.id, bed_id: bed.id,
        attending_doctor_id: doctorId ? Number(doctorId) : undefined,
        diagnosis: diagnosis || undefined,
      })
      onDone()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={`${t('beds.admitTitle')} ${bed.bed_label}`} onClose={onClose}
      busy={busy} onSubmit={submit} submitLabel={t('beds.admit')} error={err}>
      <div className="field">
        <span className="field-label">{t('beds.patient')}</span>
        <PatientPicker value={patient} onChange={setPatient} placeholder={t('queue.searchPatient')} />
      </div>
      <label className="field">
        <span>{t('beds.doctor')}</span>
        <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
          <option value="">—</option>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </select>
      </label>
      <label className="field">
        <span>{t('beds.diagnosis')}</span>
        <textarea rows={2} value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} />
      </label>
    </Modal>
  )
}

function TransferModal({ t, bed, freeBeds, onClose, onDone, onError }) {
  const [toBed, setToBed] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function submit() {
    if (!toBed) { setErr(t('beds.noFreeBeds')); return }
    setBusy(true); setErr('')
    try { await transferAdmission(bed.admission_id, Number(toBed)); onDone() }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={`${t('beds.transferTitle')} · ${bed.patient_name}`} onClose={onClose}
      busy={busy} onSubmit={submit} submitLabel={t('beds.transfer')} error={err}>
      <label className="field">
        <span>{t('beds.toBed')}</span>
        <select value={toBed} onChange={(e) => setToBed(e.target.value)}>
          <option value="">—</option>
          {freeBeds.map((b) => (
            <option key={b.id} value={b.id}>{b.bed_label} ({t(`beds.ward_${b.ward_type}`)})</option>
          ))}
        </select>
      </label>
    </Modal>
  )
}

function DischargeModal({ t, bed, onClose, onDone, onError }) {
  const [summary, setSummary] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function submit() {
    setBusy(true); setErr('')
    try { await dischargeAdmission(bed.admission_id, summary || undefined); onDone() }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={`${t('beds.dischargeTitle')} · ${bed.patient_name}`} onClose={onClose}
      busy={busy} onSubmit={submit} submitLabel={t('beds.confirmDischarge')} error={err}>
      <label className="field">
        <span>{t('beds.dischargeSummary')}</span>
        <textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />
      </label>
    </Modal>
  )
}

function Modal({ title, onClose, onSubmit, submitLabel, busy, error, children }) {
  const { t } = useTranslation()
  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {children}
          {error && <div className="alert error">{error}</div>}
        </div>
        <div className="modal-foot">
          <button className="btn-ghost" onClick={onClose}>{t('common.cancel')}</button>
          <button className="btn-primary inline" disabled={busy} onClick={onSubmit}>
            {busy ? t('common.saving') : submitLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
