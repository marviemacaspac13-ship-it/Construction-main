"""Private, immutable original images. Object operations always follow an owner RPC."""
import hashlib
import io
import os
import warnings
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.auth import current_user
from app.materials import _client
from app.revisions import rpc

BUCKET = 'trace-plans'
MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
VIEW_SECONDS = 300
FORMATS = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


def require_plan_storage():
    if os.getenv('PLAN_ASSETS_ENABLED', '').lower() != 'true':
        raise HTTPException(503, 'Original-plan storage is not configured yet. Keep this tab open and retry after storage is enabled.')


router = APIRouter(dependencies=[Depends(current_user), Depends(require_plan_storage)])


def inspect_image(raw: bytes, filename: str, declared_type: str | None) -> dict:
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(413, 'Upload an image no larger than 25 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                media = FORMATS.get(image.format)
                if media is None or declared_type != media:
                    raise HTTPException(415, 'Upload a PNG, JPG or WebP image with a matching file type. PDF is not supported yet.')
                width, height = image.size
                if width * height > MAX_PIXELS or width <= 0 or height <= 0:
                    raise HTTPException(413, 'This image exceeds 40 million pixels. Export a smaller image with readable dimensions and labels.')
                if getattr(image, 'n_frames', 1) != 1:
                    raise HTTPException(415, 'Upload a single, static plan image.')
                image.verify()
            # Verify actual pixel decoding too, without re-encoding the stored original.
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(413, 'This image exceeds the pixel limit. Export a smaller image.') from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(400, 'The image is corrupt or unsupported. Upload a readable PNG, JPG or WebP.') from exc
    if not filename or len(filename) > 255:
        raise HTTPException(422, 'Use a filename between 1 and 255 characters.')
    return {'source_sha256': hashlib.sha256(raw).hexdigest(), 'original_filename': filename,
            'media_type': media, 'byte_size': len(raw), 'pixel_width': width, 'pixel_height': height}


@router.post('/api/projects/{project_id}/plans/{upload_id}')
def upload_plan(project_id: UUID, upload_id: UUID, file: UploadFile = File(...), owner: str = Depends(current_user)):
    # Bound the read before decoding. No user-provided string becomes an object path.
    raw = file.file.read(MAX_BYTES + 1)
    metadata = inspect_image(raw, file.filename or '', file.content_type)
    reservation = rpc('begin_plan_upload', {'p_owner': owner, 'p_project_id': str(project_id),
                      'p_upload_id': str(upload_id), 'p_metadata': metadata})
    storage = _client().storage.from_(BUCKET)
    if reservation['state'] != 'ready':
        try:
            storage.upload(reservation['storage_path'], raw,
                           {'content-type': metadata['media_type'], 'upsert': 'false'})
        except Exception as upload_error:
            # A lost response may already have stored the bytes. Compare, never overwrite.
            try:
                existing = storage.download(reservation['storage_path'])
                if hashlib.sha256(existing).hexdigest() != metadata['source_sha256']:
                    raise ValueError('object mismatch')
            except Exception:
                raise HTTPException(503, 'Could not upload the original plan. Keep this tab open and retry uploading.') from upload_error
    asset = rpc('finish_plan_upload', {'p_owner': owner, 'p_project_id': str(project_id), 'p_upload_id': str(upload_id)})
    return asset


@router.get('/api/projects/{project_id}/plans/{asset_id}/view')
def view_plan(project_id: UUID, asset_id: UUID, owner: str = Depends(current_user)):
    asset = rpc('owned_plan_asset', {'p_owner': owner, 'p_project_id': str(project_id), 'p_asset_id': str(asset_id)})
    if not asset.get('storage_path'):
        raise HTTPException(404, 'The original image was not saved for this older scan. Re-upload the plan to enable viewing.')
    try:
        result = _client().storage.from_(BUCKET).create_signed_url(asset['storage_path'], VIEW_SECONDS)
        url = result.get('signedURL') or result.get('signedUrl')
        if not url:
            raise ValueError('missing viewing link')
    except Exception as exc:
        raise HTTPException(503, 'Could not open the original plan. Retry opening it.') from exc
    return {'url': url, 'expires_in': VIEW_SECONDS, 'asset_id': str(asset_id)}


@router.post('/api/plans/cleanup')
def cleanup_plans(owner: str = Depends(current_user)):
    paths = rpc('claim_plan_file_cleanup', {'p_owner': owner})
    removed = 0
    storage = _client().storage.from_(BUCKET)
    for path in paths:
        try:
            # Storage delete is idempotent, including an upload that never reached storage.
            storage.remove([path])
            rpc('finish_plan_file_cleanup', {'p_owner': owner, 'p_path': path})
            removed += 1
        except Exception as exc:
            raise HTTPException(503, 'Some plan files could not be cleaned up. Retry cleanup; saved plan versions are preserved.') from exc
    return {'removed': removed}
