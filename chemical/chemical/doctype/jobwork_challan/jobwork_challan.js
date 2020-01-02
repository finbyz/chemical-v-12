// Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

this.frm.add_fetch("item_code", "item_name", "item_name");
this.frm.add_fetch("item_code", "description", "description");
this.frm.add_fetch("item_code", "stock_uom", "stock_uom");
this.frm.add_fetch("batch_no", "packaging_material", "packaging_material");
this.frm.add_fetch("batch_no", "packing_size", "packing_size");
this.frm.add_fetch("batch_no", "valuation_rate", "rate");
this.frm.add_fetch("batch_no", "concentration", "concentration");
this.frm.add_fetch("batch_no", "batch_yield", "batch_yield");


this.frm.cscript.onload = function(frm) {
	//filter Job Worker address
	this.frm.set_query("address", function(doc) {
		if(doc.job_worker_and_consignee == undefined){
			frappe.msgprint("Please select the Job Worker");
		}
		else{
			return {
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: { link_doctype: "Supplier", link_name: cur_frm.doc.job_worker_and_consignee} 
			};
		}
	});
	
	//Job Worker contact filter
	this.frm.set_query('contact_person', function(doc) {
		if(doc.job_worker_and_consignee == undefined){
			frappe.msgprint("Please select the Job Worker");
		}
		else{
			return {
				query: "frappe.contacts.doctype.contact.contact.contact_query",
				filters: { link_doctype: "Supplier", link_name: cur_frm.doc.job_worker_and_consignee} 
			};
		}
	});
	this.frm.set_query("batch_no", "items", function(doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if(!d.item_code){
			frappe.msgprint(__("Please select Item Code"));
		}
		else{
			return {
				query: "chemical.batch_valuation.get_batch_no",
				filters: {
					'item_code': d.item_code,
					'warehouse': d.warehouse
				}
			}
		}
	});
}

frappe.ui.form.on("Jobwork Challan", {
	onload: function(frm){
		if(frm.doc.__islocal){
			frm.set_value("status",'Sent');
		}
	},
	setup: function(frm){
		frm.custom_make_buttons = {
			'Jobwork Finish': 'Receive Material'
		}

		frm.set_indicator_formatter('item_code',
			function(doc) {
				return (doc.docstatus==1 && doc.received_qty==doc.qty) ? "green" : "orange"
			})
	},
	refresh: function(frm) {
		if(frm.doc.docstatus == 1 && frm.doc.stock_entry && frm.doc.status != "Received") {
			frm.add_custom_button(__("Receive Material"), function() {
				frappe.model.open_mapped_doc({
                    method: "chemical.chemical.doctype.jobwork_challan.jobwork_challan.make_jobwork_finish",
					frm : cur_frm
				})
			})
		}
	},

	job_worker_and_consignee: function(frm) {
		frappe.call({
			method:"erpnext.accounts.party.get_party_details",
			args:{
				party: cur_frm.doc.job_worker_and_consignee,
				party_type: "Supplier"
			},
			callback: function(r){
				if(r.message){
					frm.set_value('address', r.message.supplier_address);
					frm.set_value('contact_person', r.message.contact_person);
					frm.set_value('contact_display', r.message.contact_display);
					frm.set_value('contact_mobile', r.message.contact_mobile);
					frm.set_value('contact_email', r.message.contact_email);
				}
			}
		})
	},

	address: function(frm){
		if(cur_frm.doc.address == undefined){
			frappe.msgprint("Please select the Job Worker");
		}
		else{
			return frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					"address_dict": cur_frm.doc.address
				},
				callback: function(r) {
					if(r.message)
						frm.set_value("address_display", r.message);
				}
			});
		}
	},
	
	cal_total:function(frm){
		let total_qty = 0.0;
		let total_amount = 0.0;

		frm.doc.items.forEach(function(d) {
			total_qty += flt(d.qty);
			total_amount += flt(d.net_amount);
		});	
		frm.set_value("total_qty",total_qty);
		frm.set_value("total_amount",total_amount);
	},
	
	material_received: function(frm){
		if(!frm.doc.received_stock_entry){
			frappe.prompt([{fieldtype:"Float", label: __("Received Qty for {0}", [frm.doc.finished_product]),fieldname:"quantity",reqd: 1},
				{fieldtype:"Date", label: __("Received Date"),fieldname:"date",reqd: 1}],
				function(data) {
					frappe.call({
						method: "return_stock_entry",
						doc: frm.doc,
						args:{
							qty: data.quantity,
							received_date: data.date
						},
						callback: function(r){
							frappe.msgprint(__("Material Received to {0}",[frm.doc.finished_product_warehouse]));
							frm.reload_doc();
						}
					})
				}, __("Select Quantity"), __("Make"));
		}
		else{
			frappe.msgprint(__("Material already received."))
		}
	}
});

frappe.ui.form.on("Job Work Item", {
	qty: function(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'net_amount', flt(d.qty * d.rate))
	},
	rate: function(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'net_amount', flt(d.qty * d.rate))
	},
	net_amount:function(frm, cdt ,cdn){
		frm.events.cal_total(frm);
	},
	packing_size: function(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'no_of_packages', Math.round(flt(d.qty / d.packing_size )))
	},
});