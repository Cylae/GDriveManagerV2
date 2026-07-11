from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from .models import Settings
class JsonStore:
    def __init__(self,path:Path): self.path=path
    def load(self)->Settings:
        if not self.path.exists(): return Settings()
        try: return Settings.from_json(json.loads(self.path.read_text(encoding='utf-8')))
        except (json.JSONDecodeError,ValueError,TypeError):
            self.path.replace(self.path.with_suffix(self.path.suffix+'.corrupt'))
            return Settings()
    def save(self,settings:Settings)->None:
        settings.validate(); self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.config-',dir=self.path.parent,text=True)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(settings.to_json(),f,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
            try: os.chmod(self.path,0o600)
            except OSError: pass
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
class Logger:
    def __init__(self,path:Path): self.path=path
    def write(self,level:str,message:str,**data):
        import datetime
        self.path.parent.mkdir(parents=True,exist_ok=True)
        row={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'level':level,'message':message,'data':data}
        with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
