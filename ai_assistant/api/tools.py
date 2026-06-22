"""
ERPNext tool functions exposed to the AI.

Rules for every tool:
  - Validate inputs; never trust AI-supplied values blindly.
  - Use only the Frappe ORM / whitelisted ERPNext functions — no raw SQL.
  - Return a plain dict with at minimum {"status", "message"}.
  - Register in TOOL_REGISTRY and document in TOOLS_SCHEMA.
"""

from __future__ import annotations

import json
import frappe
from frappe import _
from frappe.utils import today, add_days, flt, nowdate, get_first_day

from ai_assistant.api.bi_tools import (
    get_monthly_sales_trend,
    get_top_customers,
    get_top_selling_items,
    get_pending_quotations,
    get_overdue_invoices,
    get_stock_alerts,
    get_open_job_cards,
    analyze_business,
    get_management_summary,
    get_inactive_customers,
    get_unconverted_quotations,
    get_customers_with_overdue_balance,
    get_customers_without_recent_orders,
    get_followup_opportunities,
    diagnose_vehicle_issue,
    get_sales_analysis,
    get_payables_analysis,
)


def _require(value, field: str):
	if not value:
		frappe.throw(_("Field '{0}' is required for this operation.").format(field))


def _exists(doctype: str, name: str):
	if not frappe.db.exists(doctype, name):
		frappe.throw(_(f"{doctype} '{name}' not found."))


def _save_and_commit(doc) -> None:
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 1 — CUSTOMERS & CRM                                    ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_customer(name: str, phone: str = "", email: str = "",
					customer_group: str = "All Customer Groups",
					territory: str = "All Territories") -> dict:
	_require(name, "name")
	if frappe.db.exists("Customer", {"customer_name": name}):
		existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
		return {"status": "exists", "customer": existing,
				"message": f"Customer '{name}' already exists as {existing}."}

	doc = frappe.new_doc("Customer")
	doc.customer_name = name
	doc.customer_group = customer_group
	doc.territory = territory
	_save_and_commit(doc)

	if phone or email:
		contact = frappe.new_doc("Contact")
		contact.first_name = name
		contact.append("links", {"link_doctype": "Customer", "link_name": doc.name})
		if phone:
			contact.append("phone_nos", {"phone": phone, "is_primary_phone": 1})
		if email:
			contact.append("email_ids", {"email_id": email, "is_primary": 1})
		_save_and_commit(contact)

	return {"status": "created", "customer": doc.name,
			"message": f"Customer '{doc.name}' created successfully."}


def search_customer(query: str) -> dict:
	_require(query, "query")
	results = frappe.get_all("Customer",
		filters=[["customer_name", "like", f"%{query}%"]],
		fields=["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id"],
		limit=10)
	return {"status": "ok", "count": len(results), "customers": results}


def get_customer_history(customer: str) -> dict:
	_require(customer, "customer")
	_exists("Customer", customer)
	orders = frappe.get_all("Sales Order",
		filters={"customer": customer, "docstatus": 1},
		fields=["name", "transaction_date", "grand_total", "status", "per_billed", "per_delivered"],
		limit=10, order_by="transaction_date desc")
	invoices = frappe.get_all("Sales Invoice",
		filters={"customer": customer, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "outstanding_amount", "status"],
		limit=10, order_by="posting_date desc")
	payments = frappe.get_all("Payment Entry",
		filters={"party_type": "Customer", "party": customer, "docstatus": 1},
		fields=["name", "posting_date", "paid_amount", "mode_of_payment"],
		limit=5, order_by="posting_date desc")
	return {"status": "ok", "customer": customer,
			"sales_orders": orders, "invoices": invoices, "payments": payments}


def create_lead(lead_name: str, email: str = "", phone: str = "",
				source: str = "", notes: str = "") -> dict:
	_require(lead_name, "lead_name")
	doc = frappe.new_doc("Lead")
	doc.lead_name = lead_name
	doc.email_id = email
	doc.mobile_no = phone
	doc.source = source
	doc.notes = notes
	doc.status = "New"
	_save_and_commit(doc)
	return {"status": "created", "lead": doc.name,
			"message": f"Lead '{doc.name}' created for {lead_name}."}


def get_open_leads(limit: int = 10) -> dict:
	leads = frappe.get_all("Lead",
		filters={"status": ["in", ["New", "Open", "Replied", "Contacted"]]},
		fields=["name", "lead_name", "email_id", "mobile_no", "status", "source", "creation"],
		limit=limit, order_by="creation desc")
	return {"status": "ok", "count": len(leads), "leads": leads}


def create_opportunity(customer: str = "", lead: str = "",
					   opportunity_type: str = "Sales",
					   expected_revenue: float = 0,
					   expected_closing: str = "") -> dict:
	if not (customer or lead):
		frappe.throw(_("Either customer or lead is required."))
	doc = frappe.new_doc("Opportunity")
	doc.opportunity_from = "Customer" if customer else "Lead"
	doc.party_name = customer or lead
	doc.opportunity_type = opportunity_type
	doc.expected_revenue = expected_revenue
	doc.expected_closing = expected_closing or add_days(today(), 30)
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "opportunity": doc.name,
			"message": f"Opportunity '{doc.name}' created."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 2 — QUOTATIONS                                         ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_quotation(customer: str, items: list[dict], discount: float = 0.0) -> dict:
	_require(customer, "customer")
	_require(items, "items")
	_exists("Customer", customer)
	doc = frappe.new_doc("Quotation")
	doc.quotation_to = "Customer"
	doc.party_name = customer
	doc.transaction_date = today()
	doc.valid_till = add_days(today(), 30)
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "rate": item.get("rate", 0),
							  "discount_percentage": discount})
	_save_and_commit(doc)
	return {"status": "created", "quotation": doc.name, "grand_total": doc.grand_total,
			"message": f"Quotation {doc.name} created for {customer} — Total: {doc.grand_total}."}


def get_quotations(customer: str = "", status: str = "") -> dict:
	filters: dict = {"docstatus": ["in", [0, 1]]}
	if customer:
		filters["party_name"] = customer
	if status:
		filters["status"] = status
	rows = frappe.get_all("Quotation",
		filters=filters,
		fields=["name", "party_name", "transaction_date", "valid_till",
				"grand_total", "status"],
		limit=15, order_by="transaction_date desc")
	return {"status": "ok", "count": len(rows), "quotations": rows}


def convert_quotation_to_sales_order(quotation: str) -> dict:
	"""Convert a submitted Quotation into a Sales Order."""
	_require(quotation, "quotation")
	_exists("Quotation", quotation)

	from erpnext.selling.doctype.quotation.quotation import make_sales_order
	so_doc = make_sales_order(quotation)
	so_doc.flags.ignore_permissions = True
	so_doc.insert()
	frappe.db.commit()
	return {"status": "created", "sales_order": so_doc.name,
			"grand_total": so_doc.grand_total,
			"message": f"Sales Order {so_doc.name} created from Quotation {quotation}."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 3 — SALES ORDERS                                       ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_sales_order(customer: str, items: list[dict], delivery_date: str = "") -> dict:
	_require(customer, "customer")
	_require(items, "items")
	_exists("Customer", customer)
	doc = frappe.new_doc("Sales Order")
	doc.customer = customer
	doc.transaction_date = today()
	doc.delivery_date = delivery_date or add_days(today(), 7)
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "rate": item.get("rate", 0),
							  "delivery_date": delivery_date or add_days(today(), 7)})
	_save_and_commit(doc)
	return {"status": "created", "sales_order": doc.name, "grand_total": doc.grand_total,
			"message": f"Sales Order {doc.name} created for {customer}."}


def get_sales_orders(customer: str = "", status: str = "") -> dict:
	filters: dict = {"docstatus": 1}
	if customer:
		filters["customer"] = customer
	if status:
		filters["status"] = status
	else:
		filters["status"] = ["in", ["To Deliver and Bill", "To Bill", "To Deliver", "Partly Billed"]]
	rows = frappe.get_all("Sales Order",
		filters=filters,
		fields=["name", "customer", "transaction_date", "delivery_date",
				"grand_total", "per_billed", "per_delivered", "status"],
		limit=20, order_by="transaction_date desc")
	return {"status": "ok", "count": len(rows), "sales_orders": rows}


def convert_so_to_invoice(sales_order: str) -> dict:
	"""Convert a Sales Order into a Sales Invoice (draft)."""
	_require(sales_order, "sales_order")
	_exists("Sales Order", sales_order)

	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
	inv = make_sales_invoice(sales_order)
	inv.flags.ignore_permissions = True
	inv.insert()
	frappe.db.commit()
	return {"status": "created", "invoice": inv.name, "grand_total": inv.grand_total,
			"message": f"Sales Invoice {inv.name} created from Sales Order {sales_order}."}


def convert_so_to_delivery_note(sales_order: str) -> dict:
	"""Convert a Sales Order into a Delivery Note (draft)."""
	_require(sales_order, "sales_order")
	_exists("Sales Order", sales_order)

	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
	dn = make_delivery_note(sales_order)
	dn.flags.ignore_permissions = True
	dn.insert()
	frappe.db.commit()
	return {"status": "created", "delivery_note": dn.name,
			"message": f"Delivery Note {dn.name} created from Sales Order {sales_order}."}


def close_sales_order(sales_order: str) -> dict:
	"""Close an open Sales Order."""
	_require(sales_order, "sales_order")
	_exists("Sales Order", sales_order)

	from erpnext.selling.doctype.sales_order.sales_order import close_or_unclose_sales_orders
	close_or_unclose_sales_orders(json.dumps([sales_order]), "Closed")
	return {"status": "ok", "sales_order": sales_order,
			"message": f"Sales Order {sales_order} has been closed."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 4 — SALES INVOICES & RETURNS                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_sales_invoice(customer: str, items: list[dict]) -> dict:
	_require(customer, "customer")
	_require(items, "items")
	_exists("Customer", customer)
	doc = frappe.new_doc("Sales Invoice")
	doc.customer = customer
	doc.posting_date = today()
	doc.due_date = add_days(today(), 30)
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "rate": item.get("rate", 0)})
	_save_and_commit(doc)
	return {"status": "created", "invoice": doc.name, "grand_total": doc.grand_total,
			"message": f"Sales Invoice {doc.name} created for {customer} — Total: {doc.grand_total}."}


