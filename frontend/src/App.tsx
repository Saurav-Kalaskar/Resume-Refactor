import { useState, useEffect, FormEvent, ChangeEvent } from 'react'
import { MacWindow } from './components/MacWindow'
import { AppContent } from './components/AppContent'
import { Hero } from './components/Hero'
import { saveApiKey, getApiKey } from './utils/storage'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// sessionStorage keys
const SS_JD = 'ats_jdText'
const SS_BASE_RESUME = 'ats_baseResume'
const SS_ORIGINAL_BASE_RESUME = 'ats_originalBaseResume'
const SS_RESULT = 'ats_result'
const SS_COMPANY = 'ats_companyName'

interface RefactorResponse {
  status: string
  message: string
  pdf_base64: string
  latex_source: string
  bullets_applied: number
  keywords_found: string[]
  company_name?: string
}

// Helpers to read/write sessionStorage safely
function ssGet<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(key)
    return raw !== null ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function ssSet(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage quota exceeded (e.g. large PDF) — fail silently
  }
}

function ssRemove(key: string) {
  try {
    sessionStorage.removeItem(key)
  } catch {
    // Ignore errors
  }
}

export default function App() {
  const [jdText, setJdText] = useState<string>(() => ssGet(SS_JD, ''))
  const [companyName, setCompanyName] = useState<string>(() => ssGet(SS_COMPANY, ''))
  const [baseResume, setBaseResume] = useState<string>(() => ssGet(SS_BASE_RESUME, ''))
  const [originalBaseResume, setOriginalBaseResume] = useState<string>(() => ssGet(SS_ORIGINAL_BASE_RESUME, ''))
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RefactorResponse | null>(() => ssGet<RefactorResponse | null>(SS_RESULT, null))
  const [error, setError] = useState('')
  const [hasKey, setHasKey] = useState(false)

  // Check for existing valid API key on mount
  useEffect(() => {
    const key = getApiKey()
    setHasKey(!!key)
  }, [])

  // Sync state to sessionStorage on every change
  useEffect(() => { ssSet(SS_JD, jdText) }, [jdText])
  useEffect(() => { ssSet(SS_BASE_RESUME, baseResume) }, [baseResume])
  useEffect(() => { ssSet(SS_ORIGINAL_BASE_RESUME, originalBaseResume) }, [originalBaseResume])
  useEffect(() => { ssSet(SS_RESULT, result) }, [result])
  useEffect(() => { ssSet(SS_COMPANY, companyName) }, [companyName])

  const handleSaveKey = (key: string) => {
    saveApiKey(key)
    setHasKey(true)
  }

  // Exit to hero WITHOUT clearing the stored key — user can re-enter without re-typing
  const handleGoHome = () => {
    setHasKey(false)
    setError('')
  }

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setBaseResume(text)
    setOriginalBaseResume(text) // Store immutable copy
  }

  const handleReset = () => {
    // Clear all form states
    setJdText('')
    setCompanyName('')
    setBaseResume('')
    setOriginalBaseResume('')
    setResult(null)
    setError('')

    // Clear sessionStorage
    ssRemove(SS_JD)
    ssRemove(SS_COMPANY)
    ssRemove(SS_BASE_RESUME)
    ssRemove(SS_ORIGINAL_BASE_RESUME)
    ssRemove(SS_RESULT)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!jdText.trim()) {
      setError('Please enter a job description')
      return
    }

    const apiKey = getApiKey()
    if (!apiKey) {
      setError('Session expired. Please re-enter your API key.')
      setHasKey(false)
      return
    }

    // Clear previous result and company name for new request
    setResult(null)
    setCompanyName('')
    setError('')
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/api/v1/refactor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-NVIDIA-API-KEY': apiKey,
        },
        body: JSON.stringify({
          job_description: jdText,
          base_resume_tex: originalBaseResume || undefined, // Always send original
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to refactor resume')
      }

      setResult(data)
      if (data.company_name) {
        setCompanyName(data.company_name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const sanitizeFilename = (input: string): string =>
    input.trim().replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '_')

  const getFilename = (extension: string): string => {
    const name = companyName.trim()
      ? `Saurav_Kalaskar_Resume_${sanitizeFilename(companyName)}.${extension}`
      : `Saurav_Kalaskar_Resume.${extension}`
    return name
  }

  const downloadPDF = () => {
    if (!result?.pdf_base64) return
    const binary = atob(result.pdf_base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    const blob = new Blob([bytes], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = getFilename('pdf')
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }

  const downloadLatex = () => {
    if (!result?.latex_source) return
    const blob = new Blob([result.latex_source], { type: 'application/x-tex' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = getFilename('tex')
    a.click()
    window.URL.revokeObjectURL(url)
  }

  if (!hasKey) {
    return <Hero onSave={handleSaveKey} />
  }

  return (
    <div className="min-h-screen">
      <MacWindow onGoHome={handleGoHome}>
        <AppContent
          jdText={jdText}
          setJdText={setJdText}
          baseResume={baseResume}
          setBaseResume={setBaseResume}
          handleFileUpload={handleFileUpload}
          handleSubmit={handleSubmit}
          handleReset={handleReset}
          loading={loading}
          error={error}
          result={result}
          downloadPDF={downloadPDF}
          downloadLatex={downloadLatex}
        />
      </MacWindow>
    </div>
  )
}
