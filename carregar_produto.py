import sqlite3
import tkinter as tk


class CarregarProduto:
    """Classe responsável por carregar dados do produto na interface.

    Usa `app` (instância de `OrcamentoApp`) para acessar widgets e conexão com DB.
    """

    def __init__(self, app):
        self.app = app
        # usa a conexão já aberta pela aplicação
        self.conn = getattr(app, 'conn', None)

    def _get_faixas_por_produto(self, produto_nome):
        if not produto_nome or not self.conn:
            return []
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (produto_nome,))
        row = cursor.fetchone()
        if not row:
            return []
        pid = row[0]
        cursor.execute(
            "SELECT id, qtd_min, qtd_max, preco FROM faixas_unitarias WHERE produto_id = ? ORDER BY qtd_min",
            (pid,)
        )
        return [dict(r) for r in cursor.fetchall()]

    def _get_preco_por_quantidade(self, produto_nome, quantidade):
        if not produto_nome or not self.conn:
            return None
        try:
            qtd = int(quantidade)
        except Exception:
            return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM produtos_unitarios WHERE nome = ?", (produto_nome,))
        row = cursor.fetchone()
        if not row:
            return None
        pid = row[0]
        cursor.execute(
            "SELECT preco FROM faixas_unitarias WHERE produto_id = ? AND ? BETWEEN qtd_min AND qtd_max LIMIT 1",
            (pid, qtd),
        )
        r = cursor.fetchone()
        return float(r[0]) if r else None

    def carregar_produto(self, event=None):
        nome = self.app.produto_selecionado.get()
        if not nome:
            return
        cursor = self.conn.cursor()
        cursor.execute("SELECT tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers FROM produtos WHERE nome = ?", (nome,))
        result = cursor.fetchone()
        if result:
            tipo, largura, altura, preco_m2, preco_m, preco_unit, tiers_json = result
            # atualiza campos da UI (usa referências da app)
            try:
                self.app.ent_desc.delete(0, tk.END)
                self.app.ent_desc.insert(0, nome)
            except Exception:
                pass
            try:
                self.app.ent_larg.delete(0, tk.END)
                self.app.ent_alt.delete(0, tk.END)
                if largura is not None:
                    self.app.ent_larg.insert(0, str(largura))
                if altura is not None:
                    self.app.ent_alt.insert(0, str(altura))
            except Exception:
                pass

            try:
                self.app.ent_preco.delete(0, tk.END)
            except Exception:
                pass

            if tipo == 'm2' and preco_m2 is not None:
                try:
                    self.app.ent_preco.insert(0, str(preco_m2))
                    self.app.tipo_calculo.set('Por m²')
                except Exception:
                    pass
            elif tipo == 'm' and preco_m is not None:
                try:
                    self.app.ent_preco.insert(0, str(preco_m))
                    self.app.tipo_calculo.set('Por m')
                except Exception:
                    pass
            elif tipo == 'unit':
                try:
                    self.app.tipo_calculo.set('Por unidade')
                except Exception:
                    pass
                qtd = None
                try:
                    qtd_raw = self.app.ent_qtd.get().strip()
                    qtd = int(qtd_raw) if qtd_raw else None
                except Exception:
                    qtd = None
                if qtd:
                    preco = self._get_preco_por_quantidade(nome, qtd)
                    if preco is not None:
                        try:
                            self.app.ent_preco.insert(0, str(preco))
                            self.app.calcular_total()
                            return
                        except Exception:
                            pass
                # fallback preco_unit
                if preco_unit is not None:
                    try:
                        self.app.ent_preco.insert(0, str(preco_unit))
                    except Exception:
                        pass
                else:
                    faixas = self._get_faixas_por_produto(nome)
                    if faixas:
                        try:
                            self.app.ent_preco.insert(0, str(faixas[0]['preco']))
                        except Exception:
                            pass

        try:
            self.app.ent_qtd.delete(0, tk.END)
            self.app.ent_qtd.insert(0, "1")
        except Exception:
            pass
        # garante recálculo
        try:
            self.app.calcular_total()
        except Exception:
            pass

    def on_qtd_change(self, event=None):
        nome = self.app.produto_selecionado.get()
        if not nome:
            return

        cursor = self.conn.cursor()
        cursor.execute("SELECT tipo FROM produtos WHERE nome = ?", (nome,))
        r = cursor.fetchone()
        tipo = r[0] if r else None

        if tipo == 'unit':
            qtd = self.app.ent_qtd.get().strip()
            preco = self._get_preco_por_quantidade(nome, qtd)
            if preco is not None:
                try:
                    self.app.ent_preco.delete(0, tk.END)
                    self.app.ent_preco.insert(0, f"{preco:.2f}")
                    self.app.calcular_total()
                except Exception:
                    pass
