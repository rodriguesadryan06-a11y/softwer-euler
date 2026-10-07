# Ferramentas de apoio

[Guia dos desenvolvedores](../docs/desenvolvimento/README.md)

Execute na raiz do repositório, com o ambiente virtual ativado.

| Comando | Finalidade / saída |
|---|---|
| `python scripts/gerar_modelos.py` | Contrato em `docs/dados/` e planilha em `templates/` |
| `python scripts/gerar_exemplos_relatorio.py` | Relatórios sintéticos em `docs/exemplos_relatorio/` |
| `python scripts/gerar_pdfs_revisao.py` | Fontes de `docs/fisica/` → PDFs em `docs/revisao/` |
| `python scripts/prints.py` | Capturas em `prints/` |
| `python scripts/gravar_video_demo.py` | Vídeo em `demo/video/` |
| `python scripts/gerar_previa.py` | Prévia em `demo/previa/`; não substitui o aplicativo |
| `python scripts/medir_escala.py` | Cinco clientes sintéticos do envio ao fechamento → `docs/produto/escala_atendimento.md` (D109) |

As ferramentas visuais e de PDF exigem o extra `prints` e Chromium pelo Playwright;
o vídeo em MP4 depende também de FFmpeg. Consulte o início de cada script para as opções.

`abrir_local.py` é o inicializador Windows usado por `ABRIR-EULER.cmd`. Identifica o servidor,
evita duplicatas e mantém registros em `.euler-local/`. Ao abrir, traz a versão principal do
GitHub só por avanço rápido e só sem risco para alterações locais (D91).
`previa_modelo.html` é o modelo da prévia gerada.
