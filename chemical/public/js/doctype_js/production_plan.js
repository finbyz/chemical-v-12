
frappe.ui.form.on("Production Plan", {
    refresh: function(frm){
        console.log("Production")
		frappe.call({
			method:"chemical.api.override_proplan_functions",
			callback: function(r) {
                refresh_field("sales_orders");
                refresh_field("po_items");
			}
		});
    },
    get_finish_item:function(frm){
        frm.set_value('finish_items',[])
        if(frm.doc.get_items_from == "Sales Order"){ 
            (frm.doc.sales_orders || []).forEach(function(d) {
                frappe.model.with_doc("Sales Order", d.sales_order, function() {
                    var so_doc = frappe.model.get_doc("Sales Order", d.sales_order)
                    $.each(so_doc.items, function(index, row){
                        let fi = frm.add_child("finish_items");
                        fi.item_code = row.item_code
                        fi.outward_sample = row.outward_sample
                        fi.quantity = row.qty
                        fi.sales_order = d.sales_order
                    })          
                    frm.refresh_field("finish_items");
                });      
            });
        }
        
    },
    get_items_from:function(frm){
        frm.set_value('finish_items',[])
        frm.set_value('po_items',[])
    }
    
});

// get_items_from_sample: function(frm){
	// 	frappe.call({
    //         method:"chemical.api.get_items_from_sample",
    //         args:{
    //             doc:frm.doc
    //         },
	// 		callback: function(r) {
    //             // console.log(r.items)
	// 			refresh_field("po_items");
	// 		}
	// 	});
    // },


   