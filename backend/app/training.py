import shutil
import threading
from pathlib import Path
from ultralytics import YOLO

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATASET_YAML = BACKEND_DIR / "training_data" / "data.yaml"
MODELS_DIR = BACKEND_DIR / "models"

_state = {
    "status": "idle",
    "current_epoch": 0,
    "total_epochs": 0,
    "message": "",
    "weights_path": None,
}
_lock = threading.Lock()


def get_status() -> dict:
    with _lock:
        return dict(_state)


def dataset_ready() -> bool:
    return DATASET_YAML.exists()


def start_training(epochs: int = 100, base_model: str = "yolov8n.pt") -> None:
    with _lock:
        if _state["status"] == "running":
            raise RuntimeError("Training is already running.")
        _state.update(
            status="running",
            current_epoch=0,
            total_epochs=epochs,
            message="Starting…",
            weights_path=None,
        )

    thread = threading.Thread(target=_run_training, args=(epochs, base_model), daemon=True)
    thread.start()


def _run_training(epochs: int, base_model: str) -> None:
    try:
        model = YOLO(base_model)

        def on_epoch_end(trainer):
            with _lock:
                _state["current_epoch"] = trainer.epoch + 1
                _state["message"] = f"Epoch {trainer.epoch + 1}/{epochs}"

        model.add_callback("on_train_epoch_end", on_epoch_end)

        results = model.train(
            data=str(DATASET_YAML),
            epochs=epochs,
            project=str(BACKEND_DIR / "runs"),
            name="train",
            exist_ok=True,
        )

        best_weights = Path(results.save_dir) / "weights" / "best.pt"
        MODELS_DIR.mkdir(exist_ok=True)
        dest = MODELS_DIR / "best.pt"
        shutil.copy(best_weights, dest)

        with _lock:
            _state.update(status="done", message="Training complete.", weights_path=str(dest))

    except Exception as e:
        with _lock:
            _state.update(status="error", message=str(e))
