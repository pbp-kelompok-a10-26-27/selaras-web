import json
import logging
import uuid
from functools import wraps
from json import JSONDecodeError

from django.core.cache import cache
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadedfile import UploadedFile
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.http.multipartparser import MultiPartParser, MultiPartParserError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.challenges.models import Challenge, ChallengeParticipation
from apps.core.permissions import is_admin, is_user

from .forms import MAX_IMAGE_SIZE, FeedCommentForm, FeedPostForm
from .models import Comment, Like, Post

logger = logging.getLogger(__name__)
ALLOWED_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
)


def _is_htmx(request):
    return request.headers.get("HX-Request", "").lower() == "true"


def _error(request, status, code, message, details=None):
    if _is_htmx(request):
        response = render(
            request,
            "feeds/partials/error.html",
            {"code": code, "message": message, "details": details or []},
            status=status,
        )
    else:
        payload = {"error": {"code": code, "message": message}}
        if details is not None:
            payload["error"]["details"] = details
        response = JsonResponse(payload, status=status)
    if status == 401 and _is_htmx(request):
        response["HX-Redirect"] = reverse("accounts:login")
    return response


def _ok(request, payload, status=200, template=None, context=None, headers=None):
    if _is_htmx(request) and template:
        response = HttpResponse(
            render_to_string(template, context or {}, request=request), status=status
        )
    else:
        response = JsonResponse(payload, status=status)
    for key, value in (headers or {}).items():
        response[key] = value
    return response


def _delete_response(request):
    if _is_htmx(request):
        return HttpResponse(status=200)
    return HttpResponse(status=204)


def _api_endpoint(methods, roles=("user", "admin")):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return _error(
                    request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan."
                )
            role = "admin" if is_admin(request.user) else request.user.role
            if role not in roles:
                return _error(request, 403, "FORBIDDEN_ROLE", "Peran tidak diizinkan.")
            if request.method not in methods:
                response = _error(
                    request, 405, "METHOD_NOT_ALLOWED", "Metode tidak diizinkan."
                )
                response["Allow"] = ", ".join(methods)
                return response
            try:
                return view(request, *args, **kwargs)
            except Http404:
                code = (
                    "COMMENT_NOT_FOUND"
                    if request.resolver_match
                    and request.resolver_match.url_name
                    in (
                        "reply-create",
                        "comment-update",
                        "comment-delete",
                        "admin-comment-delete",
                    )
                    else "POST_NOT_FOUND"
                )
                return _error(
                    request,
                    404,
                    code,
                    "Komentar tidak ditemukan."
                    if code == "COMMENT_NOT_FOUND"
                    else "Postingan tidak ditemukan.",
                )
            except Exception:
                request_id = uuid.uuid4().hex
                logger.exception("Feed request failed (request_id=%s)", request_id)
                response = _error(
                    request,
                    500,
                    "INTERNAL_ERROR",
                    "Terjadi kesalahan internal.",
                )
                response["X-Request-ID"] = request_id
                return response

        return wrapped

    return decorate


def _parse_body(request):
    content_type = request.content_type or ""
    if content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
        except (JSONDecodeError, UnicodeDecodeError):
            return None, None, "malformed"
        if not isinstance(data, dict):
            return None, None, "malformed"
        return data, {}, None
    if content_type == "multipart/form-data":
        try:
            if request.method == "POST":
                return request.POST, request.FILES, None
            parser = MultiPartParser(
                request.META, request, request.upload_handlers, request.encoding
            )
            data, files = parser.parse()
            return data, files, None
        except (MultiPartParserError, ValueError):
            return None, None, "malformed"
        except RequestDataTooBig:
            return None, None, "too_large"
    if not content_type:
        return {}, {}, None
    return None, None, "unsupported"


def _validation_error(request, field, message):
    return _error(
        request,
        422,
        "VALIDATION_ERROR",
        "Data yang dikirim tidak valid.",
        [{"field": field, "message": message}],
    )


