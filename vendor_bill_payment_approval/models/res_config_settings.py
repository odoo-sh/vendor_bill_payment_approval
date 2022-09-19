# -*- coding: utf-8 -*-
# Copyright 2022 Sodexis
# License OPL-1 (See LICENSE file for full copyright and licensing details).

from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit='res.config.settings'

    threshold_for_bill_approval = fields.Float(config_parameter='vendor_bill_payment_approval.threshold_for_bill_approval')
    automated_approval_request = fields.Boolean(config_parameter='vendor_bill_payment_approval.automated_approval_request')
    threshold_for_bill_approval_indicator = fields.Boolean(string="Threshold for Bill Approval",config_parameter='vendor_bill_payment_approval.threshold_for_bill_approval_indicator')
    bill_approval_channel_id = fields.Many2one('mail.channel',string="Channel",config_parameter='vendor_bill_payment_approval.bill_approval_channel_id')
    turnoff_approval_request_email = fields.Boolean(config_parameter='vendor_bill_payment_approval.turnoff_approval_request_email')
