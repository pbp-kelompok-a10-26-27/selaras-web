from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.decorators import admin_required, login_required

from . import services
from .models import (
    Challenge,
    ChallengeParticipation,
    ChallengeProgress,
    UserBadge,
)
from .weather import get_current_weather_suggestion


def challenge_list(request):
    """List published challenges with search, filters, and weather."""

    search_query = request.GET.get("search", "").strip()

    status_filter = request.GET.get("status", "all")

    today = timezone.localdate()

    challenges = (
        Challenge.objects.filter(is_published=True)
        .select_related("badge")
        .annotate(participants_count=Count("participations"))
        .order_by("-created_at")
    )

    if search_query:
        challenges = challenges.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    is_authenticated = hasattr(request, "user") and request.user.is_authenticated

    joined_challenge_ids = set()

    if is_authenticated:
        joined_challenge_ids = set(
            request.user.challenge_participations.values_list("challenge_id", flat=True)
        )

    if status_filter == "my" and is_authenticated:
        challenges = challenges.filter(id__in=joined_challenge_ids)

    elif status_filter == "active":
        challenges = challenges.filter(start_date__lte=today, end_date__gte=today)

    elif status_filter == "upcoming":
        challenges = challenges.filter(start_date__gt=today)

    elif status_filter == "ended":
        challenges = challenges.filter(end_date__lt=today)

    user_lat = request.GET.get("lat") or request.session.get("user_lat")

    user_lon = request.GET.get("lon") or request.session.get("user_lon")

    weather = get_current_weather_suggestion(lat=user_lat, lon=user_lon)

    if weather.get("is_custom_location"):
        request.session["user_lat"] = weather["latitude"]

        request.session["user_lon"] = weather["longitude"]

    status_options = {
        "Semua challenge": ["all", "layers"],
        "Berjalan": ["active", "flame"],
        "Segera": ["upcoming", "calendar"],
    }

    if is_authenticated:
        status_options["Challenge saya"] = ["my", "user-check"]

    status_options["Selesai"] = ["ended", "award"]

    label_map = {
        "all": "Semua challenge",
        "active": "Berjalan",
        "upcoming": "Segera",
        "my": "Challenge saya",
        "ended": "Selesai",
    }

    if status_filter not in label_map or (
        status_filter == "my" and not is_authenticated
    ):
        status_filter = "all"

    status_label = label_map[status_filter]

    context = {
        "challenges": challenges,
        "community_goals": services.community_goals(request.user, limit=3),
        "weather": weather,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_options": status_options,
        "status_label": status_label,
        "joined_challenge_ids": joined_challenge_ids,
        "today": today,
        "result_count": challenges.count(),
    }

    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.GET.get("ajax") == "1"
    ):
        html = render_to_string(
            "challenges/partials/challenge_grid.html", context, request=request
        )

        return JsonResponse(
            {
                "html": html,
                "search_query": search_query,
                "status_filter": status_filter,
                "count": challenges.count(),
            }
        )

    if request.GET.get("format") == "json":
        data = [
            {
                "id": c.id,
                "title": c.title,
                "slug": c.slug,
                "description": c.description,
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat(),
                "is_active": c.start_date <= today <= c.end_date,
                "participants_count": c.participants_count,
                "is_joined": c.id in joined_challenge_ids,
            }
            for c in challenges
        ]

        return JsonResponse({"challenges": data, "count": len(data)})

    return render(request, "challenges/challenges.html", context)


def challenge_detail(request, slug):
    """Display challenge details, participation status, and progress."""

    challenge = get_object_or_404(
        Challenge.objects.select_related("badge"), slug=slug, is_published=True
    )
    today = timezone.localdate()
    participation = None
    progress = None
    progress_records = []
    already_checked_in_today = False
    streak, best_streak = 0, 0

    if request.user.is_authenticated:
        participation = (
            ChallengeParticipation.objects.filter(
                challenge=challenge, user=request.user
            )
            .select_related("challenge__badge", "user")
            .first()
        )
        if participation:
            # Also completes it (and awards the badge) if the goal was just reached
            progress, badge = services.evaluate(participation)
            if badge is not None:
                messages.success(
                    request, f"Target tercapai! Kamu dapat lencana “{badge.name}”."
                )
            progress_records = participation.progress_records.order_by("-progress_date")
            already_checked_in_today = progress_records.filter(
                progress_date=today
            ).exists()
            streak, best_streak = services.check_in_streaks(participation)

    # Rankings are only shown to the people taking part (and admins)
    ranking, my_rank, ranked_total = [], None, 0
    if participation is not None or (
        request.user.is_authenticated and request.user.is_admin
    ):
        ranking, my_rank, ranked_total = services.leaderboard(
            challenge, viewer=request.user if request.user.is_authenticated else None
        )

    context = {
        "challenge": challenge,
        "today": today,
        "duration_days": challenge.duration_days,
        "is_active": challenge.status == "active",
        "is_ended": challenge.status == "ended",
        "is_upcoming": challenge.status == "upcoming",
        "participation": participation,
        "is_joined": participation is not None,
        "already_checked_in_today": already_checked_in_today,
        "progress": progress,
        "days_completed": progress["current"] if progress else 0,
        "progress_percentage": progress["percent"] if progress else 0,
        "progress_records": progress_records,
        "streak": streak,
        "best_streak": best_streak,
        "ranking": ranking,
        "my_rank": my_rank,
        "ranked_total": ranked_total,
        "participants_count": challenge.participations.count(),
        "earned_badge": (
            UserBadge.objects.filter(user=request.user, badge=challenge.badge).exists()
            if request.user.is_authenticated and challenge.badge_id
            else False
        ),
    }

    return render(request, "challenges/challenge_detail.html", context)


