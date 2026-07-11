from pathlib import Path
p = Path('templates/chatbot.html')
data = p.read_bytes()
print('bytes', len(data))
print(data[:200])
print('---')
for needle in [b'\xe2\x80\x94', b'\xe2\x80\x9d', b'\xe2\x80\x9c', b'\xe2\x80\x98', b'\xe2\x80\x99', b'\xe2\x80\xa2']:
    print(needle, data.find(needle))
