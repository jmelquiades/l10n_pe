from odoo import _, api, fields, models
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class PleBase(models.Model):
    _name = 'ple.base'

    name = fields.Char('Name')
    date_start = fields.Date(
        string='Fecha Inicio',
        required=True
    )
    state = fields.Selection(selection=[
        ('draft', 'Borrador'),
        ('load', 'Generado'),
        ('closed', 'Declarado')
    ], string='Estado', default='draft', required=True)
    date_end = fields.Date(
        string='Fecha Fin',
        required=True
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.user.company_id
    )
    date_ple = fields.Date('Fecha de creación de reporte PLE')
    ple_base_line_ids = fields.One2many('ple.base.line', 'ple_base_id', string='Ple Base Line')

    def _get_name(self, vals):
        date_start = vals.get('date_start', self.date_start)
        date_end = vals.get('date_end', self.date_end)
        company_id = vals.get('company_id', self.company_id.id)
        company = self.env['res.company'].browse(company_id).name
        return str(date_start) + '-' + str(date_end) + ' ' + company

    def default_get(self, fields_list):
        res = super(PleBase, self).default_get(fields_list)
        date = fields.date.today()
        date_start = date.replace(day=1) - relativedelta(months=1)
        date_end = date.replace(day=1) - timedelta(days=1)
        res.update({
            'date_start': date_start,
            'date_end': date_end,
        })
        return res

    def write(self, vals):
        vals['name'] = self._get_name(vals)
        return super(PleBase, self).write(vals)

    @api.onchange('date_start', 'date_end', 'company_id')
    def _onchange_date_company(self):
        self.line_ids.unlink()

    @api.model
    def create(self, vals):
        vals['name'] = self._get_name(vals)
        return super(PleBase, self).create(vals)

    def _get_number_origin(self, invoice):
        number_origin = ''
        try:
            if invoice.type in ['out_invoice', 'out_refund']:
                if invoice.ple_state in ['0', '1', '2', '8', '9']:
                    number_origin = invoice.name.replace('/', '').replace('-', '')

            elif invoice.type in ['in_invoice', 'in_refund']:
                if invoice.ple_state in ['0', '1', '6', '7', '9']:
                    number_origin = invoice.name.replace('/', '').replace('-', '')

        except Exception:
            number_origin = ''
        return number_origin

    def _get_data_invoice(self, invoice):  # *
        ple_state = invoice.ple_state
        partner = invoice.partner_id
        if invoice.state != 'cancel':
            return invoice.invoice_date_due, ple_state, partner.l10n_latam_identification_type_id.sequence, partner.vat, partner.name  # ! partner.l10n_latam_identification_type_id.sequence >> partner.l10n_latam_identification_type_id.code
        else:
            return False, ple_state, partner.l10n_latam_identification_type_id.sequence, partner.vat, partner.name

    def _get_journal_correlative(self, company, invoice=False, new_name=''):
        if company.type_contributor == 'CUO':

            if not new_name:
                new_name = 'M000000001'
        elif company.type_contributor == 'RER':
            new_name = 'M-RER'
        return new_name

    def _get_data_origin(self, invoice):  # * corregido
        # ! return invoice.origin_invoice_date, invoice.origin_inv_document_type_id.code, invoice.origin_serie, invoice.origin_correlative, invoice.origin_number.code_aduana
        return invoice.reversed_entry_id.invoice_date, invoice.reversed_entry_id.l10n_latam_document_type_id.sequence, invoice.reversed_entry_id.sequence_prefix, invoice.reversed_entry_id.sequence_number, invoice.reversed_entry_id.code_customs_id  # l10n_pe_dte_rectification_ref_type

    def unlink(self):
        if self.state == 'closed':
            raise Warning('Regrese a estado borrador para revertir y permitir eliminar.')
        return super(PleBase, self).unlink()

    def _refund_amount(self, values):
        for k in values.keys():
            values[k] *= -1
        return values

    def action_close(self):
        self.ensure_one()
        self.write({
            'state': 'closed'
        })
        for obj_line in self.line_ids:
            if obj_line.invoice_id:
                obj_line.invoice_id.its_declared = True
        return True

    def action_rollback(self):
        for obj_line in self.line_ids:
            if obj_line.invoice_id:
                obj_line.invoice_id.its_declared = False
        self.state = 'draft'
        return True