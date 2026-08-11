# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    total_with_tax = fields.Monetary(
        string='Total con impuestos',
        compute='_compute_total_with_tax',
        currency_field='currency_id',
        store=False,
    )

    @api.depends(
        'price_unit',
        'product_uom_qty',
        'discount',
        'tax_id',
        'order_id.currency_id',
        'order_id.partner_id',
        'order_id.fiscal_position_id',
        'order_id.partner_shipping_id',
    )
    def _compute_total_with_tax(self):
        for line in self:
            if not line.tax_id:
                # Sin impuestos: total = subtotal de la linea
                line.total_with_tax = line.price_subtotal
                continue

            # Precio unitario con descuento aplicado
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)

            # Motor fiscal estandar de Odoo
            taxes = line.tax_id.compute_all(
                price,
                currency=line.order_id.currency_id,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id,
            )

            # total_included contempla todos los impuestos correctamente
            line.total_with_tax = taxes['total_included']
