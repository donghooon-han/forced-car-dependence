"""
fill_hwp.py — 공모전 한글 양식(붙임2)에 보고서 원고(report_v4.md)를 채워 넣는다.

방식
 1) 각 칸의 파란 작성 안내문을 찾아 지우고, 원고 문단을 넣는다.
    표·그림 자리에는 임시 표시(§T1§, §F1§)를 넣어 둔다.
 2) 임시 표시를 하나씩 찾아 지우고 그 자리에 표를 만들거나 그림을 넣는다.
 3) 끝의 '작성 시 유의사항' 안내 블록은 지운다.
사용: py tools/fill_hwp.py  (한글 창이 뜨면 보안 확인 창에서 [모두 허용])
"""
import re
from pathlib import Path

import win32com.client as win32
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "output" / "report_v6.md"
TEMPLATE = ROOT / "hwp" / "양식_원본.hwp"
OUT_HWP = ROOT / "hwp" / "한동훈_분석보고서.hwp"
OUT_PDF = ROOT / "hwp" / "한동훈_분석보고서.pdf"

FONT = "맑은 고딕"
BODY_PT = 10
TABLE_PT = 9
CAP_PT = 8.5
IMG_W_MM = 116          # 내용 칸 폭(약 125mm)에 맞춤

# 양식 칸별 안내문을 찾을 때 쓰는 문구 (첫 문구, 끝 문구). 끝 문구가 None이면 칸 끝까지 지운다.
CELLS = {
    "주제": ("핵심 내용을 파악", None),
    "분석 배경 및 목적": ("문제점 등", None),
    "활용 데이터": ("데이터 목록을 아래 표에", "목록 표에 작성)"),
    "분석과정 및 방법": ("구체적인 서술", None),
    "AI 기술 활용": ("AI 도구 및 기술", None),
    "분석 내용 및 결과": ("상세 내용과 도출된", None),
    "정책제안 및 기대효과": ("기대효과 및 시사점", None),
    "분석도구 및 참고문헌": ("웹사이트는 반드시", None),
    "분석결과 이미지 (필수)": ("인포그래픽", None),
}


# --------------------------------------------------------------------------------------
# 원고 읽기
# --------------------------------------------------------------------------------------
def parse_md(path):
    sections, cur = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = []
        elif cur:
            sections[cur].append(line.rstrip())
    return sections


def blocks(lines):
    """문단 / 표 / 그림 / 캡션 / 목록 블록으로 나눈다"""
    out, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                r = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in r):
                    rows.append(r)
                i += 1
            out.append(("table", rows))
            continue
        m = re.match(r"\[그림 (\d+) 삽입: (.+?)(?:\s*\|\s*([\d.]+))?\]", s)
        if m:
            out.append(("fig", (ROOT / m.group(2).strip(), float(m.group(3) or 1))))
        elif s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            out.append(("cap", s[1:-1]))
        elif s.startswith("- "):
            out.append(("item", s[2:]))
        else:
            out.append(("para", s))
        i += 1
    return out


