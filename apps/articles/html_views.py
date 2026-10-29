import logging
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permissions import is_admin
from apps.core.utils import get_query_params, safe_next_url
from apps.notifications.services import Kind, display_name, notify, notify_admins

from .forms import ArticleForm, CategoryForm
from .models import Article, ArticleCategory, ArticleRead, Tag

logger = logging.getLogger(__name__)

_FILTER_KEYS = ("search", "category", "tag", "status", "page_size")
Status = Article.Status
# Statuses an admin can filter the list by
ADMIN_STATUSES = (Status.PUBLISHED, Status.PENDING, Status.DRAFT, Status.REJECTED)
# Statuses in which the author (not an admin) may still edit or delete
AUTHOR_EDITABLE = (Status.DRAFT, Status.PENDING, Status.REJECTED)


def _admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def _list_url(request, **overrides):
    params = {
        key: value
        for key, value in request.GET.items()
        if key in _FILTER_KEYS and value
    }
    for key, value in overrides.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    query = urlencode(params)
    base_url = reverse("articles:html-list")
    return f"{base_url}?{query}" if query else base_url


def _with_reads(articles, user):
    if not user.is_authenticated:
        return articles
    return articles.annotate(
        read_by_me=Exists(ArticleRead.objects.filter(article=OuterRef("pk"), user=user))
    )


def _visible_articles(request, status):
    articles = Article.objects.select_related("category", "author").prefetch_related(
        "tags"
    )
    articles = _with_reads(articles, request.user)
    if not is_admin(request.user):
        return articles.filter(status=Status.PUBLISHED)
    return articles.filter(status=status)


def can_edit(user, article):
    if is_admin(user):
        return True
    return (
        user.is_authenticated
        and article.author_id == user.pk
        and article.status in AUTHOR_EDITABLE
    )


def article_html_list(request):
    query_params = get_query_params(request, ("search", "category", "tag", "status"))
    filters = query_params["filters"]
    pagination = query_params["pagination"]
    admin = is_admin(request.user)

    status = Status.PUBLISHED
    filter_error = ""
    if admin:
        status = filters.get("status", Status.PUBLISHED)
        if status not in ADMIN_STATUSES:
            filter_error = "Status artikel tidak dikenal."
            status = Status.PUBLISHED

    base_articles = _visible_articles(request, status)
    categories = ArticleCategory.objects.filter(articles__in=base_articles).distinct()
    categories = categories.order_by("name", "id")
    tags = (
        Tag.objects.filter(articles__in=base_articles).distinct().order_by("name", "id")
    )
    articles = base_articles

    search = filters.get("search", "")
    if search:
        articles = articles.filter(
            Q(title__icontains=search)
            | Q(summary__icontains=search)
            | Q(content__icontains=search)
            | Q(category__name__icontains=search)
        )

    category = filters.get("category", "")
    if category:
        articles = articles.filter(
            Q(category__slug__iexact=category) | Q(category__name__iexact=category)
        )

    tag = filters.get("tag", "")
    if tag:
        if not tags.filter(slug=tag).exists():
            filter_error = (
                "Tag yang dipilih tidak ditemukan pada artikel yang tersedia."
            )
            articles = articles.none()
        else:
            articles = articles.filter(tags__slug=tag)

    if status == Status.PENDING:
        # Oldest submission first, so nobody waits the longest
        articles = articles.order_by("submitted_at", "id")
    else:
        articles = articles.order_by("-published_at", "-created_at", "-id")
    paginator = Paginator(articles, pagination["page_size"])
    page_obj = paginator.get_page(pagination["page"])

    reader_stats = None
    if request.user.is_authenticated:
        reader_stats = {
            "read": request.user.article_reads.count(),
            "mine": Article.objects.filter(author=request.user).count(),
        }

    context = {
        "articles": page_obj.object_list,
        "page_obj": page_obj,
        "pagination": pagination,
        "filters": filters,
        "filter_error": filter_error,
        "categories": [
            {
                "name": item.name,
                "slug": item.slug,
                "active": item.slug == category
                or item.name.casefold() == category.casefold(),
                "url": _list_url(request, category=item.slug, page=None),
            }
            for item in categories
        ],
        "all_categories_url": _list_url(request, category=None, page=None),
        "tags": [
            {
                "name": item.name,
                "slug": item.slug,
                "active": item.slug == tag,
                "url": _list_url(request, tag=item.slug, page=None),
            }
            for item in tags
        ],
        "all_tags_url": _list_url(request, tag=None, page=None),
        "selected_status": status,
        "status_filters": _status_filters(request, status) if admin else [],
        "is_admin": admin,
        "reader_stats": reader_stats,
        "article_create_url": reverse("articles:html-create"),
    }
    response_status = 400 if filter_error else 200
    return render(request, "articles/list.html", context, status=response_status)


