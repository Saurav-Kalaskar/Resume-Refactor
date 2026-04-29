import { useState, FormEvent, ChangeEvent } from 'react';
import { MacWindow } from './components/MacWindow';
import { AppContent } from './components/AppContent';


// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface RefactorResponse {
  status: string
  message: string
  pdf_base64: string
  latex_source: string
  bullets_applied: number
  keywords_found: string[]
  company_name?: string
}

export default function App() {
  const [jdText, setJdText] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [baseResume, setBaseResume] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RefactorResponse | null>(null)
  const [error, setError] = useState('')


  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const text = await file.text()
    setBaseResume(text)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!jdText.trim()) {
      setError('Please enter a job description')
      return
    }

    setLoading(true)
    setError('')

    try {
      const res = await fetch(`${API_URL}/api/v1/refactor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_description: jdText,
          base_resume_tex: baseResume || undefined,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to refactor resume')
      }

      setResult(data)
      // Set company name from LLM-extracted value
      if (data.company_name) {
        setCompanyName(data.company_name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const sanitizeFilename = (input: string): string => {
    // Remove illegal filename characters and replace spaces with underscores
    return input
      .trim()
      .replace(/[<>:"/\\|?*]/g, '')
      .replace(/\s+/g, '_')
  }

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
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
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

  return (
    <div className="min-h-screen">
      <MacWindow>
        <AppContent
          jdText={jdText}
          setJdText={setJdText}
          baseResume={baseResume}
          setBaseResume={setBaseResume}
          handleFileUpload={handleFileUpload}
          handleSubmit={handleSubmit}
          loading={loading}
          error={error}
          result={result}
          downloadPDF={downloadPDF}
          downloadLatex={downloadLatex}
        />
      </MacWindow>
    </div>
  );
}