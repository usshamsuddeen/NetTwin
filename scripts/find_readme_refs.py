with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if any(k in line.lower() for k in ["13 dataset", "table a:", "all 13", "18 dataset"]):
        print(f"Line {i+1}: {line.strip()}")
