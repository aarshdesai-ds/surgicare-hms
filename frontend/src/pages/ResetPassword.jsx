import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { supabase } from '../lib/supabase'
import LanguageToggle from '../components/LanguageToggle'

export default function ResetPassword() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // null = still checking for a recovery session, true = ready, false = invalid link
  const [ready, setReady] = useState(null)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  // Supabase turns the recovery link's URL hash into a session on load and
  // fires PASSWORD_RECOVERY. Accept either that event or an existing session.
  useEffect(() => {
    let settled = false
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || session) { settled = true; setReady(true) }
    })
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) { settled = true; setReady(true) }
      // Give the URL-hash handler a moment before declaring the link invalid.
      else setTimeout(() => { if (!settled) setReady(false) }, 1200)
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError(t('reset.tooShort')); return }
    if (password !== confirm) { setError(t('reset.mismatch')); return }
    setBusy(true)
    const { error: updateError } = await supabase.auth.updateUser({ password })
    setBusy(false)
    if (updateError) { setError(t('reset.failed')); return }
    setDone(true)
    // Drop the recovery session so they sign in fresh with the new password.
    await supabase.auth.signOut()
  }

  return (
    <div className="auth-page">
      <div className="auth-toggle">
        <LanguageToggle />
      </div>

      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark big">✚</span>
          <h1>{t('reset.title')}</h1>
          <p className="muted">{t('reset.intro')}</p>
        </div>

        {ready === false && !done && (
          <>
            <div className="auth-msg"><div className="alert error">{t('reset.invalid')}</div></div>
            <button className="btn-primary" onClick={() => navigate('/login')}>
              {t('reset.toLogin')}
            </button>
          </>
        )}

        {done ? (
          <>
            <div className="auth-msg"><div className="alert info">{t('reset.success')}</div></div>
            <button className="btn-primary" onClick={() => navigate('/login')}>
              {t('reset.toLogin')}
            </button>
          </>
        ) : ready === true ? (
          <form onSubmit={handleSubmit} className="reset-form">
            <label className="field">
              <span>{t('reset.newPassword')}</span>
              <div className="password-field">
                <input
                  type={showPw ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button type="button" className="pw-toggle" tabIndex={-1}
                  onClick={() => setShowPw((v) => !v)}>
                  {showPw ? t('login.hide') : t('login.show')}
                </button>
              </div>
            </label>

            <label className="field">
              <span>{t('reset.confirm')}</span>
              <input
                type={showPw ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </label>

            <div className="auth-msg" aria-live="polite">
              {error && <div className="alert error">{error}</div>}
            </div>

            <button className="btn-primary" type="submit" disabled={busy}>
              {busy ? t('reset.submitting') : t('reset.submit')}
            </button>
          </form>
        ) : ready === null ? (
          <p className="muted" style={{ textAlign: 'center' }}>{t('common.loading')}</p>
        ) : null}
      </div>
    </div>
  )
}
