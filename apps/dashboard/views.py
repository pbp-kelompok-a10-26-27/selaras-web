import re
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, F, Q, Sum, Value, When
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.text import Truncator
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.articles.models import Article, ArticleCategory
from apps.challenges.forms import BadgeForm, ChallengeForm, CommunityGoalForm
from apps.challenges.models import (
    Badge,
    Challenge,
    ChallengeParticipation,
    CommunityGoal,
)
from apps.challenges.services import goal_progress, impact_summary
from apps.core.decorators import admin_required
from apps.core.templatetags.ui_extras import rupiah
from apps.core.utils import safe_next_url
from apps.donations.models import Campaign, Donation
from apps.donations.services import (
    campaign_accepts_donations,
    campaign_progress_percent,
    campaign_queryset,
)
from apps.feeds.models import Comment, Like, Post
from apps.feeds.views import delete_post
from apps.helpdesk.models import Ticket
from apps.helpdesk.views import (
    PRIORITY_FILTER_OPTIONS,
    SORT_OPTIONS,
    STATUS_FILTER_OPTIONS,
    apply_ticket_query,
    create_ticket_message,
    paginate,
    parse_page,
    parse_ticket_query,
    serialize_attachment,
    serialize_ticket_message,
    serialize_ticket_summary,
)
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .navigation import get_sidebar_sections

CHALLENGES_PER_PAGE = 10

# ================================= Dashboard Layout ================================= #


# Every dashboard page renders through this, so the sidebar always gets its data
def render_dashboard(
    request: HttpRequest,
    template_name,
    context=None,
    sidebar_sections=None,
    active_section=None,
):
    return render(
        request,
        template_name,
        {
            "sidebar_sections": sidebar_sections
            or get_sidebar_sections(request.user, active=active_section),
            "dashboard_home_url": reverse("dashboard:home"),
            "logout_url": reverse("accounts:logout"),
            **(context or {}),
        },
    )


def get_greeting():
    hour = timezone.localtime().hour
    if hour < 11:
        return "Selamat pagi"
    if hour < 15:
        return "Selamat siang"
    if hour < 19:
        return "Selamat sore"
    return "Selamat malam"


def _section_items(sidebar_sections, key):
    return next((s["items"] for s in sidebar_sections if s.get("key") == key), [])


def build_overview(admin):
    """Angka ringkasan: yang perlu ditindak sekarang dan aktivitas 7 hari."""
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    active_statuses = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]

    helpdesk = Ticket.objects.aggregate(
        assigned_to_me=Count(
            "id", filter=Q(assigned_to=admin, status__in=active_statuses)
        ),
        unassigned=Count(
            "id", filter=Q(assigned_to__isnull=True, status__in=active_statuses)
        ),
        active_total=Count("id", filter=Q(status__in=active_statuses)),
    )
    donations = Donation.objects.aggregate(
        pending=Count("id", filter=Q(status=Donation.Status.PENDING)),
        pending_amount=Sum("amount", filter=Q(status=Donation.Status.PENDING)),
        week_amount=Sum(
            "amount",
            filter=Q(status=Donation.Status.APPROVED, verified_at__gte=week_ago),
        ),
    )
    articles = Article.objects.aggregate(
        pending=Count("id", filter=Q(status=Article.Status.PENDING)),
        week_published=Count(
            "id",
            filter=Q(status=Article.Status.PUBLISHED, published_at__gte=week_ago),
        ),
    )

    return {
        "helpdesk": helpdesk,
        "todo": [
            {
                "key": "articles",
                "label": "Artikel menunggu review",
                "value": articles["pending"],
                "icon": "file-clock",
                "tone": "warning",
                "href": reverse("dashboard:admin_article_list") + "?status=PENDING",
                "cta": "Tinjau artikel",
            },
            {
                "key": "donations",
                "label": "Donasi menunggu verifikasi",
                "value": donations["pending"],
                "hint": donations["pending_amount"],
                "icon": "hand-coins",
                "tone": "secondary",
                "href": reverse("donations:verification_queue") + "?status=PENDING",
                "cta": "Verifikasi donasi",
            },
            {
                "key": "unassigned",
                "label": "Tiket belum ditugaskan",
                "value": helpdesk["unassigned"],
                "icon": "inbox",
                "tone": "danger",
                "href": reverse("dashboard:admin_ticket_list")
                + "?assignment=unassigned",
                "cta": "Ambil tiket",
            },
            {
                "key": "mine",
                "label": "Tiket ditugaskan ke kamu",
                "value": helpdesk["assigned_to_me"],
                "icon": "user-check",
                "tone": "primary",
                "href": reverse("dashboard:admin_ticket_list") + "?assignment=me",
                "cta": "Balas tiket",
            },
        ],
        "week": [
            {
                "label": "Pengguna baru",
                "value": User.objects.filter(date_joined__gte=week_ago).count(),
                "icon": "user-plus",
            },
            {
                "label": "Postingan baru",
                "value": Post.objects.filter(created_at__gte=week_ago).count(),
                "icon": "message-square-text",
            },
            {
                "label": "Artikel terbit",
                "value": articles["week_published"],
                "icon": "newspaper",
            },
            {
                "label": "Donasi disetujui",
                "value": donations["week_amount"] or Decimal("0"),
                "icon": "hand-heart",
                "is_money": True,
            },
        ],
    }


