# Copyright 2022 Sodexis
# License OPL-1 (See LICENSE file for full copyright and licensing details).

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    needs_approval = fields.Boolean(copy=False)
    approved = fields.Boolean(copy=False)
    waiting_approval_visibility = fields.Boolean(compute="_compute_waiting_approval_visibility",store=True)
    request_approval_visibility = fields.Boolean(compute="_compute_waiting_approval_visibility",store=True)

    def vendor_bill_approval_request_message(self):
        bills = self.env['account.move'].search([('move_type','=','in_invoice'),('needs_approval','=',True),('approved','=',False)])
        channel_id = int(self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.bill_approval_channel_id'))
        if bills and channel_id:
            message = ''
            for bill in bills:
                link = bill.get_share_url()
                message += F'<br/><b><a href="{link}">{bill.name}</a></b>'
            if message:
                body = F"Approval needed to proceed with payments for the following Bills {message}"
                self.env['mail.message'].create({
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'model': 'mail.channel',
                'channel_ids': [(6,0, [channel_id])],
                'body': body,
                })

    def action_register_payment(self):
        active_ids = self.env.context.get('active_ids')
        vendor_bills = self.env['account.move'].search([('id', 'in', active_ids), ('approved', '=', False), ('move_type', '=', 'in_invoice')])
        if vendor_bills:
            raise UserError(_('All Vendor bills must be approved to proceed with the payment.\n The following vendor bills are not approved %s' % ', '.join(vendor_bills.mapped('name'))))
        return super().action_register_payment()

    def _post(self,soft=True):
        res = super(AccountMove ,self)._post(soft=soft)
        for record in self:
            automated_approval_creation = record.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.automated_approval_request')
            bill_approval_indicator = record.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.threshold_for_bill_approval_indicator')
            threshold_amount = float(record.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.threshold_for_bill_approval'))
            if automated_approval_creation:
                record.request_approval()
            elif bill_approval_indicator and record.amount_total < threshold_amount:
                    record.write({
                                 'needs_approval': True,
                                 'approved': True
                                 })
        return res
    
    def button_draft(self):
        res = super(AccountMove ,self).button_draft()
        automated_approval_creation = self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.automated_approval_request')
        bill_approval_indicator = self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.threshold_for_bill_approval_indicator')
        if bill_approval_indicator or automated_approval_creation:
            self.write({
                        'needs_approval': False,
                        'approved': False
                        })
        return res

    def get_share_url(self):
        """
        this method is only used in email template to get share url.
        """
        return self._get_share_url(redirect=True, signup_partner=True)


    def request_approval(self):
        threshold_amount = float(self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.threshold_for_bill_approval'))
        bill_approval_indicator = self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.threshold_for_bill_approval_indicator')
        automated_approval_creation = self.env['ir.config_parameter'].sudo().get_param('vendor_bill_payment_approval.automated_approval_request')
        if self.move_type == 'in_invoice' and not self.needs_approval:
            if (bill_approval_indicator and self.amount_total >= threshold_amount) or (not bill_approval_indicator and automated_approval_creation) or (not bill_approval_indicator and not automated_approval_creation):
                self.write({'needs_approval': True})
                group_id = self.env['ir.model.data'].xmlid_to_res_id('vendor_bill_payment_approval.group_payment_manager', raise_if_not_found=False)
                payment_managers = self.env['res.groups'].browse(group_id).users.partner_id
                template = self.env.ref("vendor_bill_payment_approval.email_template_edi_vendor_bill_approval", raise_if_not_found=False)
                if template and payment_managers:
                    template.send_mail(self.id,force_send=True, email_values={'recipient_ids': payment_managers})
            elif bill_approval_indicator and self.amount_total <= threshold_amount:
                self.write({
                            'needs_approval': True,
                            'approved': True
                            })

    def revoke_approval_request(self):
        if self.move_type == 'in_invoice' and self.needs_approval and not self.approved:
            self.write({'needs_approval': False})

    def approve(self):
        if self.move_type == 'in_invoice' and not self.approved:
            self.write({'approved': True})
            body = "<b>Bill# {0}</b> has been approved for payment by {1}".format(self.name, self.env.user.name)
            self.message_post(body=body)
            _logger.info(body)

    @api.depends('state', 'needs_approval', 'approved')
    def _compute_waiting_approval_visibility(self):
        for invoice in self:
            invoice.waiting_approval_visibility = False
            invoice.request_approval_visibility = False
            if invoice.move_type == 'in_invoice' and invoice.state == 'posted' and invoice.needs_approval == True and invoice.approved == False:
                invoice.waiting_approval_visibility = True
            if invoice.move_type == 'in_invoice' and invoice.state == 'posted' and invoice.needs_approval == False and invoice.payment_state == 'not_paid':
                invoice.request_approval_visibility = True

    def action_approve(self):
        active_ids = self.env.context.get("active_ids", [])
        bills = self.env["account.move"].browse(active_ids)

        # Only payment managers can approve bills
        if not self.env.user.has_group("vendor_bill_payment_approval.group_payment_manager"):
            raise UserError(_("Only Payment Managers can approve bills."))

        # Only Vendor bills can be approved
        if bills.filtered(lambda b: b.move_type != 'in_invoice'):
            raise UserError(_("Only Vendor Bills can be approved."))

        # Only approve the bills that needs approval
        approval_not_requested_bills = bills.filtered(lambda b: b.move_type == "in_invoice" and b.needs_approval == False)
        if approval_not_requested_bills:
            message = """The following bills are not requested for approval.
            %s\nDon't select the bills that are not requested for approval""" % ', '.join([b.name if b.state != 'draft' else 'ID# %s' % b.id for b in approval_not_requested_bills])
            raise UserError(_(message))

        # only approve the bills are not approved
        for bill in bills.filtered(lambda b: not b.approved):
            bill.approve()

    def action_request_approval(self):
        active_ids = self.env.context.get("active_ids", [])
        bills = self.env["account.move"].browse(active_ids)

        # Only users with the group can request for payment approval
        # are allowed to request payment approval bills
        if not self.env.user.has_group("vendor_bill_payment_approval.group_payment_requester"):
            raise UserError(_("Only users with the group \"Can request for payment approval\" are allowed to request payment approval."))

        # Only Vendor bills can be requested for approval
        if bills.filtered(lambda b: b.move_type != 'in_invoice'):
            raise UserError(_("Only Vendor Bills can be requested for approval."))

        # Only request for approval for the bills that are in posted state
        can_not_be_requested = bills.filtered(lambda b: b.move_type == "in_invoice" and b.state != 'posted')
        if can_not_be_requested:
            message = """The following bills can't be requested for approval.
            %s\nOnly posted bills can be requested for approval""" % ', '.join([b.name if b.state != 'draft' else 'ID# %s' % b.id for b in can_not_be_requested])
            raise UserError(_(message))

        # only approve the bills are not requested already
        for bill in bills.filtered(lambda b: not b.needs_approval):
            bill.request_approval()
