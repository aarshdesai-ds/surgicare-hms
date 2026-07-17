import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  getInvoice, addLineItem, removeLineItem, setDiscount,
  finalizeInvoice, cancelInvoice, addPayment, listServices, money, fmtDate,
} from '../lib/billing'

const METHODS = ['cash', 'card', 'upi', 'netbanking', 'razorpay', 'other']

export default function InvoiceDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const nav = useNavigate()
  const [inv, setInv] = useState(null)
  const [services, setServices] = useState([])
  const [error, setError] = useState('')

  const load = useCallback(() => {
    getInvoice(id).then(setInv).catch((e) => setError(e.message))
  }, [id])
  useEffect(() => {
    load()
    listServices(true).then((r) => setServices(r.items)).catch(() => {})
  }, [load])

  async function act(fn) {
    setError('')
    try { setInv(await fn()) } catch (e) { setError(e.message) }
  }

  if (error && !inv) return <div className="page"><div className="alert error">{error}</div></div>
  if (!inv) return <div className="page"><p className="muted">{t('common.loading')}</p></div>

  const isDraft = inv.status === 'draft'
  const due = Number(inv.grand_total) - Number(inv.amount_paid)

  return (
    <div className="page">
      <button className="btn-ghost back-link no-print" onClick={() => nav('/billing')}>
        ‹ {t('billing.title')}
      </button>

      <div className="invoice-doc">
        <div className="report-header">
          <div className="report-hospital">{t('app.title')} · {t('app.subtitle')}</div>
          <div className="report-sub">
            {inv.invoice_no ? `${t('billing.invoiceNo')} ${inv.invoice_no}` : t('billing.draft')} — {fmtDate(inv.created_at)}
          </div>
        </div>

        <div className="invoice-meta">
          <div>
            <strong>{inv.patient_name}</strong> <span className="mono muted">{inv.patient_uhid}</span>
            <div className="muted">{inv.patient_phone}</div>
          </div>
          <span className={`badge b-${inv.status}`}>{t(`billing.status_${inv.status}`)}</span>
        </div>

        <table className="report-table">
          <thead>
            <tr>
              <th>{t('billing.description')}</th>
              <th className="ta-r">{t('billing.qty')}</th>
              <th className="ta-r">{t('billing.rate')}</th>
              <th className="ta-r">{t('billing.gst')}</th>
              <th className="ta-r">{t('billing.amount')}</th>
              {isDraft && <th className="no-print" />}
            </tr>
          </thead>
          <tbody>
            {inv.line_items.length === 0 ? (
              <tr><td colSpan={6} className="muted">{t('billing.noItems')}</td></tr>
            ) : (
              inv.line_items.map((li) => (
                <tr key={li.id}>
                  <td>{li.description}</td>
                  <td className="ta-r">{Number(li.quantity)}</td>
                  <td className="ta-r">{money(li.unit_price)}</td>
                  <td className="ta-r">{Number(li.gst_rate)}%</td>
                  <td className="ta-r">{money(li.line_total)}</td>
                  {isDraft && (
                    <td className="no-print">
                      <button className="link-danger" title={t('common.cancel')}
                        onClick={() => act(() => removeLineItem(id, li.id))}>×</button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div className="invoice-totals">
          <div><span>{t('billing.subtotal')}</span><span>{money(inv.subtotal)}</span></div>
          <div><span>{t('billing.tax')}</span><span>{money(inv.tax_total)}</span></div>
          {Number(inv.discount) > 0 && (
            <div><span>{t('billing.discount')}</span><span>−{money(inv.discount)}</span></div>
          )}
          <div className="grand"><span>{t('billing.grandTotal')}</span><span>{money(inv.grand_total)}</span></div>
          <div><span>{t('billing.paid')}</span><span>{money(inv.amount_paid)}</span></div>
          <div className="due"><span>{t('billing.due')}</span><span>{money(due)}</span></div>
        </div>

        {inv.payments.length > 0 && (
          <div className="report-section">
            <h2>{t('billing.payments')}</h2>
            <table className="report-table">
              <tbody>
                {inv.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{fmtDate(p.received_at)}</td>
                    <td>{t(`billing.method_${p.method}`)}</td>
                    <td>{p.reference || ''}</td>
                    <td className="ta-r">{money(p.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="no-print invoice-actions">
        {error && <div className="alert error">{error}</div>}

        {isDraft && (
          <AddItemPanel t={t} services={services} discount={inv.discount}
            onAdd={(d) => act(() => addLineItem(id, d))}
            onDiscount={(d) => act(() => setDiscount(id, d))} />
        )}

        <div className="invoice-buttons">
          {!isDraft && inv.status !== 'cancelled' && due > 0 && (
            <PaymentButton t={t} due={due} methods={METHODS}
              onPay={(d) => act(() => addPayment(id, d))} />
          )}
          {isDraft && (
            <button className="btn-primary inline" disabled={inv.line_items.length === 0}
              onClick={() => act(() => finalizeInvoice(id))}>
              {t('billing.finalize')}
            </button>
          )}
          {inv.status !== 'draft' && inv.status !== 'cancelled' && (
            <button className="btn-ghost" onClick={() => window.print()}>{t('reports.print')}</button>
          )}
          {inv.status !== 'paid' && inv.status !== 'cancelled' && (
            <button className="btn-ghost" onClick={() => {
              if (window.confirm(t('billing.confirmCancel'))) act(() => cancelInvoice(id))
            }}>{t('billing.cancel')}</button>
          )}
        </div>
      </div>
    </div>
  )
}

function AddItemPanel({ t, services, onAdd, onDiscount, discount }) {
  const [serviceId, setServiceId] = useState('')
  const [desc, setDesc] = useState('')
  const [qty, setQty] = useState('1')
  const [price, setPrice] = useState('')
  const [gst, setGst] = useState('0')
  const [disc, setDisc] = useState(String(Number(discount) || 0))

  function pick(sid) {
    setServiceId(sid)
    const s = services.find((x) => String(x.id) === sid)
    if (s) { setDesc(s.name); setPrice(String(Number(s.unit_price))); setGst(String(Number(s.gst_rate))) }
  }
  function add() {
    if (!desc.trim() || price === '') return
    onAdd({
      service_id: serviceId ? Number(serviceId) : undefined,
      description: desc, quantity: Number(qty) || 1,
      unit_price: Number(price), gst_rate: Number(gst) || 0,
    })
    setServiceId(''); setDesc(''); setQty('1'); setPrice(''); setGst('0')
  }

  return (
    <div className="card add-panel">
      <div className="add-item-grid">
        <div className="add-field">
          <span className="field-label">{t('billing.service')}</span>
          <select value={serviceId} onChange={(e) => pick(e.target.value)}>
            <option value="">{t('billing.manual')}</option>
            {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="add-field">
          <span className="field-label">{t('billing.description')}</span>
          <input className="reason-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
        </div>
        <div className="add-field sm">
          <span className="field-label">{t('billing.qty')}</span>
          <input className="reason-input" type="number" min="0" step="0.5" value={qty} onChange={(e) => setQty(e.target.value)} />
        </div>
        <div className="add-field sm">
          <span className="field-label">{t('billing.rate')}</span>
          <input className="reason-input" type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div className="add-field sm">
          <span className="field-label">{t('billing.gst')} %</span>
          <input className="reason-input" type="number" min="0" max="100" value={gst} onChange={(e) => setGst(e.target.value)} />
        </div>
        <button className="btn-primary inline" onClick={add}>{t('billing.addItem')}</button>
      </div>
      <div className="discount-row">
        <span className="field-label">{t('billing.discount')}</span>
        <input className="reason-input sm-w" type="number" min="0" step="0.01" value={disc} onChange={(e) => setDisc(e.target.value)} />
        <button className="btn-ghost sm" onClick={() => onDiscount(Number(disc) || 0)}>{t('common.save')}</button>
      </div>
    </div>
  )
}

function PaymentButton({ t, due, methods, onPay }) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState(String(due))
  const [method, setMethod] = useState('cash')
  if (!open) {
    return (
      <button className="btn-primary inline" onClick={() => { setAmount(String(due)); setOpen(true) }}>
        {t('billing.recordPayment')}
      </button>
    )
  }
  return (
    <div className="pay-inline">
      <input className="reason-input sm-w" type="number" min="0" step="0.01"
        value={amount} onChange={(e) => setAmount(e.target.value)} />
      <select value={method} onChange={(e) => setMethod(e.target.value)}>
        {methods.map((m) => <option key={m} value={m}>{t(`billing.method_${m}`)}</option>)}
      </select>
      <button className="btn-primary inline" onClick={() => onPay({ amount: Number(amount), method })}>
        {t('billing.pay')}
      </button>
      <button className="btn-ghost sm" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
    </div>
  )
}
