frappe.pages["ai-chat"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("AI Assistant"),
		single_column: true,
	});

	frappe.ai_chat = new AIChatPage(page, wrapper);
};

frappe.pages["ai-chat"].on_page_show = function (wrapper) {
	if (frappe.ai_chat) {
		frappe.ai_chat.on_show();
	}
};

// ──────────────────────────────────────────────────────────────────────────────
// AIChatPage class
// ──────────────────────────────────────────────────────────────────────────────

class AIChatPage {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.history = []; // [{role, content}]
		this.is_loading = false;

		this._check_settings_then_render();
	}

	on_show() {
		this.$input && this.$input.focus();
	}

	// ── Setup ──────────────────────────────────────────────────────────────────

	_check_settings_then_render() {
		frappe.call({
			method: "ai_assistant.api.chat.get_settings_status",
			callback: (r) => {
				if (r.message && r.message.enabled) {
					this._render();
					this._load_usage();
				} else {
					this._render_disabled();
				}
			},
			error: () => this._render_disabled(),
		});
	}

	_render_disabled() {
		$(this.wrapper).find(".page-content").html(`
			<div class="ai-disabled-notice">
				<div class="ai-disabled-icon">🤖</div>
				<h3>${__("AI Assistant is Disabled")}</h3>
				<p>${__("Please configure and enable AI Assistant in")}
				   <a href="/app/ai-settings">${__("AI Settings")}</a>.</p>
			</div>
		`);
	}

	_sidebar_groups() {
		return [
			{
				label: "📊 " + __("Business Intelligence"),
				items: [
					{ icon: "🧠", label: __("Business Analysis"),    msg: "Analyze my business and give me recommendations" },
					{ icon: "🌅", label: __("Daily Summary"),         msg: "Give me the management daily summary" },
					{ icon: "📈", label: __("Sales Trend"),           msg: "Show me the monthly sales trend for 6 months" },
					{ icon: "🏆", label: __("Top Customers"),         msg: "Show top customers this month" },
					{ icon: "🛍️", label: __("Top Selling Items"),    msg: "Show top selling items this month" },
				],
			},
			{
				label: "💰 " + __("Collections & AR"),
				items: [
					{ icon: "⚠️",  label: __("Overdue Invoices"),     msg: "Show overdue invoices" },
					{ icon: "🎯", label: __("Follow-Up List"),        msg: "Who needs follow-up? Show me follow-up opportunities" },
					{ icon: "💸", label: __("Overdue Customers"),     msg: "Show customers with overdue balance" },
					{ icon: "📄", label: __("Pending Quotations"),    msg: "Show pending quotations" },
				],
			},
			{
				label: "📦 " + __("Operations"),
				items: [
					{ icon: "📦", label: __("Stock Alerts"),          msg: "Show stock alerts and low stock items" },
					{ icon: "🔧", label: __("Open Job Cards"),        msg: "Show open workshop job cards" },
					{ icon: "💤", label: __("Inactive Customers"),    msg: "Show inactive customers in the last 60 days" },
				],
			},
			{
				label: "⚡ " + __("Quick Actions"),
				items: [
					{ icon: "👤", label: __("New Customer"),          msg: "Create customer " },
					{ icon: "📄", label: __("New Quotation"),         msg: "Create quotation for customer " },
					{ icon: "🔧", label: __("Diagnose Vehicle"),      msg: "Diagnose Toyota Camry 2020 with check engine light" },
				],
			},
		];
	}

	_render() {
		const sidebarHtml = this._sidebar_groups().map(group => `
			<div class="ai-sn-section">
				<div class="ai-sn-section-label">${group.label}</div>
				<div class="ai-sn-items">
					${group.items.map(item => `
						<button class="ai-sn-item" data-msg="${frappe.utils.escape_html(item.msg)}">
							<span class="ai-sn-ico">${item.icon}</span>
							<span class="ai-sn-lbl">${item.label}</span>
						</button>`).join("")}
				</div>
			</div>`).join("");

		const html = `
		<div class="ai-layout" id="ai-layout">

			<!-- Mobile sidebar backdrop -->
			<div class="ai-sb-backdrop hidden" id="ai-sb-backdrop"></div>

			<!-- ── Left Navigation Sidebar ── -->
			<div class="ai-sn" id="ai-sidebar">
				<header class="ai-sn-hdr">
					<div class="ai-sn-brand">
						<span class="ai-sn-brand-icon">⚡</span>
						<span class="ai-sn-brand-text">${__("Quick Actions")}</span>
					</div>
					<button class="ai-sn-close-btn" id="ai-sb-toggle" title="${__("Collapse sidebar")}">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="15 18 9 12 15 6"></polyline>
						</svg>
					</button>
				</header>
				<div class="ai-sn-scroll" id="ai-sb-body">
					${sidebarHtml}
				</div>
			</div><!-- end .ai-sn -->

			<!-- ── Chat Panel ── -->
			<div class="ai-chat-container">

				<!-- Header -->
				<div class="ai-chat-header">
					<div class="ai-chat-header-left">
						<button class="ai-sn-open-btn hidden" id="ai-sb-expand-btn" title="${__("Open Quick Actions")}">
							<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
								<line x1="3" y1="12" x2="21" y2="12"></line>
								<line x1="3" y1="6" x2="21" y2="6"></line>
								<line x1="3" y1="18" x2="21" y2="18"></line>
							</svg>
						</button>
						<span class="ai-avatar">🤖</span>
						<div>
							<div class="ai-chat-title">${__("AI Assistant")}</div>
							<div class="ai-chat-subtitle" id="ai-model-label">${__("Powered by ERPNext AI")}</div>
						</div>
					</div>
					<div class="ai-chat-header-right">
						<span class="ai-usage-badge" id="ai-usage-badge" title="${__("Monthly usage")}"></span>
						<button class="btn btn-xs btn-default" id="ai-clear-btn">
							<span class="ai-btn-icon">🗑</span>
							<span class="ai-btn-text">${__("Clear Chat")}</span>
						</button>
						<a href="/app/ai-settings" class="btn btn-xs btn-default">
							<span class="ai-btn-icon">⚙</span>
							<span class="ai-btn-text"> ${__("Settings")}</span>
						</a>
					</div>
				</div>

				<!-- Messages -->
				<div class="ai-messages" id="ai-messages">
					<div class="ai-welcome-msg">
						<div class="ai-welcome-icon">✨</div>
						<h4>${__("How can I help you today?")}</h4>
						<p>${__("Use the quick-action buttons on the left, or type your question below.")}</p>
					</div>
				</div>

				<!-- Typing indicator -->
				<div class="ai-typing-indicator hidden" id="ai-typing">
					<span></span><span></span><span></span>
				</div>

				<!-- Input area -->
				<div class="ai-input-area">
					<textarea id="ai-input" class="ai-input" rows="1"
						placeholder="${__("Type your message… (Enter to send, Shift+Enter for new line)")}"></textarea>
					<button class="ai-send-btn" id="ai-send-btn" disabled>
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="22" y1="2" x2="11" y2="13"></line>
							<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
						</svg>
					</button>
				</div>

			</div><!-- end .ai-chat-container -->
		</div><!-- end .ai-layout -->`;

		$(this.wrapper).find(".page-content").html(html);

		this.$messages = $("#ai-messages");
		this.$input    = $("#ai-input");
		this.$send     = $("#ai-send-btn");

		this._apply_layout();

		// Re-apply layout on window resize
		$(window).off("resize.ai_chat").on("resize.ai_chat", frappe.utils.debounce(() => {
			this._apply_layout();
		}, 200));

		this._bind_events();
	}

	_is_mobile()  { return window.innerWidth < 768; }
	_is_tablet()  { return window.innerWidth >= 768 && window.innerWidth < 1024; }
	_is_overlay() { return window.innerWidth < 1024; }

	_apply_layout() {
		const mobile  = this._is_mobile();
		const overlay = this._is_overlay();
		const $layout  = $("#ai-layout");
		const $sidebar = $("#ai-sidebar");
		const $chat    = $(".ai-chat-container");

		// Height: taller on mobile to use more screen real estate
		const layoutH = mobile ? "calc(100svh - 110px)" : "80vh";

		$layout.css({ position: "relative", width: "100%", height: layoutH, overflow: "hidden" });

		$sidebar.css({
			position: "absolute", top: 0, bottom: 0,
			width: "230px",
			background: "linear-gradient(180deg,#1e1b4b 0%,#2d2467 100%)",
			display: "flex", flexDirection: "column", overflow: "hidden",
			borderRadius: "10px 0 0 10px",
			// Overlay on tablet/mobile — sits above chat with its own z-index
			zIndex: overlay ? 20 : 1
		});

		// Force messages scroll
		this.$messages.css({ flex: "1 1 0", overflowY: "scroll", overflowX: "hidden",
			minHeight: 0, display: "inline-block", width: "100%" });

		if (overlay) {
			// Sidebar starts collapsed on tablet/mobile
			$sidebar.css({ left: "-230px" });
			$chat.css({ position: "absolute", top: 0, left: "0", right: 0, bottom: 0,
				display: "flex", flexDirection: "column", overflow: "hidden",
				background: "var(--card-bg)", borderRadius: "10px" });
			$("#ai-sb-expand-btn").removeClass("hidden");
		} else {
			// Desktop: sidebar pushes chat
			$sidebar.css({ left: "0" });
			$chat.css({ position: "absolute", top: 0, left: "230px", right: 0, bottom: 0,
				display: "flex", flexDirection: "column", overflow: "hidden",
				background: "var(--card-bg)", borderRadius: "0 10px 10px 0" });
			$("#ai-sb-expand-btn").addClass("hidden");
			$("#ai-sb-backdrop").addClass("hidden");
		}
	}

	// ── Events ─────────────────────────────────────────────────────────────────

	_bind_events() {
		this.$input.on("input", () => {
			this._auto_resize();
			this.$send.prop("disabled", !this.$input.val().trim());
		});

		this.$input.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this._send();
			}
		});

		this.$send.on("click", () => this._send());
		$("#ai-clear-btn").on("click", () => this._clear());

		// Sidebar quick-action buttons
		$(document).on("click", ".ai-sn-item", (e) => {
			const msg = $(e.currentTarget).data("msg");
			this.$input.val(msg).trigger("input").focus();
			// Auto-send only if message is complete (doesn't end with space)
			if (!msg.endsWith(" ")) {
				this._send();
			}
		});

		// Sidebar collapse / expand toggle
		$("#ai-sb-toggle").on("click", () => this._collapse_sidebar());
		$("#ai-sb-expand-btn").on("click", () => this._expand_sidebar());

		// Backdrop click closes sidebar on overlay mode
		$("#ai-sb-backdrop").on("click", () => this._collapse_sidebar());

		// Auto-close sidebar on mobile after clicking a quick-action
		$(document).on("click.ai_sidebar", ".ai-sn-item", () => {
			if (this._is_overlay()) this._collapse_sidebar();
		});
	}

	_collapse_sidebar() {
		$("#ai-sidebar").css({ left: "-230px" });
		$("#ai-sb-expand-btn").removeClass("hidden");
		if (this._is_overlay()) {
			$("#ai-sb-backdrop").addClass("hidden");
		} else {
			$(".ai-chat-container").css({ left: "0", borderRadius: "10px" });
		}
	}

	_expand_sidebar() {
		$("#ai-sidebar").css({ left: "0" });
		$("#ai-sb-expand-btn").addClass("hidden");
		if (this._is_overlay()) {
			// Overlay: sidebar floats above chat, show backdrop
			$("#ai-sb-backdrop").removeClass("hidden");
		} else {
			$(".ai-chat-container").css({ left: "230px", borderRadius: "0 10px 10px 0" });
		}
	}

	_auto_resize() {
		const el = this.$input[0];
		el.style.height = "auto";
		el.style.height = Math.min(el.scrollHeight, 150) + "px";
	}

	// ── Send ───────────────────────────────────────────────────────────────────

	_send() {
		const msg = this.$input.val().trim();
		if (!msg || this.is_loading) return;

		this.$input.val("").css("height", "auto");
		this.$send.prop("disabled", true);
		this._append_message("user", msg);

		// Remove welcome screen on first message
		$(".ai-welcome-msg").remove();

		this.is_loading = true;
		this._show_typing();

		frappe.call({
			method: "ai_assistant.api.chat.send_message",
			args: {
				message: msg,
				history: JSON.stringify(this.history),
			},
			callback: (r) => {
				this.is_loading = false;
				this._hide_typing();
				if (r.message) {
					this._handle_response(r.message, msg);
				}
			},
			error: () => {
				this.is_loading = false;
				this._hide_typing();
				this._append_message("assistant", __("⚠ Sorry, something went wrong. Please try again."), "error");
			},
		});
	}

	// ── Response handling ──────────────────────────────────────────────────────

	_handle_response(data, userMsg) {
		const results = data.results || [];
		const usage = data.usage || {};

		// Push user turn to history
		this.history.push({ role: "user", content: userMsg });

		const replyParts = [];

		if (results.length === 0) {
			// Safety fallback — should not normally happen
			this._append_message("assistant", __("No response received from AI. Please try again."), "warning");
		}

		results.forEach((result) => {
			const intent = result.intent;
			const msg = (result.message || "").trim();

			if (intent === "reply") {
				// Never show a blank bubble
				this._append_message("assistant", msg || __("(empty response — please try again)"));
				replyParts.push(msg || "");

			} else if (intent === "blocked") {
				this._append_message("assistant", `🚫 ${msg}`, "warning");

			} else if (intent === "error") {
				this._append_message("assistant", `⚠ ${msg}`, "error");

			} else {
				// Tool execution result card
				const card = this._build_result_card(result);
				this.$messages.append(card);
				this._scroll_to_bottom();
				replyParts.push(msg || JSON.stringify(result));
			}
		});

		if (replyParts.length) {
			this.history.push({ role: "assistant", content: replyParts.join("\n") });
		}

		if (this.history.length > 40) {
			this.history = this.history.slice(-40);
		}

		// Refresh usage badge after any successful exchange
		this._load_usage();
	}

	_build_result_card(result) {
		const intent = result.intent || "";
		const status = result.status || "ok";
		const message = result.message || "";

		const icon = {
			// Customers & CRM
			create_customer: "👤", search_customer: "🔍",
			get_customer_history: "📋", create_lead: "🌱",
			get_open_leads: "🌱", create_opportunity: "🎯",
			// Quotations
			create_quotation: "📄", get_quotations: "📄",
			convert_quotation_to_sales_order: "📄➡️📦",
			// Sales Orders
			create_sales_order: "📦", get_sales_orders: "📦",
			convert_so_to_invoice: "📦➡️🧾",
			convert_so_to_delivery_note: "📦➡️🚚",
			close_sales_order: "🔒",
			// Invoices & Returns
			create_sales_invoice: "🧾", get_pending_invoices: "💰",
			create_sales_return: "↩️", get_invoices_summary: "📊",
			// Delivery
			create_delivery_note: "🚚", get_delivery_notes: "🚚",
			// Payments
			record_payment: "💳", generate_payment_from_invoice: "💳",
			get_payment_entries: "💳",
			// Accounts
			get_account_balance: "🏦", create_journal_entry: "📒",
			get_journal_entries: "📒", get_accounts_receivable: "💰",
			get_sales_summary: "📊",
			// Purchasing
			create_supplier: "🏭", search_supplier: "🔍",
			create_purchase_order: "🛒", get_pending_purchase_orders: "🛒",
			get_purchase_summary: "📊",
			// Inventory
			get_stock: "📦", search_item: "🔍",
			get_item_price: "🏷️", create_material_request: "📋",
			get_stock_report: "📊",
			// Support & Projects
			create_issue: "🎫", get_open_issues: "🎫",
			create_project: "🗂️", create_task: "✅",
			create_job_card: "🔧",
			// Workshop & Rental
			create_workshop_job_card: "🔧", create_vehicle_inspection: "🔍",
			create_workshop_estimate: "📝", get_workshop_vehicle: "🚗",
			get_workshop_job_cards: "🔧", get_available_vehicles: "🚗",
			get_active_rental_contracts: "📋",
			// Business Intelligence
			get_monthly_sales_trend: "📈",
			get_top_customers: "🏆",
			get_top_selling_items: "🛍️",
			get_pending_quotations: "📄",
			get_overdue_invoices: "⚠️",
			get_stock_alerts: "📦",
			get_open_job_cards: "🔧",
			analyze_business: "🧠",
			// Management Summary
			get_management_summary: "🌅",
			// Customer Follow-Up
			get_inactive_customers: "💤",
			get_unconverted_quotations: "📄",
			get_customers_with_overdue_balance: "💸",
			get_customers_without_recent_orders: "🔄",
			get_followup_opportunities: "🎯",
			// Vehicle Diagnostics
			diagnose_vehicle_issue: "🔧",
			// HR & Employees
			create_employee: "👤", get_employees: "👥",
			create_leave_application: "🌴", get_leave_balance: "📅",
			get_attendance_summary: "🗓️",
			// Payroll
			get_salary_slips: "💵", get_payroll_summary: "💰",
			// Manufacturing
			create_work_order: "🏭", get_work_orders: "🏭",
			get_bom_list: "📋",
			// Purchase Invoice & Receipt
			create_purchase_invoice: "🧾", get_purchase_invoices: "🧾",
			create_purchase_receipt: "📥",
			// Stock Operations
			create_stock_entry: "🔄",
			// Item Management
			create_item: "🏷️", get_items: "🏷️",
			// Task Management
			get_tasks: "✅", update_task_status: "✅",
			// Expense Claims
			create_expense_claim: "💳", get_expense_claims: "💳",
		}[intent] || "✅";

		const title = intent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

		let detail = "";
		if (status === "error" || status === "validation_error") {
			detail = `<div class="ai-result-error">${frappe.utils.escape_html(message)}</div>`;

		} else if (intent === "search_customer" && result.customers) {
			detail = this._render_customer_table(result.customers);
		} else if (intent === "get_customer_history") {
			detail = this._render_customer_history(result);
		} else if ((intent === "get_pending_invoices" || intent === "get_invoices_summary") && result.invoices) {
			detail = this._render_invoice_table(result.invoices, result);
		} else if (intent === "get_accounts_receivable" && result.invoices) {
			detail = this._render_ar_table(result);
		} else if (intent === "get_stock" && result.warehouses) {
			detail = this._render_stock_table(result.warehouses, result.item);
		} else if ((intent === "get_stock_report") && result.stock) {
			detail = this._render_stock_report_table(result.stock);
		} else if (intent === "get_quotations" && result.quotations) {
			detail = this._render_doc_table(result.quotations,
				["name","party_name","transaction_date","grand_total","status"],
				["Quotation","Customer","Date","Total","Status"]);
		} else if (intent === "get_sales_orders" && result.sales_orders) {
			detail = this._render_doc_table(result.sales_orders,
				["name","customer","transaction_date","grand_total","per_billed","status"],
				["Order","Customer","Date","Total","Billed%","Status"]);
		} else if (intent === "get_delivery_notes" && result.delivery_notes) {
			detail = this._render_doc_table(result.delivery_notes,
				["name","customer","posting_date","grand_total","status"],
				["DN","Customer","Date","Total","Status"]);
		} else if (intent === "get_payment_entries" && result.payments) {
			detail = this._render_doc_table(result.payments,
				["name","party","posting_date","paid_amount","mode_of_payment"],
				["Entry","Customer","Date","Amount","Mode"]);
		} else if (intent === "get_journal_entries" && result.journal_entries) {
			detail = this._render_doc_table(result.journal_entries,
				["name","voucher_type","posting_date","total_debit","user_remark"],
				["JV","Type","Date","Debit","Remark"]);
		} else if (intent === "get_pending_purchase_orders" && result.purchase_orders) {
			detail = this._render_doc_table(result.purchase_orders,
				["name","supplier","transaction_date","grand_total","status"],
				["PO","Supplier","Date","Total","Status"]);
		} else if (intent === "get_sales_summary" || intent === "get_purchase_summary") {
			detail = this._render_summary_card(result);
		} else if (intent === "get_account_balance") {
			detail = `<div class="ai-result-message">
				<strong>${frappe.utils.escape_html(result.account)}</strong><br>
				Balance as of ${result.date}: <strong>${frappe.format(result.balance, {fieldtype:"Currency"})}</strong>
			</div>`;
		} else if (intent === "get_open_leads" && result.leads) {
			detail = this._render_doc_table(result.leads,
				["name","lead_name","mobile_no","status","source"],
				["ID","Name","Phone","Status","Source"]);
		} else if (intent === "get_open_issues" && result.issues) {
			detail = this._render_doc_table(result.issues,
				["name","subject","customer","priority","status"],
				["Issue","Subject","Customer","Priority","Status"]);
		} else if (intent === "get_workshop_job_cards" && result.job_cards) {
			detail = this._render_doc_table(result.job_cards,
				["name","vehicle","customer","complaint","status","technician"],
				["Card","Vehicle","Customer","Complaint","Status","Technician"]);
		} else if (intent === "get_available_vehicles" && result.vehicles) {
			detail = this._render_doc_table(result.vehicles,
				["name","make","model","license_plate","daily_rate","monthly_rate"],
				["ID","Make","Model","Plate","Daily Rate","Monthly Rate"]);
		} else if (intent === "get_active_rental_contracts" && result.contracts) {
			detail = this._render_doc_table(result.contracts,
				["name","customer","vehicle","start_date","end_date","grand_total"],
				["Contract","Customer","Vehicle","Start","End","Total"]);
		} else if (intent === "get_workshop_vehicle" && result.vehicles) {
			detail = this._render_doc_table(result.vehicles,
				["vehicle_no","make","model","year","customer","color"],
				["Plate","Make","Model","Year","Customer","Color"]);

		// ── Business Intelligence renderers ──────────────────────────
		} else if (intent === "analyze_business") {
			detail = this._render_bi_analysis(result);
		} else if (intent === "get_management_summary") {
			detail = this._render_management_summary(result);
		} else if (intent === "get_monthly_sales_trend" && result.trend) {
			detail = this._render_sales_trend(result);
		} else if (intent === "get_top_customers" && result.customers) {
			detail = this._render_doc_table(result.customers,
				["customer","invoice_count","total_sales","last_invoice_date"],
				["Customer","Invoices","Total Sales","Last Invoice"]);
		} else if (intent === "get_top_selling_items" && result.items) {
			detail = this._render_doc_table(result.items,
				["item_code","item_name","total_qty","total_amount"],
				["Code","Item","Qty Sold","Revenue"]);
		} else if (intent === "get_pending_quotations" && result.quotations) {
			detail = this._render_pending_quotations(result);
		} else if (intent === "get_overdue_invoices" && result.invoices) {
			detail = this._render_overdue_invoices(result);
		} else if (intent === "get_stock_alerts") {
			detail = this._render_stock_alerts(result);
		} else if (intent === "get_open_job_cards" && result.job_cards) {
			detail = this._render_open_job_cards(result);

		// ── Customer Follow-Up renderers ─────────────────────────────
		} else if (intent === "get_followup_opportunities" && result.opportunities) {
			detail = this._render_followup_opportunities(result);
		} else if (intent === "get_inactive_customers" && result.customers) {
			detail = this._render_doc_table(result.customers,
				["customer_name","customer_group","last_purchase_date","days_inactive"],
				["Customer","Group","Last Purchase","Days Inactive"]);
		} else if (intent === "get_unconverted_quotations" && result.quotations) {
			detail = this._render_doc_table(result.quotations,
				["name","party_name","transaction_date","grand_total","days_old"],
				["Quotation","Customer","Date","Value","Age (days)"]);
		} else if (intent === "get_customers_with_overdue_balance" && result.customers) {
			detail = this._render_doc_table(result.customers,
				["customer","invoice_count","total_outstanding","oldest_due_date","max_days_overdue"],
				["Customer","Invoices","Total Overdue","Oldest Due","Days Overdue"]);
		} else if (intent === "get_customers_without_recent_orders" && result.customers) {
			detail = this._render_doc_table(result.customers,
				["customer","lifetime_value","last_purchase","days_since_purchase"],
				["Customer","Lifetime Value","Last Order","Days Since"]);

		// ── HR & Employees renderers ─────────────────────────────────
		} else if (intent === "get_employees" && result.employees) {
			detail = this._render_doc_table(result.employees,
				["name", "employee_name", "department", "designation", "date_of_joining", "status"],
				["ID", "Name", "Department", "Designation", "Joined", "Status"]);
		} else if (intent === "get_leave_balance" && result.balances) {
			detail = this._render_leave_balance(result);
		} else if (intent === "get_attendance_summary") {
			detail = this._render_attendance_summary(result);
		} else if (intent === "get_tasks" && result.tasks) {
			detail = this._render_doc_table(result.tasks,
				["name", "subject", "project", "assigned_to", "status", "priority", "exp_end_date"],
				["Task", "Subject", "Project", "Assigned To", "Status", "Priority", "Due"]);
		// ── Payroll renderers ─────────────────────────────────────────
		} else if (intent === "get_salary_slips" && result.salary_slips) {
			detail = this._render_doc_table(result.salary_slips,
				["name", "employee_name", "start_date", "end_date", "gross_pay", "total_deduction", "net_pay"],
				["Slip", "Employee", "From", "To", "Gross", "Deduction", "Net Pay"]);
		} else if (intent === "get_payroll_summary") {
			detail = this._render_payroll_summary(result);
		// ── Manufacturing renderers ────────────────────────────────────
		} else if (intent === "get_work_orders" && result.work_orders) {
			detail = this._render_doc_table(result.work_orders,
				["name", "production_item", "qty", "produced_qty", "planned_start_date", "status"],
				["Work Order", "Item", "Qty", "Produced", "Planned Date", "Status"]);
		} else if (intent === "get_bom_list" && result.boms) {
			detail = this._render_doc_table(result.boms,
				["name", "item", "item_name", "quantity", "is_default"],
				["BOM", "Item Code", "Item Name", "Qty", "Default?"]);
		// ── Purchase renderers ────────────────────────────────────────
		} else if (intent === "get_purchase_invoices" && result.purchase_invoices) {
			detail = this._render_doc_table(result.purchase_invoices,
				["name", "supplier", "posting_date", "grand_total", "outstanding_amount", "status"],
				["Invoice", "Supplier", "Date", "Total", "Outstanding", "Status"]);
		// ── Item renderers ────────────────────────────────────────────
		} else if (intent === "get_items" && result.items) {
			detail = this._render_doc_table(result.items,
				["name", "item_name", "item_group", "stock_uom", "is_stock_item"],
				["Code", "Name", "Group", "UOM", "Stock Item?"]);
		// ── Expense renderers ─────────────────────────────────────────
		} else if (intent === "get_expense_claims" && result.expense_claims) {
			detail = this._render_doc_table(result.expense_claims,
				["name", "employee_name", "posting_date", "total_claimed_amount", "total_sanctioned_amount", "approval_status"],
				["Claim", "Employee", "Date", "Claimed", "Sanctioned", "Status"]);
		// ── Vehicle Diagnostics renderer ─────────────────────────────
		} else if (intent === "diagnose_vehicle_issue") {
			detail = this._render_diagnostic(result);

		} else {
			detail = `<div class="ai-result-message">${frappe.utils.escape_html(message)}</div>`;

			// Link button for created documents
			const docRouteMap = {
				create_customer:         [result.customer,           "customer"],
				create_quotation:        [result.quotation,          "quotation"],
				convert_quotation_to_sales_order: [result.sales_order, "sales-order"],
				create_sales_order:      [result.sales_order,        "sales-order"],
				convert_so_to_invoice:   [result.invoice,            "sales-invoice"],
				create_sales_invoice:    [result.invoice,            "sales-invoice"],
				create_sales_return:     [result.credit_note,        "sales-invoice"],
				convert_so_to_delivery_note: [result.delivery_note,  "delivery-note"],
				create_delivery_note:    [result.delivery_note,      "delivery-note"],
				record_payment:          [result.payment,            "payment-entry"],
				generate_payment_from_invoice: [result.payment,      "payment-entry"],
				create_journal_entry:    [result.journal_entry,      "journal-entry"],
				create_purchase_order:   [result.purchase_order,     "purchase-order"],
				create_supplier:         [result.supplier,           "supplier"],
				create_material_request: [result.material_request,   "material-request"],
				create_issue:            [result.issue,              "issue"],
				create_project:          [result.project,            "project"],
				create_task:             [result.task,               "task"],
				create_job_card:         [result.job_card,           "maintenance-visit"],
				create_workshop_job_card:[result.workshop_job_card,  "workshop-job-card"],
				create_workshop_estimate:[result.workshop_estimate,  "workshop-estimate"],
				create_vehicle_inspection:[result.vehicle_inspection,"vehicle-inspection"],
				create_lead:             [result.lead,               "lead"],
				create_opportunity:      [result.opportunity,        "opportunity"],
				// HR
				create_employee:         [result.employee,           "employee"],
				create_leave_application:[result.leave_application,  "leave-application"],
				create_expense_claim:    [result.expense_claim,      "expense-claim"],
				// Manufacturing
				create_work_order:       [result.work_order,         "work-order"],
				// Purchase
				create_purchase_invoice: [result.purchase_invoice,   "purchase-invoice"],
				create_purchase_receipt: [result.purchase_receipt,   "purchase-receipt"],
				// Stock
				create_stock_entry:      [result.stock_entry,        "stock-entry"],
				// Item
				create_item:             [result.item,               "item"],
			};
			const entry = docRouteMap[intent];
			if (entry && entry[0] && result.status === "created") {
				detail += `<a href="/app/${entry[1]}/${encodeURIComponent(entry[0])}"
					class="btn btn-xs btn-primary ai-open-btn" target="_blank">
					${__("Open")} ${entry[0]} →
				</a>`;
			}
		}

		const isError = status === "error" || status === "validation_error";
		return $(`
			<div class="ai-result-card ${isError ? "ai-result-card--error" : ""}">
				<div class="ai-result-card-header">
					<span class="ai-result-icon">${icon}</span>
					<span class="ai-result-title">${title}</span>
					${isError ? '<span class="ai-result-badge ai-result-badge--error">Error</span>' : '<span class="ai-result-badge ai-result-badge--ok">Done</span>'}
				</div>
				<div class="ai-result-body">${detail}</div>
			</div>
		`);
	}

	// ── Generic table renderer ─────────────────────────────────────
	_render_doc_table(rows, fields, headers) {
		if (!rows || !rows.length)
			return `<p class="text-muted">${__("No records found.")}</p>`;
		const ths = headers.map(h => `<th>${__(h)}</th>`).join("");
		const trs = rows.map(r => {
			const tds = fields.map((f, i) => {
				let val = r[f] != null ? r[f] : "";
				// Make the first column a link if row has a "name" field
				if (i === 0 && r.name) {
					val = `<a href="/app/${f === "name" ? "" : ""}#" target="_blank">${frappe.utils.escape_html(String(val))}</a>`;
				} else {
					val = frappe.utils.escape_html(String(val));
				}
				return `<td>${val}</td>`;
			}).join("");
			return `<tr>${tds}</tr>`;
		}).join("");
		return `<table class="ai-mini-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
	}

	_render_customer_table(customers) {
		if (!customers.length) return `<p class="text-muted">${__("No customers found.")}</p>`;
		const rows = customers.map(c => `
			<tr>
				<td><a href="/app/customer/${encodeURIComponent(c.name)}" target="_blank">${frappe.utils.escape_html(c.customer_name)}</a></td>
				<td>${frappe.utils.escape_html(c.customer_group || "")}</td>
				<td>${frappe.utils.escape_html(c.mobile_no || "")}</td>
				<td>${frappe.utils.escape_html(c.email_id || "")}</td>
			</tr>`).join("");
		return `<table class="ai-mini-table"><thead><tr><th>Name</th><th>Group</th><th>Phone</th><th>Email</th></tr></thead><tbody>${rows}</tbody></table>`;
	}

	_render_invoice_table(invoices, result) {
		if (!invoices.length) return `<p class="text-muted">${__("No invoices found.")}</p>`;
		let summary = "";
		if (result && result.total_outstanding) {
			summary = `<div class="ai-result-message" style="margin-bottom:6px">
				${__("Total Outstanding")}: <strong>${frappe.format(result.total_outstanding, {fieldtype:"Currency"})}</strong>
			</div>`;
		}
		const rows = invoices.map(i => `
			<tr>
				<td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
				<td>${frappe.utils.escape_html(i.customer || "")}</td>
				<td>${frappe.format(i.grand_total, {fieldtype:"Currency"})}</td>
				<td>${frappe.format(i.outstanding_amount, {fieldtype:"Currency"})}</td>
				<td>${i.due_date || i.posting_date || ""}</td>
			</tr>`).join("");
		return summary + `<table class="ai-mini-table"><thead><tr><th>Invoice</th><th>Customer</th><th>Total</th><th>Outstanding</th><th>Due</th></tr></thead><tbody>${rows}</tbody></table>`;
	}

	_render_ar_table(result) {
		const { invoices = [], total_outstanding = 0, total_overdue = 0, overdue_count = 0 } = result;
		if (!invoices.length) return `<p class="text-muted">${__("No outstanding invoices.")}</p>`;
		const summary = `<div class="ai-result-message" style="margin-bottom:6px">
			${__("Total Outstanding")}: <strong>${frappe.format(total_outstanding, {fieldtype:"Currency"})}</strong>
			&nbsp;|&nbsp; ${__("Overdue")} (${overdue_count}): <strong style="color:var(--red-500)">${frappe.format(total_overdue, {fieldtype:"Currency"})}</strong>
		</div>`;
		const rows = invoices.map(i => {
			const overdue = i.due_date && i.due_date < frappe.datetime.get_today();
			return `<tr${overdue ? ' style="color:var(--red-600)"' : ""}>
				<td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
				<td>${frappe.utils.escape_html(i.customer)}</td>
				<td>${frappe.format(i.grand_total, {fieldtype:"Currency"})}</td>
				<td>${frappe.format(i.outstanding_amount, {fieldtype:"Currency"})}</td>
				<td>${i.due_date || ""}${overdue ? " ⚠" : ""}</td>
			</tr>`;
		}).join("");
		return summary + `<table class="ai-mini-table"><thead><tr><th>Invoice</th><th>Customer</th><th>Total</th><th>Outstanding</th><th>Due</th></tr></thead><tbody>${rows}</tbody></table>`;
	}

	_render_summary_card(result) {
		const pairs = Object.entries(result)
			.filter(([k]) => !["status","from_date","to_date","top_customers","invoices"].includes(k))
			.map(([k, v]) => {
				const label = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
				const val = typeof v === "number" && k.includes("total")
					? frappe.format(v, {fieldtype:"Currency"})
					: v;
				return `<div class="ai-kv-row"><span class="ai-kv-label">${label}</span><span class="ai-kv-val">${val}</span></div>`;
			}).join("");
		let topCust = "";
		if (result.top_customers && result.top_customers.length) {
			const rows = result.top_customers.map(c =>
				`<tr><td>${frappe.utils.escape_html(c.customer)}</td><td>${frappe.format(c.total, {fieldtype:"Currency"})}</td></tr>`
			).join("");
			topCust = `<p style="margin-top:8px"><strong>${__("Top Customers")}</strong></p>
				<table class="ai-mini-table"><thead><tr><th>Customer</th><th>Total</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		return `<div class="ai-kv-grid">${pairs}</div>${topCust}`;
	}

	_render_customer_history(result) {
		let html = "";
		if (result.sales_orders && result.sales_orders.length) {
			const rows = result.sales_orders.map(o =>
				`<tr><td><a href="/app/sales-order/${encodeURIComponent(o.name)}" target="_blank">${o.name}</a></td>
				<td>${o.transaction_date}</td>
				<td>${frappe.format(o.grand_total, {fieldtype:"Currency"})}</td>
				<td>${o.status}</td></tr>`).join("");
			html += `<p><strong>${__("Sales Orders")}</strong></p>
				<table class="ai-mini-table"><thead><tr><th>Order</th><th>Date</th><th>Total</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.invoices && result.invoices.length) {
			const rows = result.invoices.map(i =>
				`<tr><td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
				<td>${i.posting_date}</td>
				<td>${frappe.format(i.grand_total, {fieldtype:"Currency"})}</td>
				<td>${frappe.format(i.outstanding_amount, {fieldtype:"Currency"})}</td></tr>`).join("");
			html += `<p><strong>${__("Invoices")}</strong></p>
				<table class="ai-mini-table"><thead><tr><th>Invoice</th><th>Date</th><th>Total</th><th>Outstanding</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.payments && result.payments.length) {
			const rows = result.payments.map(p =>
				`<tr><td><a href="/app/payment-entry/${encodeURIComponent(p.name)}" target="_blank">${p.name}</a></td>
				<td>${p.posting_date}</td>
				<td>${frappe.format(p.paid_amount, {fieldtype:"Currency"})}</td>
				<td>${frappe.utils.escape_html(p.mode_of_payment || "")}</td></tr>`).join("");
			html += `<p><strong>${__("Payments")}</strong></p>
				<table class="ai-mini-table"><thead><tr><th>Entry</th><th>Date</th><th>Amount</th><th>Mode</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		return html || `<p class="text-muted">${__("No history found.")}</p>`;
	}

	_render_stock_table(warehouses, item) {
		if (!warehouses.length)
			return `<p class="text-muted">${__("No stock data for")} ${frappe.utils.escape_html(item)}.</p>`;
		const rows = warehouses.map(w =>
			`<tr><td>${frappe.utils.escape_html(w.warehouse)}</td>
			<td>${w.actual_qty}</td><td>${w.reserved_qty || 0}</td><td>${w.projected_qty || 0}</td></tr>`
		).join("");
		return `<table class="ai-mini-table"><thead><tr><th>Warehouse</th><th>Actual</th><th>Reserved</th><th>Projected</th></tr></thead><tbody>${rows}</tbody></table>`;
	}

	_render_stock_report_table(stock) {
		if (!stock.length) return `<p class="text-muted">${__("No stock found.")}</p>`;
		const rows = stock.map(s =>
			`<tr><td>${frappe.utils.escape_html(s.item_code)}</td>
			<td>${frappe.utils.escape_html(s.warehouse)}</td>
			<td>${s.actual_qty}</td><td>${s.projected_qty || 0}</td></tr>`
		).join("");
		return `<table class="ai-mini-table"><thead><tr><th>Item</th><th>Warehouse</th><th>Actual</th><th>Projected</th></tr></thead><tbody>${rows}</tbody></table>`;
	}

	// ── Business Intelligence renderers ────────────────────────────────────────

	_fmt_currency(v) {
		return frappe.format(v || 0, { fieldtype: "Currency" });
	}

	_growth_badge(pct) {
		if (pct === undefined || pct === null) return "";
		const up = pct >= 0;
		const cls = up ? "ai-trend-up" : "ai-trend-down";
		const arrow = up ? "▲" : "▼";
		return `<span class="ai-trend-badge ${cls}">${arrow} ${Math.abs(pct).toFixed(1)}%</span>`;
	}

	_priority_badge(p) {
		const map = { critical: "ai-priority-critical", warning: "ai-priority-warning", high: "ai-priority-high", medium: "ai-priority-medium", info: "ai-priority-info", ok: "ai-priority-ok", low: "ai-priority-low" };
		return `<span class="ai-priority-badge ${map[p] || "ai-priority-info"}">${p}</span>`;
	}

	_render_bi_analysis(r) {
		const fmt = v => this._fmt_currency(v);
		const kpis = [
			{ label: "Sales This Month", value: fmt(r.sales_this_month), sub: this._growth_badge(r.sales_growth) + " vs last month" },
			{ label: "Collected Today",  value: fmt(r.collected_today) },
			{ label: "Pending Quotations", value: r.pending_quotations, sub: r.expiring_quotations ? `${r.expiring_quotations} expiring soon` : "" },
			{ label: "Overdue Invoices",  value: `${r.overdue_invoice_count}`, sub: fmt(r.overdue_invoice_amount) },
			{ label: "Critical Stock",    value: r.critical_stock_items, sub: "items below safety stock" },
			{ label: "Open Job Cards",    value: r.open_job_cards, sub: r.delayed_job_cards ? `${r.delayed_job_cards} delayed` : "" },
			{ label: "New Customers",     value: r.new_customers_this_month, sub: "this month" },
			{ label: "Due This Week",     value: r.invoices_due_this_week, sub: "invoices" },
		];
		const kpiHtml = kpis.map(k => `
			<div class="ai-kpi-card">
				<div class="ai-kpi-value">${k.value}</div>
				<div class="ai-kpi-label">${__(k.label)}</div>
				${k.sub ? `<div class="ai-kpi-sub">${k.sub}</div>` : ""}
			</div>`).join("");

		let recsHtml = "";
		if (r.recommendations && r.recommendations.length) {
			recsHtml = `<div class="ai-bi-section">
				<div class="ai-bi-section-title">🎯 ${__("Recommendations")}</div>
				<ul class="ai-rec-list">
					${r.recommendations.map(rec =>
						`<li class="ai-rec-item ai-rec-${rec.priority || "info"}">
							${this._priority_badge(rec.priority)} ${frappe.utils.escape_html(rec.text)}
						</li>`
					).join("")}
				</ul>
			</div>`;
		}

		let topCustHtml = "";
		if (r.top_customers && r.top_customers.length) {
			const rows = r.top_customers.map(c =>
				`<tr><td>${frappe.utils.escape_html(c.customer)}</td><td>${fmt(c.total)}</td></tr>`
			).join("");
			topCustHtml = `<div class="ai-bi-section">
				<div class="ai-bi-section-title">🏆 ${__("Top Customers This Month")}</div>
				<table class="ai-mini-table"><thead><tr><th>Customer</th><th>Sales</th></tr></thead><tbody>${rows}</tbody></table>
			</div>`;
		}

		return `<div class="ai-bi-report">
			<div class="ai-kpi-grid">${kpiHtml}</div>
			${recsHtml}
			${topCustHtml}
		</div>`;
	}

	_render_management_summary(r) {
		const fmt = v => this._fmt_currency(v);
		const s = r.sales || {};
		const q = r.quotations || {};
		const inv = r.invoices || {};
		const wk = r.workshop || {};
		const ivt = r.inventory || {};

		const salesKpis = [
			{ label: "Today",       value: fmt(s.today),      sub: `${s.today_count || 0} invoices` },
			{ label: "This Week",   value: fmt(s.this_week),  sub: `${s.week_count || 0} invoices` },
			{ label: "This Month",  value: fmt(s.this_month), sub: this._growth_badge(s.growth_pct) + " vs last month" },
			{ label: "Collected Today", value: fmt(s.collected_today) },
		];

		const kpiHtml = salesKpis.map(k => `
			<div class="ai-kpi-card">
				<div class="ai-kpi-value">${k.value}</div>
				<div class="ai-kpi-label">${__(k.label)}</div>
				${k.sub ? `<div class="ai-kpi-sub">${k.sub}</div>` : ""}
			</div>`).join("");

		const metricsRows = [
			["Pending Quotations", q.pending_count || 0, `${fmt(q.pending_value)} total`],
			["Expiring Soon",      q.expiring_soon || 0, "within 7 days"],
			["Overdue Invoices",   inv.overdue_count || 0, `${fmt(inv.overdue_amount)} owed`],
			["Due Today",          inv.due_today_count || 0, `${fmt(inv.due_today_amount)}`],
			["Low Stock Items",    ivt.low_stock_count || 0, "below safety stock"],
			["Open Job Cards",     wk.open_jobs || 0, `${wk.delayed_jobs || 0} delayed`],
			["New Customers",      (r.customers || {}).new_this_month || 0, "this month"],
		].map(([lbl, val, sub]) => `
			<div class="ai-metric-row">
				<span class="ai-metric-label">${__(lbl)}</span>
				<span class="ai-metric-value">${val}</span>
				<span class="ai-metric-sub">${sub}</span>
			</div>`).join("");

		let prioritiesHtml = "";
		if (r.priorities && r.priorities.length) {
			prioritiesHtml = `<div class="ai-bi-section">
				<div class="ai-bi-section-title">⚡ ${__("Priority Actions")}</div>
				<ul class="ai-rec-list">
					${r.priorities.map(p =>
						`<li class="ai-rec-item ai-rec-${p.type === "collect" ? "critical" : "warning"}">
							${frappe.utils.escape_html(p.text)}
						</li>`
					).join("")}
				</ul>
			</div>`;
		}

		return `<div class="ai-bi-report">
			<div class="ai-summary-greeting">${frappe.utils.escape_html(r.greeting || "Hello")} — ${frappe.utils.escape_html(r.date || "")}</div>
			<div class="ai-bi-section-title">💰 ${__("Sales")}</div>
			<div class="ai-kpi-grid">${kpiHtml}</div>
			<div class="ai-bi-section">
				<div class="ai-bi-section-title">📊 ${__("Key Metrics")}</div>
				<div class="ai-metrics-grid">${metricsRows}</div>
			</div>
			${prioritiesHtml}
		</div>`;
	}

	_render_sales_trend(r) {
		const fmt = v => this._fmt_currency(v);
		const rows = (r.trend || []).map(m =>
			`<tr>
				<td>${frappe.utils.escape_html(m.month)}</td>
				<td>${fmt(m.total_sales)}</td>
				<td>${m.invoice_count}</td>
			</tr>`
		).join("");

		const header = `<div class="ai-kv-grid" style="margin-bottom:10px">
			<div class="ai-kv-row"><span class="ai-kv-label">Current Month</span><span class="ai-kv-val">${fmt(r.current_month_sales)}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">vs Last Month</span><span class="ai-kv-val">${this._growth_badge(r.growth_vs_last_month)}</span></div>
		</div>`;

		return header + `<table class="ai-mini-table">
			<thead><tr><th>Month</th><th>Sales</th><th>Invoices</th></tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	_render_pending_quotations(r) {
		const fmt = v => this._fmt_currency(v);
		const header = `<div class="ai-kv-grid" style="margin-bottom:8px">
			<div class="ai-kv-row"><span class="ai-kv-label">Total Pending</span><span class="ai-kv-val">${r.total_pending}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Total Value</span><span class="ai-kv-val">${fmt(r.total_value)}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Expiring in 7 days</span><span class="ai-kv-val" style="color:var(--red-500)">${r.expiring_soon_count}</span></div>
		</div>`;
		const rows = (r.quotations || []).slice(0, 15).map(q => {
			const expiring = q.valid_till && q.valid_till <= frappe.datetime.add_days(frappe.datetime.get_today(), 7);
			return `<tr${expiring ? ' class="ai-row-warn"' : ""}>
				<td><a href="/app/quotation/${encodeURIComponent(q.name)}" target="_blank">${q.name}</a></td>
				<td>${frappe.utils.escape_html(q.party_name || "")}</td>
				<td>${fmt(q.grand_total)}</td>
				<td>${q.valid_till || "—"}${expiring ? " ⚠" : ""}</td>
			</tr>`;
		}).join("");
		return header + `<table class="ai-mini-table">
			<thead><tr><th>Quotation</th><th>Customer</th><th>Value</th><th>Valid Till</th></tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	_render_overdue_invoices(r) {
		const fmt = v => this._fmt_currency(v);
		const header = `<div class="ai-kv-grid" style="margin-bottom:8px">
			<div class="ai-kv-row"><span class="ai-kv-label">Overdue Count</span><span class="ai-kv-val" style="color:var(--red-500)">${r.overdue_count}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Total Overdue</span><span class="ai-kv-val" style="color:var(--red-500)">${fmt(r.total_overdue_amount)}</span></div>
		</div>`;
		const rows = (r.invoices || []).map(i =>
			`<tr>
				<td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
				<td>${frappe.utils.escape_html(i.customer || "")}</td>
				<td>${fmt(i.outstanding_amount)}</td>
				<td>${i.due_date || ""}</td>
				<td style="color:var(--red-500)">${i.days_overdue || 0}d</td>
			</tr>`
		).join("");
		return header + `<table class="ai-mini-table">
			<thead><tr><th>Invoice</th><th>Customer</th><th>Outstanding</th><th>Due Date</th><th>Overdue</th></tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	_render_stock_alerts(r) {
		let html = `<div class="ai-kv-grid" style="margin-bottom:8px">
			<div class="ai-kv-row"><span class="ai-kv-label">Low Stock Items</span><span class="ai-kv-val" style="color:var(--orange-500)">${r.low_stock_count}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Out of Stock</span><span class="ai-kv-val" style="color:var(--red-500)">${r.out_of_stock_count}</span></div>
		</div>`;
		if (r.critical_items && r.critical_items.length) {
			const rows = r.critical_items.map(i =>
				`<tr>
					<td>${frappe.utils.escape_html(i.item_code)}</td>
					<td>${frappe.utils.escape_html(i.item_name || "")}</td>
					<td>${frappe.utils.escape_html(i.warehouse || "")}</td>
					<td>${i.actual_qty}</td>
					<td>${i.safety_stock}</td>
					<td style="color:var(--orange-500)">${i.stock_pct}%</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin-top:6px">⚠ ${__("Below Safety Stock")}</p>
				<table class="ai-mini-table">
					<thead><tr><th>Code</th><th>Item</th><th>Warehouse</th><th>Actual</th><th>Safety</th><th>Level%</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (r.out_of_stock_items && r.out_of_stock_items.length) {
			const rows = r.out_of_stock_items.map(i =>
				`<tr>
					<td>${frappe.utils.escape_html(i.item_code)}</td>
					<td>${frappe.utils.escape_html(i.item_name || "")}</td>
					<td>${frappe.utils.escape_html(i.warehouse || "")}</td>
					<td style="color:var(--red-500)">${i.actual_qty}</td>
					<td>${i.reserved_qty}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin-top:8px">🔴 ${__("Out of Stock (with pending demand)")}</p>
				<table class="ai-mini-table">
					<thead><tr><th>Code</th><th>Item</th><th>Warehouse</th><th>Actual</th><th>Reserved</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		return html;
	}

	_render_open_job_cards(r) {
		const header = `<div class="ai-kv-grid" style="margin-bottom:8px">
			<div class="ai-kv-row"><span class="ai-kv-label">Open Jobs</span><span class="ai-kv-val">${r.total_open}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Delayed (&gt;2 days)</span><span class="ai-kv-val" style="color:var(--red-500)">${r.delayed_count}</span></div>
		</div>`;
		const rows = (r.job_cards || []).map(j => {
			const delayed = r.delayed_jobs && r.delayed_jobs.find(d => d.name === j.name);
			return `<tr${delayed ? ' class="ai-row-warn"' : ""}>
				<td>${frappe.utils.escape_html(j.name || "")}</td>
				<td>${frappe.utils.escape_html(j.vehicle || j.customer || "")}</td>
				<td>${frappe.utils.escape_html(j.customer || "")}</td>
				<td>${frappe.utils.escape_html(j.complaint || j.purpose || "")}</td>
				<td>${frappe.utils.escape_html(j.status || "")}</td>
			</tr>`;
		}).join("");
		return header + `<table class="ai-mini-table">
			<thead><tr><th>Card</th><th>Vehicle</th><th>Customer</th><th>Issue</th><th>Status</th></tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	_render_followup_opportunities(r) {
		const fmt = v => this._fmt_currency(v);
		const header = `<div class="ai-kv-grid" style="margin-bottom:8px">
			<div class="ai-kv-row"><span class="ai-kv-label">Total Opportunities</span><span class="ai-kv-val">${r.total_opportunities}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">High Priority</span><span class="ai-kv-val" style="color:var(--red-500)">${r.high_priority}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">Potential Value</span><span class="ai-kv-val">${fmt(r.total_potential_value)}</span></div>
		</div>`;
		const cards = (r.opportunities || []).map(o => {
			const actionsHtml = (o.quick_actions || []).map(a => {
				const labels = {
					record_payment: "💳 Record Payment",
					create_issue: "🎫 Create Issue",
					convert_quotation_to_sales_order: "📦 Convert to Order",
					create_task: "✅ Create Task",
					create_quotation: "📄 New Quotation",
				};
				return `<button class="btn btn-xs btn-default ai-quick-action" style="margin-right:4px;margin-top:4px"
					data-action="${a}" data-customer="${frappe.utils.escape_html(o.customer || "")}"
					data-quotation="${frappe.utils.escape_html(o.quotation || "")}">
					${labels[a] || a}
				</button>`;
			}).join("");
			return `<div class="ai-opportunity-card ai-opp-${o.priority}">
				<div class="ai-opp-header">
					${this._priority_badge(o.priority)}
					<strong>${frappe.utils.escape_html(o.customer || "")}</strong>
					${o.potential_value ? `<span class="ai-opp-value">${fmt(o.potential_value)}</span>` : ""}
				</div>
				<div class="ai-opp-reason">${frappe.utils.escape_html(o.reason || "")}</div>
				<div class="ai-opp-action">💡 ${frappe.utils.escape_html(o.suggested_action || "")}</div>
				<div class="ai-opp-actions">${actionsHtml}</div>
			</div>`;
		}).join("");
		return header + `<div class="ai-opportunities">${cards}</div>`;
	}

	_render_leave_balance(r) {
		if (!r.balances || !r.balances.length)
			return `<p class="text-muted">${__("No leave allocations found.")}</p>`;
		const rows = r.balances.map(b => `
			<tr>
				<td>${frappe.utils.escape_html(b.leave_type)}</td>
				<td>${b.allocated}</td>
				<td>${b.used}</td>
				<td><strong style="color:${b.balance > 0 ? "var(--green-600)" : "var(--red-500)"}">${b.balance}</strong></td>
			</tr>`).join("");
		return `<table class="ai-mini-table">
			<thead><tr><th>Leave Type</th><th>Allocated</th><th>Used</th><th>Balance</th></tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	_render_attendance_summary(r) {
		const summary = r.summary || {};
		const pairs = Object.entries(summary).map(([k, v]) =>
			`<div class="ai-kv-row"><span class="ai-kv-label">${k}</span><span class="ai-kv-val">${v}</span></div>`
		).join("");
		return `<div class="ai-kv-grid" style="margin-bottom:8px">${pairs}</div>
			<p class="text-muted" style="font-size:0.8rem">${__("Period")}: ${r.from_date} → ${r.to_date} &nbsp;|&nbsp; ${__("Total")}: ${r.total}</p>`;
	}

	_render_payroll_summary(r) {
		const fmt = v => this._fmt_currency(v);
		return `<div class="ai-kv-grid">
			<div class="ai-kv-row"><span class="ai-kv-label">${__("Period")}</span><span class="ai-kv-val">${r.from_date} → ${r.to_date}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">${__("Employees")}</span><span class="ai-kv-val">${r.employee_count}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">${__("Total Gross")}</span><span class="ai-kv-val">${fmt(r.total_gross)}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">${__("Total Deductions")}</span><span class="ai-kv-val">${fmt(r.total_deduction)}</span></div>
			<div class="ai-kv-row"><span class="ai-kv-label">${__("Total Net Pay")}</span><span class="ai-kv-val"><strong>${fmt(r.total_net)}</strong></span></div>
		</div>`;
	}

	_render_diagnostic(r) {
		if (!r.matched) {
			return `<div class="ai-diagnostic-card">
				<div class="ai-diag-section"><strong>${__("Vehicle")}</strong>: ${frappe.utils.escape_html(r.vehicle || "")}</div>
				<div class="ai-diag-section"><strong>${__("Symptoms")}</strong>: ${(r.symptoms_received || []).map(s => frappe.utils.escape_html(s)).join(", ")}</div>
				<div class="ai-diag-section">${__("Could not match symptoms. Recommend OBD scan.")}</div>
			</div>`;
		}

		const urgencyBadge = r.urgency === "immediate"
			? `<span class="ai-priority-badge ai-priority-critical">⚠ IMMEDIATE</span>` : "";

		const causesHtml = (r.possible_causes || []).map(c =>
			`<li>${frappe.utils.escape_html(c)}</li>`).join("");
		const checksHtml = (r.recommended_checks || []).map(c =>
			`<li>${frappe.utils.escape_html(c)}</li>`).join("");
		const partsHtml = (r.recommended_parts || []).map(p =>
			`<li>${frappe.utils.escape_html(p)}</li>`).join("");

		let erpPartsHtml = "";
		if (r.erp_parts_available && r.erp_parts_available.length) {
			const rows = r.erp_parts_available.map(p =>
				`<tr>
					<td>${frappe.utils.escape_html(p.item_name)}</td>
					<td>${frappe.format(p.standard_rate, { fieldtype: "Currency" })}</td>
				</tr>`
			).join("");
			erpPartsHtml = `<div class="ai-diag-section">
				<strong>📦 ${__("Parts Available in ERP")}</strong>
				<table class="ai-mini-table" style="margin-top:4px">
					<thead><tr><th>Item</th><th>Rate</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`;
		}

		const makeNote = r.make_note
			? `<div class="ai-diag-note">ℹ️ ${frappe.utils.escape_html(r.make_note)}</div>` : "";

		return `<div class="ai-diagnostic-card">
			<div class="ai-diag-header">
				<strong>${frappe.utils.escape_html(r.vehicle || "")}</strong> ${urgencyBadge}
			</div>
			<div class="ai-diag-symptoms">
				${__("Symptoms")}: ${(r.symptoms_received || []).map(s => `<code>${frappe.utils.escape_html(s)}</code>`).join(", ")}
			</div>
			<div class="ai-diag-section">
				<strong>🔍 ${__("Possible Causes")}</strong><ul class="ai-diag-list">${causesHtml}</ul>
			</div>
			<div class="ai-diag-section">
				<strong>✅ ${__("Recommended Checks")}</strong><ul class="ai-diag-list">${checksHtml}</ul>
			</div>
			<div class="ai-diag-section">
				<strong>🔩 ${__("Recommended Parts")}</strong><ul class="ai-diag-list">${partsHtml}</ul>
			</div>
			${erpPartsHtml}
			<div class="ai-diag-footer">
				⏱ ${__("Estimated Labour")}: <strong>${r.estimated_labour_hours}h</strong>
			</div>
			${makeNote}
		</div>`;
	}

	// ── UI helpers ─────────────────────────────────────────────────────────────

	_append_message(role, content, type = "") {
		const cls = role === "user" ? "ai-msg-user" : "ai-msg-assistant";
		const avatar = role === "user"
			? `<div class="ai-msg-avatar ai-msg-avatar--user">${frappe.user.abbr(frappe.session.user)}</div>`
			: `<div class="ai-msg-avatar ai-msg-avatar--bot">🤖</div>`;

		const extraCls = type === "error" ? "ai-msg--error" : type === "warning" ? "ai-msg--warning" : "";
		// Convert newlines to <br> and escape HTML
		const safeContent = frappe.utils.escape_html(content).replace(/\n/g, "<br>");

		const $msg = $(`
			<div class="ai-msg ${cls} ${extraCls}">
				${role !== "user" ? avatar : ""}
				<div class="ai-msg-bubble">${safeContent}</div>
				${role === "user" ? avatar : ""}
			</div>
		`);

		this.$messages.append($msg);
		this._scroll_to_bottom();
	}

	_show_typing() {
		$("#ai-typing").removeClass("hidden");
		this._scroll_to_bottom();
	}

	_hide_typing() {
		$("#ai-typing").addClass("hidden");
	}

	_scroll_to_bottom() {
		// Use rAF so the DOM has been painted before we measure scrollHeight.
		requestAnimationFrame(() => {
			const el = this.$messages[0];
			if (el) el.scrollTop = el.scrollHeight;
		});
	}

	_clear() {
		this.history = [];
		this.$messages.html(`
			<div class="ai-welcome-msg">
				<div class="ai-welcome-icon">✨</div>
				<h4>${__("Chat cleared. Use the sidebar or type a question below.")}</h4>
			</div>
		`);
		this.$input.val("").css("height", "auto");
		this.$send.prop("disabled", true);
	}

	_load_usage() {
		frappe.call({
			method: "ai_assistant.api.chat.get_usage_summary",
			callback: (r) => {
				if (!r.message) return;
				const d = r.message;
				const $badge = $("#ai-usage-badge");
				if (d.budget) {
					$badge.text(`$${(+d.cost).toFixed(4)} / $${d.budget} (${d.budget_used_pct}%)`);
					$badge.toggleClass("ai-usage-badge--warn", d.budget_used_pct >= 80);
				}
			},
		});

		frappe.call({
			method: "ai_assistant.api.chat.get_settings_status",
			callback: (r) => {
				if (r.message && r.message.model) {
					$("#ai-model-label").text(r.message.provider + " · " + r.message.model);
				}
			},
		});
	}
}