def get_pending_invoices(customer: str = "") -> dict:
	filters: dict = {"docstatus": 1, "outstanding_amount": [">", 0]}
	if customer:
		filters["customer"] = customer
	rows = frappe.get_all("Sales Invoice", filters=filters,
		fields=["name", "customer", "posting_date", "due_date",
				"grand_total", "outstanding_amount", "conversion_rate", "currency"],
		limit=20, order_by="posting_date desc")
	base_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
	return {"status": "ok", "count": len(rows),
			"total_outstanding": sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in rows),
			"base_currency": base_currency,
			"invoices": rows}


def create_sales_return(invoice: str, reason: str = "Return") -> dict:
	"""Create a credit note / sales return against an existing invoice."""
	_require(invoice, "invoice")
	_exists("Sales Invoice", invoice)

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
	ret = make_sales_return(invoice)
	ret.return_against = invoice
	ret.flags.ignore_permissions = True
	ret.insert()
	frappe.db.commit()
	return {"status": "created", "credit_note": ret.name,
			"grand_total": abs(ret.grand_total),
			"message": f"Credit Note {ret.name} created against Invoice {invoice}."}


def get_invoices_summary(customer: str = "", from_date: str = "", to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"docstatus": 1,
					 "posting_date": ["between", [from_date, to_date]]}
	if customer:
		filters["customer"] = customer
	rows = frappe.get_all("Sales Invoice", filters=filters,
		fields=["name", "customer", "posting_date", "grand_total", "base_grand_total",
				"outstanding_amount", "conversion_rate", "currency", "status"],
		limit=30, order_by="posting_date desc")
	base_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
	return {
		"status": "ok",
		"from_date": from_date, "to_date": to_date,
		"count": len(rows),
		"total_billed": sum(flt(r.get("base_grand_total") or r.get("grand_total")) for r in rows),
		"total_outstanding": sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in rows),
		"base_currency": base_currency,
		"invoices": rows,
	}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 5 — DELIVERY NOTES                                     ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_delivery_note(customer: str, items: list[dict],
						 posting_date: str = "") -> dict:
	_require(customer, "customer")
	_require(items, "items")
	_exists("Customer", customer)
	doc = frappe.new_doc("Delivery Note")
	doc.customer = customer
	doc.posting_date = posting_date or today()
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "rate": item.get("rate", 0)})
	_save_and_commit(doc)
	return {"status": "created", "delivery_note": doc.name,
			"message": f"Delivery Note {doc.name} created for {customer}."}


def get_delivery_notes(customer: str = "", status: str = "") -> dict:
	filters: dict = {"docstatus": 1}
	if customer:
		filters["customer"] = customer
	if status:
		filters["status"] = status
	rows = frappe.get_all("Delivery Note",
		filters=filters,
		fields=["name", "customer", "posting_date", "grand_total", "status"],
		limit=15, order_by="posting_date desc")
	return {"status": "ok", "count": len(rows), "delivery_notes": rows}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 6 — PAYMENTS                                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def record_payment(customer: str, amount: float, invoice: str = "",
				   mode_of_payment: str = "Cash") -> dict:
	_require(customer, "customer")
	_require(amount, "amount")
	_exists("Customer", customer)
	doc = frappe.new_doc("Payment Entry")
	doc.payment_type = "Receive"
	doc.party_type = "Customer"
	doc.party = customer
	doc.paid_amount = flt(amount)
	doc.received_amount = flt(amount)
	doc.posting_date = today()
	doc.mode_of_payment = mode_of_payment
	doc.reference_date = today()
	if invoice and frappe.db.exists("Sales Invoice", invoice):
		inv = frappe.get_doc("Sales Invoice", invoice)
		doc.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice,
			"due_date": inv.due_date,
			"total_amount": inv.grand_total,
			"outstanding_amount": inv.outstanding_amount,
			"allocated_amount": min(flt(amount), flt(inv.outstanding_amount)),
		})
	_save_and_commit(doc)
	return {"status": "created", "payment": doc.name,
			"message": f"Payment of {amount} received from {customer} — Entry: {doc.name}."}


def generate_payment_from_invoice(invoice: str,
								  bank_account: str = "") -> dict:
	"""Use ERPNext's built-in payment entry generator from a Sales Invoice."""
	_require(invoice, "invoice")
	_exists("Sales Invoice", invoice)

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	pe = get_payment_entry("Sales Invoice", invoice,
						   bank_account=bank_account or None,
						   ignore_permissions=True)
	pe.flags.ignore_permissions = True
	pe.insert()
	frappe.db.commit()
	return {"status": "created", "payment": pe.name,
			"paid_amount": pe.paid_amount,
			"message": f"Payment Entry {pe.name} generated from Invoice {invoice}."}


def get_payment_entries(customer: str = "", from_date: str = "",
						to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"docstatus": 1, "party_type": "Customer",
					 "posting_date": ["between", [from_date, to_date]]}
	if customer:
		filters["party"] = customer
	rows = frappe.get_all("Payment Entry", filters=filters,
		fields=["name", "party", "posting_date", "paid_amount",
				"mode_of_payment", "payment_type"],
		limit=20, order_by="posting_date desc")
	return {"status": "ok", "count": len(rows),
			"total_received": sum(flt(r.get("paid_amount")) for r in rows),
			"payments": rows}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 7 — ACCOUNTS & JOURNAL ENTRIES                         ║
# ╚══════════════════════════════════════════════════════════════════╝

def get_account_balance(account: str, date: str = "") -> dict:
	"""Get the current balance of a GL account."""
	_require(account, "account")
	from erpnext.accounts.utils import get_balance_on
	balance = get_balance_on(account=account,
							 date=date or today(),
							 ignore_account_permission=True)
	return {"status": "ok", "account": account,
			"date": date or today(),
			"balance": flt(balance),
			"message": f"Balance of account '{account}' as of {date or today()} is {flt(balance)}."}


def create_journal_entry(accounts: list[dict], narration: str = "",
						 posting_date: str = "",
						 voucher_type: str = "Journal Entry") -> dict:
	"""
	Create a Journal Entry.
	accounts: [{"account": "...", "debit": 0, "credit": 0, "party_type": "", "party": ""}]
	"""
	_require(accounts, "accounts")
	if len(accounts) < 2:
		frappe.throw(_("At least 2 account rows are required for a Journal Entry."))

	doc = frappe.new_doc("Journal Entry")
	doc.voucher_type = voucher_type
	doc.posting_date = posting_date or today()
	doc.user_remark = narration

	total_debit = 0
	total_credit = 0
	for row in accounts:
		_require(row.get("account"), "account")
		debit = flt(row.get("debit", 0))
		credit = flt(row.get("credit", 0))
		total_debit += debit
		total_credit += credit
		doc.append("accounts", {
			"account": row["account"],
			"debit_in_account_currency": debit,
			"credit_in_account_currency": credit,
			"party_type": row.get("party_type", ""),
			"party": row.get("party", ""),
		})

	if round(total_debit, 2) != round(total_credit, 2):
		frappe.throw(_(
			f"Journal Entry is unbalanced — Debit: {total_debit}, Credit: {total_credit}."
		))

	_save_and_commit(doc)
	return {"status": "created", "journal_entry": doc.name,
			"total_debit": total_debit,
			"message": f"Journal Entry {doc.name} created — {narration or 'No narration'}."}


def get_journal_entries(from_date: str = "", to_date: str = "",
						voucher_type: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"docstatus": 1,
					 "posting_date": ["between", [from_date, to_date]]}
	if voucher_type:
		filters["voucher_type"] = voucher_type
	rows = frappe.get_all("Journal Entry", filters=filters,
		fields=["name", "voucher_type", "posting_date",
				"total_debit", "user_remark"],
		limit=20, order_by="posting_date desc")
	return {"status": "ok", "count": len(rows), "journal_entries": rows}


def get_accounts_receivable(customer: str = "") -> dict:
	"""Get outstanding AR — unpaid sales invoices."""
	filters: dict = {"docstatus": 1, "outstanding_amount": [">", 0]}
	if customer:
		filters["customer"] = customer
	rows = frappe.get_all("Sales Invoice", filters=filters,
		fields=["name", "customer", "posting_date", "due_date",
				"grand_total", "outstanding_amount", "conversion_rate", "currency"],
		limit=30, order_by="due_date asc")
	overdue = [r for r in rows if r.get("due_date") and str(r["due_date"]) < today()]
	base_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
	return {
		"status": "ok",
		"count": len(rows),
		"overdue_count": len(overdue),
		"total_outstanding": sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in rows),
		"total_overdue": sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in overdue),
		"base_currency": base_currency,
		"invoices": rows,
	}


