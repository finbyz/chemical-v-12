frappe.ui.form.on("BOM", {
    before_save: function (frm) {
        let unit_qty = flt(frm.doc.total_cost / frm.doc.quantity);
        frm.set_value("per_unit_price", unit_qty);
		frm.set_value('etp_amount',flt(frm.doc.etp_qty*frm.doc.etp_rate))
		let amount = 0
		frm.doc.items.forEach(function (d) {
            amount += d.amount
        });
        frm.set_value("additional_amount", amount);
		frm.trigger('second_item_qty_cal');
		if(frm.doc.is_multiple_item){
			frm.set_value('qty_ratio_of_second_item',flt(100 - frm.doc.qty_ratio_of_first_item))
			frm.set_value('cost_ratio_of_second_item',flt(100 - frm.doc.cost_ratio_of_first_item))				
		}
    },
    onload: function (frm) {
		if(frm.doc.is_multiple_item){
			cur_frm.set_df_property("quantity", "read_only",1);
		}
        if (frm.doc.__islocal && frm.doc.rm_cost_as_per == "Price List") {
            frm.set_value("buying_price_list", "Standard Buying");
        }
    },
	is_multiple_item: function(frm){
		if(frm.doc.is_multiple_item){
			cur_frm.set_df_property("quantity", "read_only",1);
			cur_frm.set_df_property("quantity", "label",'First Item Quantity');
		}
		if(!frm.doc.is_multiple_item){
			cur_frm.set_df_property("quantity", "read_only",0);
			cur_frm.set_df_property("quantity", "label",'Quantity');
		}
	},
	cost_ratio_of_first_item:function(frm){
		if(frm.doc.is_multiple_item){ 
			frm.set_value('cost_ratio_of_second_item',flt(100 - frm.doc.cost_ratio_of_first_item))		
		}
	},
	qty_ratio_of_first_item:function(frm){
		if(frm.doc.is_multiple_item){
			frm.set_value('qty_ratio_of_second_item',flt(100 - frm.doc.qty_ratio_of_first_item))		
		}
	},
	second_item_qty_cal: function(frm){
		if(frm.doc.is_multiple_item){
			frm.set_value('second_item_qty',flt(frm.doc.total_quantity - frm.doc.quantity))
		}
	},
    /* cal_operational_cost: function (frm) {
        let op_cost = flt(frm.doc.operational_cost * frm.doc.quantity);
        let total_cost = flt(op_cost + frm.doc.total_cost)
        frm.set_value("total_operational_cost", flt(op_cost));
        frm.set_value("total_cost", total_cost);
        frm.set_value("per_unit_price", flt(total_cost / frm.doc.quantity));
    }, */

    /* operational_cost: function (frm) {
        frm.set_value("total_operational_cost", flt(frm.doc.operational_cost * frm.doc.quantity));
    }, */

    total_operational_cost: function (frm) {
        frm.set_value("total_cost", flt(frm.doc.additional_amount + frm.doc.raw_material_cost + frm.doc.volume_amount + frm.doc.etp_amount - frm.doc.scrap_material_cost));
    },

    total_cost: function (frm) {
        frm.set_value("per_unit_price", flt(frm.doc.total_cost / frm.doc.quantity));
    },

    // refresh: function(frm){
    // 	if(!frm.doc.__islocal){
    // 		frm.add_custom_button(__("Update Price List"), function() {
    // 			frm.events.update_price_list(frm);
    // 		});
    // 	}
    // },

    before_submit: function (frm) {
        let cal_yield = 0;
        frm.doc.items.forEach(function (d) {
            if (frm.doc.based_on == d.item_code) {
                cal_yield = frm.doc.quantity / d.qty;
            }
            else if (!frm.doc.based_on && d.item_code == "Vinyl Sulphone (V.S)") {
                cal_yield = frm.doc.quantity / d.qty;
            }
        });
        frm.set_value("batch_yield", cal_yield);
    },

    update_price_list: function (frm) {
        frappe.call({
            method: "chemical.api.upadte_item_price",
            args: {
                docname: frm.doc.name,
                item: frm.doc.item,
                price_list: frm.doc.buying_price_list,
                per_unit_price: frm.doc.per_unit_price
            },
            callback: function (r) {
                frappe.msgprint(r.message);
                frm.reload_doc();
            }
        });
    },
	/* refresh: function(frm){
		if(!frm.doc.__islocal){
			frm.add_custom_button(__("Update Price List"), function() {
				frappe.call({
					method:"chemical.api.upadte_item_price",
					args:{
						docname: frm.doc.name,
						item: frm.doc.item,
						price_list: frm.doc.buying_price_list,
						per_unit_price: frm.doc.per_unit_price
					},
					callback: function(r){
						frappe.msgprint(r.message);
						refresh_field("items");
					}
				});
			});
		}
	}, */
    update_cost: function (frm) {
        return frappe.call({
            doc: frm.doc,
            method: "update_cost",
            freeze: true,
            args: {
                update_parent: true,
                from_child_bom: false,
                save: true
            },
            callback: function (r) {
                frm.events.update_price_list(frm);
                if (!r.exc) frm.refresh_fields();
            }
        });
    },
	etp_qty: function(frm){
		frm.set_value('etp_amount',flt(frm.doc.etp_qty*frm.doc.etp_rate))
	},
	etp_rate: function(frm){
		frm.set_value('etp_amount',flt(frm.doc.etp_qty*frm.doc.etp_rate))
	}
});
frappe.ui.form.on("BOM Additional Cost", {
	/* qty: function(frm, cdt, cdn){
		let d = locals[cdt][cdn]
		frappe.model.set_value(d.doctype,d.name,'amount',flt(d.qty*d.rate))
	}, */
	rate: function(frm, cdt, cdn){
		let d = locals[cdt][cdn]
		frappe.model.set_value(d.doctype,d.name,'amount',flt(frm.doc.quantity*d.rate))
	}
});