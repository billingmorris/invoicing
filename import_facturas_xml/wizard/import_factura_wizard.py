# -*- coding: utf-8 -*-
import base64
import logging
from lxml import etree
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Namespaces comunes en facturas XML latinoamericanas / UBL
# ─────────────────────────────────────────────────────────────
NS_MAP = {
    # UBL 2.1 (estándar DIAN Colombia, también Perú, Chile, etc.)
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    # CFDI México
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'cfdi3': 'http://www.sat.gob.mx/cfd/3',
    'tfd':  'http://www.sat.gob.mx/TimbreFiscalDigital',
}


def _xval(node, xpath, ns=None, default=''):
    """Extrae texto de un nodo con xpath tolerante a None."""
    if node is None:
        return default
    try:
        results = node.xpath(xpath, namespaces=ns or NS_MAP)
        if results:
            val = results[0]
            return val.strip() if isinstance(val, str) else (val.text or '').strip()
        return default
    except Exception:
        return default


def _xfloat(node, xpath, ns=None, default=0.0):
    val = _xval(node, xpath, ns, '')
    try:
        return float(val.replace(',', '')) if val else default
    except (ValueError, AttributeError):
        return default


# ─────────────────────────────────────────────────────────────
#  Líneas de la vista previa (embebidas en el wizard)
# ─────────────────────────────────────────────────────────────
class ImportFacturaWizardLine(models.TransientModel):
    _name = 'import.factura.wizard.line'
    _description = 'Línea de factura a importar'

    wizard_id      = fields.Many2one('import.factura.wizard', ondelete='cascade')

    # Datos del XML
    xml_description  = fields.Char(string='Descripción XML')
    xml_qty          = fields.Float(string='Cantidad XML',    digits=(16, 4))
    xml_unit_price   = fields.Float(string='P. Unitario XML', digits=(16, 4))
    xml_tax_percent  = fields.Float(string='% Impuesto XML',  digits=(16, 2))
    xml_subtotal     = fields.Float(string='Subtotal XML',    digits=(16, 2))
    xml_product_code = fields.Char(string='Código XML')

    # Resolución en Odoo
    product_id  = fields.Many2one('product.product', string='Producto Odoo')
    tax_ids     = fields.Many2many('account.tax',    string='Impuestos Odoo')
    used_default_product = fields.Boolean(string='Usa producto por defecto')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.used_default_product = False
            # Aplicar impuestos de compra del producto
            taxes = self.product_id.supplier_taxes_id.filtered(
                lambda t: t.company_id == self.env.company
            )
            self.tax_ids = taxes


