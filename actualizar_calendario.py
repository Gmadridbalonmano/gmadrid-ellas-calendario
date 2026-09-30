#!/usr/bin/env python3
import re
import sys
import html
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TEAM = "G MADRID ELLAS 2NF"
ICS_FILE = Path("GMadrid_eLLas_2026-2027_Google_Calendar.ics")
TZ = ZoneInfo("Europe/Madrid")

BASE = [
    (1,"2026-10-04","GRUPO EGIDO BM PINTO 2NF",True),
    (2,"2026-10-18","CB PARLA 2NF",False),
    (3,"2026-10-25","BALONMANO LEGANES 2NF",True),
    (4,"2026-11-08","CLUB BALONMANO ALCOBENDAS 2NF",False),
    (5,"2026-11-15","CAB CONCE 1NF",False),
    (6,"2026-11-22","AD BALONMANO VILLAVICIOSA DE ODON 2NF",True),
    (7,"2026-11-29","CORAZONISTAS 2NF",False),
    (8,"2026-12-13","GRUPO EGIDO BM PINTO 2NF",False),
    (9,"2027-01-17","CB PARLA 2NF",True),
    (10,"2027-01-24","BALONMANO LEGANES 2NF",False),
    (11,"2027-01-31","CLUB BALONMANO ALCOBENDAS 2NF",True),
    (12,"2027-02-07","CAB CONCE 1NF",True),
    (13,"2027-02-14","AD BALONMANO VILLAVICIOSA DE ODON 2NF",False),
    (14,"2027-02-21","CORAZONISTAS 2NF",True),
]

SEED_URLS = [
 "https://resultadosbalonmano.isquad.es/competicion.php?id=1038714&id_categoria=3096&id_competicion=211899&id_territorial=21&seleccion=0",
 "https://resultadosbalonmano.isquad.es/competicion.php?id=1038714&id_competicion=211899&id_territorial=21&seleccion=0",
 "https://www.fmbalonmano.com/resultados-clasificaciones",
]
UA = "Mozilla/5.0 (compatible; GMadrid-eLLas-Calendar/1.0)"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8",errors="replace"),r.geturl()

