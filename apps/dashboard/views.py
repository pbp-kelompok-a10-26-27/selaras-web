import re
from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST
from django.db.models import Count, Q
from django.utils import timezone
from apps.core.decorators import admin_required
from apps.helpdesk.models import Ticket
from apps.helpdesk.views import (
    PRIORITY_FILTER_OPTIONS,
    SORT_OPTIONS,
    STATUS_FILTER_OPTIONS,
    apply_ticket_query,
    create_ticket_message,
    parse_ticket_query,
    serialize_ticket_message,
    serialize_ticket_summary,
)
from .navigation import get_sidebar_sections


# ================================== Dashboard Layout ================================== #

# Every dashboard page renders through this, so the sidebar always gets its data
def render_dashboard(request: HttpRequest, template_name, context=None, sidebar_sections=None):
    return render(request, template_name, {
        "sidebar_sections": sidebar_sections or get_sidebar_sections(request.user),
        "dashboard_home_url": reverse("dashboard:home"),
        "logout_url": reverse("accounts:logout"),
        **(context or {}),
    })


def get_greeting():
    hour = timezone.localtime().hour
    if hour < 11:
        return "Good morning"
    if hour < 15:
        return "Good afternoon"
    if hour < 19:
        return "Good evening"
    return "Good night"


@admin_required
def admin_dashboard(request: HttpRequest):

    sidebar_sections = get_sidebar_sections(request.user)
    active_statuses = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]

    # Helpdesk snapshot: what needs attention, in one query
    helpdesk = Ticket.objects.aggregate(
        assigned_to_me=Count("id", filter=Q(assigned_to=request.user, status__in=active_statuses)),
        unassigned=Count("id", filter=Q(assigned_to__isnull=True, status__in=active_statuses)),
        active_total=Count("id", filter=Q(status__in=active_statuses)),
    )

    # The section cards reuse the sidebar's "Management" items
    management_items = next(
        (section["items"] for section in sidebar_sections if section["label"] == "Management"), []
    )
    helpdesk_url = next((item["href"] for item in management_items if item["key"] == "helpdesk"), None)

    return render_dashboard(request, "dashboard/overview.html", {
        "greeting": get_greeting(),
        "admin_name": request.user.first_name or request.user.get_full_name() or request.user.username,
        "today": timezone.localdate(),
        "helpdesk": helpdesk,
        "helpdesk_url": helpdesk_url,
        "management_items": management_items,
    }, sidebar_sections=sidebar_sections)


# ============================= Helpdesk Admin Dashboard Views ============================= #

TICKETS_PAGE_SIZE = 20
ACTIVE_STATUSES = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]

# Assignment filter: value -> (label, icon). Empty value = anyone.
ASSIGNMENT_OPTIONS = {
    "": ("Anyone", "users"),
    "me": ("Assigned to me", "user-check"),
    "unassigned": ("Unassigned", "inbox"),
    "others": ("Assigned to others", "user-round"),
}


