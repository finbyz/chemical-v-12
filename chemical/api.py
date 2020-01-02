from __future__ import unicode_literals

import frappe
import frappe.defaults
from frappe import _
from frappe import msgprint, _
from frappe.utils import nowdate, flt, cint, cstr,now_datetime
from frappe.utils.background_jobs import enqueue
from frappe.desk.reportview import get_match_cond, get_filters_cond
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.contact.contact import get_contact_details, get_default_contact
from frappe.desk.notifications import get_filters_for

from erpnext.selling.doctype.customer.customer import Customer
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder
from erpnext.manufacturing.doctype.work_order.work_order import get_item_details	
from erpnext.manufacturing.doctype.production_plan.production_plan import ProductionPlan
from erpnext.buying.doctype.supplier.supplier import Supplier
from erpnext.manufacturing.doctype.bom.bom import add_additional_cost

import json
from six import itervalues, string_types

@frappe.whitelist()
def get_customer_ref_code(item_code, customer):
	ref_code = frappe.db.get_value("Item Customer Detail", {'parent': item_code, 'customer_name': customer}, 'ref_code')
	return ref_code if ref_code else ''

@frappe.whitelist()
def get_supplier_ref_code(item_code, supplier):

	ref_code = frappe.db.get_value("Item Supplier", {'parent': item_code, 'supplier': supplier}, 'supplier_part_no')	
	return ref_code 

@frappe.whitelist()
def customer_auto_name(self, method):
	if self.alias and self.customer_name != self.alias:
		self.name = self.alias

@frappe.whitelist()
def customer_override_after_rename(self, method, *args, **kwargs):
	Customer.after_rename = cust_after_rename

def cust_after_rename(self, olddn, newdn, merge=False):
	if frappe.defaults.get_global_default('cust_master_name') == 'Customer Name' and self.alias == self.customer_name:
		frappe.db.set(self, "customer_name", newdn)

@frappe.whitelist()
def supplier_auto_name(self, method):
	if self.alias and self.supplier_name != self.alias:
		self.name = self.alias

@frappe.whitelist()
def supplier_override_after_rename(self, method, *args, **kwargs):
	Supplier.after_rename = supp_after_rename

def supp_after_rename(self, olddn, newdn, merge=False):
	if frappe.defaults.get_global_default('supp_master_name') == 'Supplier Name' and self.alias == self.supplier_name:
		frappe.db.set(self, "supplier_name", newdn)

@frappe.whitelist()
def item_validate(self, method):
	fill_customer_code(self)

def fill_customer_code(self):
	""" Append all the customer codes and insert into "customer_code" field of item table """
	cust_code = []
	for d in self.get('customer_items'):
		cust_code.append(d.ref_code)
	self.customer_code = ""
	self.item_customer_code = ','.join(cust_code)

@frappe.whitelist()
def get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_party_details(party, party_type, ignore_permissions)

def _get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_address_details(out, party, party_type)
	set_contact_details(out, party, party_type)
	set_other_values(out, party, party_type)
	set_organization_details(out, party, party_type)
	return out

def set_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_address_display(out[billing_address_field])


def set_contact_details(out, party, party_type):
	out.contact_person = get_default_contact(party_type, party.name)

	if not out.contact_person:
		out.update({
			"contact_person": None,
			"contact_display": None,
			"contact_email": None,
			"contact_mobile": None,
			"contact_phone": None,
			"contact_designation": None,
			"contact_department": None
		})
	else:
		out.update(get_contact_details(out.contact_person))

def set_other_values(out, party, party_type):
	# copy
	if party_type=="Customer":
		to_copy = ["customer_name", "customer_group", "territory", "language"]
	else:
		to_copy = ["supplier_name", "supplier_type", "language"]
	for f in to_copy:
		out[f] = party.get(f)
		
def set_organization_details(out, party, party_type):

	organization = None

	if party_type == 'Lead':
		organization = frappe.db.get_value("Lead", {"name": party.name}, "company_name")
	elif party_type == 'Customer':
		organization = frappe.db.get_value("Customer", {"name": party.name}, "customer_name")
	elif party_type == 'Supplier':
		organization = frappe.db.get_value("Supplier", {"name": party.name}, "supplier_name")

	out.update({'party_name': organization})

@frappe.whitelist()
def IP_before_save(self,method):
	fetch_item_group(self)

def fetch_item_group(self):
	item_group = frappe.db.get_value("Item", self.item_code, "item_group")
	("item_group", item_group)

@frappe.whitelist()
def upadte_item_price(docname,item, price_list, per_unit_price):
	doc = frappe.get_doc("BOM",docname)
	if not doc.is_multiple_item:
		doc.cost_ratio_of_first_item = 100.0
	for row in doc.items:
		row.db_set('per_unit_rate', flt(row.amount)/doc.quantity * flt(doc.cost_ratio_of_first_item/100.0))
	for row in doc.scrap_items:
		row.db_set('per_unit_rate', flt(row.amount)/doc.quantity * flt(doc.cost_ratio_of_first_item/100.0))
	doc.db_set('volume_amount',flt(doc.volume_quantity) * flt(doc.volume_rate))
	doc.db_set('etp_amount',flt(doc.etp_qty) * flt(doc.etp_rate))
	doc.db_set('total_operational_cost',flt(doc.additional_amount) + flt(doc.volume_amount) + flt(doc.etp_amount))
	doc.db_set('total_scrap_cost', abs(doc.scrap_material_cost))
	doc.db_set("total_cost",doc.raw_material_cost + flt(doc.total_operational_cost) - flt(doc.scrap_material_cost))
	doc.db_set('per_unit_price',flt(doc.total_cost) / flt(doc.quantity) * flt(doc.cost_ratio_of_first_item/100.0))
	doc.db_set('per_unit_volume_cost',flt(doc.volume_amount/doc.quantity) * flt(doc.cost_ratio_of_first_item/100.0))	
	doc.db_set('per_unit_additional_cost',flt(flt(doc.additional_amount)/doc.quantity)* flt(doc.cost_ratio_of_first_item/100.0))
	doc.db_set('per_unit_rmc',flt(flt(doc.raw_material_cost)/doc.quantity)* flt(doc.cost_ratio_of_first_item/100.0))
	doc.db_set('per_unit_operational_cost',flt(flt(doc.total_operational_cost)/doc.quantity)* flt(doc.cost_ratio_of_first_item/100.0))
	doc.db_set('per_unit_scrap_cost',flt(flt(doc.total_scrap_cost)/doc.quantity)* flt(doc.cost_ratio_of_first_item/100.0))
	
	if frappe.db.exists("Item Price",{"item_code":item,"price_list":price_list}):
		name = frappe.db.get_value("Item Price",{"item_code":item,"price_list":price_list},'name')
		frappe.db.set_value("Item Price",name,"price_list_rate", per_unit_price)
	else:
		item_price = frappe.new_doc("Item Price")
		item_price.price_list = price_list
		item_price.item_code = item
		item_price.price_list_rate = per_unit_price
		
		item_price.save()
	frappe.db.commit()
		
	return "Item Price Updated!"

