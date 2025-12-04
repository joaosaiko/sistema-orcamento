#!/usr/bin/env python3
"""
Sistema de Orçamento - Integrado com faixas unitárias (tabelas)
Versão: adiciona suporte completo a produtos unitários com faixas em tabelas
Dependências:
pip install ttkbootstrap python-docx pandas

Observações:
- Substitui/integra a lógica anterior para lidar com produtos unitários em tabelas separadas
- Cria tabelas: produtos (existente), produtos_unitarios, faixas_unitarias
- Inclui popup para cadastrar/editar faixas por produto unitário
- Preenche automaticamente o preço ao digitar a quantidade para produtos unitários
- Contém um TotalCalculator local (substitui a dependência features.total para esta versão)

Use este arquivo como drop-in ou referência para adaptar ao seu projeto.
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

# Se você possui módulos externos (Clean, docxGenerator), mantenha os imports
try:
    from features.clean import Clean  # opcional
except Exception:
    Clean = None

try:
    from features.gerar_docx import docxGenerator
except Exception:
    docxGenerator = None

DB_PATH = "produtos.db"

# ----------------------- Helpers para DB das faixas unitárias -----------------------
def get_conn(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Cria/atualiza tabelas necessárias: produtos (compatível), produtos_unitarios, faixas_unitarias."""
    cursor = conn.cursor()

    # tabela produtos (mantemos compatibilidade com seu schema anterior)
    cursor.execute("PRAGMA table_info(produtos)")
    cols = [r[1] for r in cursor.fetchall()]
    if not cols:
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

    # tabela produtos_unitarios: mapeia um produto unitário com um id próprio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos_unitarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    """)

    # tabela faixas_unitarias: faixas por produto_unitario
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faixas_unitarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            qtd_min INTEGER NOT NULL,
            qtd_max INTEGER NOT NULL,
            preco REAL NOT NULL,
            FOREIGN KEY(produto_id) REFERENCES produtos_unitarios(id)
        )
    """)

    conn.commit()


# ----------------------- CRUD para produtos unitários e faixas -----------------------
def ensure_produto_unitario(conn, nome):
    """Garante que exista um registro em produtos_unitarios com esse nome. Retorna id."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (nome,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute("INSERT INTO produtos_unitarios (nome) VALUES (?)", (nome,))
    conn.commit()
    return cursor.lastrowid


def delete_produto_unitario(conn, nome):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (nome,))
    row = cursor.fetchone()
    if not row:
        return False
    pid = row["id"]
    cursor.execute("DELETE FROM faixas_unitarias WHERE produto_id = ?", (pid,))
    cursor.execute("DELETE FROM produtos_unitarios WHERE id = ?", (pid,))
    conn.commit()
    return True


def add_faixa(conn, produto_nome, qtd_min, qtd_max, preco):
    pid = ensure_produto_unitario(conn, produto_nome)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO faixas_unitarias (produto_id, qtd_min, qtd_max, preco) VALUES (?, ?, ?, ?)",
        (pid, int(qtd_min), int(qtd_max), float(preco)),
    )
    conn.commit()
    return cursor.lastrowid


def update_faixa(conn, faixa_id, qtd_min, qtd_max, preco):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE faixas_unitarias SET qtd_min = ?, qtd_max = ?, preco = ? WHERE id = ?",
        (int(qtd_min), int(qtd_max), float(preco), int(faixa_id)),
    )
    conn.commit()


def delete_faixa(conn, faixa_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faixas_unitarias WHERE id = ?", (int(faixa_id),))
    conn.commit()


def get_faixas_por_produto(conn, produto_nome):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (produto_nome,))
    row = cursor.fetchone()
    if not row:
        return []
    pid = row["id"]
    cursor.execute(
        "SELECT id, qtd_min, qtd_max, preco FROM faixas_unitarias WHERE produto_id = ? ORDER BY qtd_min",
        (pid,)
    )
    return [dict(r) for r in cursor.fetchall()]


def get_preco_por_quantidade(conn, produto_nome, quantidade):
    try:
        qtd = int(quantidade)
    except Exception:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (produto_nome,))
    row = cursor.fetchone()
    if not row:
        return None
    pid = row["id"]
    cursor.execute(
        "SELECT preco FROM faixas_unitarias WHERE produto_id = ? AND ? BETWEEN qtd_min AND qtd_max LIMIT 1",
        (pid, qtd),
    )
    r = cursor.fetchone()
    return float(r["preco"]) if r else None


