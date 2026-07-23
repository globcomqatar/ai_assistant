app_name = "ai_assistant"
app_title = "AI Assistant"
app_publisher = "Globcom Qatar"
app_description = "AI Chat Assistant inside ERPNext — natural language to ERP actions"
app_email = "waheedali2022023@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

fixtures = [
	# Load order matters — each entry must exist before anything that link-validates against it.
	# Number Card  →  Dashboard Chart  →  Dashboard  →  Workspace
	{"dt": "Number Card",        "filters": [["module", "=", "AI Assistant"]]},
	{"dt": "Dashboard Chart",    "filters": [["module", "=", "AI Assistant"]]},
	{"dt": "Dashboard",          "filters": [["module", "=", "AI Assistant"]]},
	{"dt": "Workspace",          "filters": [["module", "=", "AI Assistant"]]},
	{"dt": "AI Tool Permission", "filters": [["name", "like", "%"]]},
	{"dt": "AI Agent",           "filters": [["name", "like", "%"]]},
	{"dt": "AI Tool",            "filters": [["name", "like", "%"]]},
]

after_install  = "ai_assistant.setup.create_dashboard"
after_migrate  = "ai_assistant.setup.create_dashboard"

add_to_apps_screen = [
	{
		"name": "ai_assistant",
		"logo": "/assets/ai_assistant/images/ai-logo.png",
		"title": "AI Assistant",
		"route": "/ai-chat",
	}
]

# Inject AI chat button JS into every desk page
# Version query string busts the browser's static-asset cache (max-age=12h, no hash
# in the URL otherwise) so a `bench build` + version bump is immediately visible.
from ai_assistant import __version__ as _app_version

app_include_js = f"/assets/ai_assistant/js/ai_desk_launcher.js?v={_app_version}"
app_include_css = f"/assets/ai_assistant/css/ai_chat.css?v={_app_version}"

# Scheduled task: reset monthly usage tracking
scheduler_events = {
	"monthly": [
		"ai_assistant.tasks.reset_monthly_usage",
	],
}

default_log_clearing_doctypes = {
	"AI Usage Log": 90,
}
