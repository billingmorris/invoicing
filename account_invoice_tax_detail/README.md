# Account Invoice Tax Detail

Modulo para **Odoo 16 Community** que muestra un cuadro detallado de impuestos
en la vista formulario y en el PDF de las facturas.

## Funcionalidad

Agrega un bloque **"Detalle de impuestos"** que muestra:

| Impuesto        |     Base | Valor del impuesto |
|-----------------|:--------:|-------------------:|
| IVA 19%         | $100.000 |            $19.000 |
| IVA 5%          |  $50.000 |             $2.500 |
| Retencion 2.5%  | $150.000 |            -$3.750 |

## Documentos soportados

- Facturas de cliente (out_invoice)
- Notas credito de cliente (out_refund)
- Facturas de proveedor (in_invoice)
- Notas debito de proveedor (in_refund)

## Caracteristicas

- Usa las lineas contables de tipo 'tax' generadas por Odoo (account.move.line)
- No realiza calculos fiscales paralelos
- Agrupa por impuesto (consolida multiples lineas del mismo impuesto)
- Soporta IVA incluido/excluido, retenciones, multiples impuestos
- Compatible con configuracion fiscal Colombia (IVA, ReteIVA, ReteICA, INC)
- Formato monetario segun la moneda de la factura
- Se oculta si la factura no tiene impuestos

## Instalacion

1. Copiar carpeta a /odoo16/custom/addons/
2. Activar modo desarrollador
3. Aplicaciones -> Actualizar lista
4. Instalar "Account Invoice Tax Detail"

## Dependencia

- account
