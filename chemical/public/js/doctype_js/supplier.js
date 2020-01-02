frappe.ui.form.on("Supplier", {
	refresh: function(frm) {
        dashboard_link_doctype(frm, "Outward Sample");
        dashboard_link_doctype(frm, "Inward Sample");
	},
	onload_post_render: function(frm){
		if(frm.doc.alias && !frm.doc.__islocal && frm.doc.name != frm.doc.alias){
			frappe.call({
				method: "frappe.client.rename_doc",
				args: {
					'doctype': frm.doc.doctype,
					'old_name': frm.doc.name,
					'new_name': frm.doc.alias
				},
				callback: function(r){
					if(r.message){
						frappe.set_route('Form', 'Supplier', r.message)
					}
				}
			})
		}
	}
});

function dashboard_link_doctype(frm, doctype){

	var parent = $('.form-dashboard-wrapper [data-doctype="Pricing Rule"]').closest('div').parent();
	
	parent.find('[data-doctype="'+doctype+'"]').remove();
	
	parent.append(frappe.render_template("dashboard_link_doctype", {doctype:doctype}));
	
	var self = parent.find('[data-doctype="'+doctype+'"]');
	
	set_open_count(frm, doctype);
	
	// bind links
	self.find(".badge-link").on('click', function() {
		frappe.route_options = {"party": frm.doc.name}
		frappe.set_route("List", doctype);
	});
	
	// bind open notifications
	self.find('.open-notification').on('click', function() {
		frappe.route_options = {
			"pary": frm.doc.name,
			"status": "Draft"
		}
		frappe.set_route("List", doctype);
	});
	
	// bind new
	if(frappe.model.can_create(doctype)) {
		self.find('.btn-new').removeClass('hidden');
	}
	self.find('.btn-new').on('click', function() {
		frappe.new_doc(doctype,{
			"party": frm.doc.name,
			"link_to": "Supplier"
		});
	});
	}
function set_open_count(frm, doctype){

var method = '';
var links = {};


method = 'chemical.api.get_open_count';
links = {
	'fieldname': 'party',
	'transactions': [
		{
			'label': __('Outward Sample'),
			'items': ['Outward Sample']
		},
		{
			'label': __('Inward Sample'),
			'items': ['Inward Sample']
		},
	]
};

if(method!=""){
	frappe.call({
		type: "GET",
		method: method,
		args: {
			doctype: frm.doctype,
			name: frm.doc.name,
			links: links,
		},
		callback: function(r) {
			// update badges
			$.each(r.message.count, function(i, d) {
				frm.dashboard.set_badge_count(d.name, cint(d.open_count), cint(d.count));
			});
		}
	});
}
}

frappe.templates["dashboard_link_doctype"] = ' \
<div class="document-link" data-doctype="{{ doctype }}"> \
<a class="badge-link small">{{ __(doctype) }}</a> \
<span class="text-muted small count"></span> \
<span class="open-notification hidden" title="{{ __("Open {0}", [__(doctype)])}}"></span> \
	<button class="btn btn-new btn-default btn-xs hidden" data-doctype="{{ doctype }}"> \
			<i class="octicon octicon-plus" style="font-size: 12px;"></i> \
	</button>\
</div>';