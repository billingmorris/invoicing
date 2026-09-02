# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ImportFacturaLog(models.Model):
    _name = 'import.factura.log'
    _description = 'Historial de Importación de Facturas XML'
    _order = 'create_date desc'
    _rec_name = 'filename'

    filename = fields.Char(string='Archivo', readonly=True)
    state = fields.Selection([
        ('ok',      'Importado'),
        ('warning', 'Con advertencias'),
        ('error',   'Error'),
    ], string='Estado', readonly=True, default='ok')

    # Datos extraídos del XML
    xml_number       = fields.Char(string='N° Factura XML',   readonly=True)
    xml_date         = fields.Date(string='Fecha XML',         readonly=True)
    xml_supplier_vat = fields.Char(string='NIT/VAT Proveedor', readonly=True)
    xml_supplier_name= fields.Char(string='Nombre Proveedor',  readonly=True)
    xml_total        = fields.Float(string='Total XML',        readonly=True, digits=(16,2))
    xml_currency     = fields.Char(string='Moneda XML',        readonly=True)

    # Relaciones en Odoo
    partner_id  = fields.Many2one('res.partner',       string='Proveedor Odoo',  readonly=True)
    invoice_id  = fields.Many2one('account.move',      string='Factura creada',  readonly=True)
    user_id     = fields.Many2one('res.users',         string='Importado por',   readonly=True,
                                  default=lambda self: self.env.user)

    # Mensajes
    message = fields.Text(string='Mensajes / Advertencias', readonly=True)

    # Contenido XML original (para auditoría)
    xml_raw = fields.Text(string='XML Original', readonly=True)

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
