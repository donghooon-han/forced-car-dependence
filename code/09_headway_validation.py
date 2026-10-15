"""
09_headway_validation.py
공급 측 검증: 한국교통안전공단 대중교통현황조사의 시군별 버스 배차간격으로
'강제된 의존' 결과(통근 행태 기반)가 공급 자료로도 확인되는지 본다.

자료: data/raw/TS_경기_시군별_배차간격_2018_2019.json
  - 공단 '대중교통 운행지표 > 배차간격(요일별)'을 시군구 단위로 조회해 옮겨 적은 값(2026-10-15)
  - 시군구 단위 지표는 수도권·광역시만 공개되어 경기도 31개 시군만 쓸 수 있다
  - 2020~2022년은 값이 비어 있어 코로나 직전인 2018·2019년을 쓴다
  - 두 해의 수준 차이가 커서(집계 방식 변화로 보임) 연도별로 따로 비교한다
평일(월~금) 평균 배차간격(분)을 쓰고, 0 또는 빈 값은 결측 처리한다.
도시·농촌 차이가 섞일 수 있으므로 통근자 밀도(로그)를 통제한 편순위상관도 함께 낸다.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "TS_경기_시군별_배차간격_2018_2019.json"
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"


def load_headway() -> pd.DataFrame:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    rows = []
    for k, v in raw.items():
        if k.startswith("_") or v == "NA":
            continue
        name, yr = k.split("|")
        try:
            weekday = [float(a) for a in v.split()[1:6]]
        except ValueError:
            continue
        m = float(np.mean(weekday))
        if m > 0:
            rows.append({"name": name, "year": int(yr), "headway_weekday": m})
    return pd.DataFrame(rows).pivot(index="name", columns="year", values="headway_weekday")


def partial_spearman(x, y, z):
    """z(통제변수)의 순위를 뺀 뒤 x·y 순위 잔차끼리의 상관"""
    rx, ry, rz = (pd.Series(v).rank().to_numpy() for v in (x, y, z))
    A = np.column_stack([np.ones_like(rz), rz])
    ex = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ey = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def main():
    if not RAW.exists():
        # 공단 저작권정책상 조회값을 저장소에 다시 올리지 않았다. README '데이터 이용조건' 참고
        print(f"[건너뜀] {RAW.name} 이 없습니다. README의 '배차간격 자료 만들기'를 따라 만든 뒤 다시 실행하세요.")
        return
    h = load_headway()
    d = pd.read_csv(PROC / "sgg_2020_analyzed.csv")
    d = d[d["key"].str.startswith("경기|")].copy()
    d["name"] = d["key"].str.split("|").str[1]
    d["log_density"] = np.log(d["commuters"] / d["area_km2"])
    m = d.set_index("name").join(h)

    rows = []
    for y in [2018, 2019]:
        x = m.dropna(subset=[y])
        rows.append({
            "연도": y, "시군 수": len(x),
            "핵심 지역 중앙값(분)": x.loc[x["core"], y].median(),
            "핵심 지역 수": int(x["core"].sum()),
            "나머지 중앙값(분)": x.loc[~x["core"], y].median(),
            "순위상관_승용차비율": x[y].corr(x["car_share"], method="spearman"),
            "순위상관_대중교통비율": x[y].corr(x["transit_share"], method="spearman"),
            "순위상관_의존지수": x[y].corr(x["fcd_index"], method="spearman"),
            "편순위상관_승용차비율_밀도통제": partial_spearman(x[y], x["car_share"], x["log_density"]),
        })
    res = pd.DataFrame(rows)
    print(res.round(2).to_string(index=False))
    res.to_csv(TAB / "headway_validation.csv", index=False, encoding="utf-8-sig")
    m[[2018, 2019, "core", "car_share", "transit_share", "fcd_index"]].sort_values(2018, ascending=False) \
        .to_csv(TAB / "headway_gyeonggi.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
