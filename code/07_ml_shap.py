"""
07_ml_shap.py
설명 가능한 머신러닝: 무엇이 시군구의 승용차 통근 비율을 끌어올리는가?

모델  : 랜덤포레스트 회귀 (scikit-learn)
검증  : 5겹 교차검증 R², 같은 변수의 선형회귀와 비교, 시도 단위로 묶은 교차검증(공간 누수 점검)
해석  : SHAP (요인별 기여도), 소득 x 통근시간 격차 상호작용
주의  : 관계(연관)를 설명하는 모델이며 인과 효과를 뜻하지 않는다.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from shapely.geometry import Point
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "output" / "figures"
TAB = ROOT / "output" / "tables"
SEED = 42

SEOUL_CITY_HALL = Point(126.9780, 37.5665)

FEATURES = {
    "log_income": "1인당 근로소득",
    "time_diff": "통근시간 격차",
    "has_rail": "철도역 유무",
    "log_density": "통근자 밀도",
    "dist_seoul_km": "서울까지 거리",
    "shuttle_share": "회사 통근버스 비율",
}
# 버스정류장 밀도는 통근자 밀도와 순위상관 0.97로 사실상 같은 정보이고 15개 시군이 결측이라
# 본 모델에서는 빼고, 아래 강건성 점검에서만 넣어 본다.
ROBUST_SPECS = {
    "본 모델": list(FEATURES),
    "정류장 밀도 추가": list(FEATURES) + ["bus_stops_per_km2"],
    "통근차량 비율 제외": [c for c in FEATURES if c != "shuttle_share"],
    "밀도·통근차량 제외": [c for c in FEATURES if c not in ("shuttle_share", "log_density")],
}


def build():
    g = gpd.read_file(PROC / "sgg_2020_analyzed.geojson")
    gm = g.to_crs(5179)
    seoul = gpd.GeoSeries([SEOUL_CITY_HALL], crs=4326).to_crs(5179).iloc[0]
    g["dist_seoul_km"] = gm.geometry.representative_point().distance(seoul) / 1000
    g["log_density"] = np.log(g["commuters"] / g["area_km2"])
    g["shuttle_share"] = g["n_shuttle"] / g["commuters"]
    g["sido"] = g["key"].str.split("|").str[0]
    return g


def main():
    g = build()
    X = g[list(FEATURES)].astype(float)
    y = g["car_share"] * 100                         # % 단위

    rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)
    lin = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression())
    kf = KFold(5, shuffle=True, random_state=SEED)
    gkf = GroupKFold(n_splits=5)

    res = {
        "랜덤포레스트 R²(5겹)": cross_val_score(rf, X, y, cv=kf, scoring="r2"),
        "선형회귀 R²(5겹)": cross_val_score(lin, X, y, cv=kf, scoring="r2"),
        "랜덤포레스트 R²(시도별 묶음 5겹)": cross_val_score(rf, X, y, cv=gkf, groups=g["sido"], scoring="r2"),
    }
    perf = pd.DataFrame({k: [v.mean(), v.std()] for k, v in res.items()}, index=["평균", "표준편차"]).T
    print(perf.round(3).to_string())
    perf.to_csv(TAB / "ml_performance.csv", encoding="utf-8-sig")

    rf.fit(X, y)
    expl = shap.TreeExplainer(rf)
    sv = expl.shap_values(X)
    imp = pd.Series(np.abs(sv).mean(axis=0), index=[FEATURES[c] for c in X.columns]).sort_values(ascending=False)
    print("\nSHAP 평균 기여도(%p):")
    print(imp.round(2).to_string())
    imp.to_csv(TAB / "ml_shap_importance.csv", encoding="utf-8-sig", header=["mean_abs_shap_pp"])

    # 방향 확인: 각 요인 값과 SHAP 값의 순위상관 (+면 값이 클수록 승용차 비율을 올림)
    direction = {FEATURES[c]: pd.Series(X[c]).corr(pd.Series(sv[:, i]), method="spearman")
                 for i, c in enumerate(X.columns)}
    print("\n방향(요인 값 vs SHAP 순위상관):", {k: round(v, 2) for k, v in direction.items()})

    # 핵심 지역에서 승용차 비율을 끌어올린 요인 (핵심 17곳 평균 SHAP)
    core = g["core"].astype(bool).values
    core_sv = pd.Series(sv[core].mean(axis=0), index=[FEATURES[c] for c in X.columns]).sort_values(ascending=False)
    print("\n핵심 17곳 평균 SHAP(%p, +는 승용차 비율을 올린 방향):")
    print(core_sv.round(2).to_string())
    core_sv.to_csv(TAB / "ml_shap_core.csv", encoding="utf-8-sig", header=["mean_shap_pp"])

    # ---------------- 그림 ----------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.2, 1]})
    Xl = X.rename(columns=FEATURES)
    plt.sca(axes[0])
    shap.summary_plot(sv, Xl, show=False, plot_size=None, color_bar=True, max_display=7,
                      color_bar_label="요인 값")
    for a in fig.axes:
        if a is not axes[0] and a is not axes[1]:          # 색 막대
            a.set_yticklabels(["낮음", "높음"], fontsize=8)
            a.yaxis.label.set_size(9)
            a.yaxis.label.set_rotation(90)
    axes[0].tick_params(axis="y", labelsize=10)
    axes[0].tick_params(axis="x", labelsize=9)
    axes[0].set_title("요인별 기여 (점 = 시군구, 빨강 = 요인 값이 높음)", fontsize=10)
    axes[0].set_xlabel("승용차 통근 비율에 대한 기여 (%p)", fontsize=9)

    ax = axes[1]
    c = ["#c0392b" if v > 0 else "#4393c3" for v in core_sv.values]
    ax.barh(core_sv.index[::-1], core_sv.values[::-1], color=c[::-1])
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("핵심 17곳 평균 기여 (%p)")
    ax.set_title("핵심 17곳: 무엇이 승용차 의존을 끌어올렸나", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    r2 = perf.loc["랜덤포레스트 R²(5겹)", "평균"]
    fig.suptitle(f"랜덤포레스트 + SHAP: 승용차 통근 비율의 요인 (교차검증 R² = {r2:.2f})", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_shap.png", dpi=200)
    print("\n저장:", FIG / "fig4_shap.png")

    # ---------------- 강건성: 변수 구성을 바꿔도 결론이 같은가 ----------------
    rows = []
    for name, cols in ROBUST_SPECS.items():
        Xs = g[cols].astype(float)
        m = RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)
        r2s = cross_val_score(m, Xs, y, cv=kf, scoring="r2").mean()
        m.fit(Xs, y)
        s_ = shap.TreeExplainer(m).shap_values(Xs)
        row = {"구성": name, "R2(5겹)": r2s}
        for i, c in enumerate(cols):
            row[f"핵심17_{c}"] = s_[core, i].mean()
        rows.append(row)
    rob = pd.DataFrame(rows)
    print("\n강건성(핵심 17곳 평균 SHAP, %p)")
    print(rob.round(2).to_string(index=False))
    rob.to_csv(TAB / "ml_robustness.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
