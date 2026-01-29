
import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { getSiteData } from './lib/site-data';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Placeholder from './pages/Placeholder';
import CriacaoDeFicha from './pages/CriacaoDeFicha';
import RegrasEPunicoes from './pages/RegrasEPunicoes';
import Glossario from './pages/Glossario';
import Missoes from './pages/Missoes';
import JogadorRaca from './pages/JogadorRaca';
import JogadorClasses from './pages/JogadorClasses';
import JogadorAntecedentes from './pages/JogadorAntecedentes';
import JogadorTalentos from './pages/JogadorTalentos';
import JogadorIdiomas from './pages/JogadorIdiomas';

// Fetch data once
const siteData = getSiteData();

const App: React.FC = () => {
  return (
    <Router>
      <div className="flex flex-col min-h-screen bg-[var(--bg0)] text-[var(--text)] selection:bg-[var(--ember)] selection:text-white">
        
        <Header 
          data={siteData.header} 
          siteName={siteData.site.name} 
          logoPath={siteData.site.logoPath}
        />

        <Routes>
          {/* Home */}
          <Route path="/" element={<Home data={siteData.home} />} />

          {/* Sistemas */}
          <Route path="/sistemas/regras-e-punicoes" element={<RegrasEPunicoes />} />
          <Route path="/sistemas/glossario" element={<Glossario />} />
          <Route path="/sistemas/criacao-de-ficha" element={<CriacaoDeFicha />} />
          <Route path="/sistemas/missoes" element={<Missoes />} />

          {/* Jogador */}
          <Route path="/jogador/raca" element={<JogadorRaca />} />
          <Route path="/jogador/classes" element={<JogadorClasses />} />
          <Route path="/jogador/antecedente" element={<JogadorAntecedentes />} />
          <Route path="/jogador/talentos" element={<JogadorTalentos />} />
          <Route path="/jogador/idiomas" element={<JogadorIdiomas />} />
          <Route path="/jogador/ferramentas" element={<Placeholder title="Ferramentas" />} />

          {/* Mestre */}
          <Route path="/mestre/se-tornando-mestre" element={<Placeholder title="Se Tornando Mestre" />} />
          <Route path="/mestre/bestiario" element={<Placeholder title="Bestiário" />} />
          <Route path="/mestre/armadilhas-e-perigos" element={<Placeholder title="Armadilhas e Perigos" />} />
          <Route path="/mestre/condicoes" element={<Placeholder title="Condições" />} />
          <Route path="/mestre/mercado-de-mestre" element={<Placeholder title="Mercado de Mestre" />} />
          <Route path="/mestre/tipos-de-missoes" element={<Placeholder title="Tipos de Missões" />} />

          {/* Mercado */}
          <Route path="/mercado/armas" element={<Placeholder title="Armas" />} />
          <Route path="/mercado/itens-mundanos" element={<Placeholder title="Itens Mundanos" />} />
          <Route path="/mercado/itens-magicos" element={<Placeholder title="Itens Mágicos" />} />
          <Route path="/mercado/negociacoes" element={<Placeholder title="Negociações" />} />
          <Route path="/mercado/veiculos" element={<Placeholder title="Veículos" />} />
          <Route path="/mercado/criaturas" element={<Placeholder title="Criaturas" />} />

          {/* Magias */}
          <Route path="/magias/escolas" element={<Placeholder title="Escolas de Magia" />} />
          <Route path="/magias/listas" element={<Placeholder title="Listas de Magias" />} />
          <Route path="/magias/congregacao" element={<Placeholder title="Congregação Mágica" />} />

          {/* Mapa */}
          <Route path="/mapa" element={<Placeholder title="Mapa Interativo" />} />

          {/* Mundo */}
          <Route path="/mundo/cosmo" element={<Placeholder title="Cosmologia" />} />
          <Route path="/mundo/linha-do-tempo" element={<Placeholder title="Linha do Tempo" />} />
          <Route path="/mundo/regioes" element={<Placeholder title="Regiões" />} />
          <Route path="/mundo/organizacoes" element={<Placeholder title="Organizações" />} />
          <Route path="/mundo/jornal" element={<Placeholder title="Jornal do Mundo" />} />

          {/* Atualizações */}
          <Route path="/atualizacoes" element={<Placeholder title="Notas de Atualização" />} />
          <Route path="/quem-somos" element={<Placeholder title="Quem Somos" />} />

          {/* CTAs */}
          <Route path="/colaborador" element={<Placeholder title="Seja um Colaborador" />} />
          <Route path="/catarse" element={<Placeholder title="Apoie no Catarse" />} />
          
          {/* External Redirect Mocks */}
          <Route path="/discord" element={<div className="p-20 text-center">Redirecting to Discord...</div>} />

          {/* 404 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        <Footer data={siteData.site} social={siteData.header.social} />
      </div>
    </Router>
  );
};

export default App;
