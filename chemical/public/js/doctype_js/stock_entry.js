
// this.frm.add_fetch('batch_no', 'lot_no', 'lot_no');
// this.frm.add_fetch('batch_no', 'packaging_material', 'packaging_material');
// this.frm.add_fetch('batch_no', 'packing_size', 'packing_size');
// this.frm.add_fetch('batch_no', 'batch_yield', 'batch_yield');
// this.frm.add_fetch('batch_no', 'concentration', 'concentration');
// this.frm.add_fetch('item_code', 'item_group', 'item_group');

// Add searchfield to Item query
this.frm.cscript.onload = function (frm) {
    this.frm.set_query("batch_no", "items", function (doc, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (!d.item_code) {
            frappe.msgprint(__("Please select Item Code"));
        }
        else if (!d.s_warehouse) {
            frappe.msgprint(__("Please select source warehouse"));
        }
        else {
            return {
                query: "chemical.query.get_batch_no",
                filters: {
                    'item_code': d.item_code,
                    'warehouse': d.s_warehouse
                }
            }
        }
    });
}

frappe.ui.form.on("Stock Entry", {
	onload: function(frm){
		/* if(frm.doc.from_bom){
			frappe.db.get_value("BOM",frm.doc.bom_no,['etp_rate','volume_rate'],function(r){
				if(!frm.doc.etp_rate){
					frm.set_value('etp_rate',r.etp_rate);
				}
				if(!frm.doc.volume_rate){
					frm.set_value('volume_rate',r.volume_rate);
				}
			});
		} */
		if(frm.doc.work_order){
			frappe.db.get_value("Work Order", frm.doc.work_order, 'skip_transfer', function (r) {
				if (r.skip_transfer == 1) {
					cur_frm.set_df_property("get_raw_materials", "hidden", 0);
				}
			});
		}
	},
    // validate: function (frm) {
    //     if (frm.doc.__islocal) {
    //         frm.events.get_raw_materials(frm);
    //     }
    // },
    before_save: function (frm) {
        frm.trigger('cal_qty');
        if (frm.doc.volume) {
            let cost = flt(frm.doc.volume * frm.doc.volume_rate);
            frm.set_value('volume_cost', cost);
        }
        frappe.db.get_value("Company", frm.doc.company, 'abbr', function (r) {
            if (frm.doc.is_opening == "Yes") {
                $.each(frm.doc.items || [], function (i, d) {
                    d.expense_account = 'Temporary Opening - ' + r.abbr;
                });
            }
        });
       /*  if (frm.doc.purpose == "Manufacture" && frm.doc.work_order) {
            if ((frm.doc.additional_costs.length == 0 || frm.doc.additional_costs == undefined) && frm.doc.volume > 0) {
                var m = frm.add_child("additional_costs");
                m.description = "Spray Drying Cost";
                m.amount = frm.doc.volume_cost;
            }
        } */
        if (frm.doc.purpose == "Manufacture" && frm.doc.work_order) {
            frm.call({
                method: 'get_stock_and_rate',
                doc: frm.doc
            });
        }
    },
    set_basic_rate: function (frm, cdt, cdn) {
        const item = locals[cdt][cdn];
        if (item.t_warehouse) {
            return
        }
        item.transfer_qty = flt(item.qty) * flt(item.conversion_factor);

        let batch = '';
        if (!item.t_warehouse) {
            batch = item.batch_no;
        }

        const args = {
            'item_code': item.item_code,
            'posting_date': frm.doc.posting_date,
            'posting_time': frm.doc.posting_time,
            'warehouse': cstr(item.s_warehouse) || cstr(item.t_warehouse),
            'serial_no': item.serial_no,
            'company': frm.doc.company,
            'qty': item.s_warehouse ? -1 * flt(item.transfer_qty) : flt(item.transfer_qty),
            'voucher_type': frm.doc.doctype,
            'voucher_no': item.name,
            'allow_zero_valuation': 1,
            'batch_no': batch || ''
        };

        if (item.item_code || item.serial_no) {
            frappe.call({
                method: "erpnext.stock.utils.get_incoming_rate",
                args: {
                    args: args
                },
                callback: function (r) {
                    frappe.model.set_value(cdt, cdn, 'basic_rate', (r.message || 0.0));
                    frm.events.calculate_basic_amount(frm, item);
                }
            });
        }
    },
    // get_raw_materials: function (frm) {
    //     if (frm.doc.purpose == 'Manufacture' && frm.doc.work_order) {
    //         frappe.call({
    //             method: "chemical.chemical.doctype.material_transfer_instruction.material_transfer_instruction.get_raw_materials",
    //             args: {
    //                 work_order: frm.doc.work_order,
    //             },
    //             callback: function (r) {
    //                 if (r.message) {
    //                     let last_item = frm.doc.items[frm.doc.items.length - 1];
    //                     frm.clear_table('items');
    //                     r.message.forEach(function (d) {
    //                         let item_child = frm.add_child('items');
    //                         for (var key in d) {
    //                             item_child[key] = d[key];
    //                         }
    //                     });
    //                     let item_child = frm.add_child('items');
    //                     for (var key in last_item) {
    //                         if (!in_list(['idx', 'name'], key)) {
    //                             item_child[key] = last_item[key];
    //                         }
    //                     }
    //                     // item_child = last_item;
    //                     frm.refresh_field('items');

    //                     frm.call({
    //                         method: 'get_stock_and_rate',
    //                         doc: frm.doc
    //                     })
    //                 }
    //             }
    //         })
    //     }
    // },
    volume_rate: function (frm) {
        let cost = flt(frm.doc.volume * frm.doc.volume_rate);
        frm.set_value('volume_cost', cost);
    },
    volume: function (frm) {
        let cost = flt(frm.doc.volume * frm.doc.volume_rate);
        frm.set_value('volume_cost', cost);
    },
	etp_qty: function(frm){
		frm.set_value('volume_amount',flt(frm.doc.etp_qty*frm.doc.etp_rate))
	},
	etp_rate: function(frm){
		frm.set_value('volume_amount',flt(frm.doc.etp_qty*frm.doc.etp_rate))
	},
    cal_qty: function (frm) {
        let qty = 0;
        frm.doc.items.forEach(function (d) {
            if (d.batch_no) {
                frappe.db.get_value("Batch", d.batch_no, ['packaging_material', 'packing_size', 'lot_no', 'batch_yield', 'concentration'], function (r) {
                    frappe.model.set_value(d.doctype, d.name, 'packaging_material', r.packaging_material);
                    frappe.model.set_value(d.doctype, d.name, 'packing_size', r.packing_size);
                    frappe.model.set_value(d.doctype, d.name, 'lot_no', r.lot_no);
                    frappe.model.set_value(d.doctype, d.name, 'batch_yield', r.batch_yield);
                    frappe.model.set_value(d.doctype, d.name, 'concentration', r.concentration);
                })
            }
            // if (d.no_of_packages) {
            //     if (d.item_group == "Raw Material") {
            //         qty = (flt(d.packing_size) * flt(d.no_of_packages) * flt(d.concentration)) / 100;
            //     }
            //     else {
            //         qty = (flt(d.packing_size) * flt(d.no_of_packages));
            //     }
            //     frappe.model.set_value(d.doctype, d.name, "qty", qty);
            // }

        });
    },
});