def _positive_integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdecimal():
        parsed = int(value.strip())
    else:
        return None
    return parsed if parsed > 0 else None


def _pagination(request):
    values = {}
    for name, default, minimum, maximum in (
        ("page", 1, 1, None),
        ("per_page", 10, 1, 50),
    ):
        raw = request.GET.get(name, str(default))
        value = _positive_integer(raw)
        if (
            value is None
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            return None, _validation_error(request, name, f"Nilai {name} tidak valid.")
        values[name] = value
    return values, None


def _post_queryset(user):
    liked = Like.objects.filter(post_id=OuterRef("pk"), user=user)
    return (
        Post.objects.select_related("author", "challenge")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=Exists(liked),
        )
        .order_by("-created_at", "-id")
    )


def _author_data(user):
    return {
        "id": str(user.pk),
        "name": user.get_full_name().strip() or user.get_username(),
    }


def _post_data(request, post):
    image_url = request.build_absolute_uri(post.image.url) if post.image else None
    return {
        "id": post.pk,
        "content": post.content,
        "image_url": image_url,
        "author": _author_data(post.author),
        "challenge": (
            {"id": post.challenge_id, "title": post.challenge.title}
            if post.challenge_id
            else None
        ),
        "like_count": (
            post.like_count if hasattr(post, "like_count") else post.likes.count()
        ),
        "comment_count": (
            post.comment_count
            if hasattr(post, "comment_count")
            else post.comments.count()
        ),
        "liked_by_me": bool(getattr(post, "liked_by_me", False)),
        "is_owner": post.author_id == request.user.pk,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
    }


def _comment_data(request, comment, include_replies=True):
    data = {
        "id": comment.pk,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "author": _author_data(comment.author),
        "is_owner": comment.author_id == request.user.pk,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
    }
    if include_replies:
        data["replies"] = [
            _comment_data(request, reply, include_replies=False)
            for reply in comment.replies.all()
        ]
    return data


def _comment_json_data(comment):
    return {
        "id": comment.pk,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "author": _author_data(comment.author),
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
    }


@require_http_methods(["GET"])
def get_comment_json(request):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    comments = Comment.objects.select_related("author").order_by("created_at", "id")
    return JsonResponse({"data": [_comment_json_data(comment) for comment in comments]})


def _paged_response(request, items, page, per_page, total, key="data"):
    return {
        key: items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total_items": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


def _throttle(request):
    key = f"feed-write:{request.user.pk}"
    if cache.add(key, 1, timeout=60):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=60)
            count = 1
    if count <= 60:
        return None
    response = _error(request, 429, "TOO_MANY_REQUESTS", "Batas permintaan terlampaui.")
    response["Retry-After"] = "60"
    return response


def _image_extension(upload):
    upload.seek(0)
    signature = upload.read(12)
    upload.seek(0)
    for prefix, extension in ALLOWED_IMAGE_SIGNATURES:
        if signature.startswith(prefix):
            return extension
    if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return ".webp"
    return None


def _validate_image(request, upload):
    if upload is None:
        return None
    if not isinstance(upload, UploadedFile):
        return _validation_error(request, "image", "File foto tidak valid.")
    if upload.size > MAX_IMAGE_SIZE:
        return _error(request, 413, "PAYLOAD_TOO_LARGE", "Ukuran foto maksimal 10 MB.")
    extension = _image_extension(upload)
    if extension is None:
        return _error(
            request,
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Foto harus berformat JPEG, PNG, atau WebP.",
        )
    upload.name = f"{uuid.uuid4().hex}{extension}"
    return None


def _delete_stored_file(storage, path):
    try:
        storage.delete(path)
    except OSError:
        logger.warning("Unable to delete feed image %s", path, exc_info=True)


