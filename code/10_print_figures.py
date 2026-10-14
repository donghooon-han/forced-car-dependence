"""
10_print_figures.py
한글 보고서 칸(폭 약 11.6cm)에 실제 크기로 들어갈 인쇄용 그림.
큰 화면용 그림을 줄이면 글씨가 2~3pt가 되므로, 처음부터 인쇄 크기(인치)로 그리고 글씨를 6~7pt로 맞춘다.
  print_fig1_map_scatter.png : 의존 지수 지도 + 소득 대비 승용차 통근 비율
  print_fig2_shap.png        : 전체 요인 중요도 + 핵심 17곳 요인 기여 (막대)
  print_fig3_break_even.png  : 탄소 손익분기
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 6.5,
                     "axes.titlesize": 7.2, "axes.labelsize": 6.5, "xtick.labelsize": 6,
                     "ytick.labelsize": 6, "legend.fontsize": 5.8})

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
RED, BLUE, GREY = "#c0392b", "#2e6da4", "#bdbdbd"
DPI = 450


def fig1():
    g = gpd.read_file(PROC / "sgg_2020_analyzed.geojson")
    gm = g.to_crs(5179)
    fig, axes = plt.subplots(1, 2, figsize=(3.9, 2.05), gridspec_kw={"width_ratios": [0.85, 1.15]})
    ax = axes[0]
    xmin, ymin, xmax, ymax = gm[gm["key"] != "경북|울릉군"].total_bounds
    gm.plot(column="fcd_index", cmap="RdBu_r", vmin=-4, vmax=4, ax=ax, edgecolor="white", linewidth=0.1)
    gm[gm["core"]].boundary.plot(ax=ax, color="black", linewidth=0.5)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_axis_off()
    ax.set_title("의존 지수 (테두리: 핵심 17곳)")
    sm = plt.cm.ScalarMappable(cmap="RdBu_r", norm=plt.Normalize(-4, 4))
    cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.0, shrink=0.6)
    cb.ax.tick_params(labelsize=5)
    cb.set_label("높을수록 의심", fontsize=5.5)

    ax = axes[1]
    q = g["quadrant"]
    for name, c, lab in [("선택적 자가용(고소득)", BLUE, "고소득·고자가용"), ("저소득·저자가용", GREY, "저소득·저자가용"),
                         ("기타", "#e3e3e3", "기타"), ("강제된 의존 의심", RED, "강제된 의존 의심")]:
        s = g[q == name]
        ax.scatter(s["income_per_worker"], s["car_share"] * 100, s=5, c=c, edgecolors="none", label=lab)
    cs = g[g["core"]]
    ax.scatter(cs["income_per_worker"], cs["car_share"] * 100, s=9, facecolors="none", edgecolors="black",
               linewidths=0.5, label="핵심 17곳")
    for nm, off in [("진천군", (3, -1))]:
        r = g[g["key"].str.endswith(nm)].iloc[0]
        ax.annotate(nm, (r["income_per_worker"], r["car_share"] * 100), fontsize=5.4, xytext=off,
                    textcoords="offset points")
    ax.axvline(g["income_per_worker"].median(), color="grey", lw=0.4, ls="--")
    ax.axhline(g["car_share"].median() * 100, color="grey", lw=0.4, ls="--")
    ax.set_xlim(2500, 5200)
    ax.set_xlabel("1인당 근로소득 (만원, 2020)")
    ax.set_ylabel("승용차 통근 비율 (%)")
    ax.set_title("소득 대비 승용차 의존")
    ax.legend(loc="lower right", frameon=False, handletextpad=0.2, borderpad=0.2, labelspacing=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3, w_pad=0.6)
    fig.savefig(FIG / "print_fig1_map_scatter.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


def fig2():
    imp = pd.read_csv(TAB / "ml_shap_importance.csv", index_col=0).iloc[:, 0].sort_values()
    core = pd.read_csv(TAB / "ml_shap_core.csv", index_col=0).iloc[:, 0].sort_values()
    perf = pd.read_csv(TAB / "ml_performance.csv", index_col=0)
    r2 = perf.iloc[0, 0]
    fig, axes = plt.subplots(1, 2, figsize=(3.9, 1.55))
    ax = axes[0]
    ax.barh(imp.index, imp.values, color="#7f8c8d")
    ax.set_title(f"전체 요인 중요도 (R²={r2:.2f})")
    ax.set_xlabel("평균 |SHAP| (%p)")
    ax = axes[1]
    ax.barh(core.index, core.values, color=[RED if v > 0 else BLUE for v in core.values])
    ax.axvline(0, color="grey", lw=0.5)
    ax.set_title("핵심 17곳 기여 방향")
    ax.set_xlabel("평균 SHAP (%p, +는 의존을 올림)")
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(FIG / "print_fig2_shap.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


def fig3():
    occ = np.linspace(0, 16, 200)
    fig, ax = plt.subplots(figsize=(2.55, 1.65))
    ax.fill_between(occ, occ * 0.5 * 173, 1200, color="#f2d7d5", alpha=0.6, lw=0)
    ax.plot(occ, occ * 0.5 * 173, color="#2c3e50", lw=0.9, label="순감축 한계선(승용차 출신 50%)")
    ax.plot(occ, occ * 0.3 * 173, color="#2c3e50", lw=0.9, ls="--", label="순감축 한계선(30%)")
    ax.axhline(723, color=RED, lw=1.1)
    ax.text(0.3, 760, "대형버스 약 723 g/km", color=RED, fontsize=5.8)
    ax.axvline(723 / (0.5 * 173), color=RED, lw=0.5, ls=":")
    ax.text(8.7, 230, "새 승객 8.4명↑\n이어야 순감축", color=RED, fontsize=5.6)
    ax.text(0.5, 1040, "이 영역의 차량은 배출 증가", color="#7f2a1f", fontsize=5.6)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 1200)
    ax.set_xlabel("늘린 차량 1대당 새 승객 (명)")
    ax.set_ylabel("차량 배출 (gCO₂/km)")
    ax.legend(loc="center right", frameon=False, fontsize=5.2, bbox_to_anchor=(1.0, 0.42))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "print_fig3_break_even.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    print("저장:", FIG)
