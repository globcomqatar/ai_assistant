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
		this.current_agent = "general";
		this.agents = [];

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
					this._load_agents();
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
		const svg = {
			chart:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
			calendar: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
			trending: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
			star:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
			bag:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>`,
			warning:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
			target:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>`,
			users:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
			file:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
			box:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>`,
			tool:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>`,
			useroff:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="23" y1="1" x2="17" y2="7"/><line x1="17" y1="1" x2="23" y2="7"/></svg>`,
			useradd:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="16" y1="11" x2="22" y2="11"/></svg>`,
			fileplus: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>`,
			leak:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
			filter:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>`,
			usercheck:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg>`,
			truck:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
			pulse:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
			bolt:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
		};

		return [
			{
				label: __("Business Intelligence"),
				icon: svg.chart,
				items: [
					{ icon: svg.chart,    label: __("Business Analysis"),   msg: "Analyze my business and give me recommendations" },
					{ icon: svg.calendar, label: __("Daily Summary"),       msg: "Give me the management daily summary" },
					{ icon: svg.trending, label: __("Monthly Sales Trend"), msg: "Show me the monthly sales trend for 6 months" },
					{ icon: svg.star,     label: __("Top Customers"),       msg: "Show top customers this month" },
					{ icon: svg.bag,      label: __("Top Selling Items"),   msg: "Show top selling items this month" },
				],
			},
			{
				label: __("Collections & AR"),
				icon: svg.warning,
				items: [
					{ icon: svg.warning, label: __("Overdue Invoices"),   msg: "Show overdue invoices" },
					{ icon: svg.target,  label: __("Follow-Up List"),     msg: "Who needs follow-up? Show me follow-up opportunities" },
					{ icon: svg.users,   label: __("Overdue Customers"),  msg: "Show customers with overdue balance" },
					{ icon: svg.file,    label: __("Pending Quotations"), msg: "Show pending quotations" },
				],
			},
			{
				label: __("Composite Reports"),
				icon: svg.pulse,
				items: [
					{ icon: svg.leak,      label: __("Revenue Leakage"), msg: "show me sales orders that have not been invoiced" },
					{ icon: svg.filter,    label: __("Sales Pipeline"),  msg: "show full sales pipeline from quote to cash" },
					{ icon: svg.usercheck, label: __("Customer 360"),    msg: "give me a full customer health check" },
					{ icon: svg.truck,     label: __("PO Receipt Gap"),  msg: "show purchase orders not yet received" },
					{ icon: svg.pulse,     label: __("P&L Bridge"),      msg: "show monthly profit and loss bridge" },
				],
			},
			{
				label: __("Operations"),
				icon: svg.box,
				items: [
					{ icon: svg.box,     label: __("Stock Alerts"),       msg: "Show stock alerts and low stock items" },
					{ icon: svg.tool,    label: __("Open Job Cards"),     msg: "Show open workshop job cards" },
					{ icon: svg.useroff, label: __("Inactive Customers"), msg: "Show inactive customers in the last 60 days" },
				],
			},
			{
				label: __("Quick Actions"),
				icon: svg.bolt,
				items: [
					{ icon: svg.useradd,  label: __("New Customer"),  msg: "Create customer " },
					{ icon: svg.fileplus, label: __("New Quotation"), msg: "Create quotation for customer " },
				],
			},
		];
	}

	_render() {
		const sidebarHtml = this._sidebar_groups()
			.map(group => `
			<div class="ai-sn-section">
				<div class="ai-sn-section-label">
					${group.label}
				</div>
				${group.items.map(item => `
					<button class="ai-sn-item"
							data-msg="${frappe.utils.escape_html(item.msg)}"
							type="button">
						<span class="ai-sn-ico">${item.icon}</span>
						<span class="ai-sn-lbl">${item.label}</span>
					</button>`).join("")}
				<div class="ai-sn-divider"></div>
			</div>`).join("");

		const html = `
		<div class="ai-layout" id="ai-layout">

			<!-- Mobile sidebar backdrop -->
			<div class="ai-sb-backdrop hidden" id="ai-sb-backdrop"></div>

			<!-- ── Left Navigation Sidebar ── -->
			<div class="ai-sn" id="ai-sidebar">
				<div class="ai-sn-brand">
					<div class="ai-sn-logo-mark">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<path d="M12 2L2 7l10 5 10-5-10-5z"/>
							<path d="M2 17l10 5 10-5"/>
							<path d="M2 12l10 5 10-5"/>
						</svg>
					</div>
					<span class="ai-sn-brand-text">${__("Quick Actions")}</span>
					<button class="ai-sn-close-btn" id="ai-sb-toggle" title="${__("Collapse sidebar")}">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="15 18 9 12 15 6"></polyline>
						</svg>
					</button>
				</div>
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
						<span class="ai-avatar" id="ai-agent-avatar">🤖</span>
						<div>
							<div class="ai-chat-title" id="ai-agent-title">${__("AI Assistant")}</div>
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

				<!-- Agent selector bar -->
				<div class="ai-agent-bar" id="ai-agent-bar"></div>

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
					<div class="ai-voice-status hidden" id="ai-voice-status"></div>
					<div class="ai-input-wrapper">
						<textarea id="ai-input" class="ai-input" rows="1"
							placeholder="${__("Type your message… (Enter to send, Shift+Enter for new line)")}"></textarea>
					</div>
					<button class="ai-lang-toggle" id="ai-lang-toggle" aria-label="Switch voice language" title="EN">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="2" y1="12" x2="22" y2="12"></line>
							<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
						</svg>
						<span class="ai-lang-label">EN</span>
					</button>
					<button class="ai-mic-btn" id="ai-mic-btn" aria-label="Start voice input">
						<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
							<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
							<line x1="12" y1="19" x2="12" y2="23"></line>
							<line x1="8" y1="23" x2="16" y2="23"></line>
						</svg>
					</button>
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
		this.voice = new VoiceInput(this);
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
		const sb       = $sidebar[0];

		const layoutH = mobile ? "calc(100svh - 110px)" : "80vh";
		$layout.css({ position: "relative", width: "100%", height: layoutH, overflow: "hidden" });

		// Set non-position sidebar styles (these don't conflict with CSS !important on left)
		$sidebar.css({
			background: "var(--bg-color)",
			display: "flex", flexDirection: "column", overflow: "hidden",
		});
		// zIndex must beat CSS z-index:1 on overlay
		sb.style.setProperty("z-index", overlay ? "20" : "1", "important");

		// Force messages scroll
		this.$messages.css({ flex: "1 1 0", overflowY: "scroll", overflowX: "hidden",
			minHeight: 0, display: "inline-block", width: "100%" });

		if (overlay) {
			// Mobile/tablet: sidebar hidden off-screen, chat fills full width
			sb.style.setProperty("left", "-110vw", "important");
			$chat.css({ position: "absolute", top: 0, left: "0", right: 0, bottom: 0,
				display: "flex", flexDirection: "column", overflow: "hidden",
				background: "var(--card-bg)", borderRadius: "10px" });
			$chat[0].style.setProperty("left", "0", "important");
			$("#ai-sb-expand-btn").removeClass("hidden");
			$("#ai-sb-backdrop").addClass("hidden");
		} else {
			// Desktop: sidebar pushes chat right
			sb.style.setProperty("left", "0", "important");
			$chat.css({ position: "absolute", top: 0, right: 0, bottom: 0,
				display: "flex", flexDirection: "column", overflow: "hidden",
				background: "var(--card-bg)", borderRadius: "0 10px 10px 0" });
			$chat[0].style.setProperty("left", "230px", "important");
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

		// Agent pill clicks — System Manager only
		$(document).on("click", ".ai-agent-pill", (e) => {
			if (!frappe.user.has_role("System Manager")) return;
			const agent_code = $(e.currentTarget).data("agent");
			if (agent_code) this._switch_agent(agent_code);
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
		const sb = document.getElementById("ai-sidebar");
		// Use setProperty("important") to beat CSS left:0 !important
		sb.style.setProperty("left", "-110vw", "important");
		$("#ai-sb-expand-btn").removeClass("hidden");
		$("#ai-sb-backdrop").addClass("hidden");
		if (!this._is_overlay()) {
			const chat = document.querySelector(".ai-chat-container");
			chat.style.setProperty("left", "0", "important");
			$(".ai-chat-container").css({ borderRadius: "10px" });
		}
	}

	_expand_sidebar() {
		const sb = document.getElementById("ai-sidebar");
		sb.style.setProperty("left", "0", "important");
		$("#ai-sb-expand-btn").addClass("hidden");
		if (this._is_overlay()) {
			// Overlay: sidebar floats above chat, show dark backdrop
			$("#ai-sb-backdrop").removeClass("hidden");
		} else {
			const chat = document.querySelector(".ai-chat-container");
			chat.style.setProperty("left", "230px", "important");
			$(".ai-chat-container").css({ borderRadius: "0 10px 10px 0" });
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
				current_agent: this.current_agent || "general",
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
		const routing = data.routing || null;

		// Push user turn to history
		this.history.push({ role: "user", content: userMsg });

		// Auto-routing note — shown when supervisor routed this message
		if (routing && routing.auto && routing.agent_code) {
			const candidate = (this.agents || []).find(a => a.agent_code === routing.agent_code);
			const icon = candidate ? (candidate.icon || "🤖") : "🤖";
			const name = frappe.utils.escape_html(routing.agent_name || routing.agent_code);
			const reason = routing.reason ? ` — ${frappe.utils.escape_html(routing.reason)}` : "";
			this.$messages.append(
				`<div class="ai-routing-note">
					<span class="ai-routing-note-icon"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>
					${__("Supervisor routed to")} <strong>${name}</strong>${reason}
				</div>`
			);
			this._switch_agent_silent(routing.agent_code, routing.agent_name || routing.agent_code, icon);
		}

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
			get_sales_analysis: "📊",
			get_payables_analysis: "💳",
			get_monthly_sales_trend: "📈",
			get_top_customers: "🏆",
			get_top_selling_items: "🛍️",
			get_pending_quotations: "📄",
			get_overdue_invoices: "⚠️",
			// Composite cross-module tools
			get_so_invoice_gap: "⚠️",
			get_sales_order_dashboard: "📊",
			get_sales_pipeline_status: "🔽",
			get_customer_360: "👤",
			get_po_receipt_gap: "🚚",
			get_monthly_pl_bridge: "📊",
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

		const title = intent.replace(/^(get|create|update|delete)_/i, "").replace(/_/g, " ");

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
		} else if (intent === "get_sales_summary") {
			detail = this._render_sales_summary(result);
		} else if (intent === "get_purchase_summary") {
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
		} else if (intent === "get_monthly_sales_trend") {
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
		} else if (intent === "get_sales_analysis") {
			detail = this._render_sales_analysis(result);
		} else if (intent === "get_payables_analysis") {
			detail = this._render_payables_analysis(result);
		} else if (intent === "get_overdue_invoices") {
			detail = this._render_overdue_analysis(result);
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

		// ── Composite cross-module renderers ──────────────────────────
		} else if (intent === "get_sales_order_dashboard") {
			detail = this._render_sales_order_dashboard(result);
		} else if (intent === "get_so_invoice_gap") {
			detail = this._render_so_invoice_gap(result);
		} else if (intent === "get_sales_pipeline_status") {
			detail = this._render_sales_pipeline_status(result);
		} else if (intent === "get_customer_360") {
			detail = this._render_customer_360(result);
		} else if (intent === "get_po_receipt_gap") {
			detail = this._render_po_receipt_gap(result);
		} else if (intent === "get_monthly_pl_bridge") {
			detail = this._render_monthly_pl_bridge(result);

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
					${isError ? '<span class="ai-result-badge ai-result-badge--error">Error</span>' : (() => {
					const count = result.invoices?.length
						|| result.customers?.length
						|| result.items?.length
						|| result.quotations?.length
						|| result.sales_orders?.length
						|| result.job_cards?.length
						|| result.employees?.length
						|| null;
					const label = count != null ? `${count} records` : `<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Completed`;
					return `<span class="ai-result-badge ai-result-badge--ok">${label}</span>`;
				})()}
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

		let deptHtml = "";
		if (r.department_scores && r.department_scores.length) {
			const badges = r.department_scores.map(d => {
				const cls = {Good:"ai-dept-good", Warning:"ai-dept-warn", Critical:"ai-dept-critical"}[d.status] || "ai-dept-warn";
				return `<div class="ai-dept-badge ${cls}">
					<strong>${frappe.utils.escape_html(d.department)}</strong>
					<span>${d.status}</span>
					<div class="ai-dept-note">${frappe.utils.escape_html(d.note)}</div>
				</div>`;
			}).join("");
			deptHtml = `<div class="ai-bi-section">
				<div class="ai-bi-section-title">🏢 ${__("Department Health")}</div>
				<div class="ai-dept-grid">${badges}</div>
			</div>`;
		}
		const analysisHtml = r.analysis ? this._render_analysis_sections(r.analysis) : "";

		return `<div class="ai-bi-report">
			<div class="ai-kpi-grid">${kpiHtml}</div>
			${recsHtml}
			${topCustHtml}
			${deptHtml}
			${analysisHtml}
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

		// Alerts strip
		let alertsHtml = "";
		if (r.alerts && r.alerts.length) {
			const items = r.alerts.map(a => {
				const cls = a.level === "critical" ? "ai-alert-critical" : a.level === "warning" ? "ai-alert-warning" : "ai-alert-info";
				const icon = a.level === "critical" ? "🔴" : a.level === "warning" ? "⚠️" : "ℹ️";
				return `<div class="ai-alert ${cls}">${icon} ${frappe.utils.escape_html(a.message)}</div>`;
			}).join("");
			alertsHtml = `<div class="ai-alerts-strip">${items}</div>`;
		}

		let chartHtml = "";
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			chartHtml = this._render_chart(r.chart, mountId);
		}

		const analysisHtml = r.analysis ? this._render_analysis_sections(r.analysis) : "";

		return `<div class="ai-bi-report">
			${alertsHtml}
			<div class="ai-summary-greeting">${frappe.utils.escape_html(r.greeting || "Hello")} — ${frappe.utils.escape_html(r.date || "")}</div>
			<div class="ai-bi-section-title">💰 ${__("Sales")}</div>
			<div class="ai-kpi-grid">${kpiHtml}</div>
			${chartHtml}
			<div class="ai-bi-section">
				<div class="ai-bi-section-title">📊 ${__("Key Metrics")}</div>
				<div class="ai-metrics-grid">${metricsRows}</div>
			</div>
			${prioritiesHtml}
			${analysisHtml}
		</div>`;
	}

	_render_sales_trend(r) {
		const fmt = v => this._fmt_currency(v);
		let html = "";

		if (r.metrics) {
			html += this._render_kpi_cards([
				{ label: __("This Month"),   value: fmt(r.metrics.revenue_current_month), danger: false },
				{ label: __("Last Month"),   value: fmt(r.metrics.revenue_prev_month),    danger: false },
				{ label: __("MoM Change"),   value: this._growth_badge(r.metrics.mom_change_pct), danger: r.metrics.mom_change_pct < -10 },
				{ label: __("YTD Revenue"),  value: fmt(r.metrics.revenue_ytd),           danger: false },
				{ label: __("Best Month"),   value: r.metrics.best_month_name || "—",     danger: false },
				{ label: __("Avg Monthly"),  value: fmt(r.metrics.avg_monthly_revenue),   danger: false },
			]);
		} else {
			html += `<div class="ai-kv-grid" style="margin-bottom:10px">
				<div class="ai-kv-row"><span class="ai-kv-label">Current Month</span><span class="ai-kv-val">${fmt(r.current_month_sales)}</span></div>
				<div class="ai-kv-row"><span class="ai-kv-label">vs Last Month</span><span class="ai-kv-val">${this._growth_badge(r.growth_vs_last_month)}</span></div>
			</div>`;
		}

		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mountId);
		}

		if (r.top_customers && r.top_customers.length) {
			const rows = r.top_customers.map(c =>
				`<tr><td>${frappe.utils.escape_html(c.customer)}</td><td class="text-right">${fmt(c.revenue || c.total)}</td><td class="text-right">${c.orders || "—"}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🏆 ${__("Top Customers This Month")}</p>
				<table class="ai-table"><thead><tr><th>${__("Customer")}</th><th class="text-right">${__("Revenue")}</th><th class="text-right">${__("Orders")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}

		if (r.top_items && r.top_items.length) {
			const rows = r.top_items.map(i =>
				`<tr><td>${frappe.utils.escape_html(i.item_name || i.item_code)}</td><td class="text-right">${fmt(i.total_revenue)}</td><td class="text-right">${i.total_qty}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🛍️ ${__("Top Items This Month")}</p>
				<table class="ai-table"><thead><tr><th>${__("Item")}</th><th class="text-right">${__("Revenue")}</th><th class="text-right">${__("Qty")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}

		const trendRows = (r.trend || []).map(m =>
			`<tr><td>${frappe.utils.escape_html(m.month)}</td><td class="text-right">${fmt(m.total_sales)}</td><td class="text-right">${m.invoice_count}</td></tr>`
		).join("");
		if (trendRows) {
			html += `<p style="font-weight:600;margin:10px 0 4px">📅 ${__("Monthly Breakdown")}</p>
				<table class="ai-table"><thead><tr><th>${__("Month")}</th><th class="text-right">${__("Sales")}</th><th class="text-right">${__("Invoices")}</th></tr></thead><tbody>${trendRows}</tbody></table>`;
		}

		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
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

	_render_kpi_cards(kpis) {
		// k.value may be HTML (from frappe.format/frappe.Chart etc.) — render directly.
		// Callers must pre-escape any user-supplied string values before passing here.
		const cards = kpis.map(k =>
			`<div class="ai-kpi-card">
				<div class="ai-kpi-value${k.danger ? " ai-kpi-danger" : ""}">${k.value}</div>
				<div class="ai-kpi-label">${k.label}</div>
			</div>`
		).join("");
		return `<div class="ai-kpi-strip">${cards}</div>`;
	}

	_render_kpi_strip(metrics) {
		const fmt = v => this._fmt_currency(v);
		return this._render_kpi_cards([
			{ label: __("Total Overdue (QAR)"), value: fmt(metrics.total_overdue),        danger: true  },
			{ label: __("Invoices"),             value: metrics.invoice_count,             danger: false },
			{ label: __("Customers Affected"),   value: metrics.customers_affected,        danger: false },
			{ label: __("90+ Days (QAR)"),       value: fmt(metrics.over_90_days),         danger: metrics.over_90_pct > 20 },
			{ label: __("90+ %"),                value: `${metrics.over_90_pct}%`,         danger: metrics.over_90_pct > 20 },
			{ label: __("Top Account %"),        value: `${metrics.worst_customer_pct}%`,  danger: metrics.worst_customer_pct > 30 },
		]);
	}

	// Renders a frappe.Chart into a placeholder div after it is in the DOM.
	_render_chart(chartData, mountId) {
		setTimeout(() => {
			const el = document.getElementById(mountId);
			if (!el || !window.frappe || !frappe.Chart) return;
			try {
				new frappe.Chart(el, {
					type: chartData.type || "bar",
					title: chartData.title || "",
					data: { labels: chartData.labels || [], datasets: chartData.datasets || [] },
					height: 240,
					colors: ["#7C3AED", "#2563EB", "#0D9488", "#EA580C"],
				});
			} catch (_e) {
				el.innerHTML = `<p style="color:var(--text-muted);font-size:0.8rem;padding:8px">${__("Chart unavailable")}</p>`;
			}
		}, 150);
		return `<div id="${mountId}" class="ai-chart"></div>`;
	}

	_render_overdue_analysis(result) {
		const fmt = v => this._fmt_currency(v);
		let html = "";

		// KPI strip — only when enriched metrics are present
		if (result.metrics) {
			html += this._render_kpi_strip(result.metrics);
		} else {
			// Graceful fallback for non-enriched result
			html += `<div class="ai-kv-grid" style="margin-bottom:8px">
				<div class="ai-kv-row"><span class="ai-kv-label">Overdue Count</span><span class="ai-kv-val" style="color:var(--red-500)">${result.overdue_count || 0}</span></div>
				<div class="ai-kv-row"><span class="ai-kv-label">Total Overdue</span><span class="ai-kv-val" style="color:var(--red-500)">${fmt(result.total_overdue_amount)}</span></div>
			</div>`;
		}

		// Aging bar chart
		if (result.chart && result.chart.labels && result.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(result.chart, mountId);
		}

		// Top customers table
		if (result.top_customers && result.top_customers.length) {
			const rows = result.top_customers.map(c =>
				`<tr>
					<td>${frappe.utils.escape_html(c.customer)}</td>
					<td class="text-right">${fmt(c.outstanding)}</td>
					<td class="text-right">${c.pct_of_total}%</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">📊 ${__("Top Customers by Outstanding")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Customer")}</th><th class="text-right">${__("Outstanding")}</th><th class="text-right">${__("% of Total")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}

		// Invoice table (capped at 50 server-side)
		if (result.invoices && result.invoices.length) {
			const invRows = result.invoices.map(i =>
				`<tr>
					<td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
					<td>${frappe.utils.escape_html(i.customer || "")}</td>
					<td class="text-right">${fmt(i.outstanding_amount)}</td>
					<td>${i.due_date || ""}</td>
					<td class="text-right" style="color:var(--red-500)">${i.days_overdue || 0}d</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">⚠️ ${__("Overdue Invoices")} (${result.invoices.length})</p>
				<table class="ai-table">
					<thead><tr><th>${__("Invoice")}</th><th>${__("Customer")}</th><th class="text-right">${__("Outstanding")}</th><th>${__("Due Date")}</th><th class="text-right">${__("Overdue")}</th></tr></thead>
					<tbody>${invRows}</tbody>
				</table>`;
		}

		// AI-interpreted sections — renders only when analysis is present
		if (result.analysis) {
			html += this._render_analysis_sections(result.analysis);
		}

		return html;
	}

		_analysis_text(value) {
			if (value === null || value === undefined) return "";
			if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
				return frappe.utils.escape_html(String(value));
			}
			if (typeof value === "object") {
				const parts = [];
				for (const key of ["title", "action", "business_impact", "expected_impact", "suggested_next_step"]) {
					if (value[key]) parts.push(String(value[key]));
				}
				return frappe.utils.escape_html(parts.join(" — ") || JSON.stringify(value));
			}
			return frappe.utils.escape_html(String(value));
		}

		_analysis_list(items, cls = "") {
			const arr = Array.isArray(items) ? items : (items ? [items] : []);
			if (!arr.length) return "";
			return `<div class="ai-advisory-list ${cls}">
				${arr.map((item, idx) => `<div class="ai-advisory-item">
					<span class="ai-advisory-item-marker">${idx + 1}</span>
					<span>${this._analysis_text(item)}</span>
				</div>`).join("")}
			</div>`;
		}

		_render_analysis_section(className, icon, title, bodyHtml) {
			if (!bodyHtml) return "";
			return `<section class="ai-analysis-section ${className}">
				<div class="ai-analysis-section-header">
					<span class="ai-section-icon-wrap"><i class="${icon}" aria-hidden="true"></i></span>
					<span>${frappe.utils.escape_html(__(title))}</span>
				</div>
				${bodyHtml}
			</section>`;
		}

		_score_pill(score, label) {
			const val = Math.max(0, Math.min(100, parseInt(score || 0, 10) || 0));
			return `<span class="ai-score-pill">${frappe.utils.escape_html(label)} ${val}</span>`;
		}

		_severity_badge(severity) {
			const val = ["low", "medium", "high", "critical"].includes(String(severity).toLowerCase())
				? String(severity).toLowerCase()
				: "medium";
			return `<span class="ai-severity-badge ${val}">${frappe.utils.escape_html(__(val))}</span>`;
		}

		_priority_badge(priority) {
			const val = ["low", "medium", "high", "urgent"].includes(String(priority).toLowerCase())
				? String(priority).toLowerCase()
				: "medium";
			return `<span class="ai-priority-badge ${val}">${frappe.utils.escape_html(__(val))}</span>`;
		}

		_render_risk_cards(risks) {
			const arr = Array.isArray(risks) ? risks : (risks ? [risks] : []);
			if (!arr.length) return "";
			return `<div class="ai-advisory-card-grid">
				${arr.map(risk => {
						if (!risk || typeof risk !== "object") {
							return `<div class="ai-advisory-card risk">
								<div class="ai-advisory-card-top">
									<strong>${frappe.utils.escape_html(__("Business Risk"))}</strong>
									<span class="ai-card-icon danger"><i class="ti ti-alert-triangle" aria-hidden="true"></i></span>
								</div>
								<p>${this._analysis_text(risk)}</p>
						</div>`;
					}
					return `<div class="ai-advisory-card risk">
						<div class="ai-advisory-card-top">
							<strong>${frappe.utils.escape_html(String(risk.title || __("Business Risk")))}</strong>
							<span class="ai-card-icon danger"><i class="ti ti-alert-triangle" aria-hidden="true"></i></span>
						</div>
						<div class="ai-card-meta-row">
							${this._severity_badge(risk.severity)}
							${this._score_pill(risk.risk_score, __("Risk"))}
						</div>
						${risk.business_impact ? `<p>${frappe.utils.escape_html(String(risk.business_impact))}</p>` : ""}
					</div>`;
				}).join("")}
			</div>`;
		}

		_render_opportunity_cards(opportunities) {
			const arr = Array.isArray(opportunities) ? opportunities : (opportunities ? [opportunities] : []);
			if (!arr.length) return "";
			return `<div class="ai-advisory-card-grid">
				${arr.map(opp => {
						if (!opp || typeof opp !== "object") {
							return `<div class="ai-advisory-card opportunity">
								<div class="ai-advisory-card-top">
									<strong>${frappe.utils.escape_html(__("Business Opportunity"))}</strong>
									<span class="ai-card-icon success"><i class="ti ti-trending-up" aria-hidden="true"></i></span>
								</div>
								<p>${this._analysis_text(opp)}</p>
						</div>`;
					}
					return `<div class="ai-advisory-card opportunity">
						<div class="ai-advisory-card-top">
							<strong>${frappe.utils.escape_html(String(opp.title || __("Business Opportunity")))}</strong>
							<span class="ai-card-icon success"><i class="ti ti-trending-up" aria-hidden="true"></i></span>
						</div>
						<div class="ai-card-meta-row">
							${this._score_pill(opp.opportunity_score, __("Score"))}
						</div>
						${opp.expected_impact ? `<p>${frappe.utils.escape_html(String(opp.expected_impact))}</p>` : ""}
					</div>`;
				}).join("")}
			</div>`;
		}

		_render_action_cards(actions) {
			const arr = Array.isArray(actions) ? actions : (actions ? [actions] : []);
			if (!arr.length) return "";
			return `<div class="ai-advisory-card-grid">
				${arr.map(action => {
						if (!action || typeof action !== "object") {
							return `<div class="ai-advisory-card action">
								<div class="ai-advisory-card-top">
									<strong>${frappe.utils.escape_html(__("Required Action"))}</strong>
									<span class="ai-card-icon action"><i class="ti ti-player-play" aria-hidden="true"></i></span>
								</div>
								<p>${this._analysis_text(action)}</p>
						</div>`;
					}
					const doctype = action.related_doctype ? frappe.utils.escape_html(String(action.related_doctype)) : "";
					const doc = action.related_document ? frappe.utils.escape_html(String(action.related_document)) : "";
					const related = doctype || doc ? `<span class="ai-related-doc">${doctype}${doc ? `: ${doc}` : ""}</span>` : "";
					return `<div class="ai-advisory-card action">
						<div class="ai-advisory-card-top">
							<strong>${frappe.utils.escape_html(String(action.action || __("Required Action")))}</strong>
							<span class="ai-card-icon action"><i class="ti ti-player-play" aria-hidden="true"></i></span>
						</div>
						<div class="ai-card-meta-row">
							${this._priority_badge(action.priority)}
						</div>
						<div class="ai-action-meta">
							${action.owner_role ? `<span>${frappe.utils.escape_html(__("Owner"))}: ${frappe.utils.escape_html(String(action.owner_role))}</span>` : ""}
							${related}
						</div>
						${action.suggested_next_step ? `<p>${frappe.utils.escape_html(String(action.suggested_next_step))}</p>` : ""}
					</div>`;
				}).join("")}
			</div>`;
		}

		// Generic renderer for advisory analysis. Supports the new structured
		// object schema and the legacy four string-array format.
		_render_analysis_sections(analysis) {
			if (!analysis) return "";
			let rendered = 0;
			let topHtml = "";
			let leftHtml = "";
			let rightHtml = "";
			let bottomHtml = "";

			if (analysis.executive_summary) {
				topHtml += this._render_analysis_section(
					"executive-summary",
					"ti ti-briefcase",
					"Executive Summary",
					`<p class="ai-advisory-summary">${frappe.utils.escape_html(String(analysis.executive_summary))}</p>`
				);
				rendered++;
			}
			if (analysis.findings?.length) {
				leftHtml += this._render_analysis_section(
					"findings",
					"ti ti-search",
					"Findings",
					this._analysis_list(analysis.findings, "finding-list")
				);
				rendered++;
			}
			if (analysis.root_causes?.length) {
				leftHtml += this._render_analysis_section(
					"root-causes",
					"ti ti-git-branch",
					"Root Causes",
					this._analysis_list(analysis.root_causes, "root-cause-list")
				);
				rendered++;
			}
			if (analysis.risks?.length) {
				rightHtml += this._render_analysis_section(
					"risks",
					"ti ti-alert-triangle",
					"Risks",
					this._render_risk_cards(analysis.risks)
				);
				rendered++;
			}
			if (analysis.opportunities?.length) {
				rightHtml += this._render_analysis_section(
					"opportunities",
					"ti ti-trending-up",
					"Opportunities",
					this._render_opportunity_cards(analysis.opportunities)
				);
				rendered++;
			}
			if (analysis.recommendations?.length) {
				leftHtml += this._render_analysis_section(
					"recommendations",
					"ti ti-bulb",
					"Recommendations",
					this._analysis_list(analysis.recommendations, "recommendation-list")
				);
				rendered++;
			}
			if (analysis.required_actions?.length) {
				rightHtml += this._render_analysis_section(
					"required-actions",
					"ti ti-player-play",
					"Required Actions",
					this._render_action_cards(analysis.required_actions)
				);
				rendered++;
			}
			if (analysis.expected_business_impact) {
				bottomHtml += this._render_analysis_section(
					"expected-impact",
					"ti ti-target-arrow",
					"Expected Business Impact",
					`<p class="ai-advisory-summary">${frappe.utils.escape_html(String(analysis.expected_business_impact))}</p>`
				);
				rendered++;
			}
			if (!rendered) return "";
			const gridHtml = (leftHtml || rightHtml)
				? `<div class="ai-mi-grid">
					<div class="ai-mi-column">${leftHtml}</div>
					<div class="ai-mi-column">${rightHtml}</div>
				</div>`
				: "";
			return `<div class="ai-analysis-sections ai-advisory-sections ai-mi-report">
				${topHtml}
				${gridHtml}
				${bottomHtml}
			</div>`;
		}

	_render_sales_order_dashboard(r) {
		const fmt  = v => this._fmt_currency(v);
		const m    = r.metrics || {};
		const data = r.data    || {};
		let html   = "";

		// ── KPI strip ─────────────────────────────────
		html += this._render_kpi_cards([
			{
				label:  __("Open Orders"),
				value:  m.open_orders_count || 0,
				danger: false,
			},
			{
				label:  __("Open Value"),
				value:  fmt(m.open_orders_value),
				danger: false,
			},
			{
				label:  __("Not Invoiced"),
				value:  m.not_invoiced_count || 0,
				danger: (m.not_invoiced_count || 0) > 0,
			},
			{
				label:  __("Revenue at Risk"),
				value:  fmt(m.gap_value),
				danger: (m.gap_value || 0) > 0,
			},
			{
				label:  __("MTD Revenue"),
				value:  fmt(m.mtd_revenue),
				danger: false,
			},
			{
				label:  __("MTD Invoices"),
				value:  m.mtd_invoices || 0,
				danger: false,
			},
			{
				label:  __("Overdue Invoices"),
				value:  m.overdue_count || 0,
				danger: (m.overdue_count || 0) > 0,
			},
		]);

		// ── Status breakdown pills ────────────────────
		const breakdown = data.status_breakdown || {};
		if (Object.keys(breakdown).length) {
			const sColor = s =>
				s === "To Deliver and Bill" ? "var(--orange-500)" :
				s === "To Bill"             ? "var(--blue-500)"   :
				s === "To Deliver"          ? "var(--yellow-500)" :
				s === "Partly Billed"       ? "var(--purple-500)" :
				                              "var(--text-muted)";
			const pills = Object.entries(breakdown)
				.map(([s, n]) =>
					`<span style="display:inline-flex;align-items:center;
					  gap:5px;background:var(--bg-color);
					  border:1px solid var(--border-color);
					  border-radius:20px;padding:3px 10px;
					  font-size:0.75rem;margin:2px;">
					  <span style="width:8px;height:8px;border-radius:50%;
					    background:${sColor(s)};flex-shrink:0;"></span>
					  <strong>${frappe.utils.escape_html(s)}</strong>
					  &nbsp;${n}
					</span>`
				).join("");
			html += `<div style="margin:8px 0 4px">
				<p style="font-weight:600;font-size:0.8rem;
				          margin-bottom:6px">
				  📦 ${__("Order Status Breakdown")}
				</p>
				<div>${pills}</div>
			</div>`;
		}

		// ── Revenue chart ─────────────────────────────
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mid = "ai-chart-" + Date.now() +
			            "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mid);
		}

		// ── Top customers table ───────────────────────
		const topCx = data.top_customers || [];
		if (topCx.length) {
			const rows = topCx.map((cx, i) =>
				`<tr>
					<td style="font-weight:600;
					           color:var(--text-muted)">#${i + 1}</td>
					<td><a href="/app/customer/${
					    encodeURIComponent(cx.customer)}"
					    target="_blank">
					  ${frappe.utils.escape_html(cx.customer || "")}
					</a></td>
					<td class="text-right">${fmt(cx.revenue)}</td>
					<td class="text-right">${cx.orders || 0}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:12px 0 4px">
				🏆 ${__("Top Customers This Month")}
			</p>
			<table class="ai-table">
				<thead><tr>
					<th>#</th>
					<th>${__("Customer")}</th>
					<th class="text-right">${__("Revenue")}</th>
					<th class="text-right">${__("Orders")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>`;
		}

		// ── Open orders table ─────────────────────────
		const openOrders = data.open_orders || [];
		if (openOrders.length) {
			const sColor = s =>
				s === "To Deliver and Bill" ? "var(--orange-500)" :
				s === "To Bill"             ? "var(--blue-500)"   :
				s === "To Deliver"          ? "var(--yellow-500)" :
				s === "Partly Billed"       ? "var(--purple-500)" :
				                              "var(--text-muted)";
			const capped = openOrders.slice(0, 15);
			const rows   = capped.map(o =>
				`<tr>
					<td><a href="/app/sales-order/${
					    encodeURIComponent(o.name)}"
					    target="_blank">
					  ${frappe.utils.escape_html(o.name || "")}
					</a></td>
					<td>${frappe.utils.escape_html(o.customer || "")}</td>
					<td>${o.transaction_date || ""}</td>
					<td>${o.delivery_date   || ""}</td>
					<td class="text-right">${fmt(o.grand_total)}</td>
					<td class="text-right">
					  ${Math.round(o.per_billed || 0)}%
					</td>
					<td style="color:${sColor(o.status)};
					           font-weight:600;font-size:0.75rem">
					  ${frappe.utils.escape_html(o.status || "")}
					</td>
				</tr>`
			).join("");
			const note = openOrders.length > 15
				? `<p style="font-size:0.75rem;
				             color:var(--text-muted);margin-top:4px">
				     ${__("Showing 15 of")} ${openOrders.length}
				     ${__("orders")}
				   </p>`
				: "";
			html += `<p style="font-weight:600;margin:12px 0 4px">
				📋 ${__("Open Sales Orders")}
			</p>
			<table class="ai-table">
				<thead><tr>
					<th>${__("Order")}</th>
					<th>${__("Customer")}</th>
					<th>${__("Date")}</th>
					<th>${__("Delivery")}</th>
					<th class="text-right">${__("Value")}</th>
					<th class="text-right">${__("Billed %")}</th>
					<th>${__("Status")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>${note}`;
		}

		// ── Not invoiced table ────────────────────────
		const notInv = data.not_invoiced || [];
		if (notInv.length) {
			const capped = notInv.slice(0, 10);
			const rows   = capped.map(o =>
				`<tr>
					<td><a href="/app/sales-order/${
					    encodeURIComponent(o.name)}"
					    target="_blank">
					  ${frappe.utils.escape_html(o.name || "")}
					</a></td>
					<td>${frappe.utils.escape_html(o.customer || "")}</td>
					<td>${o.transaction_date || ""}</td>
					<td class="text-right"
					    style="color:var(--red-500);font-weight:600">
					  ${fmt(o.grand_total)}
					</td>
					<td class="text-right">
					  ${Math.round(o.per_billed || 0)}%
					</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:12px 0 4px;
			                   color:var(--red-500)">
				⚠️ ${__("Orders Not Yet Invoiced — Revenue at Risk")}
			</p>
			<table class="ai-table">
				<thead><tr>
					<th>${__("Order")}</th>
					<th>${__("Customer")}</th>
					<th>${__("Date")}</th>
					<th class="text-right">${__("Value")}</th>
					<th class="text-right">${__("Billed %")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>`;
		}

		// ── AI analysis sections ──────────────────────
		if (r.analysis) {
			html += this._render_analysis_sections(r.analysis);
		}

		return html;
	}

	_render_so_invoice_gap(r) {
		const fmt = v => this._fmt_currency(v);
		const m = r.metrics || {};
		let html = "";
		if (r.multi_currency) {
			html += `<div class="ai-multicurrency-banner">ℹ️ ${__("Amounts shown in base currency equivalent. Original transaction currencies vary.")}</div>`;
		}
		html += this._render_kpi_cards([
			{ label: __("Total Orders"),         value: m.total_orders || 0,                  danger: false },
			{ label: __("Not Invoiced"),         value: m.not_invoiced_count || 0,            danger: (m.not_invoiced_count || 0) > 0 },
			{ label: __("Revenue Not Invoiced"), value: fmt(m.not_invoiced_value),            danger: (m.not_invoiced_value || 0) > 0 },
			{ label: __("Invoiced Unpaid"),      value: m.invoiced_unpaid_count || 0,         danger: false },
			{ label: __("Unpaid Amount"),        value: fmt(m.invoiced_unpaid_value),         danger: false },
			{ label: __("Total At Risk"),        value: fmt(m.value_at_risk),                 danger: (m.value_at_risk || 0) > 0 },
			{ label: __("Gap Percentage"),       value: `${m.collection_gap_pct || 0}%`,      danger: (m.collection_gap_pct || 0) > 20 },
		]);
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mountId);
		}
		if (r.data && r.data.length) {
			const capped = r.data.slice(0, 15);
			const statusColor = s => s === "Not Invoiced" ? "var(--red-500)" : s === "Invoiced Unpaid" ? "var(--orange-500)" : "var(--green-600)";
			const rows = capped.map(row =>
				`<tr>
					<td><a href="/app/sales-order/${encodeURIComponent(row.name)}" target="_blank">${row.name}</a></td>
					<td>${frappe.utils.escape_html(row.customer || "")}</td>
					<td>${row.transaction_date || ""}</td>
					<td class="text-right">${fmt(row.base_grand_total)}</td>
					<td>${frappe.utils.escape_html(row.currency || "")}</td>
					<td style="color:${statusColor(row.invoice_status)};font-weight:600">${frappe.utils.escape_html(row.invoice_status || "")}</td>
				</tr>`
			).join("");
			const note = r.data.length > 15
				? `<p style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">${__("Showing 15 of")} ${r.data.length} ${__("orders")}</p>`
				: "";
			html += `<p style="font-weight:600;margin:10px 0 4px">📋 ${__("Sales Orders — Revenue Gap")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Order")}</th><th>${__("Customer")}</th><th>${__("Date")}</th><th class="text-right">${__("Amount")}</th><th>${__("Currency")}</th><th>${__("Status")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>${note}`;
		}
		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
	}

	_render_sales_pipeline_status(r) {
		const fmt = v => this._fmt_currency(v);
		const m = r.metrics || {};
		let html = "";
		if (r.multi_currency) {
			html += `<div class="ai-multicurrency-banner">ℹ️ ${__("Amounts shown in base currency equivalent. Original transaction currencies vary.")}</div>`;
		}
		html += this._render_kpi_cards([
			{ label: __("Total Quotes"),     value: m.total_quotes || 0,                     danger: false },
			{ label: __("Quote to Order"),   value: `${m.quote_to_order_pct || 0}%`,         danger: (m.quote_to_order_pct || 0) < 20 },
			{ label: __("Order to Invoice"), value: `${m.order_to_invoice_pct || 0}%`,       danger: false },
			{ label: __("Invoice to Paid"),  value: `${m.invoice_to_paid_pct || 0}%`,        danger: false },
			{ label: __("Quote to Cash"),    value: `${m.quote_to_cash_pct || 0}%`,          danger: (m.quote_to_cash_pct || 0) < 10 },
			{ label: __("Avg Days Q→O"),     value: `${m.avg_days_quote_to_order || 0}d`,    danger: false },
			{ label: __("Avg Days O→I"),     value: `${m.avg_days_order_to_invoice || 0}d`,  danger: false },
		]);
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mountId);
		}
		if (r.data && r.data.length) {
			const rows = r.data.map(q =>
				`<tr>
					<td><a href="/app/quotation/${encodeURIComponent(q.name)}" target="_blank">${q.name}</a></td>
					<td>${frappe.utils.escape_html(q.party_name || "")}</td>
					<td>${q.transaction_date || ""}</td>
					<td class="text-right">${fmt(q.base_grand_total)}</td>
					<td class="text-right" style="color:var(--orange-500)">${q.days_open || 0}d</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">📄 ${__("Top Open Unconverted Quotations")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Quote")}</th><th>${__("Customer")}</th><th>${__("Date")}</th><th class="text-right">${__("Value")}</th><th class="text-right">${__("Days Open")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
	}

	_render_customer_360(r) {
		const fmt = v => this._fmt_currency(v);
		const m = r.metrics || {};
		let html = "";
		if (r.multi_currency) {
			html += `<div class="ai-multicurrency-banner">ℹ️ ${__("Amounts shown in base currency equivalent. Original transaction currencies vary.")}</div>`;
		}
		const healthColor = h => h === "Good" ? "var(--green-600)" : h === "Warning" ? "var(--orange-500)" : "var(--red-500)";
		html += this._render_kpi_cards([
			{ label: __("Revenue"),          value: fmt(m.total_revenue),          danger: false },
			{ label: __("Outstanding"),      value: fmt(m.total_outstanding),       danger: (m.total_outstanding || 0) > 0 },
			{ label: __("Overdue"),          value: fmt(m.overdue_amount),          danger: (m.overdue_amount || 0) > 0 },
			{ label: __("Open Orders"),      value: m.open_orders_count || 0,       danger: false },
			{ label: __("Open Quotes"),      value: m.open_quotes_count || 0,       danger: false },
			{ label: __("Avg Payment Days"), value: m.avg_payment_delay_days != null ? `${m.avg_payment_delay_days}d` : "—", danger: false },
			{ label: __("Health Status"),    value: `<span style="color:${healthColor(m.customer_health)};font-weight:700">${frappe.utils.escape_html(m.customer_health || "—")}</span>`, danger: false },
		]);
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mountId);
		}
		const d = r.data || {};
		if (d.open_orders && d.open_orders.length) {
			const rows = d.open_orders.map(o =>
				`<tr>
					<td><a href="/app/sales-order/${encodeURIComponent(o.name)}" target="_blank">${o.name}</a></td>
					<td>${o.transaction_date || ""}</td>
					<td class="text-right">${fmt(o.base_grand_total)}</td>
					<td>${frappe.utils.escape_html(o.status || "")}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">📦 ${__("Open Orders")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Order")}</th><th>${__("Date")}</th><th class="text-right">${__("Value")}</th><th>${__("Status")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (d.unpaid_invoices && d.unpaid_invoices.length) {
			const rows = d.unpaid_invoices.map(i =>
				`<tr>
					<td><a href="/app/sales-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
					<td>${i.posting_date || ""}</td>
					<td class="text-right">${fmt(i.outstanding_amount)}</td>
					<td>${i.due_date || ""}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">💰 ${__("Unpaid Invoices")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Invoice")}</th><th>${__("Date")}</th><th class="text-right">${__("Outstanding")}</th><th>${__("Due Date")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (d.top_items && d.top_items.length) {
			const rows = d.top_items.map(it =>
				`<tr>
					<td>${frappe.utils.escape_html(it.item_name || it.item_code || "")}</td>
					<td class="text-right">${(it.total_qty || 0).toFixed(1)}</td>
					<td class="text-right">${fmt(it.total_amount)}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🛍️ ${__("Top Items Purchased")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Item")}</th><th class="text-right">${__("Qty")}</th><th class="text-right">${__("Revenue")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
	}

	_render_po_receipt_gap(r) {
		const fmt = v => this._fmt_currency(v);
		const m = r.metrics || {};
		let html = "";
		if (r.multi_currency) {
			html += `<div class="ai-multicurrency-banner">ℹ️ ${__("Amounts shown in base currency equivalent. Original transaction currencies vary.")}</div>`;
		}
		html += this._render_kpi_cards([
			{ label: __("Open POs"),         value: m.total_open_pos || 0,         danger: false },
			{ label: __("Not Received"),     value: m.not_received_count || 0,      danger: (m.not_received_count || 0) > 0 },
			{ label: __("Value Pending"),    value: fmt(m.not_received_value),       danger: false },
			{ label: __("Avg Days Overdue"), value: `${m.avg_days_overdue || 0}d`,  danger: (m.avg_days_overdue || 0) > 14 },
			{ label: __("Stockout Risk"),    value: m.stockout_risk_count || 0,      danger: (m.stockout_risk_count || 0) > 0 },
			{ label: __("Total Exposure"),   value: fmt(m.total_exposure_value),     danger: false },
		]);
		if (r.chart && r.chart.labels && r.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(r.chart, mountId);
		}
		if (r.data && r.data.length) {
			const overdueColor = d => d > 14 ? "var(--red-500)" : d > 0 ? "var(--orange-500)" : "var(--green-600)";
			const rows = r.data.map(row =>
				`<tr>
					<td><a href="/app/purchase-order/${encodeURIComponent(row.name)}" target="_blank">${row.name}</a></td>
					<td>${frappe.utils.escape_html(row.supplier || "")}</td>
					<td>${row.schedule_date || ""}</td>
					<td class="text-right" style="color:${overdueColor(row.days_overdue)};font-weight:600">${row.days_overdue || 0}d</td>
					<td class="text-right">${fmt(row.base_grand_total)}</td>
					<td>${frappe.utils.escape_html(row.receipt_status || "")}</td>
					<td style="text-align:center">${row.stockout_risk ? '<span style="color:var(--red-500)" title="Stockout Risk">⚠️</span>' : ""}</td>
				</tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🚚 ${__("Purchase Orders Pending Receipt")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("PO")}</th><th>${__("Supplier")}</th><th>${__("Expected Date")}</th><th class="text-right">${__("Days Overdue")}</th><th class="text-right">${__("Value")}</th><th>${__("Status")}</th><th>${__("Stockout")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
	}

	_render_monthly_pl_bridge(r) {
		const fmt = v => this._fmt_currency(v);
		const m = r.metrics || {};
		let html = "";
		if (r.multi_currency) {
			html += `<div class="ai-multicurrency-banner">ℹ️ ${__("Amounts shown in base currency equivalent. Original transaction currencies vary.")}</div>`;
		}
		const momBadge = v => {
			if (v == null) return "—";
			const sign = v >= 0 ? "+" : "";
			const color = v >= 0 ? "var(--green-600)" : "var(--red-500)";
			return `<span style="color:${color};font-weight:700">${sign}${v}%</span>`;
		};
		html += this._render_kpi_cards([
			{ label: __("Revenue"),      value: fmt(m.current_month_revenue),        danger: false },
			{ label: __("Cost"),         value: fmt(m.current_month_cost),           danger: false },
			{ label: __("Gross Profit"), value: fmt(m.current_month_gross_profit),   danger: false },
			{ label: __("Margin"),       value: `${m.current_month_margin_pct || 0}%`, danger: (m.current_month_margin_pct || 0) < 15 },
			{ label: __("Revenue MoM"),  value: momBadge(m.revenue_mom_pct),         danger: false },
			{ label: __("Cost MoM"),     value: momBadge(m.cost_mom_pct),            danger: false },
			{ label: __("Margin MoM"),   value: momBadge(m.margin_mom_pct),          danger: false },
			{ label: __("YTD Revenue"),  value: fmt(m.ytd_revenue),                  danger: false },
			{ label: __("YTD Profit"),   value: fmt(m.ytd_gross_profit),             danger: false },
		]);
		if (r.chart) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			if (r.chart.type === "composed") {
				html += this._render_composed_chart(r.chart, mountId);
			} else if (r.chart.labels && r.chart.labels.length) {
				html += this._render_chart(r.chart, mountId);
			}
		}
		if (r.data && r.data.length) {
			const currentLabel = r.data[r.data.length - 1]?.month_label;
			const rows = r.data.map(row => {
				const isCurrent = row.month_label === currentLabel;
				const rowStyle = isCurrent ? ' style="background:var(--blue-50,#eff6ff);font-weight:600"' : "";
				return `<tr${rowStyle}>
					<td>${frappe.utils.escape_html(row.month_label || "")}</td>
					<td class="text-right">${fmt(row.revenue)}</td>
					<td class="text-right">${fmt(row.cost)}</td>
					<td class="text-right">${fmt(row.gross_profit)}</td>
					<td class="text-right">${row.margin_pct || 0}%</td>
					<td style="text-align:center">${row.margin_squeeze ? '<span style="color:var(--red-500)" title="Margin Squeeze">⚠️</span>' : ""}</td>
				</tr>`;
			}).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">📅 ${__("Monthly Breakdown")}</p>
				<table class="ai-table">
					<thead><tr><th>${__("Month")}</th><th class="text-right">${__("Revenue")}</th><th class="text-right">${__("Cost")}</th><th class="text-right">${__("Gross Profit")}</th><th class="text-right">${__("Margin %")}</th><th>${__("Squeeze")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>`;
		}
		if (r.analysis) html += this._render_analysis_sections(r.analysis);
		return html;
	}

	_render_composed_chart(chartData, mountId) {
		// frappe.Chart axis-mixed: per-dataset chartType "bar" or "line"
		setTimeout(() => {
			const el = document.getElementById(mountId);
			if (!el || !window.frappe || !frappe.Chart) return;
			const datasets = (chartData.datasets || []).map(ds => ({
				name: ds.name,
				chartType: ds.type || "bar",
				values: ds.values || [],
			}));
			try {
				new frappe.Chart(el, {
					type: "axis-mixed",
					title: chartData.title || "",
					data: { labels: chartData.labels || [], datasets },
					height: 260,
					colors: ["#2563EB", "#EA580C", "#16a34a"],
				});
			} catch (_e) {
				el.innerHTML = `<p style="color:var(--text-muted);font-size:0.8rem;padding:8px">${__("Chart unavailable")}</p>`;
			}
		}, 150);
		return `<div id="${mountId}" class="ai-chart"></div>`;
	}

	_render_sales_summary(result) {
		const fmt = v => this._fmt_currency(v);
		if (!result.metrics) return this._render_summary_card(result);
		let html = this._render_kpi_cards([
			{ label: __("Revenue"),         value: fmt(result.metrics.total_revenue),       danger: false },
			{ label: __("Orders"),          value: result.metrics.total_orders,             danger: false },
			{ label: __("Avg Order Value"), value: fmt(result.metrics.avg_order_value),     danger: false },
			{ label: __("vs Prev Period"),  value: this._growth_badge(result.metrics.revenue_vs_prev_pct), danger: result.metrics.revenue_vs_prev_pct < -10 },
			{ label: __("Top Customer"),    value: frappe.utils.escape_html(result.metrics.top_customer || "—"), danger: false },
			{ label: __("Top Item"),        value: frappe.utils.escape_html(result.metrics.top_item || "—"),     danger: false },
		]);
		if (result.chart && result.chart.labels) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(result.chart, mountId);
		}
		if (result.top_customers && result.top_customers.length) {
			const rows = result.top_customers.map(c =>
				`<tr><td>${frappe.utils.escape_html(c.customer)}</td><td class="text-right">${fmt(c.total || c.revenue)}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:8px 0 4px">🏆 ${__("Top Customers")}</p>
				<table class="ai-table"><thead><tr><th>${__("Customer")}</th><th class="text-right">${__("Revenue")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.analysis) html += this._render_analysis_sections(result.analysis);
		return html;
	}

	_render_sales_analysis(result) {
		const fmt = v => this._fmt_currency(v);
		let html = "";
		if (result.metrics) {
			html += this._render_kpi_cards([
				{ label: __("Revenue MTD"),      value: fmt(result.metrics.total_revenue_mtd),     danger: false },
				{ label: __("Orders MTD"),       value: result.metrics.total_orders_mtd,           danger: false },
				{ label: __("Avg Deal Size"),    value: fmt(result.metrics.avg_deal_size),         danger: false },
				{ label: __("Conversion Rate"),  value: `${result.metrics.conversion_rate_pct}%`,  danger: result.metrics.conversion_rate_pct < 20 },
				{ label: __("New Customers"),    value: result.metrics.new_customers_mtd,          danger: false },
				{ label: __("Returning"),        value: result.metrics.returning_customers_mtd,    danger: false },
			]);
		}
		if (result.chart && result.chart.labels && result.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(result.chart, mountId);
		}
		if (result.by_salesperson && result.by_salesperson.length) {
			const rows = result.by_salesperson.map(s =>
				`<tr><td>${frappe.utils.escape_html(s.salesperson)}</td><td class="text-right">${fmt(s.revenue)}</td><td class="text-right">${s.orders}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">👤 ${__("Revenue by Salesperson")}</p>
				<table class="ai-table"><thead><tr><th>${__("Salesperson")}</th><th class="text-right">${__("Revenue")}</th><th class="text-right">${__("Orders")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.top_customers && result.top_customers.length) {
			const rows = result.top_customers.map(c =>
				`<tr><td>${frappe.utils.escape_html(c.customer)}</td><td class="text-right">${fmt(c.revenue)}</td><td class="text-right">${c.orders}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🏆 ${__("Top Customers MTD")}</p>
				<table class="ai-table"><thead><tr><th>${__("Customer")}</th><th class="text-right">${__("Revenue")}</th><th class="text-right">${__("Orders")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.analysis) html += this._render_analysis_sections(result.analysis);
		return html;
	}

	_render_payables_analysis(result) {
		const fmt = v => this._fmt_currency(v);
		let html = "";
		if (result.metrics) {
			html += this._render_kpi_cards([
				{ label: __("Total Payable (QAR)"), value: fmt(result.metrics.total_payable),      danger: false },
				{ label: __("Invoices"),             value: result.metrics.invoice_count,           danger: false },
				{ label: __("Suppliers"),            value: result.metrics.suppliers_affected,      danger: false },
				{ label: __("90+ Days (QAR)"),       value: fmt(result.metrics.over_90_days),       danger: result.metrics.over_90_pct > 20 },
				{ label: __("90+ %"),                value: `${result.metrics.over_90_pct}%`,       danger: result.metrics.over_90_pct > 20 },
				{ label: __("Due in 7 Days"),        value: fmt(result.metrics.due_next_7_days),    danger: true },
			]);
		}
		if (result.chart && result.chart.labels && result.chart.labels.length) {
			const mountId = "ai-chart-" + Date.now() + "-" + Math.floor(Math.random() * 9999);
			html += this._render_chart(result.chart, mountId);
		}
		if (result.upcoming_due && result.upcoming_due.length) {
			const rows = result.upcoming_due.map(i =>
				`<tr><td><a href="/app/purchase-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a></td>
				<td>${frappe.utils.escape_html(i.supplier || "")}</td>
				<td>${i.due_date || ""}</td>
				<td class="text-right">${fmt(i.outstanding_amount)}</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">📅 ${__("Due in Next 7 Days")}</p>
				<table class="ai-table"><thead><tr><th>${__("Invoice")}</th><th>${__("Supplier")}</th><th>${__("Due Date")}</th><th class="text-right">${__("Amount")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.top_suppliers && result.top_suppliers.length) {
			const rows = result.top_suppliers.map(s =>
				`<tr><td>${frappe.utils.escape_html(s.supplier)}</td><td class="text-right">${fmt(s.outstanding)}</td><td class="text-right">${s.pct_of_total}%</td></tr>`
			).join("");
			html += `<p style="font-weight:600;margin:10px 0 4px">🏭 ${__("Top Suppliers by Outstanding")}</p>
				<table class="ai-table"><thead><tr><th>${__("Supplier")}</th><th class="text-right">${__("Outstanding")}</th><th class="text-right">${__("% of Total")}</th></tr></thead><tbody>${rows}</tbody></table>`;
		}
		if (result.analysis) html += this._render_analysis_sections(result.analysis);
		return html;
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

	// ── Agent selector ────────────────────────────────────────────────────────

	_load_agents() {
		// Non-System Manager: hide the agent bar entirely, lock to general
		if (!frappe.user.has_role("System Manager")) {
			$("#ai-agent-bar").hide();
			this.current_agent = "general";
			return;
		}
		frappe.call({
			method: "ai_assistant.api.chat.get_agents",
			callback: (r) => {
				if (r.message && r.message.length) {
					this.agents = r.message;
					this._render_agent_bar(r.message);
				}
			},
		});
	}

	_render_agent_bar(agents) {
		const agentSvgMap = {
			"supervisor":                  `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>`,
			"sales":                       `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>`,
			"sales agent":                 `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>`,
			"marketing":                   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
			"marketing agent":             `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
			"accounts":                    `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
			"accounts agent":              `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
			"operations":                  `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>`,
			"operations agent":            `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>`,
			"business intelligence":       `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
			"business intelligence agent": `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
			"hr":                          `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
			"hr agent":                    `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>`,
		};
		const defaultPillSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>`;

		const pills = agents.map(a => {
			const isActive = a.agent_code === this.current_agent;
			const agentKey = (
				a.agent_code ||
				a.agent_name ||
				a.name ||
				""
			).toLowerCase().trim();
			const pillSvg = agentSvgMap[agentKey] || defaultPillSvg;
			return `<button class="ai-agent-pill${isActive ? " active" : ""}"
				data-agent="${frappe.utils.escape_html(a.agent_code)}"
				style="--agent-color: ${frappe.utils.escape_html(a.color || "#2563eb")}"
				title="${frappe.utils.escape_html(a.description || a.agent_name)}">
				<span class="ai-agent-pill-icon">${pillSvg}</span>
				<span class="ai-agent-pill-name">${frappe.utils.escape_html(a.agent_name)}</span>
			</button>`;
		}).join("");
		$("#ai-agent-bar").html(`<div class="ai-agent-pills">${pills}</div>`);
	}

	_switch_agent(agent_code) {
		const agent = (this.agents || []).find(a => a.agent_code === agent_code);
		if (!agent) return;

		this.current_agent = agent_code;
		this._render_agent_bar(this.agents);

		// Update header avatar and title
		$("#ai-agent-avatar").text(agent.icon || "🤖");
		$("#ai-agent-title").text(agent.agent_name || __("AI Assistant"));

		// Show a system message in chat
		const switchMsg = `${agent.icon || "🤖"} ${__("Switched to")} <strong>${frappe.utils.escape_html(agent.agent_name)}</strong>`;
		const $systemMsg = $(`
			<div class="ai-system-msg">
				${switchMsg}
			</div>
		`);
		this.$messages.append($systemMsg);
		this._scroll_to_bottom();
	}

	// Updates active agent state + header without injecting a chat message.
	// Used by auto-routing so the routing note row acts as the announcement.
	_switch_agent_silent(agent_code, agent_name, icon) {
		this.current_agent = agent_code;
		if (this.agents && this.agents.length) {
			this._render_agent_bar(this.agents);
		}
		$("#ai-agent-avatar").text(icon || "🤖");
		$("#ai-agent-title").text(agent_name || __("AI Assistant"));
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

// ──────────────────────────────────────────────────────────────────────────────
// VoiceInput — self-contained speech-to-text, fed into existing send flow
// ──────────────────────────────────────────────────────────────────────────────

class VoiceInput {
	constructor(chatPage) {
		this._chat        = chatPage;
		this._recog       = null;
		this._recording   = false;
		this._errTimer    = null;
		this._lang        = this._detect_lang();
		this._supported   = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
		this._use_paid_api = false;   // set to true when a paid STT provider is configured
		this._mr          = null;     // MediaRecorder instance (paid API mode)
		this._stream      = null;     // MediaStream (paid API mode)
		this._chunks      = [];       // recorded audio chunks (paid API mode)
		this._init();
	}

	// Priority: localStorage > frappe.boot.lang > session.user_lang > html[lang] > en
	_detect_lang() {
		const saved = localStorage.getItem("ai_assistant_voice_lang");
		if (saved) return saved;
		if (frappe.boot && frappe.boot.lang) return frappe.boot.lang;
		if (frappe.session && frappe.session.user_lang) return frappe.session.user_lang;
		const htmlLang = document.documentElement.lang;
		if (htmlLang) return htmlLang;
		return "en";
	}

	_recognition_lang() {
		const l = (this._lang || "en").toLowerCase();
		if (l.startsWith("ar")) return "ar-SA";
		if (l.startsWith("ur")) return "ur-PK";
		if (l.startsWith("en")) return "en-US";
		return this._lang; // pass through; falls back to en-US on recognition error
	}

	_lang_code() {
		const l = (this._lang || "en").toLowerCase();
		if (l.startsWith("ar")) return "AR";
		if (l.startsWith("ur")) return "UR";
		return "EN";
	}

	_status_text() {
		const l = (this._lang || "en").toLowerCase();
		if (l.startsWith("ar")) return "يستمع";
		if (l.startsWith("ur")) return "سن رہا ہے";
		return "Listening";
	}

	_error_msg(code) {
		const l = (this._lang || "en").toLowerCase();
		const isAr = l.startsWith("ar");
		const isUr = l.startsWith("ur");
		const tbl = {
			"no-speech":   { en: "No speech detected, please try again",                                 ar: "لم يتم الكشف عن كلام",         ur: "کوئی آواز نہیں ملی"        },
			"not-allowed": { en: "Microphone access denied, please allow microphone in browser settings", ar: "تم رفض الوصول إلى الميكروفون", ur: "مائیکروفون کی اجازت نہیں"  },
			"network":     { en: "Voice recognition unavailable, please check your connection",           ar: "التعرف على الصوت غير متاح",     ur: "آواز کی پہچان دستیاب نہیں" },
		};
		const entry = tbl[code];
		if (entry) return isAr ? entry.ar : isUr ? entry.ur : entry.en;
		return isAr ? "خطأ في إدخال الصوت" : isUr ? "آواز کی غلطی" : "Voice input error, please try again";
	}

	_apply_direction() {
		const rtl = this._recognition_lang() === "ar-SA";
		this._chat.$input.css({
			direction:  rtl ? "rtl" : "ltr",
			fontFamily: rtl ? "system-ui, Arial, sans-serif" : "",
		});
	}

	_update_lang_btn() {
		const code = this._lang_code();
		$("#ai-lang-toggle").attr("title", code).find(".ai-lang-label").text(code);
		this._apply_direction();
	}

	// ── Initialisation ────────────────────────────────────────────────────────

	_init() {
		// Ask the server whether voice input is enabled and which provider is set.
		// Mic/lang buttons stay visible until we know; if disabled we hide them.
		frappe.call({
			method: "ai_assistant.api.chat.get_settings_status",
			callback: (r) => {
				const s = r.message || {};
				if (s.enable_voice_input === false) {
					$("#ai-mic-btn, #ai-lang-toggle").hide();
					return;
				}
				const provider = s.voice_provider || "Browser (Free)";
				this._use_paid_api = provider !== "Browser (Free)";

				// For browser mode, Web Speech API must be supported
				if (!this._use_paid_api && !this._supported) {
					$("#ai-mic-btn, #ai-lang-toggle").hide();
					return;
				}
				this._update_lang_btn();
				this._bind_events();
			},
			error: () => {
				// On API error fall back to browser STT if the device supports it
				if (!this._supported) {
					$("#ai-mic-btn, #ai-lang-toggle").hide();
				} else {
					this._update_lang_btn();
					this._bind_events();
				}
			},
		});
	}

	_bind_events() {
		$("#ai-mic-btn").on("click", () => (this._recording ? this._stop() : this._start()));

		$("#ai-lang-toggle").on("click", () => {
			const cycle = { en: "ar", ar: "ur", ur: "en" };
			const l     = (this._lang || "en").toLowerCase();
			const key   = l.startsWith("ar") ? "ar" : l.startsWith("ur") ? "ur" : "en";
			this._lang  = cycle[key];
			localStorage.setItem("ai_assistant_voice_lang", this._lang);
			this._update_lang_btn();
		});
	}

	// ── Public start / stop (dispatch to right mode) ───────────────────────

	_start() {
		if (this._use_paid_api) {
			this._start_media();
		} else {
			this._start_browser();
		}
	}

	_stop() {
		if (this._use_paid_api) {
			this._stop_media();
		} else {
			this._stop_browser();
		}
	}

	// ── Browser Web Speech API (free, cloud-routed) ────────────────────────

	_start_browser() {
		const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
		if (!SR) return;

		// iOS Safari: show one-time warning
		const isIOS    = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
		const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
		if (isIOS && isSafari && !localStorage.getItem("ai_voice_ios_warned")) {
			localStorage.setItem("ai_voice_ios_warned", "1");
			this._show_error("Voice input works best in Chrome");
			return;
		}

		// Null out old handlers before stopping so stale callbacks never fire
		if (this._recog) {
			this._recog.onstart  = null;
			this._recog.onresult = null;
			this._recog.onerror  = null;
			this._recog.onend    = null;
			try { this._recog.stop(); } catch (_) {}
		}

		const recog           = new SR();
		this._recog           = recog;
		recog.lang            = this._recognition_lang();
		recog.continuous      = true;
		recog.interimResults  = true;

		recog.onstart = () => {
			this._recording = true;
			$("#ai-mic-btn").addClass("recording");
			this._show_status(this._status_text());
		};

		recog.onresult = (e) => {
			if (recog !== this._recog) return;
			let transcript = "";
			for (let i = 0; i < e.results.length; i++) {
				const res = e.results[i];
				if (res && res[0]) transcript += res[0].transcript;
			}
			if (!transcript) return;
			this._show_status(transcript);
			this._write_to_input(transcript);
		};

		recog.onerror = (e) => {
			if (recog !== this._recog) return;
			if (e.error === "no-speech") return;
			this._stop_state();
			this._show_error(this._error_msg(e.error));
		};

		recog.onend = () => {
			if (recog !== this._recog) return;
			if (this._recording) {
				try { recog.start(); return; } catch (_) {}
			}
			this._stop_state();
		};

		try {
			recog.start();
		} catch (e) {
			this._show_error(this._error_msg(e.name === "NotAllowedError" ? "not-allowed" : "other"));
			this._stop_state();
		}
	}

	_stop_browser() {
		if (this._recog) { try { this._recog.stop(); } catch (_) {} }
		this._stop_state();
	}

	// ── Paid API (MediaRecorder → backend → transcript) ───────────────────

	_start_media() {
		const isAr = (this._lang || "en").toLowerCase().startsWith("ar");
		const isUr = (this._lang || "en").toLowerCase().startsWith("ur");
		const hint = isAr ? "سجّل ... انقر مرة أخرى لإرسال"
			: isUr ? "ریکارڈ کریں ... بھیجنے کے لیے دوبارہ کلک کریں"
			: "Recording — click mic again to transcribe";

		navigator.mediaDevices.getUserMedia({ audio: true })
			.then((stream) => {
				this._stream = stream;
				this._chunks = [];

				const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
					? "audio/webm;codecs=opus"
					: "audio/webm";
				const mr = new MediaRecorder(stream, { mimeType });
				this._mr = mr;

				mr.ondataavailable = (e) => {
					if (e.data && e.data.size > 0) this._chunks.push(e.data);
				};
				mr.onstop = () => this._send_to_backend();
				mr.start(250);   // collect chunks every 250 ms

				this._recording = true;
				$("#ai-mic-btn").addClass("recording");
				this._show_status(hint);
			})
			.catch(() => {
				this._show_error(this._error_msg("not-allowed"));
			});
	}

	_stop_media() {
		this._recording = false;
		$("#ai-mic-btn").removeClass("recording");
		const isAr = (this._lang || "en").toLowerCase().startsWith("ar");
		const isUr = (this._lang || "en").toLowerCase().startsWith("ur");
		this._show_status(isAr ? "جارٍ التعرف..." : isUr ? "پہچان ہو رہی ہے..." : "Transcribing…");

		if (this._mr && this._mr.state !== "inactive") {
			this._mr.stop();
		}
		if (this._stream) {
			this._stream.getTracks().forEach((t) => t.stop());
			this._stream = null;
		}
	}

	_send_to_backend() {
		const blob = new Blob(this._chunks, { type: "audio/webm" });
		this._chunks = [];
		const reader = new FileReader();
		reader.onload = () => {
			// reader.result is "data:audio/webm;base64,AAAA..." — strip the prefix
			const base64 = reader.result.split(",")[1];
			frappe.call({
				method: "ai_assistant.api.voice.transcribe_audio",
				args: { audio_base64: base64, language: this._recognition_lang() },
				callback: (r) => {
					const transcript = (r.message && r.message.transcript) || "";
					this._hide_status();
					if (transcript) {
						this._write_to_input(transcript);
					} else {
						this._show_error("No speech detected — please try again");
					}
				},
				error: (err) => {
					const msg = (err && err.message) || "Transcription failed, please try again";
					this._show_error(msg.replace(/^Server Error:\s*/i, "").slice(0, 120));
				},
			});
		};
		reader.readAsDataURL(blob);
	}

	// ── Shared helpers ─────────────────────────────────────────────────────

	_write_to_input(transcript) {
		const el = document.getElementById("ai-input");
		if (!el) return;
		el.value = transcript;
		el.dispatchEvent(new Event("input", { bubbles: true }));
		$(el).trigger("input");
	}

	_stop_state() {
		this._recording = false;
		$("#ai-mic-btn").removeClass("recording");
		this._hide_status();
	}

	_show_status(text) {
		clearTimeout(this._errTimer);
		$("#ai-voice-status").text(text).removeClass("hidden ai-voice-error");
	}

	_show_error(text) {
		clearTimeout(this._errTimer);
		$("#ai-voice-status").text(text).removeClass("hidden").addClass("ai-voice-error");
		this._errTimer = setTimeout(() => this._hide_status(), 3000);
	}

	_hide_status() {
		$("#ai-voice-status").addClass("hidden");
	}
}