@_api_endpoint(("POST",), roles=("user", "admin"))
def api_post_create(request):
    if request.content_type != "multipart/form-data":
        return _error(
            request, 415, "UNSUPPORTED_MEDIA_TYPE", "Gunakan multipart/form-data."
        )
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    data, files, error = _parse_body(request)
    if error:
        if error == "too_large":
            return _error(
                request,
                413,
                "PAYLOAD_TOO_LARGE",
                "Ukuran request terlalu besar.",
            )
        return _error(
            request,
            400 if error == "malformed" else 415,
            "MALFORMED_REQUEST" if error == "malformed" else "UNSUPPORTED_MEDIA_TYPE",
            "Body request tidak dapat diproses.",
        )
    content = data.get("content", "")
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000:
        return _validation_error(
            request, "content", "Isi postingan wajib diisi (1-2000 karakter)."
        )
    raw_challenge_id = data.get("challenge_id")
    challenge = None
    if raw_challenge_id not in (None, ""):
        challenge_id = _positive_integer(raw_challenge_id)
        if challenge_id is None:
            return _validation_error(
                request, "challenge_id", "Challenge harus berupa integer positif."
            )
        challenge = Challenge.objects.filter(pk=challenge_id).first()
        if challenge is None:
            return _error(
                request, 404, "CHALLENGE_NOT_FOUND", "Challenge tidak ditemukan."
            )
        if not ChallengeParticipation.objects.filter(
            challenge=challenge, user=request.user
        ).exists():
            return _error(
                request,
                403,
                "NOT_CHALLENGE_PARTICIPANT",
                "Anda belum mengikuti challenge ini.",
            )
    upload = files.get("image")
    image_error = _validate_image(request, upload)
    if image_error:
        return image_error
    post = Post(
        author=request.user,
        challenge=challenge,
        content=content.strip(),
    )
    if upload:
        storage = post.image.storage
        try:
            with transaction.atomic():
                post.image.save(upload.name, upload, save=False)
                post.save()
        except Exception:
            if post.image.name:
                _delete_stored_file(storage, post.image.name)
            raise
    else:
        post.save()
    post = _post_queryset(request.user).get(pk=post.pk)
    return _ok(
        request,
        {"data": _post_data(request, post)},
        status=201,
        template="feeds/partials/post_card.html",
        context={"post": post, "post_data": _post_data(request, post)},
        headers={"Location": f"/api/v1/posts/{post.pk}"},
    )


@_api_endpoint(("GET",), roles=("user", "admin"))
def api_post_list(request):
    pagination, error = _pagination(request)
    if error:
        return error
    mine = request.GET.get("mine")
    if mine not in (None, "true", "false"):
        return _validation_error(request, "mine", "Nilai mine harus true atau false.")
    queryset = _post_queryset(request.user)
    challenge_id = request.GET.get("challenge_id")
    if challenge_id is not None:
        parsed_id = _positive_integer(challenge_id)
        if parsed_id is None:
            return _validation_error(
                request, "challenge_id", "Challenge harus berupa integer positif."
            )
        queryset = queryset.filter(challenge_id=parsed_id)
    if mine == "true":
        queryset = queryset.filter(author=request.user)
    total = queryset.count()
    offset = (pagination["page"] - 1) * pagination["per_page"]
    page_items = queryset[offset : offset + pagination["per_page"]]
    items = [_post_data(request, post) for post in page_items]
    return _ok(
        request,
        _paged_response(
            request,
            items,
            pagination["page"],
            pagination["per_page"],
            total,
        ),
        template="feeds/partials/post_list.html",
        context={"posts": page_items},
    )


@_api_endpoint(("GET",))
def api_post_detail(request, post_id):
    post = get_object_or_404(_post_queryset(request.user), pk=post_id)
    return _ok(
        request,
        {"data": _post_data(request, post)},
        template="feeds/partials/post_card.html",
        context={"post": post},
    )