# ----------------------- TotalCalculator local -----------------------
class TotalCalculator:
    """Calculadora simples que lê widgets/valores e calcula o total.
    Substitui a dependência externa para o propósito desta integração.
    """
    def __init__(self, produto_selecionado_var, ent_qtd, ent_preco, ent_larg, ent_alt, tipo_calculo_widget, conn, ent_total, install_var=None, ent_install=None, struct_var=None, ent_struct=None):
        self.produto_sel = produto_selecionado_var
        self.ent_qtd = ent_qtd
        self.ent_preco = ent_preco
        self.ent_larg = ent_larg
        self.ent_alt = ent_alt
        self.tipo_calculo = tipo_calculo_widget
        self.conn = conn
        self.ent_total = ent_total
        self.install_var = install_var
        self.ent_install = ent_install
        self.struct_var = struct_var
        self.ent_struct = ent_struct

    def calcular_total(self):
        # pega valores
        tipo = self.tipo_calculo.get() if isinstance(self.tipo_calculo, ttk.Combobox) else self.tipo_calculo
        preco_raw = self.ent_preco.get().strip().replace(',', '.') if hasattr(self.ent_preco, 'get') else str(self.ent_preco)
        qtd_raw = self.ent_qtd.get().strip() if hasattr(self.ent_qtd, 'get') else str(self.ent_qtd)
        larg_raw = self.ent_larg.get().strip() if hasattr(self.ent_larg, 'get') else str(self.ent_larg)
        alt_raw = self.ent_alt.get().strip() if hasattr(self.ent_alt, 'get') else str(self.ent_alt)

        try:
            preco = float(preco_raw) if preco_raw else 0.0
        except Exception:
            preco = 0.0
        try:
            qtd = int(qtd_raw) if qtd_raw else 1
        except Exception:
            qtd = 1

        total = 0.0
        if tipo == 'Por m²':
            # converter cm -> metros
            try:
                largura = float(larg_raw) / 100.0 if larg_raw and larg_raw != 'X' else None
                altura = float(alt_raw) / 100.0 if alt_raw and alt_raw != 'X' else None
                if largura and altura:
                    area = largura * altura
                    total = area * preco * qtd
                else:
                    total = preco * qtd
            except Exception:
                total = preco * qtd
        elif tipo == 'Por m':
            # largura representa o comprimento em metros ou cm?
            try:
                comprimento = float(larg_raw) / 100.0 if larg_raw and larg_raw != 'X' else None
                if comprimento:
                    total = comprimento * preco * qtd
                else:
                    total = preco * qtd
            except Exception:
                total = preco * qtd
        else:  # Por unidade
            total = preco * qtd

        # incluir instalação/estrutura se houver (assume valor por item)
        try:
            if self.install_var and self.install_var.get():
                inst_val = float(self.ent_install.get().strip().replace(',', '.')) if self.ent_install.get().strip() else 0.0
                total += inst_val
            if self.struct_var and self.struct_var.get():
                struct_val = float(self.ent_struct.get().strip().replace(',', '.')) if self.ent_struct.get().strip() else 0.0
                total += struct_val
        except Exception:
            pass

        # formata e coloca no campo
        try:
            self.ent_total.config(state='normal')
            self.ent_total.delete(0, tk.END)
            self.ent_total.insert(0, f"{total:.2f}")
            self.ent_total.config(state='readonly')
        except Exception:
            # se for apenas um widget sem .config
            try:
                self.ent_total.set(f"{total:.2f}")
            except Exception:
                pass


