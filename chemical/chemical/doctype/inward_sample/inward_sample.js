// Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt
//fetch territory from party.
// cur_frm.add_fetch("party", "territory", "destination");

frappe.ui.form.on('Inward Sample', {
	party: function (frm) {
		if (frm.doc.party) {
			frm.trigger("get_party_details");
		}
	},
	onload: function (frm) {
		if (frm.doc.party) {
			frm.trigger("get_party_details");
		}
		frm.set_query("party", function () {
			if (frm.doc.link_to == 'Customer') {
				return {
					query: "chemical.query.new_customer_query",
				}
			}
			else if (frm.doc.link_to == 'Supplier') {
				return {
					query: "chemical.query.new_supplier_query",

				}
			}
		});
	},
	get_party_details: function (frm) {
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
	update_pricelist_rate: function (frm) {
		if (frm.doc.item_code && frm.doc.item_price) {
			frappe.call({
				method: "chemical.query.upadte_item_price",
				args: {
					item: frm.doc.item_code,
					price_list: frm.doc.price_list || 'Standard Buying',
					per_unit_price: frm.doc.item_price
				},
				callback: function (r) {
					frappe.msgprint(r.message);
				}
			})
		}
		else {
			frappe.msgprint("Item Code or Item Price not found for updating Item price.");
		}
	},
	outward_reference: function (frm) {
		if (!frm.doc.outward_reference) {
			frm.set_value('outward_ref_no', '');
		}
	},
});