def _status_filters(request, selected):
    counts = dict(Article.objects.values_list("status").annotate(total=Count("id")))
    options = (
        (Status.PUBLISHED, "Terbit", "globe"),
        (Status.PENDING, "Menunggu review", "hourglass"),
        (Status.DRAFT, "Draf", "file-pen"),
        (Status.REJECTED, "Perlu revisi", "message-square-warning"),
    )
    return [
        {
            "label": f"{label} · {counts.get(key, 0)}",
            "icon": icon,
            "url": _list_url(request, status=key, page=None),
            "active": key == selected,
        }
        for key, label, icon in options
    ]


def article_html_detail(request, slug):
    articles = Article.objects.select_related(
        "category", "author", "reviewed_by"
    ).prefetch_related("tags")
    articles = _with_reads(articles, request.user)
    admin = is_admin(request.user)
    if not admin:
        visible = Q(status=Status.PUBLISHED)
        if request.user.is_authenticated:
            visible |= Q(author=request.user)
        articles = articles.filter(visible)
    article = get_object_or_404(articles, slug=slug)

    related = (
        Article.objects.filter(status=Status.PUBLISHED, category=article.category)
        .exclude(pk=article.pk)
        .select_related("category")
        .order_by("-published_at")[:3]
    )
    return render(
        request,
        "articles/detail.html",
        {
            "article": article,
            "is_admin": admin,
            "is_author": article.author_id == getattr(request.user, "pk", None),
            "can_edit": can_edit(request.user, article),
            "related_articles": related,
            "reads_count": article.reads.count(),
        },
    )


@login_required
@require_POST
def article_mark_read(request, slug):
    """Count a finished read (the page calls this once the reader reaches the end).

    Each reader counts once per article; challenge tracking listens for new reads.
    """
    article = get_object_or_404(Article, slug=slug, status=Status.PUBLISHED)
    _, created = ArticleRead.objects.get_or_create(user=request.user, article=article)
    return JsonResponse(
        {
            "read": True,
            "created": created,
            "total_read": request.user.article_reads.count(),
        },
        status=201 if created else 200,
    )


def _chosen_status(request, article=None):
    """What the submit button asked for, limited to what this user may do.

    Admins publish directly; everyone else saves a draft or sends it for review.
    """
    wanted = request.POST.get("status", Status.DRAFT)
    if is_admin(request.user):
        return wanted if wanted in (Status.DRAFT, Status.PUBLISHED) else Status.DRAFT
    return (
        Status.PENDING
        if wanted in (Status.PENDING, Status.PUBLISHED)
        else (Status.DRAFT)
    )


def _apply_status(request, article, old_status=None):
    """Set publish/review timestamps for the new status; returns what happened."""
    now = timezone.now()
    if article.status == Status.PUBLISHED:
        if old_status != Status.PUBLISHED or not article.published_at:
            article.published_at = now
        return "published"
    article.published_at = None
    if article.status == Status.PENDING:
        if old_status != Status.PENDING:
            article.submitted_at = now
            return "submitted"
        return "pending"
    return "draft"


def _after_save(request, article, outcome):
    detail_url = reverse("articles:html-detail", args=(article.slug,))
    if outcome == "submitted":
        notify_admins(
            Kind.ARTICLE_SUBMITTED,
            "Artikel baru menunggu review",
            f"“{article.title}” oleh {display_name(request.user)}.",
            url=detail_url,
            actor=request.user,
        )
        messages.success(
            request, "Artikel dikirim. Admin akan meninjaunya sebelum terbit."
        )
    elif outcome == "published":
        messages.success(request, "Artikel berhasil diterbitkan.")
    elif outcome == "pending":
        messages.success(request, "Perubahan disimpan. Artikel masih menunggu review.")
    else:
        messages.success(request, "Draf tersimpan.")
    return redirect(detail_url)


@login_required
def article_html_create(request):
    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                article = form.save(commit=False)
                article.author = request.user
                article.status = _chosen_status(request)
                outcome = _apply_status(request, article)
                article.save()
                form.save_m2m()
                _add_new_tags(article, form.cleaned_data["new_tags"])
            return _after_save(request, article, outcome)
    else:
        form = ArticleForm()

    return render(
        request,
        "articles/form.html",
        {"form": form, "article": None, "is_admin": is_admin(request.user)},
    )