def _url_or_none(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def parse_admin_ticket_query(request: HttpRequest):
    """The user helpdesk's status/priority/sort/search (already validated), plus assignment."""

    query = parse_ticket_query(request)
    assignment = request.GET.get("assignment", "")
    query["assignment"] = assignment if assignment in ASSIGNMENT_OPTIONS else ""
    return query


def apply_admin_ticket_query(tickets, query, admin):

    # Status, priority and sort come from the user helpdesk; search is wider for admins
    tickets = apply_ticket_query(tickets, {**query, "search": ""})

    search = query["search"]
    if search:
        matches = (
            Q(subject__icontains=search)
            | Q(description__icontains=search)
            | Q(requester__username__icontains=search)
            | Q(requester__first_name__icontains=search)
            | Q(requester__last_name__icontains=search)
            | Q(requester__email__icontains=search)
        )
        # Ticket IDs as users quote them: "#550E8400", "550e8400-e29b"
        ticket_id = search.lstrip("#").strip()
        if re.fullmatch(r"[0-9a-fA-F-]{4,36}", ticket_id):
            matches |= Q(id__istartswith=ticket_id)
        tickets = tickets.filter(matches)

    assignment = query["assignment"]
    if assignment == "me":
        tickets = tickets.filter(assigned_to=admin)
    elif assignment == "unassigned":
        tickets = tickets.filter(assigned_to__isnull=True)
    elif assignment == "others":
        tickets = tickets.filter(assigned_to__isnull=False).exclude(assigned_to=admin)

    return tickets


def serialize_admin_ticket(ticket, admin):
    is_mine = ticket.assigned_to_id == admin.id
    return {
        **serialize_ticket_summary(ticket),
        # Admins open the dashboard detail page (TODO 3), not the user-facing one
        "detail_url": _url_or_none("dashboard:admin_ticket_detail", ticket.id),
        "is_assigned_to_me": is_mine,
        "can_reply": is_mine and ticket.status != Ticket.Status.CLOSED,
        "can_assign_to_me": ticket.assigned_to_id is None,
        "requester_email": ticket.requester.email if ticket.requester else "",
    }


def build_admin_ticket_stats(admin):
    week_ago = timezone.now() - timedelta(days=7)

    counts = Ticket.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
        assigned_to_me=Count("id", filter=Q(assigned_to=admin, status__in=ACTIVE_STATUSES)),
        unassigned=Count("id", filter=Q(assigned_to__isnull=True, status__in=ACTIVE_STATUSES)),
        high_active=Count("id", filter=Q(priority=Ticket.Priority.HIGH, status__in=ACTIVE_STATUSES)),
        # updated_at is the closest signal to "resolved at" the model has
        resolved_week=Count("id", filter=Q(status=Ticket.Status.RESOLVED, updated_at__gte=week_ago)),
        **{f"status_{value}": Count("id", filter=Q(status=value)) for value in Ticket.Status.values},
        **{f"active_{value}": Count("id", filter=Q(priority=value, status__in=ACTIVE_STATUSES)) for value in Ticket.Priority.values},
    )

    return {
        "kpis": {key: counts[key] for key in ["total", "active", "assigned_to_me", "unassigned", "high_active", "resolved_week"]},
        "status": [
            {"key": value, "label": str(label), "value": counts[f"status_{value}"]}
            for value, label in Ticket.Status.choices
        ],
        # Workload: only tickets that still need work, highest priority first
        "priority": [
            {"key": value, "label": str(label), "value": counts[f"active_{value}"]}
            for value, label in reversed(Ticket.Priority.choices)
        ],
    }


@admin_required
def admin_ticket_list(request: HttpRequest):

    query = parse_admin_ticket_query(request)
    sorting_options = {label: [value, icon] for value, (label, icon, _fields) in SORT_OPTIONS.items()}

    return render_dashboard(request, "dashboard/helpdesk/ticket_list.html", {
        "status_options": STATUS_FILTER_OPTIONS,
        "priority_options": PRIORITY_FILTER_OPTIONS,
        "assignment_options": {label: [value, icon] for value, (label, icon) in ASSIGNMENT_OPTIONS.items()},
        "sorting_options": sorting_options,
        "query": query,
        "status_label": str(dict(Ticket.Status.choices).get(query["status"], "")),
        "priority_label": str(dict(Ticket.Priority.choices).get(query["priority"], "")),
        "assignment_label": ASSIGNMENT_OPTIONS[query["assignment"]][0] if query["assignment"] else "",
        "sort_label": SORT_OPTIONS[query["sort"]][0],
    })


@admin_required
def admin_ticket_list_api(request: HttpRequest):
    """Both lists for the page: the admin's assigned tickets, then every other ticket (paged)."""

    query = parse_admin_ticket_query(request)
    tickets = (
        apply_admin_ticket_query(Ticket.objects.all(), query, request.user)
        .select_related("requester", "assigned_to")
        .annotate(messages_count=Count("messages"))
    )

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1

    assigned = tickets.filter(assigned_to=request.user)
    others = tickets.exclude(assigned_to=request.user)
    others_total = others.count()
    start = (page - 1) * TICKETS_PAGE_SIZE
    others_page = others[start:start + TICKETS_PAGE_SIZE]

    return JsonResponse({
        # Page 2+ only needs more "others"; the assigned list is sent once
        "assigned": [serialize_admin_ticket(t, request.user) for t in assigned] if page == 1 else None,
        "others": [serialize_admin_ticket(t, request.user) for t in others_page],
        "others_total": others_total,
        "page": page,
        "has_more": start + TICKETS_PAGE_SIZE < others_total,
        "total_count": Ticket.objects.count(),
    })


@admin_required
def admin_ticket_stats_api(request: HttpRequest):
    return JsonResponse(build_admin_ticket_stats(request.user))


