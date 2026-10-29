import json
import logging
import uuid
from functools import wraps
from json import JSONDecodeError

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Count, Exists, OuterRef, Prefetch, Q, Value
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.http.multipartparser import MultiPartParser, MultiPartParserError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.challenges.models import Challenge, ChallengeParticipation
from apps.challenges.queries import featured_badge_prefetch
from apps.challenges.services import active_progress
from apps.core.permissions import is_admin, is_user
from apps.notifications.services import Kind, display_name, notify

from . import media
from .forms import FeedCommentForm, FeedPostForm
from .models import Comment, CommentLike, Like, Post

logger = logging.getLogger(__name__)
LIKERS_PER_PAGE = 20
FEED_SORTS = ("latest", "popular")


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
                        "comment-like",
                        "comment-likers",
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


def _liked_by(likes, user):
    if not user.is_authenticated:
        return Value(False, output_field=BooleanField())
    return Exists(likes.filter(user=user))


def _post_queryset(user):
    liked = _liked_by(Like.objects.filter(post_id=OuterRef("pk")), user)
    return (
        Post.objects.select_related("author", "challenge")
        .prefetch_related(
            "images",
            featured_badge_prefetch("author"),
            # The two latest likers for "Disukai oleh ... dan N lainnya"
            Prefetch(
                "likes",
                queryset=Like.objects.select_related("user").order_by(
                    "-created_at", "-id"
                )[:2],
                to_attr="recent_likes",
            ),
        )
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=liked,
        )
        .order_by("-created_at", "-id")
    )


def _comment_queryset(user):
    liked = _liked_by(CommentLike.objects.filter(comment_id=OuterRef("pk")), user)
    return (
        Comment.objects.select_related("author")
        .prefetch_related(featured_badge_prefetch("author"))
        .annotate(like_count=Count("likes", distinct=True), liked_by_me=liked)
        .order_by("created_at", "id")
    )


def _comment_thread(post, user):
    """Top-level comments of a post, each with its replies (one level deep)."""
    return (
        _comment_queryset(user)
        .filter(post=post, parent__isnull=True)
        .prefetch_related(Prefetch("replies", queryset=_comment_queryset(user)))
    )


def _author_data(user):
    badge = user.featured_badge
    return {
        "id": str(user.pk),
        "name": user.get_full_name().strip() or user.get_username(),
        "avatar_url": user.avatar_url,
        "badge": (
            {"name": badge.name, "icon": badge.icon, "tone": badge.tone}
            if badge
            else None
        ),
    }


def _image_urls(request, post):
    return [request.build_absolute_uri(image.image.url) for image in post.images.all()]


