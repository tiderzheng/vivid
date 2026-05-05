#!/usr/bin/env python3
from __future__ import annotations
import argparse, hmac, io, json, os, random, re, shutil, struct, subprocess, sys, time, urllib.parse
from hashlib import md5, sha256
from pathlib import Path
from typing import Any
import requests

MIX=[46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
VQ=[127,126,125,120,116,112,100,80,64,32,16]
AQ=[30251,30250,30280,30232,30216]
CM={"auto":20,"avc":7,"h264":7,"hevc":12,"h265":12,"av1":13}
AE={30251:"flac",30250:"ec3",30280:"m4a",30232:"m4a",30216:"m4a"}
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
RF="https://www.bilibili.com/"
HX="0123456789ABCDEF"
UUID_CHARS=list("123456789ABCDEF")+["10"]
BILI23_MANAGED_COOKIE_KEYS={
    '_uuid','b_lsid','b_nut','bili_ticket','bili_ticket_expires',
    'buvid_fp','buvid3','buvid4','CURRENT_FNVAL','CURRENT_QUALITY',
}

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
    return f"{'-'.join(''.join(random.choice(UUID_CHARS) for _ in range(length)) for length in (8,4,4,4,12))}{str(now % 100000).ljust(5,'0')}infoc"

def _generate_b_lsid(now:int)->str:
    return f"{''.join(hex(random.randint(0,15))[2:].upper() for _ in range(8))}_{hex(now)[2:].upper()}"

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

def _generate_buvid_fp(key:str=UA,seed:int=31)->str:
    def rotate_left(x:int,k:int)->int:
        b=bin(x)[2:].rjust(64,'0')
        return int(b[k:]+b[:k],2)
    def fmix64(k:int)->int:
        k^=k>>33; k=k*0xFF51AFD7ED558CCD%mod
        k^=k>>33; k=k*0xC4CEB9FE1A85EC53%mod
        k^=k>>33
        return k
    mod=1<<64
    c1=0x87C37B91114253D5; c2=0x4CF5AD432745937F
    c3=0x52DCE729; c4=0x38495AB5
    h1=h2=seed; processed=0
    source=io.BytesIO(key.encode('ascii','ignore'))
    while True:
        data=source.read(16); processed+=len(data)
        if len(data)==16:
            k1=struct.unpack('<q',data[:8])[0]; k2=struct.unpack('<q',data[8:])[0]
            h1^=rotate_left(k1*c1%mod,31)*c2%mod
            h1=((rotate_left(h1,27)+h2)*5+c3)%mod
            h2^=rotate_left(k2*c2%mod,33)*c1%mod
            h2=((rotate_left(h2,31)+h1)*5+c4)%mod
            continue
        if len(data):
            k1=0; k2=0
            for i in range(min(len(data),8)):
                k1^=data[i]<<(i*8)
            for i in range(8,len(data)):
                k2^=data[i]<<((i-8)*8)
            if k1:
                h1^=rotate_left(k1*c1%mod,31)*c2%mod
            if k2:
                h2^=rotate_left(k2*c2%mod,33)*c1%mod
        h1^=processed; h2^=processed
        h1=(h1+h2)%mod; h2=(h2+h1)%mod
        h1=fmix64(h1); h2=fmix64(h2)
        h1=(h1+h2)%mod; h2=(h2+h1)%mod
        return f"{h1:x}{h2:x}"

def _fetch_bili_ticket(session:requests.Session,csrf:str='')->dict[str,str]:
    now=int(time.time())
    try:
        params={
            'key_id':'ec02',
            'hexsign':hmac.new(b'XgwSnGZ1p',f'ts{now}'.encode(),sha256).hexdigest(),
            'context[ts]':f'{now}',
            'csrf':csrf,
        }
        data=session.post('https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket',params=params,timeout=10).json()
    except Exception:
        return {}
    if data.get('code',0)!=0:return {}
    inner=data.get('data') or {}
    ticket=str(inner.get('ticket') or '').strip()
    if not ticket:return {}
    return {'bili_ticket':ticket,'bili_ticket_expires':str(now+3*24*3600)}

def _exclimbwuzhi_payload(user_agent:str,uuid:str)->str:
    now_ms=int(time.time()*1000)
    payload={
        '3064':1,
        '5062':str(now_ms),
        '03bf':'https%3A%2F%2Fwww.bilibili.com%2F',
        '39c8':'333.1007.fp.risk',
        '34f1':'',
        'd402':'',
        '654a':'',
        '6e7c':'1699x794',
        '3c43':{
            '2673':0,
            '5766':32,
            '6527':0,
            '7003':1,
            '807e':1,
            'b8ce':user_agent,
            '641c':0,
            '07a4':'zh-CN',
            '1c57':32,
            '0bd0':20,
            '748e':[960,1707],
            'd61f':[912,1707],
            'fc9d':-480,
            '6aa9':'Asia/Shanghai',
            '75b8':1,
            '3b21':1,
            '8a1c':0,
            'd52f':'not available',
            'adca':'Win32',
            '80c9':[
                ['PDF Viewer','Portable Document Format',[['application/pdf','pdf'],['text/pdf','pdf']]],
                ['Chrome PDF Viewer','Portable Document Format',[['application/pdf','pdf'],['text/pdf','pdf']]],
                ['Chromium PDF Viewer','Portable Document Format',[['application/pdf','pdf'],['text/pdf','pdf']]],
                ['Microsoft Edge PDF Viewer','Portable Document Format',[['application/pdf','pdf'],['text/pdf','pdf']]],
                ['WebKit built-in PDF','Portable Document Format',[['application/pdf','pdf'],['text/pdf','pdf']]],
            ],
            '13ab':'EPQAAAAASUVORK5CYII=',
            'bfe9':'//TgNIfAAAAAZJREFUAwBde+3wgcxEHQAAAABJRU5ErkJggg==',
            'a3c1':[
                'extensions:ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode',
                'webgl aliased line width range:[1, 1]',
                'webgl aliased point size range:[1, 1024]',
                'webgl alpha bits:8',
                'webgl antialiasing:yes',
                'webgl blue bits:8',
                'webgl depth bits:24',
                'webgl green bits:8',
                'webgl max anisotropy:16',
                'webgl max combined texture image units:32',
                'webgl max cube map texture size:16384',
                'webgl max fragment uniform vectors:1024',
                'webgl max render buffer size:16384',
                'webgl max texture image units:16',
                'webgl max texture size:16384',
                'webgl max varying vectors:30',
                'webgl max vertex attribs:16',
                'webgl max vertex texture image units:16',
                'webgl max vertex uniform vectors:4095',
                'webgl max viewport dims:[32767, 32767]',
                'webgl red bits:8',
                'webgl renderer:WebKit WebGL',
                'webgl shading language version:WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)',
                'webgl stencil bits:0',
                'webgl vendor:WebKit',
                'webgl version:WebGL 1.0 (OpenGL ES 2.0 Chromium)',
                'webgl unmasked vendor:Google Inc. (NVIDIA)',
                'webgl unmasked renderer:ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU (0x000028E0) Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'webgl vertex shader high float precision:23',
                'webgl vertex shader high float precision rangeMin:127',
                'webgl vertex shader high float precision rangeMax:127',
                'webgl vertex shader medium float precision:23',
                'webgl vertex shader medium float precision rangeMin:127',
                'webgl vertex shader medium float precision rangeMax:127',
                'webgl vertex shader low float precision:23',
                'webgl vertex shader low float precision rangeMin:127',
                'webgl vertex shader low float precision rangeMax:127',
                'webgl fragment shader high float precision:23',
                'webgl fragment shader high float precision rangeMin:127',
                'webgl fragment shader high float precision rangeMax:127',
                'webgl fragment shader medium float precision:23',
                'webgl fragment shader medium float precision rangeMin:127',
                'webgl fragment shader medium float precision rangeMax:127',
                'webgl fragment shader low float precision:23',
                'webgl fragment shader low float precision rangeMin:127',
                'webgl fragment shader low float precision rangeMax:127',
                'webgl vertex shader high int precision:0',
                'webgl vertex shader high int precision rangeMin:31',
                'webgl vertex shader high int precision rangeMax:30',
                'webgl vertex shader medium int precision:0',
                'webgl vertex shader medium int precision rangeMin:31',
                'webgl vertex shader medium int precision rangeMax:30',
                'webgl vertex shader low int precision:0',
                'webgl vertex shader low int precision rangeMin:31',
                'webgl vertex shader low int precision rangeMax:30',
                'webgl fragment shader high int precision:0',
                'webgl fragment shader high int precision rangeMin:31',
                'webgl fragment shader high int precision rangeMax:30',
                'webgl fragment shader medium int precision:0',
                'webgl fragment shader medium int precision rangeMin:31',
                'webgl fragment shader medium int precision rangeMax:30',
                'webgl fragment shader low int precision:0',
                'webgl fragment shader low int precision rangeMin:31',
                'webgl fragment shader low int precision rangeMax:30',
            ],
            '6bc5':'Google Inc. (NVIDIA)~ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU (0x000028E0) Direct3D11 vs_5_0 ps_5_0, D3D11)',
            'ed31':0,
            '72bd':0,
            '097b':0,
            '52cd':[0,0,0],
            'a658':[
                'Arial','Arial Black','Arial Narrow','Book Antiqua','Bookman Old Style','Calibri',
                'Cambria','Cambria Math','Century','Century Gothic','Century Schoolbook',
                'Comic Sans MS','Consolas','Courier','Courier New','Georgia','Helvetica',
                'Impact','Lucida Bright','Lucida Calligraphy','Lucida Console','Lucida Fax',
                'Lucida Handwriting','Lucida Sans','Lucida Sans Typewriter','Lucida Sans Unicode',
                'Microsoft Sans Serif','Monotype Corsiva','MS Gothic','MS PGothic',
                'MS Reference Sans Serif','MS Sans Serif','MS Serif','Palatino Linotype',
                'Segoe Print','Segoe Script','Segoe UI','Segoe UI Light','Segoe UI Semibold',
                'Segoe UI Symbol','Tahoma','Times','Times New Roman','Trebuchet MS','Verdana',
                'Wingdings','Wingdings 2','Wingdings 3',
            ],
            'd02f':'124.04347527516074',
        },
        '54ef':'{"b_ut":"","home_version":"V8","in_new_ab":true,"ab_version":{"for_ai_home_version":"V8","in_theme_version":"OPEN","enable_web_push":"DISABLE","enable_ai_floor_api":"ENABLE","enable_shortcut_key":"DISABLE","rcmd_timeout_config":"550","home_performance_opt":"ssr_fetch_opt","infra_projection":"OFF"},"ab_split_num":{"for_ai_home_version":54,"in_theme_version":30,"enable_web_push":10,"enable_ai_floor_api":137,"enable_shortcut_key":54,"rcmd_timeout_config":49,"home_performance_opt":49,"infra_projection":49},"uniq_page_id":"1671272756362","is_modern":true}',
        '8b94':'',
        'df35':uuid,
        '07a4':'zh-CN',
        '5f45':None,
        'db46':0,
    }
    return json.dumps({'payload':json.dumps(payload,separators=(',',':'))},separators=(',',':'))

def _activate_buvid(session:requests.Session,values:dict[str,str])->None:
    uuid=values.get('_uuid') or ''
    if not uuid:return
    try:
        session.post(
            'https://api.bilibili.com/x/internal/gaia-gateway/ExClimbWuzhi',
            data=_exclimbwuzhi_payload(UA,uuid),
            headers={'Content-Type':'application/json','User-Agent':UA,'Referer':RF},
            timeout=10,
        )
    except Exception:
        return

def _set_session_cookies(session:requests.Session,values:dict[str,str])->None:
    for k,v in values.items():
        session.cookies.set(k,v,domain='.bilibili.com',path='/')

def _build_cookie_values(cookie:str='',sessdata:str='',session:requests.Session|None=None)->dict[str,str]:
    values=_parse_cookie_header(cookie)
    if sessdata and 'SESSDATA' not in values:
        values['SESSDATA']=sessdata
    values={k:v for k,v in values.items() if k not in BILI23_MANAGED_COOKIE_KEYS}
    now=int(time.time())
    values['_uuid']=_generate_uuid_cookie(now)
    values['b_lsid']=_generate_b_lsid(now)
    values['b_nut']=str(now)
    values['CURRENT_FNVAL']='4048'
    values['CURRENT_QUALITY']='0'
    if session:
        spi=_fetch_spi_buvids(session)
        if spi.get('buvid3'):
            values['buvid3']=spi['buvid3']
        if spi.get('buvid4'):
            values['buvid4']=spi['buvid4']
    values['buvid_fp']=_generate_buvid_fp(UA,31)
    return values

def _resolve_cookie_inputs(a:Any)->tuple[str,str]:
    cookie=str(getattr(a,'bili_cookie','') or os.environ.get('VIVID_BILI_COOKIE','') or os.environ.get('BILI_COOKIE','') or os.environ.get('BILI_COOKIE_HEADER','')).strip()
    sessdata=str(getattr(a,'sessdata','') or os.environ.get('BILI_SESSDATA','')).strip()
    return cookie,sessdata

class C:
    def __init__(self,cookie:str='',sessdata:str=''):
        self.s=requests.Session(); self.s.headers.update({'User-Agent':UA,'Referer':RF}); self.k=None
        base_values=_parse_cookie_header(cookie)
        if sessdata and 'SESSDATA' not in base_values:
            base_values['SESSDATA']=sessdata
        _set_session_cookies(self.s,{k:v for k,v in base_values.items() if k not in BILI23_MANAGED_COOKIE_KEYS})
        values=_build_cookie_values(cookie,sessdata,self.s)
        csrf=values.get('bili_jct','')
        _set_session_cookies(self.s,values)
        for k,v in _fetch_bili_ticket(self.s,csrf).items():
            values[k]=v
            self.s.cookies.set(k,v,domain='.bilibili.com',path='/')
        _activate_buvid(self.s,values)
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
    ep=re.search(r'ep(\d+)',nu,re.I); ss=re.search(r'ss(\d+)',nu,re.I); mdx=re.search(r'md(\d+)',nu,re.I)
    bv=re.search(r'(BV[0-9A-Za-z]+)',nu); av=re.search(r'av(\d+)',nu,re.I)
    if ep or ss or mdx:
        if ep:
            p={'ep_id':int(ep.group(1))}
        elif ss:
            p={'season_id':int(ss.group(1))}
        else:
            media=c.j('https://api.bilibili.com/pgc/review/user',{'media_id':int(mdx.group(1))})
            season_id=(media.get('result') or {}).get('media',{}).get('season_id')
            if not season_id: raise E('no season_id from media url')
            p={'season_id':int(season_id)}
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
    candidates=_ordered_candidate_urls(c,ul,ref)
    for i,u in enumerate(candidates,1):
        try:
            with c.r('GET',u,headers={'Referer':ref},stream=True) as r:
                with out.open('wb') as f:
                    for b in r.iter_content(1024*128):
                        if b:f.write(b)
            print(f"[ok] {label}: {out}"); return
        except Exception as ex:
            last=ex; print(f"[warn] {label} mirror#{i} failed")
    raise E(f"all mirrors failed for {label}: {last}")

def _ordered_candidate_urls(c:C,ul:list[str],ref:str)->list[str]:
    valid,unknown=_classify_candidate_urls(c,ul,ref)
    ret=[]
    seen=set()
    for u in valid+unknown:
        if u not in seen:
            ret.append(u); seen.add(u)
    return ret or ul

def _classify_candidate_urls(c:C,ul:list[str],ref:str)->tuple[list[str],list[str]]:
    valid=[]
    unknown=[]
    for u in ul:
        try:
            h=c.r('HEAD',u,headers={'Referer':ref}).headers
        except Exception:
            unknown.append(u)
            continue
        ct=str(h.get('Content-Type') or h.get('content-type') or '').lower()
        cl=str(h.get('Content-Length') or h.get('content-length') or '')
        if not ct or 'text' in ct:
            continue
        if not cl.isdigit() or int(cl)<=10240:
            unknown.append(u)
            continue
        valid.append(u)
    return valid,unknown

def _valid_urls(c:C,ul:list[str],ref:str)->list[str]:
    valid,_unknown=_classify_candidate_urls(c,ul,ref)
    return valid

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
