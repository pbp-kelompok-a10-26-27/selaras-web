from django.http import HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from apps.core.decorators import admin_required, login_required
from django.db.models import Case, Count, IntegerField, Q, When
from .models import Ticket
from .forms import TicketForm, AgentUpdateTicketForm, TicketMessageForm


STATUS_ICONS = {
	Ticket.Status.OPEN: "circle-dot",
	Ticket.Status.IN_PROGRESS: "loader",
	Ticket.Status.RESOLVED: "circle-check",
	Ticket.Status.CLOSED: "lock",
}

PRIORITY_ICONS = {
	Ticket.Priority.HIGH: "arrow-up",
	Ticket.Priority.NORMAL: "equal",
	Ticket.Priority.LOW: "arrow-down",
}

# One dropdown per field, so filters combine with AND (e.g. Closed + High).
# An empty value means "no filter" for that field.
STATUS_FILTER_OPTIONS = {
	"All statuses": ["", "layers"],
	**{str(label): [value, STATUS_ICONS[value]] for value, label in Ticket.Status.choices},
}
PRIORITY_FILTER_OPTIONS = {
	"All priorities": ["", "layers"],
	**{str(label): [value, PRIORITY_ICONS[value]] for value, label in Ticket.Priority.choices},
}

# Priority choices for the create-ticket modal: (value, label, icon, icon color, hint)
PRIORITY_ICON_COLORS = {
	Ticket.Priority.HIGH: "text-red-100",
	Ticket.Priority.NORMAL: "text-blue-200",
	Ticket.Priority.LOW: "text-primary-700",
}
PRIORITY_HINTS = {
	Ticket.Priority.LOW: "Minor issue, no rush",
	Ticket.Priority.NORMAL: "Something isn't working",
	Ticket.Priority.HIGH: "Blocking or urgent",
}
PRIORITY_FORM_OPTIONS = [
	(value, str(label), PRIORITY_ICONS[value], PRIORITY_ICON_COLORS[value], PRIORITY_HINTS[value])
	for value, label in Ticket.Priority.choices
]

SORT_OPTIONS = {
	"-created_at": ("Latest", "calendar-arrow-down", ("-created_at",)),
	"created_at": ("Oldest", "calendar-arrow-up", ("created_at",)),
	"-priority": ("Priority Descending", "arrow-down-wide-narrow", ("-priority_rank", "-created_at")),
	"priority": ("Priority Ascending", "arrow-up-narrow-wide", ("priority_rank", "-created_at")),
}
DEFAULT_SORT = "-created_at"


def parse_ticket_query(request):
	"""Read status/priority/sort/search from the query string, dropping anything invalid."""

	# Each value is checked against its own field's choices (an allowlist)
	status = request.GET.get("status", "")
	if status not in Ticket.Status.values:
		status = ""

	priority = request.GET.get("priority", "")
	if priority not in Ticket.Priority.values:
		priority = ""

	sort = request.GET.get("sort", DEFAULT_SORT)
	if sort not in SORT_OPTIONS:
		sort = DEFAULT_SORT

	search = request.GET.get("search", "").strip()[:100]

	return {"status": status, "priority": priority, "sort": sort, "search": search}


def apply_ticket_query(tickets, query):

	# Chained .filter() calls combine with AND
	if query["status"]:
		tickets = tickets.filter(status=query["status"])

	if query["priority"]:
		tickets = tickets.filter(priority=query["priority"])

	if query["search"]:
		tickets = tickets.filter(
			Q(subject__icontains=query["search"]) | Q(description__icontains=query["search"])
		)

	tickets = tickets.annotate(
		priority_rank=Case(
			When(priority=Ticket.Priority.LOW, then=1),
			When(priority=Ticket.Priority.NORMAL, then=2),
			When(priority=Ticket.Priority.HIGH, then=3),
			output_field=IntegerField(),
		)
	)

	_label, _icon, order_fields = SORT_OPTIONS[query["sort"]]
	return tickets.order_by(*order_fields)


@login_required
def ticket_list(request: HttpRequest):

	tickets = get_tickets(request.user)

	query = parse_ticket_query(request)

	sorting_options = {label: [value, icon] for value, (label, icon, _fields) in SORT_OPTIONS.items()}

	context = {
		"tickets": tickets,
		"status_options": STATUS_FILTER_OPTIONS,
		"priority_options": PRIORITY_FILTER_OPTIONS,
		"sorting_options": sorting_options,
		"query": query,
		"status_label": str(dict(Ticket.Status.choices).get(query["status"], "")),
		"priority_label": str(dict(Ticket.Priority.choices).get(query["priority"], "")),
		"sort_label": SORT_OPTIONS[query["sort"]][0],
		"priority_form_options": PRIORITY_FORM_OPTIONS,
		"default_priority": Ticket._meta.get_field("priority").default,
		"stats": get_ticket_stats(tickets),  # Include ticket statistics in the context
	}

	return render(request, "helpdesk/helpdesk.html", context)


