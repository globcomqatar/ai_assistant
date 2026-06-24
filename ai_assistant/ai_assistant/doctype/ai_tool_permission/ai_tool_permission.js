// Copyright (c) 2026, Globcom Qatar and contributors
// AI Tool Permission — client script
// Adds live autocomplete on tool_name field using
// the Python TOOL_REGISTRY as the source of truth.

frappe.ui.form.on("AI Tool Permission", {

	onload(frm) {
		_setup_autocomplete(frm);
	},

	refresh(frm) {
		_setup_autocomplete(frm);

		// Show tool count hint in form header
		frappe.call({
			method: "ai_assistant.api.tools.get_tool_names",
			args: { txt: "" },
			callback(r) {
				if (r.message) {
					frm.set_intro(
						__("{0} tools available — type in Tool Name to search.", [
							r.message.length,
						]),
						"blue"
					);
				}
			},
		});
	},

	tool_name(frm) {
		const name = (frm.doc.tool_name || "").trim();
		if (!name) return;
		// Auto-fill description when tool_name is set manually
		frappe.call({
			method: "ai_assistant.api.tools.get_tool_description",
			args: { tool_name: name },
			callback(r) {
				if (r.message && !frm.doc.description) {
					frm.set_value("description", r.message);
				}
			},
		});
	},
});


function _setup_autocomplete(frm) {
	const field = frm.get_field("tool_name");
	if (!field || !field.$input) return;

	// Remove any previous listener to avoid duplicates
	field.$input.off("keyup.tool_ac input.tool_ac blur.tool_ac");

	let _all_tools = [];
	let _last_txt  = "";
	let _$drop     = null;

	// Cache the full tool list once on setup
	frappe.call({
		method: "ai_assistant.api.tools.get_tool_names",
		args: { txt: "" },
		callback(r) { _all_tools = r.message || []; },
	});

	field.$input.on("keyup.tool_ac input.tool_ac", function () {
		const txt = ($(this).val() || "").trim().toLowerCase();
		if (txt === _last_txt) return;
		_last_txt = txt;

		if (txt.length < 1) { _close(); return; }

		const matches = _all_tools
			.filter(t =>
				t.value.toLowerCase().includes(txt) ||
				(t.description || "").toLowerCase().includes(txt)
			)
			.slice(0, 12);

		matches.length ? _open(frm, field, matches) : _close();
	});

	field.$input.on("blur.tool_ac", () => setTimeout(_close, 200));


	function _open(frm, field, items) {
		_close();

		const $inp  = field.$input;
		const off   = $inp.offset();
		const scrollY = $(window).scrollTop();

		_$drop = $(`<div style="
			position:fixed;
			z-index:9999;
			top:${off.top + $inp.outerHeight() + scrollY}px;
			left:${off.left}px;
			width:${$inp.outerWidth()}px;
			background:var(--card-bg,#fff);
			border:1px solid var(--border-color,#e2e8f0);
			border-radius:8px;
			box-shadow:0 8px 24px rgba(0,0,0,.10);
			overflow:hidden;
			max-height:320px;
			overflow-y:auto;
		"></div>`).appendTo("body");

		items.forEach(item => {
			const cat = _category(item.value);
			const $row = $(`<div data-value="${item.value}" style="
				padding:8px 12px;
				cursor:pointer;
				border-bottom:1px solid var(--border-color,#f1f5f9);
				transition:background .1s;
			">
				<div style="display:flex;align-items:center;gap:8px">
					<span style="
						font-size:12px;font-weight:500;
						color:var(--text-color,#111);
						font-family:var(--font-mono,monospace);
					">${item.value}</span>
					<span style="
						font-size:10px;padding:1px 6px;
						border-radius:8px;flex-shrink:0;
						background:${cat.bg};color:${cat.fg};
					">${cat.label}</span>
				</div>
				${item.description ? `<div style="
					font-size:10.5px;color:var(--text-muted,#6b7280);
					margin-top:2px;white-space:nowrap;
					overflow:hidden;text-overflow:ellipsis;
				">${item.description.slice(0, 90)}${
					item.description.length > 90 ? "…" : ""
				}</div>` : ""}
			</div>`);

			$row
				.on("mouseenter", function () {
					$(this).css("background", "var(--fg-hover,#eff6ff)");
				})
				.on("mouseleave", function () {
					$(this).css("background", "");
				})
				.on("mousedown", function () {
					const val = $(this).data("value");

					// Set field value
					frm.set_value("tool_name", val);
					field.$input.val(val);

					// Auto-fill description
					frappe.call({
						method:
							"ai_assistant.api.tools.get_tool_description",
						args: { tool_name: val },
						callback(r) {
							if (r.message && !frm.doc.description) {
								frm.set_value("description", r.message);
							}
						},
					});

					_close();
				});

			_$drop.append($row);
		});
	}

	function _close() {
		if (_$drop) { _$drop.remove(); _$drop = null; }
	}

	function _category(name) {
		if (/^(create_|convert_|record_|generate_|close_|update_)/.test(name))
			return { label: "Write",  bg: "#fee2e2", fg: "#b91c1c" };
		if (/(trend|analysis|summary|pipeline|bridge|dashboard|360)/.test(name)
			|| /^analyze_/.test(name))
			return { label: "BI",     bg: "#dbeafe", fg: "#1e40af" };
		if (/^(search_|diagnose_)/.test(name))
			return { label: "Search", bg: "#fef3c7", fg: "#92400e" };
		if (/^get_/.test(name))
			return { label: "Read",   bg: "#dcfce7", fg: "#166534" };
		return   { label: "Tool",    bg: "#f1f5f9", fg: "#475569" };
	}
}