@_api_endpoint(("PATCH",), roles=("user", "admin"))
def api_post_update(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("author", "challenge"), pk=post_id
    )
    if post.author_id != request.user.pk:
        return _error(request, 403, "NOT_OWNER", "Postingan bukan milik Anda.")
    if request.content_type != "multipart/form-data":
        return _error(
            request, 415, "UNSUPPORTED_MEDIA_TYPE", "Gunakan multipart/form-data."
        )
    data, files, error = _parse_body(request)
    if error:
        if error == "too_large":
            return _error(
                request,
                413,
                "PAYLOAD_TOO_LARGE",
                "Ukuran request terlalu besar.",
            )
        return _error(
            request,
            400 if error == "malformed" else 415,
            "MALFORMED_REQUEST" if error == "malformed" else "UNSUPPORTED_MEDIA_TYPE",
            "Body request tidak dapat diproses.",
        )
    content = data.get("content")
    if content is not None and (
        not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000
    ):
        return _validation_error(
            request, "content", "Isi postingan wajib diisi (1-2000 karakter)."
        )
    remove_image = data.get("remove_image", "false")
    if remove_image not in (True, False, "true", "false", "1", "0"):
        return _validation_error(request, "remove_image", "Nilai remove_image invalid.")
    remove_image = remove_image in (True, "true", "1")
    upload = files.get("image")
    if upload and remove_image:
        return _validation_error(
            request, "image", "Foto tidak dapat diganti dan dihapus sekaligus."
        )
    if content is None and not upload and not remove_image:
        return _validation_error(
            request, "content", "Minimal satu field yang dapat diubah diperlukan."
        )
    image_error = _validate_image(request, upload)
    if image_error:
        return image_error
    old_name = post.image.name if post.image else None
    old_storage = post.image.storage
    content_changed = content is not None and post.content != content.strip()
    image_changed = bool(upload) or (remove_image and bool(old_name))
    if not content_changed and not image_changed:
        post = _post_queryset(request.user).get(pk=post.pk)
        return _ok(
            request,
            {"data": _post_data(request, post)},
            template="feeds/partials/post_card.html",
            context={"post": post, "post_data": _post_data(request, post)},
        )
    new_name = None
    try:
        with transaction.atomic():
            update_fields = ["updated_at"]
            if content_changed:
                post.content = content.strip()
                update_fields.append("content")
            if upload:
                post.image.save(upload.name, upload, save=False)
                new_name = post.image.name
                update_fields.append("image")
            elif image_changed:
                post.image = ""
                update_fields.append("image")
            post.save(update_fields=update_fields)
            if old_name and image_changed:
                transaction.on_commit(
                    lambda: _delete_stored_file(old_storage, old_name)
                )
    except Exception:
        if new_name:
            _delete_stored_file(post.image.storage, new_name)
        raise
    post = _post_queryset(request.user).get(pk=post.pk)
    return _ok(
        request,
        {"data": _post_data(request, post)},
        template="feeds/partials/post_card.html",
        context={"post": post, "post_data": _post_data(request, post)},
    )


def _delete_post(post):
    image_name = post.image.name if post.image else None
    storage = post.image.storage
    with transaction.atomic():
        post.delete()
        if image_name:
            transaction.on_commit(lambda: _delete_stored_file(storage, image_name))


