import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

from apps.articles.models import Article, ArticleCategory
from apps.core.decorators import admin_required
from apps.core.utils import get_query_params


def article_list(request):
    """Placeholder for searching and filtering published educational articles."""
    query_params = get_query_params(request, ("search", "category", "status"))
    filters = query_params["filters"]
    pagination = query_params["pagination"]

    articles = Article.objects.select_related("category", "author")

    if request.user.is_authenticated and request.user.is_admin:
        status = filters.get("status", Article.Status.PUBLISHED)

        if status in (Article.Status.DRAFT, Article.Status.PUBLISHED):
            articles = articles.filter(status=status)
        else:
            return JsonResponse(
                {
                    "errors": {
                        "code": "INVALID_QUERY_PARAMETER",
                        "message": "Status artikel tidak valid",
                    }
                },
                status=400,
            )

    else:
        articles = articles.filter(status=Article.Status.PUBLISHED)
    search = filters.get("search")
    if search:
        articles = articles.filter(
            Q(title__icontains=search)
            | Q(summary__icontains=search)
            | Q(content__icontains=search)
        )

    category = filters.get("category")
    if category:
        articles = articles.filter(
            Q(category__slug__iexact=category) | Q(category__name__iexact=category)
        )

    articles = articles.order_by("-published_at", "-id")

    paginator = Paginator(articles, pagination["page_size"])
    page_obj = paginator.get_page(pagination["page"])

    results = [
        {
            "id": article.id,
            "title": article.title,
            "slug": article.slug,
            "summary": article.summary,
            "category": {
                "name": article.category.name,
                "slug": article.category.slug,
            },
            "author": {
                "id": article.author.id,
                "username": article.author.username,
            },
            "status": article.status,
            "published_at": (
                article.published_at.isoformat() if article.published_at else None
            ),
        }
        for article in page_obj
    ]

    return JsonResponse(
        {
            "results": results,
            "pagination": {
                "page": page_obj.number,
                "page_size": pagination["page_size"],
                "total_items": paginator.count,
                "total_pages": paginator.num_pages,
            },
        }
    )


def article_detail(request, slug):
    """Placeholder for displaying one educational article by slug."""
    articles = Article.objects.select_related("category", "author")

    if not (request.user.is_authenticated and request.user.is_admin):
        articles = articles.filter(status=Article.Status.PUBLISHED)

    article = get_object_or_404(articles, slug=slug)

    result = {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "content": article.content,
        "category": {
            "name": article.category.name,
            "slug": article.category.slug,
        },
        "author": {
            "id": article.author.id,
            "username": article.author.username,
        },
        "status": article.status,
        "published_at": (
            article.published_at.isoformat() if article.published_at else None
        ),
    }

    return JsonResponse(result)


@admin_required
def article_create(request):
    """Create a new article."""
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed."},
            status=405,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "error": {
                    "code": "INVALID_JSON",
                    "message": "Request body harus berupa JSON yang valid.",
                }
            },
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {
                "error": {
                    "code": "INVALID_JSON",
                    "message": "Request body harus berupa objek JSON.",
                }
            },
            status=400,
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Judul artikel wajib diisi.",
                    "details": {"title": ["Judul wajib diisi"]},
                }
            },
            status=400,
        )

    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Isi artikel wajib diisi",
                    "details": {"content": ["Isi artikel wajib diisi"]},
                }
            },
            status=400,
        )

    category_id = data.get("category_id")
    if not isinstance(category_id, int) or isinstance(category_id, bool):
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Kategori artikel wajib dipilih.",
                    "details": {
                        "category_id": ["ID kategori harus berupa bilangan bulat."]
                    },
                }
            },
            status=400,
        )

    category = ArticleCategory.objects.filter(id=category_id).first()
    if category is None:
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Kategori artikel tidak ditemukan.",
                    "details": {"category_id": ["Pilih kategori yang tersedia."]},
                }
            },
            status=400,
        )

    status = data.get("status", Article.Status.DRAFT)
    if status not in (
        Article.Status.DRAFT,
        Article.Status.PUBLISHED,
    ):
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Status artikel tidak valid.",
                    "details": {"status": ["Status harus DRAFT atau PUBLISHED."]},
                }
            },
            status=400,
        )

    summary = data.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Ringkasan artikel harus berupa teks.",
                    "details": {"summary": ["Ringkasan harus berupa teks."]},
                }
            },
            status=400,
        )

    summary = summary.strip()

    base_slug = slugify(title)
    slug = base_slug
    counter = 2

    while Article.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    article = Article.objects.create(
        title=title.strip(),
        content=content.strip(),
        category=category,
        author=request.user,
        status=status,
        summary=summary,
        slug=slug,
        published_at=(timezone.now() if status == Article.Status.PUBLISHED else None),
    )

    return JsonResponse(
        {
            "message": "Artikel berhasil dibuat.",
            "article": {
                "id": article.id,
                "title": article.title,
                "slug": article.slug,
                "status": article.status,
            },
        },
        status=201,
    )


@admin_required
def article_update(request, slug):
    """Placeholder for admin article editing and publication management."""
    return HttpResponse("Article update is not implemented yet.", status=501)


@admin_required
def article_delete(request, slug):
    """Placeholder for admin article deletion."""
    return HttpResponse("Article deletion is not implemented yet.", status=501)


def api_article_list(request):
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category", "author")
        .order_by("-published_at", "-id")
    )

    results = [
        {
            "title": article.title,
            "slug": article.slug,
            "summary": article.summary,
            "category": article.category.name,
            "author": article.author.username,
            "published_at": (
                article.published_at.isoformat() if article.published_at else None
            ),
        }
        for article in articles
    ]

    return JsonResponse({"results": results})
