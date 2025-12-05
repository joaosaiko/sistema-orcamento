"""
Módulo para gerenciar faixas unitárias através de popup interativo.
Fornece a classe GerenciadorPopup que encapsula toda a lógica de CRUD de faixas.
"""

import tkinter as tk
from tkinter import messagebox
from ttkbootstrap import ttk


def get_faixas_por_produto(conn, nome_produto):
    """Retorna todas as faixas de um produto unitário."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM produtos_unitarios WHERE nome = ?",
        (nome_produto,)
    )
    row = cursor.fetchone()
    if not row:
        return []
    
    produto_id = row[0]
    cursor.execute(
        "SELECT id, qtd_min, qtd_max, preco FROM faixas_unitarias WHERE produto_id = ? ORDER BY qtd_min",
        (produto_id,)
    )
    return [dict(r) for r in cursor.fetchall()]


def add_faixa(conn, nome_produto, qtd_min, qtd_max, preco):
    """Adiciona uma nova faixa de preço para um produto unitário."""
    cursor = conn.cursor()
    produto_id = ensure_produto_unitario(conn, nome_produto)
    cursor.execute(
        "INSERT INTO faixas_unitarias (produto_id, qtd_min, qtd_max, preco) VALUES (?, ?, ?, ?)",
        (produto_id, qtd_min, qtd_max, preco)
    )
    conn.commit()


def update_faixa(conn, faixa_id, qtd_min, qtd_max, preco):
    """Atualiza uma faixa de preço existente."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE faixas_unitarias SET qtd_min = ?, qtd_max = ?, preco = ? WHERE id = ?",
        (qtd_min, qtd_max, preco, faixa_id)
    )
    conn.commit()


def delete_faixa(conn, faixa_id):
    """Deleta uma faixa de preço."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faixas_unitarias WHERE id = ?", (faixa_id,))
    conn.commit()


def ensure_produto_unitario(conn, nome):
    """Garante que exista um registro em produtos_unitarios com esse nome. Retorna id."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (nome,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("INSERT INTO produtos_unitarios (nome) VALUES (?)", (nome,))
    conn.commit()
    return cursor.lastrowid


