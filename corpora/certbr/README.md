# Base pública: segurança digital

Fonte: **CERT.br / NIC.br — Cartilha de Segurança para Internet**,
<https://cartilha.cert.br/fasciculos/>.

Esta pasta inclui **cinco PDFs oficiais, sem edição**, importados em 19/10/2026.
Fonte: Cartilha de Segurança para Internet, autor CERT.br/NIC.br —
<https://cartilha.cert.br/>.

| Fascículo | Páginas | Original |
| --- | --- | --- |
| [Backup](snapshot/pdfs/fasciculo-backup.pdf) | 14 | [CERT.br](https://cartilha.cert.br/fasciculos/backup/fasciculo-backup.pdf) |
| [Autenticação](snapshot/pdfs/fasciculo-autenticacao.pdf) | 22 | [CERT.br](https://cartilha.cert.br/fasciculos/autenticacao/fasciculo-autenticacao.pdf) |
| [Golpes: evite fraudes](snapshot/pdfs/fasciculo-golpes-evite-fraudes.pdf) | 21 | [CERT.br](https://cartilha.cert.br/fasciculos/golpes-evite-fraudes/fasciculo-golpes-evite-fraudes.pdf) |
| [Redes sociais](snapshot/pdfs/fasciculo-redes-sociais.pdf) | 19 | [CERT.br](https://cartilha.cert.br/fasciculos/redes-sociais/fasciculo-redes-sociais.pdf) |
| [Proteção de dados](snapshot/pdfs/fasciculo-protecao-de-dados.pdf) | 26 | [CERT.br](https://cartilha.cert.br/fasciculos/protecao-de-dados/fasciculo-protecao-de-dados.pdf) |

Licença confirmada na [página oficial de licença](https://cartilha.cert.br/cc/):
**[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)**.
A atribuição é obrigatória, o uso deve ser não comercial e versões modificadas
dos materiais não podem ser distribuídas. Os PDFs deste diretório são cópias
integrais dos originais. O código do projeto não altera essa licença.

Para verificar os checksums da base existente, ou importar em um checkout sem os PDFs:

```bash
uv run python -m ragsearch.corpus
```

O comando precisa de acesso HTTPS a `cartilha.cert.br`. Se houver uma lista de
permissões de rede, adicione esse domínio nas configurações do ambiente e salve
a alteração antes de executar novamente. Não é necessário informar credenciais.

A importação descobre os links de PDF na página oficial, prioriza os temas do
catálogo e exige que a fonte informe uma licença Creative Commons reconhecida,
consultando a página oficial `/cc/` quando necessário. Seleciona a versão padrão
de cada fascículo, evitando duplicar as versões para impressão.
Uma licença não identificada bloqueia a importação para revisão; ela não é
substituída por uma licença presumida.

Uma importação concluída cria `snapshot/` com:

- `pdfs/`: os PDFs originais, sem edição;
- `manifest.json`: instituição, endereço da página, licença indicada na página,
  URL de cada arquivo, data de obtenção, tamanho, número de páginas e SHA-256.

Nenhum arquivo é publicado como base concluída se uma transferência ou validação
falhar. Uma base já existente tem seus checksums verificados e é reutilizada;
o comando não atualiza nem substitui automaticamente seus arquivos.

Na interface, use **Carregar base pública CERT.br**. O índice e o texto extraído
ficam em memória. Os PDFs e o manifesto podem acompanhar o repositório, observadas
as condições de licença dos materiais. Preserve a autoria, os avisos contidos nos
PDFs e a referência à fonte. A licença do conteúdo é independente da do código.
Consulte o texto completo da licença registrada no manifesto. A página oficial
de licença declara expressamente sua aplicação aos fascículos. Não há vínculo
ou endosso do CERT.br / NIC.br a este projeto.

Os arquivos foram obtidos por HTTPS e os hashes SHA-256 registrados permitem
detectar alterações locais. As assinaturas PGP disponibilizadas pelo autor não
foram verificadas nesta importação; os hashes locais não substituem essa verificação.

Consultas de recuperação verificadas nos documentos reais:

- **Como conferir um boleto antes de pagar?** — Golpes: evite fraudes, página 13.
- **O que fazer antes de descartar um celular?** — Proteção de dados, página 14.
- **Qual é a capital da Noruega?** — nenhuma evidência recuperada.

Execute `uv run pytest tests/test_public_corpus.py -q` para verificar a leitura
dos cinco PDFs, essas consultas e o carregamento na interface. Foram extraídas
102 páginas com texto e criados 107 trechos com os parâmetros padrão. A dependência
`fonttools` é necessária para interpretar fontes presentes nesses PDFs.

São smoke tests, não um benchmark representativo. Perguntas amplas podem recuperar
capas ou páginas de título; por exemplo, na consulta sobre cuidados ao compartilhar
fotos, o top-3 recuperou títulos e orientações genéricas, sem a evidência específica.
A extração também mantém artefatos de diagramação, como palavras separadas por
quebras de linha. Melhorar segmentação e recuperação é um próximo experimento.
A geração com modelo real continua dependendo de credenciais e não foi validada.
Os seis casos de `examples/evaluation.json` continuam avaliando somente a base fictícia.
