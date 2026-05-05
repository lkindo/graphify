import fitz
import os

def final_strict_extraction():
    pdf_path = r'd:\project\graphify\pdf\tree.pdf'
    output_dir = r'd:\project\graphify\assets\trees'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # RE-ORDERED and VERIFIED mapping based on TOC page numbers
    # We follow the rule: TOC number X -> Extract PDF page X+1 (doc[X]) and X+2 (doc[X+1])
    mapping = [
        {"name": "소철", "page": 8}, {"name": "은행나무", "page": 10}, {"name": "전나무", "page": 12}, 
        {"name": "구상나무", "page": 14}, {"name": "솔송나무", "page": 16}, {"name": "독일가문비", "page": 18}, 
        {"name": "잣나무", "page": 20}, {"name": "소나무", "page": 22}, {"name": "소나무속 나무의 비교", "page": 24}, 
        {"name": "일본잎갈나무", "page": 26}, {"name": "개잎갈나무", "page": 28}, {"name": "메타세쿼이아", "page": 30}, 
        {"name": "삼나무", "page": 32}, {"name": "측백나무", "page": 34}, {"name": "편백", "page": 36}, 
        {"name": "향나무", "page": 38}, {"name": "비자나무", "page": 40}, {"name": "주목", "page": 42}, 
        {"name": "오미자", "page": 44}, {"name": "붓순나무", "page": 46}, {"name": "쥐방울덩굴", "page": 48}, 
        {"name": "자주받침꽃", "page": 50}, {"name": "생강나무", "page": 52}, {"name": "비목나무", "page": 54}, 
        {"name": "녹나무", "page": 56}, {"name": "후박나무", "page": 58}, {"name": "백목련", "page": 60}, 
        {"name": "함박꽃나무", "page": 62}, {"name": "일본목련", "page": 64}, {"name": "태산목", "page": 66}, 
        {"name": "튤립나무", "page": 68}, {"name": "청미래덩굴", "page": 70}, {"name": "종려나무", "page": 72}, 
        {"name": "야자나무 종류의 비교", "page": 74}, {"name": "매발톱나무", "page": 76}, {"name": "으름덩굴", "page": 78}, 
        {"name": "멀꿀", "page": 80}, {"name": "종덩굴", "page": 82}, {"name": "양비즘나무", "page": 84}, 
        {"name": "회양목", "page": 86}, {"name": "계수나무", "page": 88}, {"name": "굴거리", "page": 90}, 
        {"name": "까마귀밥여름나무", "page": 92}, {"name": "조록나무", "page": 94}, {"name": "히어리", "page": 96}, 
        {"name": "모란", "page": 98}, {"name": "개머루", "page": 100}, {"name": "담쟁이덩굴", "page": 102}, 
        {"name": "사철나무", "page": 104}, {"name": "화살나무", "page": 106}, {"name": "산나물로 먹는 나무", "page": 108}, 
        {"name": "회나무", "page": 110}, {"name": "노박덩굴", "page": 112}, {"name": "예덕나무", "page": 114}, 
        {"name": "사람주나무", "page": 116}, {"name": "유동", "page": 118}, {"name": "망종화", "page": 120}, 
        {"name": "이나무", "page": 122}, {"name": "은사시나무", "page": 124}, {"name": "사시나무속 나무의 비교", "page": 126}, 
        {"name": "버드나무", "page": 128}, {"name": "갯버들", "page": 130}, {"name": "자귀나무", "page": 132}, 
        {"name": "박태기나무", "page": 134}, {"name": "칡", "page": 136}, {"name": "골담초", "page": 138}, 
        {"name": "아까시나무", "page": 140}, {"name": "등", "page": 142}, {"name": "족제비싸리", "page": 144}, 
        {"name": "싸리", "page": 146}, {"name": "회화나무", "page": 148}, {"name": "다릅나무", "page": 150}, 
        {"name": "오리나무", "page": 152}, {"name": "사방오리", "page": 154}, {"name": "박달나무", "page": 156}, 
        {"name": "자작나무", "page": 158}, {"name": "자작나무속 나무의 비교", "page": 160}, {"name": "개암나무", "page": 162}, 
        {"name": "서어나무", "page": 164}, {"name": "밤나무", "page": 166}, {"name": "구실잣밤나무", "page": 168}, 
        {"name": "상수리나무", "page": 170}, {"name": "참나무속 나무의 비교", "page": 172}, {"name": "가시나무", "page": 174}, 
        {"name": "굴피나무", "page": 176}, {"name": "중국굴피나무", "page": 178}, {"name": "가래나무", "page": 180}, 
        {"name": "소귀나무", "page": 182}, {"name": "팽나무", "page": 184}, {"name": "보리수나무", "page": 186}, 
        {"name": "꾸지뽕나무", "page": 188}, {"name": "닥나무", "page": 190}, {"name": "산뽕나무", "page": 192}, 
        {"name": "천선과나무", "page": 194}, {"name": "무화과", "page": 196}, {"name": "대추나무", "page": 198}, 
        {"name": "갯대추나무", "page": 200}, {"name": "가침박달", "page": 202}, {"name": "조팝나무", "page": 204}, 
        {"name": "조팝나무속 나무의 비교", "page": 206}, {"name": "국수나무", "page": 208}, {"name": "매실나무", "page": 210}, 
        {"name": "살구나무", "page": 212}, {"name": "복숭아나무", "page": 214}, {"name": "왕벚나무", "page": 216}, 
        {"name": "앵두나무", "page": 218}, {"name": "찔레꽃", "page": 220}, {"name": "해당화", "page": 222}, 
        {"name": "산딸기", "page": 224}, {"name": "산딸기속 나무의 비교", "page": 226}, {"name": "황매화", "page": 228}, 
        {"name": "비파나무", "page": 230}, {"name": "다정큼나무", "page": 232}, {"name": "모과나무", "page": 234}, 
        {"name": "사과나무", "page": 236}, {"name": "산사나무", "page": 238}, {"name": "콩배나무", "page": 240}, 
        {"name": "마가목", "page": 242}, {"name": "팥배나무", "page": 244}, {"name": "느릅나무", "page": 246}, 
        {"name": "느티나무", "page": 248}, {"name": "배롱나무", "page": 250}, {"name": "석류나무", "page": 252}, 
        {"name": "벽오동", "page": 254}, {"name": "장구밥나무", "page": 256}, {"name": "피나무", "page": 258}, 
        {"name": "무궁화", "page": 260}, {"name": "삼지닥나무", "page": 262}, {"name": "붉나무", "page": 264}, 
        {"name": "개옻나무", "page": 266}, {"name": "멀구슬나무", "page": 268}, {"name": "산초나무", "page": 270}, 
        {"name": "쉬나무", "page": 272}, {"name": "황벽나무", "page": 274}, {"name": "탱자나무", "page": 276}, 
        {"name": "칠엽수", "page": 278}, {"name": "모감주나무", "page": 280}, {"name": "고로쇠나무", "page": 282}, 
        {"name": "단풍나무", "page": 284}, {"name": "단풍나무속 나무의 비교", "page": 286}, {"name": "가죽나무", "page": 290}, 
        {"name": "소태나무", "page": 292}, {"name": "겨우살이", "page": 294}, {"name": "산딸나무", "page": 296}, 
        {"name": "산수유", "page": 298}, {"name": "층층나무", "page": 300}, {"name": "층층나무속 나무의 비교", "page": 302}, 
        {"name": "물참대", "page": 304}, {"name": "수국", "page": 306}, {"name": "산수국", "page": 308}, 
        {"name": "다래", "page": 310}, {"name": "산에서 따 먹는 열매", "page": 312}, {"name": "개다래", "page": 314}, 
        {"name": "감나무", "page": 316}, {"name": "철쭉", "page": 318}, {"name": "진달래", "page": 320}, 
        {"name": "정금나무", "page": 322}, {"name": "사스레피나무", "page": 324}, {"name": "자금우", "page": 326}, 
        {"name": "쪽동백나무", "page": 328}, {"name": "노린재나무", "page": 330}, {"name": "동백나무", "page": 332}, 
        {"name": "노각나무", "page": 334}, {"name": "차나무", "page": 336}, {"name": "두충", "page": 338}, 
        {"name": "마삭줄", "page": 340}, {"name": "치자나무", "page": 342}, {"name": "구슬꽃나무", "page": 344}, 
        {"name": "계요등", "page": 346}, {"name": "능소화", "page": 348}, {"name": "개오동", "page": 350}, 
        {"name": "작살나무", "page": 352}, {"name": "층꽃나무", "page": 354}, {"name": "누리장나무", "page": 356}, 
        {"name": "순비기나무", "page": 358}, {"name": "물푸레나무", "page": 360}, {"name": "들메나무", "page": 362}, 
        {"name": "미선나무", "page": 364}, {"name": "개나리", "page": 366}, {"name": "우리나라에서만 자생하는 특산나무", "page": 368}, 
        {"name": "라일락", "page": 370}, {"name": "이팝나무", "page": 372}, {"name": "쥐똥나무", "page": 374}, 
        {"name": "참오동나무", "page": 376}, {"name": "구기자나무", "page": 378}, {"name": "먼나무", "page": 380}, 
        {"name": "호랑가시나무", "page": 382}, {"name": "딱총나무", "page": 384}, {"name": "가막살나무", "page": 386}, 
        {"name": "분꽃나무", "page": 388}, {"name": "백당나무", "page": 390}, {"name": "댕강나무", "page": 392}, 
        {"name": "병꽃나무", "page": 394}, {"name": "괴불나무", "page": 396}, {"name": "인동덩굴", "page": 398}, 
        {"name": "송악", "page": 400}, {"name": "팔손이", "page": 402}, {"name": "황칠나무", "page": 404}, 
        {"name": "오갈피나무", "page": 406}, {"name": "돈나무", "page": 408}
    ]

    doc = fitz.open(pdf_path)
    for item in mapping:
        clean_name = item["name"].replace("/", "_").replace("?", "")
        # NO OFFSET, NO CORRECTION. Strictly TOC_NUM -> 0-indexed PDF page.
        page_idx = item["page"] 
        
        if page_idx >= len(doc): continue
        
        # Image 1 (TOC+1)
        pix1 = doc[page_idx].get_pixmap(matrix=fitz.Matrix(2, 2))
        pix1.save(os.path.join(output_dir, f"{clean_name}_1.jpg"))
        
        # Image 2 (TOC+2)
        if page_idx + 1 < len(doc):
            pix2 = doc[page_idx + 1].get_pixmap(matrix=fitz.Matrix(2, 2))
            pix2.save(os.path.join(output_dir, f"{clean_name}_2.jpg"))
    
    doc.close()
    print(f"Successfully re-extracted {len(mapping)} entries with STRICT TOC numbers and corrected order.")

if __name__ == "__main__":
    final_strict_extraction()
