"""
NetTwin 3.0 — Supplementary Artifacts Packager
==============================================
Creates a unified, publication-ready ZIP archive containing:
- README.md (Primary documentation with 30 datasets and 161 tests)
- eval/results/ (All CSV, JSON, Markdown audit dossiers, and pytest logs)
- docs/screenshots/ (Full-resolution 300 DPI interface screenshots)
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = ROOT / "supplementary_evaluation_artifacts.zip"


def create_supplementary_zip():
    files_to_zip = []

    # 1. README.md
    readme_path = ROOT / "README.md"
    if readme_path.exists():
        files_to_zip.append((readme_path, "README.md"))

    # 2. docs/screenshots/
    screenshots_dir = ROOT / "docs" / "screenshots"
    if screenshots_dir.exists():
        for p in screenshots_dir.rglob("*"):
            if p.is_file():
                rel_path = p.relative_to(ROOT)
                files_to_zip.append((p, str(rel_path).replace("\\", "/")))

    # 3. eval/results/
    eval_results_dir = ROOT / "eval" / "results"
    if eval_results_dir.exists():
        for p in eval_results_dir.rglob("*"):
            if p.is_file() and not p.name.endswith(".zip"):
                rel_path = p.relative_to(ROOT)
                files_to_zip.append((p, str(rel_path).replace("\\", "/")))

    # 4. papers/ (Figures, READMEs, generation scripts, and test runners)
    papers_dir = ROOT / "papers"
    if papers_dir.exists():
        for p in papers_dir.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                rel_path = p.relative_to(ROOT)
                files_to_zip.append((p, str(rel_path).replace("\\", "/")))

    print(f"Packaging {len(files_to_zip)} files into {ZIP_PATH}...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files_to_zip:
            zf.write(src, arc)

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Supplementary archive ready: {ZIP_PATH} ({size_mb:.2f} MB, {len(files_to_zip)} files)")
    return ZIP_PATH


if __name__ == "__main__":
    create_supplementary_zip()
