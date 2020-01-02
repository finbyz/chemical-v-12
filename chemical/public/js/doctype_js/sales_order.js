frappe.ui.form.on("Sales Order", {
    before_save: function (frm) {
        frm.doc.items.forEach(function (d) {
            if (!d.item_code) {
                frappe.throw("Please Select the item")
            }

            frappe.call({
                method: 'chemical.api.get_customer_ref_code',
                args: {
                    'item_code': d.item_code,
                    'customer': frm.doc.customer,
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(d.doctype, d.name, 'item_name', r.message);
                    }
                }
            })
        });
        frm.refresh_field('items');
    },
    
});

cur_frm.fields_dict.items.grid.get_field("outward_sample").get_query = function(doc,cdt,cdn) {
    let d = locals[cdt][cdn];
    if(!d.item_code){
        frappe.throw(__("Please select Item Code first."))
    }
	return {
		filters: {
            'docstatus':1,
            "link_to":'Customer',
            "product_name": d.item_code,
            "party":doc.customer,
            
		}
	}
};

frappe.ui.form.on("Sales Order Item", {
    item_code: function(frm,cdt,cdn) {
        console.log("call");
        let d = locals[cdt][cdn];
        frappe.model.set_value(d.doctype, d.name, 'outward_sample', "");
		// frm.set_value('outward_sample',"")
		// refresh_field('items');
	}
});