import { useState, FormEvent, useEffect } from 'react'
import { getApiKey, clearApiKey } from '../utils/storage'

interface HeroProps {
  onSave: (key: string) => void
}

export function Hero({ onSave }: HeroProps) {
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState('')
  const [showDocs, setShowDocs] = useState(false)
  const [existingKey, setExistingKey] = useState<string | null>(null)

  // Check for a still-valid saved key on every Hero mount
  useEffect(() => {
    const key = getApiKey()
    setExistingKey(key)
  }, [])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('Please enter your NVIDIA NIM API Key')
      return
    }
    setError('')
    onSave(apiKey)
  }

  const handleResumeSession = () => {
    if (existingKey) onSave(existingKey)
  }

  const handleClearAndReenter = () => {
    clearApiKey()
    setExistingKey(null)
  }

  return (
    <div className="h-screen flex flex-col selection:bg-primary selection:text-surface overflow-hidden">
      {/* TopAppBar */}
      <header className="bg-white dark:bg-black text-black dark:text-white flex justify-between items-center w-full px-3 max-w-full mx-auto fixed top-0 border-b border-black dark:border-white z-50 h-8">
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 50 50" aria-label="ATS Refactor" className="dark:invert">
            <path d="M 2.0996094 6.9609375 L 2.0996094 42.939453 L 27.550781 42.939453 L 29.679688 42.939453 L 48 42.939453 L 48 6.9609375 L 29.039062 6.9609375 L 26.599609 6.9609375 L 2.0996094 6.9609375 z M 27.679688 8.9609375 L 46 8.9609375 L 46 40.939453 L 29.009766 40.939453 C 28.739766 39.989453 28.540391 39.020781 28.400391 38.050781 C 28.290391 37.280781 28.229453 36.530547 28.189453 35.810547 L 28.189453 35.800781 C 28.197008 35.799475 28.20345 35.796383 28.210938 35.794922 C 28.213204 35.858583 28.208154 35.916455 28.210938 35.980469 C 28.870937 35.940469 29.529453 35.890547 30.189453 35.810547 C 33.709453 35.400547 37.179688 34.469062 40.429688 33.039062 L 39.630859 31.210938 C 36.640859 32.520937 33.450937 33.389063 30.210938 33.789062 C 29.550938 33.869062 28.880938 33.940469 28.210938 33.980469 C 28.21 34.000469 28.211816 34.02291 28.210938 34.042969 C 28.207058 34.04213 28.203118 34.041812 28.199219 34.041016 C 28.199457 34.034135 28.198978 34.026406 28.199219 34.019531 C 28.199219 33.999531 28.200937 33.990469 28.210938 33.980469 C 28.200937 33.910469 28.210938 33.849063 28.210938 33.789062 C 28.300938 32.099063 28.580156 30.600313 28.910156 29.320312 C 28.960156 29.130312 29.010547 28.949297 29.060547 28.779297 C 29.070547 28.769297 29.070078 28.750469 29.080078 28.730469 C 29.210078 28.270469 29.36 27.839453 29.5 27.439453 L 29.990234 26.099609 L 29.966797 26.099609 L 21.25 26.099609 C 21.83 22.079609 22.980156 18.180469 24.660156 14.480469 C 25.530156 12.570469 26.529688 10.720937 27.679688 8.9609375 z M 11.910156 13.972656 L 13.947266 13.972656 C 13.948266 15.658656 13.950172 17.34425 13.951172 19.03125 C 13.267172 19.02625 12.582437 19.021625 11.898438 19.015625 C 11.901438 17.334625 11.906156 15.653656 11.910156 13.972656 z M 34.009766 14.009766 L 34.009766 18.980469 L 35.875 18.980469 L 35.875 14.009766 L 34.009766 14.009766 z M 10.365234 31.150391 C 14.376234 32.920391 18.626281 33.889297 22.988281 34.029297 C 24.051281 34.059297 25.115734 34.050469 26.177734 33.980469 C 26.147734 34.620469 26.147734 35.290469 26.177734 35.980469 C 25.465734 36.030469 24.74225 36.050781 24.03125 36.050781 C 23.66025 36.050781 23.300687 36.039297 22.929688 36.029297 C 18.307688 35.879297 13.804734 34.860469 9.5527344 32.980469 L 10.365234 31.150391 z"/>
          </svg>
          <span className="text-sm font-black tracking-tighter uppercase text-black dark:text-white font-headline">ATS Refactor</span>
        </div>
        <div className="flex gap-2 items-center">
          <button
            className="hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors p-1"
            onClick={() => setShowDocs(!showDocs)}
          >
            <span className="material-symbols-outlined text-base leading-none">help</span>
          </button>
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center pt-16 pb-4 px-4 md:px-0 relative overflow-y-auto">
        {/* Dither background */}
        <div
          className="fixed inset-0 pointer-events-none -z-10"
          style={{
            backgroundImage: 'radial-gradient(#000000 0.5px, transparent 0.5px)',
            backgroundSize: '2px 2px',
            opacity: 0.1,
          }}
        />

        {/* Main Window */}
        <div className="w-full max-w-2xl bg-[#f9f9f9] border border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)] relative my-auto">
          {/* Window Title Bar */}
          <div className="h-8 border-b border-black flex items-center px-2 bg-[#e2e2e2] relative">
            {/* Close Box */}
            <div className="w-4 h-4 border border-black bg-[#f9f9f9] flex items-center justify-center cursor-pointer" style={{ boxShadow: 'inset 1px 1px 0px 0px #ffffff, inset -1px -1px 0px 0px #000000' }}>
              <div className="w-2 h-[1px] bg-black" />
            </div>
            {/* Window Title */}
            <div className="flex-grow h-full flex items-center justify-center relative mx-4">
              <div
                className="absolute inset-0"
                style={{
                  background: 'repeating-linear-gradient(0deg, transparent, transparent 1px, #000000 1px, #000000 2px)',
                  backgroundSize: '100% 3px',
                  opacity: 0.15,
                }}
              />
              <span className="relative z-10 bg-[#e2e2e2] px-4 text-[10px] font-bold uppercase tracking-[0.2em] font-headline text-black">
                System Session : ATS_Engine.app
              </span>
            </div>
          </div>

          {/* Window Content */}
          <div className="p-6 md:p-8 text-left relative">
            {/* Decorative background image */}
            <div className="absolute right-0 top-0 w-32 h-full opacity-5 pointer-events-none">
              <div className="w-full h-full bg-gradient-to-b from-neutral-400 to-neutral-200" />
            </div>

            <div className="relative z-10">
              <h1 className="text-4xl md:text-5xl font-black uppercase tracking-tighter font-headline leading-none mb-4 text-black">
                ATS Resume<br />Refactoring Engine
              </h1>
              <p className="text-lg font-body text-neutral-600 max-w-md mb-5 border-l-2 border-black pl-4 py-1 italic">
                Tailor your resume to any job description instantly using AI.
              </p>

              {/* Docs Panel */}
              {showDocs && (
                <div className="mb-8 p-4 bg-neutral-100 border border-black">
                  <h3 className="font-headline font-bold uppercase text-sm mb-2">Documentation</h3>
                  <p className="text-sm text-neutral-600 mb-2">
                    1. Obtain a free NVIDIA NIM API key from{' '}
                    <a href="https://build.nvidia.com/explore" target="_blank" rel="noopener noreferrer" className="underline text-blue-600">
                      build.nvidia.com
                    </a>
                  </p>
                  <p className="text-sm text-neutral-600 mb-2">
                    2. Your key is stored locally in your browser and expires after 24 hours.
                  </p>
                  <p className="text-sm text-neutral-600">
                    3. We never transmit your raw API credentials to our servers.
                  </p>
                </div>
              )}

              {existingKey ? (
                /* ── Resume Session ── */
                <div className="max-w-md space-y-6">
                  <div className="space-y-1">
                    <span className="text-xs font-bold uppercase tracking-widest text-black">Active Session Detected</span>
                    <p className="text-sm font-body text-neutral-600">
                      A valid API key is saved and has not expired. You can resume your session instantly.
                    </p>
                  </div>

                  <div className="p-4 bg-neutral-100 border border-black flex items-center gap-3"
                    style={{ boxShadow: 'inset 1px 1px 0px 0px #000000' }}>
                    <span className="material-symbols-outlined text-black" style={{ fontVariationSettings: "'FILL' 1" }}>key</span>
                    <span className="text-xs font-mono text-neutral-700 tracking-widest">
                      {existingKey.slice(0, 10)}{'•'.repeat(12)}
                    </span>
                    <span className="ml-auto text-[10px] font-bold uppercase text-green-700 bg-green-100 border border-green-400 px-1">Valid</span>
                  </div>

                  <div className="flex flex-col md:flex-row gap-4">
                    <button
                      onClick={handleResumeSession}
                      className="bg-black text-white px-8 py-4 font-headline font-bold uppercase tracking-widest text-sm hover:opacity-90 active:scale-95 transition-all flex items-center justify-center gap-2"
                      style={{ boxShadow: 'inset 1px 1px 0px 0px #ffffff, inset -1px -1px 0px 0px #000000' }}
                    >
                      Continue
                      <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                    <button
                      onClick={handleClearAndReenter}
                      className="bg-transparent border border-black text-black px-8 py-4 font-headline font-bold uppercase tracking-widest text-sm hover:bg-neutral-200 transition-all active:scale-95"
                    >
                      Reset Key
                    </button>
                  </div>
                </div>
              ) : (
                /* ── New Key Form ── */
                <form onSubmit={handleSubmit} className="space-y-6 max-w-md">
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-widest block text-black">
                      Configuration Required
                    </label>
                    <p className="text-sm leading-relaxed text-neutral-600 font-body">
                      Please enter your <span className="font-bold">NVIDIA NIM API Key</span> to begin. Your key is stored securely in your browser and expires daily.
                    </p>
                  </div>

                  {/* API Key Input */}
                  <div className="relative">
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="nvapi-xxxxxxxxxxxxxxxxxxxxxxxx"
                      className="w-full bg-white border border-black p-4 text-black font-body tracking-widest placeholder:opacity-30 focus:ring-0 focus:outline-none transition-all"
                      style={{ boxShadow: 'inset -1px -1px 0px 0px #ffffff, inset 1px 1px 0px 0px #000000' }}
                    />
                  </div>

                  {/* Error Message */}
                  {error && (
                    <div className="text-red-600 text-sm font-mono">{error}</div>
                  )}

                  {/* Action Buttons */}
                  <div className="pt-4 flex flex-col md:flex-row gap-4">
                    <button
                      type="submit"
                      className="bg-black text-white px-8 py-4 font-headline font-bold uppercase tracking-widest text-sm hover:opacity-90 active:scale-95 transition-all flex items-center justify-center gap-2"
                      style={{ boxShadow: 'inset 1px 1px 0px 0px #ffffff, inset -1px -1px 0px 0px #000000' }}
                    >
                      Save & Continue
                      <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowDocs(!showDocs)}
                      className="bg-transparent border border-black text-black px-8 py-4 font-headline font-bold uppercase tracking-widest text-sm hover:bg-neutral-200 transition-all active:scale-95"
                    >
                      Documentation
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Footer Stats */}
            <div className="mt-6 flex items-end justify-between border-t border-black/20 pt-3 text-[10px] uppercase font-bold tracking-tighter opacity-60 text-black">
              <div>
                Ver: 1.0.84-Alpha<br />
                Enc: AES-256-Local
              </div>
              <div className="text-right">
                System Status: READY<br />
                Memory: 640K REQ.
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-[#f4f3f3] dark:bg-neutral-900 text-black dark:text-white flex flex-col md:flex-row justify-between items-center w-full px-8 py-3 border-t border-black dark:border-white">
        <div className="text-sm font-bold text-black dark:text-white font-headline flex-1">
          Developer: SAURAV KALASKAR
        </div>
        <div className="flex gap-6 mt-4 md:mt-0">
          <a
            href="#"
            className="text-xs uppercase tracking-widest font-body text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white transition-colors"
          >
            API Docs
          </a>
          <a
            href="https://build.nvidia.com/explore"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs uppercase tracking-widest font-body text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white transition-colors"
          >
            NVIDIA NIM
          </a>
        </div>
        <div className="text-xs uppercase tracking-widest font-body text-neutral-600 dark:text-neutral-400 mt-4 md:mt-0 flex-1 md:text-right">
          © 2026 ATS Refactor. All rights reserved.
        </div>
      </footer>
    </div>
  )
}
