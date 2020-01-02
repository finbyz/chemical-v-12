frappe.ui.form.on('Address', {
	gst_state: function(frm){
		frm.set_value('state',frm.doc.gst_state)
	},

});