@admin_required
def admin_dashboard(request: HttpRequest):

    sidebar_sections = get_sidebar_sections(request.user)

    return render_dashboard(
        request,
        "dashboard/overview.html",
        {
            "greeting": get_greeting(),
            "admin_name": request.user.first_name
            or request.user.get_full_name()
            or request.user.username,
            "today": timezone.localdate(),
            # The section cards reuse the sidebar's "Kelola" items
            "management_items": _section_items(sidebar_sections, "manage"),
            **build_overview(request.user),
        },
        sidebar_sections=sidebar_sections,
    )


# ========================== Helpdesk Admin Dashboard Views ========================== #

ACTIVE_STATUSES = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]

# Assignment filter: value -> (label, icon). Empty value = anyone.
ASSIGNMENT_OPTIONS = {
    "": ("Siapa saja", "users"),
    "me": ("Ditugaskan ke saya", "user-check"),
    "unassigned": ("Belum ditugaskan", "inbox"),
    "others": ("Ditugaskan ke lainnya", "user-round"),
}


def _url_or_none(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def parse_admin_ticket_query(request: HttpRequest):
    """The user helpdesk's status/priority/sort/search (already validated), plus
    assignment."""

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
            | Q(assigned_to__username__icontains=search)
            | Q(assigned_to__first_name__icontains=search)
            | Q(assigned_to__last_name__icontains=search)
            | Q(assigned_to__email__icontains=search)
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
        assigned_to_me=Count(
            "id", filter=Q(assigned_to=admin, status__in=ACTIVE_STATUSES)
        ),
        unassigned=Count(
            "id", filter=Q(assigned_to__isnull=True, status__in=ACTIVE_STATUSES)
        ),
        high_active=Count(
            "id", filter=Q(priority=Ticket.Priority.HIGH, status__in=ACTIVE_STATUSES)
        ),
        # updated_at is the closest signal to "resolved at" the model has
        resolved_week=Count(
            "id", filter=Q(status=Ticket.Status.RESOLVED, updated_at__gte=week_ago)
        ),
        **{
            f"status_{value}": Count("id", filter=Q(status=value))
            for value in Ticket.Status.values
        },
        **{
            f"active_{value}": Count(
                "id", filter=Q(priority=value, status__in=ACTIVE_STATUSES)
            )
            for value in Ticket.Priority.values
        },
    )

    return {
        "kpis": {
            key: counts[key]
            for key in [
                "total",
                "active",
                "assigned_to_me",
                "unassigned",
                "high_active",
                "resolved_week",
            ]
        },
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
    sorting_options = {
        label: [value, icon] for value, (label, icon, _fields) in SORT_OPTIONS.items()
    }

    return render_dashboard(
        request,
        "dashboard/helpdesk/ticket_list.html",
        {
            "status_options": STATUS_FILTER_OPTIONS,
            "priority_options": PRIORITY_FILTER_OPTIONS,
            "assignment_options": {
                label: [value, icon]
                for value, (label, icon) in ASSIGNMENT_OPTIONS.items()
            },
            "sorting_options": sorting_options,
            "query": query,
            "status_label": str(dict(Ticket.Status.choices).get(query["status"], "")),
            "priority_label": str(
                dict(Ticket.Priority.choices).get(query["priority"], "")
            ),
            "assignment_label": ASSIGNMENT_OPTIONS[query["assignment"]][0]
            if query["assignment"]
            else "",
            "sort_label": SORT_OPTIONS[query["sort"]][0],
        },
    )


@admin_required
def admin_ticket_list_api(request: HttpRequest):
    """Both lists for the page, each paged on its own (10 per page):
    the admin's assigned tickets (?mine_page=) and every other ticket (?page=)."""

    query = parse_admin_ticket_query(request)
    tickets = (
        apply_admin_ticket_query(Ticket.objects.all(), query, request.user)
        .select_related("requester", "assigned_to")
        .annotate(messages_count=Count("messages"))
    )

    assigned, assigned_pagination = paginate(
        tickets.filter(assigned_to=request.user), parse_page(request, "mine_page")
    )
    others, others_pagination = paginate(
        tickets.exclude(assigned_to=request.user), parse_page(request, "page")
    )

    return JsonResponse(
        {
            "assigned": [serialize_admin_ticket(t, request.user) for t in assigned],
            "assigned_pagination": assigned_pagination,
            "others": [serialize_admin_ticket(t, request.user) for t in others],
            "others_pagination": others_pagination,
            "total_count": Ticket.objects.count(),
        }
    )


@admin_required
def admin_ticket_stats_api(request: HttpRequest):
    return JsonResponse(build_admin_ticket_stats(request.user))


@admin_required
@require_POST
def admin_ticket_assign(request: HttpRequest, ticket_id):
    """Take an unassigned ticket. Admins only reply to their own tickets, so this is
    how work gets picked up."""

    # Row lock + the owner check: two admins clicking at once can't both take it
    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), id=ticket_id)
        if ticket.assigned_to_id and ticket.assigned_to_id != request.user.id:
            owner = ticket.assigned_to.get_full_name() or ticket.assigned_to.username
            return JsonResponse(
                {"error": f"Tiket ini sudah diambil {owner}."}, status=409
            )

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


# =========================== Admin Ticket Detail =========================== #