@frappe.whitelist()	
def update_item_price_daily():
	data = frappe.db.sql("""
		select 
			item, per_unit_price , buying_price_list, name
		from
			`tabBOM` 
		where 
			docstatus < 2 
			and is_default = 1 """,as_dict =1)
			
	for row in data:
		upadte_item_price(row.name,row.item, row.buying_price_list, row.per_unit_price)
		
	return "Latest price updated in Price List."

@frappe.whitelist()
def bom_before_save(self, method):
	cost_calculation(self)
	yield_cal(self)

@frappe.whitelist()
def bom_validate(self, method):
	price_overrides(self)
	qty_calculation(self)
	cost_calculation(self)

def price_overrides(self):
	for row in self.items:
		if row.from_price_list:
			#row.db_set('bom_no','')
			row.bom_no = ''

def qty_calculation(self):
	if self.is_multiple_item:
		self.db_set('quantity',flt(self.total_quantity * self.qty_ratio_of_first_item)/100.0)
		self.db_set('second_item_qty', flt(self.total_quantity - self.quantity))
	
def cost_calculation(self):
	etp_amount = 0
	additional_amount = 0
	self.volume_amount = flt(self.volume_quantity) * flt(self.volume_rate)
	if not self.is_multiple_item:
		self.cost_ratio_of_first_item = 100.0
	
	if hasattr(self, 'etp_qty'):
		etp_amount = flt(self.etp_qty)*flt(self.etp_rate)
		self.etp_amount = flt(self.etp_qty)*flt(self.etp_rate)
		self.db_set('per_unit_etp_cost',(flt(etp_amount/self.quantity) * flt(self.cost_ratio_of_first_item/100.0)))

	for row in self.items:
		row.per_unit_rate = flt(row.amount)/self.quantity * flt(self.cost_ratio_of_first_item/100.0)
	for row in self.scrap_items:
		row.per_unit_rate = flt(row.amount)/self.quantity * flt(self.cost_ratio_of_first_item/100.0)
		
	additional_amount = sum(flt(d.amount) for d in self.additional_cost)
	self.additional_amount = additional_amount
	self.db_set('total_operational_cost',flt(self.additional_amount) + flt(self.volume_amount) + etp_amount)
	self.db_set('total_scrap_cost', abs(self.scrap_material_cost))
	self.db_set('total_cost',self.raw_material_cost + self.total_operational_cost - flt(self.scrap_material_cost))
	per_unit_price = flt(self.total_cost) / flt(self.quantity)
	self.db_set('per_unit_volume_cost',flt(self.volume_amount/self.quantity)* flt(self.cost_ratio_of_first_item/100.0))	
	self.db_set('per_unit_additional_cost',flt(flt(self.additional_amount)/self.quantity)* flt(self.cost_ratio_of_first_item/100.0))
	self.db_set('per_unit_rmc',flt(flt(self.raw_material_cost)/self.quantity)* flt(self.cost_ratio_of_first_item/100.0))
	self.db_set('per_unit_operational_cost',flt(flt(self.total_operational_cost)/self.quantity)* flt(self.cost_ratio_of_first_item/100.0))
	self.db_set('per_unit_scrap_cost',flt(flt(self.total_scrap_cost)/self.quantity) * flt(self.cost_ratio_of_first_item/100.0))

	if self.per_unit_price != per_unit_price:
		self.db_set('per_unit_price', per_unit_price * flt(self.cost_ratio_of_first_item/100.0))
	frappe.db.commit()
	
def yield_cal(self):
	cal_yield = 0
	for d in self.items:
		if self.based_on and self.based_on == d.item_code:
			cal_yield = flt(self.quantity) / flt(d.qty)
			if self.is_multiple_item:
				self.second_item_batch_yield = flt(self.second_item_qty) / d.qty
	
	self.batch_yield = cal_yield

@frappe.whitelist()
def enqueue_update_cost():
	frappe.enqueue("chemical.api.update_cost")
	frappe.msgprint(_("Queued for updating latest price in all Bill of Materials. It may take a few minutes."))

def update_cost():
	from erpnext.manufacturing.doctype.bom.bom import get_boms_in_bottom_up_order

	bom_list = get_boms_in_bottom_up_order()
	for bom in bom_list:
		bom_obj = frappe.get_doc("BOM", bom)
		bom_obj.update_cost(update_parent=False, from_child_bom=True)
		if not bom_obj.is_multiple_item:
			bom_obj.cost_ratio_of_first_item = 100.0
		for row in bom_obj.items:
			row.db_set('per_unit_rate', flt(row.amount)/bom_obj.quantity * flt(bom_obj.cost_ratio_of_first_item/100.0))
		for row in bom_obj.scrap_items:
			row.db_set('per_unit_rate', flt(row.amount)/bom_obj.quantity * flt(bom_obj.cost_ratio_of_first_item/100.0))
			
		bom_obj.db_set("volume_amount",flt(bom_obj.volume_quantity) * flt(bom_obj.volume_rate))
		bom_obj.db_set("etp_amount",flt(bom_obj.etp_qty) * flt(bom_obj.etp_rate))
		bom_obj.db_set('total_operational_cost',flt(bom_obj.additional_amount) + flt(bom_obj.volume_amount) + flt(bom_obj.etp_amount))
		bom_obj.db_set('total_scrap_cost', abs(bom_obj.scrap_material_cost))
		bom_obj.db_set("total_cost",bom_obj.raw_material_cost + bom_obj.total_operational_cost - flt(bom_obj.scrap_material_cost) )
		per_unit_price = flt(bom_obj.total_cost) / flt(bom_obj.quantity)
		bom_obj.db_set('per_unit_price',flt(bom_obj.total_cost) / flt(bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))
		bom_obj.db_set('per_unit_volume_cost',flt(bom_obj.volume_amount/bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))	
		bom_obj.db_set('per_unit_additional_cost',flt(flt(bom_obj.additional_amount)/bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))
		bom_obj.db_set('per_unit_rmc',flt(flt(bom_obj.raw_material_cost)/bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))
		bom_obj.db_set('per_unit_operational_cost',flt(flt(bom_obj.total_operational_cost)/bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))
		bom_obj.db_set('per_unit_scrap_cost',flt(flt(bom_obj.total_scrap_cost)/bom_obj.quantity) * flt(bom_obj.cost_ratio_of_first_item/100.0))

		# if bom_obj.per_unit_price != per_unit_price:
			# bom_obj.db_set('per_unit_price', per_unit_price)
		if frappe.db.exists("Item Price",{"item_code":bom_obj.item,"price_list":bom_obj.buying_price_list}):
			name = frappe.db.get_value("Item Price",{"item_code":bom_obj.item,"price_list":bom_obj.buying_price_list},'name')
			frappe.db.set_value("Item Price",name,"price_list_rate", per_unit_price)
		else:
			item_price = frappe.new_doc("Item Price")
			item_price.price_list = bom_obj.buying_price_list
			item_price.item_code = bom_obj.item
			item_price.price_list_rate = per_unit_price
			
			item_price.save()
		frappe.db.commit()

