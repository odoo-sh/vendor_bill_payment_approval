# -*- coding: utf-8 -*-
# Copyright 2022 Sodexis
# License OPL-1 (See LICENSE file for full copyright and licensing details).

{
    'name': "Vendor Bill Payment Approval",
    'summary': """
        This module implements the approval mechanism for vendor bill.
    """,
    'version': '14.0.1.0.0',
    'category': 'Uncategorized',
    'website': "http://sodexis.com/",
    'author': "Sodexis",
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'depends': [
        'account',
        'payment',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'data/vendor_bill_payment_approval_edi_data.xml',
        'data/approval_request_ir_cron.xml',
        'views/account_move_views.xml',
        'views/res_config_settings.xml',
    ],
}
