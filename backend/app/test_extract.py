# test_extract.py
from pathlib import Path
from app.drive import extract_text_from_bytes

p = Path("path/to/your/test.pptx")  # change to a real pptx path
b = p.read_bytes()
txt = extract_text_from_bytes(b, p.name, "")
print("EXTRACTED TEXT (first 800 chars):")
print(txt[:800])