@frappe.whitelist()
def se_before_submit(self, method):
	override_wo_functions(self)
	validate_concentration(self)

@frappe.whitelist()
def se_before_cancel(self, method):
	override_wo_functions(self)

def validate_concentration(self):
	if self.work_order and self.purpose == "Manufacture":
		wo_item = frappe.db.get_value("Work Order",self.work_order,'production_item')
		for row in self.items:
			if row.t_warehouse and row.item_code == wo_item and not row.concentration:
				frappe.throw(_("Add concentration in row {} for item {}".format(row.idx,row.item_code)))		

def override_wo_functions(self):
	WorkOrder.get_status = get_status
	WorkOrder.update_work_order_qty = update_work_order_qty

def get_status(self, status=None):

	'''Return the status based on stock entries against this Work Order'''
	if not status:
		status = self.status

	if self.docstatus==0:
		status = 'Draft'
	elif self.docstatus==1:
		if status != 'Stopped':
			stock_entries = frappe._dict(frappe.db.sql("""select purpose, sum(fg_completed_qty)
				from `tabStock Entry` where work_order=%s and docstatus=1
				group by purpose""", self.name))

			status = "Not Started"
			if stock_entries:
				status = "In Process"
				produced_qty = stock_entries.get("Manufacture")

				under_production = flt(frappe.db.get_value("Manufacturing Settings", None, "under_production_allowance_percentage"))
				allowed_qty = flt(self.qty) * (100 - under_production) / 100.0

				if flt(produced_qty) >= flt(allowed_qty):
					status = "Completed"
	else:
		status = 'Cancelled'

	return status

def update_work_order_qty(self):
	"""Update **Manufactured Qty** and **Material Transferred for Qty** in Work Order
		based on Stock Entry"""

	for purpose, fieldname in (("Manufacture", "produced_qty"),
		("Material Transfer for Manufacture", "material_transferred_for_manufacturing")):
		qty = flt(frappe.db.sql("""select sum(fg_completed_qty)
			from `tabStock Entry` where work_order=%s and docstatus=1
			and purpose=%s""", (self.name, purpose))[0][0])

		if not self.skip_transfer:
			if purpose == "Material Transfer for Manufacture" and self.material_transferred_for_manufacturing > self.qty:
				qty = self.qty

		self.db_set(fieldname, qty)

@frappe.whitelist()
def stock_entry_before_save(self, method):
	get_based_on(self)
	cal_target_yield_cons(self)
	if self.purpose == 'Repack' and cint(self.from_ball_mill) != 1:
		self.get_stock_and_rate()
	update_additional_cost(self)
	
def get_based_on(self):
	if self.work_order:
		self.based_on = frappe.db.get_value("Work Order", self.work_order, 'based_on')
		
def update_additional_cost(self):
	if self.purpose == "Manufacture" and self.bom_no:
		bom = frappe.get_doc("BOM",self.bom_no)
		
		if self.is_new() and not self.amended_from:
			self.append("additional_costs",{
				'description': "Spray drying cost",
				'qty': self.volume,
				'rate': self.volume_rate,
				'amount': self.volume_cost
			})
			if hasattr(self, 'etp_qty'):
				self.append("additional_costs",{
					'description': "ETP cost",
					'qty': self.etp_qty,
					'rate': self.etp_rate,
					'amount': flt(self.etp_qty * self.etp_rate)
				})
			if bom.additional_cost:
				for d in bom.additional_cost:
					self.append('additional_costs', {
						'description': d.description,
						'qty': flt(flt(self.fg_completed_qty * bom.quantity)/ bom.quantity),
						'rate': abs(d.rate),
						'amount':  abs(d.rate)* flt(flt(self.fg_completed_qty * bom.quantity)/ bom.quantity)
					})
		else:
			for row in self.additional_costs:
				if row.description == "Spray drying cost":
					row.qty = self.volume
					row.rate = self.volume_rate
					row.amount = self.volume_cost
				elif hasattr(self, 'etp_qty') and row.description == "ETP cost":
					row.qty = flt(self.etp_qty)
					row.rate = flt(self.etp_rate)
					row.amount = flt(self.etp_qty) * flt(self.etp_rate)
				elif bom.additional_cost:
					for d in bom.additional_cost:
						if row.description == d.description:
							row.qty = flt(flt(self.fg_completed_qty * bom.quantity)/ bom.quantity)
							row.rate = abs(d.rate)
							row.amount = abs(d.rate)* flt(flt(self.fg_completed_qty * bom.quantity)/ bom.quantity)   
							break
				
					
def cal_target_yield_cons(self):
	cal_yield = 0
	cons = 0
	tot_quan = 0
	item_arr = list()
	item_map = dict()
	flag = 0
	if self.purpose == "Manufacture" and self.based_on:
		for d in self.items:
			if d.t_warehouse:
				flag+=1		
			if d.item_code not in item_arr:
				item_map.setdefault(d.item_code, 0)
			
			item_map[d.item_code] += flt(d.qty)
			
		if flag == 1:
			# Last row object
			last_row = self.items[-1]

			# Last row batch_yield
			batch_yield = last_row.batch_yield

			# List of item_code from items table
			items_list = [row.item_code for row in self.items]

			# Check if items list has "Vinyl Sulphone (V.S)" and no based_on value
			if not self.based_on and "Vinyl Sulphone (V.S)" in items_list:
				cal_yield = flt(last_row.qty / item_map["Vinyl Sulphone (V.S)"]) # Last row qty / sum of items of "Vinyl Sulphone (V.S)" from map variable

			# Check if items list has frm.doc.based_on value
			elif self.based_on in items_list:
				cal_yield = flt(last_row.qty / item_map[self.based_on]) # Last row qty / sum of items of based_on item from map variable

			# if self.bom_no:
			# 	bom_batch_yield = flt(frappe.db.get_value("BOM", self.bom_no, 'batch_yield'))
			# 	cons = flt(bom_batch_yield * 100) / flt(cal_yield)
			# 	last_row.concentration = cons

			last_row.batch_yield = flt(cal_yield) * (flt(last_row.concentration) / 100.0)

