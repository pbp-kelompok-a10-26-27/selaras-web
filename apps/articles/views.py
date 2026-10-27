from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from apps.articles.models import Article
from apps.core.decorators import admin_required, login_required
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


@login_required
def article_create(request):
    """Placeholder for authenticated article creation."""
    return HttpResponse("Article creation is not implemented yet.", status=501)


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