class NovoProdutoPopup:
    """
    Popup para criar e editar produtos com suporte a faixas unitárias.
    Gerencia campos de nome, tipo, preço e tabela de faixas de preço.
    """
    
    def __init__(self, parent, conn, callback_salvar):
        """
        Inicializa o popup de novo produto.
        
        Args:
            parent: janela pai (tk.Tk)
            conn: conexão com banco de dados SQLite
            callback_salvar: função a chamar quando produto é salvo (nome, tipo, preco_m2, preco_m, preco_unit)
        """
        self.parent = parent
        self.conn = conn
        self.callback_salvar = callback_salvar
        
        # Criar janela popup
        self.popup = tk.Toplevel(parent)
        self.popup.title("Adicionar Novo Produto")
        self.popup.geometry("640x520")
        
        # Variáveis
        self.tipo_var = tk.StringVar(value='unit')
        
        # Widgets
        self.ent_nome = None
        self.ent_preco_unit = None
        self.ent_preco_m2 = None
        self.ent_preco_m = None
        self.tree_faixas = None
        self.ent_qmin = None
        self.ent_qmax = None
        self.ent_qpreco = None
        
        self._criar_interface()
    
    def _criar_interface(self):
        """Constrói a interface do popup."""
        # --- Nome do produto ---
        ttk.Label(self.popup, text="Nome:*").grid(row=0, column=0, sticky='w', pady=6, padx=6)
        self.ent_nome = ttk.Entry(self.popup, width=40)
        self.ent_nome.grid(row=0, column=1, pady=6, padx=6, columnspan=3)
        self.ent_nome.bind('<FocusOut>', self._on_nome_change)
        
        # --- Tipo de produto ---
        ttk.Label(self.popup, text="Tipo:* (unit | m2 | m)").grid(row=1, column=0, sticky='w', pady=6, padx=6)
        ttk.Radiobutton(self.popup, text='Preço por m²', variable=self.tipo_var, value='m2').grid(row=1, column=1, sticky='w')
        ttk.Radiobutton(self.popup, text='Unitário (Faixas)', variable=self.tipo_var, value='unit').grid(row=1, column=2, sticky='w')
        ttk.Radiobutton(self.popup, text='Preço por metro linear', variable=self.tipo_var, value='m').grid(row=1, column=3, sticky='w')
        
        # --- Preços ---
        ttk.Label(self.popup, text="Preço por m² (R$):").grid(row=2, column=0, sticky='w', pady=6, padx=6)
        self.ent_preco_m2 = ttk.Entry(self.popup, width=20)
        self.ent_preco_m2.grid(row=2, column=1, sticky='w')
        
        ttk.Label(self.popup, text="Preço por metro linear (R$):").grid(row=2, column=2, sticky='w', pady=6, padx=6)
        self.ent_preco_m = ttk.Entry(self.popup, width=20)
        self.ent_preco_m.grid(row=2, column=3, sticky='w')
        
        ttk.Label(self.popup, text="Preço unitário (R$):").grid(row=3, column=0, sticky='w', pady=6, padx=6)
        self.ent_preco_unit = ttk.Entry(self.popup, width=20)
        self.ent_preco_unit.grid(row=3, column=1, sticky='w')
        
        # --- Treeview de faixas ---
        ttk.Label(self.popup, text="Faixas (apenas se unitário):").grid(row=4, column=0, sticky='nw', pady=6, padx=6)
        
        frame_faixas = ttk.Frame(self.popup)
        frame_faixas.grid(row=4, column=1, columnspan=3, pady=6, padx=6, sticky='nsew')
        self.popup.rowconfigure(4, weight=1)
        self.popup.columnconfigure(3, weight=1)
        
        cols = ("id", "min", "max", "preco")
        self.tree_faixas = ttk.Treeview(frame_faixas, columns=cols, show='headings', height=6)
        
        for col in cols:
            self.tree_faixas.heading(col, text=col)
            self.tree_faixas.column(col, width=80)
        
        self.tree_faixas.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(frame_faixas, orient='vertical', command=self.tree_faixas.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree_faixas.configure(yscrollcommand=scrollbar.set)
        
        # --- Inputs para faixas ---
        ttk.Label(self.popup, text="Qtd min:").grid(row=5, column=0, sticky='w')
        self.ent_qmin = ttk.Entry(self.popup, width=10)
        self.ent_qmin.grid(row=5, column=1, sticky='w')
        
        ttk.Label(self.popup, text="Qtd max:").grid(row=5, column=2, sticky='w')
        self.ent_qmax = ttk.Entry(self.popup, width=10)
        self.ent_qmax.grid(row=5, column=3, sticky='w')
        
        ttk.Label(self.popup, text="Preço (R$):").grid(row=6, column=0, sticky='w')
        self.ent_qpreco = ttk.Entry(self.popup, width=15)
        self.ent_qpreco.grid(row=6, column=1, sticky='w')
        
        # --- Botões de faixas ---
        ttk.Button(self.popup, text='Adicionar Faixa', command=self._adicionar_faixa).grid(row=7, column=1, pady=6)
        ttk.Button(self.popup, text='Remover Faixa', command=self._remover_faixa).grid(row=7, column=2, pady=6)
        
        # --- Botão salvar ---
        ttk.Button(self.popup, text="Salvar Produto", command=self._salvar_produto).grid(row=8, column=0, columnspan=4, pady=10)
    
    def _on_nome_change(self, event=None):
        """Carrega faixas existentes quando o nome mudar."""
        nome = self.ent_nome.get().strip()
        if nome:
            self._carregar_faixas_para_tree(nome)
    
    def _carregar_faixas_para_tree(self, nome_produto):
        """Carrega as faixas de um produto na treeview."""
        self.tree_faixas.delete(*self.tree_faixas.get_children())
        
        faixas = get_faixas_por_produto(self.conn, nome_produto)
        for faixa in faixas:
            self.tree_faixas.insert('', 'end', values=(
                faixa['id'], 
                faixa['qtd_min'], 
                faixa['qtd_max'], 
                faixa['preco']
            ))
    
    def _adicionar_faixa(self):
        """Adiciona uma nova faixa à tabela."""
        nome = self.ent_nome.get().strip()
        if not nome:
            messagebox.showwarning('Erro', 'Informe o nome antes de adicionar faixas')
            return
        
        try:
            qmin = int(self.ent_qmin.get())
            qmax = int(self.ent_qmax.get())
            preco = float(self.ent_qpreco.get().replace(',', '.'))
        except ValueError:
            messagebox.showwarning("Erro", "Valores inválidos")
            return
        
        add_faixa(self.conn, nome, qmin, qmax, preco)
        self._carregar_faixas_para_tree(nome)
        
        self.ent_qmin.delete(0, tk.END)
        self.ent_qmax.delete(0, tk.END)
        self.ent_qpreco.delete(0, tk.END)
    
    def _remover_faixa(self):
        """Remove a faixa selecionada."""
        sel = self.tree_faixas.selection()
        if not sel:
            messagebox.showinfo('Info', 'Selecione uma faixa para remover')
            return
        
        faixa_id = self.tree_faixas.item(sel)['values'][0]
        delete_faixa(self.conn, faixa_id)
        self._carregar_faixas_para_tree(self.ent_nome.get().strip())
    
    def _salvar_produto(self):
        """Salva o produto no banco de dados."""
        nome = self.ent_nome.get().strip()
        tipo = self.tipo_var.get()
        
        if not nome:
            messagebox.showwarning("Erro", "Informe o nome.")
            return
        
        preco_unit = preco_m2 = preco_m = None
        
        try:
            if tipo == "unit" and self.ent_preco_unit.get().strip():
                preco_unit = float(self.ent_preco_unit.get().replace(",", "."))
            if tipo == "m2":
                preco_m2 = float(self.ent_preco_m2.get().replace(",", "."))
            if tipo == "m":
                preco_m = float(self.ent_preco_m.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Erro", "Preço inválido")
            return
        
        # Chama callback para salvar no banco
        self.callback_salvar(nome, tipo, preco_m2, preco_m, preco_unit)
        
        messagebox.showinfo("OK", f"Produto '{nome}' salvo.")
        self.popup.destroy()


class GerenciadorPopup:
    """
    Gerenciador interativo de faixas de preço para produtos unitários.
    Fornece interface com Treeview para listar, adicionar, editar e remover faixas.
    """
    
    def __init__(self, parent, conn, nome_produto):
        """
        Inicializa o gerenciador de popup.
        
        Args:
            parent: janela pai (tk.Tk ou tk.Toplevel)
            conn: conexão com banco de dados SQLite
            nome_produto: nome do produto para gerenciar faixas
        """
        self.parent = parent
        self.conn = conn
        self.nome_produto = nome_produto
        
        # Criar janela popup
        self.popup = tk.Toplevel(parent)
        self.popup.title(f"Gerenciar Faixas - {nome_produto}")
        self.popup.geometry('600x450')
        
        # Widgets
        self.tree = None
        self.ent_qmin = None
        self.ent_qmax = None
        self.ent_qpreco = None
        
        self._criar_interface()
        self._carregar_faixas()
    
    def _criar_interface(self):
        """Constrói a interface do popup."""
        # --- Treeview para listar faixas ---
        self._criar_treeview()
        
        # --- Frame de inputs ---
        self._criar_frame_inputs()
        
        # --- Frame de botões ---
        self._criar_frame_botoes()
    
    def _criar_treeview(self):
        """Cria a treeview para exibir faixas."""
        cols = ('ID', 'Qtd Min', 'Qtd Max', 'Preço')
        self.tree = ttk.Treeview(self.popup, columns=cols, show='headings')
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        self.tree.pack(fill='both', expand=True, padx=8, pady=8)
    
    def _criar_frame_inputs(self):
        """Cria o frame com campos de entrada."""
        frame_inputs = ttk.Frame(self.popup)
        frame_inputs.pack(fill='x', padx=8, pady=4)
        
        ttk.Label(frame_inputs, text='Qtd Min').grid(row=0, column=0)
        self.ent_qmin = ttk.Entry(frame_inputs, width=8)
        self.ent_qmin.grid(row=0, column=1, padx=4)
        
        ttk.Label(frame_inputs, text='Qtd Max').grid(row=0, column=2)
        self.ent_qmax = ttk.Entry(frame_inputs, width=8)
        self.ent_qmax.grid(row=0, column=3, padx=4)
        
        ttk.Label(frame_inputs, text='Preço').grid(row=0, column=4)
        self.ent_qpreco = ttk.Entry(frame_inputs, width=12)
        self.ent_qpreco.grid(row=0, column=5, padx=4)
    
    def _criar_frame_botoes(self):
        """Cria o frame com botões de ação."""
        btn_frame = ttk.Frame(self.popup)
        btn_frame.pack(fill='x', padx=8, pady=4)
        
        ttk.Button(btn_frame, text='Adicionar', command=self.adicionar_faixa).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Editar', command=self.editar_faixa).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Remover', command=self.remover_faixa).pack(side='left', padx=4)
    
    def _carregar_faixas(self):
        """Carrega as faixas da base de dados e exibe na treeview."""
        self.tree.delete(*self.tree.get_children())
        faixas = get_faixas_por_produto(self.conn, self.nome_produto)
        for faixa in faixas:
            self.tree.insert('', 'end', values=(faixa['id'], faixa['qtd_min'], faixa['qtd_max'], faixa['preco']))
    
    def _limpar_inputs(self):
        """Limpa os campos de entrada."""
        self.ent_qmin.delete(0, tk.END)
        self.ent_qmax.delete(0, tk.END)
        self.ent_qpreco.delete(0, tk.END)
    
    def _ler_inputs(self):
        """
        Lê e valida os campos de entrada.
        
        Returns:
            Tupla (qtd_min, qtd_max, preco) ou None se houver erro
        """
        qmin_str = self.ent_qmin.get().strip()
        qmax_str = self.ent_qmax.get().strip()
        preco_str = self.ent_qpreco.get().strip().replace(',', '.')
        
        if not qmin_str or not qmax_str or not preco_str:
            messagebox.showwarning('Erro', 'Preencha todos os campos')
            return None
        
        try:
            qmin = int(qmin_str)
            qmax = int(qmax_str)
            preco = float(preco_str)
        except ValueError:
            messagebox.showwarning('Erro', 'Valores de faixa inválidos')
            return None
        
        if qmin <= 0 or qmax <= 0 or qmin > qmax:
            messagebox.showwarning('Erro', 'Qtd Min deve ser ≤ Qtd Max e ambos positivos')
            return None
        
        return qmin, qmax, preco
    
    def _verifica_sobreposicao(self, qmin, qmax, ignore_id=None):
        """
        Verifica se uma nova faixa se sobrepõe com faixas existentes.
        
        Args:
            qmin: quantidade mínima
            qmax: quantidade máxima
            ignore_id: ID de faixa a ignorar na verificação (útil para edição)
        
        Returns:
            True se houver sobreposição, False caso contrário
        """
        faixas = get_faixas_por_produto(self.conn, self.nome_produto)
        
        for faixa in faixas:
            if ignore_id is not None and faixa['id'] == ignore_id:
                continue
            
            fmin = faixa['qtd_min']
            fmax = faixa['qtd_max']
            
            # Verifica se há interseção
            if not (qmax < fmin or qmin > fmax):
                return True
        
        return False
    
    def adicionar_faixa(self):
        """Adiciona uma nova faixa após validação."""
        valores = self._ler_inputs()
        if valores is None:
            return
        
        qmin, qmax, preco = valores
        
        if self._verifica_sobreposicao(qmin, qmax):
            messagebox.showwarning('Erro', 'Faixa sobrepõe outra já existente')
            return
        
        add_faixa(self.conn, self.nome_produto, qmin, qmax, preco)
        self._carregar_faixas()
        self._limpar_inputs()
        messagebox.showinfo('Sucesso', 'Faixa adicionada com sucesso')
    
    def editar_faixa(self):
        """Edita a faixa selecionada após validação."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Info', 'Selecione uma faixa para editar')
            return
        
        fid = self.tree.item(sel)['values'][0]
        
        valores = self._ler_inputs()
        if valores is None:
            return
        
        qmin, qmax, preco = valores
        
        if self._verifica_sobreposicao(qmin, qmax, ignore_id=fid):
            messagebox.showwarning('Erro', 'Faixa sobrepõe outra já existente')
            return
        
        update_faixa(self.conn, fid, qmin, qmax, preco)
        self._carregar_faixas()
        self._limpar_inputs()
        messagebox.showinfo('Sucesso', 'Faixa atualizada com sucesso')
    
    def remover_faixa(self):
        """Remove a faixa selecionada após confirmação."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Info', 'Selecione uma faixa para remover')
            return
        
        if messagebox.askyesno('Confirmação', 'Deseja remover esta faixa?'):
            fid = self.tree.item(sel)['values'][0]
            delete_faixa(self.conn, fid)
            self._carregar_faixas()
            messagebox.showinfo('Sucesso', 'Faixa removida com sucesso')
