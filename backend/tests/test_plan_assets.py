"""Private originals: decode limits, retry safety, ownership and link renewal."""
import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.plan_assets import inspect_image

client = TestClient(app)
PROJECT, UPLOAD = str(uuid4()), str(uuid4())
URL = f'/api/projects/{PROJECT}/plans/{UPLOAD}'


def image_bytes(fmt='PNG'):
    out = io.BytesIO()
    Image.new('RGB', (24, 18), 'white').save(out, format=fmt)
    return out.getvalue()


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('PLAN_ASSETS_ENABLED', 'true')


@pytest.mark.parametrize('fmt,mime', [('PNG','image/png'),('JPEG','image/jpeg'),('WEBP','image/webp')])
def test_supported_images_preserve_metadata_and_bytes(fmt, mime):
    raw = image_bytes(fmt)
    metadata = inspect_image(raw, 'original.'+fmt.lower(), mime)
    assert metadata['pixel_width'] == 24 and metadata['pixel_height'] == 18
    assert metadata['byte_size'] == len(raw) and metadata['media_type'] == mime
    storage = MagicMock()
    with patch('app.plan_assets.rpc', side_effect=[{'storage_path':'owned/path','state':'pending'}, {'id':UPLOAD}]) as rpc, \
         patch('app.plan_assets._client') as factory:
        factory.return_value.storage.from_.return_value = storage
        response = client.post(URL, files={'file':('original.'+fmt.lower(),raw,mime)})
    assert response.status_code == 200
    assert rpc.call_args_list[0].args[1]['p_owner'] == 'test-user'
    assert storage.upload.call_args.args[1] == raw
    assert storage.upload.call_args.args[2]['upsert'] == 'false'


@pytest.mark.parametrize('raw,mime,status', [(b'%PDF-1.5','application/pdf',400),
    (image_bytes(),'image/jpeg',415),(b'broken','image/png',400),(b'','image/png',413)])
def test_invalid_files_never_reserve_storage(raw,mime,status):
    with patch('app.plan_assets.rpc') as rpc:
        assert client.post(URL, files={'file':('file.png',raw,mime)}).status_code == status
        rpc.assert_not_called()


def test_pixel_limit_before_decode(monkeypatch):
    monkeypatch.setattr('app.plan_assets.MAX_PIXELS', 100)
    with pytest.raises(HTTPException) as error:
        inspect_image(image_bytes(), 'plan.png', 'image/png')
    assert error.value.status_code == 413


def test_byte_limit_before_decode(monkeypatch):
    monkeypatch.setattr('app.plan_assets.MAX_BYTES', 10)
    with patch('app.plan_assets.Image.open') as decoder:
        assert client.post(URL, files={'file':('plan.png',b'x'*11,'image/png')}).status_code == 413
    decoder.assert_not_called()


def test_lost_upload_response_compares_original_before_finishing():
    raw = image_bytes()
    with patch('app.plan_assets.rpc', side_effect=[{'storage_path':'owned/path','state':'pending'},{'id':UPLOAD}]) as rpc, \
         patch('app.plan_assets._client') as factory:
        storage = factory.return_value.storage.from_.return_value
        storage.upload.side_effect = TimeoutError()
        storage.download.return_value = raw
        assert client.post(URL, files={'file':('plan.png',raw,'image/png')}).status_code == 200
        assert rpc.call_args.args[0] == 'finish_plan_upload'


def test_mismatched_stored_object_never_overwritten_or_finalized():
    with patch('app.plan_assets.rpc', return_value={'storage_path':'owned/path','state':'pending'}) as rpc, \
         patch('app.plan_assets._client') as factory:
        storage = factory.return_value.storage.from_.return_value
        storage.upload.side_effect = ValueError('exists')
        storage.download.return_value = b'different'
        assert client.post(URL, files={'file':('plan.png',image_bytes(),'image/png')}).status_code == 503
        assert rpc.call_count == 1


def test_ownership_refusal_happens_before_object_access():
    with patch('app.plan_assets.rpc', side_effect=HTTPException(404,'Project not found.')), \
         patch('app.plan_assets._client') as factory:
        assert client.post(URL,files={'file':('plan.png',image_bytes(),'image/png')}).status_code == 404
        assert client.get(URL+'/view').status_code == 404
    factory.assert_not_called()


def test_ready_retry_never_uploads_again():
    with patch('app.plan_assets.rpc', side_effect=[{'state':'ready'},{'id':UPLOAD}]), \
         patch('app.plan_assets._client') as factory:
        assert client.post(URL,files={'file':('plan.png',image_bytes(),'image/png')}).status_code == 200
    factory.return_value.storage.from_.return_value.upload.assert_not_called()


def test_view_links_are_short_lived_and_regenerated():
    with patch('app.plan_assets.rpc', return_value={'storage_path':'owned/path'}), patch('app.plan_assets._client') as factory:
        storage = factory.return_value.storage.from_.return_value
        storage.create_signed_url.side_effect = [{'signedURL':'https://storage.test/first'},{'signedURL':'https://storage.test/renewed'}]
        first, second = client.get(URL+'/view'), client.get(URL+'/view')
        assert first.json()['url'] != second.json()['url']
        assert first.json()['expires_in'] == 300
        assert storage.create_signed_url.call_args.args == ('owned/path',300)


def test_legacy_metadata_does_not_invent_a_file():
    with patch('app.plan_assets.rpc', return_value={'storage_path':None}), patch('app.plan_assets._client') as factory:
        assert client.get(URL+'/view').status_code == 404
    factory.assert_not_called()


def test_cleanup_only_uses_owned_rpc_paths_and_retries_failures():
    with patch('app.plan_assets.rpc', side_effect=[['owned/old'],True]) as rpc, patch('app.plan_assets._client') as factory:
        assert client.post('/api/plans/cleanup').json() == {'removed':1}
        factory.return_value.storage.from_.return_value.remove.assert_called_once_with(['owned/old'])
        assert rpc.call_args.args == ('finish_plan_file_cleanup',{'p_owner':'test-user','p_path':'owned/old'})
    with patch('app.plan_assets.rpc', return_value=['owned/old']) as rpc, patch('app.plan_assets._client') as factory:
        factory.return_value.storage.from_.return_value.remove.side_effect = TimeoutError()
        assert client.post('/api/plans/cleanup').status_code == 503
        assert rpc.call_count == 1


def test_unconfigured_storage_refuses_without_object_access(monkeypatch):
    monkeypatch.delenv('PLAN_ASSETS_ENABLED')
    with patch('app.plan_assets._client') as factory:
        assert client.get(URL+'/view').status_code == 503
    factory.assert_not_called()