frappe.ui.form.on("Stock Entry Detail", {
    form_render: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        var item_grid = frm.get_field('items').grid;
        let batch_no = item_grid.grid_rows[d.idx - 1].get_field('batch_no');
        if (!in_list(["Material Issue", "Material Transfer", "Material Transfer for Manufacture"], frm.doc.purpose)) {
            if (d.s_warehouse) {
                batch_no.df.read_only = 0;
            }
            else if (d.t_warehouse) {
                batch_no.df.read_only = 1;
            }
        }
        frm.refresh_field('items');
    },
    s_warehouse: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        var item_grid = frm.get_field('items').grid;
        let batch_no = item_grid.grid_rows[d.idx - 1].get_field('batch_no');
        if (!in_list(["Material Issue", "Material Transfer", "Material Transfer for Manufacture"], frm.doc.purpose)) {
            if (d.s_warehouse) {
                batch_no.df.read_only = 0;
            }
            else if (d.t_warehouse) {
                batch_no.df.read_only = 1;
            }
        }
        frm.refresh_field('items');
    },
    t_warehouse: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        var item_grid = frm.get_field('items').grid;
        let batch_no = item_grid.grid_rows[d.idx - 1].get_field('batch_no');
        if (!in_list(["Material Issue", "Material Transfer", "Material Transfer for Manufacture"], frm.doc.purpose)) {
            if (d.s_warehouse) {
                batch_no.df.read_only = 0;
            }
            else if (d.t_warehouse) {
                batch_no.df.read_only = 1;
            }
        }
        frm.refresh_field('items');
    },

    conversion_factor: function (frm, cdt, cdn) {
        frm.events.set_basic_rate(frm, cdt, cdn);
    },

    qty: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];

        frm.events.set_serial_no(frm, cdt, cdn, () => {
            frm.events.set_basic_rate(frm, cdt, cdn);
        });

        if (!d.s_warehouse && d.t_warehouse && d.bom_no == frm.doc.bom_no) {
            frm.set_value('fg_completed_qty', d.qty);
        }
    },
});

erpnext.stock.select_batch_and_serial_no = (frm, item) => {

}