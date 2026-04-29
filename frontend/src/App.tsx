import { useState, useRef, FormEvent, ChangeEvent } from 'react'
import { FileText, Upload, Loader2, Download, Sparkles, FileCheck, ChevronDown, ChevronUp, Monitor } from 'lucide-react'
import './App.css'

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
  const [showPreview, setShowPreview] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
      <header className="header">
        <div className="container header-content">
          <h1 className="title">
            <Sparkles className="icon" size={28} />
            ATS Resume Refactoring Engine
          </h1>
          <p className="subtitle">
            Tailor your resume for any job using AI
          </p>
        </div>
      </header>

      <main className="container main">
        <div className="grid">
          {/* Left panel - Input */}
          <div className="card input-card">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="label">
                  <FileText size={16} />
                  Job Description
                </label>
                <textarea
                  className="textarea"
                  placeholder="Paste the job description here..."
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  rows={12}
                />
                <div className="char-count">
                  {jdText.length} characters
                </div>
              </div>

              <div className="form-group">
                <label className="label">
                  <Upload size={16} />
                  Base Resume (LaTeX)
                </label>
                <div
                  className="file-dropzone"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".tex"
                    onChange={handleFileUpload}
                    hidden
                  />
                  {baseResume ? (
                    <span className="file-label">
                      <FileCheck size={20} />
                      Resume loaded ({baseResume.length} chars)
                    </span>
                  ) : (
                    <span className="file-label">
                      <Upload size={20} />
                      Click to upload resume.tex
                    </span>
                  )}
                </div>
                <p className="help-text">
                  Uses default template if none uploaded
                </p>
              </div>

              {error && (
                <div className="error-box">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
              >
                {loading ? (
                  <>
                    <Loader2 className="spin" size={18} />
                    Refactoring...
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    Refactor Resume
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Right panel - Results */}
          <div className="card result-card">
            {result ? (
              <div className="results">
                <div className="result-header">
                  <h2 className="result-title">
                    <FileCheck size={20} />
                    Refactored Resume
                  </h2>
                  <div className="stats">
                    <span className="stat">
                      {result.bullets_applied} bullets
                    </span>
                    <span className="stat">
                      {result.keywords_found.length} keywords
                    </span>
                  </div>
                </div>

                {result.keywords_found.length > 0 && (
                  <div className="keywords-section">
                    <h3 className="keywords-title">Keywords highlighted:</h3>
                    <div className="keywords-list">
                      {result.keywords_found.slice(0, 12).map((kw) => (
                        <span key={kw} className="keyword-tag">
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="preview-toggle">
                  <button
                    className="toggle-btn"
                    onClick={() => setShowPreview(!showPreview)}
                  >
                    <Monitor size={16} />
                    {showPreview ? 'Hide' : 'Show'} Preview
                    {showPreview ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {showPreview && (
                  <div className="pdf-preview">
                    <object
                      data={`data:application/pdf;base64,${result.pdf_base64}`}
                      type="application/pdf"
                      width="100%"
                      height="600px"
                    >
                      <p>Your browser does not support PDF preview.</p>
                    </object>
                  </div>
                )}


                <div className="actions">
                  <button
                    className="btn btn-primary"
                    onClick={downloadPDF}
                  >
                    <Download size={16} />
                    Download PDF
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={downloadLatex}
                  >
                    <Monitor size={16} />
                    Download LaTeX
                  </button>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <FileText size={64} className="empty-icon" />
                <p className="empty-text">
                  Your refactored resume will appear here
                </p>
                <p className="empty-subtext">
                  Paste a job description and click Refactor
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