def _post_data(request, post):
    images = _image_urls(request, post)
    return {
        "id": str(post.pk),
        "content": post.content,
        # First photo, kept for clients written before posts had several
        "image_url": images[0] if images else None,
        "images": images,
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
    like_count = (
        comment.like_count if hasattr(comment, "like_count") else comment.likes.count()
    )
    data = {
        "id": str(comment.pk),
        "post_id": str(comment.post_id),
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "content": comment.content,
        "author": _author_data(comment.author),
        "like_count": like_count,
        "liked_by_me": bool(getattr(comment, "liked_by_me", False)),
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
        "id": str(comment.pk),
        "post_id": str(comment.post_id),
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "content": comment.content,
        "author": _author_data(comment.author),
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
    }


@require_http_methods(["GET"])
def get_comment_json(request):
    if not request.user.is_authenticated:
        return _error(request, 401, "UNAUTHENTICATED", "Autentikasi diperlukan.")
    comments = (
        Comment.objects.select_related("author")
        .prefetch_related(featured_badge_prefetch("author"))
        .order_by("created_at", "id")
    )
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


_IMAGE_ERRORS = {
    "too_many": (422, "TOO_MANY_IMAGES"),
    "too_large": (413, "PAYLOAD_TOO_LARGE"),
    "unsupported": (415, "UNSUPPORTED_MEDIA_TYPE"),
}


def _uploaded_images(files):
    if not files:
        return []
    if hasattr(files, "getlist"):
        return files.getlist("images") + files.getlist("image")
    return [files[key] for key in ("images", "image") if files.get(key)]


def _validate_images(request, uploads):
    """Returns (validated uploads, error response)."""
    try:
        return media.validate_images(uploads, request.user), None
    except ValidationError as error:
        if error.code in _IMAGE_ERRORS:
            status, code = _IMAGE_ERRORS[error.code]
            return None, _error(request, status, code, error.messages[0])
        return None, _validation_error(request, "images", error.messages[0])


def _delete_stored_files(names):
    for name in names:
        media.delete_file(name)


# ---------------------------------------------------------------- notifications


def _notify_post_liked(post, actor):
    notify(
        post.author,
        Kind.POST_LIKED,
        f"{display_name(actor)} menyukai postinganmu",
        post.content[:120],
        url=reverse("feeds:detail", args=(post.pk,)),
        actor=actor,
        dedupe_key=f"post:{post.pk}",
    )


def _notify_comment(comment, actor):
    post = comment.post
    url = f"{reverse('feeds:detail', args=(post.pk,))}#comment-{comment.pk}"
    if comment.parent_id:
        parent = comment.parent
        notify(
            parent.author,
            Kind.COMMENT_REPLIED,
            f"{display_name(actor)} membalas komentarmu",
            comment.content[:200],
            url=url,
            actor=actor,
        )
        if post.author_id == parent.author_id:
            return
    notify(
        post.author,
        Kind.POST_COMMENTED,
        f"{display_name(actor)} mengomentari postinganmu",
        comment.content[:200],
        url=url,
        actor=actor,
    )


def _notify_comment_liked(comment, actor):
    post_url = reverse("feeds:detail", args=(comment.post_id,))
    notify(
        comment.author,
        Kind.COMMENT_LIKED,
        f"{display_name(actor)} menyukai komentarmu",
        comment.content[:120],
        url=f"{post_url}#comment-{comment.pk}",
        actor=actor,
        dedupe_key=f"comment:{comment.pk}",
    )


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
                "Kamu belum mengikuti challenge ini.",
            )
    uploads, image_error = _validate_images(request, _uploaded_images(files))
    if image_error:
        return image_error
    post = Post(author=request.user, challenge=challenge, content=content.strip())
    with transaction.atomic():
        post.save()
        media.save_images(post, uploads)
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
        return _error(request, 403, "NOT_OWNER", "Postingan bukan milikmu.")
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
    uploads = _uploaded_images(files)
    if uploads and remove_image:
        return _validation_error(
            request, "image", "Foto tidak dapat diganti dan dihapus sekaligus."
        )
    if content is None and not uploads and not remove_image:
        return _validation_error(
            request, "content", "Minimal satu field yang dapat diubah diperlukan."
        )
    uploads, image_error = _validate_images(request, uploads)
    if image_error:
        return image_error
    old_names = media.stored_names(post)
    content_changed = content is not None and post.content != content.strip()
    # New photos replace the old set; remove_image clears it
    images_changed = bool(uploads) or (remove_image and bool(old_names))
    if not content_changed and not images_changed:
        post = _post_queryset(request.user).get(pk=post.pk)
        return _ok(
            request,
            {"data": _post_data(request, post)},
            template="feeds/partials/post_card.html",
            context={"post": post, "post_data": _post_data(request, post)},
        )
    with transaction.atomic():
        update_fields = ["updated_at"]
        if content_changed:
            post.content = content.strip()
            update_fields.append("content")
        if images_changed:
            post.images.all().delete()
            media.save_images(post, uploads)
            transaction.on_commit(lambda: _delete_stored_files(old_names))
        post.save(update_fields=update_fields)
    post = _post_queryset(request.user).get(pk=post.pk)
    return _ok(
        request,
        {"data": _post_data(request, post)},
        template="feeds/partials/post_card.html",
        context={"post": post, "post_data": _post_data(request, post)},
    )


def delete_post(post):
    names = media.stored_names(post)
    with transaction.atomic():
        post.delete()
        transaction.on_commit(lambda: _delete_stored_files(names))


