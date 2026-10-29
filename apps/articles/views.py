import json
import logging
from functools import wraps
from pathlib import Path

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.http.multipartparser import MultiPartParser, MultiPartParserError
from django.utils import timezone
from django.views.csrf import csrf_failure as django_csrf_failure
from PIL import Image, UnidentifiedImageError

from apps.articles.models import Article, ArticleCategory, Tag
from apps.core.permissions import is_admin
from apps.core.utils import get_query_params

logger = logging.getLogger(__name__)


def _error_response(code, message, status, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JsonResponse({"error": error}, status=status)


def csrf_failure(request, reason=""):
    is_articles_api = request.path_info.startswith("/api/") or (
        request.path_info.startswith("/articles/")
        and request.path_info.endswith(("/create/", "/edit/", "/delete/"))
    )
    if is_articles_api:
        return _error_response(
            "PERMISSION_DENIED", "Permintaan gagal pemeriksaan CSRF.", 403
        )
    return django_csrf_failure(request, reason=reason)


def _json_api(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception:
            logger.exception(
                "Unhandled error in Articles API view %s", view_func.__name__
            )
            return _error_response(
                "INTERNAL_ERROR", "Terjadi kesalahan internal server.", 500
            )

    return wrapped


def _admin_json_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _error_response("AUTHENTICATION_REQUIRED", "Login diperlukan.", 401)
        if not is_admin(request.user):
            return _error_response(
                "PERMISSION_DENIED", "Hanya admin yang boleh mengelola konten.", 403
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def _method_not_allowed(allowed):
    response = _error_response(
        "METHOD_NOT_ALLOWED", "Metode HTTP tidak diizinkan.", 405
    )
    response["Allow"] = ", ".join(allowed)
    return response


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


def _request_article_payload(request):
    if request.content_type.startswith("multipart/form-data"):
        if request.method == "POST":
            form_data, files = request.POST, request.FILES
        else:
            try:
                form_data, files = MultiPartParser(
                    request.META, request, request.upload_handlers, request.encoding
                ).parse()
            except MultiPartParserError:
                return (
                    None,
                    None,
                    _error_response(
                        "INVALID_MULTIPART",
                        "Request body multipart tidak valid.",
                        400,
                    ),
                )
        data = form_data.dict()
        if "category_id" in data:
            try:
                data["category_id"] = int(data["category_id"])
            except ValueError:
                pass
        for field in ("tags", "new_tags"):
            if field in data:
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    return (
                        None,
                        None,
                        _error_response(
                            "VALIDATION_ERROR",
                            f"Field {field} harus berupa JSON array.",
                            400,
                            {field: ["Kirim array JSON yang valid."]},
                        ),
                    )
        return data, None, files
    data, error = _request_json_object(request)
    return data, error, request.FILES


def _validate_tag_inputs(data, article=None):
    tag_slugs = data.get("tags", [])
    new_tag_names = data.get("new_tags", [])

    for field, value in (("tags", tag_slugs), ("new_tags", new_tag_names)):
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            return (
                None,
                None,
                _error_response(
                    "VALIDATION_ERROR",
                    f"Field {field} harus berupa array string.",
                    400,
                    {field: ["Kirim array string yang valid."]},
                ),
            )

    tag_slugs = [value.strip() for value in tag_slugs]
    if any(not value for value in tag_slugs) or len(set(tag_slugs)) != len(tag_slugs):
        return (
            None,
            None,
            _error_response(
                "VALIDATION_ERROR",
                "Daftar tag berisi slug kosong atau duplikat.",
                400,
                {"tags": ["Gunakan slug unik yang tidak kosong."]},
            ),
        )

    existing_tags = list(Tag.objects.filter(slug__in=tag_slugs))
    found_slugs = {tag.slug for tag in existing_tags}
    unknown_slugs = sorted(set(tag_slugs) - found_slugs)
    if unknown_slugs:
        return (
            None,
            None,
            _error_response(
                "VALIDATION_ERROR",
                "Satu atau lebih tag tidak ditemukan.",
                400,
                {
                    "tags": [
                        f"Slug tag tidak dikenal: {slug}." for slug in unknown_slugs
                    ]
                },
            ),
        )

    new_tag_names = [name.strip() for name in new_tag_names]
    if any(not name or len(name) > 100 for name in new_tag_names):
        return (
            None,
            None,
            _error_response(
                "VALIDATION_ERROR",
                "Nama tag harus berisi 1 sampai 100 karakter.",
                400,
                {"new_tags": ["Nama tag tidak valid."]},
            ),
        )

    if len({name.casefold() for name in new_tag_names}) != len(new_tag_names):
        return (
            None,
            None,
            _error_response(
                "VALIDATION_ERROR",
                "Nama tag baru tidak boleh duplikat.",
                400,
                {"new_tags": ["Hapus nama tag duplikat."]},
            ),
        )

    if article is not None and "tags" not in data:
        existing_tags = list(article.tags.all())
    return existing_tags, new_tag_names, None


def _create_or_get_tags(names):
    tags = []
    for name in names:
        tag = Tag.objects.filter(name__iexact=name).first()
        if tag is None:
            tag = Tag.objects.create(name=name)
        if tag not in tags:
            tags.append(tag)
    return tags


def _validate_image_upload(upload):
    if upload is None:
        return None

    if upload.size > 5 * 1024 * 1024:
        return _error_response(
            "VALIDATION_ERROR",
            "Ukuran gambar maksimal 5 MB.",
            400,
            {"image": ["Ukuran file melebihi 5 MB."]},
        )

    extension = Path(upload.name).suffix.lower()
    allowed_extensions = {
        "JPEG": {".jpg", ".jpeg"},
        "PNG": {".png"},
        "WEBP": {".webp"},
        "GIF": {".gif"},
    }
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return _error_response(
            "VALIDATION_ERROR",
            "File yang diunggah bukan gambar yang valid.",
            400,
            {"image": ["Unggah JPEG, PNG, WEBP, atau GIF yang valid."]},
        )
    finally:
        upload.seek(0)

    if (
        image_format not in allowed_extensions
        or extension not in allowed_extensions[image_format]
        or width * height > 20_000_000
    ):
        return _error_response(
            "VALIDATION_ERROR",
            "Format atau dimensi gambar tidak diizinkan.",
            400,
            {"image": ["Gunakan JPEG, PNG, WEBP, atau GIF maksimal 20 megapiksel."]},
        )
    return None


def _image_url(request, article):
    return request.build_absolute_uri(article.image.url) if article.image else None


def _delete_stored_file(file_field):
    if not file_field:
        return
    try:
        file_field.delete(save=False)
    except Exception:
        logger.exception("Failed to remove article image %s", file_field.name)


def _serialize_tags(article):
    tags = sorted(article.tags.all(), key=lambda tag: (tag.name.casefold(), tag.pk))
    return [{"name": tag.name, "slug": tag.slug} for tag in tags]


@_json_api
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


@_json_api
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


@_json_api
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


@_json_api
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


@_json_api
def article_list(request):
    """Return a searchable and paginated article list."""
    if request.method != "GET":
        return _method_not_allowed(("GET",))

    query_params = get_query_params(request, ("search", "category", "tag", "status"))
    filters = query_params["filters"]
    pagination = query_params["pagination"]

    articles = Article.objects.select_related("category", "author").prefetch_related(
        "tags"
    )

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
            | Q(category__name__icontains=search)
        )

    category = filters.get("category")
    if category:
        articles = articles.filter(
            Q(category__slug__iexact=category) | Q(category__name__iexact=category)
        )

    tag_slug = filters.get("tag")
    if tag_slug:
        if not Tag.objects.filter(slug=tag_slug).exists():
            return _error_response(
                "INVALID_QUERY_PARAMETER",
                "Tag tidak ditemukan.",
                400,
                {"tag": [f"Slug tag tidak dikenal: {tag_slug}."]},
            )
        articles = articles.filter(tags__slug=tag_slug)

    articles = articles.order_by("-published_at", "-id")

    paginator = Paginator(articles, pagination["page_size"])
    page_obj = paginator.get_page(pagination["page"])

    results = [
        {
            "id": article.id,
            "title": article.title,
            "slug": article.slug,
            "summary": article.summary,
            "image": _image_url(request, article),
            "tags": _serialize_tags(article),
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


@_json_api
def article_detail(request, slug):
    """Return a published article, or a draft to an administrator."""
    if request.method != "GET":
        return _method_not_allowed(("GET",))

    articles = Article.objects.select_related("category", "author").prefetch_related(
        "tags"
    )

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
        "image": _image_url(request, article),
        "tags": _serialize_tags(article),
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


@_json_api
@_admin_json_required
def article_create(request):
    """Create a new article."""
    if request.method != "POST":
        return _method_not_allowed(("POST",))

    data, error, files = _request_article_payload(request)
    if error:
        return error
    if "image" in data:
        return _error_response(
            "VALIDATION_ERROR",
            "Gambar harus dikirim sebagai file multipart, bukan URL atau teks.",
            400,
            {"image": ["Gunakan upload file multipart/form-data."]},
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

    tags, new_tag_names, error = _validate_tag_inputs(data)
    if error:
        return error
    image_upload = files.get("image")
    error = _validate_image_upload(image_upload)
    if error:
        return error

    with transaction.atomic():
        article = Article.objects.create(
            title=title.strip(),
            content=content.strip(),
            image=image_upload,
            category=category,
            author=request.user,
            status=status,
            summary=summary,
            published_at=(
                timezone.now() if status == Article.Status.PUBLISHED else None
            ),
        )
        created_tags = _create_or_get_tags(new_tag_names)
        article.tags.set([*tags, *created_tags])

    return JsonResponse(
        {
            "message": "Artikel berhasil dibuat.",
            "article": {
                "id": article.id,
                "title": article.title,
                "slug": article.slug,
                "status": article.status,
                "image": _image_url(request, article),
                "tags": _serialize_tags(article),
            },
        },
        status=201,
    )


@_json_api
@_admin_json_required
def article_update(request, slug):
    """Placeholder for admin article editing and publication management."""
    if request.method not in ("PUT", "PATCH"):
        return _method_not_allowed(("PUT", "PATCH"))

    article = Article.objects.filter(slug=slug).first()
    if article is None:
        return _error_response("ARTICLE_NOT_FOUND", "Artikel tidak ditemukan.", 404)
    data, error, files = _request_article_payload(request)
    if error:
        return error
    if "image" in data:
        return _error_response(
            "VALIDATION_ERROR",
            "Gambar harus dikirim sebagai file multipart, bukan URL atau teks.",
            400,
            {"image": ["Gunakan upload file multipart/form-data."]},
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
        data.setdefault("tags", [])

    allowed_fields = {
        "title",
        "summary",
        "content",
        "category_id",
        "status",
        "tags",
        "new_tags",
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

    tags, new_tag_names, error = _validate_tag_inputs(data, article=article)
    if error:
        return error
    image_upload = files.get("image")
    error = _validate_image_upload(image_upload)
    if error:
        return error

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
        article.title = data["title"].strip()

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

    old_image = article.image
    if image_upload:
        article.image = image_upload

    with transaction.atomic():
        article.save()
        if "tags" in data or "new_tags" in data:
            created_tags = _create_or_get_tags(new_tag_names)
            article.tags.set([*tags, *created_tags])

    if image_upload and old_image and old_image.name != article.image.name:
        _delete_stored_file(old_image)

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
                "image": _image_url(request, article),
                "tags": _serialize_tags(article),
            },
        }
    )


@_json_api
@_admin_json_required
def article_delete(request, slug):
    """Delete an article by slug. Only administrators may call this endpoint."""
    if request.method != "DELETE":
        return _method_not_allowed(("DELETE",))

    article = Article.objects.filter(slug=slug).first()
    if article is None:
        return _error_response("ARTICLE_NOT_FOUND", "Artikel tidak ditemukan.", 404)

    image = article.image
    article.delete()
    _delete_stored_file(image)
    return HttpResponse(status=204)


@_json_api
def api_article_list(request):
    if request.method != "GET":
        return _method_not_allowed(("GET",))
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("category", "author")
        .prefetch_related("tags")
        .order_by("-published_at", "-id")
    )

    results = [
        {
            "title": article.title,
            "slug": article.slug,
            "summary": article.summary,
            "image": _image_url(request, article),
            "tags": _serialize_tags(article),
            "category": article.category.name,
            "author": article.author.username,
            "published_at": (
                article.published_at.isoformat() if article.published_at else None
            ),
        }
        for article in articles
    ]

    return JsonResponse({"results": results})
