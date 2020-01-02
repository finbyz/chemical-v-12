// Copyright (c) 2019, FinByz Tech Pvt. Ltd. and contributors
// For license information, please see license.txt

//fetch territory from party.
//cur_frm.add_fetch("party", "territory", "destination");

//fetch item name in child table.
cur_frm.add_fetch("inward_sample", "item_code", "item_name");
cur_frm.add_fetch("batch_no", "concentration", "concentration");

cur_frm.add_fetch("item_code", "item_name", "item_name");
cur_frm.add_fetch("item_code", "stock_uom", "uom");
cur_frm.add_fetch("item_code", "item_group", "item_group");

// Add searchfield to customer  and Supplier and item query
this.frm.cscript.onload = function (frm) {
	// this.frm.set_query("product_name", function () {
	// 	return {
	// 		query: "chemical.query.new_item_query",
	// 		filters: {
	// 			'is_sales_item': 1,
	// 			"item_group": "FINISHED DYES"
	// 		}
	// 	}
	// });
	this.frm.set_query("party", function (frm) {
		if (cur_frm.doc.link_to == 'Customer') {
			return {
				query: "chemical.query.new_customer_query",
			}
		}
		else if (cur_frm.doc.link_to == 'Supplier') {
			return {
				query: "chemical.query.new_supplier_query",
			}
		}

	});
	this.frm.set_query("sales_order", function () {
		return {
			query: "chemical.query.sales_order_query",
			filters: {
				"customer": cur_frm.doc.party
			}
		}
	});
	this.frm.set_query("batch_no", "details", function (doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (!d.item_name) {
			frappe.msgprint(__("Please select Item"));
		}
		else {
			return {
				query: "chemical.query.get_batch_no",
				filters: {
					'item_code': d.item_name,
				}
			}
		}
	});
	// this.frm.set_query("batch_no", "details", function(doc, cdt, cdn) {
	// 	let d = locals[cdt][cdn];
	// 	if(!d.item_name){
	// 		frappe.msgprint(__("Please select Item"));
	// 	}
	// 	else{
	// 		return {
	// 			query: "chemical.query.get_outward_sample_batch_no",
	// 			filters: {
	// 				'item_name': d.item_name,
	// 			}
	// 		}
	// 	}
	// });
}

