import re

_DIGITS = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
_WORDS = set(_DIGITS) | {"mười", "trăm", "nghìn", "ngàn", "triệu", "tỷ", "tỉ", "linh", "lẻ", "mươi"}

def _parse(tokens):
    total = current = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _DIGITS: current += _DIGITS[token]
        elif token == "mười": current = current + 10 if current >= 100 else (current or 1) * 10
        elif token == "mươi":
            if current >= 100 and index > 0 and tokens[index - 1] in _DIGITS:
                digit = _DIGITS[tokens[index - 1]]; current = current - digit + digit * 10
            else: current = current + 10 if current >= 100 else (current or 1) * 10
        elif token == "trăm":
            current = current * 100 if current else 0
            remainder = tokens[index + 1:]
            if len(remainder) == 2 and all(word in _DIGITS for word in remainder): return total + current + _DIGITS[remainder[0]] * 10 + _DIGITS[remainder[1]]
        elif token in ("nghìn", "ngàn"): total += (current or 1) * 1000; current = 0
        elif token == "triệu": total += (current or 1) * 1000000; current = 0
        elif token in ("tỷ", "tỉ"): total += (current or 1) * 1000000000; current = 0
        index += 1
    return total + current

def normalize_vietnamese_numbers(text):
    word_pattern = "|".join(sorted(map(re.escape, _WORDS), key=len, reverse=True))
    pattern = re.compile(rf"(?<![\wÀ-ỹ])({word_pattern})(?:\s+({word_pattern}))*(?![\wÀ-ỹ])", re.IGNORECASE | re.UNICODE)
    def replace(match):
        words = re.findall(rf"(?:{word_pattern})", match.group(0).lower(), re.IGNORECASE)
        if all(word in _DIGITS for word in words): return "".join(str(_DIGITS[word]) for word in words)
        return str(_parse(words))
    return pattern.sub(replace, str(text))