@frappe.whitelist()
def stock_entry_on_submit(self, method):
	update_po(self)

def update_po(self):
	if self.purpose in ["Material Transfer for Manufacture", "Manufacture"] and self.work_order:
		po = frappe.get_doc("Work Order",self.work_order)
		if self.purpose == "Material Transfer for Manufacture":
			if po.material_transferred_for_manufacturing > po.qty:
				 po.material_transferred_for_manufacturing = po.qty
							
		if self.purpose == 'Manufacture':	
			if self.volume:
				update_po_volume(self, po)
			
			update_po_transfer_qty(self, po)
			update_po_items(self, po)

			last_item = self.items[-1]

			po.batch_yield = last_item.batch_yield
			po.concentration = last_item.concentration
			po.batch = last_item.get('batch_no')
			po.lot_no = last_item.lot_no
			po.valuation_rate = last_item.valuation_rate

		po.save()
		frappe.db.commit()

def update_po_volume(self, po, ignore_permissions = True):
	if not self.volume:
		frappe.throw(_("Please add volume before submitting the stock entry"))

	if self._action == 'submit':
		po.volume += self.volume
		self.volume_cost = flt(flt(self.volume) * flt(self.volume_rate))		
		po.volume_cost +=  self.volume_cost
		#self.save(ignore_permissions = True)
		po.save(ignore_permissions = True)

	elif self._action == 'cancel':
		po.volume -= self.volume
		po.volume_cost -= self.volume_cost
		po.save(ignore_permissions=True)
		
def update_po_transfer_qty(self, po):
	for d in po.required_items:
		se_items_date = frappe.db.sql('''select sum(qty), valuation_rate
			from `tabStock Entry` entry, `tabStock Entry Detail` detail
			where
				entry.work_order = %s
				and entry.purpose = "Manufacture"
				and entry.docstatus = 1
				and detail.parent = entry.name
				and detail.item_code = %s''', (po.name, d.item_code))[0]

		d.db_set('transferred_qty', flt(se_items_date[0]), update_modified = False)
		d.db_set('valuation_rate', flt(se_items_date[1]), update_modified = False)

def update_po_items(self,po):
	from erpnext.stock.utils import get_latest_stock_qty

	for row in self.items:
		if row.s_warehouse and not row.t_warehouse:
			item = [d.name for d in po.required_items if d.item_code == row.item_code]

			if not item:
				po.append('required_items', {
					'item_code': row.item_code,
					'item_name': row.item_name,
					'description': row.description,
					'source_warehouse': row.s_warehouse,
					'required_qty': row.qty,
					'transferred_qty': row.qty,
					'valuation_rate': row.valuation_rate,
					'available_qty_at_source_warehouse': get_latest_stock_qty(row.item_code, row.s_warehouse),
				})

	for child in po.required_items:
		child.db_update()

@frappe.whitelist()
def stock_entry_on_cancel(self, method):
	if self.work_order:
		pro_doc = frappe.get_doc("Work Order", self.work_order)
		set_po_status(self, pro_doc)
		if self.volume:		
			update_po_volume(self, pro_doc)
			
		update_po_transfer_qty(self, pro_doc)

		pro_doc.save()
		frappe.db.commit()

def set_po_status(self, pro_doc):
	status = None
	if flt(pro_doc.material_transferred_for_instruction):
		status = "In Process"

	if status:
		pro_doc.db_set('status', status)

@frappe.whitelist()
def make_stock_entry(work_order_id, purpose, qty=None):
	from erpnext.stock.doctype.stock_entry.stock_entry import get_additional_costs

	work_order = frappe.get_doc("Work Order", work_order_id)
	if not frappe.db.get_value("Warehouse", work_order.wip_warehouse, "is_group") \
			and not work_order.skip_transfer:
		wip_warehouse = work_order.wip_warehouse
	else:
		wip_warehouse = None
	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.purpose = purpose
	stock_entry.work_order = work_order_id
	stock_entry.company = work_order.company
	stock_entry.from_bom = 1
	stock_entry.bom_no = work_order.bom_no
	stock_entry.use_multi_level_bom = work_order.use_multi_level_bom
	stock_entry.fg_completed_qty = qty or (flt(work_order.qty) - flt(work_order.produced_qty))
	if work_order.bom_no:
		stock_entry.inspection_required = frappe.db.get_value('BOM',
			work_order.bom_no, 'inspection_required')
	
	if purpose=="Material Transfer for Manufacture":
		stock_entry.to_warehouse = wip_warehouse
		stock_entry.project = work_order.project
	else:
		stock_entry.from_warehouse = wip_warehouse
		stock_entry.to_warehouse = work_order.fg_warehouse
		stock_entry.project = work_order.project
		# if purpose=="Manufacture":
			# additional_costs = get_additional_costs(work_order, fg_qty=stock_entry.fg_completed_qty)
			# stock_entry.set("additional_costs", additional_costs)

	get_items(stock_entry)
	if purpose=='Manufacture':
		if hasattr(work_order, 'second_item'):
			if work_order.second_item:
				bom = frappe.db.sql(''' select name from tabBOM where item = %s ''',work_order.second_item)
				if bom:
					bom = bom[0][0]
					stock_entry.append('items',{
						'item_code': work_order.second_item,
						't_warehouse': work_order.fg_warehouse,
						'qty': work_order.second_item_qty,
						'uom': frappe.db.get_value('Item',work_order.second_item,'stock_uom'),
						'stock_uom': frappe.db.get_value('Item',work_order.second_item,'stock_uom'),
						'conversion_factor': 1 ,
						'bom_no': bom
					})
				else:
					frappe.throw(_('Please create BOM for item {}'.format(work_order.second_item)))
	return stock_entry.as_dict()