@_api_endpoint(("DELETE",), roles=("user", "admin"))
def api_post_delete(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    if not is_admin(request.user) and post.author_id != request.user.pk:
        return _error(request, 403, "NOT_OWNER", "Postingan bukan milikmu.")
    delete_post(post)
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
    delete_post(post)
    return _delete_response(request)


@_api_endpoint(("GET",))
def api_comment_list(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    pagination, error = _pagination(request)
    if error:
        return error
    queryset = _comment_thread(post, request.user)
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
    _notify_comment(comment, request.user)
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
    _notify_comment(reply, request.user)
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
        return _error(request, 403, "NOT_OWNER", "Komentar bukan milikmu.")
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
        return _error(request, 403, "NOT_OWNER", "Komentar bukan milikmu.")
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
        if created:
            _notify_post_liked(post, request.user)
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


@_api_endpoint(("POST", "DELETE"), roles=("user", "admin"))
def api_toggle_comment_like(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("author"), pk=comment_id)
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    created = False
    if request.method == "POST":
        try:
            _, created = CommentLike.objects.get_or_create(
                comment=comment, user=request.user
            )
        except IntegrityError:
            created = False
        if created:
            _notify_comment_liked(comment, request.user)
    else:
        CommentLike.objects.filter(comment=comment, user=request.user).delete()
    liked = request.method == "POST"
    like_count = CommentLike.objects.filter(comment=comment).count()
    return JsonResponse(
        {
            "data": {
                "comment_id": str(comment.pk),
                "liked": liked,
                "like_count": like_count,
            }
        },
        status=201 if created else 200,
    )


def _likers_page(request, likes):
    """One page of the people behind some likes, as JSON."""
    likes = (
        likes.select_related("user")
        .prefetch_related(featured_badge_prefetch("user"))
        .order_by("-created_at", "-id")
    )
    page_obj = Paginator(likes, LIKERS_PER_PAGE).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "data": [
                {**_author_data(like.user), "liked_at": like.created_at.isoformat()}
                for like in page_obj.object_list
            ],
            "meta": {
                "page": page_obj.number,
                "per_page": LIKERS_PER_PAGE,
                "total_items": page_obj.paginator.count,
                "total_pages": page_obj.paginator.num_pages,
            },
        }
    )