def clean(raw):
    raw=re.sub(r"<script\\b[^>]*>.*?</script>"," ",raw,flags=re.I|re.S)
    raw=re.sub(r"<style\\b[^>]*>.*?</style>"," ",raw,flags=re.I|re.S)
    raw=re.sub(r"<br\\s*/?>","\\n",raw,flags=re.I)
    raw=re.sub(r"</(?:td|th|tr|p|div|li|h\\d)>","\\n",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    raw=html.unescape(raw).replace("\\xa0"," ")
    raw=re.sub(r"[ \\t]+"," ",raw)
    return re.sub(r"\\n+","\\n",raw).strip()

def links(raw):
    out=[]
    pattern = r'''(?:href|src)=["']([^"']+)["']'''
    for x in re.findall(pattern,raw,flags=re.I):
        x=html.unescape(x)
        if "resultadosbalonmano.isquad.es" in x:
            if not x.startswith("http"): x="https://"+x.lstrip("/")
            out.append(x)
        elif x.startswith(("competicion.php","equipo.php")):
            out.append("https://resultadosbalonmano.isquad.es/"+x)
    return list(dict.fromkeys(out))

def discover():
    queue=list(SEED_URLS); seen=set(); pages=[]
    while queue and len(seen)<40:
        url=queue.pop(0)
        if url in seen: continue
        seen.add(url)
        try: raw,final=fetch(url)
        except Exception as e:
            print("[WARN]",url,e); continue
        txt=clean(raw)
        up=txt.upper()
        if TEAM in up or ("2" in up and "NACIONAL FEMENINA" in up and "2026" in up):
            pages.append((final,txt))
        for x in links(raw):
            if x not in seen and ("competicion.php" in x or "equipo.php" in x):
                queue.append(x)
    return pages

def norm(s):
    return re.sub(r"\\s+"," ",html.unescape(s).upper()).strip()

def live_matches():
    pages=discover()
    if not pages:
        raise RuntimeError("No se localizaron paginas publicas de la competicion 2026-27.")
    candidates=[]
    dr=re.compile(r"\\b(\\d{1,2}/\\d{1,2}/20(?:26|27))\\s+(\\d{1,2}:\\d{2})\\b")
    for url,txt in pages:
        up=txt.upper()
        for m in re.finditer(re.escape(TEAM),up):
            chunk=txt[max(0,m.start()-600):min(len(txt),m.end()+1200)]
            dm=dr.search(chunk)
            if not dm: continue
            dt=datetime.strptime(dm.group(1)+" "+dm.group(2),"%d/%m/%Y %H:%M")
            before=chunk[:dm.start()]
            lines=[x.strip() for x in before.splitlines() if x.strip()]
            teams=" ".join([x for x in lines[-12:] if "2NF" in x.upper() or TEAM in x.upper()])
            after=chunk[dm.end():]
            alines=[x.strip() for x in after.splitlines() if x.strip()]
            place=""
            for x in alines[:10]:
                ux=x.upper()
                if ux not in {"PREVIO","STREAMING","ESTAD.","DIRECTO","ACTA","CRONICA","CRÓNICA"} and not re.match(r"^\\d+\\s*-\\s*\\d+$",x):
                    place=x; break
            candidates.append({"dt":dt,"teams":teams,"place":place,"url":url})
    live={}
    for j,bd,rival,home in BASE:
        base=datetime.strptime(bd,"%Y-%m-%d").date()
        options=[]
        for c in candidates:
            nt=norm(c["teams"])
            if TEAM in nt and norm(rival) in nt:
                delta=abs((c["dt"].date()-base).days)
                if delta<=45: options.append((delta,c))
        if options:
            options.sort(key=lambda x:x[0])
            live[j]=options[0][1]
    return live

def esc(s):
    return str(s).replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")

def generate(live):
    stamp=datetime.now(TZ).astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    out=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//GMadrid Sports//eLLas 2026-2027//ES",
         "CALSCALE:GREGORIAN","METHOD:PUBLISH","X-WR-CALNAME:GMadrid eLLas 2026-2027",
         "X-WR-TIMEZONE:Europe/Madrid","REFRESH-INTERVAL;VALUE=DURATION:PT6H","X-PUBLISHED-TTL:PT6H"]
    for j,bd,rival,home in BASE:
        info=live.get(j)
        title=f"🤾 GMadrid eLLas - {rival}" if home else f"🤾 {rival} - GMadrid eLLas"
        default_place="Colegio Santa Joaquina de Vedruna, Travesía de Costa Brava 3, 28034 Madrid" if home else ""
        out += ["BEGIN:VEVENT",f"UID:gmadrid-ellas-2627-j{j}@gmadridsports",f"DTSTAMP:{stamp}",
                f"SUMMARY:{esc(title)}",
                f"DESCRIPTION:{esc('Jornada '+str(j)+' - Segunda Nacional Femenina 2026/27. Actualizado desde FMBM/iSquad. https://www.fmbalonmano.com/resultados-clasificaciones')}"]
        if info:
            start=info["dt"]; end=start+timedelta(hours=1,minutes=30)
            out += [f"DTSTART;TZID=Europe/Madrid:{start:%Y%m%dT%H%M%S}",
                    f"DTEND;TZID=Europe/Madrid:{end:%Y%m%dT%H%M%S}",
                    f"LOCATION:{esc(info['place'] or default_place)}","STATUS:CONFIRMED","TRANSP:OPAQUE"]
            print(f"[OK] J{j}: {start:%d/%m/%Y %H:%M} | {info['place']}")
        else:
            d=datetime.strptime(bd,"%Y-%m-%d").date()
            out += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}",f"DTEND;VALUE=DATE:{(d+timedelta(days=1)):%Y%m%d}"]
            if default_place: out.append(f"LOCATION:{esc(default_place)}")
            out += ["STATUS:TENTATIVE","TRANSP:TRANSPARENT"]
            print(f"[BASE] J{j}: {d:%d/%m/%Y} | sin horario localizado")
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(out)+"\r\n"

def main():
    try:
        live=live_matches()
        if 1 not in live:
            print("[ERROR] TEST J1: no se localizo el horario publicado de GMadrid-Pinto.",file=sys.stderr)
            return 2
        print(f"[TEST J1] Detectado: {live[1]['dt']:%d/%m/%Y %H:%M}")
        ICS_FILE.write_text(generate(live),encoding="utf-8",newline="")
        print("[DONE]",ICS_FILE)
        return 0
    except Exception as e:
        print("[ERROR]",e,file=sys.stderr); return 1

if __name__=="__main__":
    raise SystemExit(main())
