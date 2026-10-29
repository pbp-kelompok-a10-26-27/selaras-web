from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import login_required

from . import services
from .models import Notification

FEED_SIZE = 8


def _inbox(user):
    return Notification.objects.filter(recipient=user).select_related("actor")


@login_required
@require_GET
def notification_list(request):
    show = request.GET.get("show", "all")
    if show not in ("all", "unread"):
        show = "all"
    notifications = _inbox(request.user)
    if show == "unread":
        notifications = notifications.filter(read_at__isnull=True)
    page_obj = Paginator(notifications, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "notifications/list.html",
        {
            "page_obj": page_obj,
            "notifications": page_obj.object_list,
            "show": show,
            "unread": services.unread_count(request.user),
        },
    )


@login_required
@require_GET
def notification_feed(request):
    """The latest few notifications for the navbar bell (HTML + unread count)."""
    items = list(_inbox(request.user)[:FEED_SIZE])
    return JsonResponse(
        {
            "unread": services.unread_count(request.user),
            "html": render_to_string(
                "notifications/partials/feed.html",
                {"notifications": items},
                request=request,
            ),
        }
    )


@login_required
@require_POST
def notification_read_all(request):
    services.mark_all_read(request.user)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"unread": 0})
    return redirect("notifications:list")


@login_required
@require_GET
def notification_open(request, notification_id):
    """Mark one notification read and go to what it is about."""
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    services.mark_read(notification)
    target = notification.url
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("notifications:list")
