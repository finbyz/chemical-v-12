frappe.ui.form.on("BOM Update Tool", {
	update_latest_price_in_all_boms: function() {
		frappe.call({
			method: "erpnext.manufacturing.doctype.bom_update_tool.bom_update_tool.enqueue_update_cost",
			freeze: true,
			callback: function() {
				frm.events.update_price_list(frm);
			}
		});
	},

	update_price_list: function(frm){
		frappe.call({
			method:"chemical.api.update_item_price_daily",
			callback: function(r){
				frappe.msgprint(__("Latest price updated in all BOMs"));
				frm.reload_doc()
			}
		});
	}
});