def get_sales_summary(from_date: str = "", to_date: str = "") -> dict:
	from_date = str(from_date or str(get_first_day(today())))
	to_date   = str(to_date   or today())
	result = frappe.db.sql("""
		SELECT COUNT(*) AS invoice_count,
			   COALESCE(SUM(base_grand_total), 0) AS total_sales,
			   COALESCE(SUM(outstanding_amount * COALESCE(conversion_rate, 1)), 0) AS total_outstanding
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
	""", (from_date, to_date), as_dict=True)
	top_customers = frappe.db.sql("""
		SELECT customer, SUM(base_grand_total) AS total
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
		GROUP BY customer ORDER BY total DESC LIMIT 5
	""", (from_date, to_date), as_dict=True)
	row = result[0] if result else {}
	invoice_count = int(row.get("invoice_count", 0))
	total_sales   = float(row.get("total_sales", 0))
	avg_order_value = round(total_sales / invoice_count, 2) if invoice_count else 0

	# Compare with the previous period of equal length
	from datetime import datetime as _dt
	period_days = (_dt.strptime(to_date, "%Y-%m-%d") - _dt.strptime(from_date, "%Y-%m-%d")).days + 1
	prev_from = str(add_days(from_date, -period_days))
	prev_to   = str(add_days(to_date,   -period_days))
	prev_r = frappe.db.sql("""
		SELECT COALESCE(SUM(base_grand_total), 0) AS v FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
	""", (prev_from, prev_to), as_dict=True)
	prev_sales = float((prev_r[0] or {}).get("v", 0))
	revenue_vs_prev_pct = round((total_sales - prev_sales) / prev_sales * 100, 1) if prev_sales else 0

	# Top item this period
	top_item_r = frappe.db.sql("""
		SELECT sii.item_name FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s
		GROUP BY sii.item_code, sii.item_name
		ORDER BY SUM(sii.amount) DESC LIMIT 1
	""", (from_date, to_date), as_dict=True)
	top_item     = (top_item_r[0].get("item_name") or "N/A") if top_item_r else "N/A"
	top_customer = top_customers[0]["customer"] if top_customers else "N/A"

	base_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
	metrics = {
		"total_revenue":       round(total_sales, 2),
		"total_orders":        invoice_count,
		"avg_order_value":     avg_order_value,
		"revenue_vs_prev_pct": revenue_vs_prev_pct,
		"top_customer":        top_customer,
		"top_item":            top_item,
		"base_currency":       base_currency,
		"multi_currency":      True,
	}
	chart = {
		"type": "bar",
		"title": "Sales Summary",
		"labels": ["Revenue", "Avg Order Value"],
		"datasets": [{"name": base_currency, "values": [round(total_sales, 2), avg_order_value]}],
	}
	return {
		"status": "ok",
		"from_date": from_date, "to_date": to_date,
		"invoice_count":     invoice_count,
		"total_sales":       total_sales,
		"total_outstanding": float(row.get("total_outstanding", 0)),
		"top_customers":     top_customers,
		"base_currency":     base_currency,
		"message": (
			f"Sales {from_date} to {to_date}: {base_currency} {total_sales:,.0f} (base currency) from "
			f"{invoice_count} orders ({revenue_vs_prev_pct:+.1f}% vs prev period)."
		),
		"metrics": metrics,
		"chart":   chart,
	}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 8 — SUPPLIERS & PURCHASING                             ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_supplier(name: str, supplier_group: str = "All Supplier Groups",
					phone: str = "", email: str = "") -> dict:
	_require(name, "name")
	if frappe.db.exists("Supplier", {"supplier_name": name}):
		existing = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
		return {"status": "exists", "supplier": existing,
				"message": f"Supplier '{name}' already exists as {existing}."}
	doc = frappe.new_doc("Supplier")
	doc.supplier_name = name
	doc.supplier_group = supplier_group
	_save_and_commit(doc)
	return {"status": "created", "supplier": doc.name,
			"message": f"Supplier '{doc.name}' created."}


def search_supplier(query: str) -> dict:
	_require(query, "query")
	results = frappe.get_all("Supplier",
		filters=[["supplier_name", "like", f"%{query}%"]],
		fields=["name", "supplier_name", "supplier_group", "country", "mobile_no"],
		limit=10)
	return {"status": "ok", "count": len(results), "suppliers": results}


def create_purchase_order(supplier: str, items: list[dict],
						  schedule_date: str = "") -> dict:
	_require(supplier, "supplier")
	_require(items, "items")
	_exists("Supplier", supplier)
	doc = frappe.new_doc("Purchase Order")
	doc.supplier = supplier
	doc.transaction_date = today()
	doc.schedule_date = schedule_date or add_days(today(), 7)
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "rate": item.get("rate", 0),
							  "schedule_date": schedule_date or add_days(today(), 7)})
	_save_and_commit(doc)
	return {"status": "created", "purchase_order": doc.name,
			"grand_total": doc.grand_total,
			"message": f"Purchase Order {doc.name} created for {supplier}."}


def get_pending_purchase_orders(supplier: str = "") -> dict:
	filters: dict = {"docstatus": 1,
					 "status": ["in", ["To Receive and Bill", "To Bill", "To Receive", "Partly Billed"]]}
	if supplier:
		filters["supplier"] = supplier
	rows = frappe.get_all("Purchase Order", filters=filters,
		fields=["name", "supplier", "transaction_date", "schedule_date",
				"grand_total", "per_billed", "per_received", "status"],
		limit=20, order_by="transaction_date desc")
	return {"status": "ok", "count": len(rows), "purchase_orders": rows}


def get_purchase_summary(from_date: str = "", to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	result = frappe.db.sql("""
		SELECT COUNT(*) AS order_count,
			   COALESCE(SUM(base_grand_total), 0) AS total_purchase
		FROM `tabPurchase Order`
		WHERE docstatus = 1 AND transaction_date BETWEEN %s AND %s
	""", (from_date, to_date), as_dict=True)
	row = result[0] if result else {}
	return {"status": "ok", "from_date": from_date, "to_date": to_date,
			"order_count": row.get("order_count", 0),
			"total_purchase": float(row.get("total_purchase", 0))}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 9 — INVENTORY & ITEMS                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

def get_stock(item: str, warehouse: str = "") -> dict:
	_require(item, "item")
	_exists("Item", item)
	filters: dict = {"item_code": item}
	if warehouse:
		filters["warehouse"] = warehouse
	bins = frappe.get_all("Bin", filters=filters,
		fields=["warehouse", "actual_qty", "reserved_qty",
				"ordered_qty", "projected_qty"])
	return {"status": "ok", "item": item,
			"total_actual_qty": sum(flt(b.get("actual_qty")) for b in bins),
			"warehouses": bins}


def search_item(query: str, item_group: str = "") -> dict:
	_require(query, "query")
	filters = [["item_name", "like", f"%{query}%"], ["disabled", "=", 0]]
	if item_group:
		filters.append(["item_group", "=", item_group])
	results = frappe.get_all("Item", filters=filters,
		fields=["name", "item_name", "item_group", "stock_uom", "standard_rate"],
		limit=15)
	return {"status": "ok", "count": len(results), "items": results}


def get_item_price(item: str, price_list: str = "Standard Selling") -> dict:
	_require(item, "item")
	prices = frappe.get_all("Item Price",
		filters={"item_code": item, "price_list": price_list},
		fields=["price_list", "price_list_rate", "currency",
				"valid_from", "valid_upto"],
		limit=5)
	return {"status": "ok", "item": item, "price_list": price_list, "prices": prices}


def create_material_request(items: list[dict], purpose: str = "Purchase",
							schedule_date: str = "") -> dict:
	_require(items, "items")
	doc = frappe.new_doc("Material Request")
	doc.material_request_type = purpose
	doc.transaction_date = today()
	doc.schedule_date = schedule_date or add_days(today(), 7)
	for item in items:
		code = item.get("item_code") or item.get("item")
		_require(code, "item_code")
		doc.append("items", {"item_code": code, "qty": item.get("qty", 1),
							  "schedule_date": schedule_date or add_days(today(), 7)})
	_save_and_commit(doc)
	return {"status": "created", "material_request": doc.name,
			"message": f"Material Request {doc.name} created ({purpose})."}


def get_stock_report(item_group: str = "", warehouse: str = "") -> dict:
	filters = [["actual_qty", ">", 0]]
	if item_group:
		filters.append(["item_group", "=", item_group])
	if warehouse:
		filters.append(["warehouse", "=", warehouse])
	bins = frappe.get_all("Bin", filters=filters,
		fields=["item_code", "warehouse", "actual_qty",
				"reserved_qty", "projected_qty"],
		limit=30, order_by="actual_qty desc")
	return {"status": "ok", "count": len(bins), "stock": bins}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 10 — SUPPORT, PROJECTS, MAINTENANCE                    ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_issue(subject: str, description: str = "", customer: str = "",
				 priority: str = "Medium") -> dict:
	_require(subject, "subject")
	doc = frappe.new_doc("Issue")
	doc.subject = subject
	doc.description = description
	doc.customer = customer
	doc.priority = priority
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "issue": doc.name,
			"message": f"Support Issue {doc.name} created: '{subject}'."}


def get_open_issues(customer: str = "") -> dict:
	filters: dict = {"status": ["in", ["Open", "Replied", "Hold"]]}
	if customer:
		filters["customer"] = customer
	issues = frappe.get_all("Issue", filters=filters,
		fields=["name", "subject", "customer", "priority", "status", "creation"],
		limit=20, order_by="creation desc")
	return {"status": "ok", "count": len(issues), "issues": issues}


def create_project(project_name: str, customer: str = "",
				   expected_start: str = "", expected_end: str = "",
				   description: str = "") -> dict:
	_require(project_name, "project_name")
	doc = frappe.new_doc("Project")
	doc.project_name = project_name
	doc.customer = customer
	doc.expected_start_date = expected_start or today()
	doc.expected_end_date = expected_end or add_days(today(), 30)
	doc.description = description
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "project": doc.name,
			"message": f"Project '{doc.name}' created."}


def create_task(title: str, project: str = "", assigned_to: str = "",
				due_date: str = "", description: str = "",
				priority: str = "Medium") -> dict:
	_require(title, "title")
	doc = frappe.new_doc("Task")
	doc.subject = title
	doc.project = project
	doc.assigned_to = assigned_to
	doc.exp_end_date = due_date or add_days(today(), 7)
	doc.description = description
	doc.priority = priority
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "task": doc.name,
			"message": f"Task '{doc.name}' created."}


