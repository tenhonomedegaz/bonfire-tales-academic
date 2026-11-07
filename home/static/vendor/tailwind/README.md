# Tailwind local

Snapshot do runtime Tailwind **3.4.17** com o plugin Typography, obtido em
13-09-2026 de `https://cdn.tailwindcss.com/3.4.17?plugins=typography`.

Arquivo: `tailwind-3.4.17-typography.js`.
SHA-256: `40f00f2a537733b55c4d30fbb762164329de258493af6faf88b72f48d354ae6f`.

O bundle está preservado sem alterações, incluindo avisos de dependências.
`LICENSE.txt` contém a licença do Tailwind, obtida de
`https://raw.githubusercontent.com/tailwindlabs/tailwindcss/v3.4.17/LICENSE`.
O endpoint não identifica separadamente a versão de Typography; o checksum
fixa o artefato completo utilizado e deve acompanhar qualquer atualização.

O template base serve este arquivo pelo static do Django. Isso elimina a
dependência do CDN para gerar os utilitários usados pela navegação e pelas
páginas, inclusive classes acrescentadas pelo JavaScript após carregar.
O código inspecionado não faz chamadas `fetch` nem carrega plugins remotos.

Esta é uma etapa de fixação da dependência existente, mantendo sua compilação
no navegador. A substituição por CSS compilado no build permanece pendente:
exige inventariar classes dinâmicas e validar os consumidores, e não deve
descartar estilos criados em tempo de execução. Fontes e Marked continuam
com dependências externas próprias e não são cobertos por este snapshot.

Atualizações: baixar para um novo arquivo versionado, preservar licença,
registrar origem/checksum e executar testes e inspeção visual das páginas
consumidoras antes de alterar o template. Não sobrescrever silenciosamente
este artefato com outra versão.
