from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from erpnext.utilities.product import get_price
from frappe import _

class Controller(Document):
    def get_spare_price(self, item_code, price_list, customer_group="All Customer Groups", company=None):
        price = get_spare_price(item_code, price_list, customer_group, company)
        return price

def get_spare_price(item_code, price_list, customer_group="All Customer Groups", company=None):
	price = get_price(item_code, price_list, customer_group, company)
	
	if not price:
		price = frappe._dict({'price_list_rate': 0.0})

	return price