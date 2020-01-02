// Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

cur_frm.add_fetch("sample_ref", "product_name", "item");
cur_frm.add_fetch("sample_ref", "total_qty", "quantity");
cur_frm.add_fetch("sample_ref", "ref_no", "ref_no");
cur_frm.add_fetch("sample_ref", "batch_size", "pss_qty");
cur_frm.add_fetch("sample_ref", "po_no", "po_no");
cur_frm.add_fetch("sample_ref", "supply_site", "supply_site");

cur_frm.fields_dict.sample_items.grid.get_field("sample_ref").get_query = function (doc) {
	return {
		filters: {
			"party": doc.party,
		}
	}
};

//Contact Filter
cur_frm.set_query("contact_person", function () {
	if (cur_frm.doc.link_to == "Customer") {
		return {
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Customer", link_name: cur_frm.doc.party }
		};
	}
	else if (cur_frm.doc.link_to == "Supplier") {
		return {
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Supplier", link_name: cur_frm.doc.party }
		};
	}
	else {
		return {
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Lead", link_name: cur_frm.doc.party }
		};
	}
});

//Company Address filter
cur_frm.set_query("company_address", function (doc) {
	if (doc.company == undefined) {
		frappe.msgprint("Please select the Company");
	}
	else {
		return {
			query: "frappe.contacts.doctype.address.address.address_query",
			filters: { link_doctype: "Company", link_name: cur_frm.doc.company }
		};
	}
});

cur_frm.set_query("address_link", function () {
	if (cur_frm.doc.link_to == "Customer") {
		return {
			query: "frappe.contacts.doctype.address.address.address_query",
			filters: { link_doctype: "Customer", link_name: cur_frm.doc.party }
		};
	}
	else if (cur_frm.doc.link_to == "Supplier") {
		return {
			query: "frappe.contacts.doctype.address.address.address_query",
			filters: { link_doctype: "Supplier", link_name: cur_frm.doc.party }
		};
	}
	else {
		return {
			query: "frappe.contacts.doctype.address.address.address_query",
			filters: { link_doctype: "Lead", link_name: cur_frm.doc.party }
		};
	}
});

//Get Contact updated in Outward Tracking
frappe.ui.form.on('Outward Tracking', {
	link_to: function (frm) {
		frm.set_value('party', '')
	},
	party: function (frm) {
		if (frm.doc.party && frm.doc.link_to) {
			frappe.call({
				method: "chemical.api.get_party_details",
				args: {
					party: frm.doc.party,
					party_type: frm.doc.link_to
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value('contact_person', r.message.contact_person)
						frm.set_value('contact_display', r.message.contact_display)
						frm.set_value('contact_mobile', r.message.contact_mobile)
						frm.set_value('contact_email', r.message.contact_email)
						frm.set_value('address', r.message.address_display)
						frm.set_value('party_name', r.message.party_name)
						if (frm.doc.link_to == "Customer") {
							frm.set_value('address_link', r.message.customer_address)
						}
						else if (frm.doc.link_to == "Supplier") {
							frm.set_value('address_link', r.message.supplier_address)
						}
						else {
							frm.set_value('address_link', r.message.lead_address)
						}
					}
				}
			});
		}
	},
	address_link: function (frm) {
		if (frm.doc.address_link) {
			return frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					"address_dict": frm.doc.address_link
				},
				callback: function (r) {
					if (r.message)
						frm.set_value("address", r.message);
				}
			});
		}
	},
	before_save: function (frm) {
		let total_qty = 0.0;
		let total_amount = 0.0;
		
		if (frm.doc.has_sample) { 
			frm.doc.sample_items.forEach(function (d) {
				total_qty += flt(d.quantity);
				total_amount += flt(d.amount);
			});
		}
		frm.set_value("total_qty", total_qty);
		frm.set_value("total_amount", total_amount);
	},
	onload: function (frm) {
		var company_name = "";
		company_name = frappe.defaults.get_user_default("Company");
		frm.set_value("company", company_name);
	}
});
