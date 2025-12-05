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
from tkinter import Scrollbar, filedialog, messagebox
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

# Importa as classes orientadas a objeto dos popups
try:
    from gerenciador_popup import NovoProdutoPopup, GerenciadorPopup
except Exception:
    NovoProdutoPopup = None
    GerenciadorPopup = None

# Importa builder de UI
try:
    from UI import AppUI
except Exception:
    AppUI = None

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

from total_calculator import TotalCalculator

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

        # Monta interface (UI movida para UI.AppUI)
        if AppUI is None:
            messagebox.showerror("Erro", "Módulo UI.py não encontrado — interface não construída.")
        else:
            AppUI(self)
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


    def novo_produto_popup(self):
        if NovoProdutoPopup is None:
            messagebox.showerror("Erro", "Classe NovoProdutoPopup não encontrada.")
            return
        def salvar_callback(nome, tipo, preco_m2, preco_m, preco_unit):
            self.adicionar_produto_db(
                nome,
                tipo,
                preco_m2=preco_m2,
                preco_m=preco_m,
                preco_unit=preco_unit,
                tiers=None
            )
        NovoProdutoPopup(self, self.conn, salvar_callback)

    def gerenciar_faixas_popup(self):
        if GerenciadorPopup is None:
            messagebox.showerror("Erro", "Classe GerenciadorPopup não encontrada.")
            return
        nome = self.produto_selecionado.get()
        if not nome:
            messagebox.showinfo('Info', 'Selecione um produto para gerenciar suas faixas')
            return
        GerenciadorPopup(self, self.conn, nome)

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
    