def create_job_card(vehicle: str, issue: str, customer: str = "",
					priority: str = "Medium") -> dict:
	_require(vehicle, "vehicle")
	_require(issue, "issue")
	try:
		doc = frappe.new_doc("Maintenance Visit")
		doc.customer = customer
		doc.maint_date = today()
		doc.purpose = "Repair"
		doc.append("purposes", {"item_code": vehicle, "description": issue})
		_save_and_commit(doc)
		return {"status": "created", "job_card": doc.name,
				"message": f"Maintenance Visit {doc.name} created for {vehicle}."}
	except Exception:
		todo = frappe.new_doc("ToDo")
		todo.description = f"Job Card — Vehicle: {vehicle}\nIssue: {issue}"
		todo.priority = priority
		todo.owner = frappe.session.user
		_save_and_commit(todo)
		return {"status": "created", "job_card": todo.name, "type": "todo",
				"message": f"Task {todo.name} created for vehicle {vehicle}."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 11 — AUTO WORKSHOP (auto_workshop app)                  ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_workshop_job_card(vehicle: str, customer: str, complaint: str,
							 technician: str = "", bay: str = "") -> dict:
	_require(vehicle, "vehicle")
	_require(customer, "customer")
	_require(complaint, "complaint")
	if not frappe.db.exists("DocType", "Workshop Job Card"):
		return create_job_card(vehicle, complaint, customer)
	doc = frappe.new_doc("Workshop Job Card")
	doc.vehicle = vehicle
	doc.customer = customer
	doc.complaint = complaint
	if technician:
		doc.technician = technician
	if bay:
		doc.workshop_bay = bay
	doc.date = today()
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "workshop_job_card": doc.name,
			"message": f"Workshop Job Card {doc.name} created for vehicle {vehicle}."}


def create_vehicle_inspection(vehicle: str, customer: str = "",
							  notes: str = "") -> dict:
	_require(vehicle, "vehicle")
	if not frappe.db.exists("DocType", "Vehicle Inspection"):
		return {"status": "error", "message": "Vehicle Inspection DocType not found."}
	doc = frappe.new_doc("Vehicle Inspection")
	doc.vehicle = vehicle
	doc.customer = customer
	doc.inspection_date = today()
	doc.notes = notes
	_save_and_commit(doc)
	return {"status": "created", "vehicle_inspection": doc.name,
			"message": f"Vehicle Inspection {doc.name} created."}


def create_workshop_estimate(vehicle: str, customer: str,
							 parts: list[dict] | None = None,
							 labor: list[dict] | None = None) -> dict:
	_require(vehicle, "vehicle")
	_require(customer, "customer")
	if not frappe.db.exists("DocType", "Workshop Estimate"):
		return {"status": "error", "message": "Workshop Estimate DocType not found."}
	doc = frappe.new_doc("Workshop Estimate")
	doc.vehicle = vehicle
	doc.customer = customer
	doc.date = today()
	for part in (parts or []):
		doc.append("parts", {"item_code": part.get("item_code", ""),
							  "qty": part.get("qty", 1), "rate": part.get("rate", 0)})
	for lb in (labor or []):
		doc.append("labor", {"description": lb.get("description", ""),
							  "hours": lb.get("hours", 1), "rate": lb.get("rate", 0)})
	_save_and_commit(doc)
	return {"status": "created", "workshop_estimate": doc.name,
			"message": f"Workshop Estimate {doc.name} created."}


def get_workshop_vehicle(query: str) -> dict:
	_require(query, "query")
	if not frappe.db.exists("DocType", "Workshop Vehicle"):
		return {"status": "error", "message": "Workshop Vehicle DocType not found."}
	results = frappe.get_all("Workshop Vehicle",
		filters=[["vehicle_no", "like", f"%{query}%"]],
		fields=["name", "vehicle_no", "make", "model", "year", "customer", "color"],
		limit=10)
	if not results:
		results = frappe.get_all("Workshop Vehicle",
			filters=[["customer", "like", f"%{query}%"]],
			fields=["name", "vehicle_no", "make", "model", "year", "customer", "color"],
			limit=10)
	return {"status": "ok", "count": len(results), "vehicles": results}


def get_workshop_job_cards(status: str = "Open", limit: int = 10) -> dict:
	if not frappe.db.exists("DocType", "Workshop Job Card"):
		return {"status": "error", "message": "Workshop Job Card DocType not found."}
	filters = {}
	if status:
		filters["status"] = status
	cards = frappe.get_all("Workshop Job Card", filters=filters,
		fields=["name", "vehicle", "customer", "complaint",
				"status", "technician", "date"],
		limit=limit, order_by="date desc")
	return {"status": "ok", "count": len(cards), "job_cards": cards}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 12 — CAR RENTAL (erpcloud_rental app)                  ║
# ╚══════════════════════════════════════════════════════════════════╝

def get_available_vehicles(start_date: str = "", end_date: str = "") -> dict:
	if not frappe.db.exists("DocType", "Vehicle"):
		return {"status": "error", "message": "Vehicle DocType not found."}
	vehicles = frappe.get_all("Vehicle",
		filters={"status": "Available"},
		fields=["name", "make", "model", "license_plate",
				"status", "daily_rate", "monthly_rate"],
		limit=20)
	return {"status": "ok", "count": len(vehicles), "vehicles": vehicles}


def get_active_rental_contracts(customer: str = "") -> dict:
	if not frappe.db.exists("DocType", "Rental Contract"):
		return {"status": "error", "message": "Rental Contract DocType not found."}
	filters = {"status": "Active", "docstatus": 1}
	if customer:
		filters["customer"] = customer
	contracts = frappe.get_all("Rental Contract", filters=filters,
		fields=["name", "customer", "vehicle", "start_date",
				"end_date", "rental_amount", "grand_total", "status"],
		limit=20, order_by="start_date desc")
	return {"status": "ok", "count": len(contracts), "contracts": contracts}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 13 — HR & EMPLOYEES                                    ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_employee(first_name: str, last_name: str = "", company: str = "",
					department: str = "", designation: str = "",
					date_of_joining: str = "") -> dict:
	_require(first_name, "first_name")
	if not company:
		company = frappe.defaults.get_global_default("company") or ""
	doc = frappe.new_doc("Employee")
	doc.first_name = first_name
	doc.last_name = last_name
	doc.employee_name = f"{first_name} {last_name}".strip()
	doc.company = company
	doc.department = department
	doc.designation = designation
	doc.date_of_joining = date_of_joining or today()
	doc.gender = "Male"
	_save_and_commit(doc)
	return {"status": "created", "employee": doc.name,
			"message": f"Employee {doc.employee_name} created as {doc.name}."}


def get_employees(department: str = "", designation: str = "",
				  status: str = "Active") -> dict:
	filters: dict = {"status": status}
	if department:
		filters["department"] = department
	if designation:
		filters["designation"] = designation
	rows = frappe.get_all("Employee", filters=filters,
		fields=["name", "employee_name", "department", "designation",
				"date_of_joining", "status"],
		limit=25, order_by="employee_name asc")
	return {"status": "ok", "count": len(rows), "employees": rows}


def create_leave_application(employee: str, leave_type: str,
							 from_date: str, to_date: str,
							 reason: str = "") -> dict:
	_require(employee, "employee")
	_require(leave_type, "leave_type")
	_require(from_date, "from_date")
	_require(to_date, "to_date")
	doc = frappe.new_doc("Leave Application")
	doc.employee = employee
	doc.leave_type = leave_type
	doc.from_date = from_date
	doc.to_date = to_date
	doc.description = reason
	doc.status = "Open"
	_save_and_commit(doc)
	return {"status": "created", "leave_application": doc.name,
			"message": f"Leave application created for {employee} from {from_date} to {to_date}."}


def get_leave_balance(employee: str, leave_type: str = "", date: str = "") -> dict:
	_require(employee, "employee")
	date = date or today()
	try:
		alloc_filters: dict = {
			"employee": employee, "docstatus": 1,
			"from_date": ["<=", date], "to_date": [">=", date],
		}
		if leave_type:
			alloc_filters["leave_type"] = leave_type
		allocs = frappe.get_all("Leave Allocation", filters=alloc_filters,
			fields=["leave_type", "total_leaves_allocated"])
		year_start = frappe.utils.get_year_start(date)
		used_rows = frappe.get_all("Leave Application",
			filters={"employee": employee, "docstatus": 1, "status": "Approved",
					 "from_date": [">=", year_start]},
			fields=["leave_type", "total_leave_days"])
		used: dict = {}
		for r in used_rows:
			lt = r["leave_type"]
			used[lt] = used.get(lt, 0) + flt(r["total_leave_days"])
		balances = []
		for alloc in allocs:
			lt = alloc["leave_type"]
			allocated = flt(alloc["total_leaves_allocated"])
			balances.append({"leave_type": lt, "allocated": allocated,
							 "used": used.get(lt, 0),
							 "balance": allocated - used.get(lt, 0)})
		return {"status": "ok", "employee": employee, "date": date, "balances": balances}
	except Exception as exc:
		frappe.log_error(title="AI Leave Balance Error", message=str(exc))
		return {"status": "error", "message": f"Could not retrieve leave balance: {str(exc)}"}


