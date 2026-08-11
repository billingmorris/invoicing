# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountInvoiceTaxDetail(models.TransientModel):
    """
    Modelo transient para almacenar el detalle de impuestos calculado
    por linea de factura, agrupado por impuesto.

    Se usa TransientModel para evitar acumulacion de registros en base de datos.
    Los registros se calculan en tiempo de ejecucion y no se persisten.
    """
    _name = 'account.invoice.tax.detail'
    _description = 'Detalle de impuestos de factura'

    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        ondelete='cascade',
    )

    tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto',
    )

    tax_name = fields.Char(
        string='Impuesto',
    )

    base_amount = fields.Monetary(
        string='Base',
        currency_field='currency_id',
    )

    tax_amount = fields.Monetary(
        string='Valor del impuesto',
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
    )
