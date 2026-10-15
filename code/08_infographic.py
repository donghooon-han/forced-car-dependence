"""
08_infographic.py
보고서 '분석결과 이미지(필수)' 칸에 넣을 한 장 요약 인포그래픽.
지도(핵심 17곳) + 핵심 수치 4개 + 정책 제안 4개. 수치는 모두 앞 단계 결과 파일에서 읽는다.
보고서 칸 폭(약 11.6cm)에 맞춰 실제 인쇄 크기(5.4 x 3.9인치)로 그려 글씨가 작아지지 않게 한다.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"

RED, BLUE, DARK = "#c0392b", "#2e6da4", "#1f2d3d"


def card(fig, x, y, w, h, big, small, color):
    ax = fig.add_axes([x, y, w, h])
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((0.01, 0.03), 0.98, 0.94, boxstyle="round,pad=0.01,rounding_size=0.06",
                                fc="#f5f5f5", ec="#dddddd", lw=0.6, transform=ax.transAxes))
    ax.text(0.07, 0.73, big, fontsize=14, fontweight="bold", color=color, va="center", transform=ax.transAxes)
    ax.text(0.07, 0.32, small, fontsize=6.8, color=DARK, va="center", transform=ax.transAxes, linespacing=1.4)


def main():
    g = gpd.read_file(PROC / "sgg_2020_analyzed.geojson").to_crs(5179)
    comp = pd.read_csv(TAB / "target_vs_rest.csv", index_col=0)
    trend = pd.read_csv(TAB / "trend_2015_2020.csv", index_col=0)
    shap_core = pd.read_csv(TAB / "ml_shap_core.csv", index_col=0)["mean_shap_pp"]

    core, rest = comp.loc["핵심"], comp.loc["나머지(212)"]
    tr = trend.loc["핵심 지역"]
    inc = shap_core.filter(like="근로소득").iloc[0]
    struct = shap_core[shap_core > 0].sum()

    fig = plt.figure(figsize=(5.4, 3.9))
    fig.text(0.03, 0.945, "한눈에 보는 결과 ｜ 버스가 없어서 차를 산다", fontsize=11, fontweight="bold", color=DARK)
    fig.text(0.03, 0.895, "전국 229개 시군구 · 2020 인구주택총조사 통근 자료 · '강제된 자동차 의존' 핵심 17곳",
             fontsize=6.3, color="#555555")

    ax = fig.add_axes([0.0, 0.25, 0.36, 0.62])
    xmin, ymin, xmax, ymax = g[g["key"] != "경북|울릉군"].total_bounds
    g.plot(ax=ax, color="#e6e6e6", edgecolor="white", linewidth=0.15)
    g[g["core"]].plot(ax=ax, color=RED, edgecolor="white", linewidth=0.2)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_axis_off()
    ax.text(0.5, -0.02, "빨강: 핵심 17곳\n수도권 북·동부 외곽, 충북 중부 등", fontsize=6.3, ha="center", va="top",
            color=DARK, transform=ax.transAxes, linespacing=1.35)

    x0, w, h = 0.38, 0.295, 0.355
    card(fig, x0, 0.53, w, h, f"{core['승용차비율']*100:.1f}%",
         f"핵심 17곳 승용차 통근\n(나머지 {rest['승용차비율']*100:.1f}%)\n"
         f"대중교통 {core['대중교통비율']*100:.1f}% vs {rest['대중교통비율']*100:.1f}%", RED)
    card(fig, x0 + w + 0.015, 0.53, w, h, f"+{tr['승용차_변화_%p(중앙값)']:.1f}%p",
         "2015→2020 승용차 비율\n지역별 상승폭 중앙값\n17곳 모두 상승", RED)
    card(fig, x0, 0.16, w, h, f"소득 {inc:+.1f}%p",
         f"모형 예측 기여도(SHAP)\n소득은 예측을 낮추고\n지역 여건이 +{struct:.1f}%p", BLUE)
    card(fig, x0 + w + 0.015, 0.16, w, h, "8.4명",
         "늘린 버스 평균 재차인원\n손익분기(새 승객 중\n원래 운전자 50% 가정)", BLUE)

    ax = fig.add_axes([0.03, 0.015, 0.94, 0.12])
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((0, 0.05), 1, 0.9, boxstyle="round,pad=0.005,rounding_size=0.05",
                                fc=DARK, ec="none", transform=ax.transAxes))
    ax.text(0.015, 0.5, "정책\n제안", fontsize=7.5, fontweight="bold", color="white", va="center",
            transform=ax.transAxes)
    props = ["① 투자·보조금에\n의존 지수 반영", "② 여건별 수단 선택\n(셔틀·DRT·역 연계)",
             "③ 최소 서비스 보장 후\n탄소 점검으로 수단 선택", "④ 2025 센서스로\n지수 갱신·점검"]
    for i, t in enumerate(props):
        ax.text(0.10 + i * 0.225, 0.5, t, fontsize=6.6, color="white", va="center", transform=ax.transAxes,
                linespacing=1.35)
    fig.savefig(FIG / "fig5_infographic.png", dpi=400)
    print("저장:", FIG / "fig5_infographic.png")


if __name__ == "__main__":
    main()
