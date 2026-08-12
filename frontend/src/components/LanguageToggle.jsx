import { useTranslation } from 'react-i18next'

/** Two-state EN / ગુ toggle. Choice is persisted by i18next LanguageDetector. */
export default function LanguageToggle() {
  const { i18n } = useTranslation()
  const lang = i18n.language?.startsWith('gu') ? 'gu' : 'en'

  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        className={lang === 'en' ? 'active' : ''}
        onClick={() => i18n.changeLanguage('en')}
        type="button"
        aria-pressed={lang === 'en'}
      >
        English
      </button>
      <button
        className={lang === 'gu' ? 'active' : ''}
        onClick={() => i18n.changeLanguage('gu')}
        type="button"
        aria-pressed={lang === 'gu'}
      >
        ગુજરાતી
      </button>
    </div>
  )
}
