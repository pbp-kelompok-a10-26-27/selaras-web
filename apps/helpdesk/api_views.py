from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.api_views import AuthenticatedAPIView

from .models import Ticket, TicketAttachment
from .serializers import (
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketMessageCreateSerializer,
    TicketMessageSerializer,
)
from .views import (
    TICKETS_PER_PAGE,
    apply_ticket_query,
    can_post_message,
    can_reply_to_ticket,
    can_view_ticket,
    get_ticket_stats,
    get_tickets,
    parse_ticket_query,
)


class TicketClosed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Tiket ini sudah ditutup dan tidak menerima balasan."
    default_code = "ticket_closed"


class TicketPagination(PageNumberPagination):
    page_size = TICKETS_PER_PAGE
    page_size_query_param = "page_size"
    max_page_size = 50


class TicketObjectMixin:
    """Loads the ticket named in the URL and refuses anyone who may not see it
    (the person who opened it, or an admin)."""

    def get_ticket(self, queryset=None):
        ticket = get_object_or_404(
            queryset or Ticket.objects.select_related("requester", "assigned_to"),
            id=self.kwargs["ticket_id"],
        )
        if not can_view_ticket(self.request.user, ticket):
            raise PermissionDenied("Kamu tidak punya akses ke tiket ini.")
        return ticket


class TicketListCreateAPIView(AuthenticatedAPIView, generics.ListCreateAPIView):
    """GET: your tickets (admins see all), newest first.
    Query: ``status``, ``priority``, ``search``, ``sort`` (-created_at, created_at,
    -priority, priority), ``page``, ``page_size``.

    POST: open a ticket (JSON, or multipart to attach screenshots).
    """

    pagination_class = TicketPagination

    def get_queryset(self):
        tickets = get_tickets(self.request.user)
        return (
            apply_ticket_query(tickets, parse_ticket_query(self.request))
            .select_related("requester", "assigned_to")
            .annotate(messages_count=Count("messages"))
        )

    def get_serializer_class(self):
        return (
            TicketCreateSerializer
            if self.request.method == "POST"
            else TicketListSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        data = TicketListSerializer(ticket, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class TicketStatsAPIView(AuthenticatedAPIView):
    """GET: ticket counts by status and priority."""

    def get(self, request):
        return Response({"stats": get_ticket_stats(get_tickets(request.user))})


class TicketDetailAPIView(
    TicketObjectMixin, AuthenticatedAPIView, generics.RetrieveDestroyAPIView
):
    """GET: one ticket with its screenshots. DELETE: remove it (opener or admin)."""

    serializer_class = TicketDetailSerializer

    def get_object(self):
        queryset = Ticket.objects.select_related(
            "requester", "assigned_to"
        ).prefetch_related("attachments")
        return self.get_ticket(queryset)


class TicketMessageListCreateAPIView(
    TicketObjectMixin, AuthenticatedAPIView, generics.ListCreateAPIView
):
    """GET: the conversation, oldest first. POST: reply, optionally quoting another
    message with ``reply_to``. Only the opener and the assigned admin may post, and
    closed tickets take no replies."""

    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketMessageCreateSerializer
        return TicketMessageSerializer

    def get_queryset(self):
        return self.get_ticket().messages.select_related("author", "reply_to__author")

    def create(self, request, *args, **kwargs):
        ticket = self.get_ticket()
        if not can_post_message(request.user, ticket):
            raise PermissionDenied(
                "Hanya pengirim dan koordinator tiket yang bisa membalas tiket ini."
            )
        if not can_reply_to_ticket(ticket):
            raise TicketClosed()

        serializer = TicketMessageCreateSerializer(
            data=request.data, context={"request": request, "ticket": ticket}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        data = TicketMessageSerializer(message, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class AttachmentDownloadAPIView(AuthenticatedAPIView):
    """GET: an uploaded screenshot, only for people who may see its ticket."""

    def get(self, request, attachment_id):
        attachment = get_object_or_404(
            TicketAttachment.objects.select_related("ticket"), id=attachment_id
        )
        if not can_view_ticket(request.user, attachment.ticket) or not attachment.file:
            raise Http404

        response = FileResponse(attachment.file.open("rb"))
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=3600"
        return response
