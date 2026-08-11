# -*- coding: utf-8 -*-
{
    'name': 'Account Invoice Tax Detail',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Muestra cuadro detallado de impuestos en la factura (formulario y PDF)',
    'description': """
        Agrega un bloque "Detalle de impuestos" en la vista formulario y en el PDF
        de las facturas de Odoo 16 Community. Agrupa los impuestos por tipo y muestra
        base gravable y valor del impuesto. Compatible con IVA, retenciones y
        configuraciones fiscales de Colombia.
    """,
    'author': 'Custom',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_invoice_tax_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
