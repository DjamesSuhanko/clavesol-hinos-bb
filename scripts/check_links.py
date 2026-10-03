from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import os
root=Path(__file__).resolve().parents[1]/'dist';base=os.environ.get('BASE_PATH','').rstrip('/');errors=[]
class Links(HTMLParser):
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k not in ['src','href'] or not v: continue
   u=urlsplit(v)
   if u.scheme or u.netloc or not u.path: continue
   p=unquote(u.path)
   if base and p.startswith(base+'/'):p=p[len(base):]
   target=root/p.lstrip('/') if p.startswith('/') else current.parent/p
   if not target.exists(): errors.append(f'{current.relative_to(root)}: {v}')
for current in root.rglob('*.html'):Links().feed(current.read_text())
if errors:raise SystemExit('\n'.join(errors))
print('All internal pages and assets resolve.')