# The statuses an admin can set from the ticket page: (value, label, icon, icon color)
ADMIN_STATUS_ACTIONS = [
    (Ticket.Status.IN_PROGRESS, "Diproses", "loader", "text-secondary-700"),
    (Ticket.Status.RESOLVED, "Selesai", "circle-check", "text-primary-700"),
    (Ticket.Status.CLOSED, "Ditutup", "lock", "text-secondary-500"),
]
ADMIN_SETTABLE_STATUSES = {
    value for value, _label, _icon, _color in ADMIN_STATUS_ACTIONS
}


# The assigned coordinator owns the ticket: only they reply and change its status.
# (To let every admin change status, return True here.)
def can_manage_ticket(admin, ticket):
    return ticket.assigned_to_id == admin.id


def get_admin_ticket(ticket_id):
    return get_object_or_404(
        Ticket.objects.select_related("requester", "assigned_to").annotate(
            messages_count=Count("messages")
        ),
        id=ticket_id,
    )


def serialize_admin_ticket_detail(ticket, admin):
    return {
        **serialize_admin_ticket(ticket, admin),
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
        "attachments": [
            serialize_attachment(attachment) for attachment in ticket.attachments.all()
        ],
        "can_update_status": can_manage_ticket(admin, ticket),
    }


@admin_required
def admin_ticket_detail(request: HttpRequest, ticket_id):

    ticket = get_admin_ticket(ticket_id)
    is_assignee = can_manage_ticket(request.user, ticket)

    return render_dashboard(
        request,
        "dashboard/helpdesk/ticket_detail.html",
        {
            "ticket": ticket,
            "ticket_id_str": str(ticket.id),
            "short_id": str(ticket.id)[:8].upper(),
            "is_assignee": is_assignee,
            "ticket_is_closed": ticket.status == Ticket.Status.CLOSED,
            "status_actions": ADMIN_STATUS_ACTIONS,
            "assignee_name": (
                ticket.assigned_to.get_full_name() or ticket.assigned_to.username
            )
            if ticket.assigned_to
            else "",
        },
    )


@admin_required
def admin_ticket_detail_api(request: HttpRequest, ticket_id):

    ticket = get_admin_ticket(ticket_id)
    messages = ticket.messages.select_related("author", "reply_to__author")

    return JsonResponse(
        {
            "ticket": serialize_admin_ticket_detail(ticket, request.user),
            "messages": [
                serialize_ticket_message(message, request.user) for message in messages
            ],
        }
    )


@admin_required
@require_POST
def admin_ticket_message_create(request: HttpRequest, ticket_id):
    """Reply as the assigned coordinator (same rules as the user side:
    create_ticket_message)."""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    response = create_ticket_message(request, ticket)

    # Without JS the form posts here directly: go back to the ticket page
    if (
        "application/json" not in request.headers.get("Accept", "")
        and response.status_code == 201
    ):
        return redirect("dashboard:admin_ticket_detail", ticket_id=ticket.id)
    return response


@admin_required
@require_POST
def admin_ticket_update(request: HttpRequest, ticket_id):
    """Change a ticket's status (In progress / Resolved / Closed). Assigned
    coordinator only."""

    status = request.POST.get("status", "")
    if status not in ADMIN_SETTABLE_STATUSES:
        return JsonResponse(
            {"error": "Pilih Diproses, Selesai, atau Ditutup."}, status=400
        )

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), id=ticket_id)
        if not can_manage_ticket(request.user, ticket):
            return JsonResponse(
                {"error": ("Hanya koordinator tiket yang bisa mengubah statusnya.")},
                status=403,
            )

        if ticket.status != status:
            ticket.status = status
            # closed_at records when it was closed; reopening clears it
            ticket.closed_at = (
                timezone.now() if status == Ticket.Status.CLOSED else None
            )
            ticket.save(update_fields=["status", "closed_at", "updated_at"])

    return JsonResponse(
        {
            "ticket": serialize_admin_ticket_detail(
                get_admin_ticket(ticket_id), request.user
            )
        }
    )


# ==================================================================================== #


# ==================================================================================== #
#                                 Challenges Management                                #
# ==================================================================================== #


