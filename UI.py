"""
UI builder para o OrcamentoApp.
A classe `AppUI` recebe uma instância de `OrcamentoApp` e monta a interface,
atribuindo widgets como atributos da instância do app para compatibilidade.
"""
import tkinter as tk
from ttkbootstrap import ttk


class AppUI:
    def __init__(self, app):
        self.app = app
        self.build()

    def build(self):
        a = self.app
        container = ttk.Frame(a, padding=12)
        container.pack(fill='both', expand=True)

        # === Topo ===
        top_card = ttk.Labelframe(container, text="Modelo e Informações", padding=10, bootstyle="info")
        top_card.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(top_card)
        row1.pack(fill='x', pady=5)
        ttk.Label(row1, text='Modelo .docx:').pack(side='left')
        ttk.Label(row1, textvariable=a.template_path).pack(side='left', padx=8)
        ttk.Button(row1, text='Selecionar Modelo', bootstyle="secondary", command=a.selecionar_modelo).pack(side='right')

        form = ttk.Frame(top_card)
        form.pack(fill='x', pady=5)
        ttk.Label(form, text='Cliente:').grid(row=0, column=0, sticky='w')
        ttk.Entry(form, textvariable=a.cliente, width=50).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Label(form, text='Nº Proposta:').grid(row=1, column=0, sticky='w', pady=3)
        ttk.Entry(form, textvariable=a.numero_proposta, width=10).grid(row=1, column=1, sticky='w', padx=6, pady=3)
        ttk.Button(form, text='Atualizar', bootstyle="warning", command=a._refresh_proposta).grid(row=1, column=2, padx=6, pady=3)
        ttk.Label(form, text='Proposta:').grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(form, textvariable=a.proposta_completa, foreground='#1f6feb').grid(row=2, column=1, sticky='w', pady=3)
        ttk.Label(form, text='Data:').grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(form, textvariable=a.data_label).grid(row=3, column=1, sticky='w', pady=3)
        form.columnconfigure(1, weight=1)

        # === Card de Produtos ===
        add_card = ttk.Labelframe(container, text="Serviços / Produtos", padding=10, bootstyle="info")
        add_card.pack(fill='x', pady=(10, 0))
        entradas = ttk.Frame(add_card)
        entradas.pack(fill='x')

        ttk.Label(entradas, text='Produtos:').grid(row=0, column=0, sticky='w')
        a.cb_produtos = ttk.Combobox(
            entradas, textvariable=a.produto_selecionado, values=a.produtos_lista, state='readonly', width=40
        )
        a.cb_produtos.grid(row=0, column=1, sticky='w', padx=6)
        a.cb_produtos.bind('<<ComboboxSelected>>', a.carregar_produto)

        ttk.Button(
            entradas, text='Adicionar Novo Produto', bootstyle="secondary", command=a.novo_produto_popup
        ).grid(row=0, column=2, padx=6)

        # Novo: botão para gerenciar faixas do produto selecionado
        ttk.Button(entradas, text='Gerenciar Faixas (unit.)', bootstyle="outline-primary", command=a.gerenciar_faixas_popup).grid(row=0, column=3, padx=6)

        # Botões de gerenciamento
        ttk.Button(
            entradas, text='Remover Produto', bootstyle="danger", command=a.remover_produto_db
        ).grid(row=0, column=4, padx=6)

        ttk.Button(
            entradas, text='Limpar Campos', bootstyle="warning-outline", command=(a.clean.limpar_campos_produto if a.clean else a._clear_inputs)
        ).grid(row=0, column=5, padx=6)

        # Campos de produto/serviço
        ttk.Label(entradas, text='Descrição:').grid(row=1, column=0, sticky='w')
        a.ent_desc = ttk.Entry(entradas, width=40)
        a.ent_desc.grid(row=1, column=1, sticky='ew', padx=6)

        ttk.Label(entradas, text='Largura (cm):').grid(row=2, column=0, sticky='w', pady=3)
        a.ent_larg = ttk.Entry(entradas, width=10)
        a.ent_larg.grid(row=2, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Altura (cm):').grid(row=3, column=0, sticky='w', pady=3)
        a.ent_alt = ttk.Entry(entradas, width=10)
        a.ent_alt.grid(row=3, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Quantidade:').grid(row=4, column=0, sticky='w', pady=3)
        a.ent_qtd = ttk.Entry(entradas, width=10)
        a.ent_qtd.grid(row=4, column=1, sticky='w', padx=6, pady=3)
        # bind para atualização automática do preço quando for produto unitário
        a.ent_qtd.bind('<KeyRelease>', a._on_qtd_change)

        # --- Instalação / Estrutura metálica ---
        a.install_var = tk.BooleanVar()
        a.struct_var = tk.BooleanVar()

        ttk.Checkbutton(
            entradas, text="Incluir Instalação", variable=a.install_var,
            command=a.toggle_install
        ).grid(row=5, column=0, sticky='w', pady=3)
        a.ent_install = ttk.Entry(entradas, width=10, state='disabled')
        a.ent_install.grid(row=5, column=1, sticky='w', padx=6)

        ttk.Checkbutton(
            entradas, text="Estrutura Metálica + Instalação", variable=a.struct_var,
            command=a.toggle_struct
        ).grid(row=5, column=2, sticky='w', pady=3)
        a.ent_struct = ttk.Entry(entradas, width=10, state='disabled')
        a.ent_struct.grid(row=5, column=3, sticky='w', padx=6)

        ttk.Label(entradas, text='Preço (R$):').grid(row=6, column=0, sticky='w', pady=3)
        a.ent_preco = ttk.Entry(entradas, width=10)
        a.ent_preco.grid(row=6, column=1, sticky='w', padx=6, pady=3)

        ttk.Label(entradas, text='Cálculo:').grid(row=7, column=0, sticky='w', pady=3)
        a.tipo_calculo = ttk.Combobox(entradas, values=['Por unidade', 'Por m²', 'Por m'], state='readonly', width=15)
        a.tipo_calculo.set('Por unidade')
        a.tipo_calculo.grid(row=7, column=1, sticky='w', padx=6)

        ttk.Label(entradas, text='Total (R$):').grid(row=4, column=2, sticky='w', pady=3)
        a.ent_total = ttk.Entry(entradas, width=16, state='readonly')
        a.ent_total.grid(row=4, column=3, sticky='w', padx=6, pady=3)

        ttk.Button(entradas, text='Calcular Total', bootstyle="info", command=a.calcular_total).grid(row=4, column=4, padx=6)
        ttk.Button(entradas, text='Adicionar Serviço', bootstyle="success", command=a.adicionar_servico).grid(row=1, column=4, rowspan=2, padx=8)
        entradas.columnconfigure(1, weight=1)

        # === Tabela de Serviços ===
        table_card = ttk.Labelframe(container, text="Tabela de Serviços", padding=10, bootstyle="info")
        table_card.pack(fill='both', expand=True, pady=(10, 0))
        cols = ('#', 'Descrição', 'Largura', 'Altura', 'Qtd', 'Preço', 'Total (R$)')
        a.tree = ttk.Treeview(table_card, columns=cols, show='headings', selectmode='browse', bootstyle='dark')
        for c in cols:
            a.tree.heading(c, text=c)
            a.tree.column(c, width=300 if c == 'Descrição' else 100, anchor='center')
        a.tree.pack(fill='both', expand=True, side='left')

        vsb = ttk.Scrollbar(table_card, orient='vertical', command=a.tree.yview)
        vsb.pack(side='right', fill='y')
        a.tree.configure(yscrollcommand=vsb.set)

        # Botões da tabela
        btns = ttk.Frame(container)
        btns.pack(fill='x', pady=(8, 0))
        ttk.Button(btns, text='Editar', bootstyle="secondary", command=a.editar_selecionado).pack(side='left', padx=6)
        ttk.Button(btns, text='Remover', bootstyle="danger", command=a.remover_selecionado).pack(side='left', padx=6)
        ttk.Button(btns, text='Limpar Serviços', bootstyle="warning-outline", command=a.limpar_servicos).pack(side='left', padx=6)

        # Footer
        footer = ttk.Frame(container)
        footer.pack(fill='x', pady=(12, 0))
        ttk.Label(footer, text='Total:').pack(side='left')
        ttk.Label(footer, textvariable=a.total_valor, font=('Segoe UI', 12, 'bold')).pack(side='left', padx=6)
        ttk.Button(footer, text='Gerar DOCX', bootstyle="success", command=a.gerar_documento).pack(side='right')
