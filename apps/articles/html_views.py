import logging
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permissions import is_admin
from apps.core.utils import get_query_params

from .forms import ArticleForm
from .models import Article, ArticleCategory, Tag

logger = logging.getLogger(__name__)

_FILTER_KEYS = ("search", "category", "tag", "status", "page_size")


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


def _visible_articles(request, status):
    articles = Article.objects.select_related("category", "author").prefetch_related(
        "tags"
    )
    if not is_admin(request.user):
        return articles.filter(status=Article.Status.PUBLISHED)
    return articles.filter(status=status)


def article_html_list(request):
    query_params = get_query_params(request, ("search", "category", "tag", "status"))
    filters = query_params["filters"]
    pagination = query_params["pagination"]
    admin = is_admin(request.user)

    status = Article.Status.PUBLISHED
    filter_error = ""
    if admin:
        status = filters.get("status", Article.Status.PUBLISHED)
        if status not in (Article.Status.DRAFT, Article.Status.PUBLISHED):
            filter_error = "Status artikel harus DRAFT atau PUBLISHED."
            status = Article.Status.PUBLISHED

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

    articles = articles.order_by("-published_at", "-id")
    paginator = Paginator(articles, pagination["page_size"])
    page_obj = paginator.get_page(pagination["page"])

    page_links = []
    if paginator.num_pages > 1:
        start = max(page_obj.number - 2, 1)
        end = min(start + 4, paginator.num_pages)
        start = max(end - 4, 1)
        page_links = [
            {
                "number": page_number,
                "url": _list_url(request, page=page_number),
                "current": page_number == page_obj.number,
            }
            for page_number in range(start, end + 1)
        ]

    context = {
        "articles": page_obj.object_list,
        "page_obj": page_obj,
        "pagination": pagination,
        "page_links": page_links,
        "previous_page_url": (
            _list_url(request, page=page_obj.previous_page_number())
            if page_obj.has_previous()
            else None
        ),
        "next_page_url": (
            _list_url(request, page=page_obj.next_page_number())
            if page_obj.has_next()
            else None
        ),
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
        "is_admin": admin,
        "article_create_url": reverse("articles:html-create"),
    }
    response_status = 400 if filter_error else 200
    return render(request, "articles/list.html", context, status=response_status)


def article_html_detail(request, slug):
    articles = Article.objects.select_related("category", "author").prefetch_related(
        "tags"
    )
    if not is_admin(request.user):
        articles = articles.filter(status=Article.Status.PUBLISHED)
    article = get_object_or_404(articles, slug=slug)
    return render(
        request,
        "articles/detail.html",
        {"article": article, "is_admin": is_admin(request.user)},
    )


@login_required
@_admin_required
def article_html_create(request):
    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                article = form.save(commit=False)
                article.author = request.user
                article.published_at = (
                    timezone.now()
                    if article.status == Article.Status.PUBLISHED
                    else None
                )
                article.save()
                form.save_m2m()
                _add_new_tags(article, form.cleaned_data["new_tags"])
            messages.success(request, "Artikel berhasil dibuat.")
            return redirect("articles:html-detail", slug=article.slug)
    else:
        form = ArticleForm()

    return render(request, "articles/form.html", {"form": form, "article": None})


@login_required
@_admin_required
def article_html_update(request, slug):
    article = get_object_or_404(Article, slug=slug)
    old_image = article.image
    old_status = article.status

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            image_changed = "image" in form.changed_data and bool(old_image)
            with transaction.atomic():
                article = form.save(commit=False)
                if article.status == Article.Status.PUBLISHED:
                    if (
                        old_status != Article.Status.PUBLISHED
                        or not article.published_at
                    ):
                        article.published_at = timezone.now()
                else:
                    article.published_at = None
                article.save()
                form.save_m2m()
                _add_new_tags(article, form.cleaned_data["new_tags"])

            if image_changed and (
                not article.image or old_image.name != article.image.name
            ):
                _delete_image(old_image)
            messages.success(request, "Artikel berhasil diperbarui.")
            return redirect("articles:html-detail", slug=article.slug)
    else:
        form = ArticleForm(instance=article)

    return render(request, "articles/form.html", {"form": form, "article": article})


@login_required
@_admin_required
@require_POST
def article_html_delete(request, slug):
    article = get_object_or_404(Article, slug=slug)
    image = article.image
    article.delete()
    _delete_image(image)
    messages.success(request, "Artikel berhasil dihapus.")
    return redirect("articles:html-list")


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
