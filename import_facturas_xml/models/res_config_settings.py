# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Producto por defecto cuando no se encuentra en el XML
    xml_import_default_product_id = fields.Many2one(
        'product.product',
        string='Producto por defecto (importación XML)',
        config_parameter='import_facturas_xml.default_product_id',
        help='Se usa cuando un producto del XML no se encuentra en Odoo.',
    )

    # Cuenta de gasto por defecto (fallback)
    xml_import_default_account_id = fields.Many2one(
        'account.account',
        string='Cuenta contable por defecto',
        config_parameter='import_facturas_xml.default_account_id',
        domain=[('account_type', 'in', ['expense', 'expense_direct_cost'])],
        help='Cuenta usada si el producto por defecto no tiene cuenta configurada.',
    )

    # Impuesto por defecto de compras
    xml_import_default_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto de compra por defecto',
        config_parameter='import_facturas_xml.default_tax_id',
        domain=[('type_tax_use', '=', 'purchase')],
        help='Impuesto aplicado cuando no se puede mapear el impuesto del XML.',
    )

    # Diario de compras
    xml_import_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de compras para importación',
        config_parameter='import_facturas_xml.default_journal_id',
        domain=[('type', '=', 'purchase')],
    )
