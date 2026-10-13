import re
from .number_normalizer import normalize_vietnamese_numbers


def apply_code_mode(text: str) -> str:
    """
    Chuyển đổi văn bản thu từ mic trong chế độ mã:
    1. Chuyển các từ chỉ số (không, một, hai, ba...) thành chữ số (0, 1, 2, 3...)
    2. Chuyển từ "xuất hiện" / "Xuất Hiện" thành "XH"
    """
    if not text:
        return ""

    # 1. Chuyển từ "xuất hiện" / "Xuất Hiện" (không phân biệt hoa thường) thành "XH"
    pattern_xh = re.compile(r"\bxuất\s+hiện\b", re.IGNORECASE | re.UNICODE)
    text = pattern_xh.sub("XH", text)

    # 2. Chuẩn hóa các con số tiếng Việt thành chữ số
    text = normalize_vietnamese_numbers(text)

    return text
