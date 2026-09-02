# -*- coding: utf-8 -*-
{
    'name': 'Importar Facturas XML de Proveedor',
    'version': '16.0.1.0.0',
    'summary': 'Importa facturas de proveedor desde archivos XML y crea borradores automáticamente',
    'description': """
        Módulo para importar facturas de proveedor en formato XML estándar (UBL/CFDI/genérico).
        
        Características:
        - Importación masiva o individual de archivos XML
        - Detección automática de proveedor por NIT/VAT/nombre
        - Si el proveedor no existe: selector de partner existente
        - Si el producto no existe: asigna producto por defecto configurable
        - Mapeo de impuestos automático
        - Historial de importaciones con estado y errores
        - No crea duplicados de partners ni productos
        - Vista previa antes de crear la factura
    """,
    'author': 'Custom',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'depends': ['account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/import_factura_wizard_views.xml',
        'views/import_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'import_facturas_xml/static/src/css/import_style.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