@admin_required
def admin_challenge_list(request: HttpRequest):
    """Admin dashboard view for managing all challenges, viewing participation stats,
    filtering by status, and accessing CRUD operations."""
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "all")
    today = timezone.localdate()

    challenges = Challenge.objects.annotate(
        participants_count=Count("participations")
    ).order_by("-created_at")

    if search_query:
        challenges = challenges.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    if status_filter == "active":
        challenges = challenges.filter(
            is_published=True, start_date__lte=today, end_date__gte=today
        )
    elif status_filter == "upcoming":
        challenges = challenges.filter(is_published=True, start_date__gt=today)
    elif status_filter == "ended":
        challenges = challenges.filter(is_published=True, end_date__lt=today)
    elif status_filter == "draft":
        challenges = challenges.filter(is_published=False)

    status_options = {
        "Semua status": ["all", "layers"],
        "Berjalan": ["active", "flame"],
        "Segera": ["upcoming", "calendar"],
        "Selesai": ["ended", "award"],
        "Draf": ["draft", "file-pen"],
    }
    label_map = {
        "all": "Semua status",
        "active": "Berjalan",
        "upcoming": "Segera",
        "ended": "Selesai",
        "draft": "Draf",
    }
    if status_filter not in label_map:
        status_filter = "all"
    status_label = label_map[status_filter]

    # Metric snapshots for the admin overview
    total_challenges = Challenge.objects.count()
    active_challenges = Challenge.objects.filter(
        is_published=True, start_date__lte=today, end_date__gte=today
    ).count()
    total_participants = ChallengeParticipation.objects.count()
    draft_challenges = Challenge.objects.filter(is_published=False).count()

    page_challenges, pagination = paginate(
        challenges, parse_page(request), per_page=CHALLENGES_PER_PAGE
    )

    def page_url(page=None, **overrides):
        params = {"search": search_query, "status": status_filter, "page": page}
        params.update(overrides)
        params = {
            key: value
            for key, value in params.items()
            if value and value != "all" and not (key == "page" and value == 1)
        }
        base = reverse("dashboard:admin_challenge_list")
        return f"{base}?{urlencode(params)}" if params else base

    pagination["prev_url"] = (
        page_url(pagination["page"] - 1) if pagination["page"] > 1 else None
    )
    pagination["next_url"] = (
        page_url(pagination["page"] + 1)
        if pagination["page"] < pagination["total_pages"]
        else None
    )

    context = {
        "challenges": page_challenges,
        "pagination": pagination,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_options": status_options,
        "status_label": status_label,
        "clear_search_url": page_url(search="", page=None),
        "clear_status_url": page_url(status="all", page=None),
        "reset_url": reverse("dashboard:admin_challenge_list"),
        "today": today,
        "metrics": {
            "total": total_challenges,
            "active": active_challenges,
            "participants": total_participants,
            "draft": draft_challenges,
        },
    }
    return render_dashboard(
        request, "dashboard/challenges/challenge_list.html", context
    )


def challenge_form_dropdowns(form):
    """Data komponen dropdown untuk pilihan target dan lencana di form challenge."""
    goal_value = str(form["goal_type"].value() or Challenge.GoalType.CHECK_IN)
    goal_options = {
        str(label): [value, Challenge(goal_type=value).goal_icon]
        for value, label in Challenge.GoalType.choices
    }

    badge_value = str(form["badge"].value() or "")
    badge_options = {"Tanpa lencana": ["", "circle-off"]}
    badge_label = "Tanpa lencana"
    for badge in form.fields["badge"].queryset:
        badge_options[badge.name] = [str(badge.pk), badge.icon]
        if str(badge.pk) == badge_value:
            badge_label = badge.name

    return {
        "goal_options": goal_options,
        "goal_value": goal_value,
        "goal_label": str(dict(Challenge.GoalType.choices).get(goal_value, "")),
        "badge_options": badge_options,
        "badge_value": badge_value,
        "badge_label": badge_label,
    }


@admin_required
def admin_challenge_create(request: HttpRequest):
    """Create a new challenge from within the admin dashboard."""
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save()
            messages.success(request, f"Challenge “{challenge.title}” berhasil dibuat.")
            return redirect("dashboard:admin_challenge_list")
    else:
        form = ChallengeForm()

    context = {
        "form": form,
        "is_edit": False,
        "title": "Challenge baru",
        "back_url": reverse("dashboard:admin_challenge_list"),
        **challenge_form_dropdowns(form),
    }
    return render_dashboard(
        request, "dashboard/challenges/challenge_form.html", context
    )


@admin_required
def admin_challenge_update(request: HttpRequest, slug):
    """Edit an existing challenge from within the admin dashboard."""
    challenge = get_object_or_404(Challenge, slug=slug)

    if request.method == "POST":
        form = ChallengeForm(request.POST, instance=challenge)
        if form.is_valid():
            challenge = form.save()
            messages.success(
                request, f"Challenge “{challenge.title}” berhasil diperbarui."
            )
            return redirect("dashboard:admin_challenge_list")
    else:
        form = ChallengeForm(instance=challenge)

    context = {
        "form": form,
        "challenge": challenge,
        "is_edit": True,
        "title": f"Edit challenge: {challenge.title}",
        "back_url": reverse("dashboard:admin_challenge_list"),
        **challenge_form_dropdowns(form),
    }
    return render_dashboard(
        request, "dashboard/challenges/challenge_form.html", context
    )


@admin_required
@require_POST
def admin_challenge_delete(request: HttpRequest, slug):
    """Safely delete an unparticipated challenge from within the admin dashboard."""
    challenge = get_object_or_404(Challenge, slug=slug)
    participants_count = challenge.participations.count()

    if participants_count > 0:
        messages.error(
            request,
            (
                f"“{challenge.title}” tidak bisa dihapus karena sudah punya "
                f"{participants_count} peserta. Ubah jadi draf saja."
            ),
        )
    else:
        challenge_title = challenge.title
        challenge.delete()
        messages.success(request, f"Challenge “{challenge_title}” berhasil dihapus.")

    return redirect("dashboard:admin_challenge_list")


# ================================== Badges Management =============================== #


@admin_required
def admin_badge_list(request: HttpRequest):
    """Every badge with how many challenges offer it and how many people own it."""
    badges = Badge.objects.annotate(
        challenge_count=Count("challenges", distinct=True),
        holder_count=Count("awarded_to", distinct=True),
    ).order_by("name")
    return render_dashboard(
        request,
        "dashboard/challenges/badge_list.html",
        {"badges": badges, "back_url": reverse("dashboard:admin_challenge_list")},
    )