def get_items(self):
	self.set('items', [])
	self.validate_work_order()

	if not self.posting_date or not self.posting_time:
		frappe.throw(_("Posting date and posting time is mandatory"))

	self.set_work_order_details()

	if self.bom_no:

		if self.purpose in ["Material Issue", "Material Transfer", "Manufacture", "Repack",
				"Subcontract", "Material Transfer for Manufacture", "Material Consumption for Manufacture"]:

			if self.work_order and self.purpose == "Material Transfer for Manufacture":
				item_dict = self.get_pending_raw_materials()
				if self.to_warehouse and self.pro_doc:
					for item in itervalues(item_dict):
						item["to_warehouse"] = self.pro_doc.wip_warehouse
				self.add_to_stock_entry_detail(item_dict)

			elif (self.work_order and (self.purpose == "Manufacture" or self.purpose == "Material Consumption for Manufacture")
				and not self.pro_doc.skip_transfer and frappe.db.get_single_value("Manufacturing Settings",
				"backflush_raw_materials_based_on")== "Material Transferred for Manufacture"):
				get_transfered_raw_materials(self)

			elif (self.work_order and (self.purpose == "Manufacture" or self.purpose == "Material Consumption for Manufacture")
				and self.pro_doc.skip_transfer and frappe.db.get_single_value("Manufacturing Settings",
				"backflush_raw_materials_based_on")== "Material Transferred for Manufacture"):
				get_material_transfered_raw_materials(self)

			elif self.work_order and (self.purpose == "Manufacture" or self.purpose == "Material Consumption for Manufacture") and \
				frappe.db.get_single_value("Manufacturing Settings", "backflush_raw_materials_based_on")== "BOM" and \
				frappe.db.get_single_value("Manufacturing Settings", "material_consumption")== 1:
				self.get_unconsumed_raw_materials()

			else:
				if not self.fg_completed_qty:
					frappe.throw(_("Manufacturing Quantity is mandatory"))

				item_dict = self.get_bom_raw_materials(self.fg_completed_qty)

				#Get PO Supplied Items Details
				if self.purchase_order and self.purpose == "Subcontract":
					#Get PO Supplied Items Details
					item_wh = frappe._dict(frappe.db.sql("""
						select rm_item_code, reserve_warehouse
						from `tabPurchase Order` po, `tabPurchase Order Item Supplied` poitemsup
						where po.name = poitemsup.parent
							and po.name = %s""",self.purchase_order))

				for item in itervalues(item_dict):
					if self.pro_doc and (cint(self.pro_doc.from_wip_warehouse) or not self.pro_doc.skip_transfer):
						item["from_warehouse"] = self.pro_doc.wip_warehouse
					#Get Reserve Warehouse from PO
					if self.purchase_order and self.purpose=="Subcontract":
						item["from_warehouse"] = item_wh.get(item.item_code)
					item["to_warehouse"] = self.to_warehouse if self.purpose=="Subcontract" else ""

				self.add_to_stock_entry_detail(item_dict)

				if self.purpose != "Subcontract":
					scrap_item_dict = self.get_bom_scrap_material(self.fg_completed_qty)
					for item in itervalues(scrap_item_dict):
						if self.pro_doc and self.pro_doc.scrap_warehouse:
							item["to_warehouse"] = self.pro_doc.scrap_warehouse

					self.add_to_stock_entry_detail(scrap_item_dict, bom_no=self.bom_no)

		# fetch the serial_no of the first stock entry for the second stock entry
		if self.work_order and self.purpose == "Manufacture":
			self.set_serial_nos(self.work_order)
			work_order = frappe.get_doc('Work Order', self.work_order)
			add_additional_cost(self, work_order)

		# add finished goods item
		if self.purpose in ("Manufacture", "Repack"):
			self.load_items_from_bom()

	self.set_actual_qty()
	self.calculate_rate_and_amount(raise_error_if_no_rate=False)

def get_transfered_raw_materials(self):
	transferred_materials = frappe.db.sql("""
		select
			item_name, original_item, item_code, qty, sed.t_warehouse as warehouse,
			description, stock_uom, expense_account, cost_center, batch_no
		from `tabStock Entry` se,`tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1 and se.purpose='Material Transfer for Manufacture'
			and se.work_order= %s and ifnull(sed.t_warehouse, '') != ''
	""", self.work_order, as_dict=1)

	materials_already_backflushed = frappe.db.sql("""
		select
			item_code, sed.s_warehouse as warehouse, sum(qty) as qty
		from
			`tabStock Entry` se, `tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1
			and (se.purpose='Manufacture' or se.purpose='Material Consumption for Manufacture')
			and se.work_order= %s and ifnull(sed.s_warehouse, '') != ''
	""", self.work_order, as_dict=1)

	backflushed_materials= {}
	for d in materials_already_backflushed:
		backflushed_materials.setdefault(d.item_code,[]).append({d.warehouse: d.qty})

	po_qty = frappe.db.sql("""select qty, produced_qty, material_transferred_for_manufacturing from
		`tabWork Order` where name=%s""", self.work_order, as_dict=1)[0]

	manufacturing_qty = flt(po_qty.qty)
	produced_qty = flt(po_qty.produced_qty)
	trans_qty = flt(po_qty.material_transferred_for_manufacturing)

	for item in transferred_materials:
		qty= item.qty
		item_code = item.original_item or item.item_code
		req_items = frappe.get_all('Work Order Item',
			filters={'parent': self.work_order, 'item_code': item_code},
			fields=["required_qty", "consumed_qty"]
			)
		if not req_items:
			frappe.msgprint(_("Did not found transfered item {0} in Work Order {1}, the item not added in Stock Entry")
				.format(item_code, self.work_order))
			continue

		req_qty = flt(req_items[0].required_qty)
		req_qty_each = flt(req_qty / manufacturing_qty)
		consumed_qty = flt(req_items[0].consumed_qty)

		if trans_qty and manufacturing_qty >= (produced_qty + flt(self.fg_completed_qty)):
			# if qty >= req_qty:
			# 	qty = (req_qty/trans_qty) * flt(self.fg_completed_qty)
			# else:
			qty = qty - consumed_qty

			if self.purpose == 'Manufacture':
				# If Material Consumption is booked, must pull only remaining components to finish product
				if consumed_qty != 0:
					remaining_qty = consumed_qty - (produced_qty * req_qty_each)
					exhaust_qty = req_qty_each * produced_qty
					if remaining_qty > exhaust_qty :
						if (remaining_qty/(req_qty_each * flt(self.fg_completed_qty))) >= 1:
							qty =0
						else:
							qty = (req_qty_each * flt(self.fg_completed_qty)) - remaining_qty
				# else:
				# 	qty = req_qty_each * flt(self.fg_completed_qty)


		elif backflushed_materials.get(item.item_code):
			for d in backflushed_materials.get(item.item_code):
				if d.get(item.warehouse):
					if (qty > req_qty):
						qty = req_qty
						qty-= d.get(item.warehouse)

		if qty > 0:
			add_to_stock_entry_detail(self, {
				item.item_code: {
					"from_warehouse": item.warehouse,
					"to_warehouse": "",
					"qty": qty,
					"item_name": item.item_name,
					"description": item.description,
					"stock_uom": item.stock_uom,
					"expense_account": item.expense_account,
					"cost_center": item.buying_cost_center,
					"original_item": item.original_item,
					"batch_no": item.batch_no
				}
			})


