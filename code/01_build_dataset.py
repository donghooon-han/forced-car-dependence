"""
01_build_dataset.py
시군구(시·군·자치구) 단위 분석용 데이터셋을 만든다.

입력 (data/raw)
  - KOSIS_통근통학_소요시간_교통수단_시군구_2020.csv  : 인구총조사 2020 표본, 통근·통학 수단 x 소요시간
  - 국세청_시군구별_근로소득_주소지_2020.csv           : 근로소득 연말정산(주소지 기준) 2020
  - 국토부_전국버스정류장위치_20251031.csv             : 전국 버스정류장 좌표 (BIS 연계 지자체만)
  - 국가철도공단_전체도시철도역사정보_20260630.xlsx     : 도시·광역철도 역 좌표
  - boundary/HangJeongDong_ver20201001.geojson         : 행정동 경계 (admdongkor, CC BY 4.0)

출력 (data/processed)
  - sgg_2020.csv     : 시군구별 변수
  - sgg_2020.geojson : 위 변수 + 시군구 경계 (지도용)

분석 단위: 시·군·자치구. 수원시 장안구 같은 '일반구'는 상위 시로 합친다.
"""
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# 시도 정식 명칭 -> 약칭 (국세청 자료가 약칭을 씀)
SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}
DO_SIDO = {"경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"}

# 소요시간 구간 중앙값(분). '120분 이상'은 135분으로 가정한다.
TIME_MID = {"15분 미만": 7.5, "15~30": 22.5, "30~45": 37.5, "45~60": 52.5,
            "60~90": 75.0, "90~120": 105.0, "120분 이상": 135.0}

MODE_COLS = {
    "통근·통학 인구(12세 이상)": "total",
    "걸어서": "walk", "자전거": "bike",
    "승용차,승합차(벤)": "car", "트럭": "truck",
    "시내,좌석,마을버스": "bus", "통근,통학차량": "shuttle",
    "고속,시외버스": "intercity_bus", "전철,지하철": "subway", "기차": "train",
    "택시": "taxi", "기타": "other", "복합수단": "multi",
}


def clean_name(s: str) -> str:
    """'미추홀구(남구)' -> '미추홀구' 처럼 괄호 부분을 지운다."""
    return re.sub(r"\(.*?\)", "", str(s)).strip()