def _badge_form_page(request, badge=None):
    form = BadgeForm(request.POST or None, instance=badge)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(
            request,
            f"Lencana “{saved.name}” berhasil {'diperbarui' if badge else 'dibuat'}.",
        )
        return redirect("dashboard:admin_badge_list")
    return render_dashboard(
        request,
        "dashboard/challenges/badge_form.html",
        {
            "form": form,
            "badge": badge,
            "is_edit": badge is not None,
            "title": f"Edit lencana: {badge.name}" if badge else "Lencana baru",
            "back_url": reverse("dashboard:admin_badge_list"),
            "tone_choices": Badge.Tone.choices,
            "icon_choices": Badge.ICON_CHOICES,
        },
    )


@admin_required
def admin_badge_create(request: HttpRequest):
    return _badge_form_page(request)


@admin_required
def admin_badge_update(request: HttpRequest, slug):
    return _badge_form_page(request, get_object_or_404(Badge, slug=slug))


@admin_required
@require_POST
def admin_badge_delete(request: HttpRequest, slug):
    """Delete a badge nobody owns yet (owned badges are part of people's history)."""
    badge = get_object_or_404(Badge, slug=slug)
    holders = badge.awarded_to.count()
    if holders:
        messages.error(
            request,
            f"“{badge.name}” tidak bisa dihapus karena sudah dimiliki {holders} orang.",
        )
    else:
        name = badge.name
        badge.delete()
        messages.success(request, f"Lencana “{name}” berhasil dihapus.")
    return redirect("dashboard:admin_badge_list")


# ============================== Community Goals Management ========================== #


@admin_required
def admin_goal_list(request: HttpRequest):
    """Every community goal with its live progress."""
    goals = [
        goal_progress(goal) for goal in CommunityGoal.objects.order_by("-end_date")
    ]
    return render_dashboard(
        request,
        "dashboard/challenges/goal_list.html",
        {"goals": goals, "back_url": reverse("dashboard:admin_challenge_list")},
    )


def _goal_form_page(request, goal=None):
    form = CommunityGoalForm(request.POST or None, instance=goal)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(
            request,
            f"Target “{saved.title}” berhasil {'diperbarui' if goal else 'dibuat'}.",
        )
        return redirect("dashboard:admin_goal_list")
    return render_dashboard(
        request,
        "dashboard/challenges/goal_form.html",
        {
            "form": form,
            "goal": goal,
            "title": f"Edit target: {goal.title}" if goal else "Target komunitas baru",
            "back_url": reverse("dashboard:admin_goal_list"),
        },
    )


@admin_required
def admin_goal_create(request: HttpRequest):
    return _goal_form_page(request)


@admin_required
def admin_goal_update(request: HttpRequest, pk):
    return _goal_form_page(request, get_object_or_404(CommunityGoal, pk=pk))


@admin_required
@require_POST
def admin_goal_delete(request: HttpRequest, pk):
    goal = get_object_or_404(CommunityGoal, pk=pk)
    title = goal.title
    goal.delete()
    messages.success(request, f"Target “{title}” berhasil dihapus.")
    return redirect("dashboard:admin_goal_list")


# ==================================================================================== #
#                                 Shared list helpers                                  #
# ==================================================================================== #

LIST_PER_PAGE = 15


def _choice(request, name, options, default="all"):
    value = request.GET.get(name, default)
    return value if value in options else default


def _dropdown(options):
    """{value: (label, icon, ...)} -> format komponen dropdown {label: [value, icon]}"""
    return {label: [value, icon] for value, (label, icon, *_rest) in options.items()}


def _list_url(url_name, params, **overrides):
    """URL daftar dengan filter yang sama; nilai default tidak ikut ditulis."""
    params = {**params, **overrides}
    params = {
        key: value
        for key, value in params.items()
        if value and value != "all" and not (key == "page" and str(value) == "1")
    }
    base = reverse(url_name)
    return f"{base}?{urlencode(params)}" if params else base


def _filter_chips(url_name, params, labels):
    """Chip filter aktif. labels: {param: label tampil}, hanya yang tidak default."""
    return [
        {"label": label, "url": _list_url(url_name, params, **{key: ""})}
        for key, label in labels.items()
        if params.get(key) not in ("", "all", None)
    ]


def _page(request, queryset, per_page=LIST_PER_PAGE):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


# ==================================================================================== #
#                                   Users Management                                   #
# ==================================================================================== #

USER_ROLE_FILTERS = {
    "all": ("Semua peran", "users"),
    User.Role.ADMIN: ("Admin", "shield-check"),
    User.Role.USER: ("Pengguna", "user-round"),
}
USER_STATE_FILTERS = {
    "all": ("Semua status", "layers"),
    "active": ("Aktif", "circle-check"),
    "inactive": ("Nonaktif", "circle-slash"),
}
USER_SORTS = {
    "newest": ("Terbaru gabung", "arrow-down-wide-narrow", ("-date_joined",)),
    "last_login": (
        "Terakhir masuk",
        "clock",
        (F("last_login").desc(nulls_last=True),),
    ),
    "name": ("Nama A–Z", "arrow-down-a-z", ("first_name", "last_name", "username")),
}


