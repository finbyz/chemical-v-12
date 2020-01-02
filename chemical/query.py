from __future__ import unicode_literals
import frappe
import json
from frappe import _, db
from erpnext.utilities.product import get_price
from frappe.desk.reportview import get_match_cond, get_filters_cond
from frappe.utils import nowdate, flt

def new_item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	conditions = []

	return db.sql("""
		select tabItem.name, tabItem.item_customer_code, tabItem.item_group,
			if(length(tabItem.item_name) > 40, concat(substr(tabItem.item_name, 1, 40), "..."), item_name) as item_name,
			tabItem.item_group, if(length(tabItem.description) > 40, concat(substr(tabItem.description, 1, 40), "..."), description) as decription
		from tabItem
		where 
			tabItem.docstatus < 2
			and tabItem.has_variants=0
			and tabItem.disabled=0
			and (tabItem.end_of_life > %(today)s or ifnull(tabItem.end_of_life, '0000-00-00')='0000-00-00')
			and (tabItem.`{key}` LIKE %(txt)s
				or tabItem.item_name LIKE %(txt)s
				or tabItem.item_group LIKE %(txt)s
				or tabItem.item_customer_code LIKE %(txt)s)
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, item_name), locate(%(_txt)s, item_name), 99999) 
		limit %(start)s, %(page_len)s """.format(
			key=searchfield,
			fcond=get_filters_cond(doctype, filters, conditions).replace('%', '%%'),
			mcond=get_match_cond(doctype).replace('%', '%%')),
			{
				"today": nowdate(),
				"txt": "%s%%" % txt,
				"_txt": txt.replace("%", ""),
				"start": start,
				"page_len": page_len
			}, as_dict=as_dict)

 # searches for customer
