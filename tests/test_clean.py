import sys
from src.services.llm_service import clean_speech_text

sys.stdout.reconfigure(encoding='utf-8')
sample = 'ನೀವು ಎರಡು ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬಯಸುತ್ತೀರಿ, ದಯವಿಟ್ಟು. , "deliverytype": "delivery"}}'
res = clean_speech_text(sample)
print("CLEANED:", res)
assert "delivery" not in res
assert "{" not in res
assert "}" not in res
print("PASS!")
