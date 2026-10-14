"""
03_carbon.py
핵심 지역(강건성 점검을 통과한 17곳)의 버스 서비스를 늘렸을 때
승용차 통근 감소와 온실가스 변화를 '근거 기반 시나리오'로 추정한다.

[1단계] 승용차 → 버스 전환 통근자
  버스 통근자 증가 = 현재 버스(시내·시외) 통근자 * 서비스 증가율 * 서비스 탄력성
      버스 차량·km 탄력성: 단기 0.4, 장기 0.7 (Paulley 외 2006, Transport Policy 13(4) 표 4: 0.38/0.66)
  그중 원래 승용차 통근자 비율: 30% / 50% (해외 사례 44~66%, 도시·철도 중심이라 낮춰 잡음)

[2단계] 승용차 배출 감소
  편도거리 = 승용차 평균 통근시간 / 60 * 30km/h, 왕복 * 연 250일
  승용차 173 gCO2/인·km (한국철도기술연구원 2010, 권영민 외 2020 재인용)

[3단계] 버스를 더 굴리면서 생기는 배출 (상쇄분)
  대형버스 약 723 gCO2/km (국립환경과학원 NIER-06 시험, 서울시 자료)
  -> 버스 1대가 평균 723/173 ≈ 4.2명 이상을 태워야 승용차보다 배출이 적다(손익분기 재차인원).
  새로 늘린 버스의 평균 재차인원을 2/4/8명으로 바꿔 가며 순감축량을 본다.
"""
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TAB = ROOT / "output" / "tables"

EF_CAR = 173.0          # gCO2/인·km
EF_BUS_VEH = 723.0      # gCO2/대·km (대형 경유버스)
SPEED = 30.0            # km/h, 승용차 통근 평균속도 가정
WORKDAYS = 250
BREAK_EVEN_OCC = EF_BUS_VEH / EF_CAR

SERVICE_UP = {"배차 1.5배": 0.5, "배차 2배": 1.0}
ELASTICITY = {"단기 0.4": 0.4, "장기 0.7": 0.7}
FROM_CAR = {"30%": 0.3, "50%": 0.5}
OCCUPANCY = {"2명": 2.0, "4명": 4.0, "8명": 8.0}     # 새로 늘린 버스의 평균 재차인원


def scenario(d: pd.DataFrame, group: str) -> pd.DataFrame:
    km_oneway = d["time_car"] / 60 * SPEED
    # 버스 서비스를 늘리는 시나리오이므로 기준은 버스(시내·시외) 통근자만 쓴다 (전철·기차 제외)
    n_transit = d["n_bus"] + d["n_intercity_bus"]
    rows = []
    for (su, up), (el, e), (fc, f), (oc, occ) in product(
            SERVICE_UP.items(), ELASTICITY.items(), FROM_CAR.items(), OCCUPANCY.items()):
        new_riders = n_transit * up * e
        car_to_bus = new_riders * f
        car_pkm = car_to_bus * 2 * WORKDAYS * km_oneway
        gross = (car_pkm * EF_CAR / 1e6).sum()                      # 승용차 감소분 tCO2
        # 새 승객 전체(승용차 출신 + 그 밖)를 태우려고 늘린 버스 주행거리
        rider_pkm = (new_riders * 2 * WORKDAYS * km_oneway).sum()
        bus_vkm = rider_pkm / occ
        offset = bus_vkm * EF_BUS_VEH / 1e6
        rows.append({
            "대상": group, "서비스증가": su, "탄력성": el, "승용차출신비율": fc, "증차버스_재차인원": oc,
            "버스로_옮긴_승용차통근자": car_to_bus.sum(),
            "승용차통근자_대비_전환율": car_to_bus.sum() / d["n_car"].sum(),
            "승용차_감축_t": gross, "버스_추가배출_t": offset, "순감축_t": gross - offset,
        })
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv(PROC / "sgg_2020_analyzed.csv")
    core = d[d["core"]]
    quad = d[d["quadrant"] == "강제된 의존 의심"]

    sc = pd.concat([scenario(core, f"핵심 {len(core)}곳"), scenario(quad, f"의심 {len(quad)}곳")])
    sc.to_csv(TAB / "carbon_scenarios.csv", index=False, encoding="utf-8-sig")
    print(f"손익분기 재차인원: 버스 1대당 {BREAK_EVEN_OCC:.1f}명")
    # 새 승객 중 일부만 승용차 출신이므로, 증차 차량이 순감축을 내려면
    #   차량 배출(g/km) <= 새 승객 재차인원 * 승용차출신비율 * 173
    cond = pd.DataFrame([{"새승객_재차인원": o, "승용차출신비율": f,
                          "순감축_조건_차량배출_g/km_이하": o * f * EF_CAR,
                          "대형경유버스(723)_순감축여부": o * f * EF_CAR > EF_BUS_VEH}
                         for o in [2, 4, 8, 12] for f in [0.3, 0.5]])
    print(cond.to_string(index=False))
    cond.to_csv(TAB / "carbon_break_even.csv", index=False, encoding="utf-8-sig")

    key = sc[(sc["대상"].str.startswith("핵심")) & (sc["승용차출신비율"] == "50%")]
    print(f"\n핵심 {len(core)}곳, 승용차 출신 50% 가정")
    print(key[["서비스증가", "탄력성", "증차버스_재차인원", "버스로_옮긴_승용차통근자",
               "승용차통근자_대비_전환율", "승용차_감축_t", "버스_추가배출_t", "순감축_t"]]
          .round(3).to_string(index=False))

    # 현재 상태 비교표 (핵심 / 의심 / 나머지)
    km = d["time_car"] / 60 * SPEED
    d["t_per_driver"] = 2 * WORKDAYS * km * EF_CAR / 1e6
    d["group"] = "나머지"
    d.loc[d["quadrant"] == "강제된 의존 의심", "group"] = "의심(사분면)"
    d.loc[d["core"], "group"] = "핵심"

    def summarize(x):
        c = x["commuters"].sum()
        return pd.Series({
            "시군구수": len(x), "통근자": c, "승용차통근자": x["n_car"].sum(),
            "승용차비율": x["n_car"].sum() / c,
            "대중교통비율": (x["transit_share"] * x["commuters"]).sum() / c,
            "승용차_평균통근시간": (x["time_car"] * x["n_car"]).sum() / x["n_car"].sum(),
            "대중교통_평균통근시간": (x["time_transit"] * x["commuters"]).sum() / c,
            "통근시간차이_분_평균": x["time_diff"].mean(),
            "1인당근로소득_평균": x["income_per_worker"].mean(),
            "운전자1인당_연간통근배출_t": (x["t_per_driver"] * x["n_car"]).sum() / x["n_car"].sum(),
            "전국_승용차통근배출_비중": (x["t_per_driver"] * x["n_car"]).sum() / (d["t_per_driver"] * d["n_car"]).sum(),
        })
    comp = d.groupby("group").apply(summarize, include_groups=False)
    print("\n집단 비교")
    print(comp.round(3).to_string())
    comp.to_csv(TAB / "target_vs_rest.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
