import React from 'react';

export const MacWindow: React.FC<{ children: React.ReactNode; title?: string }> = ({ children, title = "Dashboard" }) => {
  return (
    <>
      <header className="bg-white flex justify-between items-center px-2 w-full fixed top-0 z-50 h-8 border-b border-black shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex items-center gap-4">
          <div className="font-headline font-black text-lg tracking-tighter text-black flex items-center gap-1">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>ios</span>
          </div>
          <nav className="flex items-center gap-2">
            <a className="bg-black text-white px-2 py-1 font-headline uppercase tracking-tighter text-sm font-bold cursor-pointer active:invert" href="#">Dashboard</a>
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <button className="text-black px-2 py-1 hover:bg-zinc-200 transition-colors duration-75 cursor-pointer active:invert flex items-center justify-center">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>settings</span>
          </button>
          <button className="text-black px-2 py-1 hover:bg-zinc-200 transition-colors duration-75 cursor-pointer active:invert flex items-center justify-center">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>help</span>
          </button>
        </div>
      </header>

      <main className="flex-1 mt-12 p-4 md:p-8 flex justify-center items-start">
        {/* Classic Desktop Window */}
        <div className="bg-surface w-full max-w-4xl border border-primary shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)] flex flex-col relative">
          
          {/* Title Bar */}
          <div className="h-6 border-b border-primary bg-surface-container-highest flex items-center justify-center relative window-title-bar px-1">
            <div className="absolute left-1 top-1 h-3 w-3 border border-primary bg-surface flex items-center justify-center cursor-pointer active:invert">
              {/* Close Box */}
            </div>
            <div className="bg-surface px-2 border border-primary font-headline uppercase tracking-tighter text-xs font-bold z-10 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">
              {title}
            </div>
          </div>

          {/* Window Content */}
          <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4 h-full bg-surface">
            {children}
          </div>

          {/* Resize handler mockup */}
          <div className="absolute bottom-0 right-0 w-3 h-3 border-t border-l border-primary bg-surface cursor-se-resize"></div>
        </div>
      </main>
    </>
  );
};
