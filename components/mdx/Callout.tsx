
import React from 'react';
import { Info, AlertTriangle, CheckCircle, AlertOctagon } from 'lucide-react';

interface CalloutProps {
  type?: 'info' | 'warning' | 'success' | 'danger';
  title?: string;
  children: React.ReactNode;
}

const Callout: React.FC<CalloutProps> = ({ type = 'info', title, children }) => {
  const styles = {
    info: {
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/50',
      text: 'text-blue-400',
      icon: <Info className="w-5 h-5" />
    },
    warning: {
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/50',
      text: 'text-amber-400',
      icon: <AlertTriangle className="w-5 h-5" />
    },
    success: {
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/50',
      text: 'text-emerald-400',
      icon: <CheckCircle className="w-5 h-5" />
    },
    danger: {
      bg: 'bg-red-500/10',
      border: 'border-red-500/50',
      text: 'text-red-400',
      icon: <AlertOctagon className="w-5 h-5" />
    }
  };

  const s = styles[type];

  return (
    <div className={`my-6 p-4 rounded-lg border-l-4 ${s.bg} ${s.border} animate-in fade-in slide-in-from-left-2`}>
      <div className="flex gap-3">
        <div className={s.text}>{s.icon}</div>
        <div className="flex-1">
          {title && <h4 className={`font-bold text-sm uppercase tracking-wider mb-1 ${s.text}`}>{title}</h4>}
          <div className="text-sm text-[var(--text)] opacity-90 leading-relaxed">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Callout;
