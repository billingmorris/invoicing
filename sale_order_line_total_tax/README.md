# Sale Order Line Total with Tax

Módulo para **Odoo 16 Community** que agrega la columna **"Total con impuestos"**
al reporte PDF estándar de las Órdenes de Venta.

## Funcionalidad

En el PDF de la Orden de Venta se agrega una nueva columna que muestra, por cada
línea de producto, el total de esa línea **con todos los impuestos aplicados incluidos**.

| Producto   | Cantidad | Precio unit. | Impuestos | Importe | Total con impuestos |
|------------|:--------:|-------------:|-----------|--------:|--------------------:|
| Producto A |    2     |     $10.000  | IVA 19%   | $20.000 |            $23.800  |
| Producto B |    3     |      $5.000  | IVA 19%   | $15.000 |            $17.850  |

## Cálculo

Utiliza el motor fiscal estándar de Odoo (`tax_id.compute_all()`) para garantizar
compatibilidad con:

- IVA incluido en precio
- IVA excluido del precio
- Múltiples impuestos por línea
- Posiciones fiscales
- Descuentos
- Líneas sin impuestos
- Redondeo de moneda configurado en Odoo

## Instalación

1. Copiar la carpeta `sale_order_line_total_tax/` a tu directorio de addons custom.
2. Activar modo desarrollador en Odoo.
3. Ir a **Aplicaciones → Actualizar lista de aplicaciones**.
4. Buscar **"Sale Order Line Total Tax"** e instalar.

## Compatibilidad

- Odoo **16.0 Community Edition**
- No requiere módulos Enterprise
- Dependencia: `sale`

## Estructura

```
sale_order_line_total_tax/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_order_line.py   # Campo total_with_tax (Monetary, computed)
├── views/
│   └── sale_order_report.xml  # Herencia del reporte QWeb
└── README.md
```

## Casos de prueba

| Caso | Cantidad | Precio unit. | Descuento | Impuesto | Resultado esperado |
|------|:--------:|-------------:|:---------:|----------|-------------------:|
| Sin impuesto | 2 | $10.000 | 0% | — | $20.000 |
| IVA 19% excluido | 2 | $10.000 | 0% | 19% | $23.800 |
| IVA 19% incluido | 2 | $11.900 | 0% | 19% inc. | $23.800 |
| Con descuento | 2 | $10.000 | 10% | 19% | $21.420 |
