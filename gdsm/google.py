from __future__ import annotations
import base64, hashlib, json, secrets, threading, time, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .models import DriveItem, Settings
class GoogleOAuth:
    def __init__(self,settings:Settings,on_refresh): self.s=settings; self.on_refresh=on_refresh; self.access=''; self.expiry=0
    def token(self)->str:
        if self.access and time.time()<self.expiry: return self.access
        if self.s.refresh_token:
            try: return self._exchange({'client_id':self.s.client_id,'refresh_token':self.s.refresh_token,'grant_type':'refresh_token'})
            except Exception: pass
        return self._interactive()
    def _exchange(self,data):
        req=urllib.request.Request('https://oauth2.googleapis.com/token',urllib.parse.urlencode(data).encode(),method='POST')
        with urllib.request.urlopen(req,timeout=30) as res: payload=json.load(res)
        self.access=payload['access_token']; self.expiry=time.time()+max(60,int(payload.get('expires_in',3600))-60)
        if payload.get('refresh_token'):
            self.s.refresh_token=payload['refresh_token']; self.on_refresh(self.s)
        return self.access
    def _interactive(self):
        if not self.s.client_id: raise RuntimeError('Configure the Google OAuth Desktop Client ID first.')
        verifier=base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b'=').decode(); challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(); state=secrets.token_urlsafe(24)
        result={}; ready=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query); result['code']=q.get('code',[''])[0]; result['state']=q.get('state',[''])[0]; self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(b'<h2>Authentication completed. You may close this tab.</h2>'); ready.set()
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler); redirect=f'http://127.0.0.1:{server.server_port}/'; thread=threading.Thread(target=server.handle_request,daemon=True); thread.start()
        params={'client_id':self.s.client_id,'redirect_uri':redirect,'response_type':'code','scope':'https://www.googleapis.com/auth/drive','access_type':'offline','prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256','state':state}
        webbrowser.open('https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params))
        if not ready.wait(300): server.server_close(); raise TimeoutError('Google sign-in timed out')
        server.server_close()
        if result.get('state')!=state or not result.get('code'): raise RuntimeError('OAuth cancelled or state validation failed')
        return self._exchange({'code':result['code'],'client_id':self.s.client_id,'redirect_uri':redirect,'grant_type':'authorization_code','code_verifier':verifier})
class DriveApi:
    def __init__(self,oauth:GoogleOAuth): self.oauth=oauth
    def _request(self,url,method='GET',body=None,headers=None):
        h={'Authorization':'Bearer '+self.oauth.token(),**(headers or {})}; req=urllib.request.Request(url,data=body,headers=h,method=method)
        return urllib.request.urlopen(req,timeout=60)
    def inventory(self):
        all_items=[]; page=None; fields='nextPageToken,files(id,name,mimeType,size,quotaBytesUsed,md5Checksum,modifiedTime,parents,owners(displayName),capabilities(canDownload,canTrash))'
        while True:
            q={'pageSize':'1000','q':'trashed = false','orderBy':'quotaBytesUsed desc','fields':fields}
            if page:q['pageToken']=page
            with self._request('https://www.googleapis.com/drive/v3/files?'+urllib.parse.urlencode(q)) as r: data=json.load(r)
            for x in data.get('files',[]):
                mime=x['mimeType']; caps=x.get('capabilities',{}); raw=x.get('quotaBytesUsed',x.get('size','0'))
                try:size=int(raw)
                except (ValueError,TypeError):size=0
                owners=x.get('owners',[]); owner=owners[0].get('displayName','') if owners else ''
                all_items.append(DriveItem(x['id'],x['name'],mime,size,x.get('md5Checksum'),x.get('modifiedTime',''),owner,tuple(x.get('parents',[])),bool(caps.get('canDownload')),bool(caps.get('canTrash')),mime=='application/vnd.google-apps.folder',mime.startswith('application/vnd.google-apps.') and mime!='application/vnd.google-apps.folder'))
            page=data.get('nextPageToken')
            if not page: return all_items
    def binary_url(self,item): return 'https://www.googleapis.com/drive/v3/files/'+urllib.parse.quote(item.id,safe='')+'?alt=media'
    def download_request(self,item,offset=0):
        h={'Authorization':'Bearer '+self.oauth.token()}
        if offset:h['Range']=f'bytes={offset}-'
        return urllib.request.Request(self.binary_url(item),headers=h)
    def trash(self,item):
        data=b'{"trashed":true}'; headers={'Content-Type':'application/json'}
        with self._request('https://www.googleapis.com/drive/v3/files/'+urllib.parse.quote(item.id,safe=''),method='PATCH',body=data,headers=headers): pass
