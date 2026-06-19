import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("handler", ROOT / "handler.py")
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)

event = json.loads((ROOT / "test_event.json").read_text(encoding="utf-8"))
result = handler.lambda_handler(event, None)

print(json.dumps(result, indent=2, ensure_ascii=False))