@login_required
def ticket_detail(request, ticket_id):
	
	ticket = get_object_or_404(Ticket, id=ticket_id)

	# Ensure that the user has permission to view this ticket
	if not request.user.is_admin and ticket.requester != request.user:
		return HttpResponse("You do not have permission to view this ticket.", status=403)

	messages = ticket.messages.all()

	return render(request, "helpdesk/ticket_detail.html", {"ticket": ticket, "messages": messages})


@login_required
def ticket_create(request: HttpRequest):

	form = TicketForm(request.POST)

	if request.method == "POST" and form.is_valid():
		ticket = form.save(commit=False)
		ticket.requester = request.user
		ticket.save()
		return redirect("helpdesk:ticket_list")  # Redirect to the ticket list after creation
		
	return render(request, "helpdesk/ticket_create.html", {"form": form})
	
@login_required
def ticket_message_create(request, ticket_id):

	ticket = get_object_or_404(Ticket, id=ticket_id)

	# Ensure that the user has permission to add a message to this ticket
	if not request.user.is_admin and ticket.requester != request.user:
		return HttpResponse("You do not have permission to add a message to this ticket.", status=403)

	form = TicketMessageForm(request.POST)

	if request.method == "POST" and form.is_valid():
		message = form.save(commit=False)
		message.ticket = ticket
		message.author = request.user
		message.is_admin_response = request.user.is_admin
		message.save()
		return redirect("helpdesk:ticket_detail", ticket_id=ticket.id)  # Redirect to the ticket detail after adding a message

	return render(request, "helpdesk/ticket_message_create.html", {"form": form, "ticket": ticket})


@admin_required
def ticket_update(request, ticket_id):

	ticket = get_object_or_404(Ticket, id=ticket_id)

	# Ensure that the user has permission to update this ticket
	if not request.user.is_admin and ticket.requester != request.user:
		return HttpResponse("You do not have permission to update this ticket.", status=403)

	form = AgentUpdateTicketForm(request.POST or None, instance=ticket)

	if request.method == "POST" and form.is_valid():
		form.save()
		return redirect("helpdesk:ticket_detail", ticket_id=ticket.id)  # Redirect to the ticket detail after update

	return render(request, "helpdesk/ticket_update.html", {"form": form, "ticket": ticket})

@login_required
def ticket_delete(request, ticket_id):

	ticket = get_object_or_404(Ticket, id=ticket_id)

	# Ensure that the user has permission to delete this ticket
	if not request.user.is_admin and ticket.requester != request.user:
		return HttpResponse("You do not have permission to delete this ticket.", status=403)

	if request.method == "POST":
		ticket.delete()
		return redirect("helpdesk:ticket_list")  # Redirect to the ticket list after deletion

	return render(request, "helpdesk/ticket_confirm_delete.html", {"ticket": ticket})


# Helper function to get ticket statistics for the current user
def get_ticket_stats(tickets):

	counts = tickets.aggregate(
		open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
		in_progress=Count("id", filter=Q(status=Ticket.Status.IN_PROGRESS)),
		closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
		resolved=Count("id", filter=Q(status=Ticket.Status.RESOLVED)),
		low=Count("id", filter=Q(priority=Ticket.Priority.LOW)),
		normal=Count("id", filter=Q(priority=Ticket.Priority.NORMAL)),
		high=Count("id", filter=Q(priority=Ticket.Priority.HIGH))
	)

	return [
		{"key": "open", "label": "Open", "value": counts["open"], "icon": "circle-dot"},
		{"key": "in_progress", "label": "In Progress", "value": counts["in_progress"], "icon": "loader"},
		{"key": "closed", "label": "Closed", "value": counts["closed"], "icon": "lock"},
		{"key": "resolved", "label": "Resolved", "value": counts["resolved"], "icon": "circle-check"},
		{"key": "low", "label": "Low", "value": counts["low"], "icon": "arrow-down"},
		{"key": "normal", "label": "Normal", "value": counts["normal"], "icon": "equal"},
		{"key": "high", "label": "High", "value": counts["high"], "icon": "arrow-up"},
	]
	
# Helper functions to get ticket as single source of truth
def get_tickets(user):

	if user.is_admin:
		return Ticket.objects.all()

	return Ticket.objects.filter(requester=user)


@login_required
def ticket_stats_api(request: HttpRequest):
	stats = get_ticket_stats(get_tickets(request.user))
	return JsonResponse({"stats": stats})

@login_required
def ticket_list_api(request: HttpRequest):
	
	all_tickets = get_tickets(request.user)
	tickets = (
		apply_ticket_query(all_tickets, parse_ticket_query(request))
		.select_related("requester", "assigned_to")
		.annotate(messages_count=Count("messages"))
	)
	ticket_data = [serialize_ticket_summary(ticket) for ticket in tickets]
	
	return JsonResponse({"tickets": ticket_data, "total_count": all_tickets.count()})

