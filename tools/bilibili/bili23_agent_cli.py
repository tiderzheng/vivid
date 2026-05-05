#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, random, re, shutil, subprocess, sys, time, urllib.parse
from hashlib import md5
from pathlib import Path
from typing import Any
import requests

MIX=[46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
VQ=[127,126,125,120,116,112,100,80,64,32,16]
AQ=[30251,30250,30280,30232,30216]
CM={"auto":20,"avc":7,"h264":7,"hevc":12,"h265":12,"av1":13}
AE={30251:"flac",30250:"ec3",30280:"m4a",30232:"m4a",30216:"m4a"}
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
RF="https://www.bilibili.com/"
HX="0123456789ABCDEF"

class E(Exception):pass

def safe(n:str)->str:
    n=re.sub(r'[\\/:*?"<>|]','_',n)
    return re.sub(r'\s+',' ',n).strip()[:180] or 'untitled'

def fmt(template:str,ctx:dict[str,Any])->str:
    try:return safe(template.format(**{k:safe(str(v)) for k,v in ctx.items()}))
    except:return safe(str(ctx.get('title','untitled')))

def qpick(av:list[int],req:str,pri:list[int])->int:
    av=sorted(set(int(x) for x in av),reverse=True)
    if not av: raise E('no available quality')
    if req=='auto':
        for x in pri:
            if x in av:return x
        return av[0]
    t=int(req)
    if t in av:return t
    lo=[x for x in av if x<=t]
    return lo[0] if lo else av[0]

def _parse_cookie_header(raw:str)->dict[str,str]:
    raw=raw.strip()
    if not raw:return {}
    if raw.lower().startswith('cookie:'):
        raw=raw.split(':',1)[1].strip()
    cookies={}
    for part in raw.split(';'):
        if '=' not in part: continue
        k,v=part.split('=',1)
        k=k.strip()
        if not k: continue
        cookies[k]=v.strip()
    return cookies

def _rand_hex(length:int)->str:
    return ''.join(random.choice(HX) for _ in range(length))

def _generate_uuid_cookie(now:int)->str:
    return f"{'-'.join(_rand_hex(length) for length in (8,4,4,4,12))}{str(now % 100000).ljust(5,'0')}infoc"

def _generate_b_lsid(now:int)->str:
    return f"{_rand_hex(8)}_{format(now,'X')}"

def _fetch_spi_buvids(session:requests.Session)->dict[str,str]:
    try:
        data=session.get('https://api.bilibili.com/x/frontend/finger/spi',timeout=10).json()
    except Exception:
        return {}
    if data.get('code',0)!=0:return {}
    inner=data.get('data') or {}
    ret={}
    if inner.get('b_3'):ret['buvid3']=str(inner['b_3'])
    if inner.get('b_4'):ret['buvid4']=str(inner['b_4'])
    return ret

def _build_cookie_values(cookie:str='',sessdata:str='',session:requests.Session|None=None)->dict[str,str]:
    values=_parse_cookie_header(cookie)
    if sessdata and 'SESSDATA' not in values:
        values['SESSDATA']=sessdata
    now=int(time.time())
    values.setdefault('_uuid',_generate_uuid_cookie(now))
    values.setdefault('b_lsid',_generate_b_lsid(now))
    values.setdefault('b_nut',str(now))
    values.setdefault('CURRENT_FNVAL','4048')
    values.setdefault('CURRENT_QUALITY','0')
    if session and ('buvid3' not in values or 'buvid4' not in values):
        spi=_fetch_spi_buvids(session)
        if 'buvid3' not in values and spi.get('buvid3'):
            values['buvid3']=spi['buvid3']
        if 'buvid4' not in values and spi.get('buvid4'):
            values['buvid4']=spi['buvid4']
    return values

def _resolve_cookie_inputs(a:Any)->tuple[str,str]:
    cookie=str(getattr(a,'bili_cookie','') or os.environ.get('VIVID_BILI_COOKIE','') or os.environ.get('BILI_COOKIE','') or os.environ.get('BILI_COOKIE_HEADER','')).strip()
    sessdata=str(getattr(a,'sessdata','') or os.environ.get('BILI_SESSDATA','')).strip()
    return cookie,sessdata

class C:
    def __init__(self,cookie:str='',sessdata:str=''):
        self.s=requests.Session(); self.s.headers.update({'User-Agent':UA,'Referer':RF}); self.k=None
        for k,v in _build_cookie_values(cookie,sessdata,self.s).items():
            self.s.cookies.set(k,v,domain='.bilibili.com',path='/')
    def r(self,m,u,**kw):
        h={'User-Agent':UA,'Referer':RF}; h.update(kw.pop('headers',{}) or {})
        x=self.s.request(m,u,headers=h,timeout=20,**kw); x.raise_for_status(); return x
    def j(self,u,p=None,h=None,sig=False,path=None):
        p=p or {}
        if sig:p=self.sign(dict(p))
        d=self.r('GET',u,params=p,headers=h).json()
        if d.get('code',0)!=0: raise E(f"api error {d.get('code')}: {d.get('message') or d.get('msg')}")
        n=d
        for k in (path or []): n=n[k]
        return n
    def sign(self,p):
        if not self.k:
            nav=self.j('https://api.bilibili.com/x/web-interface/nav').get('data',{})
            w=nav.get('wbi_img',{})
            a=w.get('img_url','').rsplit('/',1)[-1].split('.')[0]
            b=w.get('sub_url','').rsplit('/',1)[-1].split('.')[0]
            if not a or not b: raise E('cannot get wbi key')
            self.k=(a,b)
        s=self.k[0]+self.k[1]
        m=''.join(s[i] for i in MIX)[:32]
        p['wts']=int(time.time())
        q={k:''.join(ch for ch in str(v) if ch not in "!'()*") for k,v in sorted(p.items())}
        q['w_rid']=md5((urllib.parse.urlencode(q)+m).encode()).hexdigest()
        return q
    def expand(self,u:str)->str:
        h=urllib.parse.urlparse(u).netloc.lower()
        return self.r('GET',u,allow_redirects=True).url if ('b23.tv' in h or 'bili2233.cn' in h) else u


def parse_ctx(c:C,url:str):
    nu=c.expand(url)
    ep=re.search(r'ep(\d+)',nu,re.I); ss=re.search(r'ss(\d+)',nu,re.I)
    bv=re.search(r'(BV[0-9A-Za-z]+)',nu); av=re.search(r'av(\d+)',nu,re.I)
    if ep or ss:
        p={'ep_id':int(ep.group(1))} if ep else {'season_id':int(ss.group(1))}
        d=c.j('https://api.bilibili.com/pgc/view/web/season',p,path=['result'])
        eps=[]; di=0; te=int(ep.group(1)) if ep else 0
        for i,e in enumerate(d.get('episodes',[]),1):
            eid=int(e.get('id',0));
            if te and eid==te:di=i-1
            dur=int(e.get('duration',0)); dur=dur//1000 if dur>10000 else dur
            t=(f"E{i:02d}-{e.get('long_title') or e.get('title') or ''}").rstrip('-')
            eps.append({'type':'bangumi','bvid':e.get('bvid',''),'aid':int(e.get('aid',0)),'cid':int(e.get('cid',0)),'ep_id':eid,'title':t,'full':d.get('title',''),'dur':dur,'cover':e.get('cover') or d.get('cover',''),'ref':e.get('share_url') or e.get('link') or f"https://www.bilibili.com/bangumi/play/ep{eid}"})
        if not eps: raise E('no episodes from bangumi url')
        return {'stype':'bangumi','url':url,'norm':nu,'detail':d,'eps':eps,'defi':di}
    if not (bv or av): raise E('unsupported url')
    q=urllib.parse.parse_qs(urllib.parse.urlparse(nu).query); p=1
    try:p=max(1,int((q.get('p') or ['1'])[0]))
    except:pass
    d=c.j('https://api.bilibili.com/x/web-interface/wbi/view',{'bvid':bv.group(1)} if bv else {'aid':int(av.group(1))},sig=True,path=['data'])
    pages=d.get('pages') or []
    if not pages: raise E('no pages from video url')
    eps=[]
    for i,x in enumerate(pages,1):
        t=d.get('title','untitled') if len(pages)==1 else f"P{i:02d}-{x.get('part') or d.get('title','untitled')}"
        r=f"https://www.bilibili.com/video/{d.get('bvid','')}"+(f"?p={i}" if len(pages)>1 else '')
        eps.append({'type':'video','bvid':d.get('bvid',''),'aid':int(d.get('aid',0)),'cid':int(x.get('cid',0)),'ep_id':0,'title':t,'full':d.get('title',''),'dur':int(x.get('duration',0)),'cover':d.get('pic',''),'ref':r})
    return {'stype':'video','url':url,'norm':nu,'detail':d,'eps':eps,'defi':min(p,len(eps))-1}


def play(c:C,e:dict,qn:int):
    if e['type']=='video':
        return c.j('https://api.bilibili.com/x/player/wbi/playurl',{'bvid':e['bvid'],'cid':e['cid'],'qn':qn,'fnver':0,'fnval':4048,'fourk':1},h={'Referer':e['ref']},sig=True,path=['data'])
    return c.j('https://api.bilibili.com/pgc/player/web/playurl',{'bvid':e['bvid'],'cid':e['cid'],'qn':qn,'fnver':0,'fnval':12240,'fourk':1},h={'Referer':e['ref']},path=['result'])

def stype(d):
    if 'dash' in d:return 'DASH'
    if d.get('durl'):return 'FLV'
    if d.get('durls'):return 'MP4'
    return 'UNKNOWN'

def urls(n):
    r=[]
    for k in ('baseUrl','base_url','url'):
        if n.get(k):r.append(n[k])
    for k in ('backupUrl','backup_url'):
        if n.get(k):r.extend(n[k])
    return [x for x in r if x]

def audios(dash):
    a=[]; a.extend(dash.get('audio') or [])
    d=(dash.get('dolby') or {}).get('audio')
    if d:
        if isinstance(d,list):
            for x in d: y=dict(x); y['id']=y.get('id') or 30250; a.append(y)
        else:
            y=dict(d); y['id']=y.get('id') or 30250; a.append(y)
    f=(dash.get('flac') or {}).get('audio')
    if f:
        if isinstance(f,list):
            for x in f: y=dict(x); y['id']=y.get('id') or 30251; a.append(y)
        else:
            y=dict(f); y['id']=y.get('id') or 30251; a.append(y)
    return a

def dl(c:C,ul:list[str],out:Path,ref:str,label:str):
    out.parent.mkdir(parents=True,exist_ok=True)
    last=None
    for i,u in enumerate(ul,1):
        try:
            with c.r('GET',u,headers={'Referer':ref},stream=True) as r:
                with out.open('wb') as f:
                    for b in r.iter_content(1024*128):
                        if b:f.write(b)
            print(f"[ok] {label}: {out}"); return
        except Exception as ex:
            last=ex; print(f"[warn] {label} mirror#{i} failed")
    raise E(f"all mirrors failed for {label}: {last}")

def merge(ff,v,a,o):
    if shutil.which(ff) is None: raise E(f'ffmpeg not found: {ff}')
    subprocess.run([ff,'-y','-i',str(v),'-i',str(a),'-c','copy',str(o)],check=True)
    print(f"[ok] merged: {o}")

def conv(ff,src,dst):
    if shutil.which(ff) is None: raise E(f'ffmpeg not found: {ff}')
    subprocess.run([ff,'-y','-i',str(src),str(dst)],check=True)
    print(f"[ok] converted: {dst}")

def to_srt(d):
    def t(x):
        ms=int(round(float(x)*1000)); h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000; s=ms//1000; ms%=1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    o=[]
    for i,x in enumerate(d.get('body',[]),1): o += [str(i),f"{t(x.get('from',0))} --> {t(x.get('to',0))}",str(x.get('content','')),'']
    return '\n'.join(o)

def to_txt(d):
    return '\n'.join(str(x.get('content','')) for x in d.get('body',[]))

def to_lrc(d):
    def t(x):
        x=float(x); m=int(x//60); s=x-m*60
        return f"{m:02d}:{s:05.2f}"
    return '\n'.join(f"[{t(x.get('from',0))}]{x.get('content','')}" for x in d.get('body',[]))

def sub(c:C,e:dict,out:Path,bn:str,fmtx:str,lan:str):
    if fmtx=='none':return
    p={'bvid':e['bvid'],'cid':e['cid'],'dm_img_list':'[]','dm_img_str':'V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ','dm_cover_img_str':'QU5HTEUgKE5WSURJQSwgTlZJRElBIEdlRm9yY2UgUlRYIDQwNjAgTGFwdG9wIEdQVSAoMHgwMDAwMjhFMCkgRGlyZWN0M0QxMSB2c181XzAgcHNfNV8wLCBEM0QxMSlHb29nbGUgSW5jLiAoTlZJRElBKQ','dm_img_inter':'{"ds":[],"wh":[5231,6067,75],"of":[475,950,475]}'}
    d=c.j('https://api.bilibili.com/x/player/wbi/v2',p,h={'Referer':e['ref']},sig=True,path=['data'])
    ls=d.get('subtitle',{}).get('subtitles',[])
    if not ls: print('[info] no subtitle'); return
    allx=lan.lower()=='all'; allow={x.strip() for x in lan.split(',') if x.strip()}
    for it in ls:
        l=it.get('lan') or 'unknown'
        if not allx and l not in allow: continue
        u=it.get('subtitle_url','');
        if u.startswith('//'):u='https:'+u
        if not u: continue
        sd=c.r('GET',u,headers={'Referer':e['ref']}).json(); fp=out/f"{bn}_{safe(l)}"
        if fmtx=='json': fp.with_suffix('.json').write_text(json.dumps(sd,ensure_ascii=False,indent=2),encoding='utf-8')
        elif fmtx=='srt': fp.with_suffix('.srt').write_text(to_srt(sd),encoding='utf-8')
        elif fmtx=='txt': fp.with_suffix('.txt').write_text(to_txt(sd),encoding='utf-8')
        elif fmtx=='lrc': fp.with_suffix('.lrc').write_text(to_lrc(sd),encoding='utf-8')
        else: raise E('unsupported subtitle-format')
        print(f"[ok] subtitle({l}): {fp}")

def danmaku(c:C,e:dict,out:Path,bn:str,fmtx:str):
    if fmtx=='none':return
    if fmtx!='xml': raise E('danmaku-format only supports none/xml in this skill version')
    u=f"https://api.bilibili.com/x/v1/dm/list.so?oid={e['cid']}"
    (out/f"{bn}.xml").write_bytes(c.r('GET',u,headers={'Referer':e['ref']}).content)
    print(f"[ok] danmaku(xml): {out/f'{bn}.xml'}")

def cover(c:C,e:dict,out:Path,bn:str):
    u=e.get('cover','')
    if not u: print('[info] no cover'); return
    ex=Path(urllib.parse.urlparse(u).path).suffix.lower() or '.jpg'
    if ex not in {'.jpg','.jpeg','.png','.webp','.avif'}: ex='.jpg'
    p=out/f"{bn}{ex}"; p.write_bytes(c.r('GET',u,headers={'Referer':e['ref']}).content); print(f"[ok] cover: {p}")

def meta(c:C,ctx:dict,e:dict,out:Path,bn:str,fmtx:str):
    if fmtx=='none':return
    own=ctx['detail'].get('owner') or {}
    m={'source_type':ctx['stype'],'original_url':ctx['url'],'normalized_url':ctx['norm'],'title':e['title'],'parent_title':e['full'],'description':ctx['detail'].get('desc') or ctx['detail'].get('evaluate',''),'bvid':e['bvid'],'aid':e['aid'],'cid':e['cid'],'ep_id':e['ep_id'],'duration':e['dur'],'uploader':own.get('name') or '','uploader_mid':own.get('mid') or 0,'cover_url':e.get('cover',''),'raw_episode':e}
    if fmtx=='json':
        (out/f"{bn}.metadata.json").write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8'); print(f"[ok] metadata(json): {out/f'{bn}.metadata.json'}")
        return
    if fmtx=='nfo':
        nfo=["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\" ?>","<movie>",f"  <title>{m['title']}</title>",f"  <plot>{m['description']}</plot>",f"  <director>{m['uploader']}</director>",f"  <uniqueid type=\"bvid\">{m['bvid']}</uniqueid>","</movie>"]
        (out/f"{bn}.nfo").write_text('\\n'.join(nfo),encoding='utf-8'); print(f"[ok] metadata(nfo): {out/f'{bn}.nfo'}")
        return
    raise E('unsupported metadata-format')


def probe(a):
    cookie,sessdata=_resolve_cookie_inputs(a)
    c=C(cookie,sessdata); x=parse_ctx(c,a.url); e=x['eps'][x['defi']]; d=play(c,e,0)
    s={'source_type':x['stype'],'normalized_url':x['norm'],'episode_count':len(x['eps']),'default_episode':x['defi']+1,'episodes':[{'index':i+1,'title':k['title'],'cid':k['cid'],'ep_id':k['ep_id'],'duration_sec':k['dur']} for i,k in enumerate(x['eps'])]}
    t=stype(d); s['stream_type']=t
    if t=='DASH':
        v=d.get('dash',{}).get('video',[]); au=audios(d.get('dash',{}))
        s['video_quality_ids']=sorted(set(int(i.get('id',0)) for i in v if i.get('id')),reverse=True)
        s['video_codec_ids']=sorted(set(int(i.get('codecid',0)) for i in v if i.get('codecid')))
        s['audio_quality_ids']=sorted(set(int(i.get('id',0)) for i in au if i.get('id')),reverse=True)
    else: s['accept_quality']=d.get('accept_quality',[])
    print(json.dumps(s,ensure_ascii=False,indent=2)); return 0

def download(a):
    cookie,sessdata=_resolve_cookie_inputs(a)
    c=C(cookie,sessdata); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True); x=parse_ctx(c,a.url)
    sel=a.episode.strip().lower()
    if sel=='all': ids=list(range(len(x['eps'])))
    elif sel=='current': ids=[x['defi']]
    else:
        ids=[]
        for p in sel.split(','):
            i=int(p.strip())-1
            if i<0 or i>=len(x['eps']): raise E(f'episode out of range: {p}')
            ids.append(i)
        ids=sorted(set(ids))
    print(f"[info] source={x['stype']}, episodes={len(x['eps'])}, selected={','.join(str(i+1) for i in ids)}")
    for n,i in enumerate(ids,1):
        e=x['eps'][i]; bn=fmt(a.filename_template,{'title':e['title'],'full_title':e['full'],'bvid':e['bvid'],'aid':e['aid'],'cid':e['cid'],'ep_id':e['ep_id'],'index':n,'global_index':i+1})
        print(f"[info] processing episode {i+1}: {e['title']}")
        if a.content!='none':
            d=play(c,e,0 if a.video_quality=='auto' else int(a.video_quality)); t=stype(d); print(f"[info] stream={t}")
            if t=='DASH':
                ds=d.get('dash',{}); vn=ds.get('video',[]); an=audios(ds)
                vf=af=None
                if a.content in ('video','video_audio'):
                    vq=qpick([int(z.get('id',0)) for z in vn if z.get('id')],a.video_quality,VQ)
                    avail=[int(z.get('codecid',0)) for z in vn if int(z.get('id',0))==vq]
                    cset=sorted(set(avail));
                    cc=CM.get(a.video_codec.lower()) if a.video_codec.lower() in CM else int(a.video_codec)
                    if cc==20:
                        for pr in (7,12,13):
                            if pr in cset: cc=pr; break
                    if cc not in cset and cset: cc=cset[0]
                    v=next((z for z in vn if int(z.get('id',0))==vq and int(z.get('codecid',0))==cc),None)
                    if not v: raise E('no matching video stream')
                    vf=out/f"{bn}.video.m4s"; dl(c,urls(v),vf,e['ref'],'video')
                if a.content in ('audio','video_audio'):
                    aq=qpick([int(z.get('id',0)) for z in an if z.get('id')],a.audio_quality,AQ)
                    u=next((z for z in an if int(z.get('id',0))==aq),None)
                    if not u: raise E('no matching audio stream')
                    af=out/f"{bn}.audio.{AE.get(aq,'m4a')}"; dl(c,urls(u),af,e['ref'],'audio')
                if a.content=='video_audio' and not a.no_merge:
                    if not vf or not af: raise E('cannot merge without video+audio')
                    merge(a.ffmpeg,vf,af,out/f"{bn}.mp4")
                if a.content=='audio' and a.audio_format!='keep':
                    if not af: raise E('no audio file to convert')
                    conv(a.ffmpeg,af,out/f"{bn}.{a.audio_format}")
            elif t in ('FLV','MP4'):
                durl=d.get('durl') or ([x.get('durl',[{}])[0] for x in d.get('durls',[]) if x.get('durl')] if d.get('durls') else [])
                if not durl: raise E('no durl stream')
                ex='flv' if t=='FLV' else 'mp4'
                if len(durl)==1: dl(c,urls(durl[0]),out/f"{bn}.{ex}",e['ref'],t.lower())
                else:
                    for j,node in enumerate(durl,1): dl(c,urls(node),out/f"{bn}.part{j}.{ex}",e['ref'],f"{t.lower()}-part{j}")
            else: raise E(f'unsupported stream type: {t}')
        sub(c,e,out,bn,a.subtitle_format,a.subtitle_lang); danmaku(c,e,out,bn,a.danmaku_format)
        if a.cover: cover(c,e,out,bn)
        meta(c,x,e,out,bn,a.metadata_format)
    print('[done] all tasks complete'); return 0


def build():
    p=argparse.ArgumentParser(prog='bili23_agent_cli',description='Bili23-style downloader CLI for AI skill workflows')
    s=p.add_subparsers(dest='cmd',required=True)
    b=argparse.ArgumentParser(add_help=False)
    b.add_argument('--url',required=True); b.add_argument('--bili-cookie',default=''); b.add_argument('--sessdata',default='')
    pr=s.add_parser('probe',parents=[b]); pr.set_defaults(f=probe)
    d=s.add_parser('download',parents=[b])
    d.add_argument('--output',default='./download'); d.add_argument('--episode',default='current')
    d.add_argument('--content',choices=['video_audio','video','audio','none'],default='video_audio')
    d.add_argument('--video-quality',default='auto'); d.add_argument('--audio-quality',default='auto'); d.add_argument('--video-codec',default='auto')
    d.add_argument('--no-merge',action='store_true'); d.add_argument('--ffmpeg',default='ffmpeg')
    d.add_argument('--audio-format',default='keep',choices=['keep','mp3','m4a','flac','wav'])
    d.add_argument('--subtitle-format',default='none',choices=['none','srt','txt','lrc','json']); d.add_argument('--subtitle-lang',default='all')
    d.add_argument('--danmaku-format',default='none',choices=['none','xml']); d.add_argument('--cover',action='store_true')
    d.add_argument('--metadata-format',default='none',choices=['none','json','nfo'])
    d.add_argument('--filename-template',default='{title}')
    d.set_defaults(f=download)
    return p


def main(argv=None):
    a=build().parse_args(argv)
    try:return int(a.f(a))
    except requests.HTTPError as ex: print(f'[error] HTTP error: {ex}',file=sys.stderr); return 2
    except E as ex: print(f'[error] {ex}',file=sys.stderr); return 3
    except subprocess.CalledProcessError as ex: print(f'[error] external command failed: {ex}',file=sys.stderr); return 4
    except KeyboardInterrupt: print('[error] interrupted',file=sys.stderr); return 130

if __name__=='__main__': raise SystemExit(main())
