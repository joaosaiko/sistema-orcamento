import json
import tkinter as tk

class TotalCalculator:
    def __init__(
        self,
        produto_selecionado,
        ent_qtd,
        ent_preco,
        ent_larg,
        ent_alt,
        tipo_calculo,
        conn,
        ent_total,
        install_var,
        ent_install,
        struct_var,
        ent_struct,
    ):
        self.produto_selecionado = produto_selecionado
        self.ent_qtd = ent_qtd
        self.ent_preco = ent_preco
        self.ent_larg = ent_larg
        self.ent_alt = ent_alt
        self.tipo_calculo = tipo_calculo
        self.conn = conn
        self.ent_total = ent_total
        self.install_var = install_var
        self.ent_install = ent_install
        self.struct_var = struct_var
        self.ent_struct = ent_struct

    def calcular_total(self):
        try:
            qtd = int(float(self.ent_qtd.get().replace(',', '.') or 1))
        except Exception:
            qtd = 1

        try:
            preco_input = float(self.ent_preco.get().replace(',', '.') or 0)
        except Exception:
            preco_input = 0.0

        try:
            larg = float(self.ent_larg.get().replace(',', '.') or 0)
        except Exception:
            larg = 0.0
        try:
            alt = float(self.ent_alt.get().replace(',', '.') or 0)
        except Exception:
            alt = 0.0

        # --- Lógica de Detecção de Unidade (CM ou M) para o Cálculo ---
        # As entradas são rotuladas como (cm). 
        # Se o valor for menor que 20 (improvável para 2000cm), assumimos que o usuário digitou em METROS (m).
        # Caso contrário, o valor é tratado como CENTÍMETROS (cm) e convertido para M.
        
        if self.tipo_calculo.get() in ['Por m²', 'Por m']:
            # Se Largura < 20, assume-se que foi digitada em Metros (m).
            larg_m = larg if larg < 20.0 and larg > 0 else larg / 100.0
            # Se Altura < 20, assume-se que foi digitada em Metros (m).
            alt_m = alt if alt < 20.0 and alt > 0 else alt / 100.0
        else:
            # Se for 'Por unidade', a conversão é mais segura (cm -> m) para a descrição na tabela.
            larg_m = larg / 100.0
            alt_m = alt / 100.0

        area = larg_m * alt_m * qtd

        total = 0.0

        produto_nome = self.produto_selecionado.get().strip()
        if produto_nome:
            cursor = self.conn.cursor()
            cursor.execute("SELECT tipo, preco_m2, preco_m, preco_unit, tiers FROM produtos WHERE nome = ?", (produto_nome,))
            r = cursor.fetchone()
            if r:
                tipo_db, preco_m2, preco_unit, tiers_json = r
                if tipo_db == 'm2' and preco_m2 is not None:
                    total = area * float(preco_m2)
                elif tipo_db == 'unit' and tiers_json:
                    try:
                        tiers = json.loads(tiers_json)
                        unit_price = None
                        for t in tiers:
                            mn = int(t.get('min', 0))
                            mx = int(t.get('max', 10**9))
                            price = float(t.get('price', 0))
                            if mn <= qtd <= mx:
                                unit_price = price
                                break
                        if unit_price is None:
                            unit_price = preco_unit if preco_unit is not None else preco_input
                        total = qtd * unit_price
                    except Exception:
                        total = qtd * (preco_unit if preco_unit is not None else preco_input)
                elif tipo_db == 'unit' and preco_unit is not None:
                    total = qtd * float(preco_unit)
                else:
                    # fallback manual
                    if self.tipo_calculo.get() == 'Por m²':
                        total = area * preco_input
                    elif self.tipo_calculo.get() == 'Por m':
                        total = (larg_m * qtd) * preco_input
                    else:
                        total = qtd * preco_input
            else:
                # produto não encontrado
                if self.tipo_calculo.get() == 'Por m²':
                    total = area * preco_input
                elif self.tipo_calculo.get() == 'Por m':
                    total = (larg_m * qtd) * preco_input
                else:
                    total = qtd * preco_input
        else:
            # sem produto selecionado
            if self.tipo_calculo.get() == 'Por m²':
                total = area * preco_input
            elif self.tipo_calculo.get() == 'Por m':
                total = (larg_m * qtd) * preco_input
            else:
                total = qtd * preco_input

        # instalação/estrutura adicionam valor por área (somando ao total)
        if self.install_var.get():
            try:
                # Atenção: usa a área calculada acima (já em m²)
                inst = float(self.ent_install.get().replace(',', '.') or 0)
                total += area * inst
            except Exception:
                pass

        if self.struct_var.get():
            try:
                # Atenção: usa a área calculada acima (já em m²)
                struct = float(self.ent_struct.get().replace(',', '.') or 0)
                total += area * struct
            except Exception:
                pass

        self.ent_total.config(state='normal')
        self.ent_total.delete(0, tk.END)
        self.ent_total.insert(0, f"{total:.2f}")
        self.ent_total.config(state='readonly')