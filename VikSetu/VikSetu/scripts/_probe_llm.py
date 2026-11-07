import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import llm

print(llm.which())
print(llm.ask("Reply with exactly: ready"))