# ─────────────────────────────────────────────────────────────
#  Wizard principal
# ─────────────────────────────────────────────────────────────
class ImportFacturaWizard(models.TransientModel):
    _name = 'import.factura.wizard'
    _description = 'Importar Factura de Proveedor desde XML'

    # ── Estado del wizard (multi-step) ─────────────────────
    state = fields.Selection([
        ('upload',   'Cargar XML'),
        ('review',   'Revisar y Completar'),
        ('done',     'Importado'),
    ], default='upload', string='Paso')

    # ── Archivos ────────────────────────────────────────────
    xml_file  = fields.Binary(string='Archivo XML', attachment=False)
    xml_fname = fields.Char(string='Nombre del archivo')

    # ── Datos extraídos (readonly, para mostrar) ────────────
    xml_number        = fields.Char(string='N° Factura',        readonly=True)
    xml_date          = fields.Date(string='Fecha Factura',     readonly=True)
    xml_date_due      = fields.Date(string='Fecha Vencimiento', readonly=True)
    xml_supplier_vat  = fields.Char(string='NIT/VAT Proveedor', readonly=True)
    xml_supplier_name = fields.Char(string='Nombre Proveedor',  readonly=True)
    xml_total         = fields.Float(string='Total XML',        readonly=True, digits=(16,2))
    xml_subtotal      = fields.Float(string='Subtotal XML',     readonly=True, digits=(16,2))
    xml_tax_total     = fields.Float(string='Impuestos XML',    readonly=True, digits=(16,2))
    xml_currency_code = fields.Char(string='Moneda XML',        readonly=True)
    xml_notes         = fields.Text(string='Notas XML',         readonly=True)

    # ── Resolución de proveedor ─────────────────────────────
    partner_found    = fields.Boolean(string='Proveedor encontrado', default=False)
    partner_id       = fields.Many2one(
        'res.partner', string='Proveedor',
        domain=[('is_company', '=', True)],
        help='Si el proveedor no se encontró automáticamente, selecciónelo aquí.',
    )
    partner_warning  = fields.Char(string='Aviso proveedor', readonly=True)

    # ── Líneas ──────────────────────────────────────────────
    line_ids = fields.One2many(
        'import.factura.wizard.line', 'wizard_id', string='Líneas')

    # ── Opciones ────────────────────────────────────────────
    journal_id = fields.Many2one(
        'account.journal', string='Diario',
        domain=[('type', '=', 'purchase')],
    )
    currency_id = fields.Many2one('res.currency', string='Moneda')

    # ── Resultado ───────────────────────────────────────────
    invoice_id   = fields.Many2one('account.move', string='Factura creada', readonly=True)
    warnings     = fields.Text(string='Advertencias', readonly=True)
    has_warnings = fields.Boolean(compute='_compute_has_warnings')

    @api.depends('warnings')
    def _compute_has_warnings(self):
        for r in self:
            r.has_warnings = bool(r.warnings)

    # ════════════════════════════════════════════════════════
    #   PASO 1 — Parsear el XML cargado
    # ════════════════════════════════════════════════════════
    def action_parse_xml(self):
        self.ensure_one()
        if not self.xml_file:
            raise UserError(_('Por favor cargue un archivo XML.'))

        try:
            xml_bytes = base64.b64decode(self.xml_file)
            root = etree.fromstring(xml_bytes)
        except Exception as e:
            raise UserError(_('El archivo no es un XML válido:\n%s') % str(e))

        warnings = []

        # ── Detectar formato ────────────────────────────────
        tag = root.tag.lower()
        if 'invoice' in tag or 'ubl' in tag or 'cbc' in str(root.nsmap):
            data = self._parse_ubl(root, warnings)
        elif 'comprobante' in tag or 'cfdi' in tag.replace('{', '').replace('}', ''):
            data = self._parse_cfdi(root, warnings)
        else:
            # Intento genérico
            data = self._parse_generic(root, warnings)

        if not data:
            raise UserError(_('No se pudo extraer información del XML. '
                               'Verifique que sea una factura válida.'))

        # ── Escribir campos extraídos ────────────────────────
        self.write({
            'xml_number':        data.get('number', ''),
            'xml_date':          data.get('date'),
            'xml_date_due':      data.get('date_due'),
            'xml_supplier_vat':  data.get('supplier_vat', ''),
            'xml_supplier_name': data.get('supplier_name', ''),
            'xml_total':         data.get('total', 0.0),
            'xml_subtotal':      data.get('subtotal', 0.0),
            'xml_tax_total':     data.get('tax_total', 0.0),
            'xml_currency_code': data.get('currency', ''),
            'xml_notes':         data.get('notes', ''),
        })

        # ── Resolver proveedor ──────────────────────────────
        partner, p_warning = self._resolve_partner(data)
        if partner:
            self.partner_id    = partner.id
            self.partner_found = True
        else:
            self.partner_found = False
            self.partner_id    = False
            if p_warning:
                warnings.append(p_warning)

        self.partner_warning = p_warning or ''

        # ── Resolver moneda ─────────────────────────────────
        currency = self._resolve_currency(data.get('currency', ''))
        self.currency_id = currency.id if currency else self.env.company.currency_id.id

        # ── Resolver diario ─────────────────────────────────
        journal = self._get_default_journal()
        self.journal_id = journal.id if journal else False

        # ── Construir líneas ────────────────────────────────
        self.line_ids = [(5, 0, 0)]
        line_vals = []
        for item in data.get('lines', []):
            product, used_default = self._resolve_product(item, warnings)
            taxes = self._resolve_taxes(item.get('tax_percent', 0.0), product, warnings)
            line_vals.append((0, 0, {
                'xml_description':  item.get('description', ''),
                'xml_qty':          item.get('qty', 1.0),
                'xml_unit_price':   item.get('unit_price', 0.0),
                'xml_tax_percent':  item.get('tax_percent', 0.0),
                'xml_subtotal':     item.get('subtotal', 0.0),
                'xml_product_code': item.get('code', ''),
                'product_id':       product.id if product else False,
                'tax_ids':          [(6, 0, taxes.ids)] if taxes else [],
                'used_default_product': used_default,
            }))
        self.line_ids = line_vals
        self.warnings = '\n'.join(warnings) if warnings else ''
        self.state = 'review'

        return self._reopen()

    # ════════════════════════════════════════════════════════
    #   PASO 2 — Crear la factura borrador
    # ════════════════════════════════════════════════════════
    def action_create_invoice(self):
        self.ensure_one()

        if not self.partner_id:
            raise ValidationError(
                _('Debe seleccionar el proveedor antes de crear la factura.')
            )
        if not self.line_ids:
            raise UserError(_('El XML no contiene líneas de factura.'))
        if not self.journal_id:
            raise UserError(_('Seleccione el diario de compras.'))

        # ── Cuenta por defecto (fallback) ───────────────────
        default_account = self._get_default_account()

        # ── Construir líneas de la factura ──────────────────
        invoice_lines = []
        for line in self.line_ids:
            product = line.product_id

            # Cuenta contable
            account = False
            if product:
                account = product.product_tmpl_id.get_product_accounts().get('expense')
            if not account:
                account = default_account
            if not account:
                raise UserError(
                    _('No se encontró cuenta contable para "%s". '
                      'Configure un producto por defecto con cuenta de gasto '
                      'en Ajustes › Importación XML.')
                    % (line.xml_description or 'línea')
                )

            invoice_lines.append((0, 0, {
                'name':        line.xml_description or (product.name if product else _('Servicio')),
                'product_id':  product.id if product else False,
                'quantity':    line.xml_qty or 1.0,
                'price_unit':  line.xml_unit_price,
                'tax_ids':     [(6, 0, line.tax_ids.ids)],
                'account_id':  account.id,
            }))

        # ── Crear el move ───────────────────────────────────
        invoice_vals = {
            'move_type':          'in_invoice',
            'partner_id':         self.partner_id.id,
            'invoice_date':       self.xml_date or fields.Date.today(),
            'invoice_date_due':   self.xml_date_due,
            'journal_id':         self.journal_id.id,
            'currency_id':        self.currency_id.id,
            'ref':                self.xml_number,
            'narration':          self.xml_notes,
            'invoice_line_ids':   invoice_lines,
        }

        invoice = self.env['account.move'].create(invoice_vals)
        self.invoice_id = invoice.id

        # ── Registrar en el log ─────────────────────────────
        xml_raw = ''
        if self.xml_file:
            try:
                xml_raw = base64.b64decode(self.xml_file).decode('utf-8', errors='replace')
            except Exception:
                pass

        self.env['import.factura.log'].create({
            'filename':         self.xml_fname or 'desconocido.xml',
            'state':            'warning' if self.warnings else 'ok',
            'xml_number':       self.xml_number,
            'xml_date':         self.xml_date,
            'xml_supplier_vat': self.xml_supplier_vat,
            'xml_supplier_name':self.xml_supplier_name,
            'xml_total':        self.xml_total,
            'xml_currency':     self.xml_currency_code,
            'partner_id':       self.partner_id.id,
            'invoice_id':       invoice.id,
            'message':          self.warnings or 'Importado correctamente.',
            'xml_raw':          xml_raw,
        })

        self.state = 'done'
        return self._reopen()

    def action_open_invoice(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id':    self.invoice_id.id,
            'view_mode': 'form',
            'target':    'current',
        }

    # ════════════════════════════════════════════════════════
    #   PARSERS por formato
    # ════════════════════════════════════════════════════════

    # ── UBL 2.1 (DIAN Colombia, Perú, Chile, UE) ───────────
    def _parse_ubl(self, root, warnings):
        ns = NS_MAP

        # Datos de cabecera
        number   = _xval(root, './/cbc:ID',                           ns)
        date_str = _xval(root, './/cbc:IssueDate',                    ns)
        due_str  = _xval(root, './/cbc:PaymentDueDate',               ns) or \
                   _xval(root, './/cac:PaymentTerms/cbc:PaymentDueDate', ns)
        currency = _xval(root, './/cbc:DocumentCurrencyCode',         ns)
        notes    = _xval(root, './/cbc:Note',                         ns)

        # Proveedor — AccountingSupplierParty
        supplier_node = root.find('.//cac:AccountingSupplierParty', ns) or \
                        root.find('.//cac:SellerSupplierParty', ns)
        sup_vat  = _xval(supplier_node, './/cbc:CompanyID',           ns) or \
                   _xval(supplier_node, './/cbc:ID',                  ns)
        sup_name = _xval(supplier_node, './/cbc:RegistrationName',    ns) or \
                   _xval(supplier_node, './/cbc:Name',                ns)

        # Totales
        total    = _xfloat(root, './/cac:LegalMonetaryTotal/cbc:PayableAmount',         ns)
        subtotal = _xfloat(root, './/cac:LegalMonetaryTotal/cbc:LineExtensionAmount',   ns) or \
                   _xfloat(root, './/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount',    ns)
        tax_total= _xfloat(root, './/cac:TaxTotal/cbc:TaxAmount',                      ns)

        # Líneas
        lines = []
        for item in root.findall('.//cac:InvoiceLine', ns) or \
                    root.findall('.//cac:CreditNoteLine', ns):
            code  = _xval(item, './/cac:Item/cac:SellersItemIdentification/cbc:ID', ns) or \
                    _xval(item, './/cac:Item/cac:BuyersItemIdentification/cbc:ID',  ns)
            desc  = _xval(item, './/cac:Item/cbc:Description', ns) or \
                    _xval(item, './/cac:Item/cbc:Name',         ns)
            qty        = _xfloat(item, './/cbc:InvoicedQuantity', ns) or 1.0
            unit_price = _xfloat(item, './/cac:Price/cbc:PriceAmount', ns)
            line_total = _xfloat(item, './/cbc:LineExtensionAmount',   ns)

            # Impuesto de la línea
            tax_pct = 0.0
            tax_node = item.find('.//cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory', ns)
            if tax_node is not None:
                tax_pct = _xfloat(tax_node, 'cbc:Percent', ns)

            # Recalcular precio unitario si viene cero
            if unit_price == 0.0 and qty and line_total:
                unit_price = line_total / qty

            lines.append({
                'code':        code,
                'description': desc,
                'qty':         qty,
                'unit_price':  unit_price,
                'tax_percent': tax_pct,
                'subtotal':    line_total,
            })

        return {
            'number':        number,
            'date':          self._parse_date(date_str),
            'date_due':      self._parse_date(due_str),
            'supplier_vat':  self._clean_vat(sup_vat),
            'supplier_name': sup_name,
            'total':         total,
            'subtotal':      subtotal,
            'tax_total':     tax_total,
            'currency':      currency,
            'notes':         notes,
            'lines':         lines,
        }

    # ── CFDI México ─────────────────────────────────────────
    def _parse_cfdi(self, root, warnings):
        # Detectar versión
        ns_cfdi = NS_MAP['cfdi'] if '{%s}' % NS_MAP['cfdi'] in root.tag else NS_MAP['cfdi3']
        ns = {'cfdi': ns_cfdi, 'tfd': NS_MAP['tfd']}

        attrib = root.attrib
        number   = attrib.get('Folio', '') or attrib.get('NoCertificado', '')
        date_str = attrib.get('Fecha', '') or attrib.get('fecha', '')
        currency = attrib.get('Moneda', 'MXN')
        total    = float(attrib.get('Total', 0))
        subtotal = float(attrib.get('SubTotal', 0))

        # Emisor (proveedor)
        emisor = root.find('{%s}Emisor' % ns_cfdi) or root.find('Emisor')
        sup_vat  = emisor.attrib.get('Rfc', '')   if emisor is not None else ''
        sup_name = emisor.attrib.get('Nombre', '') if emisor is not None else ''

        # Impuestos
        impuestos_node = root.find('{%s}Impuestos' % ns_cfdi) or root.find('Impuestos')
        tax_total = float(impuestos_node.attrib.get('TotalImpuestosTrasladados', 0)) \
                    if impuestos_node is not None else 0.0

        # Líneas (Conceptos)
        lines = []
        for concepto in root.iter('{%s}Concepto' % ns_cfdi):
            a = concepto.attrib
            qty        = float(a.get('Cantidad', 1))
            unit_price = float(a.get('ValorUnitario', 0))
            line_total = float(a.get('Importe', qty * unit_price))
            desc       = a.get('Descripcion', '')
            code       = a.get('ClaveProdServ', '') or a.get('NoIdentificacion', '')

            # Impuesto del concepto
            tax_pct = 0.0
            for traslado in concepto.iter('{%s}Traslado' % ns_cfdi):
                tax_pct = float(traslado.attrib.get('TasaOCuota', 0)) * 100

            lines.append({
                'code':        code,
                'description': desc,
                'qty':         qty,
                'unit_price':  unit_price,
                'tax_percent': tax_pct,
                'subtotal':    line_total,
            })

        return {
            'number':        number,
            'date':          self._parse_date(date_str[:10] if date_str else ''),
            'date_due':      None,
            'supplier_vat':  self._clean_vat(sup_vat),
            'supplier_name': sup_name,
            'total':         total,
            'subtotal':      subtotal,
            'tax_total':     tax_total,
            'currency':      currency,
            'notes':         '',
            'lines':         lines,
        }

    # ── Genérico / Fallback ─────────────────────────────────
    def _parse_generic(self, root, warnings):
        """Parser tolerante para XMLs de estructura libre."""
        warnings.append('⚠ Formato XML no reconocido. Se realizó extracción genérica.')

        def find_text(*tags):
            for tag in tags:
                # Búsqueda insensible a namespace
                for el in root.iter():
                    local = el.tag.split('}')[-1].lower()
                    if local == tag.lower() and el.text:
                        return el.text.strip()
            return ''

        def find_float(*tags):
            val = find_text(*tags)
            try:
                return float(val.replace(',', '')) if val else 0.0
            except ValueError:
                return 0.0

        # Extraer datos básicos con nombres comunes
        number   = find_text('invoiceid', 'invoice_id', 'numero', 'number',
                              'folio', 'id', 'documentnumber')
        date_str = find_text('issuedate', 'fecha', 'date', 'invoicedate')
        sup_vat  = find_text('companyid', 'nit', 'vat', 'rfc', 'taxid',
                              'supplierid', 'rut')
        sup_name = find_text('registrationname', 'nombre', 'name',
                              'suppliername', 'razonsocial')
        total    = find_float('payableamount', 'total', 'grandtotal',
                              'invoicetotal', 'totalimporte')
        subtotal = find_float('lineextensionamount', 'subtotal', 'taxexclusiveamount')
        currency = find_text('documentcurrencycode', 'moneda', 'currency', 'currencycode')

        # Líneas — buscar nodos repetidos con precio
        lines = []
        line_tags = ['invoiceline', 'concepto', 'item', 'line',
                     'detalle', 'lineitem', 'invoiceitem']
        line_nodes = []
        for tag in line_tags:
            for el in root.iter():
                if el.tag.split('}')[-1].lower() == tag:
                    line_nodes.append(el)
            if line_nodes:
                break

        for node in line_nodes:
            def lval(*tags):
                for t in tags:
                    for child in node.iter():
                        if child.tag.split('}')[-1].lower() == t.lower() and child.text:
                            return child.text.strip()
                return ''

            def lfloat(*tags):
                v = lval(*tags)
                try:
                    return float(v.replace(',', '')) if v else 0.0
                except ValueError:
                    return 0.0

            qty   = lfloat('quantity', 'cantidad', 'invoicedquantity', 'qty')
            price = lfloat('priceamount', 'valorunitario', 'unitprice', 'price', 'preciounitario')
            total_l = lfloat('lineextensionamount', 'importe', 'linetotal', 'subtotal')
            desc  = lval('description', 'descripcion', 'name', 'nombre', 'item')
            code  = lval('id', 'code', 'codigo', 'productcode', 'claveprodserv')

            if qty == 0:
                qty = 1.0
            if price == 0.0 and total_l and qty:
                price = total_l / qty

            lines.append({
                'code':        code,
                'description': desc or 'Ítem importado',
                'qty':         qty,
                'unit_price':  price,
                'tax_percent': 0.0,
                'subtotal':    total_l,
            })

        if not lines:
            warnings.append('⚠ No se encontraron líneas de detalle en el XML.')

        return {
            'number':        number,
            'date':          self._parse_date(date_str),
            'date_due':      None,
            'supplier_vat':  self._clean_vat(sup_vat),
            'supplier_name': sup_name,
            'total':         total,
            'subtotal':      subtotal,
            'tax_total':     total - subtotal if total > subtotal else 0.0,
            'currency':      currency,
            'notes':         '',
            'lines':         lines,
        }

    # ════════════════════════════════════════════════════════
    #   RESOLVERS
    # ════════════════════════════════════════════════════════

    def _resolve_partner(self, data):
        """Busca el partner por VAT, nombre o referencia. Devuelve (partner|False, warning)."""
        Partner = self.env['res.partner']
        vat  = data.get('supplier_vat', '').strip()
        name = data.get('supplier_name', '').strip()

        if not vat and not name:
            return False, _('El XML no contiene datos del proveedor.')

        # 1. Búsqueda exacta por VAT (NIT/RUC/RFC)
        if vat:
            # Limpiar el VAT para comparación
            vat_clean = self._clean_vat(vat)
            partner = Partner.search([
                ('vat', 'ilike', vat_clean),
                ('is_company', '=', True),
            ], limit=1)
            if not partner:
                # Intentar sin guiones/puntos
                digits_only = ''.join(filter(str.isdigit, vat_clean))
                if digits_only:
                    for p in Partner.search([('is_company', '=', True), ('vat', '!=', False)], limit=500):
                        if ''.join(filter(str.isdigit, p.vat or '')) == digits_only:
                            partner = p
                            break
            if partner:
                return partner, ''

        # 2. Búsqueda por nombre exacto
        if name:
            partner = Partner.search([
                ('name', '=ilike', name),
                ('is_company', '=', True),
            ], limit=1)
            if partner:
                return partner, _('Proveedor encontrado por nombre (sin VAT coincidente).')

            # 3. Búsqueda por nombre aproximado (contiene)
            words = [w for w in name.split() if len(w) > 3]
            if words:
                domain = [('is_company', '=', True)]
                for w in words[:3]:
                    domain.append(('name', 'ilike', w))
                partner = Partner.search(domain, limit=1)
                if partner:
                    return partner, _(
                        'Proveedor asignado por similitud de nombre. '
                        'Verifique que sea correcto.'
                    )

        # 4. No encontrado
        msg = _('Proveedor no encontrado')
        if vat:
            msg += _(' (VAT: %s)') % vat
        if name:
            msg += _(' (Nombre: %s)') % name
        msg += _('. Selecciónelo manualmente.')
        return False, msg

    def _resolve_product(self, item, warnings):
        """
        Busca el producto por código o nombre.
        Si no lo encuentra, usa el producto por defecto.
        Devuelve (product|False, used_default:bool).
        """
        Product = self.env['product.product']
        code = (item.get('code') or '').strip()
        desc = (item.get('description') or '').strip()

        product = False

        # 1. Por código exacto (referencia interna)
        if code:
            product = Product.search([
                ('default_code', '=', code)
            ], limit=1)

        # 2. Por código en barras
        if not product and code:
            product = Product.search([
                ('barcode', '=', code)
            ], limit=1)

        # 3. Por nombre exacto
        if not product and desc:
            product = Product.search([
                ('name', '=ilike', desc)
            ], limit=1)

        # 4. Nombre aproximado (primeras palabras significativas)
        if not product and desc:
            words = [w for w in desc.split() if len(w) > 3]
            if words:
                product = Product.search([
                    ('name', 'ilike', words[0])
                ], limit=1)

        if product:
            return product, False

        # 5. Usar producto por defecto
        default_product = self._get_default_product()
        if default_product:
            warnings.append(
                _('Producto "%s" (cód: %s) no encontrado → se usará el producto por defecto "%s".')
                % (desc or '?', code or '?', default_product.name)
            )
            return default_product, True

        # 6. Sin producto ni defecto
        warnings.append(
            _('Producto "%s" no encontrado y no hay producto por defecto configurado. '
              'La línea se creará sin producto.')
            % (desc or '?')
        )
        return False, False

    def _resolve_taxes(self, tax_percent, product, warnings):
        """Resuelve el impuesto de la línea."""
        Tax = self.env['account.tax']
        company = self.env.company

        # 1. Del producto
        if product:
            prod_taxes = product.supplier_taxes_id.filtered(
                lambda t: t.company_id == company
            )
            if prod_taxes:
                return prod_taxes

        # 2. Por porcentaje
        if tax_percent > 0:
            tax = Tax.search([
                ('type_tax_use', '=', 'purchase'),
                ('amount', '=', tax_percent),
                ('amount_type', '=', 'percent'),
                ('company_id', '=', company.id),
            ], limit=1)
            if tax:
                return tax

        # 3. Impuesto por defecto configurado
        default_tax = self._get_default_tax()
        if default_tax and tax_percent > 0:
            warnings.append(
                _('Impuesto %.1f%% no encontrado en Odoo → se usa impuesto por defecto "%s".')
                % (tax_percent, default_tax.name)
            )
            return default_tax

        return Tax.browse()

    # ════════════════════════════════════════════════════════
    #   CONFIGURACIÓN (parámetros del sistema)
    # ════════════════════════════════════════════════════════

    def _get_default_product(self):
        pid = int(self.env['ir.config_parameter'].sudo().get_param(
            'import_facturas_xml.default_product_id', 0))
        return self.env['product.product'].browse(pid).exists() if pid else \
               self.env['product.product'].browse()

    def _get_default_account(self):
        aid = int(self.env['ir.config_parameter'].sudo().get_param(
            'import_facturas_xml.default_account_id', 0))
        return self.env['account.account'].browse(aid).exists() if aid else \
               self.env['account.account'].browse()

    def _get_default_tax(self):
        tid = int(self.env['ir.config_parameter'].sudo().get_param(
            'import_facturas_xml.default_tax_id', 0))
        return self.env['account.tax'].browse(tid).exists() if tid else \
               self.env['account.tax'].browse()

    def _get_default_journal(self):
        jid = int(self.env['ir.config_parameter'].sudo().get_param(
            'import_facturas_xml.default_journal_id', 0))
        if jid:
            j = self.env['account.journal'].browse(jid).exists()
            if j:
                return j
        return self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

    def _get_default_currency(self):
        return self.env.company.currency_id

    # ════════════════════════════════════════════════════════
    #   HELPERS
    # ════════════════════════════════════════════════════════

    def _parse_date(self, date_str):
        if not date_str:
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y%m%d',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
            try:
                return datetime.strptime(date_str[:len(fmt.replace('%Y','0000').replace('%m','00').replace('%d','00').replace('%H','00').replace('%M','00').replace('%S','00').replace('%f','000000'))], fmt).date()
            except (ValueError, TypeError):
                continue
        # Intento directo con los 10 primeros caracteres
        try:
            return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        except Exception:
            return None

    def _clean_vat(self, vat):
        """Normaliza el VAT eliminando caracteres no alfanuméricos."""
        if not vat:
            return ''
        return vat.strip().upper()

    def _resolve_currency(self, code):
        if not code:
            return self.env.company.currency_id
        cur = self.env['res.currency'].search([
            ('name', '=', code.upper())
        ], limit=1)
        return cur or self.env.company.currency_id

    def _reopen(self):
        """Reabre el wizard en el mismo registro."""
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'import.factura.wizard',
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
            'context':   self.env.context,
        }
