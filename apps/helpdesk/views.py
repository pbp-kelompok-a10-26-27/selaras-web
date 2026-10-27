from django.contrib import messages as django_messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.decorators import admin_required, login_required

from .forms import AgentUpdateTicketForm, TicketForm, TicketMessageForm
from .models import Ticket, TicketAttachment, TicketMessage
from .services import save_attachments, validate_attachments

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
    **{
        str(label): [value, STATUS_ICONS[value]]
        for value, label in Ticket.Status.choices
    },
}
PRIORITY_FILTER_OPTIONS = {
    "All priorities": ["", "layers"],
    **{
        str(label): [value, PRIORITY_ICONS[value]]
        for value, label in Ticket.Priority.choices
    },
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
    (
        value,
        str(label),
        PRIORITY_ICONS[value],
        PRIORITY_ICON_COLORS[value],
        PRIORITY_HINTS[value],
    )
    for value, label in Ticket.Priority.choices
]

SORT_OPTIONS = {
    "-created_at": ("Latest", "calendar-arrow-down", ("-created_at",)),
    "created_at": ("Oldest", "calendar-arrow-up", ("created_at",)),
    "-priority": (
        "Priority Descending",
        "arrow-down-wide-narrow",
        ("-priority_rank", "-created_at"),
    ),
    "priority": (
        "Priority Ascending",
        "arrow-up-narrow-wide",
        ("priority_rank", "-created_at"),
    ),
}
DEFAULT_SORT = "-created_at"


def parse_ticket_query(request):
    """Read status/priority/sort/search from the query string, dropping anything
    invalid."""

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
            Q(subject__icontains=query["search"])
            | Q(description__icontains=query["search"])
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

    sorting_options = {
        label: [value, icon] for value, (label, icon, _fields) in SORT_OPTIONS.items()
    }

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
        return HttpResponse(
            "You do not have permission to view this ticket.", status=403
        )

    messages = ticket.messages.all()

    return render(
        request,
        "helpdesk/ticket_detail.html",
        {
            "ticket": ticket,
            "messages": messages,
            "can_post": can_post_message(request.user, ticket),
            "ticket_id_str": str(ticket.id),
            "ticket_is_closed": ticket.status == Ticket.Status.CLOSED,
        },
    )


@login_required
def ticket_create(request: HttpRequest):

    form = TicketForm(request.POST)

    if request.method == "POST" and form.is_valid():
        # Same fields the create-ticket dialog sends, so screenshots are kept even
        # when its script didn't run
        files, links, attachment_errors = validate_attachments(
            request.FILES.getlist("attachments"),
            [link for link in request.POST.getlist("image_links") if link.strip()],
        )
        if attachment_errors:
            django_messages.error(request, " ".join(attachment_errors))
            return redirect("helpdesk:ticket_list")

        with transaction.atomic():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            ticket.save()
            save_attachments(ticket, files, links)
        return redirect(
            "helpdesk:ticket_list"
        )  # Redirect to the ticket list after creation

    return render(request, "helpdesk/ticket_create.html", {"form": form})


@login_required
def ticket_message_create(request, ticket_id):

    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Ensure that the user has permission to add a message to this ticket
    if not can_post_message(request.user, ticket):
        return HttpResponse(
            "You do not have permission to add a message to this ticket.", status=403
        )

    form = TicketMessageForm(request.POST)

    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.ticket = ticket
        message.author = request.user
        message.is_admin_response = request.user.is_admin
        message.save()
        return redirect(
            "helpdesk:ticket_detail", ticket_id=ticket.id
        )  # Redirect to the ticket detail after adding a message

    return render(
        request, "helpdesk/ticket_message_create.html", {"form": form, "ticket": ticket}
    )


@admin_required
def ticket_update(request, ticket_id):

    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Ensure that the user has permission to update this ticket
    if not request.user.is_admin and ticket.requester != request.user:
        return HttpResponse(
            "You do not have permission to update this ticket.", status=403
        )

    form = AgentUpdateTicketForm(request.POST or None, instance=ticket)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(
            "helpdesk:ticket_detail", ticket_id=ticket.id
        )  # Redirect to the ticket detail after update

    return render(
        request, "helpdesk/ticket_update.html", {"form": form, "ticket": ticket}
    )