def _user_guard(admin, target):
    """Alasan admin tidak boleh mengubah akun ini, atau None."""
    if target.pk == admin.pk:
        return "Akunmu sendiri tidak bisa diubah dari sini."
    if target.is_superuser and not admin.is_superuser:
        return "Akun superuser hanya bisa diubah oleh superuser."
    return None


@admin_required
def admin_user_list(request: HttpRequest):
    params = {
        "search": request.GET.get("search", "").strip()[:100],
        "role": _choice(request, "role", USER_ROLE_FILTERS),
        "state": _choice(request, "state", USER_STATE_FILTERS),
        "sort": _choice(request, "sort", USER_SORTS, default="newest"),
    }

    users = User.objects.annotate(
        post_count=Count("posts", distinct=True),
        article_count=Count("articles", distinct=True),
    )
    if params["search"]:
        term = params["search"]
        users = users.filter(
            Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
        )
    if params["role"] != "all":
        users = users.filter(role=params["role"])
    if params["state"] != "all":
        users = users.filter(is_active=params["state"] == "active")
    users = users.order_by(*USER_SORTS[params["sort"]][2], "username")

    week_ago = timezone.now() - timedelta(days=7)
    metrics = User.objects.aggregate(
        total=Count("id"),
        admins=Count("id", filter=Q(role=User.Role.ADMIN)),
        new_week=Count("id", filter=Q(date_joined__gte=week_ago)),
        inactive=Count("id", filter=Q(is_active=False)),
    )

    url_name = "dashboard:admin_user_list"
    return render_dashboard(
        request,
        "dashboard/users/user_list.html",
        {
            "page_obj": _page(request, users),
            "params": params,
            "metrics": metrics,
            "role_options": _dropdown(USER_ROLE_FILTERS),
            "state_options": _dropdown(USER_STATE_FILTERS),
            "sort_options": _dropdown(USER_SORTS),
            "role_label": USER_ROLE_FILTERS[params["role"]][0],
            "state_label": USER_STATE_FILTERS[params["state"]][0],
            "sort_label": USER_SORTS[params["sort"]][0],
            "chips": _filter_chips(
                url_name,
                params,
                {
                    "search": f"“{params['search']}”",
                    "role": USER_ROLE_FILTERS[params["role"]][0],
                    "state": USER_STATE_FILTERS[params["state"]][0],
                },
            ),
            "reset_url": reverse(url_name),
        },
    )


@admin_required
def admin_user_detail(request: HttpRequest, user_id):
    member = get_object_or_404(User, pk=user_id)
    donations = Donation.objects.filter(donor=member)
    impact = impact_summary(member)
    donated = donations.aggregate(
        approved=Sum("amount", filter=Q(status=Donation.Status.APPROVED)),
        pending=Count("id", filter=Q(status=Donation.Status.PENDING)),
    )
    tickets = Ticket.objects.filter(requester=member).count()

    return render_dashboard(
        request,
        "dashboard/users/user_detail.html",
        {
            "member": member,
            "guard": _user_guard(request.user, member),
            "stats": [
                {
                    "icon": "message-square-text",
                    "label": "Postingan",
                    "value": impact["posts"],
                    "hint": f"{impact['likes_received']} suka diterima",
                    "tone": "primary",
                },
                {
                    "icon": "newspaper",
                    "label": "Artikel terbit",
                    "value": impact["articles_published"],
                    "hint": f"{impact['articles_read']} artikel dibaca",
                    "tone": "info",
                },
                {
                    "icon": "trophy",
                    "label": "Challenge",
                    "value": impact["challenges_joined"],
                    "hint": f"{impact['challenges_completed']} selesai · "
                    f"{impact['badges']} lencana",
                    "tone": "warning",
                },
                {
                    "icon": "hand-heart",
                    "label": "Donasi disetujui",
                    "prefix": "Rp",
                    "value": rupiah(donated["approved"] or 0),
                    "hint": f"{donated['pending']} menunggu · {tickets} tiket bantuan",
                    "tone": "neutral",
                },
            ],
            "recent_posts": member.posts.annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
            ).order_by("-created_at")[:5],
            "recent_articles": member.articles.select_related("category").order_by(
                "-updated_at"
            )[:5],
            "recent_donations": donations.select_related("campaign").order_by(
                "-created_at"
            )[:5],
        },
        active_section="users",
    )


@admin_required
@require_POST
def admin_user_role(request: HttpRequest, user_id):
    member = get_object_or_404(User, pk=user_id)
    back = safe_next_url(request, reverse("dashboard:admin_user_list"))
    role = request.POST.get("role", "")

    if role not in User.Role.values:
        messages.error(request, "Pilih peran Admin atau Pengguna.")
    elif problem := _user_guard(request.user, member):
        messages.error(request, problem)
    elif member.role == role:
        messages.info(
            request, f"{member.display_name} sudah jadi {member.get_role_display()}."
        )
    else:
        member.role = role
        member.save(update_fields=["role", "updated_at"])
        messages.success(
            request,
            f"{member.display_name} sekarang jadi {member.get_role_display()}.",
        )
    return redirect(back)


