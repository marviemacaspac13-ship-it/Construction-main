# TRACE Detection API

FastAPI service that runs YOLOv8 (detection) + OpenCV (preprocessing) +
Tesseract (dimension OCR) on an uploaded construction plan image, matches
what it finds against your Supabase materials catalog, and returns a
priced takeoff.

## 1. Install

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

You also need the **Tesseract OCR engine itself** installed (pytesseract
just calls out to it):
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

## 2. Configure

```bash
cp .env.example .env
```

Fill in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Project Settings →
API in your Supabase dashboard — use the **service role** key here, not
the anon key, since this runs server-side). Run `materials_seed.sql`
(one level up) in the Supabase SQL editor first so the `materials` table
exists and is populated.

If Tesseract isn't on your PATH, set `TESSERACT_CMD` to its install path.

## 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Check it's alive: http://localhost:8000/health

## 4. The one thing this scaffold does NOT include: a trained model

`YOLO_WEIGHTS_PATH` defaults to the stock `yolov8n.pt`, which is trained
on everyday objects (COCO) — it will not recognize outlets, rebar, pipe
fittings, etc. To get real detections:

1. Collect plan images (the more varied, the better).
2. Label symbol instances — tools like Roboflow, CVAT, or LabelImg work well.
   Use class names that match `LABEL_MAP` in `app/pricing.py` (or edit
   that map to match whatever names you choose).
3. Train:
   ```bash
   yolo detect train data=plans.yaml model=yolov8n.pt epochs=100 imgsz=1280
   ```
4. Point `YOLO_WEIGHTS_PATH` in `.env` at the resulting `best.pt`.

Nothing else in the pipeline needs to change — swap the weights file and
the API starts returning real detections.

## API

`POST /api/scan` — multipart form upload, field name `file`.

Response:
```json
{
  "line_items": [
    { "item_id": "CHB02", "item_name": "Concrete Hollow Blocks", "unit": "6 inches / Per Pc",
      "unit_price": 18, "quantity": 340, "line_total": 6120, "avg_confidence": 0.81 }
  ],
  "unmatched_detections": [],
  "grand_total": 6120
}
```

`unmatched_detections` are things YOLO found but couldn't confidently map
to a catalog SKU (e.g. OCR didn't catch a dimension) — surface these in
the UI so the estimator can review/correct them rather than silently
dropping them.
