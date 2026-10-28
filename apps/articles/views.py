import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify

from apps.articles.models import Article, ArticleCategory
from apps.core.decorators import admin_required
from apps.core.permissions import is_admin
from apps.core.utils import get_query_params


def _error_response(code, message, status, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JsonResponse({"error": error}, status=status)


def _method_not_allowed(allowed):
    response = _error_response(
        "METHOD_NOT_ALLOWED", "Metode HTTP tidak diizinkan.", 405
    )
    response["Allow"] = ", ".join(allowed)
    return response


def _unique_article_slug(title, current_article=None):
    base_slug = slugify(title) or "article"
    slug = base_slug
    counter = 2
    matches = Article.objects.all()
    if current_article is not None:
        matches = matches.exclude(pk=current_article.pk)
    while matches.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _unique_category_slug(name, current_category=None):
    base_slug = slugify(name) or "category"
    slug = base_slug
    counter = 2
    matches = ArticleCategory.objects.all()
    if current_category is not None:
        matches = matches.exclude(pk=current_category.pk)
    while matches.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _request_json_object(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error_response(
            "INVALID_JSON", "Request body harus berupa JSON yang valid.", 400
        )
    if not isinstance(data, dict):
        return None, _error_response(
            "INVALID_JSON", "Request body harus berupa objek JSON.", 400
        )
    return data, None


def article_api_collection(request):
    """Dispatch the collection API while keeping HTML routes separate."""
    if request.method == "GET":
        return article_list(request)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
        if not is_admin(request.user):
            return _error_response(
                "PERMISSION_DENIED", "Hanya admin yang boleh mengelola artikel.", 403
            )
        return article_create(request)
    return _method_not_allowed(("GET", "POST"))


def article_api_detail(request, slug):
    """Dispatch detail and mutation API methods with JSON access errors."""
    if request.method == "GET":
        return article_detail(request, slug)
    if request.method in ("PATCH", "PUT", "DELETE"):
        if not request.user.is_authenticated:
            return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
        if not is_admin(request.user):
            return _error_response(
                "PERMISSION_DENIED", "Hanya admin yang boleh mengelola artikel.", 403
            )
        if request.method == "DELETE":
            return article_delete(request, slug)
        return article_update(request, slug)
    return _method_not_allowed(("GET", "PATCH", "PUT", "DELETE"))


def category_api_collection(request):
    """List categories for authenticated readers and create them as admin."""
    if request.method == "GET":
        if not request.user.is_authenticated:
            return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
        categories = ArticleCategory.objects.order_by("name", "id")
        return JsonResponse(
            {
                "results": [
                    {"id": item.id, "name": item.name, "slug": item.slug}
                    for item in categories
                ]
            }
        )

    if request.method == "POST":
        if not request.user.is_authenticated:
            return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
        if not is_admin(request.user):
            return _error_response(
                "PERMISSION_DENIED", "Hanya admin yang boleh mengelola kategori.", 403
            )
        data, error = _request_json_object(request)
        if error:
            return error
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return _error_response(
                "VALIDATION_ERROR",
                "Nama kategori wajib diisi.",
                400,
                {"name": ["Nama kategori wajib diisi."]},
            )
        name = name.strip()
        if ArticleCategory.objects.filter(name__iexact=name).exists():
            return _error_response(
                "VALIDATION_ERROR",
                "Nama kategori sudah digunakan.",
                400,
                {"name": ["Nama kategori harus unik."]},
            )
        category = ArticleCategory.objects.create(
            name=name,
            slug=_unique_category_slug(name),
        )
        return JsonResponse(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
            },
            status=201,
        )

    return _method_not_allowed(("GET", "POST"))


def category_api_detail(request, slug):
    """Rename or delete a category, protecting categories used by articles."""
    if request.method not in ("PATCH", "DELETE"):
        return _method_not_allowed(("PATCH", "DELETE"))
    if not request.user.is_authenticated:
        return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
    if not is_admin(request.user):
        return _error_response(
            "PERMISSION_DENIED", "Hanya admin yang boleh mengelola kategori.", 403
        )

    category = ArticleCategory.objects.filter(slug=slug).first()
    if category is None:
        return _error_response("CATEGORY_NOT_FOUND", "Kategori tidak ditemukan.", 404)

    if request.method == "PATCH":
        data, error = _request_json_object(request)
        if error:
            return error
        invalid_fields = set(data) - {"name"}
        if invalid_fields:
            return _error_response(
                "VALIDATION_ERROR",
                "Hanya nama kategori yang dapat diubah.",
                400,
                {"fields": sorted(invalid_fields)},
            )
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return _error_response(
                "VALIDATION_ERROR",
                "Nama kategori wajib diisi.",
                400,
                {"name": ["Nama kategori wajib diisi."]},
            )
        name = name.strip()
        duplicate_name = ArticleCategory.objects.filter(name__iexact=name).exclude(
            pk=category.pk
        )
        if duplicate_name.exists():
            return _error_response(
                "VALIDATION_ERROR",
                "Nama kategori sudah digunakan.",
                400,
                {"name": ["Nama kategori harus unik."]},
            )
        if name != category.name:
            category.name = name
            category.slug = _unique_category_slug(name, current_category=category)
            category.save()
        return JsonResponse(
            {"id": category.id, "name": category.name, "slug": category.slug}
        )

    if category.articles.exists():
        return _error_response(
            "CATEGORY_IN_USE",
            "Kategori tidak dapat dihapus karena masih digunakan oleh artikel.",
            409,
        )
    try:
        category.delete()
    except ProtectedError:
        return _error_response(
            "CATEGORY_IN_USE",
            "Kategori tidak dapat dihapus karena masih digunakan oleh artikel.",
            409,
        )
    return HttpResponse(status=204)


def article_list(request):
    """Return a searchable and paginated article list."""
    if request.method != "GET":
        return _method_not_allowed(("GET",))

    query_params = get_query_params(request, ("search", "category", "status"))
    filters = query_params["filters"]
    pagination = query_params["pagination"]

    articles = Article.objects.select_related("category", "author")

    if request.user.is_authenticated and request.user.is_admin:
        status = filters.get("status", Article.Status.PUBLISHED)

        if status in (Article.Status.DRAFT, Article.Status.PUBLISHED):
            articles = articles.filter(status=status)
        else:
            return _error_response(
                "INVALID_QUERY_PARAMETER",
                "Status artikel tidak valid.",
                400,
                {"status": ["Status harus DRAFT atau PUBLISHED."]},
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
    """Return a published article, or a draft to an administrator."""
    if request.method != "GET":
        return _method_not_allowed(("GET",))

    articles = Article.objects.select_related("category", "author")

    if not (request.user.is_authenticated and request.user.is_admin):
        articles = articles.filter(status=Article.Status.PUBLISHED)

    article = articles.filter(slug=slug).first()
    if article is None:
        return _error_response("ARTICLE_NOT_FOUND", "Artikel tidak ditemukan.", 404)

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
        return _method_not_allowed(("POST",))

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

    slug = _unique_article_slug(title)

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
    if request.method not in ("PUT", "PATCH"):
        return _method_not_allowed(("PUT", "PATCH"))

    article = Article.objects.filter(slug=slug).first()
    if article is None:
        return _error_response("ARTICLE_NOT_FOUND", "Artikel tidak ditemukan.", 404)
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

    if request.method == "PUT":
        required_fields = {"title", "content", "category_id", "status"}
        missing_fields = sorted(required_fields - set(data))
        if missing_fields:
            return _error_response(
                "VALIDATION_ERROR",
                "Field wajib untuk pembaruan penuh belum dikirim.",
                400,
                {field: ["Field ini wajib diisi."] for field in missing_fields},
            )
        data.setdefault("summary", "")

    allowed_fields = {
        "title",
        "summary",
        "content",
        "category_id",
        "status",
    }

    invalid_fields = set(data.keys()) - allowed_fields
    if invalid_fields:
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Ada field yang tidak boleh diubah.",
                    "details": {
                        "fields": sorted(invalid_fields),
                    },
                }
            },
            status=400,
        )

    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return JsonResponse(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Judul artikel wajib diisi.",
                        "details": {"title": ["Judul wajib diisi."]},
                    }
                },
                status=400,
            )

    if "content" in data:
        if not isinstance(data["content"], str) or not data["content"].strip():
            return JsonResponse(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Isi artikel wajib diisi.",
                        "details": {"content": ["Isi artikel wajib diisi."]},
                    }
                },
                status=400,
            )

    if "summary" in data and data["summary"] is not None:
        if not isinstance(data["summary"], str):
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

    if "category_id" in data:
        category_id = data["category_id"]
        if not isinstance(category_id, int) or isinstance(category_id, bool):
            return JsonResponse(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "ID kategori harus berupa bilangan bulat.",
                        "details": {"category_id": ["Pilih kategori yang tersedia."]},
                    }
                },
                status=400,
            )

        if not ArticleCategory.objects.filter(id=category_id).exists():
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

    if "status" in data:
        if data["status"] not in (
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

    if "title" in data:
        new_title = data["title"].strip()
        if new_title != article.title:
            article.slug = _unique_article_slug(new_title, current_article=article)
        article.title = new_title

    if "summary" in data:
        article.summary = (data["summary"] or "").strip()

    if "content" in data:
        article.content = data["content"].strip()

    if "category_id" in data:
        article.category = ArticleCategory.objects.get(id=data["category_id"])

    old_status = article.status
    if "status" in data:
        article.status = data["status"]

    if article.status == Article.Status.PUBLISHED:
        if old_status != Article.Status.PUBLISHED or article.published_at is None:
            article.published_at = timezone.now()
    else:
        article.published_at = None

    article.save()

    return JsonResponse(
        {
            "message": "Artikel berhasil diperbarui.",
            "article": {
                "id": article.id,
                "title": article.title,
                "slug": article.slug,
                "status": article.status,
                "published_at": (
                    article.published_at.isoformat() if article.published_at else None
                ),
            },
        }
    )


@admin_required
def article_delete(request, slug):
    """Delete an article by slug. Only administrators may call this endpoint."""
    if request.method != "DELETE":
        return _method_not_allowed(("DELETE",))

    article = Article.objects.filter(slug=slug).first()
    if article is None:
        return _error_response("ARTICLE_NOT_FOUND", "Artikel tidak ditemukan.", 404)

    article.delete()
    return HttpResponse(status=204)


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
