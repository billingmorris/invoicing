# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    tax_detail_ids = fields.One2many(
        'account.invoice.tax.detail',
        'move_id',
        string='Detalle de impuestos',
        compute='_compute_tax_detail_ids',
    )

    has_tax_detail = fields.Boolean(
        compute='_compute_tax_detail_ids',
        store=False,
    )

    @api.depends(
        'invoice_line_ids',
        'invoice_line_ids.price_unit',
        'invoice_line_ids.quantity',
        'invoice_line_ids.discount',
        'invoice_line_ids.tax_ids',
        'invoice_line_ids.price_subtotal',
        'currency_id',
        'fiscal_position_id',
    )
    def _compute_tax_detail_ids(self):
        """
        Calcula el detalle de impuestos agrupado por impuesto.

        Estrategia: leer las lineas de tipo 'tax' de account.move.line,
        que son las lineas contables que Odoo genera para los impuestos.
        Estas lineas ya contienen el valor real calculado por el motor
        fiscal de Odoo, incluyendo redondeos, impuestos incluidos, etc.

        Para la base gravable, se busca la linea de tipo 'tax' en
        account.move.line y se acumula el campo tax_base_amount,
        que Odoo calcula y almacena en cada linea de impuesto.
        """
        TaxDetail = self.env['account.invoice.tax.detail']

        for move in self:
            # Limpiar registros transient anteriores de este move
            TaxDetail.search([('move_id', '=', move.id)]).unlink()

            if move.move_type not in (
                'out_invoice', 'out_refund',
                'in_invoice', 'in_refund',
            ):
                move.tax_detail_ids = TaxDetail
                move.has_tax_detail = False
                continue

            # Acumulador: { tax_id: {'name': ..., 'base': ..., 'amount': ...} }
            tax_groups = {}

            # Las lineas de tipo 'tax' en account.move.line contienen:
            #   tax_line_id  -> el impuesto al que corresponde la linea
            #   tax_base_amount -> base gravable calculada por Odoo
            #   balance / amount_currency -> valor del impuesto
            #
            # Usamos amount_currency para respetar la moneda de la factura.
            # balance siempre esta en moneda de la compania.
            for line in move.line_ids.filtered(
                lambda l: l.display_type == 'tax' and l.tax_line_id
            ):
                tax = line.tax_line_id
                tid = tax.id

                # El signo de amount_currency ya refleja si es retension (negativo)
                # o impuesto normal (positivo) segun el tipo de documento.
                if move.is_inbound():
                    # Facturas de cliente: amount_currency es negativo en el debe
                    # Invertimos para mostrar valores positivos
                    amount = -line.amount_currency
                    base = -line.tax_base_amount
                else:
                    # Facturas de proveedor
                    amount = line.amount_currency
                    base = line.tax_base_amount

                if tid not in tax_groups:
                    tax_groups[tid] = {
                        'tax_id': tid,
                        'tax_name': tax.name,
                        'base': 0.0,
                        'amount': 0.0,
                    }

                tax_groups[tid]['base'] += base
                tax_groups[tid]['amount'] += amount

            if not tax_groups:
                move.tax_detail_ids = TaxDetail
                move.has_tax_detail = False
                continue

            # Crear registros transient
            records = TaxDetail
            for data in tax_groups.values():
                rec = TaxDetail.create({
                    'move_id': move.id,
                    'tax_id': data['tax_id'],
                    'tax_name': data['tax_name'],
                    'base_amount': data['base'],
                    'tax_amount': data['amount'],
                    'currency_id': move.currency_id.id,
                })
                records |= rec

            move.tax_detail_ids = records
            move.has_tax_detail = bool(records)
