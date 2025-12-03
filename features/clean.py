import tkinter as tk


class Clean:
    def __init__(self, budget_system):
        self.budget_system = budget_system

    # ==================== Limpeza de campos ====================
    def _clear_produto_inputs(self):
        """Limpa todos os campos de entrada relacionados ao produto."""
        for e in [self.budget_system.ent_desc, self.budget_system.ent_larg, self.budget_system.ent_alt, self.budget_system.ent_qtd, self.budget_system.ent_preco, self.budget_system.ent_total]:
            e.config(state='normal')
            e.delete(0, tk.END)
            if e == self.budget_system.ent_total:
                e.config(state='readonly')

    def limpar_campos_produto(self):
        """Limpa apenas os campos do formulário (sem tocar no BD)."""
        self.budget_system.produto_selecionado.set("")
        self.budget_system.cb_produtos.set("")
        self._clear_produto_inputs()