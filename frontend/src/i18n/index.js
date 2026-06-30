import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './en.json'
import gu from './gu.json'

i18n
  .use(LanguageDetector) // remembers choice in localStorage
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      gu: { translation: gu },
    },
    fallbackLng: 'en',
    supportedLngs: ['en', 'gu'],
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  })

export default i18n
