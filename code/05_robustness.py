"""
05_robustness.py
레드팀 점검: 결과가 가정·지표 선택에 따라 얼마나 흔들리는지 본다.

A. 통근시간 비율의 분모 효과: 승용차 통근이 짧은 곳은 비율이 저절로 커지는가?
B. 기준 바꾸기: 중앙값 대신 삼분위, 지수 가중치 변경 시 상위 지역이 얼마나 겹치는가?
C. 산업단지 통근: 의심 지역의 통근차량(회사 버스) 비율
D. 소득 지표: 근로소득 신고자 비율(통근자 대비)이 낮은 곳 = 소득 지표 대표성 문제
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"


def z(s):
    return (s - s.mean()) / s.std()


def main():
    d = pd.read_csv(PROC / "sgg_2020_analyzed.csv")
    tgt = d["quadrant"] == "강제된 의존 의심"
    base_top = set(d.nsmallest(31, "fcd_rank")["key"])

    print("A. 분모 효과")
    print("  승용차 통근시간 vs 시간비율 (스피어만):",
          round(d["time_car"].corr(d["time_ratio_transit_car"], method="spearman"), 3))
    print("  대중교통 통근시간 vs 시간비율:",
          round(d["time_transit"].corr(d["time_ratio_transit_car"], method="spearman"), 3))
    d["time_diff"] = d["time_transit"] - d["time_car"]      # 분 단위 차이(대안 지표)
    alt = z(d["car_share"]) + z(d["time_diff"]) - z(d["log_income"])
    top_alt = set(d.loc[alt.nlargest(31).index, "key"])
    print(f"  시간 '비율' 대신 '차이(분)'로 바꿨을 때 상위31 겹침: {len(base_top & top_alt)}/31")

    print("\nB. 기준·가중치 민감도")
    for name, w in {"자가용x2": (2, 1, 1), "격차x2": (1, 2, 1), "소득x2": (1, 1, 2),
                    "소득 제외": (1, 1, 0)}.items():
        s = w[0] * d["z_car"] + w[1] * d["z_gap"] - w[2] * d["z_inc"]
        top = set(d.loc[s.nlargest(31).index, "key"])
        print(f"  {name}: 상위31 겹침 {len(base_top & top)}/31")
    t1 = d["income_per_worker"] < d["income_per_worker"].quantile(1/3)
    t2 = d["car_share"] > d["car_share"].quantile(2/3)
    t3 = d["time_ratio_transit_car"] > d["time_ratio_transit_car"].quantile(2/3)
    strict = set(d.loc[t1 & t2 & t3, "key"])
    print(f"  삼분위 기준(더 엄격): {len(strict)}곳, 그중 기존 31곳에 포함 {len(strict & set(d.loc[tgt,'key']))}곳",
          sorted(strict))
    print(f"  사분면 31곳 vs 지수 상위31 겹침: {len(set(d.loc[tgt,'key']) & base_top)}/31")

    print("\nC. 통근차량(회사·학교 버스) 비율")
    d["shuttle_share"] = d["n_shuttle"] / d["commuters"]
    print(d.groupby("quadrant")["shuttle_share"].median().round(3).to_dict())
    print(d[tgt].nlargest(6, "shuttle_share")[["key", "shuttle_share", "car_share"]].round(3).to_string(index=False))

    print("\nD. 소득 지표 대표성: 근로소득 신고자 / 통근자")
    d["wage_cov"] = d["n_workers"] / d["commuters"]
    print(d.groupby("quadrant")["wage_cov"].median().round(3).to_dict())

    print("\nE. 농촌 고령 지역: 걷기 통근 비율 (자가용이 낮은 이유가 '차가 없어서'일 수도)")
    d["walk_share"] = d["n_walk"] / d["commuters"]
    print(d.groupby("quadrant")["walk_share"].median().round(3).to_dict())


def robust_core():
    """여러 정의(사분면, 지수 4종, 시간차이 지수)에서 반복해서 뽑히는 '강건한 핵심 지역'."""
    d = pd.read_csv(PROC / "sgg_2020_analyzed.csv")
    d["time_diff"] = d["time_transit"] - d["time_car"]
    specs = {
        "사분면(중앙값)": set(d.loc[d["quadrant"] == "강제된 의존 의심", "key"]),
    }
    variants = {
        "지수(기본)": d["z_car"] + d["z_gap"] - d["z_inc"],
        "지수(시간차이)": d["z_car"] + z(d["time_diff"]) - d["z_inc"],
        "지수(자가용x2)": 2 * d["z_car"] + d["z_gap"] - d["z_inc"],
        "지수(격차x2)": d["z_car"] + 2 * d["z_gap"] - d["z_inc"],
        "지수(소득x2)": d["z_car"] + d["z_gap"] - 2 * d["z_inc"],
    }
    for k, s in variants.items():
        specs[k] = set(d.loc[s.nlargest(31).index, "key"])
    cnt = pd.Series(0, index=d["key"])
    for s in specs.values():
        cnt[list(s)] += 1
    core = cnt[cnt >= 5].sort_values(ascending=False)
    print(f"\nF. 6개 정의 중 5개 이상에서 뽑힌 핵심 지역: {len(core)}곳")
    print(core.to_string())
    out = d.set_index("key").loc[core.index, ["car_share", "transit_share", "time_car", "time_transit",
                                              "income_per_worker", "commuters", "n_car"]]
    out["선정횟수"] = core
    out.to_csv(TAB / "robust_core_regions.csv", encoding="utf-8-sig")
    print("핵심 지역 승용차 통근자 합:", int(out["n_car"].sum()))


if __name__ == "__main__":
    main()
    robust_core()
