"""Módulo que contém a classe TotalCalculator extraída de `budget_system.py`.

Fornece a mesma lógica de cálculo de total usada pela UI.
"""
import tkinter as tk
from ttkbootstrap import ttk


class TotalCalculator:
	"""Calculadora simples que lê widgets/valores e calcula o total.
	Mantém compatibilidade com a implementação anterior em `budget_system.py`.
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

		def _parse_number_to_meters(s):
			"""Converte uma string numérica para metros.
			Aceita decimais com '.' ou ','; se o número for maior que 10 assume-se centímetros e divide por 100.
			Retorna None se inválido ou vazio.
			"""
			if not s:
				return None
			s = str(s).strip().replace(',', '.')
			if s.upper() == 'X':
				return None
			try:
				v = float(s)
			except Exception:
				return None
			# se valor aparentemente em centímetros (ex: 80, 120) converte para metros
			if v > 10:
				return v / 100.0
			# senão trata como metros (ex: 1.2, 0.8)
			return v

		def _maybe_split_pair(field):
			"""Se o campo contém 'x' como '80x120', retorna tuple (a, b) como strings (sem espaços).
			Caso contrário retorna None.
			"""
			if not field:
				return None
			if 'x' in field.lower():
				parts = [p.strip() for p in field.lower().split('x') if p.strip()]
				if len(parts) >= 2:
					return parts[0], parts[1]
			return None

		# tenta capturar entradas do tipo '80x120' colocadas em apenas um campo
		pair = _maybe_split_pair(larg_raw) or _maybe_split_pair(alt_raw)
		if pair and (not larg_raw or not alt_raw or 'x' in larg_raw.lower() or 'x' in alt_raw.lower()):
			# se encontramos um par em algum campo, atualizamos largura/altura bruta
			larg_raw, alt_raw = pair[0], pair[1]

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
			largura_m = _parse_number_to_meters(larg_raw)
			altura_m = _parse_number_to_meters(alt_raw)
			if largura_m and altura_m:
				area = largura_m * altura_m
				total = area * preco * qtd
			else:
				# se não foi possível calcular área, cai para preço * qtd
				total = preco * qtd
		elif tipo == 'Por m':
			# comprimento pode ser em cm (ex: 80) ou m (ex: 1.2)
			comprimento_m = _parse_number_to_meters(larg_raw)
			if comprimento_m:
				total = comprimento_m * preco * qtd
			else:
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

