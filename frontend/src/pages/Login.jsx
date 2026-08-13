import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import LanguageToggle from '../components/LanguageToggle'

export default function Login() {
  const { t } = useTranslation()
  const { signIn, resetPassword } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [capsOn, setCapsOn] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setInfo('')
    setSubmitting(true)
    const { error: signInError } = await signIn(email, password)
    setSubmitting(false)
    if (signInError) {
      // Show Supabase's actual message so failures are diagnosable.
      setError(signInError.message || t('login.error'))
      return
    }
    navigate('/', { replace: true })
  }

  async function handleForgot() {
    setError('')
    setInfo('')
    if (!email.trim()) {
      setError(t('login.resetNeedEmail'))
      return
    }
    const { error: resetError } = await resetPassword(email.trim())
    if (resetError) {
      setError(t('login.resetFailed'))
      return
    }
    setInfo(t('login.resetSent'))
  }

  // Caps Lock detection on the password field (both key events carry the state).
  function checkCaps(e) {
    if (typeof e.getModifierState === 'function') {
      setCapsOn(e.getModifierState('CapsLock'))
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-toggle">
        <LanguageToggle />
      </div>

      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-brand">
          <span className="brand-mark big">✚</span>
          <h1>{t('app.title')}</h1>
          <p className="muted">{t('login.intro')}</p>
        </div>

        <label className="field">
          <span>{t('login.email')}</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>{t('login.password')}</span>
          <div className="password-field">
            <input
              type={showPw ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyUp={checkCaps}
              onKeyDown={checkCaps}
              onBlur={() => setCapsOn(false)}
              required
            />
            <button
              type="button"
              className="pw-toggle"
              onClick={() => setShowPw((v) => !v)}
              tabIndex={-1}
            >
              {showPw ? t('login.hide') : t('login.show')}
            </button>
          </div>
          {capsOn && (
            <span className="caps-hint">⇪ {t('login.capsLock')}</span>
          )}
        </label>

        <div className="auth-row">
          <button type="button" className="link-btn" onClick={handleForgot}>
            {t('login.forgot')}
          </button>
        </div>

        {/* Reserved space so the card doesn't jump when a message appears */}
        <div className="auth-msg" aria-live="polite">
          {error && <div className="alert error">{error}</div>}
          {info && <div className="alert info">{info}</div>}
        </div>

        <button className="btn-primary" type="submit" disabled={submitting}>
          {submitting ? t('login.submitting') : t('login.submit')}
        </button>
      </form>
    </div>
  )
}