@admin_required
@require_POST
def admin_user_active(request: HttpRequest, user_id):
    """Nonaktifkan atau aktifkan lagi akun. Akun nonaktif langsung keluar dan
    tidak bisa masuk; datanya tetap tersimpan."""
    member = get_object_or_404(User, pk=user_id)
    back = safe_next_url(request, reverse("dashboard:admin_user_list"))

    if problem := _user_guard(request.user, member):
        messages.error(request, problem)
    else:
        member.is_active = request.POST.get("active") == "1"
        member.save(update_fields=["is_active", "updated_at"])
        if member.is_active:
            messages.success(request, f"Akun {member.display_name} aktif lagi.")
        else:
            messages.success(
                request,
                f"Akun {member.display_name} dinonaktifkan dan tidak bisa masuk "
                "sampai diaktifkan lagi.",
            )
    return redirect(back)


# ==================================================================================== #
#                                 Articles Management                                  #
# ==================================================================================== #

ARTICLE_STATUS_FILTERS = {
    "all": ("Semua status", "layers"),
    Article.Status.PENDING: ("Menunggu review", "hourglass"),
    Article.Status.PUBLISHED: ("Terbit", "globe"),
    Article.Status.REJECTED: ("Perlu revisi", "message-square-warning"),
    Article.Status.DRAFT: ("Draf", "file-pen"),
}


@admin_required
def admin_article_list(request: HttpRequest):
    category_filters = {
        "all": ("Semua kategori", "folder"),
        **{
            c.slug: (c.name, "folder-open")
            for c in ArticleCategory.objects.order_by("name")
        },
    }
    params = {
        "search": request.GET.get("search", "").strip()[:100],
        "status": _choice(request, "status", ARTICLE_STATUS_FILTERS),
        "category": _choice(request, "category", category_filters),
    }

    articles = Article.objects.select_related("author", "category").annotate(
        read_count=Count("reads", distinct=True),
        # Yang menunggu review selalu di atas
        needs_review=Case(
            When(status=Article.Status.PENDING, then=Value(0)), default=Value(1)
        ),
    )
    if params["search"]:
        term = params["search"]
        articles = articles.filter(
            Q(title__icontains=term)
            | Q(summary__icontains=term)
            | Q(author__username__icontains=term)
            | Q(author__first_name__icontains=term)
            | Q(author__last_name__icontains=term)
        )
    if params["status"] != "all":
        articles = articles.filter(status=params["status"])
    if params["category"] != "all":
        articles = articles.filter(category__slug=params["category"])
    articles = articles.order_by("needs_review", "-updated_at")

    metrics = Article.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status=Article.Status.PUBLISHED)),
        pending=Count("id", filter=Q(status=Article.Status.PENDING)),
        drafts=Count(
            "id",
            filter=Q(status__in=[Article.Status.DRAFT, Article.Status.REJECTED]),
        ),
    )

    url_name = "dashboard:admin_article_list"
    return render_dashboard(
        request,
        "dashboard/articles/article_list.html",
        {
            "page_obj": _page(request, articles),
            "params": params,
            "metrics": metrics,
            "status_options": _dropdown(ARTICLE_STATUS_FILTERS),
            "category_options": _dropdown(category_filters),
            "status_label": ARTICLE_STATUS_FILTERS[params["status"]][0],
            "category_label": category_filters[params["category"]][0],
            "chips": _filter_chips(
                url_name,
                params,
                {
                    "search": f"“{params['search']}”",
                    "status": ARTICLE_STATUS_FILTERS[params["status"]][0],
                    "category": category_filters[params["category"]][0],
                },
            ),
            "reset_url": reverse(url_name),
        },
    )


# ==================================================================================== #
#                                 Donations Management                                 #
# ==================================================================================== #

CAMPAIGN_STATUS_FILTERS = {
    "all": ("Semua status", "layers"),
    Campaign.Status.PUBLISHED: ("Terbit", "globe"),
    Campaign.Status.DRAFT: ("Draf", "file-pen"),
    Campaign.Status.CLOSED: ("Ditutup", "lock"),
}


@admin_required
def admin_donation_list(request: HttpRequest):
    params = {
        "search": request.GET.get("search", "").strip()[:100],
        "status": _choice(request, "status", CAMPAIGN_STATUS_FILTERS),
    }

    campaigns = campaign_queryset().annotate(
        pending_count=Count(
            "donations", filter=Q(donations__status=Donation.Status.PENDING)
        ),
        donor_count=Count(
            "donations__donor",
            filter=Q(donations__status=Donation.Status.APPROVED),
            distinct=True,
        ),
    )
    if params["search"]:
        campaigns = campaigns.filter(
            Q(title__icontains=params["search"])
            | Q(description__icontains=params["search"])
        )
    if params["status"] != "all":
        campaigns = campaigns.filter(status=params["status"])
    page_obj = _page(request, campaigns.order_by("-created_at", "title"), per_page=10)
    for campaign in page_obj:
        campaign.progress = campaign_progress_percent(campaign)
        campaign.accepting = campaign_accepts_donations(campaign)

    totals = Donation.objects.aggregate(
        collected=Sum("amount", filter=Q(status=Donation.Status.APPROVED)),
        pending=Count("id", filter=Q(status=Donation.Status.PENDING)),
        pending_amount=Sum("amount", filter=Q(status=Donation.Status.PENDING)),
        donors=Count("donor", filter=Q(status=Donation.Status.APPROVED), distinct=True),
    )
    now = timezone.now()
    totals["open_campaigns"] = (
        Campaign.objects.filter(status=Campaign.Status.PUBLISHED)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .count()
    )

    url_name = "dashboard:admin_donation_list"
    return render_dashboard(
        request,
        "dashboard/donations/donation_overview.html",
        {
            "page_obj": page_obj,
            "params": params,
            "totals": totals,
            # Antrean: yang paling lama menunggu duluan
            "pending_donations": Donation.objects.filter(status=Donation.Status.PENDING)
            .select_related("campaign", "donor")
            .order_by("created_at")[:5],
            "status_options": _dropdown(CAMPAIGN_STATUS_FILTERS),
            "status_label": CAMPAIGN_STATUS_FILTERS[params["status"]][0],
            "chips": _filter_chips(
                url_name,
                params,
                {
                    "search": f"“{params['search']}”",
                    "status": CAMPAIGN_STATUS_FILTERS[params["status"]][0],
                },
            ),
            "reset_url": reverse(url_name),
        },
    )