# --------------------------------------------------------------------------------------
# 한글 조작 도우미
# --------------------------------------------------------------------------------------
class Hwp:
    def __init__(self):
        self.h = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        self.h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        self.h.XHwpWindows.Item(0).Visible = True

    def run(self, name):
        return self.h.HAction.Run(name)

    def find(self, text):
        self.h.MovePos(2, 0, 0)                      # 문서 처음
        a, p = self.h.HAction, self.h.HParameterSet.HFindReplace
        a.GetDefault("ForwardFind", p.HSet)
        p.FindString = text
        p.IgnoreMessage = 1
        p.Direction = 0
        p.WholeWordOnly = 0
        return a.Execute("ForwardFind", p.HSet)

    def char(self, size=BODY_PT, bold=False, italic=False, color=(0, 0, 0)):
        a, p = self.h.HAction, self.h.HParameterSet.HCharShape
        a.GetDefault("CharShape", p.HSet)
        for k in ["FaceNameHangul", "FaceNameLatin", "FaceNameHanja", "FaceNameJapanese",
                  "FaceNameOther", "FaceNameSymbol", "FaceNameUser"]:
            setattr(p, k, FONT)
        for k in ["FontTypeHangul", "FontTypeLatin", "FontTypeHanja", "FontTypeJapanese",
                  "FontTypeOther", "FontTypeSymbol", "FontTypeUser"]:
            setattr(p, k, 1)
        p.Height = int(size * 100)
        p.Bold = 1 if bold else 0
        p.Italic = 1 if italic else 0
        p.TextColor = self.h.RGBColor(*color)
        for k, v in {"StrikeOutType": 0, "UnderlineType": 0, "ShadeColor": 0xFFFFFFFF}.items():
            try:
                setattr(p, k, v)          # 양식에 남아 있던 취소선·밑줄 서식 제거
            except Exception:
                pass
        a.Execute("CharShape", p.HSet)

    def para(self, align=0, spacing=150, left=0, indent=0, before=0, after=2):
        """align: 0 양쪽, 1 왼쪽, 2 오른쪽, 3 가운데"""
        a, p = self.h.HAction, self.h.HParameterSet.HParaShape
        a.GetDefault("ParagraphShape", p.HSet)
        p.AlignType = align
        p.LineSpacingType = 0
        p.LineSpacing = spacing
        p.LeftMargin = int(left * 200)
        p.Indentation = int(indent * 200)
        p.PrevSpacing = int(before * 200)
        p.NextSpacing = int(after * 200)
        try:
            p.HeadingType = 0             # 양식 안내문의 글머리표('-') 제거
        except Exception:
            pass
        try:
            p.BreakNonLatinWord = 1       # 한글 줄 나눔을 '글자' 단위로 (양쪽 정렬 시 글자 간격 벌어짐 방지)
        except Exception:
            pass
        a.Execute("ParagraphShape", p.HSet)

    def text(self, s):
        a, p = self.h.HAction, self.h.HParameterSet.HInsertText
        a.GetDefault("InsertText", p.HSet)
        p.Text = s
        a.Execute("InsertText", p.HSet)

    def rich(self, s, size=BODY_PT, base_bold=False, italic=False, color=(0, 0, 0)):
        """**굵게** 표시를 처리하며 글자를 넣는다"""
        for tok in re.split(r"(\*\*[^*]+\*\*)", s):
            if not tok:
                continue
            if tok.startswith("**"):
                self.char(size, True, italic, color)
                self.text(tok[2:-2])
            else:
                self.char(size, base_bold, italic, color)
                self.text(tok)

    def select_guidance(self, first, last):
        """안내문이 있는 칸으로 가서, 칸 처음부터 (last 문구 끝 또는 칸 끝)까지 선택"""
        if not self.find(first):
            raise RuntimeError(f"안내문을 못 찾음: {first}")
        self.run("Cancel")
        self.run("MoveListBegin")
        if last is None:
            self.run("MoveSelListEnd")
            return
        _, sp, sc = self.h.GetPos()
        if not self.find(last):
            raise RuntimeError(f"끝 문구를 못 찾음: {last}")
        _, ep, ec = self.h.GetPos()
        self.run("Cancel")
        self.h.SelectText(sp, 0, ep, ec)

    def table(self, rows, col_ratio=None):
        nr, nc = len(rows), len(rows[0])
        a, p = self.h.HAction, self.h.HParameterSet.HTableCreation
        a.GetDefault("TableCreate", p.HSet)
        p.Rows, p.Cols = nr, nc
        p.WidthType = 2
        p.HeightType = 0
        total = 115.0
        ratio = col_ratio or [1] * nc
        p.WidthValue = self.h.MiliToHwpUnit(total)
        p.CreateItemArray("ColWidth", nc)
        for j, r in enumerate(ratio):
            p.ColWidth.SetItem(j, self.h.MiliToHwpUnit(total * r / sum(ratio) - 1.0))
        a.Execute("TableCreate", p.HSet)
        for i, row in enumerate(rows):
            for j in range(nc):
                self.para(align=3 if i == 0 else 1, spacing=120, after=0)
                cell = row[j] if j < len(row) else ""
                self.rich(cell, size=TABLE_PT, base_bold=(i == 0))
                if not (i == nr - 1 and j == nc - 1):
                    self.run("TableRightCell")
        # 머리글 행 음영 (실패해도 내용에는 영향 없음)
        try:
            self.run("TableColBegin")
            self.run("TableColPageUp")
            self.run("TableCellBlock")
            self.run("TableCellBlockExtend")
            self.run("TableColEnd")
            cs = self.h.HParameterSet.HCellBorderFill
            self.h.HAction.GetDefault("CellFill", cs.HSet)
            cs.FillAttr.type = self.h.BrushType("NullBrush|WinBrush")
            cs.FillAttr.WinBrushFaceColor = self.h.RGBColor(220, 230, 240)
            cs.FillAttr.WinBrushHatchColor = self.h.RGBColor(0, 0, 0)
            cs.FillAttr.WinBrushFaceStyle = self.h.HatchStyle("None")
            self.h.HAction.Execute("CellFill", cs.HSet)
        except Exception as e:
            print("머리글 음영 생략:", e)
        self.run("Cancel")

    def picture(self, path, ratio):
        w = IMG_W_MM * min(ratio / 0.85, 1.0) if ratio < 1 else IMG_W_MM
        with Image.open(path) as im:
            hmm = w * im.height / im.width
        self.para(align=3, spacing=100, after=0)
        self.h.InsertPicture(str(path), True, 1, False, False, 0, int(w), int(hmm))