# ----------------------- Aplicação principal (UI) -----------------------
class OrcamentoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Orçamento - Gráfica (Unitários em Tabelas)")
        self.geometry("1100x760")
        self.minsize(1000, 660)
        self.style = Style(theme="darkly")

        # Variáveis
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
        self.conn = get_conn()
        init_db(self.conn)
        self._corrigir_estrutura_produtos()

        # Produto selecionado
        self.produto_selecionado = tk.StringVar()
        self.produtos_lista = []

        # Limpeza (opcional)
        self.clean = Clean(self) if Clean else None

        # Monta interface
        self._build_ui()
        self._refresh_proposta()
        self._refresh_total()
        self._atualizar_produtos()

        # protocolo de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ==================== Banco de Dados (compatibilidade atualizada) ====================
    def _corrigir_estrutura_produtos(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(produtos)")
        cols_info = cursor.fetchall()
        existing_cols = [c[1] for c in cols_info]

        def add_col(col_def):
            try:
                cursor.execute(f"ALTER TABLE produtos ADD COLUMN {col_def}")
            except Exception:
                pass

        needed_cols = {
            "tipo": "tipo TEXT",
            "largura": "largura REAL",
            "altura": "altura REAL",
            "preco_m2": "preco_m2 REAL",
            "preco_m": "preco_m REAL",
            "preco_unit": "preco_unit REAL",
            "tiers": "tiers TEXT",
        }
        for col_name, col_def in needed_cols.items():
            if col_name not in existing_cols:
                add_col(col_def)
        self.conn.commit()

    # ---------------- DB helpers (produtos table) ----------------
    def adicionar_produto_db(self, nome, tipo, preco_m2=None, preco_m=None, preco_unit=None, tiers=None, largura=None, altura=None):
        cursor = self.conn.cursor()
        tiers_json = json.dumps(tiers, ensure_ascii=False) if tiers else None
        cursor.execute(
            "INSERT OR REPLACE INTO produtos (nome, tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nome, tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers_json),
        )
        self.conn.commit()

        # se for unit e tiver faixas (ou não), garantimos tabela produtos_unitarios esteja consistente
        if tipo == 'unit':
            ensure_produto_unitario(self.conn, nome)

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

            if tipo == 'm2' and preco_m2 is not None:
                self.ent_preco.insert(0, str(preco_m2))
                self.tipo_calculo.set('Por m²')
            elif tipo == 'm' and preco_m is not None:
                self.ent_preco.insert(0, str(preco_m))
                self.tipo_calculo.set('Por m')
            elif tipo == 'unit':
                # tenta carregar preco por faixa (com qtd atual) ou preco_unit
                self.tipo_calculo.set('Por unidade')
                qtd = None
                try:
                    qtd_raw = self.ent_qtd.get().strip()
                    qtd = int(qtd_raw) if qtd_raw else None
                except Exception:
                    qtd = None
                if qtd:
                    preco = get_preco_por_quantidade(self.conn, nome, qtd)
                    if preco is not None:
                        self.ent_preco.insert(0, str(preco))
                        self.calcular_total()
                        return
                # fallback para preco_unit
                if preco_unit is not None:
                    self.ent_preco.insert(0, str(preco_unit))
                else:
                    # se tiver faixas, mostra a primeira como referência
                    faixas = get_faixas_por_produto(self.conn, nome)
                    if faixas:
                        self.ent_preco.insert(0, str(faixas[0]['preco']))

            self.ent_qtd.delete(0, tk.END)
            self.ent_qtd.insert(0, "1")
            self.calcular_total()

    # ---------------- Funções de remoção/limpeza ----------------
    def remover_produto_db(self):
        nome = self.produto_selecionado.get()
        if not nome:
            messagebox.showinfo("Info", "Selecione um produto para remover.")
            return
        if not messagebox.askyesno("Confirmar", f"Deseja realmente remover o produto '{nome}'?"):
            return
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM produtos WHERE nome = ?", (nome,))
        # removemos também das tabelas unitárias para manter consistente
        delete_produto_unitario(self.conn, nome)
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
        cursor.execute("DELETE FROM produtos_unitarios")
        cursor.execute("DELETE FROM faixas_unitarias")
        self.conn.commit()
        messagebox.showinfo("Sucesso", "Todos os produtos foram removidos.")
        self._atualizar_produtos()
        try:
            self._clear_produto_inputs()
        except Exception:
            pass
    
    def limpar_servicos(self):
        """Remove todos os serviços da treeview e zera o total."""
        for item in self.tree_servicos.get_children():
            self.tree_servicos.delete(item)

        self.ent_total.delete(0, tk.END)
        self.ent_total.insert(0, "0.00")


    # ==================== UI ====================
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

        # Novo: botão para gerenciar faixas do produto selecionado
        ttk.Button(entradas, text='Gerenciar Faixas (unit.)', bootstyle="outline-primary", command=self.gerenciar_faixas_popup).grid(row=0, column=3, padx=6)

        # Botões de gerenciamento
        ttk.Button(
            entradas, text='Remover Produto', bootstyle="danger", command=self.remover_produto_db
        ).grid(row=0, column=4, padx=6)

        ttk.Button(
            entradas, text='Limpar Campos', bootstyle="warning-outline", command=(self.clean.limpar_campos_produto if self.clean else self._clear_inputs)
        ).grid(row=0, column=5, padx=6)

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
        # bind para atualização automática do preço quando for produto unitário
        self.ent_qtd.bind('<KeyRelease>', self._on_qtd_change)

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
        self.tipo_calculo = ttk.Combobox(entradas, values=['Por unidade', 'Por m²', 'Por m'], state='readonly', width=15)
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
        self.tree = ttk.Treeview(table_card, columns=cols, show='headings', selectmode='browse', bootstyle='dark')
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
            self.ent_struct,
        )
        calculator.calcular_total()

    # bind da quantidade para auto ajuste do preço em produtos unitários
    def _on_qtd_change(self, event=None):
        nome = self.produto_selecionado.get()
        if not nome:
            return

        cursor = self.conn.cursor()
        cursor.execute("SELECT tipo FROM produtos WHERE nome = ?", (nome,))
        r = cursor.fetchone()
        tipo = r[0] if r else None

        if tipo == 'unit':
            qtd = self.ent_qtd.get().strip()
            preco = get_preco_por_quantidade(self.conn, nome, qtd)
            if preco is not None:
                # ATUALIZA O PREÇO NA INTERFACE
                self.ent_preco.delete(0, tk.END)
                self.ent_preco.insert(0, f"{preco:.2f}")
                # E SÓ DEPOIS RECALCULA O TOTAL
                self.calcular_total()


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

    # ==================== Novo Produto Popup (ajustado para unitários) ====================
    def novo_produto_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Adicionar Novo Produto")
        popup.geometry("640x520")

        ttk.Label(popup, text="Nome:*").grid(row=0, column=0, sticky='w', pady=6, padx=6)
        ent_nome = ttk.Entry(popup, width=40)
        ent_nome.grid(row=0, column=1, pady=6, padx=6, columnspan=3)

        ttk.Label(popup, text="Tipo:* (unit | m2 | m)").grid(row=1, column=0, sticky='w', pady=6, padx=6)
        tipo_var = tk.StringVar(value='unit')
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

        # Preço por m linear
        ttk.Label(popup, text="Preço por m (linear) (R$):").grid(row=2, column=2, sticky='w', pady=6, padx=6)
        ent_preco_m = ttk.Entry(popup, width=20)
        ent_preco_m.grid(row=2, column=3, pady=6, padx=6, sticky='w')

        # Preço unitário simples (fallback)
        ttk.Label(popup, text="Preço unitário (R$):").grid(row=3, column=0, sticky='w', pady=6, padx=6)
        ent_preco_unit = ttk.Entry(popup, width=20)
        ent_preco_unit.grid(row=3, column=1, pady=6, padx=6, sticky='w')

        # Faixas para produto unitário - tabela simples (Treeview)
        ttk.Label(popup, text="Faixas (apenas se unitário):").grid(row=4, column=0, sticky='nw', pady=6, padx=6)
        frame_faixas = ttk.Frame(popup)
        frame_faixas.grid(row=4, column=1, columnspan=3, pady=6, padx=6, sticky='nsew')
        popup.rowconfigure(4, weight=1)
        popup.columnconfigure(3, weight=1)

        cols = ("id", "min", "max", "preco")
        tree_faixas = ttk.Treeview(frame_faixas, columns=cols, show='headings', height=6)
        for c in cols:
            tree_faixas.heading(c, text=c)
            tree_faixas.column(c, width=80)
        tree_faixas.pack(side='left', fill='both', expand=True)

        vsb = ttk.Scrollbar(frame_faixas, orient='vertical', command=tree_faixas.yview)
        vsb.pack(side='right', fill='y')
        tree_faixas.configure(yscrollcommand=vsb.set)

        # inputs para nova faixa
        ttk.Label(popup, text="Qtd min:").grid(row=5, column=0, sticky='w', pady=6, padx=6)
        ent_qmin = ttk.Entry(popup, width=10)
        ent_qmin.grid(row=5, column=1, sticky='w')
        ttk.Label(popup, text="Qtd max:").grid(row=5, column=2, sticky='w', pady=6, padx=6)
        ent_qmax = ttk.Entry(popup, width=10)
        ent_qmax.grid(row=5, column=3, sticky='w')
        ttk.Label(popup, text="Preço (R$):").grid(row=6, column=0, sticky='w', pady=6, padx=6)
        ent_qpreco = ttk.Entry(popup, width=15)
        ent_qpreco.grid(row=6, column=1, sticky='w')

        def carregar_faixas_para_tree():
            # 1. Obter a conexão e o nome do produto selecionado
            conn = get_conn() # Assumindo que você tem uma função get_conn() acessível
            nome_produto = 'Nome do Produto Selecionado na UI' # Obter o nome da UI
            
            # 2. Usar a função utilitária
            faixas = get_faixas_por_produto(conn, nome_produto)
            
            # 3. Limpar e popular o Treeview com os dados de 'faixas'
            # ...
            conn.close()

        def adicionar_faixa_local():
            nome = ent_nome.get().strip()
            if not nome:
                messagebox.showwarning('Erro', 'Informe o nome do produto antes de adicionar faixas')
                return
            try:
                qmin = int(ent_qmin.get().strip())
                qmax = int(ent_qmax.get().strip())
                preco = float(ent_qpreco.get().strip().replace(',', '.'))
            except Exception:
                messagebox.showwarning('Erro', 'Valores de faixa inválidos')
                return
            add_faixa(self.conn, nome, qmin, qmax, preco)
            carregar_faixas_para_tree(nome)
            ent_qmin.delete(0, tk.END)
            ent_qmax.delete(0, tk.END)
            ent_qpreco.delete(0, tk.END)

        def remover_faixa_local():
            sel = tree_faixas.selection()
            if not sel:
                return
            faixa_id = tree_faixas.item(sel)['values'][0]
            delete_faixa(self.conn, faixa_id)
            carregar_faixas_para_tree(ent_nome.get().strip())

        ttk.Button(popup, text='Adicionar Faixa', command=adicionar_faixa_local).grid(row=7, column=1, pady=6)
        ttk.Button(popup, text='Remover Faixa', command=remover_faixa_local).grid(row=7, column=2, pady=6)

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
            elif tipo == 'm':
                try:
                    preco_m_val = float(ent_preco_m.get().replace(',', '.'))
                except Exception:
                    messagebox.showwarning("Erro", "Preço por metro linear inválido")
                    return
            elif tipo == 'unit':
                # faixas já salvas dinamicamente quando adicionadas no popup
                try:
                    if ent_preco_unit.get().strip():
                        preco_unit_val = float(ent_preco_unit.get().replace(',', '.'))
                except Exception:
                    messagebox.showwarning("Erro", "Preço unitário inválido")
                    return

            # largura/altura (opcional)
            try:
                if ent_preco_m2.get().strip():
                    pass
            except Exception:
                pass

            try:
                self.adicionar_produto_db(nome, tipo, preco_m2=preco_m2_val, preco_m=preco_m_val, preco_unit=preco_unit_val, tiers=None, largura=largura_val, altura=altura_val)
                messagebox.showinfo("Sucesso", f"Produto '{nome}' salvo.")
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar: {e}")

        ttk.Button(popup, text="Salvar", bootstyle="success", command=salvar_produto).grid(row=8, column=0, columnspan=4, pady=10)

        # se nome já existir, carregar faixas
        def on_nome_change(event=None):
            nome = ent_nome.get().strip()
            if nome:
                carregar_faixas_para_tree(nome)

        ent_nome.bind('<FocusOut>', on_nome_change)

    # ==================== Popup para gerenciar faixas de produto já existente ====================
    def gerenciar_faixas_popup(self):
        nome = self.produto_selecionado.get()
        if not nome:
            messagebox.showinfo('Info', 'Selecione um produto para gerenciar suas faixas')
            return

        popup = tk.Toplevel(self)
        popup.title(f"Gerenciar Faixas - {nome}")
        popup.geometry('600x450')

        # --- Treeview ---
        cols = ('ID', 'Qtd Min', 'Qtd Max', 'Preço')
        tree = ttk.Treeview(popup, columns=cols, show='headings')
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=100)
        tree.pack(fill='both', expand=True, padx=8, pady=8)

        # --- Inputs ---
        frame_inputs = ttk.Frame(popup)
        frame_inputs.pack(fill='x', padx=8, pady=4)

        ttk.Label(frame_inputs, text='Qtd Min').grid(row=0, column=0)
        ent_qmin = ttk.Entry(frame_inputs, width=8)
        ent_qmin.grid(row=0, column=1)

        ttk.Label(frame_inputs, text='Qtd Max').grid(row=0, column=2)
        ent_qmax = ttk.Entry(frame_inputs, width=8)
        ent_qmax.grid(row=0, column=3)

        ttk.Label(frame_inputs, text='Preço').grid(row=0, column=4)
        ent_qpreco = ttk.Entry(frame_inputs, width=12)
        ent_qpreco.grid(row=0, column=5)

        # ====== Funções ======
        def carregar_faixas_para_tree():
            tree.delete(*tree.get_children())
            faixas = get_faixas_por_produto(self.conn, nome)
            for f in faixas:
                tree.insert('', 'end', values=(f['id'], f['qtd_min'], f['qtd_max'], f['preco']))

        def faixa_sobreposta(qmin, qmax, ignore_id=None):
            faixas = get_faixas_por_produto(self.conn, nome)
            for f in faixas:
                if ignore_id is not None and f['id'] == ignore_id:
                    continue
                fmin, fmax = f['qtd_min'], f['qtd_max']
                if not (qmax < fmin or qmin > fmax):
                    return True
            return False

        # ================= Validação =================
        def ler_inputs():
            qmin_str = ent_qmin.get().strip()
            qmax_str = ent_qmax.get().strip()
            preco_str = ent_qpreco.get().strip().replace(',', '.')

            if not qmin_str or not qmax_str or not preco_str:
                messagebox.showwarning('Erro', 'Preencha todos os campos')
                return None

            try:
                qmin = int(qmin_str)
                qmax = int(qmax_str)
                preco = float(preco_str)
            except:
                messagebox.showwarning('Erro', 'Valores de faixa inválidos')
                return None

            if qmin <= 0 or qmax <= 0 or qmin > qmax:
                messagebox.showwarning('Erro', 'Qtd Min deve ser ≤ Qtd Max e ambos positivos')
                return None

            return qmin, qmax, preco

        # =============== Operações ===============
        def adicionar_faixa_local():
            valores = ler_inputs()
            if valores is None:
                return

            qmin, qmax, preco = valores

            if faixa_sobreposta(qmin, qmax):
                messagebox.showwarning('Erro', 'Faixa sobrepõe outra já existente')
                return

            add_faixa(self.conn, nome, qmin, qmax, preco)
            carregar_faixas_para_tree()

            ent_qmin.delete(0, tk.END)
            ent_qmax.delete(0, tk.END)
            ent_qpreco.delete(0, tk.END)

        def editar_faixa_local():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo('Info', 'Selecione uma faixa para editar')
                return
            
            fid = tree.item(sel)['values'][0]

            valores = ler_inputs()
            if valores is None:
                return

            qmin, qmax, preco = valores

            if faixa_sobreposta(qmin, qmax, ignore_id=fid):
                messagebox.showwarning('Erro', 'Faixa sobrepõe outra já existente')
                return

            update_faixa(self.conn, fid, qmin, qmax, preco)
            carregar_faixas_para_tree()

        def remover_faixa_local():
            sel = tree.selection()
            if not sel:
                return
            fid = tree.item(sel)['values'][0]
            delete_faixa(self.conn, fid)
            carregar_faixas_para_tree()

        # --- Botões ---
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill='x', padx=8, pady=4)

        ttk.Button(btn_frame, text='Adicionar', command=adicionar_faixa_local).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Editar', command=editar_faixa_local).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Remover', command=remover_faixa_local).pack(side='left', padx=4)

        carregar_faixas_para_tree()



    # ==================== Gerar documento (usa docxGenerator se disponível) ====================
    def gerar_documento(self):
        if docxGenerator:
            generator = docxGenerator(
                template_path=self.template_path.get() if isinstance(self.template_path, tk.StringVar) else self.template_path,
                cliente=self.cliente.get() if isinstance(self.cliente, tk.StringVar) else self.cliente,
                numero_proposta=self.numero_proposta.get() if isinstance(self.numero_proposta, tk.StringVar) else self.numero_proposta,
                proposta_completa=self.proposta_completa.get() if isinstance(self.proposta_completa, tk.StringVar) else self.proposta_completa,
                data_label=self.data_label.get() if isinstance(self.data_label, tk.StringVar) else self.data_label,
                servicos=self.servicos
            )
            generator.gerar_docx()
        else:
            # fallback simples: exporta CSV
            df = pd.DataFrame(self.servicos)
            fname = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV','*.csv')])
            if not fname:
                return
            df.to_csv(fname, index=False)
            messagebox.showinfo('Exportado', f'Arquivo salvo em {fname}')

    def on_close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = OrcamentoApp()
    app.mainloop()
    