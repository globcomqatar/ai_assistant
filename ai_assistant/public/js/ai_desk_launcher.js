/**
 * ai_desk_launcher.js
 * Injected on every ERPNext Desk page.
 * Adds a floating "🤖" button that navigates to the AI Chat page.
 */

$(document).on("page-change", function () {
	// Only on desk pages, not on the chat page itself
	if (frappe.get_route_str() === "ai-chat") return;
	if ($("#ai-fab-btn").length) return;

	const fab = $(`
		<button class="ai-launcher-fab" id="ai-fab-btn" title="${__("Open AI Assistant")}">🤖</button>
		<div class="ai-launcher-fab-tooltip">${__("AI Assistant")}</div>
	`);

	$("body").append(fab);

	$("#ai-fab-btn").on("click", function () {
		frappe.set_route("ai-chat");
	});
});
