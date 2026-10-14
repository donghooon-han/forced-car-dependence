"""
04_trend.py
2015 → 2020 승용차·대중교통 통근 비율 변화를 비교한다.
강제된 의존 의심 지역에서 자가용 의존이 더 굳어지고 있는지(고착, lock-in) 확인하기 위함.
"""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"

# 01_build_dataset.py 의 지역 key 만드는 규칙을 그대로 쓴다
spec = importlib.util.spec_from_file_location("b", ROOT / "code" / "01_build_dataset.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

# 2015년 표는 수단 이름이 2020년과 다르다
MODE_2015 = {
    "통근·통학 인구(12세 이상)": "total",
    "승용차 소형 승합차": "car",
    "시내·좌석·마을 버스": "bus", "고속 시외 버스": "intercity_bus",
    "전철 지하철": "subway", "기차": "train",
}
RENAME_2015 = {"인천|남구": "인천|미추홀구"}   # 2018년 명칭 변경


def shares(path: Path, mode_map: dict) -> pd.DataFrame:
    b.MODE_COLS = {**mode_map}
    df = pd.read_csv(path, encoding="cp949", dtype=str).iloc[:, :6]
    df.columns = ["region", "type", "time", "item", "unit", "val"]
    df["val"] = pd.to_numeric(df["val"].str.replace(",", ""), errors="coerce").fillna(0)
    # key 부여: 01 스크립트와 같은 순서 규칙
    sido, parent_si, keys = None, None, []
    for name in df["region"]:
        if name in b.SIDO_SHORT:
            sido, parent_si = b.SIDO_SHORT[name], None
            keys.append(None)
            continue
        if sido is None:
            keys.append(None)
            continue
        if sido in b.DO_SIDO and name.endswith("시"):
            parent_si = name
            keys.append(f"{sido}|{name}")
        elif sido in b.DO_SIDO and parent_si and name.endswith("구"):
            keys.append(None)
        else:
            if not name.endswith("구"):
                parent_si = None
            keys.append(f"{sido}|{name}")
    df["key"] = keys
    df = df.dropna(subset=["key"])
    df["key"] = df["key"].replace({"세종|세종시": "세종|세종", **RENAME_2015})
    w = df[(df["type"] == "통근") & (df["time"] == "계")].copy()
    w["mode"] = w["item"].map(mode_map)
    p = w.dropna(subset=["mode"]).pivot_table(index="key", columns="mode", values="val", aggfunc="sum")
    out = pd.DataFrame(index=p.index)
    out["car_share"] = p["car"] / p["total"]
    out["transit_share"] = (p["bus"] + p["intercity_bus"] + p["subway"] + p["train"]) / p["total"]
    out["commuters"] = p["total"]
    return out


def main():
    s15 = shares(RAW / "KOSIS_통근통학_소요시간_교통수단_시군구_2015.csv", MODE_2015)
    d = pd.read_csv(PROC / "sgg_2020_analyzed.csv").set_index("key")
    d["group"] = d["quadrant"]
    d.loc[d["core"], "group"] = "핵심 지역"
    m = d[["car_share", "transit_share", "commuters", "quadrant", "group", "fcd_index"]].join(
        s15, rsuffix="_2015", how="left")
    print("2015년과 못 맞춘 시군구:", m[m["car_share_2015"].isna()].index.tolist())
    m["d_car"] = (m["car_share"] - m["car_share_2015"]) * 100      # %p
    m["d_transit"] = (m["transit_share"] - m["transit_share_2015"]) * 100

    def wmean(x, col, wcol="commuters"):
        # 각 연도 비율은 그 연도 통근자 수로 가중평균한다
        x = x.dropna(subset=[col])
        return (x[col] * x[wcol]).sum() / x[wcol].sum()

    summ = m.groupby("group").apply(lambda x: pd.Series({
        "시군구수": len(x),
        "승용차비율_2015": wmean(x, "car_share_2015", "commuters_2015") * 100,
        "승용차비율_2020": wmean(x, "car_share") * 100,
        "대중교통비율_2015": wmean(x, "transit_share_2015", "commuters_2015") * 100,
        "대중교통비율_2020": wmean(x, "transit_share") * 100,
        "승용차_변화_%p(중앙값)": x["d_car"].median(),
        "대중교통_변화_%p(중앙값)": x["d_transit"].median(),
        "승용차비율_오른_지역_비율": (x["d_car"] > 0).mean(),
    }), include_groups=False)
    print(summ.round(2).to_string())
    summ.to_csv(TAB / "trend_2015_2020.csv", encoding="utf-8-sig")
    m.reset_index().to_csv(PROC / "sgg_trend_2015_2020.csv", index=False, encoding="utf-8-sig")
    print("\n상관(지수 vs 승용차 변화):", round(m["fcd_index"].corr(m["d_car"], method="spearman"), 3))


if __name__ == "__main__":
    main()