# ==================================================================================== #
#                                   Feeds Moderation                                   #
# ==================================================================================== #

FEED_TABS = {"posts": "Postingan", "comments": "Komentar"}
POST_SORTS = {
    "newest": ("Terbaru", "clock", ("-created_at",)),
    "likes": ("Paling disukai", "heart", ("-like_count", "-created_at")),
    "comments": ("Paling ramai", "message-circle", ("-comment_count", "-created_at")),
}
# value -> (label, icon, jumlah hari ke belakang)
FEED_PERIODS = {
    "all": ("Kapan saja", "calendar", None),
    "today": ("Hari ini", "calendar-check", 0),
    "week": ("7 hari terakhir", "calendar-days", 7),
    "month": ("30 hari terakhir", "calendar-range", 30),
}


@admin_required
def admin_feed_list(request: HttpRequest):
    tab = request.GET.get("tab", "posts")
    if tab not in FEED_TABS:
        tab = "posts"
    params = {
        "tab": tab,
        "search": request.GET.get("search", "").strip()[:100],
        "period": _choice(request, "period", FEED_PERIODS),
        "sort": _choice(request, "sort", POST_SORTS, default="newest"),
    }

    term = params["search"]
    author_match = (
        Q(author__username__icontains=term)
        | Q(author__first_name__icontains=term)
        | Q(author__last_name__icontains=term)
    )
    if tab == "posts":
        items = Post.objects.select_related("author", "challenge").annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            image_count=Count("images", distinct=True),
        )
        items = items.order_by(*POST_SORTS[params["sort"]][2])
    else:
        items = Comment.objects.select_related(
            "author", "post__author", "parent__author"
        ).order_by("-created_at")
    if term:
        items = items.filter(Q(content__icontains=term) | author_match)
    days = FEED_PERIODS[params["period"]][2]
    if days is not None:
        start = timezone.localdate() - timedelta(days=days)
        items = items.filter(created_at__date__gte=start)

    week_ago = timezone.now() - timedelta(days=7)
    metrics = {
        **Post.objects.aggregate(
            posts=Count("id"),
            posts_week=Count("id", filter=Q(created_at__gte=week_ago)),
        ),
        "comments": Comment.objects.count(),
        "likes": Like.objects.count(),
    }

    url_name = "dashboard:admin_feed_list"
    return render_dashboard(
        request,
        "dashboard/feeds/feed_list.html",
        {
            "page_obj": _page(request, items),
            "params": params,
            "metrics": metrics,
            "tabs": [
                {
                    "key": key,
                    "label": label,
                    "url": _list_url(url_name, {"tab": key}),
                    "active": key == tab,
                }
                for key, label in FEED_TABS.items()
            ],
            "sort_options": _dropdown(POST_SORTS),
            "period_options": _dropdown(FEED_PERIODS),
            "sort_label": POST_SORTS[params["sort"]][0],
            "period_label": FEED_PERIODS[params["period"]][0],
            "chips": _filter_chips(
                url_name,
                params,
                {"search": f"“{term}”", "period": FEED_PERIODS[params["period"]][0]},
            ),
            "reset_url": _list_url(url_name, {"tab": tab}),
        },
    )


def _notify_removed(request, author, what, content):
    """Kabari penulis bahwa kontennya dihapus, plus alasan kalau diisi admin."""
    reason = request.POST.get("reason", "").strip()[:200]
    message = f"“{Truncator(content).chars(80)}”"
    if reason:
        message += f" Alasan: {reason}"
    notify(
        author,
        Notification.Kind.CONTENT_REMOVED,
        f"{what} kamu dihapus admin",
        message,
        actor=request.user,
    )


@admin_required
@require_POST
def admin_feed_post_delete(request: HttpRequest, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    _notify_removed(request, post.author, "Postingan", post.content)
    delete_post(post)
    messages.success(request, "Postingan dihapus.")
    return redirect(safe_next_url(request, reverse("dashboard:admin_feed_list")))


@admin_required
@require_POST
def admin_feed_comment_delete(request: HttpRequest, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("author"), pk=comment_id)
    _notify_removed(request, comment.author, "Komentar", comment.content)
    comment.delete()
    messages.success(request, "Komentar dihapus beserta balasannya.")
    return redirect(
        safe_next_url(request, reverse("dashboard:admin_feed_list") + "?tab=comments")
    )