def get_material_transfered_raw_materials(self):
	mti_data = frappe.db.sql("""select name
		from `tabMaterial Transfer Instruction`
		where docstatus = 1
			and work_order = %s """, self.work_order, as_dict = 1)

	if not mti_data:
		frappe.msgprint(_("No Material Transfer Instruction found!"))
		return

	transfer_data = []

	for mti in mti_data:
		mti_doc = frappe.get_doc("Material Transfer Instruction", mti.name)
		for row in mti_doc.items:
			self.append('items', {
				'item_code': row.item_code,
				'item_name': row.item_name,
				'description': row.description,
				'uom': row.uom,
				'stock_uom': row.stock_uom,
				'qty': row.qty,
				'batch_no': row.batch_no,
				'transfer_qty': row.transfer_qty,
				'conversion_factor': row.conversion_factor,
				's_warehouse': row.s_warehouse,
				'bom_no': row.bom_no,
				'lot_no': row.lot_no,
				'packaging_material': row.packaging_material,
				'packing_size': row.packing_size,
				'batch_yield': row.batch_yield,
				'concentration': row.concentration,
			})

def add_to_stock_entry_detail(self, item_dict, bom_no=None):
	cost_center = frappe.db.get_value("Company", self.company, 'cost_center')

	for d in item_dict:
		stock_uom = item_dict[d].get("stock_uom") or frappe.db.get_value("Item", d, "stock_uom")

		se_child = self.append('items')
		se_child.s_warehouse = item_dict[d].get("from_warehouse")
		se_child.t_warehouse = item_dict[d].get("to_warehouse")
		se_child.item_code = item_dict[d].get('item_code') or cstr(d)
		se_child.item_name = item_dict[d]["item_name"]
		se_child.description = item_dict[d]["description"]
		se_child.uom = item_dict[d]["uom"] if item_dict[d].get("uom") else stock_uom
		se_child.stock_uom = stock_uom
		se_child.qty = flt(item_dict[d]["qty"], se_child.precision("qty"))
		se_child.expense_account = item_dict[d].get("expense_account")
		se_child.cost_center = item_dict[d].get("cost_center") or cost_center
		se_child.allow_alternative_item = item_dict[d].get("allow_alternative_item", 0)
		se_child.subcontracted_item = item_dict[d].get("main_item_code")
		se_child.original_item = item_dict[d].get("original_item")
		se_child.batch_no = item_dict[d].get("batch_no")

		if item_dict[d].get("idx"):
			se_child.idx = item_dict[d].get("idx")

		if se_child.s_warehouse==None:
			se_child.s_warehouse = self.from_warehouse
		if se_child.t_warehouse==None:
			se_child.t_warehouse = self.to_warehouse

		# in stock uom
		se_child.conversion_factor = flt(item_dict[d].get("conversion_factor")) or 1
		se_child.transfer_qty = flt(item_dict[d]["qty"]*se_child.conversion_factor, se_child.precision("qty"))


		# to be assigned for finished item
		se_child.bom_no = bom_no


@frappe.whitelist()
def dn_on_submit(self, method):
	update_sales_invoice(self)
	validate_customer_batch(self)

@frappe.whitelist()
def dn_before_cancel(self, method):
	update_sales_invoice(self)

def update_sales_invoice(self):
	for row in self.items:
		if row.against_sales_invoice and row.si_detail:
			if self._action == 'submit':
				delivery_note = self.name
				dn_detail = row.name

			elif self._action == 'cancel':
				delivery_note = ''
				dn_detail = ''

			frappe.db.sql("""update `tabSales Invoice Item` 
				set dn_detail = %s, delivery_note = %s 
				where name = %s """, (dn_detail, delivery_note, row.si_detail))
				
@frappe.whitelist()
def si_before_submit(self,method):
	validate_customer_batch(self)
	
def validate_customer_batch(self):
	for row in self.items:
		if row.batch_no:
			batch_customer = frappe.db.get_value("Batch",row.batch_no,"customer")
			if batch_customer:
				if batch_customer != self.customer:
					frappe.throw(_("Please select correct batch for customer <strong>{}</strong> in row {}".format(self.customer,row.idx)))

@frappe.whitelist()
def pr_validate(self, method):
	validate_batch_wise_item_for_concentration(self)

@frappe.whitelist()
def stock_entry_validate(self, method):
	if self.purpose == "Material Receipt":
		validate_batch_wise_item_for_concentration(self)

def validate_batch_wise_item_for_concentration(self):
	for row in self.items:
		has_batch_no = frappe.db.get_value('Item', row.item_code, 'has_batch_no')

		# if not has_batch_no and flt(row.concentration):
			# frappe.throw(_("Row #{idx}. Please remove concentration for non batch item {item_code}.".format(idx = row.idx, item_code = frappe.bold(row.item_code))))
		if not has_batch_no:
			row.concentration = 100
			
@frappe.whitelist()
def sl_before_submit(self, method):
	batch_qty_validation_with_date_time(self)
	
def batch_qty_validation_with_date_time(self):
	if self.batch_no and not self.get("allow_negative_stock"):
		batch_bal_after_transaction = flt(frappe.db.sql("""select sum(actual_qty)
			from `tabStock Ledger Entry`
			where warehouse=%s and item_code=%s and batch_no=%s and concat(posting_date, ' ', posting_time) <= %s %s """,
			(self.warehouse, self.item_code, self.batch_no, self.posting_date, self.posting_time))[0][0])
		
		if flt(batch_bal_after_transaction) < 0:
			frappe.throw(_("Stock balance in Batch {0} will become negative {1} for Item {2} at Warehouse {3} at date {4} and time {5}")
				.format(self.batch_no, batch_bal_after_transaction, self.item_code, self.warehouse, self.posting_date, self.posting_time))


