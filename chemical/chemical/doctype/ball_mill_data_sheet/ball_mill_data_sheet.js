// Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

cur_frm.add_fetch("batch_no", "concentration", "concentration");
cur_frm.fields_dict.product_name.get_query = function(doc) {
	return {
		filters: {
			"item_group": 'Finished Products'
		}
	}
};
cur_frm.fields_dict.default_source_warehouse.get_query = function(doc) {
	return {
		filters: {
			"is_group": 0
		}
	}
};
cur_frm.fields_dict.items.grid.get_field("source_warehouse").get_query = function(doc) {
	return {
		filters: {
		  	"is_group": 0
		}
	};
};
// cur_frm.fields_dict.sample_no.get_query = function(doc) {
// 	return {
// 		filters: {
// 			"product_name": doc.product_name,
// 			"party": doc.customer_name 
// 		}
// 	}
// };
// cur_frm.fields_dict.sales_order.get_query = function(doc) {
// 	console.log("call")
// 	return {	
// 		filters: {
// 			'docstatus':1,
//             // "product_name": doc.product_name,
//             "customer":doc.customer_name,
// 		}
// 	}
// };

// this.frm.cscript.onload = function(frm) {
// 	this.frm.set_query("sales_order",function(doc) {
// 		console.log("call",doc)
// 		return{
// 						query:"chemical.chemical.doctype.ball_mill_data_sheet.ball_mill_data_sheet.get_sales_order",
// 						filters:{
// 							'doc':doc,
// 							'docstatus':doc.docstatus,
// 							// 'customer':doc.customer_name
// 						}
// 			}
// 	});
// }

this.frm.cscript.onload = function(frm) {
	this.frm.set_query("batch_no", "items", function(doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if(!d.item_name){
			frappe.msgprint(__("Please select Item"));
		}
		else if(!d.source_warehouse){
			frappe.msgprint(__("Please select source warehouse"));
		}
		else{
			return {
				query: "chemical.batch_valuation.get_batch",
				filters: {
					'item_code': d.item_name,
					'warehouse': d.source_warehouse
				}
			}
		}
	});
	this.frm.set_query("sales_order",function(doc) {
		return{
						query:"chemical.chemical.doctype.ball_mill_data_sheet.ball_mill_data_sheet.get_sales_order",
						filters:{
							'customer_name':doc.customer_name,	
							'product_name':doc.product_name
						}
			}
	});
}
function get_qty(frm) {
	if(flt(frm.doc.target_qty) != 0 && frm.doc.sales_order){
		frappe.model.with_doc("Outward Sample", frm.doc.sample_no, function() {
			var os_doc = frappe.model.get_doc("Outward Sample", frm.doc.sample_no)
			console.log("os_doc",os_doc.total_qty);
			$.each(os_doc.details, function(index, row){
				let d = frm.add_child("items");
				d.item_name = row.item_name;
				d.source_warehouse = frm.doc.default_source_warehouse;
				d.quantity = flt(flt(frm.doc.target_qty * row.quantity) / os_doc.total_qty);
				d.required_quantity = flt(flt(frm.doc.target_qty * row.quantity) / os_doc.total_qty);
			})
		});
	}
	// return 
  }

frappe.ui.form.on('Ball Mill Data Sheet', {
	refresh: function(frm){
		if(frm.doc.docstatus == 1){
			frm.add_custom_button(__("Outward Sample"), function() {
				frappe.model.open_mapped_doc({
					method : "chemical.chemical.doctype.ball_mill_data_sheet.ball_mill_data_sheet.make_outward_sample",
					frm : cur_frm
				})
			}, __("Make"));
		}
	},
	sales_order:function(frm){
		if(!frm.doc.sales_order || frm.doc.sales_order == undefined ){
			frm.set_value('sample_no','')
			frm.set_value('lot_no','')
			return false;
		}

		frappe.call({
			method : "chemical.chemical.doctype.ball_mill_data_sheet.ball_mill_data_sheet.get_sample_no",
			args:{
				parent:frm.doc.sales_order,	
			   	item_code:frm.doc.product_name,
			},
			callback: function(r) {
				if(!r.exc){
					frm.set_value('sample_no',r.message)
				}
			}
		});
		
	},
	product_name: function(frm) {
		console.log("call pr");
		frm.set_value('sales_order','')
		frm.set_value('sample_no','')
       
	},
	sample_no:function(frm){
		frm.set_value('items',[])
		get_qty(frm);
		frm.refresh_field("items");
	},
	target_qty:function(frm){
		frm.set_value('items',[])
		get_qty(frm);
		frm.refresh_field("items");
	},
	default_source_warehouse:function(frm){

		frm.doc.items.forEach(function(d) {
			d.source_warehouse = frm.doc.default_source_warehouse;
		});
		frm.refresh_field("items");
	}	
});

frappe.ui.form.on('Ball Mill Data Sheet Item', {
	items_add: function(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if(!row.source_warehouse && row.source_warehouse == undefined){
		 row.source_warehouse = cur_frm.doc.default_source_warehouse;
		 frm.refresh_field("items");
		}
	},
	
});
