"""
run_all.py
02~10번 분석을 순서대로 실행해 보고서의 표(output/tables)와 그림(output/figures)을 다시 만든다.
01번(원자료 결합)은 행정동 경계 파일이 있어야 하므로 기본으로는 건너뛴다. 필요하면 --with-01 을 붙인다.

    python run_all.py
    python run_all.py --with-01
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["02_analysis", "03_carbon", "04_trend", "05_robustness", "06_figures",
         "07_ml_shap", "08_infographic", "09_headway_validation", "10_print_figures"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    steps = (["01_build_dataset"] if "--with-01" in sys.argv else []) + STEPS
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}
    (ROOT / "output" / "tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "output" / "figures").mkdir(parents=True, exist_ok=True)
    for s in steps:
        t = time.time()
        r = subprocess.run([sys.executable, str(ROOT / "code" / f"{s}.py")], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"[실패] {s}\n{r.stderr[-2000:]}")
            sys.exit(1)
        print(f"[완료] {s} ({time.time() - t:.0f}초)")
    print("모든 단계 완료: output/tables, output/figures 를 확인하세요.")


if __name__ == "__main__":
    main()