def so_on_cancel(self, method):
	pass
	
def update_outward_sample(self) :
	for row in self.items:
		if row.outward_sample:
			os_doc = frappe.get_doc("Outward Sample",row.outward_sample)
			os_doc.db_set('sales_order', '')

# Override Production Plan Functions
@frappe.whitelist()
def override_proplan_functions():

	ProductionPlan.get_open_sales_orders = get_open_sales_orders
	ProductionPlan.get_items = get_items_from_sample

def get_sales_orders(self):
	so_filter = item_filter = ""
	if self.from_date:
		so_filter += " and so.transaction_date >= %(from_date)s"
	if self.to_date:
		so_filter += " and so.transaction_date <= %(to_date)s"
	if self.customer:
		so_filter += " and so.customer = %(customer)s"
	if self.project:
		so_filter += " and so.project = %(project)s"

	if self.item_code:
		item_filter += " and so_item.item_code = %(item)s"

	open_so = frappe.db.sql("""
		select distinct so.name, so.transaction_date, so.customer, so.base_grand_total
		from `tabSales Order` so, `tabSales Order Item` so_item
		where so_item.parent = so.name
			and so.docstatus = 1 and so.status not in ("Stopped", "Closed")
			and so.company = %(company)s
			and so_item.qty > so_item.work_order_qty {0} {1}

		""".format(so_filter, item_filter), {
			"from_date": self.from_date,
			"to_date": self.to_date,
			"customer": self.customer,
			"project": self.project,
			"item": self.item_code,
			"company": self.company

		}, as_dict=1)

	return open_so

def get_open_sales_orders(self):
		""" Pull sales orders  which are pending to deliver based on criteria selected"""
		open_so = get_sales_orders(self)
		if open_so:
			self.add_so_in_table(open_so)
		else:
			frappe.msgprint(_("Sales orders are not available for production"))

@frappe.whitelist()
def get_items_from_sample(self):
	if self.get_items_from == "Sales Order":
			get_so_items(self)
	elif self.get_items_from == "Material Request":
			self.get_mr_items()

def get_so_items(self):
		so_list = [d.sales_order for d in self.get("sales_orders", []) if d.sales_order]
		if not so_list:
			msgprint(_("Please enter Sales Orders in the above table"))
			return []
		item_condition = ""
		if self.item_code:
			item_condition = ' and so_item.item_code = "{0}"'.format(frappe.db.escape(self.item_code))
	# -----------------------	custom added code  ------------#
		if self.as_per_projected_qty == 1:                                                           #condition 1
			sample_list = [[d.outward_sample, d.quantity ,d.projected_qty] for d in self.get("finish_items", []) if d.outward_sample]	
			if not sample_list:
				frappe.msgprint(_("Please Get Finished Items."))
				return []	
			item_details = frappe._dict()

			for sample, quantity ,projected_qty in sample_list:#changes here
				if projected_qty < 0:
					sample_doc = frappe.get_doc("Outward Sample",sample)
					for row in sample_doc.details:
						bom_no = frappe.db.exists("BOM", {'item':row.item_code,'is_active':1,'is_default':1,'docstatus':1})

						if bom_no:
							item_details.setdefault(row.item_code, frappe._dict({
								'planned_qty': 0.0,
								'bom_no': bom_no,
								'item_code': row.item_code
							}))
							
							item_details[row.item_code].planned_qty += flt(abs(projected_qty)) * flt(row.quantity) / flt(sample_doc.total_qty)
			
			items = [values for values in item_details.values()]

		elif self.as_per_actual_qty == 1:															 #condition 2
			
			sample_list = [[d.outward_sample, d.quantity,d.actual_qty] for d in self.get("finish_items", []) if d.outward_sample]	
			if not sample_list:
				frappe.msgprint(_("Please Get Finished Items."))
				return []	
			item_details = frappe._dict()
			for sample, quantity, actual_qty in sample_list:
				diff = actual_qty - quantity #changes here
				if diff < 0:
					sample_doc = frappe.get_doc("Outward Sample",sample)

					for row in sample_doc.details:
						bom_no = frappe.db.exists("BOM", {'item':row.item_code,'is_active':1,'is_default':1,'docstatus':1})

						if bom_no:
							item_details.setdefault(row.item_code, frappe._dict({
								'planned_qty': 0.0,
								'bom_no': bom_no,
								'item_code': row.item_code
							}))
							
							item_details[row.item_code].planned_qty += flt(abs(diff)) * flt(row.quantity) / flt(sample_doc.total_qty)
							
			items = [values for values in item_details.values()]

		else:		
																						 #default
			sample_list = [[d.outward_sample, d.quantity] for d in self.get("finish_items", []) if d.outward_sample]	
			if not sample_list:
				frappe.msgprint(_("Please Get Finished Items."))
				return []	
			item_details = frappe._dict()
			for sample, quantity in sample_list:
				sample_doc = frappe.get_doc("Outward Sample",sample)

				for row in sample_doc.details:
					bom_no = frappe.db.exists("BOM", {'item':row.item_code,'is_active':1,'is_default':1,'docstatus':1})

					if bom_no:
						item_details.setdefault(row.item_code, frappe._dict({
							'planned_qty': 0.0,
							'bom_no': bom_no,
							'item_code': row.item_code
						}))

						item_details[row.item_code].planned_qty += flt(quantity) * flt(row.quantity) / flt(sample_doc.total_qty)

			items = [values for values in item_details.values()]

		
	# -----------------------	
		# items = frappe.db.sql("""select distinct parent, item_code, warehouse,
		# 	(qty - work_order_qty) * conversion_factor as pending_qty, name
		# 	from `tabSales Order Item` so_item
		# 	where parent in (%s) and docstatus = 1 and qty > work_order_qty
		# 	and exists (select name from `tabBOM` bom where bom.item=so_item.item_code
		# 			and bom.is_active = 1) %s""" % \
		# 	(", ".join(["%s"] * len(so_list)), item_condition), tuple(so_list), as_dict=1)

		if self.item_code:
			item_condition = ' and so_item.item_code = "{0}"'.format(frappe.db.escape(self.item_code))

		packed_items = frappe.db.sql("""select distinct pi.parent, pi.item_code, pi.warehouse as warehouse,
			(((so_item.qty - so_item.work_order_qty) * pi.qty) / so_item.qty)
				as pending_qty, pi.parent_item, so_item.name
			from `tabSales Order Item` so_item, `tabPacked Item` pi
			where so_item.parent = pi.parent and so_item.docstatus = 1
			and pi.parent_item = so_item.item_code
			and so_item.parent in (%s) and so_item.qty > so_item.work_order_qty
			and exists (select name from `tabBOM` bom where bom.item=pi.item_code
					and bom.is_active = 1) %s""" % \
			(", ".join(["%s"] * len(so_list)), item_condition), tuple(so_list), as_dict=1)

		add_items(self,items + packed_items)
		calculate_total_planned_qty(self)