@login_required
def join_challenge(request, slug):
    """Enables authenticated users to join an active challenge."""

    challenge = get_object_or_404(Challenge, slug=slug, is_published=True)

    today = timezone.localdate()

    if challenge.end_date < today:
        messages.warning(
            request, "Challenge ini sudah berakhir, jadi nggak bisa diikuti lagi."
        )

        return redirect("challenges:detail", slug=slug)

    if challenge.start_date > today:
        messages.warning(
            request, "Challenge ini belum dimulai. Tunggu tanggal mulainya, ya."
        )

        return redirect("challenges:detail", slug=slug)

    participation, created = ChallengeParticipation.objects.get_or_create(
        challenge=challenge, user=request.user
    )

    if created:
        messages.success(
            request,
            f"Kamu sudah gabung di “{challenge.title}”. Semangat!",
        )

    else:
        messages.info(request, "Kamu sudah ikut challenge ini.")

    return redirect("challenges:detail", slug=slug)


@login_required
def leave_challenge(request, slug):
    """Enables authenticated users to cancel/leave challenge participation."""

    challenge = get_object_or_404(Challenge, slug=slug)

    if request.method == "POST":
        participation = ChallengeParticipation.objects.filter(
            challenge=challenge, user=request.user
        ).first()

        if participation:
            participation.delete()

            messages.success(
                request,
                f"Kamu keluar dari “{challenge.title}”.",
            )

        else:
            messages.warning(request, "Kamu belum ikut challenge ini.")

    # Only same-site paths, so the form can't be used as an open redirect
    next_url = request.POST.get("next")

    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)

    return redirect("challenges:detail", slug=slug)


@login_required
def record_progress(request, slug):
    """Record or update the daily check-in for a check-in challenge."""

    challenge = get_object_or_404(Challenge, slug=slug, is_published=True)

    participation = get_object_or_404(
        ChallengeParticipation.objects.select_related("challenge__badge", "user"),
        challenge=challenge,
        user=request.user,
    )

    today = timezone.localdate()

    if request.method == "POST":
        if challenge.is_tracked:
            messages.info(
                request,
                "Challenge ini mencatat aktivitasmu otomatis, nggak perlu check-in.",
            )
            return redirect("challenges:detail", slug=slug)

        notes = request.POST.get("notes", "").strip()

        progress, created = ChallengeProgress.objects.get_or_create(
            participation=participation,
            progress_date=today,
            defaults={"notes": notes, "is_completed": True},
        )

        if not created:
            progress.notes = notes
            progress.is_completed = True
            progress.save()
            messages.success(request, "Catatan hari ini sudah diperbarui.")
        else:
            _, badge = services.evaluate(participation)
            if participation.completed_at and badge is not None:
                messages.success(
                    request,
                    f"Challenge selesai! Kamu dapat lencana “{badge.name}”.",
                )
            elif participation.completed_at:
                messages.success(request, "Challenge selesai! Kerja bagus!")
            else:
                messages.success(
                    request,
                    f"Progres {date_format(today, 'j F Y')} tersimpan.",
                )

    return redirect("challenges:detail", slug=slug)


@login_required
def challenge_history(request):
    """View user's challenge participation history, metrics, and badges."""

    tab = request.GET.get("tab", "all")

    raw_participations = (
        ChallengeParticipation.objects.filter(user=request.user)
        .select_related("challenge__badge", "user")
        .prefetch_related("progress_records")
        .order_by("-created_at")
    )

    participations_list = []

    total_completed = 0

    for p in raw_participations:
        progress, _ = services.evaluate(p)

        p.progress = progress

        p.duration_days = p.challenge.duration_days

        p.days_completed = progress["current"]

        p.progress_percentage = progress["percent"]

        p.is_completed = progress["completed"]

        if p.is_completed:
            total_completed += 1

        participations_list.append(p)

    total_joined = len(participations_list)

    total_ongoing = total_joined - total_completed

    total_checkins = ChallengeProgress.objects.filter(
        participation__user=request.user, is_completed=True
    ).count()

    if tab == "ongoing":
        display_participations = [p for p in participations_list if not p.is_completed]

    elif tab == "completed":
        display_participations = [p for p in participations_list if p.is_completed]

    else:
        display_participations = participations_list

    user_badges = (
        UserBadge.objects.filter(user=request.user)
        .select_related("badge", "challenge")
        .order_by("-awarded_at")
    )

    context = {
        "participations": display_participations,
        "total_joined": total_joined,
        "total_completed": total_completed,
        "total_ongoing": total_ongoing,
        "total_checkins": total_checkins,
        "user_badges": user_badges,
        "active_tab": tab,
    }

    return render(request, "challenges/challenge_history.html", context)


@admin_required
def challenge_create(request):
    """Redirect to the unified admin dashboard challenge creation view."""
    return redirect("dashboard:admin_challenge_create")


@admin_required
def challenge_update(request, slug):
    """Redirect to the unified admin dashboard challenge update view."""
    return redirect("dashboard:admin_challenge_update", slug=slug)


@admin_required
def challenge_delete(request, slug):
    """Redirect to the unified admin dashboard challenge list view."""
    return redirect("dashboard:admin_challenge_list")


def weather_api(request):
    """

    Internal server-side API proxy for weather recommendations.

    Accepts lat and lon query parameters, returns interpreted weather data,

    and caches coordinates in user session. Adheres to PRD Section 29.

    """

    lat = request.GET.get("lat")

    lon = request.GET.get("lon")

    weather_data = get_current_weather_suggestion(lat=lat, lon=lon)

    if weather_data.get("is_custom_location"):
        request.session["user_lat"] = weather_data["latitude"]

        request.session["user_lon"] = weather_data["longitude"]

    return JsonResponse(weather_data)
