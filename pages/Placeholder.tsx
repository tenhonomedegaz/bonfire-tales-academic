import React from 'react';
import { Link } from 'react-router-dom';
import { Hammer, ArrowLeft } from 'lucide-react';

interface PlaceholderProps {
  title: string;
}

const Placeholder: React.FC<PlaceholderProps> = ({ title }) => {
  return (
    <div className="flex-1 min-h-[60vh] flex flex-col items-center justify-center p-4 text-center">
      <div className="w-16 h-16 rounded-full bg-[var(--bg1)] border border-[var(--stroke)] flex items-center justify-center mb-6">
        <Hammer className="w-8 h-8 text-[var(--muted)]" />
      </div>
      
      <h1 className="font-rpg text-3xl md:text-4xl font-bold text-[var(--text)] mb-4">
        {title}
      </h1>
      
      <p className="text-[var(--muted)] max-w-md mb-8">
        Esta página está em construção. O grimório está sendo escrito pelos escribas.
      </p>
      
      <Link 
        to="/"
        className="inline-flex items-center gap-2 text-[var(--ember)] hover:text-[var(--flame)] font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Voltar para a Fogueira
      </Link>
    </div>
  );
};

export default Placeholder;