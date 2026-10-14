"""
06_figures.py
보고서용 보조 그림
  fig2_trend.png      : 유형별 승용차·대중교통 통근 비율 변화 (2015 → 2020)
  fig3_break_even.png : 늘린 차량 1대당 새 승객 수에 따른 순감축 조건 (탄소 손익분기)
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "output" / "figures"

EF_CAR = 173.0
EF_BUS_VEH = 723.0

ORDER = ["핵심 지역", "선택적 자가용(고소득)", "저소득·저자가용", "기타"]
LABEL = {"핵심 지역": "핵심 17곳", "선택적 자가용(고소득)": "선택적 자가용\n(고소득)",
         "저소득·저자가용": "저소득·\n저자가용", "기타": "기타"}
COLOR = {"핵심 지역": "#c0392b", "선택적 자가용(고소득)": "#4393c3",
         "저소득·저자가용": "#9e9e9e", "기타": "#cfcfcf"}


def fig_trend():
    m = pd.read_csv(PROC / "sgg_trend_2015_2020.csv")
    m = m[m["group"].isin(ORDER)]

    def wmean(x, col, wcol):
        x = x.dropna(subset=[col])
        return (x[col] * x[wcol]).sum() / x[wcol].sum() * 100

    rows = []
    for g in ORDER:
        x = m[m["group"] == g]
        rows.append({
            "group": g,
            "car15": wmean(x, "car_share_2015", "commuters_2015"),
            "car20": wmean(x, "car_share", "commuters"),
            "tr15": wmean(x, "transit_share_2015", "commuters_2015"),
            "tr20": wmean(x, "transit_share", "commuters"),
        })
    s = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, (a, b, title) in zip(axes, [("car15", "car20", "승용차 통근 비율"),
                                         ("tr15", "tr20", "대중교통 통근 비율")]):
        for i, r in s.iterrows():
            c = COLOR[r["group"]]
            lw = 3.2 if r["group"] == "핵심 지역" else 1.8
            ax.plot([0, 1], [r[a], r[b]], color=c, lw=lw, marker="o", ms=7 if lw > 2 else 5)
            dy = {"저소득·저자가용": 6, "기타": -6}.get(r["group"], 0) if a == "car15" else 0
            ax.annotate(f"{r[b]:.1f}%", (1, r[b]), xytext=(8, dy), textcoords="offset points",
                        va="center", fontsize=9, color=c, fontweight="bold" if lw > 2 else "normal")
            ax.annotate(f"{r[a]:.1f}%", (0, r[a]), xytext=(-8, dy), textcoords="offset points",
                        va="center", ha="right", fontsize=8, color=c)
        ax.set_xticks([0, 1], ["2015", "2020"])
        ax.set_xlim(-0.35, 1.45)
        ax.set_title(title, fontsize=12)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("%")
    handles = [plt.Line2D([], [], color=COLOR[g], lw=3.2 if g == "핵심 지역" else 1.8, label=LABEL[g].replace("\n", ""))
               for g in ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9)
    fig.suptitle("핵심 17곳: 승용차 의존은 가장 빠르게 늘고, 대중교통은 제자리 (통근자 가중평균)", fontsize=12)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(FIG / "fig2_trend.png", dpi=200)
    print(s.round(1).to_string(index=False))


def fig_break_even():
    occ = np.linspace(0, 16, 200)
    fig, ax = plt.subplots(figsize=(8, 5.0))
    for f, ls in [(0.5, "-"), (0.3, "--")]:
        ax.plot(occ, occ * f * EF_CAR, color="#2c3e50", ls=ls,
                label=f"순감축 한계선 (새 승객 중 승용차 출신 {int(f*100)}%)")
    ax.axhline(EF_BUS_VEH, color="#c0392b", lw=2)
    ax.text(0.3, EF_BUS_VEH + 25, "대형 경유·CNG 버스 약 723 g/km", color="#c0392b", fontsize=10)
    x50 = EF_BUS_VEH / (0.5 * EF_CAR)
    ax.axvline(x50, color="#c0392b", lw=0.8, ls=":")
    ax.annotate(f"새 승객 {x50:.1f}명 이상이어야\n대형버스 증차가 순감축", (x50, 200), xytext=(10, 0),
                textcoords="offset points", fontsize=9, color="#c0392b")
    ax.fill_between(occ, occ * 0.5 * EF_CAR, 1200, color="#f2d7d5", alpha=0.5)
    ax.text(1.2, 1050, "이 영역의 차량은 오히려 배출 증가", fontsize=9, color="#7f2a1f")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 1200)
    ax.set_xlabel("늘린 차량 1대에 타는 새 승객 수 (평균, 명)")
    ax.set_ylabel("차량 배출 (gCO₂/km)")
    ax.set_title("수요가 적은 지역일수록 '작고 깨끗한' 차량이어야 탄소가 줄어든다", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_break_even.png", dpi=200)


if __name__ == "__main__":
    fig_trend()
    fig_break_even()
    print("저장:", FIG)
