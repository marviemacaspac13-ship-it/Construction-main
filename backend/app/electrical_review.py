"""Electrical review boundary shared by authenticated local proposal routes.

Authenticated routes must pass their checked owner, never a body-supplied
owner. Receipts bind original observations to exact image bytes and expire in 4h.
"""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import io
import os
import secrets
import time

from PIL import Image
from pydantic import Field

from app.electrical_models import ElectricalObservation, ElectricalReview, ElectricalReviewSubmission, ReviewModel, ElectricalProposalAttempt
from app.plan_assets import inspect_image, MAX_BYTES

DOMAIN = b'trace-electrical-review-v1:'
_LOCAL_SECRET = secrets.token_bytes(32)
MAX_RECEIPT = 1_000_000


class ProposalEnvelope(ReviewModel):
    version: str = Field(pattern=r'^electrical-review-v1$')
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    image_width: int = Field(gt=0, strict=True)
    image_height: int = Field(gt=0, strict=True)
    owner_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(pattern=r'^(template|gemini|openrouter|manual)$')
    model: str = Field(min_length=1, max_length=120)
    issued_at: float = Field(ge=0)
    proposed: list[ElectricalObservation] = Field(max_length=500)
    prompt_version: str | None = Field(None, pattern=r'^electrical-devices-v1$', exclude_if=lambda v: v is None)
    attempts: list[ElectricalProposalAttempt] = Field(default_factory=list, max_length=2, exclude_if=lambda v: not v)
    limitations: list[str] = Field(default_factory=list, max_length=30, exclude_if=lambda v: not v)


def _key():
    return os.environ['ELECTRICAL_REVIEW_SECRET'].encode() if os.getenv('ELECTRICAL_REVIEW_SECRET') else _LOCAL_SECRET


def _identity(raw):
    # Use the same byte/pixel/static-image guards as uploaded originals.
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Electrical review needs an original image no larger than 25 MB.')
    with Image.open(io.BytesIO(raw)) as image:
        mime = Image.MIME.get(image.format)
        filename = {'image/png': 'review.png', 'image/jpeg': 'review.jpg', 'image/webp': 'review.webp'}.get(mime)
        if filename is None or image.getexif().get(274, 1) != 1:
            raise ValueError('Use an upright PNG/JPEG/WebP original for electrical review.')
    return inspect_image(raw, filename, mime)


def issue_review(raw, owner, observations, *, provider, model, prompt_version=None, attempts=None, limitations=None):
    metadata = _identity(raw)
    payload = ProposalEnvelope(version='electrical-review-v1', source_sha256=metadata['source_sha256'],
        image_width=metadata['pixel_width'], image_height=metadata['pixel_height'],
        owner_id=owner, provider=provider, model=model, issued_at=time.time(), proposed=observations,
        prompt_version=prompt_version, attempts=attempts or [], limitations=limitations or [])
    ids = [p.id for p in payload.proposed]
    if len(ids) != len(set(ids)):
        raise ValueError('Original electrical proposal IDs must be unique.')
    encoded = base64.urlsafe_b64encode(payload.model_dump_json().encode()).decode()
    token = encoded + '.' + hmac.new(_key(), DOMAIN + encoded.encode(), hashlib.sha256).hexdigest()
    if len(token) > MAX_RECEIPT:
        raise ValueError('Electrical proposal receipt is too large.')
    return token


def confirm_review(submission, raw, owner):
    submission = ElectricalReviewSubmission.model_validate(submission)
    try:
        encoded, signature = submission.receipt.rsplit('.', 1)
        expected = hmac.new(_key(), DOMAIN + encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('signature')
        payload = ProposalEnvelope.model_validate_json(base64.b64decode(encoded, altchars=b'-_', validate=True))
        metadata = _identity(raw)
        if (payload.owner_id != owner or payload.source_sha256 != metadata['source_sha256'] or
            payload.image_width != metadata['pixel_width'] or payload.image_height != metadata['pixel_height'] or
            not 0 <= time.time() - payload.issued_at < 14400):
            raise ValueError('binding')
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('Electrical review expired or does not belong to this owner/image.') from exc
    return ElectricalReview(**payload.model_dump(exclude={'issued_at'}), choices=submission.choices,
        confirmed_at=datetime.now(timezone.utc), estimate_scope=submission.estimate_scope)


def reviewed_plan(review):
    """Absolute reviewed source counts. Never add them to template aggregates."""
    from app.takeoff.schema import FixtureCount, PlanSchema
    review = ElectricalReview.model_validate(review.model_dump())
    review.require_priceable()
    return PlanSchema(plan_type='Electrical Plan', source='detection', electrical_review=review,
        fixtures=[FixtureCount(item_id=k, count=v) for k, v in sorted(review.priced_counts().items())])
