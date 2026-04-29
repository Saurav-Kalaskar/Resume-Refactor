import React, { ChangeEvent, FormEvent } from 'react';

interface RefactorResponse {
  status: string;
  message: string;
  pdf_base64: string;
  latex_source: string;
  bullets_applied: number;
  keywords_found: string[];
  company_name?: string;
}

interface AppContentProps {
  jdText: string;
  setJdText: (val: string) => void;
  baseResume: string;
  setBaseResume: (val: string) => void;
  handleFileUpload: (e: ChangeEvent<HTMLInputElement>) => void;
  handleSubmit: (e: FormEvent) => void;
  loading: boolean;
  error: string;
  result: RefactorResponse | null;
  downloadPDF: () => void;
  downloadLatex: () => void;
}

export const AppContent: React.FC<AppContentProps> = ({
  jdText,
  setJdText,
  baseResume,
  handleFileUpload,
  handleSubmit,
  loading,
  error,
  result,
  downloadPDF,
  downloadLatex
}) => {
  return (
    <>
      {/* Configuration Panel */}
      <div className="md:col-span-1 flex flex-col gap-4">
        <div className="border border-outline-variant/20 p-4 relative pt-6 bg-surface-container-low">
          <span className="absolute -top-3 left-2 bg-surface-container-low px-1 font-headline text-xs uppercase font-bold text-primary">Configuration</span>
          <form className="space-y-4" onSubmit={handleSubmit}>
            {/* Target Job Description */}
            <div className="flex flex-col gap-1">
              <label className="font-label text-xs uppercase tracking-widest text-primary">Target Job Description</label>
              <div className="relative">
                <textarea 
                  className="w-full bg-surface-container-lowest border border-primary text-sm font-body px-2 py-1 shadow-[2px_2px_0px_0px_rgba(0,0,0,0.2)] focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)] transition-shadow" 
                  style={{ borderTopColor: '#fff', borderLeftColor: '#fff', borderRightColor: '#000', borderBottomColor: '#000', borderWidth: '1px' }} 
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  rows={4}
                  required
                />
              </div>
            </div>
            
            {/* File Upload */}
            <div className="flex flex-col gap-1 pt-2">
              <label className="font-label text-xs uppercase tracking-widest text-primary">Base Resume (Optional)</label>
              <label className="cursor-pointer border border-primary border-dashed p-2 text-center bg-surface-container-lowest shadow-[inset_1px_1px_0px_0px_rgba(0,0,0,0.1)] hover:bg-surface transition-colors" style={{ borderTopColor: '#000', borderLeftColor: '#000', borderRightColor: '#fff', borderBottomColor: '#fff' }}>
                  <span className="text-xs font-body font-bold">{baseResume ? 'Resume Loaded ✓' : 'Click to Upload (.txt, .tex)'}</span>
                  <input type="file" accept=".txt,.tex" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>

            {error && <div className="text-xs font-bold text-error mt-2">{error}</div>}

            {/* Button */}
            <div className="pt-4">
              <button 
                className="w-full bg-surface border border-primary font-headline uppercase text-sm font-bold py-1 px-4 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyIiBoZWlnaHQ9IjIiPjxyZWN0IHdpZHRoPSIxIiBoZWlnaHQ9IjEiIGZpbGw9IiMwMDAiLz48cmVjdCB4PSIxIiB5PSIxIiB3aWR0aD0iMSIgaGVpZ2h0PSIxIiBmaWxsPSIjMDAwIi8+PC9zdmc+')] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] active:translate-y-[1px] active:translate-x-[1px] transition-all disabled:opacity-50" 
                style={{ borderTopColor: '#fff', borderLeftColor: '#fff', borderRightColor: '#000', borderBottomColor: '#000' }} 
                type="submit"
                disabled={loading}
              >
                {loading ? 'Processing...' : 'Refactor'}
              </button>
            </div>
          </form>
        </div>

        {/* Status Box */}
        <div className="border border-outline-variant/20 p-2 bg-surface-container-high flex flex-col gap-1 mt-auto">
          <span className="font-headline text-[10px] uppercase font-bold text-primary">System Status</span>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>memory</span>
            <span className="text-xs font-body">{loading ? 'Refactoring in progress...' : result ? 'Task completed successfully.' : 'Ready for processing...'}</span>
          </div>
        </div>
      </div>

      {/* Preview Area */}
      <div className="md:col-span-2 border border-primary bg-surface-container-low relative p-4 flex flex-col">
        <span className="absolute -top-3 left-4 bg-surface px-2 border border-primary font-headline text-xs uppercase font-bold text-primary z-10 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">Preview Document</span>
        
        <div className="flex-1 bg-surface-container-lowest border border-outline-variant/20 shadow-[inset_2px_2px_0px_0px_rgba(0,0,0,0.1)] p-6 overflow-y-auto font-body text-sm leading-relaxed relative flex flex-col">
          {loading ? (
            <div className="flex-1 flex items-center justify-center font-headline text-primary animate-pulse">Processing Document...</div>
          ) : result ? (
            <>
              <div className="flex justify-end gap-2 mb-4">
                <button onClick={downloadLatex} className="border border-primary bg-surface px-2 py-1 text-xs font-bold uppercase shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] hover:bg-surface-container-high active:shadow-none active:translate-y-[1px] active:translate-x-[1px]">.TEX</button>
                <button onClick={downloadPDF} className="border border-primary bg-surface px-2 py-1 text-xs font-bold uppercase shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] hover:bg-surface-container-high active:shadow-none active:translate-y-[1px] active:translate-x-[1px]">PDF</button>
              </div>
              <div className="flex-1">
                <iframe 
                  src={`data:application/pdf;base64,${result.pdf_base64}`}
                  width="100%"
                  height="100%"
                  style={{ border: '1px solid black', backgroundColor: '#fff', minHeight: '500px' }}
                  title="PDF Preview"
                />
              </div>
              <div className="mt-4 pt-4 border-t border-primary/20 text-xs font-bold flex justify-between">
                <span>{result.bullets_applied} Bullets Refactored</span>
                <span>{result.keywords_found?.length || 0} Keywords Injected</span>
              </div>
            </>
          ) : (
            <div className="text-center text-outline mt-10">
              Submit a job description to preview the tailored resume here.
            </div>
          )}
        </div>
      </div>
    </>
  );
};