# Helper function to serialize a ticket for the ticket cards (list + create API).
# Expects `messages_count` to be annotated (or set) on the ticket.
def serialize_ticket_summary(ticket):
	return {
		"id": str(ticket.id),
		"title": ticket.subject,
		"description": ticket.description,
		"status": ticket.status,
		"status_label": ticket.get_status_display(),
		"priority": ticket.priority,
		"priority_label": ticket.get_priority_display(),
		"requester": serialize_ticket_user(ticket.requester),
		"assignee": serialize_ticket_user(ticket.assigned_to),
		"messages_count": ticket.messages_count,
		"detail_url": reverse("helpdesk:ticket_detail", args=[ticket.id]),
		"created_at": ticket.created_at.isoformat() if ticket.created_at else None,
		"updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
	}


# Helper function to serialize the requester / assignee of a ticket
def serialize_ticket_user(user):

	if user is None:
		return None

	return {
		"name": user.get_full_name() or user.username,
		"role": user.get_role_display(),
	}
	
# ========================= TICKET DETAIL API =========================

MESSAGE_MAX_LENGTH = 5000


def can_view_ticket(user, ticket):
	return user.is_admin or ticket.requester_id == user.id


# Closed tickets are read-only; resolved ones can still be replied to (e.g. to reopen the discussion)
def can_reply_to_ticket(ticket):
	return ticket.status != Ticket.Status.CLOSED


def serialize_ticket_message(message, viewer):
	return {
		"id": message.id,
		"author": serialize_ticket_user(message.author),
		"is_admin_response": message.is_admin_response,
		"is_own": message.author_id == viewer.id,
		"message": message.message,
		"created_at": message.created_at.isoformat() if message.created_at else None,
	}


@login_required
def ticket_detail_api(request: HttpRequest, ticket_id):

	ticket = get_object_or_404(Ticket.objects.select_related("requester", "assigned_to"), id=ticket_id)

	if not can_view_ticket(request.user, ticket):
		return JsonResponse({"error": "You do not have permission to view this ticket."}, status=403)

	messages = ticket.messages.select_related("author")

	return JsonResponse({
		"ticket": {
			"id": str(ticket.id),
			"title": ticket.subject,
			"description": ticket.description,
			"status": ticket.status,
			"status_label": ticket.get_status_display(),
			"priority": ticket.priority,
			"priority_label": ticket.get_priority_display(),
			"requester": serialize_ticket_user(ticket.requester),
			"assignee": serialize_ticket_user(ticket.assigned_to),
			"can_reply": can_reply_to_ticket(ticket),
			"created_at": ticket.created_at.isoformat() if ticket.created_at else None,
			"updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
			"closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
		},
		"messages": [serialize_ticket_message(message, request.user) for message in messages],
	})


@login_required
@require_POST
def ticket_message_api(request: HttpRequest, ticket_id):

	ticket = get_object_or_404(Ticket, id=ticket_id)

	if not can_view_ticket(request.user, ticket):
		return JsonResponse({"error": "You do not have permission to reply to this ticket."}, status=403)

	if not can_reply_to_ticket(ticket):
		return JsonResponse({"error": "This ticket is closed and no longer accepts replies."}, status=409)

	form = TicketMessageForm(request.POST)
	text = request.POST.get("message", "").strip()

	if not form.is_valid() or not text:
		return JsonResponse({"error": "Your reply can't be empty."}, status=400)

	if len(text) > MESSAGE_MAX_LENGTH:
		return JsonResponse({"error": f"Replies are limited to {MESSAGE_MAX_LENGTH} characters."}, status=400)

	message = form.save(commit=False)
	message.message = text
	message.ticket = ticket
	message.author = request.user
	message.is_admin_response = request.user.is_admin
	message.save()

	return JsonResponse({"message": serialize_ticket_message(message, request.user)}, status=201)


# ========================= TICKET CREATE API =========================

TICKET_DESCRIPTION_MAX_LENGTH = 5000


@login_required
@require_POST
def ticket_create_api(request: HttpRequest):

	form = TicketForm(request.POST)

	# is_valid() fills cleaned_data with every field that passed, so the length
	# check runs even when another field failed, and all errors come back at once
	form.is_valid()
	if len(form.cleaned_data.get("description", "")) > TICKET_DESCRIPTION_MAX_LENGTH:
		form.add_error("description", f"Keep the description under {TICKET_DESCRIPTION_MAX_LENGTH} characters.")

	if not form.is_valid():
		# {"subject": ["This field is required."], ...} so the modal can show each error under its field
		errors = {
			field: [error["message"] for error in field_errors]
			for field, field_errors in form.errors.get_json_data().items()
		}
		return JsonResponse({"errors": errors}, status=400)

	ticket = form.save(commit=False)
	ticket.requester = request.user
	ticket.save()

	# A brand-new ticket has no replies; set it instead of querying for it
	ticket.messages_count = 0

	return JsonResponse({"ticket": serialize_ticket_summary(ticket)}, status=201)
