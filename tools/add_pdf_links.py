"""
add_pdf_links.py
한글에서 저장한 보고서 PDF를 마무리한다.
  - 끝에 남은 빈 쪽(쪽 번호와 머리글 로고만 있는 쪽)을 지운다.
  - 코드 저장소 주소에 클릭 가능한 링크를 건다(이미 있으면 다시 걸지 않음).
fill_hwp.py 실행 뒤 이어서 돌린다.
"""
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "hwp" / "한동훈_분석보고서.pdf"
URL = "https://github.com/donghooon-han/forced-car-dependence"


def is_blank(page, logo_count):
    text = "".join(page.get_text().split()).strip("-0123456789")
    return not text and len(page.get_images()) <= logo_count


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = pymupdf.open(PDF)
    logo_count = min(len(p.get_images()) for p in doc)  # 모든 쪽에 공통인 머리글 로고 수
    removed = 0
    while len(doc) > 1 and is_blank(doc[-1], logo_count):
        doc.delete_page(len(doc) - 1)
        removed += 1
    n = 0
    for page in doc:
        has = {(round(l["from"].x0), round(l["from"].y0)) for l in page.get_links() if l.get("uri") == URL}
        for rect in page.search_for(URL):
            if (round(rect.x0), round(rect.y0)) in has:
                continue
            page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": URL})
            n += 1
    tmp = PDF.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    tmp.replace(PDF)
    print(f"빈 쪽 {removed}개 삭제, 링크 {n}곳 추가:", PDF)


if __name__ == "__main__":
    main()
