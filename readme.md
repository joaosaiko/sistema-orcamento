**Sistema de Orçamento - Gráfica (Unitários em Tabelas)**

Um sistema de orçamentos simples e focado em gráficas, construído em Python com interface gráfica (Tkinter + `ttkbootstrap`) e suporte completo para produtos unitários com faixas/tabelas de preço.

**Resumo**: Este repositório contém uma pequena aplicação desktop que permite cadastrar produtos (unitários, por m² ou por metro linear), definir faixas de preço para produtos unitários, montar propostas (serviços/produtos) e gerar documentos `.docx` de saída. O design prioriza usabilidade: popups para CRUD de produtos/faixas, cálculo automático de total e uma UI limpa.

**Badges**
- **Status:**: Em desenvolvimento
- **Linguagem:**: `Python 3.x`

**Destaques / Features**
- **Faixas unitárias**: Produtos do tipo `unit` podem ter várias faixas (qtd_min, qtd_max, preço) armazenadas em `faixas_unitarias`.
- **Banco SQLite embutido**: Dados persistidos em `produtos.db` (criado/atualizado automaticamente).
- **UI moderna**: Interface construída com `ttkbootstrap` (tema `darkly`) e componentes organizados em `UI.AppUI`.
- **Popups de gerenciamento**: `NovoProdutoPopup` e `GerenciadorPopup` para criar/editar produtos e gerenciar faixas.
- **Geração de DOCX**: Integração opcional com `python-docx` (há suporte para usar um `docxGenerator` quando disponível).
- **Calculadora de total**: Lógica isolada em `total_calculator.py` para facilitar testes e reuso.

**Arquivos Principais**
- `budget_system.py`: Aplicação principal (UI + lógica de orçamentos). Use como referência para execução direta.
- `total_calculator.py`: Classe `TotalCalculator` responsável por calcular total de um item conforme tipo (por unidade, por m², por m).
- `UI.py`: Builder da interface (`AppUI`) que monta e liga widgets à instância `OrcamentoApp`.
- `gerenciador_popup.py`: Popups para criar/editar produtos e gerenciar faixas unitárias.
- `requirements.txt`: Dependências sugeridas.

**Instalação Rápida**
1. Clone o repositório:

	`git clone <repo-url>`

2. Crie/ative um ambiente virtual (recomendado):

	- Windows (Powershell):
	  `python -m venv .venv; .\.venv\Scripts\Activate.ps1`

3. Instale dependências:

	`pip install -r requirements.txt`

4. Execute a aplicação:

	`python budget_system.py`

Observação: se preferir, você também pode executar `budget_system.py` diretamente a partir do seu IDE.

**Uso / Fluxo Básico**
- **Cadastrar produto**: clique em `Adicionar Novo Produto` e preencha nome, tipo e preços. Para produtos `unit`, abra o painel de faixas e adicione intervalos com preço.
- **Gerenciar faixas**: selecione um produto na lista e clique em `Gerenciar Faixas (unit.)` para abrir a interface de edição de faixas.
- **Adicionar serviço à proposta**: preencha descrição, largura, altura (em cm), quantidade e preço; clique em `Calcular Total` e depois em `Adicionar Serviço`.
- **Gerar documento**: clique em `Gerar DOCX` para exportar a proposta (requer `python-docx`; há suporte a um template `.docx`).

**Banco de Dados e Estrutura**
- Arquivo DB: `produtos.db`
- Tabelas principais criadas/atualizadas automaticamente:
  - `produtos` (compatível com versão anterior; armazena `tipo`, `preco_m2`, `preco_m`, `preco_unit`, `tiers`, etc.)
  - `produtos_unitarios` (mapeia produtos unitários por nome para gerenciar faixas)
  - `faixas_unitarias` (cada registro contém `produto_id`, `qtd_min`, `qtd_max`, `preco`)

**Extensibilidade / Arquitetura**
- A UI é separada em `UI.AppUI` para facilitar customizações ou uso em outro projeto.
- A lógica de cálculo foi extraída para `total_calculator.py` (fácil de testar isoladamente).
- Módulos opcionalmente detectados: `features.clean` e `features.gerar_docx` são utilizados quando presentes.

**Dependências**
- `ttkbootstrap` (UI moderna)
- `python-docx` (geração de `.docx`)
- `pandas` (usado em algumas rotinas opcionais — ver `features/`)

Instale tudo com: `pip install -r requirements.txt`

**Erros Comuns / Soluções**
- `ModuleNotFoundError: ttkbootstrap` — instale com `pip install ttkbootstrap`.
- Problemas com `.docx`: confirme `python-docx` instalado e que o template selecionado é um `.docx` válido.
- Se a DB estiver corrompida, renomeie `produtos.db` e reinicie a aplicação para recriar as tabelas.

**Contribuindo**
- Abra uma issue para bugs ou ideias.
- Para PRs: mantenha mudanças focadas, adicione testes quando possível e documente alterações.

**Roadmap / Melhorias sugeridas**
- Importação/Exportação CSV para listas de produtos.
- Validação e testes unitários para `TotalCalculator`.
- Suporte a múltiplos templates e seleção de layout ao gerar `.docx`.

**Licença**
- Veja o arquivo `LICENSE` no repositório para detalhes.

---

Se quiser, eu posso:
- gerar um README traduzido para outro idioma;
- adicionar exemplos de uso com screenshots;
- preparar um script de instalação automatizado.

Diga qual próximo passo prefere.

