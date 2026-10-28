from pathlib import Path
from datetime import UTC,datetime
from io import BytesIO
import requests,json,zipfile,hashlib

out=Path(__file__).resolve().parent/'official_j18'
out.mkdir(exist_ok=True)
urls={
 'composition.zip':'https://www.selae.es/f/loterias/web_corporativa/Comunicacion/Avisos_de_interes/COMPOSICION%20DE%20BOLETOS%20JORNADAS%2018%20DE%20LA%20QUINIELA%2C%20ELIGE%208%20Y%2019%20DEL%20QUINIGOL%20.zip',
 'closing.pdf':'https://www.selae.es/f/loterias/web_corporativa/Comunicacion/Avisos_de_interes/Aviso%20cierre%20La%20Quiniela%20jornada%2018%C2%AA%20y%20El%20QuiniGol%20jornada%2019%C2%AA%20de%2031%20Octubre%20-%201%20Noviembre%20de%202026.pdf',
 'j14_scrutiny.html':'https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-18-de-octubre-de-2026',
 'j16_scrutiny.html':'https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-25-de-octubre-de-2026'}
audit=[]
for name,url in urls.items():
 if (out/name).exists():raise ValueError('Already captured; choose a new directory')
 try:
  r=requests.get(url,timeout=45)
  item={'file':name,'url':url,'captured_at':datetime.now(UTC).isoformat(),'status_code':r.status_code}
  if r.status_code!=200:
   audit.append(item);continue
  content=r.content
  (out/name).write_bytes(content)
  item['sha256']=hashlib.sha256(content).hexdigest()
  if name.endswith('.zip'):
   z=zipfile.ZipFile(BytesIO(content))
   item['members']=[{'name':m.filename,'bytes':m.file_size} for m in z.infolist()]
   for n,m in enumerate(z.infolist()):
    if m.file_size>10000000:raise ValueError('Large archive member')
    if not m.is_dir() and Path(m.filename).suffix.lower() in {'.pdf','.png','.jpg','.jpeg','.txt'}:
     dest=out/f'composition_{n}{Path(m.filename).suffix.lower()}'
     dest.write_bytes(z.read(m));item.setdefault('extracted',[]).append({'original':m.filename,'file':dest.name})
  audit.append(item)
 except requests.RequestException as exc:
  audit.append({'file':name,'url':url,'error':type(exc).__name__})
(out/'capture_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(audit,indent=2))
