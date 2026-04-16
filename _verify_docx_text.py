import zipfile, re
with zipfile.ZipFile('Smart Pick Pro Tournament.docx', 'r') as z:
    xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
text = re.sub(r'<[^>]+>', '\n', xml)
text = re.sub(r'\n+', '\n', text)
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
for ln in lines[:80]:
    print(ln)