@frappe.whitelist(allow_guest = 1)
def new_customer_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []
	meta = frappe.get_meta("Customer")
	searchfields = meta.get_search_fields()
	searchfields = searchfields + [f for f in [searchfield or "name", "customer_name"] \
			if not f in searchfields]

	searchfields = " or ".join([field + " like %(txt)s" for field in searchfields])
	fields = ["name"]
	fields = ", ".join(fields)

	return frappe.db.sql("""select {fields} from `tabCustomer`
		where docstatus < 2
			and ({scond}) and disabled=0
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, customer_name), locate(%(_txt)s, customer_name), 99999),
			idx desc,
			name, customer_name
		limit %(start)s, %(page_len)s""".format(**{
			"fields": fields,
			"mcond": get_match_cond(doctype),
			"scond": searchfields,
			"fcond": get_filters_cond(doctype, filters, conditions).replace('%', '%%'),
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

# searches for supplier
@frappe.whitelist()
def new_supplier_query(doctype, txt, searchfield, start, page_len, filters):
	supp_master_name = frappe.defaults.get_user_default("supp_master_name")
	if supp_master_name == "Supplier Name":
		fields = ["name"]
	else:
		fields = ["name"]
	fields = ", ".join(fields)

	return frappe.db.sql("""select {field} from `tabSupplier`
		where docstatus < 2
			and ({key} like %(txt)s
				or supplier_name like %(txt)s) and disabled=0
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, supplier_name), locate(%(_txt)s, supplier_name), 99999),
			idx desc,
			name, supplier_name
		limit %(start)s, %(page_len)s """.format(**{
			'field': fields,
			'key': searchfield,
			'mcond':get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

@frappe.whitelist()	
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []

	so_searchfield = frappe.get_meta("Sales Order").get_search_fields()
	so_searchfields = " or ".join(["so.`" + field + "` like %(txt)s" for field in so_searchfield])

	soi_searchfield = frappe.get_meta("Sales Order Item").get_search_fields()
	soi_searchfield += ["item_code"]
	soi_searchfields = " or ".join(["soi.`" + field + "` like %(txt)s" for field in soi_searchfield])

	searchfield = so_searchfields + " or " + soi_searchfields

	return frappe.db.sql("""select so.name, so.status, so.transaction_date, so.customer, soi.item_code
			from `tabSales Order` so
		RIGHT JOIN `tabSales Order Item` soi ON (so.name = soi.parent)
		where so.docstatus = 1
			and so.status != "Closed"
			and so.customer = %(customer)s
			and ({searchfield})
		order by
			if(locate(%(_txt)s, so.name), locate(%(_txt)s, so.name), 99999)
		limit %(start)s, %(page_len)s """.format(searchfield=searchfield), {
			'txt': '%%%s%%' % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
			'customer': filters.get('customer')
		})

# @frappe.whitelist()
# def update_item_price(item, price_list, per_unit_price):
	
	# if db.exists("Item Price",{"item_code":item,"price_list":price_list}):
		# name = db.get_value("Item Price",{"item_code":item,"price_list":price_list},'name')
		# db.set_value("Item Price",name,"price_list_rate", per_unit_price)	
	# else:
		# item_price = frappe.new_doc("Item Price")
		# item_price.price_list = price_list
		# item_price.item_code = item
		# item_price.price_list_rate = per_unit_price
	
		# item_price.save()
	# db.commit()
		
	# return ["Item Price Updated!",per_unit_price]

# @frappe.whitelist()
# def update_bom_price(bom):
	# doc = frappe.get_doc("BOM",bom)
	# operating_cost = flt(doc.volume_quantity * doc.volume_rate)
	# doc.db_set("total_cost",doc.raw_material_cost + doc.total_operational_cost + operating_cost - doc.scrap_material_cost )
	# doc.db_set('per_unit_price',flt(doc.total_cost) / flt(doc.quantity))
	# doc.db_set('operating_cost', operating_cost)
	# doc.save()
	# update_item_price(doc.item, doc.buying_price_list, doc.per_unit_price)
	
# @frappe.whitelist()	
# def update_item_price_daily():
	# data = db.sql("""
		# select 
			# item, per_unit_price , buying_price_list
		# from
			# `tabBOM` 
		# where 
			# docstatus < 2 
			# and is_default = 1 """,as_dict =1)
			
	# for row in data:
		# update_item_price(row.item, row.buying_price_list, row.per_unit_price)
		
	# return "Latest price updated in Price List."

def get_batch_no(doctype, txt, searchfield, start, page_len, filters):
	cond = ""

	meta = frappe.get_meta("Batch")
	searchfield = meta.get_search_fields()

	searchfields = " or ".join(["batch." + field + " like %(txt)s" for field in searchfield])

	if filters.get("posting_date"):
		cond = "and (batch.expiry_date is null or batch.expiry_date >= %(posting_date)s)"

	batch_nos = None
	args = {
		'item_code': filters.get("item_code"),
		'warehouse': filters.get("warehouse"),
		'posting_date': filters.get('posting_date'),
		'txt': "%{0}%".format(txt),
		"start": start,
		"page_len": page_len
	}

	if args.get('warehouse'):
		batch_nos = frappe.db.sql("""select sle.batch_no, batch.lot_no, round(sum(sle.actual_qty),2), sle.stock_uom
				from `tabStock Ledger Entry` sle
					INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
				where
					sle.item_code = %(item_code)s
					and sle.warehouse = %(warehouse)s
					and batch.docstatus < 2
					and (sle.batch_no like %(txt)s or {searchfields})
					{0}
					{match_conditions}
				group by batch_no having sum(sle.actual_qty) > 0
				order by batch.expiry_date, sle.batch_no desc
				limit %(start)s, %(page_len)s""".format(cond, match_conditions=get_match_cond(doctype), searchfields=searchfields), args)

	if batch_nos:
		return batch_nos
	else:
		return frappe.db.sql("""select name, lot_no, expiry_date from `tabBatch` batch
			where item = %(item_code)s
			and name like %(txt)s
			and docstatus < 2
			{0}
			{match_conditions}
			order by expiry_date, name desc
			limit %(start)s, %(page_len)s""".format(cond, match_conditions=get_match_cond(doctype)), args)


@frappe.whitelist()
def get_outward_sample_batch_no(doctype, txt, searchfield, start, page_len, filters, as_dict):
	return frappe.db.sql("""
	SELECT 
			name
	FROM
			`tabBatch`
	WHERE
			item = '{0}' """.format(filters.get("item_name")))