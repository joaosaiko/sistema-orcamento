
<!--- Modern README: emojis, tabela, comandos prontos --->

# 🚀 Sistema de Orçamento - Gráfica (Unitários em Tabelas)

Um aplicativo desktop leve para criar propostas e orçamentos usado por gráficas e prestadores de serviços. Fornece suporte a produtos por unidade (com faixas de preço), por m² e por metro linear, com UI baseada em `ttkbootstrap` e exportação para `.docx`.

**Status:** 🛠️ Em desenvolvimento · **Linguagem:** 🐍 Python 3.x

## 📌 Tabela de Conteúdos

- [Destaques](#-destaques)
- [Arquivos Principais](#-arquivos-principais)
- [Instalação Rápida](#-instalação-rápida)
- [Comandos Úteis (copy & paste)](#-comandos-úteis-copy--paste)
- [Uso / Fluxo Básico](#-uso--fluxo-básico)
- [Estrutura do Banco de Dados](#-estrutura-do-banco-de-dados)
- [Solução de Problemas](#-solução-de-problemas)
- [Contribuição e Roadmap](#-contribuição-e-roadmap)
- [Licença](#-licença)

## ✨ Destaques

| Feature | Descrição |
|---|---|
| Faixas unitárias | Produtos `unit` podem ter várias faixas (qtd_min, qtd_max, preço) gerenciadas em uma UI dedicada. |
| Persistência | SQLite (`produtos.db`) criado/atualizado automaticamente. |
| UI | Interface com `ttkbootstrap` (tema `darkly`) — botão, popups, treeviews. |
| Export | Geração de `.docx` via `python-docx` (suporte a templates). |
| Modularidade | Lógica de cálculo isolada em `total_calculator.py` para testes e reuso. |

## 📁 Arquivos Principais

- `budget_system.py` — Aplicação principal (UI + lógica). Inicia a janela principal.
- `total_calculator.py` — Classe `TotalCalculator` (cálculo de total por tipo).
- `UI.py` — `AppUI` monta a interface e expõe widgets usados pela app.
- `gerenciador_popup.py` — Popups para criar/editar produtos e gerenciar faixas.
- `requirements.txt` — Dependências recomendadas.

## ⚙️ Instalação Rápida

Clone e rode localmente (comandos prontos para PowerShell):

```powershell
git clone <repo-url>
cd sistema-orcamento
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python budget_system.py
```

Observações:
- Se você usa `cmd.exe`, ative o venv com: `.venv\Scripts\activate.bat`
- Se preferir, abra `budget_system.py` no seu IDE e rode a partir daí.

## 🧰 Comandos Úteis (Copy & Paste)

- Clonar (substitua `<repo-url>`):

```powershell
git clone <repo-url>
```

- Criar/ativar venv (PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

- Instalar dependências:

```powershell
pip install -r requirements.txt
```

- Rodar a aplicação:

```powershell
python budget_system.py
```

- Recriar banco de dados (ou reset simples): renomeie o arquivo `produtos.db` antes de rodar, por exemplo:

```powershell
mv produtos.db produtos.db.bak
python budget_system.py
```

## 🧭 Uso / Fluxo Básico

1. Abrir a aplicação (`python budget_system.py`).
2. Para cadastrar um produto: clique em **Adicionar Novo Produto**.
	 - Escolha tipo: `unit` | `m2` | `m`.
	 - Para `unit` adicione faixas (Qtd min / Qtd max / Preço) no popup.
3. Selecione o produto no combobox, insira descrição, dimensões (cm), quantidade e preço.
4. Clique em **Calcular Total** e depois **Adicionar Serviço** para inserir na proposta.
5. Ao finalizar, use **Gerar DOCX** para exportar (pode usar template selecionável).

## 🗄️ Estrutura do Banco de Dados

Tabelas criadas automaticamente:

- `produtos` — mantém compatibilidade com esquema anterior. Campos: `id`, `nome`, `tipo`, `largura`, `altura`, `preco_m2`, `preco_m`, `preco_unit`, `tiers`.
- `produtos_unitarios` — mapeia produtos unitários por `id` e `nome`.
- `faixas_unitarias` — colunas: `id`, `produto_id`, `qtd_min`, `qtd_max`, `preco`.

O arquivo é `produtos.db` na raiz do projeto.

## 🐞 Solução de Problemas (rápido)

- Erro: `ModuleNotFoundError: ttkbootstrap`
	- Solução: `pip install ttkbootstrap`

- Problema ao gerar `.docx`
	- Confirme `python-docx` instalado: `pip install python-docx`.
	- Verifique se o template é um `.docx` válido.

- Banco corrompido ou perder dados
	- Renomeie `produtos.db` e reinicie; as tabelas serão recriadas.

## 🤝 Contribuição

- Abra uma issue para bugs/ideias.
- Faça fork → branch com nome claro → PR com descrição e testes se possível.

Sugestões de PRs úteis:

- Adicionar testes unitários para `TotalCalculator`.
- Exemplos de templates `.docx` e screenshots.
- Automatizar CI (linters/tests).

## 🛣️ Roadmap / Melhorias Sugeridas

- Import/Export CSV de produtos.
- Melhor UX para sobreposição de faixas (warnings em tempo real).
- Sistema de templates múltiplos para `.docx`.

## 📜 Licença

Consulte o arquivo `LICENSE` neste repositório.

---

Se desejar, eu posso:

- 🎨 Gerar imagens / screenshots para incluir no README;
- 🧪 Criar um pequeno teste para `TotalCalculator` e adicionar ao repo;
- 📦 Preparar um script `install.ps1` que automatiza venv + pip install + run.

Diga qual desses passos você quer que eu execute agora.