@admin_required
@require_POST
def admin_ticket_assign(request: HttpRequest, ticket_id):
    """Take an unassigned ticket. Admins only reply to their own tickets, so this is how work gets picked up."""

    # Row lock + the owner check: two admins clicking at once can't both take it
    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), id=ticket_id)
        if ticket.assigned_to_id and ticket.assigned_to_id != request.user.id:
            owner = ticket.assigned_to.get_full_name() or ticket.assigned_to.username
            return JsonResponse({"error": f"{owner} already took this ticket."}, status=409)

        ticket.assigned_to = request.user
        ticket.save(update_fields=["assigned_to", "updated_at"])

    ticket = (
        Ticket.objects.select_related("requester", "assigned_to")
        .annotate(messages_count=Count("messages"))
        .get(id=ticket.id)
    )
    return JsonResponse({"ticket": serialize_admin_ticket(ticket, request.user)})


@admin_required
@require_POST
def admin_ticket_delete(request: HttpRequest, ticket_id):
    """Any admin can delete any ticket; its messages go with it (on_delete=CASCADE)."""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket.delete()
    return JsonResponse({"deleted": str(ticket_id)})
# =============================== Admin Ticket Detail (TODO 3) =============================== #

# The statuses an admin can set from the ticket page: (value, label, icon, icon color)
ADMIN_STATUS_ACTIONS = [
    (Ticket.Status.IN_PROGRESS, "In progress", "loader", "text-secondary-700"),
    (Ticket.Status.RESOLVED, "Resolved", "circle-check", "text-primary-700"),
    (Ticket.Status.CLOSED, "Closed", "lock", "text-secondary-500"),
]
ADMIN_SETTABLE_STATUSES = {value for value, _label, _icon, _color in ADMIN_STATUS_ACTIONS}


# The assigned coordinator owns the ticket: only they reply and change its status.
# (To let every admin change status, return True here.)
def can_manage_ticket(admin, ticket):
    return ticket.assigned_to_id == admin.id


def get_admin_ticket(ticket_id):
    return get_object_or_404(
        Ticket.objects.select_related("requester", "assigned_to").annotate(messages_count=Count("messages")),
        id=ticket_id,
    )


def serialize_admin_ticket_detail(ticket, admin):
    return {
        **serialize_admin_ticket(ticket, admin),
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
        "can_update_status": can_manage_ticket(admin, ticket),
    }


@admin_required
def admin_ticket_detail(request: HttpRequest, ticket_id):

    ticket = get_admin_ticket(ticket_id)
    is_assignee = can_manage_ticket(request.user, ticket)

    return render_dashboard(request, "dashboard/helpdesk/ticket_detail.html", {
        "ticket": ticket,
        "ticket_id_str": str(ticket.id),
        "short_id": str(ticket.id)[:8].upper(),
        "is_assignee": is_assignee,
        "ticket_is_closed": ticket.status == Ticket.Status.CLOSED,
        "status_actions": ADMIN_STATUS_ACTIONS,
        "assignee_name": (ticket.assigned_to.get_full_name() or ticket.assigned_to.username) if ticket.assigned_to else "",
    })


@admin_required
def admin_ticket_detail_api(request: HttpRequest, ticket_id):

    ticket = get_admin_ticket(ticket_id)
    messages = ticket.messages.select_related("author", "reply_to__author")

    return JsonResponse({
        "ticket": serialize_admin_ticket_detail(ticket, request.user),
        "messages": [serialize_ticket_message(message, request.user) for message in messages],
    })


@admin_required
@require_POST
def admin_ticket_message_create(request: HttpRequest, ticket_id):
    """Reply as the assigned coordinator (same rules as the user side: create_ticket_message)."""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    response = create_ticket_message(request, ticket)

    # Without JS the form posts here directly: go back to the ticket page
    if "application/json" not in request.headers.get("Accept", "") and response.status_code == 201:
        return redirect("dashboard:admin_ticket_detail", ticket_id=ticket.id)
    return response


@admin_required
@require_POST
def admin_ticket_update(request: HttpRequest, ticket_id):
    """Change a ticket's status (In progress / Resolved / Closed). Assigned coordinator only."""

    status = request.POST.get("status", "")
    if status not in ADMIN_SETTABLE_STATUSES:
        return JsonResponse({"error": "Choose In progress, Resolved or Closed."}, status=400)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), id=ticket_id)
        if not can_manage_ticket(request.user, ticket):
            return JsonResponse({"error": "Only the assigned coordinator can change this ticket's status."}, status=403)

        if ticket.status != status:
            ticket.status = status
            # closed_at records when it was closed; reopening clears it
            ticket.closed_at = timezone.now() if status == Ticket.Status.CLOSED else None
            ticket.save(update_fields=["status", "closed_at", "updated_at"])

    return JsonResponse({"ticket": serialize_admin_ticket_detail(get_admin_ticket(ticket_id), request.user)})

# =========================================================================================== #
