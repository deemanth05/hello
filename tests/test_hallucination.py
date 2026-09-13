import sys
from src.services.stt_service import is_hallucination

sys.stdout.reconfigure(encoding='utf-8')

test_cases = [
    ("ನನಿನನನನನನನನನನನನನನನ", True),
    ("...............", True),
    ("aaaaaaa", True),
    ("", True),
    ("2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬೇಕು", False),
    ("Hello", False),
    ("ಅಕ್ಕಿ ಮತ್ತು ಬೇಳೆ", False),
    ("ನನ್ನ ಹೆಸರು ದೀಮಂತ್", False),
]

for text, expected in test_cases:
    res = is_hallucination(text)
    print(f"Text: '{text}' -> Hallucination: {res} (Expected: {expected})")
    assert res == expected, f"Failed on '{text}'"

print("ALL HALLUCINATION TESTS PASSED!")
