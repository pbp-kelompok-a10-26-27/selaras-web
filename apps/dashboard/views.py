from django.http import HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone
from apps.core.decorators import admin_required
from apps.helpdesk.models import Ticket, TicketMessage
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

# Helper functions
# @admin_required
# def admin_ticket_list(request: HttpRequest):

#     # All tickets
#     all_tickets = Ticket.objects.all()

#     # Admin assigned tickets
#     assigned_tickets = Ticket.objects.select_related("assigned_to").filter(assigned_to=request.user).all()

#     data = {
#         "tickets": [get_ticket_detail(ticket) for ticket in all_tickets],
#         "assigned_tickets": [get_ticket_detail(ticket) for ticket in assigned_tickets],
#         "all_ticket_stats": admin_tickets_stats(all_tickets),
#         "assigned_ticket_stats": admin_tickets_stats(assigned_tickets),
#     }

#     return JsonResponse(data, safe=False)

# # Helper function to get ticket stats for API response
# def admin_tickets_stats(tickets):
      
#     counts = tickets.aggregate(
#         open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
#         in_progress=Count("id", filter=Q(status=Ticket.Status.IN_PROGRESS)),
#         closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
#         resolved=Count("id", filter=Q(status=Ticket.Status.RESOLVED)),
#         low=Count("id", filter=Q(priority=Ticket.Priority.LOW)),
#         normal=Count("id", filter=Q(priority=Ticket.Priority.NORMAL)),
#         high=Count("id", filter=Q(priority=Ticket.Priority.HIGH))
#     )

#     return [
#         {"key": "open", "label": "Open", "value": counts["open"], "icon": "circle-dot"},
#         {"key": "in_progress", "label": "In Progress", "value": counts["in_progress"], "icon": "loader"},
#         {"key": "closed", "label": "Closed", "value": counts["closed"], "icon": "lock"},
#         {"key": "resolved", "label": "Resolved", "value": counts["resolved"], "icon": "circle-check"},
#         {"key": "low", "label": "Low", "value": counts["low"], "icon": "arrow-down"},
#         {"key": "normal", "label": "Normal", "value": counts["normal"], "icon": "equal"},
#         {"key": "high", "label": "High", "value": counts["high"], "icon": "arrow-up"},
#     ]
      

# Helper function to get ticket detail data for API response
# def get_ticket_detail(ticket):

#     return {
#         "id": str(ticket.id),
#         "title": ticket.subject,
#         "description": ticket.description,
#         "status": ticket.status,
#         "status_label": ticket.get_status_display(),
#         "priority": ticket.priority,
#         "priority_label": ticket.get_priority_display(),
#         "requester": serialize_ticket_user(ticket.requester),
#         "assignee": serialize_ticket_user(ticket.assigned_to),
#         # "messages_count": ticket.messages_count,
#         "detail_url": reverse("dashboard:admin_ticket_detail", args=[ticket.id]),
#         "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
#         "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
#     }

# # Helper function to serialize the requester / assignee of a ticket
# def serialize_ticket_user(user):

# 	if user is None:
# 		return None

# 	return {
# 		"name": user.get_full_name() or user.username,
# 		"role": user.get_role_display(),
# 	}
# =========================================================================================== #