# --------------------------------------------------------------------------------------
def main():
    sec = parse_md(SRC_MD)
    hwp = Hwp()
    h = hwp.h
    h.Open(str(TEMPLATE), "HWP", "forceopen:true")

    # 0) 끝의 유의사항 블록 삭제
    if hwp.find("분석보고서 작성 시 유의사항"):
        hwp.run("Cancel")
        hwp.run("MoveLineBegin")
        hwp.run("MoveSelDocEnd")
        hwp.run("Delete")

    # 1) 이름/팀명 (빈 칸)
    name = " ".join(l for l in sec["이름/팀명"] if l.strip()).strip()
    hwp.find("이름/팀명")
    hwp.run("Cancel")
    hwp.run("TableRightCell")
    hwp.para()
    hwp.rich(name)

    # 1-2) '요약' 행 추가: 양식에 없는 항목이라 '주제' 행 아래에 별도 제목으로 끼워 넣는다
    if "요약" in sec:
        hwp.find(CELLS["주제"][0])
        hwp.run("Cancel")
        hwp.run("TableInsertLowerRow")
        hwp.run("TableLowerCell")
        hwp.run("TableColBegin")
        hwp.para(align=3, spacing=130, after=0)
        hwp.char(size=10.5)
        hwp.text("요약")
        hwp.run("TableRightCell")
        for k, (kind, val) in enumerate(blocks(sec["요약"])):
            if k > 0:
                hwp.run("BreakPara")
            hwp.para(align=0, left=2, indent=-2, spacing=140, after=1)
            hwp.rich("· " + val if kind == "item" else val)

    # 2) 각 칸 채우기 (표·그림은 임시 표시)
    pending, tcount, fcount = [], 0, 0
    for title, (first, last) in CELLS.items():
        lines = sec[title]
        if title == "활용 데이터":
            # 데이터 표는 양식 안의 표에 따로 채우고, 표 아래 설명 문단만 위쪽 안내문 자리에 넣는다
            bl = [b for b in blocks(lines) if b[0] != "table"]
            data_rows = [b for b in blocks(lines) if b[0] == "table"][0][1][1:]
        else:
            bl = blocks(lines)
        hwp.select_guidance(first, last)
        hwp.run("Delete")
        for k, (kind, val) in enumerate(bl):
            if k > 0:
                hwp.run("BreakPara")
            small = title == "분석도구 및 참고문헌"
            if kind == "para":
                hwp.para(align=1 if "http" in val else 0)
                hwp.rich(val, size=9 if small else BODY_PT)
            elif kind == "item":
                hwp.para(align=1, left=2, indent=-2, spacing=130 if small else 150, after=1 if small else 2)
                hwp.rich("· " + val, size=9 if small else BODY_PT)
            elif kind == "cap":
                hwp.para(align=3, spacing=120, after=3)
                hwp.rich(val, size=CAP_PT, italic=True, color=(70, 70, 70))
            elif kind == "table":
                tcount += 1
                tag = f"§T{tcount}§"
                pending.append((tag, "table", val))
                hwp.para()
                hwp.char()
                hwp.text(tag)
            elif kind == "fig":
                fcount += 1
                tag = f"§F{fcount}§"
                pending.append((tag, "fig", val))
                hwp.para()
                hwp.char()
                hwp.text(tag)

    # 3) 임시 표시를 표·그림으로 바꾸기
    ratios = {1: [1.3, 1.4, 2.6], 2: [1.6, 1, 1.6], 3: [2.2, 1.6, 2.2]}
    for tag, kind, val in pending:
        if not hwp.find(tag):
            raise RuntimeError(f"표시를 못 찾음: {tag}")
        hwp.run("Delete")
        if kind == "table":
            n = int(tag[2:-1])
            hwp.table(val, ratios.get(n))
        else:
            hwp.picture(*val)

    # 4) 양식 안의 활용 데이터 표 채우기 (머리글 2줄 아래, 데이터 4줄)
    #    데이터가 4개보다 많으면 먼저 필요한 만큼 줄을 늘린 뒤, 처음 칸으로 돌아가 차례로 채운다.
    #    (줄을 채우는 도중에 추가하면 커서가 표 처음으로 튀어 내용이 섞이는 문제가 있었다)
    extra = len(data_rows) - 4
    for _ in range(max(extra, 0)):
        hwp.find("플랫폼(명)")
        hwp.run("Cancel")
        hwp.run("TableLowerCell")
        hwp.run("TableAppendRow")
    hwp.find("플랫폼(명)")
    hwp.run("Cancel")
    hwp.run("TableLowerCell")
    hwp.run("TableColBegin")
    for i, r in enumerate(data_rows):
        name_, org, src, plat, url = (r + [""] * 5)[:5]
        cells = [f"{name_} ({src})", org, plat, url]
        for j, c in enumerate(cells):
            hwp.para(align=1, spacing=115, after=0)
            hwp.rich(c, size=TABLE_PT - 0.5)
            if not (i == len(data_rows) - 1 and j == 3):
                hwp.run("TableRightCell")

    hwp.run("Cancel")
    h.SaveAs(str(OUT_HWP), "HWP", "")
    h.SaveAs(str(OUT_PDF), "PDF", "")
    print("쪽수:", h.PageCount)
    h.Clear(1)
    h.Quit()
    print("저장:", OUT_HWP, OUT_PDF)


if __name__ == "__main__":
    main()
