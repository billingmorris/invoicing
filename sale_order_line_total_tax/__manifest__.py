# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Line Total with Tax',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Muestra el total por línea con impuestos incluidos en el PDF de la Orden de Venta',
    'description': """
        Agrega una columna "Total con impuestos" al reporte PDF estándar de la Orden de Venta.
        El cálculo utiliza el motor fiscal estándar de Odoo (compute_all) para garantizar
        compatibilidad con IVA incluido, excluido, múltiples impuestos y posiciones fiscales.
    """,
    'author': 'Custom',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
        'views/sale_order_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