@login_required
def ticket_delete(request, ticket_id):

    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Ensure that the user has permission to delete this ticket
    if not request.user.is_admin and ticket.requester != request.user:
        return HttpResponse(
            "You do not have permission to delete this ticket.", status=403
        )

    if request.method == "POST":
        ticket.delete()
        return redirect(
            "helpdesk:ticket_list"
        )  # Redirect to the ticket list after deletion

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
        high=Count("id", filter=Q(priority=Ticket.Priority.HIGH)),
    )

    return [
        {"key": "open", "label": "Open", "value": counts["open"], "icon": "circle-dot"},
        {
            "key": "in_progress",
            "label": "In Progress",
            "value": counts["in_progress"],
            "icon": "loader",
        },
        {"key": "closed", "label": "Closed", "value": counts["closed"], "icon": "lock"},
        {
            "key": "resolved",
            "label": "Resolved",
            "value": counts["resolved"],
            "icon": "circle-check",
        },
        {"key": "low", "label": "Low", "value": counts["low"], "icon": "arrow-down"},
        {
            "key": "normal",
            "label": "Normal",
            "value": counts["normal"],
            "icon": "equal",
        },
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
    page_tickets, pagination = paginate(tickets, parse_page(request))

    return JsonResponse(
        {
            "tickets": [serialize_ticket_summary(ticket) for ticket in page_tickets],
            "pagination": pagination,
            "total_count": all_tickets.count(),
        }
    )


# ============================== PAGINATION ==============================

TICKETS_PER_PAGE = 10


def parse_page(request, param="page"):
    try:
        return max(1, int(request.GET.get(param, 1)))
    except (TypeError, ValueError):
        return 1


def paginate(queryset, page_number, per_page=TICKETS_PER_PAGE):
    """One page of a queryset plus what the pager needs. Out-of-range pages snap to
    the last one, so a page that emptied (e.g. after a delete or a narrower filter)
    still shows tickets."""

    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(page_number)
    return page.object_list, {
        "page": page.number,
        "total_pages": paginator.num_pages,
        "count": paginator.count,
        "per_page": per_page,
        "start": page.start_index(),
        "end": page.end_index(),
    }


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


def serialize_attachment(attachment):
    """What the ticket page needs to show one screenshot: a link to the image itself,
    or (for uploads) the permission-checked download URL."""
    return {
        "id": attachment.id,
        "kind": "link" if attachment.is_link else "file",
        "url": attachment.url
        or reverse("helpdesk:attachment_file", args=[attachment.id]),
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


# Closed tickets are read-only; resolved ones can still be replied to (e.g. to
# reopen the discussion)
def can_reply_to_ticket(ticket):
    return ticket.status != Ticket.Status.CLOSED


# Only the requester and the admin assigned to the ticket take part in the
# conversation. Other admins can read it (dashboard) but not post, so every ticket
# has one clear owner.
def can_post_message(user, ticket):
    return ticket.requester_id == user.id or (
        user.is_admin and ticket.assigned_to_id == user.id
    )


def serialize_reply_preview(message):
    """The quoted message shown above a reply."""
    if message is None:
        return None
    return {
        "id": message.id,
        "author_name": (message.author.get_full_name() or message.author.username)
        if message.author
        else "Deleted user",
        "is_admin_response": message.is_admin_response,
        "excerpt": message.message[:160],
    }


def create_ticket_message(request, ticket):
    """Validate and save a reply (optionally to another message). Shared by the user
    and admin APIs."""

    if not can_post_message(request.user, ticket):
        return JsonResponse(
            {
                "error": (
                    "Only the requester and the assigned coordinator can reply to "
                    "this ticket."
                )
            },
            status=403,
        )

    if not can_reply_to_ticket(ticket):
        return JsonResponse(
            {"error": "This ticket is closed and no longer accepts replies."},
            status=409,
        )

    form = TicketMessageForm(request.POST)
    text = request.POST.get("message", "").strip()

    if not form.is_valid() or not text:
        return JsonResponse({"error": "Your reply can't be empty."}, status=400)

    if len(text) > MESSAGE_MAX_LENGTH:
        return JsonResponse(
            {"error": f"Replies are limited to {MESSAGE_MAX_LENGTH} characters."},
            status=400,
        )

    # The quoted message must be part of this same ticket
    reply_to = None
    reply_to_id = request.POST.get("reply_to", "").strip()
    if reply_to_id:
        reply_to = (
            TicketMessage.objects.select_related("author")
            .filter(ticket=ticket, id=reply_to_id)
            .first()
            if reply_to_id.isdigit()
            else None
        )
        if reply_to is None:
            return JsonResponse(
                {"error": "The message you're replying to no longer exists."},
                status=400,
            )

    message = form.save(commit=False)
    message.message = text
    message.ticket = ticket
    message.author = request.user
    message.is_admin_response = request.user.is_admin
    message.reply_to = reply_to
    message.save()

    return JsonResponse(
        {"message": serialize_ticket_message(message, request.user)}, status=201
    )


def serialize_ticket_message(message, viewer):
    return {
        "id": message.id,
        "author": serialize_ticket_user(message.author),
        "is_admin_response": message.is_admin_response,
        "is_own": message.author_id == viewer.id,
        "message": message.message,
        "reply_to": serialize_reply_preview(message.reply_to),
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@login_required
def ticket_detail_api(request: HttpRequest, ticket_id):

    ticket = get_object_or_404(
        Ticket.objects.select_related("requester", "assigned_to"), id=ticket_id
    )

    if not can_view_ticket(request.user, ticket):
        return JsonResponse(
            {"error": "You do not have permission to view this ticket."}, status=403
        )

    messages = ticket.messages.select_related("author", "reply_to__author")

    return JsonResponse(
        {
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
                "attachments": [
                    serialize_attachment(attachment)
                    for attachment in ticket.attachments.all()
                ],
                "can_reply": can_reply_to_ticket(ticket)
                and can_post_message(request.user, ticket),
                "created_at": ticket.created_at.isoformat()
                if ticket.created_at
                else None,
                "updated_at": ticket.updated_at.isoformat()
                if ticket.updated_at
                else None,
                "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            },
            "messages": [
                serialize_ticket_message(message, request.user) for message in messages
            ],
        }
    )


@login_required
@require_POST
def ticket_message_api(request: HttpRequest, ticket_id):

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if not can_view_ticket(request.user, ticket):
        return JsonResponse(
            {"error": "You do not have permission to reply to this ticket."}, status=403
        )

    return create_ticket_message(request, ticket)


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
        form.add_error(
            "description",
            f"Keep the description under {TICKET_DESCRIPTION_MAX_LENGTH} characters.",
        )

    if not form.is_valid():
        # {"subject": ["This field is required."], ...} so the modal can show each
        # error under its field
        errors = {
            field: [error["message"] for error in field_errors]
            for field, field_errors in form.errors.get_json_data().items()
        }
        return JsonResponse({"errors": errors}, status=400)

    files, links, attachment_errors = validate_attachments(
        request.FILES.getlist("attachments"),
        [link for link in request.POST.getlist("image_links") if link.strip()],
    )
    if attachment_errors:
        return JsonResponse({"errors": {"attachments": attachment_errors}}, status=400)

    with transaction.atomic():
        ticket = form.save(commit=False)
        ticket.requester = request.user
        ticket.save()
        save_attachments(ticket, files, links)

    # A brand-new ticket has no replies; set it instead of querying for it
    ticket.messages_count = 0

    return JsonResponse({"ticket": serialize_ticket_summary(ticket)}, status=201)


@login_required
def attachment_file(request: HttpRequest, attachment_id):
    """Download an uploaded screenshot, only for people who may see its ticket."""

    attachment = get_object_or_404(
        TicketAttachment.objects.select_related("ticket"), id=attachment_id
    )
    if not can_view_ticket(request.user, attachment.ticket) or not attachment.file:
        raise Http404

    response = FileResponse(attachment.file.open("rb"))
    # Browsers must not guess a different type from the bytes, and the page that
    # shows it is the only intended consumer
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