@_api_endpoint(("DELETE",), roles=("user", "admin"))
def api_post_delete(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    if not is_admin(request.user) and post.author_id != request.user.pk:
        return _error(request, 403, "NOT_OWNER", "Postingan bukan milik Anda.")
    _delete_post(post)
    return _delete_response(request)


@_api_endpoint(("GET",), roles=("admin",))
def api_admin_post_list(request):
    pagination, error = _pagination(request)
    if error:
        return error
    query = request.GET.get("q", "").strip()
    if len(query) > 100:
        return _validation_error(request, "q", "Pencarian maksimal 100 karakter.")
    queryset = _post_queryset(request.user)
    if query:
        queryset = queryset.filter(
            Q(content__icontains=query)
            | Q(author__username__icontains=query)
            | Q(author__first_name__icontains=query)
            | Q(author__last_name__icontains=query)
        )
    challenge_id = request.GET.get("challenge_id")
    if challenge_id is not None:
        parsed_id = _positive_integer(challenge_id)
        if parsed_id is None:
            return _validation_error(
                request, "challenge_id", "Challenge harus berupa integer positif."
            )
        queryset = queryset.filter(challenge_id=parsed_id)
    total = queryset.count()
    offset = (pagination["page"] - 1) * pagination["per_page"]
    page_items = queryset[offset : offset + pagination["per_page"]]
    items = [_post_data(request, post) for post in page_items]
    return _ok(
        request,
        _paged_response(
            request,
            items,
            pagination["page"],
            pagination["per_page"],
            total,
        ),
        template="feeds/partials/post_list.html",
        context={"posts": page_items},
    )


@_api_endpoint(("DELETE",), roles=("admin",))
def api_admin_post_delete(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    _delete_post(post)
    return _delete_response(request)


@_api_endpoint(("GET",))
def api_comment_list(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    pagination, error = _pagination(request)
    if error:
        return error
    replies = Comment.objects.select_related("author").order_by("created_at", "id")
    queryset = (
        Comment.objects.filter(post=post, parent__isnull=True)
        .select_related("author")
        .prefetch_related(Prefetch("replies", queryset=replies))
        .order_by("created_at", "id")
    )
    total = queryset.count()
    offset = (pagination["page"] - 1) * pagination["per_page"]
    page_items = queryset[offset : offset + pagination["per_page"]]
    items = [_comment_data(request, comment) for comment in page_items]
    return _ok(
        request,
        _paged_response(
            request,
            items,
            pagination["page"],
            pagination["per_page"],
            total,
        ),
        template="feeds/partials/comment_list.html",
        context={"comments": page_items},
    )


def api_posts_collection(request):
    if request.method == "POST":
        return api_post_create(request)
    return api_post_list(request)


def api_post_resource(request, post_id):
    if request.method == "PATCH":
        return api_post_update(request, post_id)
    if request.method == "DELETE":
        return api_post_delete(request, post_id)
    return api_post_detail(request, post_id)


def api_comment_collection(request, post_id):
    if request.method == "POST":
        return api_comment_create(request, post_id)
    return api_comment_list(request, post_id)


def api_comment_resource(request, comment_id):
    if request.method == "DELETE":
        return api_comment_delete(request, comment_id)
    return api_comment_update(request, comment_id)


@_api_endpoint(("POST",), roles=("user", "admin"))
def api_comment_create(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    if request.content_type not in (None, "", "application/json"):
        return _error(
            request, 415, "UNSUPPORTED_MEDIA_TYPE", "Gunakan application/json."
        )
    data, _, error = _parse_body(request)
    if error:
        return _error(
            request,
            400 if error == "malformed" else 415,
            "MALFORMED_REQUEST" if error == "malformed" else "UNSUPPORTED_MEDIA_TYPE",
            "Body request tidak dapat diproses.",
        )
    content = data.get("content")
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 500:
        return _validation_error(
            request, "content", "Isi komentar wajib diisi (1-500 karakter)."
        )
    comment = Comment.objects.create(
        post=post, author=request.user, content=content.strip()
    )
    return _ok(
        request,
        {"data": _comment_data(request, comment, include_replies=False)},
        status=201,
        template="feeds/partials/comment_item.html",
        context={"comment": comment},
    )


@_api_endpoint(("POST",), roles=("user", "admin"))
def api_reply_create(request, comment_id):
    parent = get_object_or_404(
        Comment.objects.select_related("post", "author"), pk=comment_id
    )
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    if request.content_type not in (None, "", "application/json"):
        return _error(
            request, 415, "UNSUPPORTED_MEDIA_TYPE", "Gunakan application/json."
        )
    data, _, error = _parse_body(request)
    if error:
        return _error(
            request,
            400 if error == "malformed" else 415,
            "MALFORMED_REQUEST" if error == "malformed" else "UNSUPPORTED_MEDIA_TYPE",
            "Body request tidak dapat diproses.",
        )
    content = data.get("content")
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 500:
        return _validation_error(
            request, "content", "Isi komentar wajib diisi (1-500 karakter)."
        )
    if parent.parent_id is not None:
        return _error(
            request,
            422,
            "REPLY_DEPTH_EXCEEDED",
            "Balasan hanya dapat dibuat pada komentar utama.",
        )
    with transaction.atomic():
        locked_parent = get_object_or_404(
            Comment.objects.select_for_update(), pk=comment_id
        )
        if locked_parent.parent_id is not None:
            return _error(
                request,
                422,
                "REPLY_DEPTH_EXCEEDED",
                "Balasan hanya dapat dibuat pada komentar utama.",
            )
        reply = Comment.objects.create(
            post_id=locked_parent.post_id,
            parent=locked_parent,
            author=request.user,
            content=content.strip(),
        )
    return _ok(
        request,
        {"data": _comment_data(request, reply, include_replies=False)},
        status=201,
        template="feeds/partials/comment_item.html",
        context={"comment": reply},
    )


@_api_endpoint(("PATCH",), roles=("user", "admin"))
def api_comment_update(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("author"), pk=comment_id)
    if comment.author_id != request.user.pk:
        return _error(request, 403, "NOT_OWNER", "Komentar bukan milik Anda.")
    if request.content_type not in (None, "", "application/json"):
        return _error(
            request, 415, "UNSUPPORTED_MEDIA_TYPE", "Gunakan application/json."
        )
    data, _, error = _parse_body(request)
    if error:
        return _error(
            request,
            400 if error == "malformed" else 415,
            "MALFORMED_REQUEST" if error == "malformed" else "UNSUPPORTED_MEDIA_TYPE",
            "Body request tidak dapat diproses.",
        )
    content = data.get("content")
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 500:
        return _validation_error(
            request, "content", "Isi komentar wajib diisi (1-500 karakter)."
        )
    if comment.content == content.strip():
        return _ok(
            request,
            {"data": _comment_data(request, comment, include_replies=False)},
            template="feeds/partials/comment_item.html",
            context={"comment": comment},
        )
    comment.content = content.strip()
    comment.save(update_fields=("content", "updated_at"))
    return _ok(
        request,
        {"data": _comment_data(request, comment, include_replies=False)},
        template="feeds/partials/comment_item.html",
        context={"comment": comment},
    )


def _delete_comment(comment):
    with transaction.atomic():
        comment.delete()


@_api_endpoint(("DELETE",), roles=("user", "admin"))
def api_comment_delete(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("author"), pk=comment_id)
    if not is_admin(request.user) and comment.author_id != request.user.pk:
        return _error(request, 403, "NOT_OWNER", "Komentar bukan milik Anda.")
    _delete_comment(comment)
    return _delete_response(request)


@_api_endpoint(("DELETE",), roles=("admin",))
def api_admin_comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    _delete_comment(comment)
    return _delete_response(request)


@_api_endpoint(("POST", "DELETE"), roles=("user", "admin"))
def api_toggle_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    if request.method == "POST":
        try:
            _, created = Like.objects.get_or_create(post=post, user=request.user)
        except IntegrityError:
            created = False
        liked = True
    else:
        Like.objects.filter(post=post, user=request.user).delete()
        created = False
        liked = False
    like_count = Like.objects.filter(post=post).count()
    payload = {"data": {"post_id": post.pk, "liked": liked, "like_count": like_count}}
    return _ok(
        request,
        payload,
        status=201 if request.method == "POST" and created else 200,
        template="feeds/partials/like_button.html",
        context={
            "post": post,
            "liked": liked,
            "like_count": like_count,
        },
    )


@require_http_methods(["GET"])
def post_list(request):
    if request.path.startswith("/api/"):
        return api_post_list(request)
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    queryset = _post_queryset(request.user)
    page = request.GET.get("page", "1")
    try:
        page_number = max(int(page), 1)
    except ValueError:
        page_number = 1
    posts = Paginator(queryset, 10).get_page(page_number)
    return render(
        request,
        "feeds/feeds.html",
        {
            "posts": posts,
            "can_create_post": is_user(request.user) or is_admin(request.user),
        },
    )


def post_detail(request, post_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    post = get_object_or_404(_post_queryset(request.user), pk=post_id)
    replies = Comment.objects.select_related("author").order_by("created_at", "id")
    comments = (
        Comment.objects.filter(post=post, parent__isnull=True)
        .select_related("author")
        .prefetch_related(Prefetch("replies", queryset=replies))
        .order_by("created_at", "id")
    )
    return render(
        request,
        "feeds/detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": FeedCommentForm(),
            "can_comment": is_user(request.user) or is_admin(request.user),
        },
    )


def post_create(request):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Peran tidak diizinkan membuat postingan.")
    if request.method == "GET":
        return render(
            request,
            "feeds/create.html",
            {"form": FeedPostForm(request.user)},
        )
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "GET, POST"})
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    form = FeedPostForm(request.user, request.POST, request.FILES)
    if form.is_valid():
        form.save(request.user)
        return redirect("feeds:list")
    return render(
        request,
        "feeds/create.html",
        {"form": form},
        status=422,
    )


def post_update(request, post_id):
    return api_post_update(request, post_id)


def post_delete(request, post_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Hanya pemilik postingan yang dapat menghapusnya.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    if post.author_id != request.user.pk:
        return HttpResponseForbidden("Postingan bukan milik Anda.")
    _delete_post(post)
    if request.POST.get("return_to") == "detail":
        return redirect("feeds:list")
    return redirect(f"{reverse('feeds:list')}#post-{post_id}")


def toggle_like(request, post_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Peran tidak diizinkan menyukai postingan.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post, pk=post_id)
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    action = request.POST.get("action")
    if action == "like":
        Like.objects.get_or_create(post=post, user=request.user)
    elif action == "unlike":
        Like.objects.filter(post=post, user=request.user).delete()
    else:
        return _validation_error(request, "action", "Aksi like tidak valid.")
    if request.POST.get("return_to") == "detail":
        return redirect(
            f"{reverse('feeds:detail', args=(post.pk,))}#post-actions-{post.pk}"
        )
    return redirect(f"{reverse('feeds:list')}#post-{post.pk}")


def comment_create(request, post_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Peran tidak diizinkan membuat komentar.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post, pk=post_id)
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    form = FeedCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        return redirect("feeds:detail", post_id=post.pk)
    replies = Comment.objects.select_related("author").order_by("created_at", "id")
    comments = (
        Comment.objects.filter(post=post, parent__isnull=True)
        .select_related("author")
        .prefetch_related(Prefetch("replies", queryset=replies))
        .order_by("created_at", "id")
    )
    post = _post_queryset(request.user).get(pk=post.pk)
    return render(
        request,
        "feeds/detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": form,
            "can_comment": True,
        },
        status=422,
    )


def comment_delete(request, comment_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Peran tidak diizinkan menghapus komentar.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    comment = get_object_or_404(Comment, pk=comment_id)
    if not is_admin(request.user) and comment.author_id != request.user.pk:
        return HttpResponseForbidden("Komentar bukan milik Anda.")
    post_id = comment.post_id
    _delete_comment(comment)
    return redirect("feeds:detail", post_id=post_id)


def moderate_post(request, post_id):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    if not is_admin(request.user):
        return HttpResponseForbidden("Hanya admin yang dapat memoderasi postingan.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post, pk=post_id)
    _delete_post(post)
    if request.POST.get("return_to") == "detail":
        return redirect("feeds:list")
    return redirect(f"{reverse('feeds:list')}#post-{post_id}")
