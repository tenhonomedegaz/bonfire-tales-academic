
import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';

interface CopyBlockProps {
  title: string;
  content: string;
}

const CopyBlock: React.FC<CopyBlockProps> = ({ title, content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-6 border border-[var(--stroke)] rounded-lg bg-[var(--bg0)] overflow-hidden shadow-xl">
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg2)] border-b border-[var(--stroke)]">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[var(--muted)]" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">{title}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-[var(--muted)] hover:text-[var(--text)] transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
          {copied ? 'Copiado!' : 'Copiar'}
        </button>
      </div>
      <div className="p-4 overflow-x-auto">
        <pre className="text-xs font-mono text-[var(--muted)] whitespace-pre-wrap leading-relaxed selection:bg-[var(--ember)] selection:text-white">
          {content}
        </pre>
      </div>
    </div>
  );
};

export default CopyBlock;
