"""
02_analysis.py
'강제된 자동차 의존' 의심 지역을 찾는다.

1) 강제된 의존 지수(FCD index): 표준점수로 바꾼 세 지표의 합
     + 승용차 통근 비율      (차를 많이 탄다)
     + 통근시간 격차         (대중교통으로 가면 차보다 훨씬 오래 걸린다)
     - 1인당 근로소득        (경제적 여유가 적다)
2) K-평균 군집분석(머신러닝)으로 시군구 유형을 나누고 지수 결과와 비교한다.
3) 표와 그림을 output/ 에 저장한다.

주의: 시군구 평균 자료이므로 '이 지역에서 차를 타는 사람이 저소득층'이라는 뜻이 아니다.
      결과는 '강제된 의존이 의심되는 지역'으로만 해석한다.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "output" / "figures"
TAB = ROOT / "output" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

SEED = 42


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def main():
    src = PROC / "sgg_2020.geojson"
    if not src.exists():  # 저장소에는 용량 때문에 sgg_2020.geojson.zip 으로 들어 있다
        src = f"zip://{(PROC / 'sgg_2020.geojson.zip').as_posix()}!sgg_2020.geojson"
    g = gpd.read_file(src)
    g["sido"] = g["key"].str.split("|").str[0]
    g["name"] = g["key"].str.split("|").str[1]
    g["log_income"] = np.log(g["income_per_worker"])

    # ------------------------------------------------------------------
    # 1. 강제된 의존 지수
    # ------------------------------------------------------------------
    g["z_car"] = zscore(g["car_share"])
    g["z_gap"] = zscore(g["time_ratio_transit_car"])
    g["z_inc"] = zscore(g["log_income"])
    g["fcd_index"] = g["z_car"] + g["z_gap"] - g["z_inc"]
    g["fcd_rank"] = g["fcd_index"].rank(ascending=False).astype(int)

    # 사분면 구분 (중앙값 기준): 경쟁 설명(고소득 교외의 '선택적' 자가용)과 나누기 위함
    lo_inc = g["income_per_worker"] < g["income_per_worker"].median()
    hi_car = g["car_share"] > g["car_share"].median()
    hi_gap = g["time_ratio_transit_car"] > g["time_ratio_transit_car"].median()
    g["quadrant"] = np.select(
        [lo_inc & hi_car & hi_gap, ~lo_inc & hi_car, lo_inc & ~hi_car],
        ["강제된 의존 의심", "선택적 자가용(고소득)", "저소득·저자가용"],
        default="기타",
    )

    # 강건성: 6가지 정의 중 5개 이상에서 반복해 뽑힌 곳을 '핵심 지역'으로 삼는다.
    # (통근시간 '비율'은 승용차 통근이 짧은 곳에서 저절로 커지므로, 분 단위 '차이' 지수도 함께 쓴다)
    g["time_diff"] = g["time_transit"] - g["time_car"]
    g["z_diff"] = zscore(g["time_diff"])
    n_pick = int((g["quadrant"] == "강제된 의존 의심").sum())
    variants = {
        "지수(기본)": g["fcd_index"],
        "지수(시간차이)": g["z_car"] + g["z_diff"] - g["z_inc"],
        "지수(자가용x2)": 2 * g["z_car"] + g["z_gap"] - g["z_inc"],
        "지수(격차x2)": g["z_car"] + 2 * g["z_gap"] - g["z_inc"],
        "지수(소득x2)": g["z_car"] + g["z_gap"] - 2 * g["z_inc"],
    }
    g["n_selected"] = (g["quadrant"] == "강제된 의존 의심").astype(int)
    for s in variants.values():
        g["n_selected"] += s.index.isin(s.nlargest(n_pick).index).astype(int)
    g["core"] = g["n_selected"] >= 5
    print(f"핵심 지역({g['core'].sum()}곳):", g.loc[g["core"], "name"].tolist())

    # ------------------------------------------------------------------
    # 2. K-평균 군집분석
    # ------------------------------------------------------------------
    feats = ["car_share", "transit_share", "time_ratio_transit_car", "log_income"]
    X = StandardScaler().fit_transform(g[feats])
    scores = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=50, random_state=SEED).fit(X)
        scores[k] = silhouette_score(X, km.labels_)
    print("실루엣 점수:", {k: round(v, 3) for k, v in scores.items()})
    # 해석 가능성을 위해 4~6개 중 실루엣 점수가 가장 높은 k를 쓴다
    best_k = max([4, 5, 6], key=lambda k: scores[k])
    km = KMeans(n_clusters=best_k, n_init=50, random_state=SEED).fit(X)
    g["cluster"] = km.labels_

    prof = g.groupby("cluster").agg(
        n=("key", "size"),
        car_share=("car_share", "mean"),
        transit_share=("transit_share", "mean"),
        time_ratio=("time_ratio_transit_car", "mean"),
        income=("income_per_worker", "mean"),
        fcd_index=("fcd_index", "mean"),
        rail_share=("has_rail", "mean"),
        commuters=("commuters", "sum"),
        examples=("name", lambda s: ", ".join(s.head(6))),
    ).sort_values("fcd_index", ascending=False)
    print(f"\n군집 {best_k}개 특성 (지수 높은 순)")
    print(prof.round(2).to_string())

    # ------------------------------------------------------------------
    # 3. 저장
    # ------------------------------------------------------------------
    cols = ["fcd_rank", "key", "fcd_index", "car_share", "transit_share", "time_car",
            "time_transit", "time_ratio_transit_car", "time_diff", "income_per_worker", "rail_stations",
            "bus_stops_per_km2", "commuters", "n_car", "quadrant", "n_selected", "core", "cluster"]
    g.sort_values("fcd_rank")[cols].to_csv(TAB / "fcd_ranking.csv", index=False, encoding="utf-8-sig")
    prof.to_csv(TAB / "cluster_profile.csv", encoding="utf-8-sig")
    g.drop(columns="geometry").to_csv(PROC / "sgg_2020_analyzed.csv", index=False, encoding="utf-8-sig")
    g.to_file(PROC / "sgg_2020_analyzed.geojson", driver="GeoJSON")

    print("\n강제된 의존 지수 상위 20")
    print(g.sort_values("fcd_rank")[cols[:10]].head(20).round(2).to_string(index=False))
    print("\n사분면별 개수:", g["quadrant"].value_counts().to_dict())

    # ------------------------------------------------------------------
    # 4. 그림
    # ------------------------------------------------------------------
    gm = g.to_crs(5179)
    core = gm[gm["core"]]
    # 울릉·독도는 지도 범위에서 빼서 본토를 크게 보이게 한다
    xmin, ymin, xmax, ymax = gm[~gm["name"].isin(["울릉군"])].total_bounds

    def draw_map(ax):
        gm.plot(column="fcd_index", cmap="RdBu_r", legend=True, ax=ax, edgecolor="white",
                linewidth=0.2, vmin=-4, vmax=4,
                legend_kwds={"shrink": 0.45, "label": "강제된 의존 지수 (높을수록 의심)"})
        core.boundary.plot(ax=ax, color="black", linewidth=0.9)
        ax.set_xlim(xmin - 5e3, xmax + 5e3)
        ax.set_ylim(ymin - 5e3, ymax + 5e3)
        ax.set_axis_off()
        ax.set_title(f"강제된 자동차 의존 지수 (검은 테두리: 핵심 {len(core)}곳)", fontsize=11)

    def draw_scatter(ax):
        colors = {"선택적 자가용(고소득)": "#4393c3", "저소득·저자가용": "#bababa",
                  "기타": "#e0e0e0", "강제된 의존 의심": "#d6604d"}
        for q, c in colors.items():
            s = g[g["quadrant"] == q]
            ax.scatter(s["income_per_worker"], s["car_share"] * 100, s=18 + s["time_diff"].clip(lower=0) * 2,
                       c=c, alpha=0.85, edgecolors="white", linewidths=0.5, label=f"{q} ({len(s)})")
        cs = g[g["core"]]
        ax.scatter(cs["income_per_worker"], cs["car_share"] * 100, s=18 + cs["time_diff"].clip(lower=0) * 2,
                   facecolors="none", edgecolors="black", linewidths=1.0, label=f"핵심 지역 ({len(cs)})")
        ax.axvline(g["income_per_worker"].median(), color="grey", lw=0.8, ls="--")
        ax.axhline(g["car_share"].median() * 100, color="grey", lw=0.8, ls="--")
        for _, r in cs.iterrows():
            ax.annotate(r["name"], (r["income_per_worker"], r["car_share"] * 100), fontsize=7,
                        xytext=(3, 2), textcoords="offset points")
        ax.set_xlim(2500, 5200)
        ax.set_xlabel("1인당 근로소득 (만원, 2020)  ※ 5,200만원 초과 일부 구 생략")
        ax.set_ylabel("승용차 통근 비율 (%)")
        ax.set_title("소득 대비 승용차 의존 (점 크기: 대중교통-승용차 통근시간 차이)", fontsize=11)
        ax.legend(loc="lower right", fontsize=7)

    fig, ax = plt.subplots(figsize=(8, 6))
    draw_scatter(ax)
    fig.tight_layout()
    fig.savefig(FIG / "scatter_income_car.png", dpi=200)

    fig, ax = plt.subplots(figsize=(6.5, 8))
    draw_map(ax)
    fig.tight_layout()
    fig.savefig(FIG / "map_fcd_index.png", dpi=200)

    # 보고서용: 지도 + 산점도 한 장
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={"width_ratios": [1, 1.25]})
    draw_map(axes[0])
    draw_scatter(axes[1])
    fig.tight_layout()
    fig.savefig(FIG / "fig1_map_scatter.png", dpi=200)

    # (c) 지도: 군집
    fig, ax = plt.subplots(figsize=(7, 9))
    gm["cluster_label"] = gm["cluster"].astype(str)
    gm.plot(column="cluster_label", categorical=True, cmap="Set2", legend=True, ax=ax,
            edgecolor="white", linewidth=0.2)
    ax.set_axis_off()
    ax.set_title(f"K-평균 군집 결과 (k={best_k})")
    fig.tight_layout()
    fig.savefig(FIG / "map_clusters.png", dpi=200)
    print("\n그림 저장:", FIG)


if __name__ == "__main__":
    main()