# ---------------------------------------------------------------------------
# 1. 통근 자료 (2020 인구총조사)
# ---------------------------------------------------------------------------
def load_commute(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949", dtype=str)
    df = df.iloc[:, :6]
    df.columns = ["region", "type", "time", "item", "unit", "val"]
    df["val"] = pd.to_numeric(df["val"].str.replace(",", ""), errors="coerce").fillna(0)

    # 지역명은 시도 → 시군구 순서로 나열되어 있다. 같은 이름(중구 등)을 구분하려고 시도를 붙인다.
    sido, parent_si, keys = None, None, []
    for name in df["region"]:
        if name in SIDO_SHORT:
            sido, parent_si = SIDO_SHORT[name], None
            keys.append(None)
            continue
        if sido is None:          # 전국/동부/읍부/면부
            keys.append(None)
            continue
        if sido in DO_SIDO and name.endswith("시"):
            parent_si = name
            keys.append(f"{sido}|{name}")
        elif sido in DO_SIDO and parent_si and name.endswith("구"):
            keys.append(None)     # 일반구: 상위 시 값에 이미 포함되어 있으므로 버린다
        else:
            if not name.endswith("구"):
                parent_si = None
            keys.append(f"{sido}|{name}")
    df["key"] = keys
    df = df.dropna(subset=["key"])
    df["key"] = df["key"].str.replace("세종|세종시", "세종|세종", regex=False)

    work = df[df["type"] == "통근"].copy()   # 통학은 빼고 '통근'만 쓴다
    work["mode"] = work["item"].map(MODE_COLS)
    work = work.dropna(subset=["mode"])

    # (a) 수단별 통근자 수
    tot = work[work["time"] == "계"].pivot_table(index="key", columns="mode", values="val", aggfunc="sum")

    # (b) 수단별 평균 통근시간 (구간 중앙값 가중평균)
    t = work[work["time"].isin(TIME_MID)].copy()
    t["mid"] = t["time"].map(TIME_MID)
    t["w"] = t["val"] * t["mid"]
    g = t.groupby(["key", "mode"])[["w", "val"]].sum()
    avg_t = (g["w"] / g["val"].replace(0, np.nan)).unstack("mode")

    out = pd.DataFrame(index=tot.index)
    out["commuters"] = tot["total"]
    for m in ["walk", "bike", "car", "truck", "bus", "shuttle", "intercity_bus",
              "subway", "train", "taxi", "other", "multi"]:
        out[f"n_{m}"] = tot[m]
    n = out["commuters"]
    out["car_share"] = tot["car"] / n
    out["transit_share"] = (tot["bus"] + tot["intercity_bus"] + tot["subway"] + tot["train"]) / n
    out["multi_share"] = tot["multi"] / n                 # 복합수단(환승 등)
    out["active_share"] = (tot["walk"] + tot["bike"]) / n

    out["time_car"] = avg_t["car"]
    out["time_bus"] = avg_t["bus"]
    # 단일 대중교통수단 평균시간: 버스·전철·기차·시외버스 이용자 가중평균
    tr = t[t["mode"].isin(["bus", "intercity_bus", "subway", "train"])].groupby("key")[["w", "val"]].sum()
    out["time_transit"] = tr["w"] / tr["val"].replace(0, np.nan)
    out["time_ratio_transit_car"] = out["time_transit"] / out["time_car"]
    return out.reset_index()


# ---------------------------------------------------------------------------
# 2. 소득 (국세청 근로소득, 주소지 기준 2020)
# ---------------------------------------------------------------------------
def load_income(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="cp949", header=None, dtype=str).iloc[3:]
    raw = raw[[0, 1, 4, 5]]
    raw.columns = ["sido", "name", "n_workers", "pay_mil"]
    raw["name"] = raw["name"].map(clean_name)
    raw.loc[(raw["sido"] == "세종") & (raw["name"] == "소계"), "name"] = "세종"
    raw = raw[raw["name"] != "소계"]
    raw["key"] = raw["sido"] + "|" + raw["name"]
    for c in ["n_workers", "pay_mil"]:
        raw[c] = pd.to_numeric(raw[c].str.replace(",", ""), errors="coerce")
    # 1인당 총급여 (만원)
    raw["income_per_worker"] = raw["pay_mil"] / raw["n_workers"] * 100
    return raw[["key", "n_workers", "income_per_worker"]]


# ---------------------------------------------------------------------------
# 3. 시군구 경계 (행정동 경계를 시군구로 합침)
# ---------------------------------------------------------------------------
def load_boundary(path: Path) -> gpd.GeoDataFrame:
    g = gpd.read_file(path)
    g["sido"] = g["sidonm"].map(SIDO_SHORT)
    tok = g["adm_nm"].str.split().str[1]

    def parent(sido, name, sgg):
        if sido == "세종":
            return "세종", "36110"
        m = re.match(r"^(.+?시)(.+구)$", name)
        if sido in DO_SIDO and m:                      # 수원시장안구 -> 수원시
            return m.group(1), sgg[:4] + "0"
        return name, sgg

    pr = [parent(s, n, c) for s, n, c in zip(g["sido"], tok, g["sgg"])]
    g["name"] = [p[0] for p in pr]
    g["sgg_cd"] = [p[1] for p in pr]
    g["key"] = g["sido"] + "|" + g["name"]
    sgg = g.dissolve(by=["key", "sgg_cd"], as_index=False)[["key", "sgg_cd", "geometry"]]
    sgg = sgg.to_crs(5179)                             # 면적 계산용 (미터 단위)
    sgg["area_km2"] = sgg.area / 1e6
    return sgg


# ---------------------------------------------------------------------------
# 4. 대중교통 공급 (버스정류장, 철도역) - 점을 시군구 경계에 넣어 센다
# ---------------------------------------------------------------------------
def count_points(points: gpd.GeoDataFrame, sgg: gpd.GeoDataFrame, col: str) -> pd.Series:
    j = gpd.sjoin(points.to_crs(5179), sgg[["key", "geometry"]], predicate="within", how="inner")
    return j.groupby("key").size().rename(col)


def load_bus(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():  # 저장소에는 용량 때문에 같은 이름의 .zip으로 들어 있다
        path = path.with_suffix(".zip")
    b = pd.read_csv(path, encoding="cp949", dtype=str)
    b = b.rename(columns={"위도": "lat", "경도": "lon", "도시명": "city"})
    b["lat"] = pd.to_numeric(b["lat"], errors="coerce")
    b["lon"] = pd.to_numeric(b["lon"], errors="coerce")
    b = b.dropna(subset=["lat", "lon"]).drop_duplicates(subset=["lat", "lon"])
    return gpd.GeoDataFrame(b, geometry=gpd.points_from_xy(b["lon"], b["lat"]), crs=4326)


def bus_file_counts(bus: gpd.GeoDataFrame) -> pd.Series:
    """원본 파일의 '도시명'(예: '강원특별자치도 강릉시')별 정류장 수. 광역시는 시 전체로만 나온다."""
    def to_key(city):
        parts = str(city).split()
        if len(parts) != 2:
            return None
        sido = parts[0].replace("강원특별자치도", "강원도").replace("전북특별자치도", "전라북도")
        return f"{SIDO_SHORT.get(sido, sido)}|{parts[1]}"
    return bus["city"].map(to_key).value_counts()


def load_rail(path: Path) -> gpd.GeoDataFrame:
    r = pd.read_excel(path, dtype=str)
    r["lat"] = pd.to_numeric(r["역위도"], errors="coerce")
    r["lon"] = pd.to_numeric(r["역경도"], errors="coerce")
    r = r.dropna(subset=["lat", "lon"])
    # 환승역은 노선마다 한 줄씩 있으므로 역 이름+대략 위치로 한 번만 센다
    r["pos"] = r["lat"].round(3).astype(str) + "," + r["lon"].round(3).astype(str)
    r = r.drop_duplicates(subset=["역사명", "pos"])
    return gpd.GeoDataFrame(r, geometry=gpd.points_from_xy(r["lon"], r["lat"]), crs=4326)


def main():
    commute = load_commute(RAW / "KOSIS_통근통학_소요시간_교통수단_시군구_2020.csv")
    income = load_income(RAW / "국세청_시군구별_근로소득_주소지_2020.csv")
    sgg = load_boundary(RAW / "boundary" / "HangJeongDong_ver20201001.geojson")
    bus = load_bus(RAW / "국토부_전국버스정류장위치_20251031.csv")
    rail = load_rail(RAW / "국가철도공단_전체도시철도역사정보_20260630.xlsx")

    n_bus = count_points(bus, sgg, "bus_stops")
    n_rail = count_points(rail, sgg, "rail_stations")

    df = sgg.merge(commute, on="key", how="left").merge(income, on="key", how="left")
    df = df.merge(n_bus, left_on="key", right_index=True, how="left")
    df = df.merge(n_rail, left_on="key", right_index=True, how="left")
    df["rail_stations"] = df["rail_stations"].fillna(0)
    # 버스정류장 자료는 BIS 연계 지자체만 제대로 들어 있다.
    # 도 지역 시·군 중 원본 파일에 150개 미만으로 올라온 곳(또는 아예 없는 곳)은
    # 면적이 아주 작아 밀도가 정상(1개/km² 이상)인 경우를 빼고 '자료 부족'으로 보고 결측 처리한다.
    file_n = bus_file_counts(bus)
    sido_of = df["key"].str.split("|").str[0]
    raw_n = df["key"].map(file_n).fillna(0)
    dens = df["bus_stops"] / df["area_km2"]
    df["bus_low_coverage"] = (sido_of.isin(DO_SIDO) & (raw_n < 150) & ~(dens >= 1.0)) | df["bus_stops"].isna()
    print("버스 자료 부족으로 결측 처리:", df.loc[df["bus_low_coverage"], "key"].tolist())
    df.loc[df["bus_low_coverage"], "bus_stops"] = np.nan

    df["bus_stops_per_km2"] = df["bus_stops"] / df["area_km2"]
    df["bus_stops_per_1k_commuters"] = df["bus_stops"] / df["commuters"] * 1000
    df["has_rail"] = (df["rail_stations"] > 0).astype(int)

    # 결합 점검
    print("시군구 수:", len(df))
    for c in ["commuters", "income_per_worker", "bus_stops"]:
        miss = df[df[c].isna()]["key"].tolist()
        print(f"{c} 결측 {len(miss)}개:", miss)
    unmatched_commute = set(commute["key"]) - set(df["key"])
    unmatched_income = set(income["key"]) - set(df["key"])
    print("경계와 못 맞춘 통근 key:", sorted(unmatched_commute))
    print("경계와 못 맞춘 소득 key:", sorted(unmatched_income))

    df.drop(columns="geometry").to_csv(OUT / "sgg_2020.csv", index=False, encoding="utf-8-sig")
    df.to_crs(4326).to_file(OUT / "sgg_2020.geojson", driver="GeoJSON")
    print("저장 완료:", OUT)


if __name__ == "__main__":
    main()
