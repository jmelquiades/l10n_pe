from odoo import _, api, fields, models
import base64


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'
    _description = 'Account Batch Payment'

    arrival_journal_id = fields.Many2one('account.journal', string='Banco destino')
    txt_binary = fields.Binary('Txt Binary')
    txt_name = fields.Char('Txt Name')
    correlative_detraction_batch_payment = fields.Char('Correlativo de pago de detracción por lotes', default=lambda self: 'Nuevo')

    def generate_txt(self):
        values_content = self.get_data()
        self.txt_binary = base64.b64encode(
            values_content and values_content.encode() or '\n'.encode()
        )
        date = fields.Date.today()
        # correlative = '0001'
        year = str(date.year)[:2]
        correlative = self.correlative_detraction_batch_payment
        self.txt_name = f'D{self.env.user.company_id.vat}{year}{correlative}.txt'

    def get_data(self):
        company = self.env.user.company_id
        raw = f'*{company.vat}{company.name}'
        spaces = len(raw)
        raw += ' ' * (48 - spaces)
        date = fields.Date.today()
        if self.correlative_detraction_batch_payment == 'Nuevo':
            self.correlative_detraction_batch_payment = self.env['ir.sequence'].next_by_code('seq.detraction.batch.payment')
        correlative = self.correlative_detraction_batch_payment
        amount_total = sum(self.payment_ids.mapped(lambda p: int(p.move_id.l10n_pe_dte_detraction_amount)))
        amount_total = str(amount_total).zfill(15)
        year = str(date.year)[:2]
        raw += f'{year}{correlative}{amount_total}00\r\n'

        for payment in self.payment_ids:
            move = payment.reconciled_bill_ids[0] if payment.reconciled_bill_ids else False
            if move:
                # move = payment.move_id
                partner = move.partner_id
                date = move.date
                line = f'{partner.l10n_latam_identification_type_id.l10n_pe_vat_code}{partner.vat}'
                spaces = len(line)
                service = move.l10n_pe_dte_detraction_code
                acc_number = payment.partner_bank_id.acc_number.replace('-', '')
                op_code = '01'
                amount = str(int(move.l10n_pe_dte_detraction_amount))
                prefix = move.sequence_prefix.split()[-1].replace('-', '')
                line += ' ' * (48 - spaces) + f'000000000{service}{acc_number}0000000000{amount}00{op_code}{date.year}{date.month}{move.l10n_latam_document_type_id.code}{prefix}{move.sequence_number}\r\n'
                raw += line
        return raw