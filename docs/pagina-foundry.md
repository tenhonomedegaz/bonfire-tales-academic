# Arquitetura da página Foundry

Escopo autorizado da frente 3: definir a página pública de distribuição e orientação em português. Este documento não autoriza publicar um pacote Foundry, oferecer downloads, implantar o adaptador de personagens nem vender conteúdo.

## Estado verificado e fronteira

- `home/urls.py` não possui rota Foundry. O exportador existente é o comando administrativo `home/management/commands/export_personagem_vtt.py`, com JSON Bonfire versionado; ele não produz um pacote instalável do Foundry.
- O checkout local `bonfire-vtt` não apresenta `module.json` ou `system.json`. Isso não identifica nem descarta o sistema privado mencionado na seção 13 da arquitetura; a identidade, a licença e a compatibilidade desse pacote precisam ser confirmadas antes de anunciar instalação.
- A página não expõe exportações privadas, dados de personagens ou direitos premium. Construção e economia ficam no Bonfire; estado de mesa fica no Foundry, conforme a seção 13.

## Rota e estrutura proposta

Reservar `GET /foundry/` como página pública somente de leitura, no layout base do site. O título e a navegação devem distinguir “Foundry” do VTT próprio. Enquanto não houver release auditada, a página pode explicar o projeto e seu estado, mas não deve exibir botão de instalação ou URL de manifest fictícia.

Ordem do conteúdo:

1. **Apresentação e estado**: o que a integração pretende permitir, com selo inequívoco “Em preparação” ou “Disponível”. Uma frase informa que a ficha oficial continua no Bonfire.
2. **O que funciona hoje**: somente capacidades demonstradas em uma versão publicada; separar delas os recursos planejados (compêndios, importação, temas e direitos premium).
3. **Instalação**, apenas no estado disponível: URL do manifest copiável, tipo de pacote (sistema ou módulo), versões do Foundry testadas, versão do pacote, data da release e instruções PT-BR em passos curtos. Identificar requisitos adicionais se for módulo.
4. **Versões e mudanças**: release atual e histórico com notas, compatibilidade, checksum dos arquivos e downloads imutáveis por versão. O manifest estável aponta para a release atual auditada; versões antigas permanecem identificáveis.
5. **Personagens e limites**: explicar importação em sentido único e contrato JSON Bonfire; avisar que nova importação só atualiza campos gerenciados pelo adaptador e que notas e estado local da mesa não são sincronizados. Mostrar limitações conhecidas antes de qualquer ação de importar.
6. **Ajuda e procedência**: origem/licença do conteúdo distribuído, instruções de atualização, canal de suporte e link para notas de versão. Evitar promessas de acesso premium antes de validar autenticação, revogação e instalação.

Em tela estreita, manter versão/compatibilidade junto ao CTA de instalação, passos em coluna única e URL copiável sem rolagem horizontal. Todos os estados e erros precisam de texto, além de cor; o foco do teclado deve alcançar links e botão de cópia.

## Fonte de verdade e publicação

O catálogo de releases da página é editorial, com campos mínimos: `version`, `package_type`, `manifest_url`, `download_url`, `foundry_versions_tested`, `released_at`, `changelog`, `sha256`, `license_summary` e `verified_by`. São metadados de uma release já inspecionada, não valores a inferir do diretório `bonfire-vtt` ou do exportador JSON. Um registro em rascunho não gera links públicos. Publicar requer artefato imutável acessível, manifest coerente, checksum conferido, instalação testada e autorização editorial; retirar uma release revoga o CTA sem apagar o histórico de versões.

A URL estável do manifest e os downloads versionados pertencem ao processo de distribuição do pacote, não à resposta dinâmica da página. A página lê apenas metadados publicados e trata falha temporária da fonte de releases exibindo estado indisponível, sem inventar compatibilidade ou redirecionar para um arquivo arbitrário. Nenhum segredo ou token pessoal entra em HTML, manifest ou cache público.

## Portões e critérios de aceite da futura página

1. **Sem release auditada**: visitante anônimo recebe página PT-BR com estado “Em preparação”, limites claros e nenhum CTA/URL de instalação; rotas privadas de ficha continuam protegidas.
2. **Com release publicada**: página e manifest apontam à mesma versão; tipo de pacote, versões testadas, changelog, checksum e arquivo imutável são verificáveis. Instalação pela URL do manifest passa na versão declarada do Foundry.
3. **Atualização**: uma versão posterior pode ser instalada sem perder mundo existente; histórico e downloads antigos permanecem rastreáveis. Falha de artefato/manifest retira o CTA e mostra erro seguro.
4. **Personagens**: texto e fluxo anunciam somente importação unidirecional; importar duas vezes não duplica itens e preserva notas/estado de mesa, com limitações explícitas. Os casos simples, conjurador, multiclasse e Caçador versionado são testados antes de anunciá-los.
5. **Acesso**: instalação básica e conteúdo gratuito funcionam sem login Bonfire; premium só aparece após mecanismo compatível com Foundry, vínculo forte de conta e revogação testados. Ausência de rede não impede abrir o conteúdo básico já instalado.
6. **Apresentação**: desktop e viewport móvel passam por inspeção visual de hierarquia, leitura, foco por teclado, cópia da URL e mensagens de erro.

Esses critérios são de implementação e QA futuros. Este documento fecha somente a arquitetura da página; não declara aceite de pacote, importador ou distribuição.
