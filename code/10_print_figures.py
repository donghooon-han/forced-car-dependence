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
    fig = plt.figure(figsize=(3.9, 2.15))
    # 두 패널의 제목 높이를 맞추려고 축 위치를 직접 정한다(제목은 같은 높이의 fig.text)
    ax_map = fig.add_axes([0.0, 0.17, 0.36, 0.72])
    ax_cb = fig.add_axes([0.06, 0.10, 0.24, 0.025])
    ax = fig.add_axes([0.47, 0.17, 0.52, 0.72])

    xmin, ymin, xmax, ymax = gm[gm["key"] != "경북|울릉군"].total_bounds
    gm.plot(column="fcd_index", cmap="RdBu_r", vmin=-4, vmax=4, ax=ax_map, edgecolor="white", linewidth=0.1)
    gm[gm["core"]].boundary.plot(ax=ax_map, color="black", linewidth=0.5)
    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_axis_off()
    sm = plt.cm.ScalarMappable(cmap="RdBu_r", norm=plt.Normalize(-4, 4))
    cb = fig.colorbar(sm, cax=ax_cb, orientation="horizontal", ticks=[-4, -2, 0, 2, 4])
    cb.ax.tick_params(labelsize=5, length=1.5, pad=1)
    cb.outline.set_linewidth(0.4)
    cb.set_label("의존 지수 (높을수록 의심)", fontsize=5.5, labelpad=1.5)

    q = g["quadrant"]
    for name, c, lab in [("선택적 자가용(고소득)", BLUE, "고소득·고자가용"), ("저소득·저자가용", GREY, "저소득·저자가용"),
                         ("기타", "#e3e3e3", "기타"), ("강제된 의존 의심", RED, "강제된 의존 의심")]:
        sub = g[q == name]
        ax.scatter(sub["income_per_worker"], sub["car_share"] * 100, s=5, c=c, edgecolors="none", label=lab)
    cs = g[g["core"]]
    ax.scatter(cs["income_per_worker"], cs["car_share"] * 100, s=9, facecolors="none", edgecolors="black",
               linewidths=0.5, label="핵심 17곳")
    r = g[g["key"].str.endswith("진천군")].iloc[0]
    ax.annotate("진천군", (r["income_per_worker"], r["car_share"] * 100), fontsize=5.4, xytext=(3, -1),
                textcoords="offset points")
    ax.axvline(g["income_per_worker"].median(), color="grey", lw=0.4, ls="--")
    ax.axhline(g["car_share"].median() * 100, color="grey", lw=0.4, ls="--")
    ax.set_xlim(2500, 5200)
    ax.set_xlabel("근로소득 신고자 1인당 총급여 (만원, 2020)", labelpad=2)
    ax.set_ylabel("승용차 통근 비율 (%)", labelpad=2)
    leg = ax.legend(loc="lower right", frameon=True, handletextpad=0.2, borderpad=0.3, labelspacing=0.25,
                    fontsize=5.4)
    leg.get_frame().set_facecolor("white")
    leg.get_frame().set_edgecolor("none")
    leg.get_frame().set_alpha(0.92)
    ax.spines[["top", "right"]].set_visible(False)

    # 제목: 두 패널 모두 같은 높이, 각 패널 가운데
    ty = 0.955
    fig.text(0.18, ty, "의존 지수 (테두리: 핵심 17곳)", ha="center", va="center", fontsize=7.2)
    pos = ax.get_position()
    fig.text((pos.x0 + pos.x1) / 2, ty, "소득 대비 승용차 통근 비율", ha="center", va="center", fontsize=7.2)
    fig.savefig(FIG / "print_fig1_map_scatter.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


def fig2():
    imp = pd.read_csv(TAB / "ml_shap_importance.csv", index_col=0).iloc[:, 0].sort_values()
    core = pd.read_csv(TAB / "ml_shap_core.csv", index_col=0).iloc[:, 0].sort_values()
    perf = pd.read_csv(TAB / "ml_performance.csv", index_col=0)
    r2 = perf.iloc[0, 0]
    fig, axes = plt.subplots(1, 2, figsize=(3.9, 1.6))
    ax = axes[0]
    ax.barh(imp.index, imp.values, color="#7f8c8d", height=0.65)
    ax.set_title("전체 요인 중요도", pad=4)
    ax.set_xlabel("평균 |SHAP| (%p)")
    ax.text(0.98, 0.04, f"교차검증 R² {r2:.2f}", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=5.4, color="#555555")
    ax = axes[1]
    ax.barh(core.index, core.values, color=[RED if v > 0 else BLUE for v in core.values], height=0.65)
    ax.axvline(0, color="grey", lw=0.5)
    ax.set_xlim(-2, 4)
    ax.set_xticks([-2, -1, 0, 1, 2, 3, 4])
    ax.set_title("핵심 17곳 기여 방향", pad=4)
    ax.set_xlabel("평균 SHAP (%p)")
    ax.text(0.2, list(core.index).index("철도역 유무"), "+ 예측 올림, - 내림", ha="left", va="center",
            fontsize=5.4, color="#555555")
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.3, w_pad=1.0)
    fig.savefig(FIG / "print_fig2_shap.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


def fig3():
    occ = np.linspace(0, 16, 200)
    fig, ax = plt.subplots(figsize=(2.55, 1.65))
    ax.fill_between(occ, occ * 0.5 * 173, 1200, color="#f2d7d5", alpha=0.6, lw=0)
    ax.plot(occ, occ * 0.5 * 173, color="#2c3e50", lw=0.9, label="승용차 배출 감소량(원래 운전자 50%)")
    ax.plot(occ, occ * 0.3 * 173, color="#2c3e50", lw=0.9, ls="--", label="승용차 배출 감소량(30%)")
    ax.axhline(723, color=RED, lw=1.1)
    ax.text(0.3, 760, "대형버스 약 723 g/km", color=RED, fontsize=5.8)
    ax.axvline(723 / (0.5 * 173), color=RED, lw=0.5, ls=":")
    ax.text(8.7, 300, "새 승객 8.4명↑\n이어야 순감축", color=RED, fontsize=5.6)
    ax.text(0.5, 1040, "이 영역의 차량은 배출 증가", color="#7f2a1f", fontsize=5.6)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 1200)
    ax.set_xlabel("늘린 차량의 평균 재차인원 (새 승객, 명)")
    ax.set_ylabel("차량 배출 (gCO₂/km)")
    ax.legend(loc="lower right", frameon=False, fontsize=5.0, bbox_to_anchor=(1.02, 0.0))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "print_fig3_break_even.png", dpi=DPI, bbox_inches="tight", pad_inches=0.03)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    print("저장:", FIG)
