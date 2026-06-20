frappe.ui.form.on("AI Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.show_alert({ message: __("Testing connection…"), indicator: "blue" });

			frappe.call({
				method: "ai_assistant.api.chat.test_connection",
				freeze: true,
				freeze_message: __("Contacting AI provider…"),
				callback(r) {
					if (!r.message) return;
					const d = r.message;

					if (d.status === "ok") {
						frappe.msgprint({
							title: __("Connection Successful ✅"),
							indicator: "green",
							message: `
								<b>Provider:</b> ${d.provider}<br>
								<b>Model:</b> ${d.model}<br>
								<b>Tokens used:</b> ${d.tokens}<br>
								<b>Cost:</b> $${(d.cost_usd || 0).toFixed(6)}<br><br>
								<b>Raw response:</b><br>
								<code style="word-break:break-all">${frappe.utils.escape_html(d.raw_response)}</code>
							`,
						});
					} else {
						frappe.msgprint({
							title: __("Connection Failed ❌"),
							indicator: "red",
							message: `<b>Error:</b><br><code>${frappe.utils.escape_html(d.error || "Unknown error")}</code>`,
						});
					}
				},
				error() {
					frappe.show_alert({ message: __("Test failed — check error logs."), indicator: "red" });
				},
			});
		}, __("Actions"));
	},
});
