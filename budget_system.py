#!/usr/bin/env python3
"""
Sistema de Orçamento - Tkinter + ttkbootstrap + SQLite
Versão: Suporte a produtos por m² (preço fixo), produtos por metro linear e produtos unitários com faixas.
Dependências:
pip install ttkbootstrap python-docx pandas

Observações:
- Mantive chamadas para `_clear_produto_inputs()` dentro de try/except (você disse que existe em outro arquivo).
- A tabela `produtos` foi criada/atualizada sem colunas NOT NULL obrigatórias para preço (evita erro NOT NULL).
- Produtos unitários podem usar faixas (texto no popup) ou um preço unitário simples.
"""

import os
import sqlite3
import json
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from ttkbootstrap import ttk, Style
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import pandas as pd
from features.clean import Clean  # sua classe externa
from features.gerar_docx import docxGenerator
from features.total import TotalCalculator


DB_PATH = "produtos.db"


class OrcamentoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Orçamento - Gráfica")
        self.geometry("1050x750")
        self.minsize(950, 650)
        self.style = Style(theme="darkly")

        # Variáveis principais
        self.ano_atual = datetime.today().year
        self.data_orcamento = datetime.today().strftime('%d/%m/%Y')
        self.template_path = tk.StringVar(value='(nenhum modelo selecionado)')
        self.cliente = tk.StringVar()
        self.numero_proposta = tk.StringVar()
        self.proposta_completa = tk.StringVar()
        self.data_label = tk.StringVar(value=self.data_orcamento)
        self.total_valor = tk.StringVar(value="R$ 0,00")
        self.servicos = []

        # Banco de dados
        self.conn = sqlite3.connect(DB_PATH)
        self._corrigir_estrutura_produtos()

        # Produto selecionado
        self.produto_selecionado = tk.StringVar()
        self.produtos_lista = []

        # Limpeza de campos
        self.clean = Clean(self)

        # Inicializa gerador de documentos




        # Monta interface
        self._build_ui()
        self._refresh_proposta()
        self._refresh_total()
        self._atualizar_produtos()

    # ==================== Banco de Dados (estrutura final) ====================
    def _corrigir_estrutura_produtos(self):
        """
        Garante estrutura flexível para produtos:
        - id, nome, tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers
        - tipo: 'm2' | 'm' | 'unit'
        - tiers: JSON string com faixas para produtos unitários (opcional)
        """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(produtos)")
        cols_info = cursor.fetchall()
        existing_cols = [c[1] for c in cols_info]

        if not existing_cols:
            cursor.execute("""
                CREATE TABLE produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    tipo TEXT,
                    largura REAL,
                    altura REAL,
                    preco_m2 REAL,
                    preco_m REAL,
                    preco_unit REAL,
                    tiers TEXT
                )
            """)
            self.conn.commit()
            return

        def add_col(col_def):
            try:
                cursor.execute(f"ALTER TABLE produtos ADD COLUMN {col_def}")
            except Exception:
                pass

        if "tipo" not in existing_cols:
            add_col("tipo TEXT")
        if "largura" not in existing_cols:
            add_col("largura REAL")
        if "altura" not in existing_cols:
            add_col("altura REAL")
        if "preco_m2" not in existing_cols:
            add_col("preco_m2 REAL")
        if "preco_m" not in existing_cols:
            add_col("preco_m REAL")
        if "preco_unit" not in existing_cols:
            add_col("preco_unit REAL")
        if "tiers" not in existing_cols:
            add_col("tiers TEXT")
        self.conn.commit()

        # compatibilidade: se houver coluna 'preco' antiga, migrar para preco_m2
        if "preco" in existing_cols and "preco_m2" in existing_cols:
            try:
                cursor.execute("SELECT id, preco FROM produtos WHERE preco IS NOT NULL")
                rows = cursor.fetchall()
                for r in rows:
                    pid, preco = r
                    cursor.execute("UPDATE produtos SET preco_m2 = ?, tipo = COALESCE(tipo, 'm2') WHERE id = ?", (preco, pid))
                self.conn.commit()
            except Exception:
                pass

    def adicionar_produto_db(self, nome, tipo, preco_m2=None, preco_m=None, preco_unit=None, tiers=None, largura=None, altura=None):
        """
        Adiciona ou substitui um produto na tabela.
        tiers deve ser uma lista de dicts [{'min':1,'max':9,'price':7.0}, ...]
        """
        cursor = self.conn.cursor()
        tiers_json = json.dumps(tiers, ensure_ascii=False) if tiers else None
        cursor.execute(
            "INSERT OR REPLACE INTO produtos (nome, tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nome, tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers_json),
        )
        self.conn.commit()
        self._atualizar_produtos()

    def _atualizar_produtos(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT nome FROM produtos ORDER BY nome")
        produtos = [row[0] for row in cursor.fetchall()]
        self.produtos_lista = produtos
        try:
            self.cb_produtos["values"] = produtos
        except Exception:
            pass

    def carregar_produto(self, event=None):
        nome = self.produto_selecionado.get()
        if not nome:
            return
        cursor = self.conn.cursor()
        cursor.execute("SELECT tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers FROM produtos WHERE nome = ?", (nome,))
        result = cursor.fetchone()
        if result:
            tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers_json = result
            self.ent_desc.delete(0, tk.END)
            self.ent_desc.insert(0, nome)
            self.ent_larg.delete(0, tk.END)
            self.ent_alt.delete(0, tk.END)
            if largura:
                self.ent_larg.insert(0, str(largura))
            if altura:
                self.ent_alt.insert(0, str(altura))
            self.ent_preco.delete(0, tk.END)
            # preenche campo preço com o valor mais representativo
            if tipo == 'm2' and preco_m2 is not None:
                self.ent_preco.insert(0, str(preco_m2))
                self.tipo_calculo.set('Por m²')
            elif tipo == 'unit' and preco_unit is not None:
                self.ent_preco.insert(0, str(preco_unit))
                self.tipo_calculo.set('Por unidade')
            elif tipo == 'unit' and tiers_json:
                # mostra preço da primeira faixa como referência
                try:
                    tiers = json.loads(tiers_json)
                    if tiers:
                        self.ent_preco.insert(0, str(tiers[0].get('price', '')))
                        self.tipo_calculo.set('Por unidade')
                except Exception:
                    pass

            self.ent_qtd.delete(0, tk.END)
            self.ent_qtd.insert(0, "1")
            self.calcular_total()

    # ==================== Funções de banco existentes ====================
    def remover_produto_db(self):
        nome = self.produto_selecionado.get()
        if not nome:
            messagebox.showinfo("Info", "Selecione um produto para remover.")
            return

        if not messagebox.askyesno("Confirmar", f"Deseja realmente remover o produto '{nome}'?"):
            return

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM produtos WHERE nome = ?", (nome,))
        self.conn.commit()

        messagebox.showinfo("Sucesso", f"Produto '{nome}' removido com sucesso.")
        self._atualizar_produtos()
        self.produto_selecionado.set("")
        try:
            self.cb_produtos.set("")
        except Exception:
            pass
        try:
            self._clear_produto_inputs()
        except Exception:
            pass

    def limpar_todos_produtos_db(self):
        if not messagebox.askyesno("Confirmar", "Deseja realmente apagar TODOS os produtos cadastrados?"):
            return
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM produtos")
        self.conn.commit()
        messagebox.showinfo("Sucesso", "Todos os produtos foram removidos.")
        self._atualizar_produtos()
        try:
            self._clear_produto_inputs()
        except Exception:
            pass

    # ==================== Tabela de serviços ====================
    def limpar_servicos(self):
        if messagebox.askyesno('Confirmar', 'Deseja remover todos os serviços adicionados?'):
            self.servicos.clear()
            self._refresh_tree()
            self._refresh_total()

    # ==================== Interface ====================
    def _build_ui(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill='both', expand=True)

        # === Topo ===
        top_card = ttk.Labelframe(container, text="Modelo e Informações", padding=10, bootstyle="info")
        top_card.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(top_card)
        row1.pack(fill='x', pady=5)
        ttk.Label(row1, text='Modelo .docx:').pack(side='left')
        ttk.Label(row1, textvariable=self.template_path).pack(side='left', padx=8)
        ttk.Button(row1, text='Selecionar Modelo', bootstyle="secondary", command=self.selecionar_modelo).pack(side='right')

        form = ttk.Frame(top_card)
        form.pack(fill='x', pady=5)
        ttk.Label(form, text='Cliente:').grid(row=0, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.cliente, width=50).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Label(form, text='Nº Proposta:').grid(row=1, column=0, sticky='w', pady=3)
        ttk.Entry(form, textvariable=self.numero_proposta, width=10).grid(row=1, column=1, sticky='w', padx=6, pady=3)
        ttk.Button(form, text='Atualizar', bootstyle="warning", command=self._refresh_proposta).grid(row=1, column=2, padx=6, pady=3)
        ttk.Label(form, text='Proposta:').grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(form, textvariable=self.proposta_completa, foreground='#1f6feb').grid(row=2, column=1, sticky='w', pady=3)
        ttk.Label(form, text='Data:').grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(form, textvariable=self.data_label).grid(row=3, column=1, sticky='w', pady=3)
        form.columnconfigure(1, weight=1)

        # === Card de Produtos ===
        add_card = ttk.Labelframe(container, text="Serviços / Produtos", padding=10, bootstyle="info")
        add_card.pack(fill='x', pady=(10, 0))
        entradas = ttk.Frame(add_card)
        entradas.pack(fill='x')

        ttk.Label(entradas, text='Produtos:').grid(row=0, column=0, sticky='w')
        self.cb_produtos = ttk.Combobox(
            entradas, textvariable=self.produto_selecionado, values=self.produtos_lista, state='readonly', width=40
        )
        self.cb_produtos.grid(row=0, column=1, sticky='w', padx=6)
        self.cb_produtos.bind('<<ComboboxSelected>>', self.carregar_produto)

        ttk.Button(
            entradas, text='Adicionar Novo Produto', bootstyle="secondary", command=self.novo_produto_popup
        ).grid(row=0, column=2, padx=6)

        # Botões de gerenciamento
        ttk.Button(
            entradas, text='Remover Produto', bootstyle="danger", command=self.remover_produto_db
        ).grid(row=0, column=3, padx=6)

        ttk.Button(
            entradas, text='Limpar Campos', bootstyle="warning-outline", command=self.clean.limpar_campos_produto
        ).grid(row=0, column=4, padx=6)

        # Campos de produto/serviço
        ttk.Label(entradas, text='Descrição:').grid(row=1, column=0, sticky='w')
        self.ent_desc = ttk.Entry(entradas, width=40)
        self.ent_desc.grid(row=1, column=1, sticky='ew', padx=6)

        ttk.Label(entradas, text='Largura (cm):').grid(row=2, column=0, sticky='w', pady=3)
        self.ent_larg = ttk.Entry(entradas, width=10)
        self.ent_larg.grid(row=2, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Altura (cm):').grid(row=3, column=0, sticky='w', pady=3)
        self.ent_alt = ttk.Entry(entradas, width=10)
        self.ent_alt.grid(row=3, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Quantidade:').grid(row=4, column=0, sticky='w', pady=3)
        self.ent_qtd = ttk.Entry(entradas, width=10)
        self.ent_qtd.grid(row=4, column=1, sticky='w', padx=6, pady=3)

        # --- Instalação / Estrutura metálica ---
        self.install_var = tk.BooleanVar()
        self.struct_var = tk.BooleanVar()

        ttk.Checkbutton(
            entradas, text="Incluir Instalação", variable=self.install_var,
            command=self.toggle_install
        ).grid(row=5, column=0, sticky='w', pady=3)
        self.ent_install = ttk.Entry(entradas, width=10, state='disabled')
        self.ent_install.grid(row=5, column=1, sticky='w', padx=6)

        ttk.Checkbutton(
            entradas, text="Estrutura Metálica + Instalação", variable=self.struct_var,
            command=self.toggle_struct
        ).grid(row=5, column=2, sticky='w', pady=3)
        self.ent_struct = ttk.Entry(entradas, width=10, state='disabled')
        self.ent_struct.grid(row=5, column=3, sticky='w', padx=6)

        ttk.Label(entradas, text='Preço (R$):').grid(row=6, column=0, sticky='w', pady=3)
        self.ent_preco = ttk.Entry(entradas, width=10)
        self.ent_preco.grid(row=6, column=1, sticky='w', padx=6, pady=3)

        ttk.Label(entradas, text='Cálculo:').grid(row=7, column=0, sticky='w', pady=3)
        self.tipo_calculo = ttk.Combobox(entradas, values=['Por unidade', 'Por m²'], state='readonly', width=15)
        self.tipo_calculo.set('Por unidade')
        self.tipo_calculo.grid(row=7, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Total (R$):').grid(row=4, column=2, sticky='w', pady=3)
        self.ent_total = ttk.Entry(entradas, width=16, state='readonly')
        self.ent_total.grid(row=4, column=3, sticky='w', padx=6, pady=3)

        ttk.Button(entradas, text='Calcular Total', bootstyle="info", command=self.calcular_total).grid(row=4, column=4, padx=6)
        ttk.Button(entradas, text='Adicionar Serviço', bootstyle="success", command=self.adicionar_servico).grid(row=1, column=4, rowspan=2, padx=8)
        entradas.columnconfigure(1, weight=1)

        # === Tabela de Serviços ===
        table_card = ttk.Labelframe(container, text="Tabela de Serviços", padding=10, bootstyle="info")
        table_card.pack(fill='both', expand=True, pady=(10, 0))
        cols = ('#', 'Descrição', 'Largura', 'Altura', 'Qtd', 'Preço', 'Total (R$)')
        self.tree = ttk.Treeview(table_card, columns=cols, show='headings', selectmode='browse', bootstyle="dark")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=300 if c == 'Descrição' else 100, anchor='center')
        self.tree.pack(fill='both', expand=True, side='left')

        vsb = ttk.Scrollbar(table_card, orient='vertical', command=self.tree.yview)
        vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=vsb.set)

        # Botões da tabela
        btns = ttk.Frame(container)
        btns.pack(fill='x', pady=(8, 0))
        ttk.Button(btns, text='Editar', bootstyle="secondary", command=self.editar_selecionado).pack(side='left', padx=6)
        ttk.Button(btns, text='Remover', bootstyle="danger", command=self.remover_selecionado).pack(side='left', padx=6)
        ttk.Button(btns, text='Limpar Serviços', bootstyle="warning-outline", command=self.limpar_servicos).pack(side='left', padx=6)

        # Footer
        footer = ttk.Frame(container)
        footer.pack(fill='x', pady=(12, 0))
        ttk.Label(footer, text='Total:').pack(side='left')
        ttk.Label(footer, textvariable=self.total_valor, font=('Segoe UI', 12, 'bold')).pack(side='left', padx=6)
        ttk.Button(footer, text='Gerar DOCX', bootstyle="success", command=self.gerar_documento).pack(side='right')

    # ==================== Cálculos ====================
    def calcular_total(self):
        calculator = TotalCalculator(
            self.produto_selecionado,
            self.ent_qtd,
            self.ent_preco,
            self.ent_larg,
            self.ent_alt,
            self.tipo_calculo,
            self.conn,
            self.ent_total,
            self.install_var,
            self.ent_install,
            self.struct_var,
            self.ent_struct
        )
        calculator.calcular_total()

    # ==================== Toggle install/struct ====================
    def toggle_install(self):
        if self.install_var.get():
            self.ent_install.config(state='normal')
            self.struct_var.set(False)
            self.ent_struct.config(state='disabled')
            self.ent_struct.delete(0, tk.END)
        else:
            self.ent_install.config(state='disabled')
            self.ent_install.delete(0, tk.END)

    def toggle_struct(self):
        if self.struct_var.get():
            self.ent_struct.config(state='normal')
            self.install_var.set(False)
            self.ent_install.config(state='disabled')
            self.ent_install.delete(0, tk.END)
        else:
            self.ent_struct.config(state='disabled')
            self.ent_struct.delete(0, tk.END)

    # ==================== Selecionar modelo / proposta ====================
    def selecionar_modelo(self):
        path = filedialog.askopenfilename(title='Selecione o modelo .docx', filetypes=[('Word Document', '*.docx')])
        if path:
            self.template_path.set(path)

    def _refresh_proposta(self):
        num = self.numero_proposta.get().strip()
        if not num:
            self.proposta_completa.set('(número não definido)')
            return
        try:
            nro = str(int(num)).zfill(2)
        except Exception:
            nro = num.zfill(2)
        self.proposta_completa.set(f"{nro}-{self.ano_atual}")

    # ==================== Adicionar serviço ====================
    def adicionar_servico(self):
        desc = self.ent_desc.get().strip().upper()
        qtd = self.ent_qtd.get().strip()
        preco = self.ent_preco.get().strip().replace(',', '.')
        total = self.ent_total.get().strip().replace(',', '.')
        larg = self.ent_larg.get().strip()
        alt = self.ent_alt.get().strip()

        larg = larg if larg else 'X'
        alt = alt if alt else 'X'

        if not desc:
            messagebox.showwarning('Aviso', 'A descrição é obrigatória')
            return
        if not total:
            self.calcular_total()

        try:
            qtd_i = int(qtd) if qtd else 1
            preco_f = float(preco) if preco else 0.0
            total_f = float(total)
        except Exception:
            messagebox.showwarning('Aviso', 'Valores numéricos inválidos')
            return

        item = {
            'Descrição': desc,
            'Largura': larg,
            'Altura': alt,
            'Quantidade': qtd_i,
            'Preço': preco_f,
            'Total (R$)': total_f
        }

        self.servicos.append(item)
        self._refresh_tree()
        self._clear_inputs()
        self._refresh_total()

    def _clear_inputs(self):
        for e in [self.ent_desc, self.ent_larg, self.ent_alt, self.ent_qtd, self.ent_preco, self.ent_total]:
            try:
                e.delete(0, tk.END)
            except Exception:
                pass

    def _refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, s in enumerate(self.servicos, start=1):
            self.tree.insert('', 'end', values=(idx, s['Descrição'], s['Largura'], s['Altura'],
                                                s['Quantidade'], f"R$ {s['Preço']:.2f}", f"R$ {s['Total (R$)']:.2f}"))

    def _refresh_total(self):
        total = sum(item['Total (R$)'] for item in self.servicos)
        self.total_valor.set(f"R$ {total:,.2f}")

    def editar_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Info', 'Nenhum item selecionado')
            return
        idx = int(self.tree.item(sel)['values'][0]) - 1
        item = self.servicos[idx]
        self.ent_desc.insert(0, item['Descrição'])
        self.ent_larg.insert(0, item['Largura'])
        self.ent_alt.insert(0, item['Altura'])
        self.ent_qtd.insert(0, str(item['Quantidade']))
        self.ent_preco.insert(0, f"{item['Preço']:.2f}")
        self.ent_total.insert(0, f"{item['Total (R$)']:.2f}")
        del self.servicos[idx]
        self._refresh_tree()
        self._refresh_total()

    def remover_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Info', 'Nenhum item selecionado')
            return
        idx = int(self.tree.item(sel)['values'][0]) - 1
        del self.servicos[idx]
        self._refresh_tree()
        self._refresh_total()

    def limpar_tudo(self):
        if messagebox.askyesno('Confirmar', 'Deseja remover todos os serviços?'):
            self.servicos.clear()
            self._refresh_tree()
            self._refresh_total()

    # ==================== Novo Produto Popup (ajustado) ====================
    def novo_produto_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Adicionar Novo Produto")
        popup.geometry("560x450")

        ttk.Label(popup, text="Nome:*").grid(row=0, column=0, sticky='w', pady=6, padx=6)
        ent_nome = ttk.Entry(popup, width=40)
        ent_nome.grid(row=0, column=1, pady=6, padx=6, columnspan=3)

        ttk.Label(popup, text="Tipo:*").grid(row=1, column=0, sticky='w', pady=6, padx=6)
        tipo_var = tk.StringVar(value='m2')
        rb_m2 = ttk.Radiobutton(popup, text='Preço por m²', variable=tipo_var, value='m2')
        rb_unit = ttk.Radiobutton(popup, text='Preço por Faixas (unitário)', variable=tipo_var, value='unit')
        rb_m = ttk.Radiobutton(popup, text='Preço por m (linear)', variable=tipo_var, value='m')
        rb_m2.grid(row=1, column=1, sticky='w')
        rb_unit.grid(row=1, column=2, sticky='w')
        rb_m.grid(row=1, column=3, sticky='w')

        # Preço m2
        ttk.Label(popup, text="Preço por m² (R$):").grid(row=2, column=0, sticky='w', pady=6, padx=6)
        ent_preco_m2 = ttk.Entry(popup, width=20)
        ent_preco_m2.grid(row=2, column=1, pady=6, padx=6, sticky='w')

        # Preço unitário simples
        ttk.Label(popup, text="Preço unitário (R$):").grid(row=3, column=0, sticky='w', pady=6, padx=6)
        ent_preco_unit = ttk.Entry(popup, width=20)
        ent_preco_unit.grid(row=3, column=1, pady=6, padx=6, sticky='w')

        # Faixas para produto unitário - texto livre (cada linha: min-max:price)
        ttk.Label(popup, text="Faixas (apenas se unitário, ex: 1-9:7)").grid(row=4, column=0, sticky='nw', pady=6, padx=6)
        txt_faixas = tk.Text(popup, width=50, height=8)
        txt_faixas.grid(row=4, column=1, columnspan=3, pady=6, padx=6)

        ttk.Label(popup, text="Largura (cm) [opcional]:").grid(row=5, column=0, sticky='w', pady=6, padx=6)
        ent_larg = ttk.Entry(popup, width=15)
        ent_larg.grid(row=5, column=1, pady=6, padx=6, sticky='w')

        ttk.Label(popup, text="Altura (cm) [opcional]:").grid(row=5, column=2, sticky='w', pady=6, padx=6)
        ent_alt = ttk.Entry(popup, width=15)
        ent_alt.grid(row=5, column=3, pady=6, padx=6, sticky='w')

        def parse_faixas(text):
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            tiers = []
            for line in lines:
                try:
                    left, price = line.split(':')
                    mn, mx = left.split('-')
                    tiers.append({"min": int(mn.strip()), "max": int(mx.strip()), "price": float(price.replace(',', '.').strip())})
                except Exception:
                    continue
            tiers.sort(key=lambda x: x['min'])
            return tiers

        def salvar_produto():
            nome = ent_nome.get().strip()
            tipo = tipo_var.get()
            preco_m2_val = None
            preco_m_val = None
            preco_unit_val = None
            tiers = None
            largura_val = None
            altura_val = None

            if not nome:
                messagebox.showwarning("Erro", "Nome obrigatório")
                return
            if tipo == 'm2':
                try:
                    preco_m2_val = float(ent_preco_m2.get().replace(',', '.'))
                except Exception:
                    messagebox.showwarning("Erro", "Preço por m² inválido")
                    return
            else:  # unit
                txt = txt_faixas.get("1.0", tk.END)
                tiers = parse_faixas(txt)
                # se não houver faixas válidas, aceita preço unitário simples
                if not tiers:
                    try:
                        if ent_preco_unit.get().strip():
                            preco_unit_val = float(ent_preco_unit.get().replace(',', '.'))
                        else:
                            messagebox.showwarning("Erro", "Insira faixas válidas ou um preço unitário")
                            return
                    except Exception:
                        messagebox.showwarning("Erro", "Preço unitário inválido")
                        return

            try:
                if ent_larg.get().strip():
                    largura_val = float(ent_larg.get().replace(',', '.'))
                if ent_alt.get().strip():
                    altura_val = float(ent_alt.get().replace(',', '.'))
            except Exception:
                messagebox.showwarning("Erro", "Largura/Altura inválida")
                return

            try:
                self.adicionar_produto_db(nome, tipo, preco_m2=preco_m2_val, preco_m=preco_m_val, preco_unit=preco_unit_val, tiers=tiers, largura=largura_val, altura=altura_val)
                messagebox.showinfo("Sucesso", f"Produto '{nome}' salvo.")
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar: {e}")

        ttk.Button(popup, text="Salvar", bootstyle="success", command=salvar_produto).grid(row=6, column=0, columnspan=4, pady=10)
        
    def gerar_documento(self):
        generator = docxGenerator(
            template_path=self.template_path,
            cliente=self.cliente,
            numero_proposta=self.numero_proposta,
            proposta_completa=self.proposta_completa,
            data_label=self.data_label,
            servicos=self.servicos
        )
        generator.gerar_docx()

if __name__ == "__main__":
    app = OrcamentoApp()
    app.mainloop()
    