def add_items(self, items):
	# frappe.msgprint("call add")
	self.set('po_items', [])
	for data in items:
		item_details = get_item_details(data.item_code)
		pi = self.append('po_items', {
			'include_exploded_items': 1,
			'warehouse': data.warehouse,
			'item_code': data.item_code,
			'description': item_details and item_details.description or '',
			'stock_uom': item_details and item_details.stock_uom or '',
			'bom_no': item_details and item_details.bom_no or '',
			# 'planned_qty': data.pending_qty, 
			'planned_qty':data.planned_qty,
			'pending_qty': data.pending_qty,
			'planned_start_date': now_datetime(),
			'product_bundle_item': data.parent_item
		})

		if self.get_items_from == "Sales Order":
			pi.sales_order = data.parent
			pi.sales_order_item = data.name

		elif self.get_items_from == "Material Request":
			pi.material_request = data.parent
			pi.material_request_item = data.name

def calculate_total_planned_qty(self):
		self.total_planned_qty = 0
		for d in self.po_items:
			self.total_planned_qty += flt(d.planned_qty)

@frappe.whitelist()
def get_actual_and_projected_qty(warehouse,item_code):
	qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse},["projected_qty", "actual_qty"], as_dict=True, cache=True)
	return qty['actual_qty'] ,qty['projected_qty']


@frappe.whitelist()
def get_open_count(doctype, name, links):
	'''Get open count for given transactions and filters

	:param doctype: Reference DocType
	:param name: Reference Name
	:param transactions: List of transactions (json/dict)
	:param filters: optional filters (json/list)'''

	frappe.has_permission(doc=frappe.get_doc(doctype, name), throw=True)

	meta = frappe.get_meta(doctype)
	#links = meta.get_dashboard_data()

	links = frappe._dict({
		'fieldname': 'party',
		'transactions': [
			{
				'label': _('Outward Sample'),
				'items': ['Outward Sample']
			},
			{
				'label': _('Inward Sample'),
				'items': ['Inward Sample']
			},
		]
	})
    #frappe.msgprint(str(links))
    #links = frappe._dict(links)
    #return {'count':0}


	# compile all items in a list
	items = []
	for group in links.transactions:
		items.extend(group.get('items'))

	out = []
	for d in items:
		if d in links.get('internal_links', {}):
			# internal link
			continue

		filters = get_filters_for(d)
		fieldname = links.get('non_standard_fieldnames', {}).get(d, links.fieldname)
        #return fieldname
		data = {'name': d}
		if filters:
			# get the fieldname for the current document
			# we only need open documents related to the current document
			filters[fieldname] = name
			total = len(frappe.get_all(d, fields='name',
				filters=filters, limit=100, distinct=True, ignore_ifnull=True))
			data['open_count'] = total

		total = len(frappe.get_all(d, fields='name',
			filters={fieldname: name}, limit=100, distinct=True, ignore_ifnull=True))
		data['count'] = total
		out.append(data)

	out = {
		'count': out,
	}

	module = frappe.get_meta_module(doctype)
	if hasattr(module, 'get_timeline_data'):
		out['timeline_data'] = module.get_timeline_data(doctype, name)
    
	return out

	
# 	if isinstance(doc, string_types):
# 		doc = json.loads(doc)
		
# 	so_list = [d['sales_order'] for d in doc['sales_orders'] if d['sales_order']]

# 	sample_list = [d['outward_sample'] for d in doc['finish_items'] if d['outward_sample']]
# 	if not sample_list:
# 		frappe.msgprint(_("Please enter Sales Orders in the above table"))
# 		return []

# 	for sample in sample_list:
# 		sample_doc = frappe.get_doc("Outward Sample",sample)
# 		items_list = [d.item_code for d in sample_doc.details]

# 		for item_code in items_list:
# 			items = frappe.db.sql("""select item as item_code,name as bom_no from `tabBOM` where item = '%s' and is_active = 1 and is_default = 1 and docstatus= 1"""%item_code,as_dict=1)
			
	
# 	if doc['item_code']:
# 		item_condition = ' and so_item.item_code = "{0}"'.format(frappe.db.escape( doc['item_code']))

# 		packed_items = frappe.db.sql("""select distinct pi.parent, pi.item_code, pi.warehouse as warehouse,
# 			(((so_item.qty - so_item.work_order_qty) * pi.qty) / so_item.qty)
# 				as pending_qty, pi.parent_item, so_item.name
# 			from `tabSales Order Item` so_item, `tabPacked Item` pi
# 			where so_item.parent = pi.parent and so_item.docstatus = 1
# 			and pi.parent_item = so_item.item_code
# 			and so_item.parent in (%s) and so_item.qty > so_item.work_order_qty
# 			and exists (select name from `tabBOM` bom where bom.item=pi.item_code
# 					and bom.is_active = 1) %s""" % \
# 			(", ".join(["%s"] * len(so_list)), item_condition), tuple(so_list), as_dict=1)

# 	add_items(items,packed_items)
# 	# calculate_total_planned_qty()

# def add_items(self, items):
# 	self.set('po_items', [])
# 	for data in items:
# 		item_details = get_item_details(data.item_code)
# 		pi = self.append('po_items', {
# 			'include_exploded_items': 1,
# 			'warehouse': data.warehouse,
# 			'item_code': data.item_code,
# 			'description': item_details and item_details.description or '',
# 			'stock_uom': item_details and item_details.stock_uom or '',
# 			'bom_no': item_details and item_details.bom_no or '',
# 			'planned_qty': data.pending_qty,
# 			'pending_qty': data.pending_qty,
# 			'planned_start_date': now_datetime(),
# 			'product_bundle_item': data.parent_item
# 		})

# 		if self.get_items_from == "Sales Order":
# 			pi.sales_order = data.parent
# 			pi.sales_order_item = data.name

# 		elif self.get_items_from == "Material Request":
# 			pi.material_request = data.parent
# 			pi.material_request_item = data.name

# # def calculate_total_planned_qty(self):
# # 	self.total_planned_qty = 0
# # 	for d in self.po_items:
# # 		self.total_planned_qty += flt(d.planned_qty)

	
		

	