@_api_endpoint(("GET",))
def api_post_likers(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    return _likers_page(request, Like.objects.filter(post=post))


@_api_endpoint(("GET",))
def api_comment_likers(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    return _likers_page(request, CommentLike.objects.filter(comment=comment))


def _login_required_page(request, next_url=None):
    """Kirim tamu ke halaman masuk, lalu kembali ke halaman yang dituju."""
    if request.method == "GET":
        next_url = request.get_full_path()
    return redirect_to_login(next_url or reverse("feeds:list"))


def _feed_sidebar(user):
    """Running challenges that feed activity moves forward."""
    return active_progress(
        user,
        goal_types=(
            Challenge.GoalType.POSTS_CREATED,
            Challenge.GoalType.LIKES_RECEIVED,
            Challenge.GoalType.COMMENTS_WRITTEN,
        ),
    )


@require_http_methods(["GET"])
def post_list(request):
    if request.path.startswith("/api/"):
        return api_post_list(request)
    sort = request.GET.get("sort", "latest")
    if sort not in FEED_SORTS:
        sort = "latest"
    queryset = _post_queryset(request.user)
    if sort == "popular":
        # Most liked first among the last 30 days, so old hits don't stay on top
        since = timezone.now() - timezone.timedelta(days=30)
        queryset = queryset.filter(created_at__gte=since).order_by(
            "-like_count", "-comment_count", "-created_at"
        )
    page = request.GET.get("page", "1")
    try:
        page_number = max(int(page), 1)
    except ValueError:
        page_number = 1
    posts = Paginator(queryset, 10).get_page(page_number)
    can_create_post = is_user(request.user) or is_admin(request.user)
    return render(
        request,
        "feeds/feeds.html",
        {
            "posts": posts,
            "sort": sort,
            "sort_options": (
                ("latest", "Terbaru", "clock"),
                ("popular", "Populer", "trending-up"),
            ),
            "can_create_post": can_create_post,
            # The quick composer on the list page posts to feeds:create
            "form": FeedPostForm(request.user) if can_create_post else None,
            "challenge_progress": _feed_sidebar(request.user),
        },
    )


def _detail_context(request, post, comment_form=None):
    return {
        "post": post,
        "comments": _comment_thread(post, request.user),
        "comment_form": comment_form or FeedCommentForm(),
        "can_comment": is_user(request.user) or is_admin(request.user),
    }


def post_detail(request, post_id):
    if not request.user.is_authenticated:
        return _login_required_page(request)
    post = get_object_or_404(_post_queryset(request.user), pk=post_id)
    return render(request, "feeds/detail.html", _detail_context(request, post))


def post_create(request):
    if not request.user.is_authenticated:
        return _login_required_page(request)
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
        return _login_required_page(request)
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Hanya pemilik postingan yang dapat menghapusnya.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)
    if post.author_id != request.user.pk:
        return HttpResponseForbidden("Postingan bukan milikmu.")
    delete_post(post)
    if request.POST.get("return_to") == "detail":
        return redirect("feeds:list")
    return redirect(f"{reverse('feeds:list')}#post-{post_id}")


def toggle_like(request, post_id):
    if not request.user.is_authenticated:
        return _login_required_page(request, reverse("feeds:detail", args=(post_id,)))
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
        _, created = Like.objects.get_or_create(post=post, user=request.user)
        if created:
            _notify_post_liked(post, request.user)
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
        return _login_required_page(request, reverse("feeds:detail", args=(post_id,)))
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
        _notify_comment(comment, request.user)
        return redirect("feeds:detail", post_id=post.pk)
    post = _post_queryset(request.user).get(pk=post.pk)
    return render(
        request, "feeds/detail.html", _detail_context(request, post, form), status=422
    )


def _can_interact(user):
    return is_user(user) or is_admin(user)


def reply_create(request, comment_id):
    """Reply from the post page. Replying to a reply answers the same thread,
    like Instagram, so threads never get deeper than one level."""
    if not request.user.is_authenticated:
        return _login_required_page(request)
    if not _can_interact(request.user):
        return HttpResponseForbidden("Peran tidak diizinkan membalas komentar.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    target = get_object_or_404(
        Comment.objects.select_related("post", "parent"), pk=comment_id
    )
    throttle_response = _throttle(request)
    if throttle_response:
        return throttle_response
    root = target.parent or target
    form = FeedCommentForm(request.POST)
    detail_url = reverse("feeds:detail", args=(root.post_id,))
    if not form.is_valid():
        messages.error(request, form.errors["content"][0])
        return redirect(f"{detail_url}#comment-{target.pk}")
    reply = Comment.objects.create(
        post_id=root.post_id,
        parent=root,
        author=request.user,
        content=form.cleaned_data["content"],
    )
    _notify_comment(reply, request.user)
    return redirect(f"{detail_url}#comment-{reply.pk}")


def comment_like(request, comment_id):
    """Like/unlike a comment without JavaScript (the page uses the API)."""
    if not request.user.is_authenticated:
        return _login_required_page(request)
    if not _can_interact(request.user):
        return HttpResponseForbidden("Peran tidak diizinkan menyukai komentar.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    comment = get_object_or_404(Comment.objects.select_related("author"), pk=comment_id)
    action = request.POST.get("action")
    if action == "like":
        _, created = CommentLike.objects.get_or_create(
            comment=comment, user=request.user
        )
        if created:
            _notify_comment_liked(comment, request.user)
    elif action == "unlike":
        CommentLike.objects.filter(comment=comment, user=request.user).delete()
    else:
        return _validation_error(request, "action", "Aksi like tidak valid.")
    detail_url = reverse("feeds:detail", args=(comment.post_id,))
    return redirect(f"{detail_url}#comment-{comment.pk}")


def post_likers(request, post_id):
    """Who liked a post: the modal fetches this page as HTML."""
    if not request.user.is_authenticated:
        return _login_required_page(request)
    post = get_object_or_404(Post, pk=post_id)
    return _likers_html(request, Like.objects.filter(post=post))


def comment_likers(request, comment_id):
    if not request.user.is_authenticated:
        return _login_required_page(request)
    comment = get_object_or_404(Comment, pk=comment_id)
    return _likers_html(request, CommentLike.objects.filter(comment=comment))


def _likers_html(request, likes):
    likes = (
        likes.select_related("user")
        .prefetch_related(featured_badge_prefetch("user"))
        .order_by("-created_at", "-id")
    )
    page_obj = Paginator(likes, LIKERS_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "feeds/partials/likers.html",
        {"page_obj": page_obj, "likes": page_obj.object_list},
    )


def comment_delete(request, comment_id):
    if not request.user.is_authenticated:
        return _login_required_page(request)
    if not (is_user(request.user) or is_admin(request.user)):
        return HttpResponseForbidden("Peran tidak diizinkan menghapus komentar.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    comment = get_object_or_404(Comment, pk=comment_id)
    if not is_admin(request.user) and comment.author_id != request.user.pk:
        return HttpResponseForbidden("Komentar bukan milikmu.")
    post_id = comment.post_id
    _delete_comment(comment)
    return redirect("feeds:detail", post_id=post_id)


def moderate_post(request, post_id):
    if not request.user.is_authenticated:
        return _login_required_page(request)
    if not is_admin(request.user):
        return HttpResponseForbidden("Hanya admin yang dapat memoderasi postingan.")
    if request.method != "POST":
        return HttpResponse(status=405, headers={"Allow": "POST"})
    post = get_object_or_404(Post, pk=post_id)
    delete_post(post)
    if request.POST.get("return_to") == "detail":
        return redirect("feeds:list")
    return redirect(f"{reverse('feeds:list')}#post-{post_id}")