frappe.ui.form.on('Outward Sample', {
	before_save: function (frm) {
		frm.trigger("cal_total_qty");
		frm.trigger("cal_yield");
		frm.trigger("cal_rate");
		frm.trigger("cal_amount");
		frm.trigger("cal_per_unit_price");
		if (frm.doc.link_to == 'Customer') {
			frappe.call({
				method: 'chemical.api.get_customer_ref_code',
				args: {
					'item_code': frm.doc.product_name,
					'customer': frm.doc.party,
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value('item_name', r.message);
					}
				}
			})
		}
		if (frm.doc.link_to == 'Supplier') {
			frappe.call({
				method: 'chemical.api.get_supplier_ref_code',
				args: {
					'item_code': frm.doc.product_name,
					'supplier': frm.doc.party
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value('item_name', r.message);
					}
				}
			})

		}

	},
	update_price: function (frm) {
		frm.call({
			method: "update_outward_sample",
			doc: frm.doc,
			args: {
				doc_name: frm.doc.name
			},
			callback: function (r) {
				frm.refresh();
				if (r.message) {
					frappe.msgprint(r.message);
					frm.refresh_field('details');
					cur_frm.reload_doc();
				}
			}
		});
	},
	sample_type: function (frm) {
		if (frm.doc.sample_type == "Post Shipment Sample") {
			frm.set_value("status", '');
		}
	},
	total_amount: function (frm) {
		frm.trigger("cal_per_unit_price");
	},
	party: function (frm) {
		frappe.call({
			method: "chemical.api.get_party_details",
			args: {
				party: frm.doc.party,
				party_type: frm.doc.link_to
			},
			callback: function (r) {
				if (r.message) {
					frm.set_value('party_name', r.message.party_name);
				}
			}
		});
		frm.set_value("party_alias", frm.doc.party)
	},
	cal_total_qty: function (frm) {
		let total_qty = 0.0;
		let total_amount = 0.0;
		frm.doc.details.forEach(function (d) {
			total_qty += flt(d.quantity);
			total_amount += flt(d.amount);
		});
		frm.set_value("total_qty", total_qty);
		frm.set_value("total_amount", total_amount);
	},
	cal_per_unit_price: function (frm) {
		let per_unit = 0.0;
		per_unit = flt(frm.doc.total_amount) / flt(frm.doc.total_qty);
		frm.set_value("per_unit_price", per_unit);
	},
	cal_yield: function (frm) {
		let yield_1 = 0;
		frm.doc.details.forEach(function (d) {
			if (d.concentration) {
				frappe.db.get_value("BOM", { 'item': d.item_code }, 'batch_yield', function (r) {
					if (r) {
						if (r.batch_yield != 0) {
							yield_1 = flt(r.batch_yield * 100 / d.concentration);
						}
						else {
							yield_1 = 2.2;
						}
						frappe.model.set_value(d.doctype, d.name, 'batch_yield', yield_1);
					}
				});
			}
			else {
				frappe.model.set_value(d.doctype, d.name, 'batch_yield', 0);
			}
		});
	},
	cal_rate: function (frm) {
		let rate = 0;
		let yield_1 = 0;
		frm.doc.details.forEach(function (d) {
			if (d.batch_yield) {
				frappe.db.get_value("BOM", { 'item': d.item_code }, 'batch_yield', function (r) {
					if (r.batch_yield != 0) {
						rate = ((d.price_list_rate * r.batch_yield) / d.batch_yield);
					}
					else {
						yield_1 = 2.2;
						rate = ((d.price_list_rate * 2.2) / d.batch_yield);
					}
					frappe.model.set_value(d.doctype, d.name, 'rate', rate);
				});
			}
			else {
				frappe.model.set_value(d.doctype, d.name, 'rate', d.price_list_rate);
			}
		});
	},
	cal_amount: function (frm) {
		frm.doc.details.forEach(function (d) {
			let amount = flt(d.quantity * d.rate);
			frappe.model.set_value(d.doctype, d.name, 'amount', amount);
		});
	},

	refresh: function (frm) {
		if (!frm.doc.__is_local) {
			frm.add_custom_button(__("Quotation"), function () {
				frappe.model.open_mapped_doc({
					method: "chemical.chemical.doctype.outward_sample.outward_sample.make_quotation",
					frm: cur_frm
				})
			}, __("Make"))
		}
	},
	address_name: function (frm) {
		if (frm.doc.address_name) {
			return frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					"address_dict": frm.doc.address_name
				},
				callback: function (r) {
					if (r.message)
						frm.set_value("address_display", r.message);
				}
			});
		}
	}
});

// calculate total_qty on quantity(field) in child table.
frappe.ui.form.on("Outward Sample Detail", {
	quantity: function (frm, cdt, cdn) {
		frm.events.cal_total_qty(frm);
		frm.events.cal_amount(frm);
	},
	batch_yield: function (frm, cdt, cdn) {
		frm.events.cal_rate(frm);
	},
	concentration: function (frm, cdt, cdn) {
		frm.events.cal_yield(frm);
	},
	rate: function (frm, cdt, cdn) {
		frm.events.cal_amount(frm);
	},
	amount: function (frm, cdt, cdn) {
		frm.events.cal_total_qty(frm);
	},
	item_code: function (frm, cdt, cdn) {
		var m = locals[cdt][cdn];
		if (m.item_code) {
			frm.call({
				method: "get_spare_price",
				doc: frm.doc,
				args: {
					item_code: m.item_code,
					price_list: frm.doc.price_list || 'Standard Buying',
					company: frm.doc.company
				},
				callback: function (r) {
					frappe.model.set_value(m.doctype, m.name, 'rate', r.message.price_list_rate);
					frappe.model.set_value(m.doctype, m.name, 'price_list_rate', r.message.price_list_rate);
					frm.events.cal_yield(frm);
				}
			});
		}
		
	},
});