def get_attendance_summary(employee: str = "", from_date: str = "",
						   to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"attendance_date": ["between", [from_date, to_date]], "docstatus": 1}
	if employee:
		filters["employee"] = employee
	rows = frappe.get_all("Attendance", filters=filters,
		fields=["employee", "employee_name", "attendance_date", "status"],
		limit=100, order_by="attendance_date desc")
	summary: dict = {}
	for r in rows:
		s = r["status"]
		summary[s] = summary.get(s, 0) + 1
	return {"status": "ok", "from_date": from_date, "to_date": to_date,
			"summary": summary, "total": len(rows), "records": rows[:30]}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 14 — PAYROLL                                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def get_salary_slips(employee: str = "", from_date: str = "",
					 to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"docstatus": 1,
					 "start_date": [">=", from_date],
					 "end_date": ["<=", to_date]}
	if employee:
		filters["employee"] = employee
	slips = frappe.get_all("Salary Slip", filters=filters,
		fields=["name", "employee", "employee_name", "start_date", "end_date",
				"gross_pay", "net_pay", "total_deduction"],
		limit=25, order_by="end_date desc")
	return {"status": "ok", "count": len(slips), "salary_slips": slips}


def get_payroll_summary(from_date: str = "", to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	result = frappe.db.sql("""
		SELECT
			COUNT(*) AS employee_count,
			COALESCE(SUM(gross_pay), 0) AS total_gross,
			COALESCE(SUM(total_deduction), 0) AS total_deduction,
			COALESCE(SUM(net_pay), 0) AS total_net
		FROM `tabSalary Slip`
		WHERE docstatus = 1 AND start_date >= %s AND end_date <= %s
	""", (from_date, to_date), as_dict=True)
	r = result[0] if result else {}
	return {"status": "ok", "from_date": from_date, "to_date": to_date,
			"employee_count": int(r.get("employee_count") or 0),
			"total_gross": flt(r.get("total_gross")),
			"total_deduction": flt(r.get("total_deduction")),
			"total_net": flt(r.get("total_net"))}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 15 — MANUFACTURING                                     ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_work_order(item: str, qty: float, bom_no: str = "",
					  planned_start_date: str = "", company: str = "") -> dict:
	_require(item, "item")
	_require(qty, "qty")
	if not company:
		company = frappe.defaults.get_global_default("company") or ""
	if not bom_no:
		bom_no = frappe.db.get_value("BOM", {"item": item, "is_default": 1, "is_active": 1}, "name") or ""
	doc = frappe.new_doc("Work Order")
	doc.production_item = item
	doc.qty = flt(qty)
	doc.bom_no = bom_no
	doc.planned_start_date = planned_start_date or today()
	doc.company = company
	_save_and_commit(doc)
	return {"status": "created", "work_order": doc.name,
			"message": f"Work Order {doc.name} created for {item} × {qty}."}


def get_work_orders(status: str = "", item: str = "") -> dict:
	filters: dict = {}
	if status:
		filters["status"] = status
	if item:
		filters["production_item"] = item
	rows = frappe.get_all("Work Order", filters=filters,
		fields=["name", "production_item", "qty", "produced_qty",
				"planned_start_date", "status"],
		limit=20, order_by="planned_start_date desc")
	return {"status": "ok", "count": len(rows), "work_orders": rows}


def get_bom_list(item: str = "") -> dict:
	filters: dict = {"is_active": 1}
	if item:
		filters["item"] = item
	rows = frappe.get_all("BOM", filters=filters,
		fields=["name", "item", "item_name", "quantity", "is_default", "is_active"],
		limit=20)
	return {"status": "ok", "count": len(rows), "boms": rows}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 16 — PURCHASE INVOICE & RECEIPT                        ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_purchase_invoice(supplier: str, items: list[dict],
							posting_date: str = "") -> dict:
	_require(supplier, "supplier")
	_require(items, "items")
	doc = frappe.new_doc("Purchase Invoice")
	doc.supplier = supplier
	doc.posting_date = posting_date or today()
	doc.company = frappe.defaults.get_global_default("company") or ""
	for it in items:
		doc.append("items", {
			"item_code": it.get("item_code"),
			"qty": flt(it.get("qty", 1)),
			"rate": flt(it.get("rate", 0)),
		})
	doc.set_missing_values()
	_save_and_commit(doc)
	return {"status": "created", "purchase_invoice": doc.name,
			"message": f"Purchase Invoice {doc.name} created for {supplier}."}


def get_purchase_invoices(supplier: str = "", from_date: str = "",
						  to_date: str = "") -> dict:
	from_date = from_date or str(get_first_day(today()))
	to_date = to_date or today()
	filters: dict = {"docstatus": 1,
					 "posting_date": ["between", [from_date, to_date]]}
	if supplier:
		filters["supplier"] = supplier
	rows = frappe.get_all("Purchase Invoice", filters=filters,
		fields=["name", "supplier", "posting_date", "grand_total", "base_grand_total",
				"outstanding_amount", "conversion_rate", "currency", "status"],
		limit=20, order_by="posting_date desc")
	base_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
	return {"status": "ok", "count": len(rows), "purchase_invoices": rows,
			"total_amount": sum(flt(r.get("base_grand_total") or r.get("grand_total")) for r in rows),
			"base_currency": base_currency}


def create_purchase_receipt(purchase_order: str) -> dict:
	_require(purchase_order, "purchase_order")
	_exists("Purchase Order", purchase_order)
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	doc = make_purchase_receipt(purchase_order)
	_save_and_commit(doc)
	return {"status": "created", "purchase_receipt": doc.name,
			"message": f"Purchase Receipt {doc.name} created from {purchase_order}."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 17 — STOCK OPERATIONS                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_stock_entry(stock_entry_type: str, items: list[dict],
					   from_warehouse: str = "", to_warehouse: str = "") -> dict:
	_require(stock_entry_type, "stock_entry_type")
	_require(items, "items")
	valid_types = ["Material Transfer", "Material Issue", "Material Receipt", "Manufacture"]
	if stock_entry_type not in valid_types:
		frappe.throw(_(f"stock_entry_type must be one of: {', '.join(valid_types)}"))
	doc = frappe.new_doc("Stock Entry")
	doc.stock_entry_type = stock_entry_type
	doc.company = frappe.defaults.get_global_default("company") or ""
	doc.posting_date = today()
	for it in items:
		row: dict = {
			"item_code": it.get("item_code"),
			"qty": flt(it.get("qty", 1)),
			"basic_rate": flt(it.get("rate", 0)),
		}
		s_wh = it.get("from_warehouse") or from_warehouse
		t_wh = it.get("to_warehouse") or to_warehouse
		if s_wh:
			row["s_warehouse"] = s_wh
		if t_wh:
			row["t_warehouse"] = t_wh
		doc.append("items", row)
	doc.set_missing_values()
	_save_and_commit(doc)
	return {"status": "created", "stock_entry": doc.name,
			"message": f"Stock Entry ({stock_entry_type}) {doc.name} created."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 18 — ITEM MANAGEMENT                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_item(item_name: str, item_group: str = "All Item Groups",
				item_code: str = "", is_stock_item: int = 1,
				valuation_rate: float = 0, standard_rate: float = 0,
				unit_of_measure: str = "Nos") -> dict:
	_require(item_name, "item_name")
	doc = frappe.new_doc("Item")
	doc.item_name = item_name
	doc.item_code = item_code or item_name
	doc.item_group = item_group
	doc.is_stock_item = is_stock_item
	doc.stock_uom = unit_of_measure
	doc.valuation_rate = flt(valuation_rate)
	if standard_rate:
		doc.append("item_defaults", {
			"company": frappe.defaults.get_global_default("company") or "",
		})
	_save_and_commit(doc)
	return {"status": "created", "item": doc.name,
			"message": f"Item '{item_name}' created as {doc.name}."}


def get_items(item_group: str = "", query: str = "") -> dict:
	filters: dict = {"disabled": 0}
	if item_group:
		filters["item_group"] = item_group
	if query:
		filters["item_name"] = ["like", f"%{query}%"]
	rows = frappe.get_all("Item", filters=filters,
		fields=["name", "item_name", "item_group", "stock_uom",
				"is_stock_item", "disabled"],
		limit=25, order_by="item_name asc")
	return {"status": "ok", "count": len(rows), "items": rows}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 19 — TASK MANAGEMENT                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

def get_tasks(project: str = "", assigned_to: str = "", status: str = "") -> dict:
	filters: dict = {}
	if project:
		filters["project"] = project
	if assigned_to:
		filters["assigned_to"] = assigned_to
	if status:
		filters["status"] = status
	rows = frappe.get_all("Task", filters=filters,
		fields=["name", "subject", "project", "assigned_to",
				"status", "priority", "exp_end_date"],
		limit=25, order_by="exp_end_date asc")
	return {"status": "ok", "count": len(rows), "tasks": rows}


def update_task_status(task: str, status: str) -> dict:
	_require(task, "task")
	_require(status, "status")
	valid_statuses = ["Open", "Working", "Pending Review", "Completed", "Cancelled"]
	if status not in valid_statuses:
		frappe.throw(_(f"Status must be one of: {', '.join(valid_statuses)}"))
	doc = frappe.get_doc("Task", task)
	doc.status = status
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()
	return {"status": "updated", "task": task, "new_status": status,
			"message": f"Task {task} updated to '{status}'."}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  SECTION 20 — EXPENSE CLAIMS                                    ║
# ╚══════════════════════════════════════════════════════════════════╝

def create_expense_claim(employee: str, expense_type: str, amount: float,
						 expense_date: str = "", description: str = "") -> dict:
	_require(employee, "employee")
	_require(expense_type, "expense_type")
	_require(amount, "amount")
	expense_date = expense_date or today()
	doc = frappe.new_doc("Expense Claim")
	doc.employee = employee
	doc.posting_date = expense_date
	doc.company = frappe.defaults.get_global_default("company") or ""
	doc.append("expenses", {
		"expense_date": expense_date,
		"expense_type": expense_type,
		"amount": flt(amount),
		"description": description,
	})
	doc.total_claimed_amount = flt(amount)
	_save_and_commit(doc)
	return {"status": "created", "expense_claim": doc.name,
			"message": f"Expense Claim {doc.name} created for {employee}."}


def get_expense_claims(employee: str = "", status: str = "") -> dict:
	filters: dict = {}
	if employee:
		filters["employee"] = employee
	if status:
		filters["approval_status"] = status
	rows = frappe.get_all("Expense Claim", filters=filters,
		fields=["name", "employee", "employee_name", "posting_date",
				"total_claimed_amount", "total_sanctioned_amount", "approval_status"],
		limit=20, order_by="posting_date desc")
	return {"status": "ok", "count": len(rows), "expense_claims": rows}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  REGISTRY & SCHEMA                                              ║
# ╚══════════════════════════════════════════════════════════════════╝

TOOL_REGISTRY: dict[str, callable] = {
	# ── Customers & CRM ─────────────────────────────────────────────
	"create_customer":              create_customer,
	"search_customer":              search_customer,
	"get_customer_history":         get_customer_history,
	"create_lead":                  create_lead,
	"get_open_leads":               get_open_leads,
	"create_opportunity":           create_opportunity,
	# ── Quotations ──────────────────────────────────────────────────
	"create_quotation":             create_quotation,
	"get_quotations":               get_quotations,
	"convert_quotation_to_sales_order": convert_quotation_to_sales_order,
	# ── Sales Orders ────────────────────────────────────────────────
	"create_sales_order":           create_sales_order,
	"get_sales_orders":             get_sales_orders,
	"convert_so_to_invoice":        convert_so_to_invoice,
	"convert_so_to_delivery_note":  convert_so_to_delivery_note,
	"close_sales_order":            close_sales_order,
	# ── Sales Invoices ───────────────────────────────────────────────
	"create_sales_invoice":         create_sales_invoice,
	"get_pending_invoices":         get_pending_invoices,
	"create_sales_return":          create_sales_return,
	"get_invoices_summary":         get_invoices_summary,
	# ── Delivery Notes ──────────────────────────────────────────────
	"create_delivery_note":         create_delivery_note,
	"get_delivery_notes":           get_delivery_notes,
	# ── Payments ────────────────────────────────────────────────────
	"record_payment":               record_payment,
	"generate_payment_from_invoice": generate_payment_from_invoice,
	"get_payment_entries":          get_payment_entries,
	# ── Accounts / Finance ──────────────────────────────────────────
	"get_account_balance":          get_account_balance,
	"create_journal_entry":         create_journal_entry,
	"get_journal_entries":          get_journal_entries,
	"get_accounts_receivable":      get_accounts_receivable,
	"get_sales_summary":            get_sales_summary,
	# ── Suppliers & Purchasing ───────────────────────────────────────
	"create_supplier":              create_supplier,
	"search_supplier":              search_supplier,
	"create_purchase_order":        create_purchase_order,
	"get_pending_purchase_orders":  get_pending_purchase_orders,
	"get_purchase_summary":         get_purchase_summary,
	# ── Inventory ───────────────────────────────────────────────────
	"get_stock":                    get_stock,
	"search_item":                  search_item,
	"get_item_price":               get_item_price,
	"create_material_request":      create_material_request,
	"get_stock_report":             get_stock_report,
	# ── Support & Projects ──────────────────────────────────────────
	"create_issue":                 create_issue,
	"get_open_issues":              get_open_issues,
	"create_project":               create_project,
	"create_task":                  create_task,
	"create_job_card":              create_job_card,
	# ── Auto Workshop ────────────────────────────────────────────────
	"create_workshop_job_card":     create_workshop_job_card,
	"create_vehicle_inspection":    create_vehicle_inspection,
	"create_workshop_estimate":     create_workshop_estimate,
	"get_workshop_vehicle":         get_workshop_vehicle,
	"get_workshop_job_cards":       get_workshop_job_cards,
	# ── Car Rental ──────────────────────────────────────────────────
	"get_available_vehicles":       get_available_vehicles,
	"get_active_rental_contracts":  get_active_rental_contracts,
	# ── Business Intelligence ─────────────────────────────────────────
	"get_monthly_sales_trend":               get_monthly_sales_trend,
	"get_top_customers":                     get_top_customers,
	"get_top_selling_items":                 get_top_selling_items,
	"get_pending_quotations":                get_pending_quotations,
	"get_overdue_invoices":                  get_overdue_invoices,
	"get_stock_alerts":                      get_stock_alerts,
	"get_open_job_cards":                    get_open_job_cards,
	"analyze_business":                      analyze_business,
	# ── Management Summary ────────────────────────────────────────────
	"get_management_summary":                get_management_summary,
	# ── Deep Analytics ────────────────────────────────────────────────
	"get_sales_analysis":                    get_sales_analysis,
	"get_payables_analysis":                 get_payables_analysis,
	# ── Customer Follow-Up ────────────────────────────────────────────
	"get_inactive_customers":                get_inactive_customers,
	"get_unconverted_quotations":            get_unconverted_quotations,
	"get_customers_with_overdue_balance":    get_customers_with_overdue_balance,
	"get_customers_without_recent_orders":   get_customers_without_recent_orders,
	"get_followup_opportunities":            get_followup_opportunities,
	# ── Vehicle Diagnostics ───────────────────────────────────────────
	"diagnose_vehicle_issue":                diagnose_vehicle_issue,
	# ── HR & Employees ───────────────────────────────────────────────
	"create_employee":              create_employee,
	"get_employees":                get_employees,
	"create_leave_application":     create_leave_application,
	"get_leave_balance":            get_leave_balance,
	"get_attendance_summary":       get_attendance_summary,
	# ── Payroll ──────────────────────────────────────────────────────
	"get_salary_slips":             get_salary_slips,
	"get_payroll_summary":          get_payroll_summary,
	# ── Manufacturing ────────────────────────────────────────────────
	"create_work_order":            create_work_order,
	"get_work_orders":              get_work_orders,
	"get_bom_list":                 get_bom_list,
	# ── Purchase Invoice & Receipt ───────────────────────────────────
	"create_purchase_invoice":      create_purchase_invoice,
	"get_purchase_invoices":        get_purchase_invoices,
	"create_purchase_receipt":      create_purchase_receipt,
	# ── Stock Operations ─────────────────────────────────────────────
	"create_stock_entry":           create_stock_entry,
	# ── Item Management ──────────────────────────────────────────────
	"create_item":                  create_item,
	"get_items":                    get_items,
	# ── Task Management ──────────────────────────────────────────────
	"get_tasks":                    get_tasks,
	"update_task_status":           update_task_status,
	# ── Expense Claims ───────────────────────────────────────────────
	"create_expense_claim":         create_expense_claim,
	"get_expense_claims":           get_expense_claims,
}

TOOLS_SCHEMA: list[dict] = [
	# ── Customers & CRM ─────────────────────────────────────────────
	{"name": "create_customer",
	 "description": "Create a new Customer with optional phone and email contact.",
	 "parameters": {"name": {"type": "string", "required": True},
					"phone": {"type": "string"}, "email": {"type": "string"},
					"customer_group": {"type": "string"}, "territory": {"type": "string"}}},

	{"name": "search_customer",
	 "description": "Search customers by partial name.",
	 "parameters": {"query": {"type": "string", "required": True}}},

	{"name": "get_customer_history",
	 "description": "Get sales orders, invoices, and payments for a customer.",
	 "parameters": {"customer": {"type": "string", "required": True}}},

	{"name": "create_lead",
	 "description": "Create a new CRM Lead.",
	 "parameters": {"lead_name": {"type": "string", "required": True},
					"email": {"type": "string"}, "phone": {"type": "string"},
					"source": {"type": "string"}, "notes": {"type": "string"}}},

	{"name": "get_open_leads",
	 "description": "List open/new CRM leads.",
	 "parameters": {"limit": {"type": "integer"}}},

	{"name": "create_opportunity",
	 "description": "Create a Sales Opportunity linked to a customer or lead.",
	 "parameters": {"customer": {"type": "string"}, "lead": {"type": "string"},
					"opportunity_type": {"type": "string"},
					"expected_revenue": {"type": "number"},
					"expected_closing": {"type": "string", "description": "YYYY-MM-DD"}}},

	# ── Quotations ──────────────────────────────────────────────────
	{"name": "create_quotation",
	 "description": "Create a Quotation for a customer with items.",
	 "parameters": {"customer": {"type": "string", "required": True},
					"items": {"type": "array", "required": True,
							  "description": "[{item_code, qty, rate}]"},
					"discount": {"type": "number"}}},

	{"name": "get_quotations",
	 "description": "List quotations, optionally filtered by customer or status.",
	 "parameters": {"customer": {"type": "string"}, "status": {"type": "string"}}},

	{"name": "convert_quotation_to_sales_order",
	 "description": "Convert a Quotation into a Sales Order.",
	 "parameters": {"quotation": {"type": "string", "required": True,
								  "description": "Quotation name e.g. SAL-QTN-2024-00001"}}},

	# ── Sales Orders ────────────────────────────────────────────────
	{"name": "create_sales_order",
	 "description": "Create a Sales Order for a customer.",
	 "parameters": {"customer": {"type": "string", "required": True},
					"items": {"type": "array", "required": True},
					"delivery_date": {"type": "string"}}},

	{"name": "get_sales_orders",
	 "description": "List open/pending sales orders, optionally filtered by customer or status.",
	 "parameters": {"customer": {"type": "string"}, "status": {"type": "string"}}},

	{"name": "convert_so_to_invoice",
	 "description": "Convert a Sales Order into a Sales Invoice (draft).",
	 "parameters": {"sales_order": {"type": "string", "required": True}}},

	{"name": "convert_so_to_delivery_note",
	 "description": "Convert a Sales Order into a Delivery Note (draft).",
	 "parameters": {"sales_order": {"type": "string", "required": True}}},

	{"name": "close_sales_order",
	 "description": "Close an open Sales Order that will no longer be fulfilled.",
	 "parameters": {"sales_order": {"type": "string", "required": True}}},

	# ── Sales Invoices ───────────────────────────────────────────────
	{"name": "create_sales_invoice",
	 "description": "Create a Sales Invoice directly for a customer with items.",
	 "parameters": {"customer": {"type": "string", "required": True},
					"items": {"type": "array", "required": True}}},

	{"name": "get_pending_invoices",
	 "description": "List unpaid/outstanding sales invoices, optionally by customer.",
	 "parameters": {"customer": {"type": "string"}}},

	{"name": "create_sales_return",
	 "description": "Create a Credit Note / sales return against an existing Sales Invoice.",
	 "parameters": {"invoice": {"type": "string", "required": True},
					"reason": {"type": "string"}}},

	{"name": "get_invoices_summary",
	 "description": "Get invoice totals and outstanding amounts for a date range.",
	 "parameters": {"customer": {"type": "string"},
					"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Delivery Notes ──────────────────────────────────────────────
	{"name": "create_delivery_note",
	 "description": "Create a Delivery Note for a customer.",
	 "parameters": {"customer": {"type": "string", "required": True},
					"items": {"type": "array", "required": True},
					"posting_date": {"type": "string"}}},

	{"name": "get_delivery_notes",
	 "description": "List delivery notes, optionally filtered by customer or status.",
	 "parameters": {"customer": {"type": "string"}, "status": {"type": "string"}}},

	# ── Payments ────────────────────────────────────────────────────
	{"name": "record_payment",
	 "description": "Record a payment received from a customer, optionally linked to an invoice.",
	 "parameters": {"customer": {"type": "string", "required": True},
					"amount": {"type": "number", "required": True},
					"invoice": {"type": "string"},
					"mode_of_payment": {"type": "string",
										"description": "Cash / Cheque / Bank Transfer"}}},

	{"name": "generate_payment_from_invoice",
	 "description": "Auto-generate a Payment Entry from a Sales Invoice using ERPNext defaults.",
	 "parameters": {"invoice": {"type": "string", "required": True},
					"bank_account": {"type": "string"}}},

	{"name": "get_payment_entries",
	 "description": "List customer payment entries for a date range.",
	 "parameters": {"customer": {"type": "string"},
					"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Accounts / Finance ──────────────────────────────────────────
	{"name": "get_account_balance",
	 "description": "Get the current debit/credit balance of a GL account.",
	 "parameters": {"account": {"type": "string", "required": True,
								"description": "Full account name e.g. '1210 - Accounts Receivable'"},
					"date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"}}},

	{"name": "create_journal_entry",
	 "description": "Create a balanced Journal Entry with debit and credit rows.",
	 "parameters": {
		 "accounts": {"type": "array", "required": True,
					  "description": "[{account, debit, credit, party_type, party}]"},
		 "narration": {"type": "string"},
		 "posting_date": {"type": "string"},
		 "voucher_type": {"type": "string",
						  "description": "Journal Entry / Bank Entry / Cash Entry / Credit Note"}}},

	{"name": "get_journal_entries",
	 "description": "List journal entries for a date range.",
	 "parameters": {"from_date": {"type": "string"}, "to_date": {"type": "string"},
					"voucher_type": {"type": "string"}}},

	{"name": "get_accounts_receivable",
	 "description": "Get all outstanding/unpaid sales invoices (AR report), with overdue flag.",
	 "parameters": {"customer": {"type": "string"}}},

	{"name": "get_sales_summary",
	 "description": "Get total sales, invoice count, and top 5 customers for a date range.",
	 "parameters": {"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Suppliers & Purchasing ───────────────────────────────────────
	{"name": "create_supplier",
	 "description": "Create a new Supplier.",
	 "parameters": {"name": {"type": "string", "required": True},
					"supplier_group": {"type": "string"},
					"phone": {"type": "string"}, "email": {"type": "string"}}},

	{"name": "search_supplier",
	 "description": "Search suppliers by partial name.",
	 "parameters": {"query": {"type": "string", "required": True}}},

	{"name": "create_purchase_order",
	 "description": "Create a Purchase Order for a supplier.",
	 "parameters": {"supplier": {"type": "string", "required": True},
					"items": {"type": "array", "required": True},
					"schedule_date": {"type": "string"}}},

	{"name": "get_pending_purchase_orders",
	 "description": "List pending/open purchase orders, optionally filtered by supplier.",
	 "parameters": {"supplier": {"type": "string"}}},

	{"name": "get_purchase_summary",
	 "description": "Get total purchase order amount and count for a date range.",
	 "parameters": {"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Inventory ───────────────────────────────────────────────────
	{"name": "get_stock",
	 "description": "Check actual stock quantity for an item across warehouses.",
	 "parameters": {"item": {"type": "string", "required": True},
					"warehouse": {"type": "string"}}},

	{"name": "search_item",
	 "description": "Search items/products by name.",
	 "parameters": {"query": {"type": "string", "required": True},
					"item_group": {"type": "string"}}},

	{"name": "get_item_price",
	 "description": "Get selling price of an item from a price list.",
	 "parameters": {"item": {"type": "string", "required": True},
					"price_list": {"type": "string"}}},

	{"name": "create_material_request",
	 "description": "Create a Material Request to reorder stock.",
	 "parameters": {"items": {"type": "array", "required": True},
					"purpose": {"type": "string", "description": "Purchase / Manufacture"},
					"schedule_date": {"type": "string"}}},

	{"name": "get_stock_report",
	 "description": "List current stock levels, optionally by item group or warehouse.",
	 "parameters": {"item_group": {"type": "string"}, "warehouse": {"type": "string"}}},

	# ── Support & Projects ──────────────────────────────────────────
	{"name": "create_issue",
	 "description": "Create a Support Issue / ticket.",
	 "parameters": {"subject": {"type": "string", "required": True},
					"description": {"type": "string"}, "customer": {"type": "string"},
					"priority": {"type": "string",
								 "description": "Low / Medium / High / Urgent"}}},

	{"name": "get_open_issues",
	 "description": "List open support issues, optionally filtered by customer.",
	 "parameters": {"customer": {"type": "string"}}},

	{"name": "create_project",
	 "description": "Create a new Project.",
	 "parameters": {"project_name": {"type": "string", "required": True},
					"customer": {"type": "string"},
					"expected_start": {"type": "string"},
					"expected_end": {"type": "string"},
					"description": {"type": "string"}}},

	{"name": "create_task",
	 "description": "Create a Task, optionally linked to a Project.",
	 "parameters": {"title": {"type": "string", "required": True},
					"project": {"type": "string"}, "assigned_to": {"type": "string"},
					"due_date": {"type": "string"}, "priority": {"type": "string"}}},

	{"name": "create_job_card",
	 "description": "Create a maintenance visit / job card for a vehicle or item.",
	 "parameters": {"vehicle": {"type": "string", "required": True},
					"issue": {"type": "string", "required": True},
					"customer": {"type": "string"}, "priority": {"type": "string"}}},

	# ── Auto Workshop ────────────────────────────────────────────────
	{"name": "create_workshop_job_card",
	 "description": "Create a Workshop Job Card (auto_workshop app).",
	 "parameters": {"vehicle": {"type": "string", "required": True},
					"customer": {"type": "string", "required": True},
					"complaint": {"type": "string", "required": True},
					"technician": {"type": "string"}, "bay": {"type": "string"}}},

	{"name": "create_vehicle_inspection",
	 "description": "Create a Vehicle Inspection record.",
	 "parameters": {"vehicle": {"type": "string", "required": True},
					"customer": {"type": "string"}, "notes": {"type": "string"}}},

	{"name": "create_workshop_estimate",
	 "description": "Create a Workshop Estimate with parts and labor.",
	 "parameters": {"vehicle": {"type": "string", "required": True},
					"customer": {"type": "string", "required": True},
					"parts": {"type": "array",
							  "description": "[{item_code, qty, rate}]"},
					"labor": {"type": "array",
							  "description": "[{description, hours, rate}]"}}},

	{"name": "get_workshop_vehicle",
	 "description": "Search workshop vehicles by plate number or customer name.",
	 "parameters": {"query": {"type": "string", "required": True}}},

	{"name": "get_workshop_job_cards",
	 "description": "List workshop job cards by status.",
	 "parameters": {"status": {"type": "string",
							   "description": "Open / In Progress / Completed"},
					"limit": {"type": "integer"}}},

	# ── Car Rental ──────────────────────────────────────────────────
	{"name": "get_available_vehicles",
	 "description": "List available rental vehicles.",
	 "parameters": {"start_date": {"type": "string"}, "end_date": {"type": "string"}}},

	{"name": "get_active_rental_contracts",
	 "description": "List active rental contracts, optionally filtered by customer.",
	 "parameters": {"customer": {"type": "string"}}},

	# ── Business Intelligence ────────────────────────────────────────
	{"name": "get_monthly_sales_trend",
	 "description": "Monthly sales totals and invoice counts for the past N months. Use for trend/growth analysis.",
	 "parameters": {"months": {"type": "integer", "description": "Number of months (default 6, max 24)"}}},

	{"name": "get_top_customers",
	 "description": "Top customers by sales revenue in the last N days. Use for customer ranking reports.",
	 "parameters": {"period_days": {"type": "integer", "description": "Look-back days (default 30)"},
					"limit": {"type": "integer", "description": "Max customers to return (default 10)"}}},

	{"name": "get_top_selling_items",
	 "description": "Top selling items/products by revenue in the last N days.",
	 "parameters": {"period_days": {"type": "integer", "description": "Look-back days (default 30)"},
					"limit": {"type": "integer", "description": "Max items (default 10)"}}},

	{"name": "get_pending_quotations",
	 "description": "All open/pending quotations not yet converted. Shows count, total value, and expiring-soon alerts.",
	 "parameters": {"days_old": {"type": "integer",
								 "description": "Only show quotations older than N days (0 = all)"}}},

	{"name": "get_overdue_invoices",
	 "description": "All sales invoices past their due date with outstanding amounts. Use for collections analysis.",
	 "parameters": {}},

	{"name": "get_stock_alerts",
	 "description": "Items below safety stock level and out-of-stock items with pending demand.",
	 "parameters": {}},

	{"name": "get_open_job_cards",
	 "description": "Open and in-progress workshop job cards. Detects delayed jobs.",
	 "parameters": {"status": {"type": "string", "description": "Filter by status (optional)"},
					"limit": {"type": "integer"}}},

	{"name": "analyze_business",
	 "description": "Comprehensive AI business intelligence report: sales KPIs, AR, quotations, stock, workshop. Returns prioritised recommendations. Use when the user asks to analyze or review their business.",
	 "parameters": {}},

	# ── Management Summary ───────────────────────────────────────────
	{"name": "get_management_summary",
	 "description": "Daily management briefing: today/week/month sales, collections, pending quotations, overdue invoices, inventory, and workshop status. Use for 'morning briefing' or 'daily summary' requests.",
	 "parameters": {}},

	# ── Deep Analytics ───────────────────────────────────────────────
	{"name": "get_sales_analysis",
	 "description": "Deep sales analysis for the current month: revenue by item group and salesperson, quotation conversion rate, top customers, top items, new vs returning customers. Use for sales performance deep-dives.",
	 "parameters": {}},

	{"name": "get_payables_analysis",
	 "description": "Outstanding purchase invoices with aging buckets, top suppliers by balance, upcoming-due forecast (next 7 days), and payables health metrics. Use for 'what do we owe' or payables/AP analysis.",
	 "parameters": {}},

	# ── Customer Follow-Up ───────────────────────────────────────────
	{"name": "get_inactive_customers",
	 "description": "Customers with no purchase in the last N days — useful for win-back campaigns.",
	 "parameters": {"days_inactive": {"type": "integer",
									  "description": "Inactivity threshold in days (default 60)"}}},

	{"name": "get_unconverted_quotations",
	 "description": "Open quotations older than N days that have not been converted to orders.",
	 "parameters": {"days_old": {"type": "integer", "description": "Age threshold in days (default 14)"}}},

	{"name": "get_customers_with_overdue_balance",
	 "description": "Customers ranked by total overdue amount. Use for collections prioritisation.",
	 "parameters": {}},

	{"name": "get_customers_without_recent_orders",
	 "description": "Previously active, high-value customers who have not ordered in the last N days.",
	 "parameters": {"days": {"type": "integer", "description": "Inactivity threshold (default 90)"}}},

	{"name": "get_followup_opportunities",
	 "description": "Composite follow-up intelligence: overdue payments, stale quotations, lapsed customers — prioritised by revenue impact. Use when asked who needs follow-up or attention.",
	 "parameters": {}},

	# ── Vehicle Diagnostics ──────────────────────────────────────────
	{"name": "diagnose_vehicle_issue",
	 "description": "AI-powered vehicle diagnostic assistant. Given make, model, year, and symptom list, returns possible causes, recommended checks, required parts, and estimated labour hours.",
	 "parameters": {
		 "vehicle_make":  {"type": "string", "description": "Make / brand e.g. Toyota"},
		 "vehicle_model": {"type": "string", "description": "Model e.g. Camry"},
		 "symptoms":      {"type": "array",
						   "description": "List of symptom strings e.g. [\"check engine light\", \"rough idle\"]",
						   "required": True},
		 "year":          {"type": "integer", "description": "Model year e.g. 2020"}}},

	# ── HR & Employees ───────────────────────────────────────────────
	{"name": "create_employee",
	 "description": "Create a new Employee record.",
	 "parameters": {"first_name": {"type": "string", "required": True},
					"last_name": {"type": "string"},
					"company": {"type": "string"},
					"department": {"type": "string"},
					"designation": {"type": "string"},
					"date_of_joining": {"type": "string", "description": "YYYY-MM-DD"}}},

	{"name": "get_employees",
	 "description": "List employees, optionally filtered by department, designation, or status.",
	 "parameters": {"department": {"type": "string"},
					"designation": {"type": "string"},
					"status": {"type": "string", "description": "Active / Inactive / Left"}}},

	{"name": "create_leave_application",
	 "description": "Create a Leave Application for an employee.",
	 "parameters": {"employee": {"type": "string", "required": True},
					"leave_type": {"type": "string", "required": True,
								   "description": "e.g. Annual Leave, Sick Leave"},
					"from_date": {"type": "string", "required": True, "description": "YYYY-MM-DD"},
					"to_date": {"type": "string", "required": True, "description": "YYYY-MM-DD"},
					"reason": {"type": "string"}}},

	{"name": "get_leave_balance",
	 "description": "Get leave allocation and balance for an employee.",
	 "parameters": {"employee": {"type": "string", "required": True},
					"leave_type": {"type": "string"},
					"date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"}}},

	{"name": "get_attendance_summary",
	 "description": "Get attendance records summary for an employee or all employees in a date range.",
	 "parameters": {"employee": {"type": "string"},
					"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Payroll ──────────────────────────────────────────────────────
	{"name": "get_salary_slips",
	 "description": "List salary slips for a date range, optionally filtered by employee.",
	 "parameters": {"employee": {"type": "string"},
					"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	{"name": "get_payroll_summary",
	 "description": "Get total gross pay, deductions, and net pay for a payroll period.",
	 "parameters": {"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	# ── Manufacturing ────────────────────────────────────────────────
	{"name": "create_work_order",
	 "description": "Create a Manufacturing Work Order for a finished good item.",
	 "parameters": {"item": {"type": "string", "required": True,
							 "description": "Finished goods item code"},
					"qty": {"type": "number", "required": True},
					"bom_no": {"type": "string"},
					"planned_start_date": {"type": "string", "description": "YYYY-MM-DD"},
					"company": {"type": "string"}}},

	{"name": "get_work_orders",
	 "description": "List Work Orders, optionally filtered by status or item.",
	 "parameters": {"status": {"type": "string",
							   "description": "Draft / Submitted / In Process / Completed / Stopped"},
					"item": {"type": "string"}}},

	{"name": "get_bom_list",
	 "description": "List Bills of Materials (BOM), optionally filtered by item.",
	 "parameters": {"item": {"type": "string"}}},

	# ── Purchase Invoice & Receipt ───────────────────────────────────
	{"name": "create_purchase_invoice",
	 "description": "Create a Purchase Invoice from a supplier with items.",
	 "parameters": {"supplier": {"type": "string", "required": True},
					"items": {"type": "array", "required": True,
							  "description": "[{item_code, qty, rate}]"},
					"posting_date": {"type": "string"}}},

	{"name": "get_purchase_invoices",
	 "description": "List purchase invoices for a date range, optionally by supplier.",
	 "parameters": {"supplier": {"type": "string"},
					"from_date": {"type": "string"}, "to_date": {"type": "string"}}},

	{"name": "create_purchase_receipt",
	 "description": "Create a Purchase Receipt from an existing Purchase Order.",
	 "parameters": {"purchase_order": {"type": "string", "required": True}}},

	# ── Stock Operations ─────────────────────────────────────────────
	{"name": "create_stock_entry",
	 "description": "Create a Stock Entry for material transfer, issue, or receipt.",
	 "parameters": {"stock_entry_type": {"type": "string", "required": True,
										 "description": "Material Transfer / Material Issue / Material Receipt / Manufacture"},
					"items": {"type": "array", "required": True,
							  "description": "[{item_code, qty, rate, from_warehouse, to_warehouse}]"},
					"from_warehouse": {"type": "string"},
					"to_warehouse": {"type": "string"}}},

	# ── Item Management ──────────────────────────────────────────────
	{"name": "create_item",
	 "description": "Create a new Item (product or service) in the Item master.",
	 "parameters": {"item_name": {"type": "string", "required": True},
					"item_group": {"type": "string"},
					"item_code": {"type": "string"},
					"is_stock_item": {"type": "integer", "description": "1 for stock item, 0 for service"},
					"valuation_rate": {"type": "number"},
					"standard_rate": {"type": "number"},
					"unit_of_measure": {"type": "string", "description": "Nos / Kg / Ltr etc."}}},

	{"name": "get_items",
	 "description": "List items from the Item master, optionally filtered by group or name.",
	 "parameters": {"item_group": {"type": "string"},
					"query": {"type": "string"}}},

	# ── Task Management ──────────────────────────────────────────────
	{"name": "get_tasks",
	 "description": "List tasks, optionally filtered by project, assignee, or status.",
	 "parameters": {"project": {"type": "string"},
					"assigned_to": {"type": "string"},
					"status": {"type": "string",
							   "description": "Open / Working / Pending Review / Completed / Cancelled"}}},

	{"name": "update_task_status",
	 "description": "Update the status of an existing Task.",
	 "parameters": {"task": {"type": "string", "required": True,
							 "description": "Task name/ID e.g. TASK-00001"},
					"status": {"type": "string", "required": True,
							   "description": "Open / Working / Pending Review / Completed / Cancelled"}}},

	# ── Expense Claims ───────────────────────────────────────────────
	{"name": "create_expense_claim",
	 "description": "Create an Expense Claim for an employee.",
	 "parameters": {"employee": {"type": "string", "required": True},
					"expense_type": {"type": "string", "required": True},
					"amount": {"type": "number", "required": True},
					"expense_date": {"type": "string", "description": "YYYY-MM-DD"},
					"description": {"type": "string"}}},

	{"name": "get_expense_claims",
	 "description": "List Expense Claims, optionally filtered by employee or approval status.",
	 "parameters": {"employee": {"type": "string"},
					"status": {"type": "string",
							   "description": "Draft / Approved / Rejected / Cancelled / Paid"}}},
]