@login_required
def article_html_update(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not can_edit(request.user, article):
        raise PermissionDenied
    old_image = article.image
    old_status = article.status

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            image_changed = "image" in form.changed_data and bool(old_image)
            with transaction.atomic():
                article = form.save(commit=False)
                article.status = _chosen_status(request, article)
                outcome = _apply_status(request, article, old_status)
                article.save()
                form.save_m2m()
                _add_new_tags(article, form.cleaned_data["new_tags"])

            if image_changed and (
                not article.image or old_image.name != article.image.name
            ):
                _delete_image(old_image)
            return _after_save(request, article, outcome)
    else:
        form = ArticleForm(instance=article)

    return render(
        request,
        "articles/form.html",
        {"form": form, "article": article, "is_admin": is_admin(request.user)},
    )


@login_required
@require_POST
def article_html_delete(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not can_edit(request.user, article):
        raise PermissionDenied
    image = article.image
    article.delete()
    _delete_image(image)
    messages.success(request, "Artikel berhasil dihapus.")
    if is_admin(request.user):
        return redirect(safe_next_url(request, reverse("articles:html-list")))
    return redirect("articles:mine")


@login_required
@_admin_required
@require_POST
def article_review(request, slug):
    """Approve (publish) or send back a submitted article, with a note."""
    article = get_object_or_404(Article.objects.select_related("author"), slug=slug)
    decision = request.POST.get("decision")
    note = request.POST.get("review_note", "").strip()[:1000]
    detail_url = reverse("articles:html-detail", args=(article.slug,))
    # Dari dashboard admin, kembali ke daftar yang sama
    back_url = safe_next_url(request, detail_url)
    if article.status != Status.PENDING:
        messages.warning(request, "Artikel ini tidak sedang menunggu review.")
        return redirect(back_url)
    if decision not in ("approve", "reject"):
        messages.error(request, "Pilih terbitkan atau kembalikan ke penulis.")
        return redirect(back_url)
    if decision == "reject" and not note:
        messages.error(request, "Tulis catatan agar penulis tahu apa yang diubah.")
        return redirect(back_url if back_url != detail_url else f"{detail_url}#review")

    now = timezone.now()
    article.reviewed_at = now
    article.reviewed_by = request.user
    article.review_note = note
    if decision == "approve":
        article.status = Status.PUBLISHED
        article.published_at = now
        notify(
            article.author,
            Kind.ARTICLE_APPROVED,
            "Artikelmu terbit!",
            f"“{article.title}” kini bisa dibaca semua orang.",
            url=detail_url,
            actor=request.user,
        )
        messages.success(request, "Artikel diterbitkan.")
    else:
        article.status = Status.REJECTED
        article.published_at = None
        notify(
            article.author,
            Kind.ARTICLE_REJECTED,
            "Artikelmu perlu sedikit perubahan",
            note,
            url=detail_url,
            actor=request.user,
        )
        messages.success(request, "Artikel dikembalikan ke penulis dengan catatan.")
    article.save()
    return redirect(back_url)


@login_required
def article_mine(request):
    """A writer's own articles with their review status."""
    status = request.GET.get("status", "")
    articles = (
        Article.objects.filter(author=request.user)
        .select_related("category", "reviewed_by")
        .annotate(reads_total=Count("reads", distinct=True))
        .order_by("-updated_at", "-id")
    )
    counts = dict(
        Article.objects.filter(author=request.user)
        .values_list("status")
        .annotate(total=Count("id"))
    )
    if status in Status.values:
        articles = articles.filter(status=status)
    else:
        status = ""
    page_obj = Paginator(articles, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "articles/mine.html",
        {
            "page_obj": page_obj,
            "articles": page_obj.object_list,
            "status": status,
            "all_label": f"Semua · {sum(counts.values())}",
            "status_options": [
                {
                    "key": key,
                    "label": f"{label} · {counts.get(key, 0)}",
                    "icon": icon,
                    "url": f"?status={key}",
                }
                for key, label, icon in (
                    (Status.DRAFT, "Draf", "file-pen"),
                    (Status.PENDING, "Menunggu review", "hourglass"),
                    (Status.REJECTED, "Perlu revisi", "message-square-warning"),
                    (Status.PUBLISHED, "Terbit", "globe"),
                )
            ],
            "reads_count": request.user.article_reads.count(),
        },
    )


@login_required
@_admin_required
def category_manage(request):
    """List, add, rename and delete article categories."""
    editing = None
    edit_id = request.GET.get("edit", "")
    if edit_id.isdigit():
        editing = ArticleCategory.objects.filter(pk=edit_id).first()
    form = CategoryForm(instance=editing)
    if request.method == "POST":
        action = request.POST.get("action", "create")
        if action == "delete":
            category = get_object_or_404(ArticleCategory, pk=request.POST.get("id"))
            try:
                category.delete()
                messages.success(request, f"Kategori “{category.name}” dihapus.")
            except ProtectedError:
                messages.error(
                    request,
                    f"“{category.name}” masih dipakai artikel, tidak bisa dihapus.",
                )
            return redirect("articles:categories")
        instance = None
        if action == "rename":
            instance = editing = get_object_or_404(
                ArticleCategory, pk=request.POST.get("id")
            )
        form = CategoryForm(request.POST, instance=instance)
        if form.is_valid():
            category = form.save()
            messages.success(
                request,
                f"Kategori “{category.name}” "
                + ("diperbarui." if instance else "ditambahkan."),
            )
            return redirect("articles:categories")

    categories = ArticleCategory.objects.annotate(
        total=Count("articles", distinct=True),
        published=Count(
            "articles",
            filter=Q(articles__status=Status.PUBLISHED),
            distinct=True,
        ),
    ).order_by("name")
    return render(
        request,
        "articles/categories.html",
        {"categories": categories, "form": form, "editing": editing},
    )


def _add_new_tags(article, names):
    for name in names:
        tag = Tag.objects.filter(name__iexact=name).first()
        if tag is None:
            tag = Tag.objects.create(name=name)
        article.tags.add(tag)


def _delete_image(image):
    if image:
        try:
            image.delete(save=False)
        except Exception:
            logger.exception("Failed to remove article image %s", image.name)
