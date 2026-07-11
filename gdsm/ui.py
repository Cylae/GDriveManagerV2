from __future__ import annotations
import csv,queue,threading,tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,ttk
from .models import Settings
from .storage import JsonStore,Logger
from .google import GoogleOAuth,DriveApi
from .transfer import TransferEngine
from .safety import safe_target
class App:
 def __init__(self):
  self.home=Path.home()/'.gdrive-space-manager';self.store=JsonStore(self.home/'config.json');self.settings=self.store.load();self.log=Logger(self.home/'operations.jsonl');self.items=[];self.events=queue.Queue();self.cancel=threading.Event();self.root=tk.Tk();self.root.title('GDrive Space Manager — project_v0.2');self.root.geometry('1250x760');self._widgets();self.root.after(100,self._drain)
 def _widgets(self):
  top=ttk.Frame(self.root,padding=8);top.pack(fill='x');
  for text,cmd in [('Refresh',self.refresh),('Settings',self.settings_dialog),('Download selected',self.download),('Trash selected',self.trash),('Cancel',self.cancel.set),('Export CSV',self.export_csv)]:ttk.Button(top,text=text,command=cmd).pack(side='left',padx=3)
  row=ttk.Frame(self.root,padding=(8,0));row.pack(fill='x');ttk.Label(row,text='Destination').pack(side='left');self.dest=tk.StringVar(value=self.settings.destination);ttk.Entry(row,textvariable=self.dest).pack(side='left',fill='x',expand=True,padx=5);ttk.Button(row,text='Choose',command=self.choose).pack(side='left');self.search=tk.StringVar();self.search.trace_add('write',lambda *_:self.render());ttk.Entry(row,textvariable=self.search,width=30).pack(side='left',padx=5)
  cols=('name','path','type','size','modified','owner');self.tree=ttk.Treeview(self.root,columns=cols,show='headings',selectmode='extended');
  for c,w in zip(cols,(250,300,230,100,160,150)):self.tree.heading(c,text=c.title());self.tree.column(c,width=w,stretch=c in ('name','path','type'))
  self.tree.pack(fill='both',expand=True,padx=8,pady=8);self.progress=ttk.Progressbar(self.root,maximum=100);self.progress.pack(fill='x',padx=8);self.status=tk.StringVar(value='Ready');ttk.Label(self.root,textvariable=self.status,padding=8).pack(anchor='w');self.queue=ttk.Treeview(self.root,columns=('name','state','detail'),show='headings',height=8);[self.queue.heading(c,text=c.title()) for c in ('name','state','detail')];self.queue.pack(fill='x',padx=8,pady=8)
 def api(self):
  oauth=GoogleOAuth(self.settings,lambda s:self.store.save(s));return DriveApi(oauth)
 def choose(self):
  x=filedialog.askdirectory(initialdir=self.dest.get() or str(Path.home()));
  if x:self.dest.set(x);self.settings.destination=x;self.store.save(self.settings)
 def settings_dialog(self):
  w=tk.Toplevel(self.root);w.title('Settings');v=tk.StringVar(value=self.settings.client_id);ttk.Label(w,text='Google OAuth Desktop Client ID').pack(padx=15,pady=(15,2));ttk.Entry(w,textvariable=v,width=70).pack(padx=15);ttk.Label(w,text='A browser opens when a Drive action needs sign-in.').pack(padx=15,pady=8)
  def save():self.settings.client_id=v.get().strip();self.store.save(self.settings);w.destroy()
  ttk.Button(w,text='Save',command=save).pack(pady=15)
 def refresh(self):
  self.cancel.clear();self.status.set('Loading Drive inventory...');threading.Thread(target=self._refresh_worker,daemon=True).start()
 def _refresh_worker(self):
  try:self.events.put(('items',self.api().inventory()))
  except Exception as e:self.events.put(('error',str(e)))
 def render(self):
  q=self.search.get().lower();self.tree.delete(*self.tree.get_children())
  for i,item in enumerate(self.items):
   if q and q not in (item.name+' '+item.mime_type+' '+item.drive_path).lower():continue
   self.tree.insert('', 'end',iid=str(i),values=(item.name,item.drive_path,item.mime_type,item.size,item.modified,item.owner))
 def selected(self):return [self.items[int(x)] for x in self.tree.selection()]
 def download(self):
  chosen=[x for x in self.selected() if not x.is_folder]
  if not chosen:return messagebox.showinfo('GDrive','Select one or more files.')
  if not self.dest.get() or not Path(self.dest.get()).is_dir():return messagebox.showerror('GDrive','Choose an existing destination.')
  self.cancel.clear();self.status.set('Downloading...');threading.Thread(target=self._download_worker,args=(chosen,),daemon=True).start()
 def _download_worker(self,chosen):
  try:
   api=self.api();engine=TransferEngine(api,self.settings,self.log);jobs=[]
   for i in chosen:
    if i.is_native:self.events.put(('queue',(i.name,'skipped','Workspace export requires a separate export workflow')));continue
    jobs.append((i,safe_target(self.dest.get(),i.name)))
   total=sum(i.size for i,_ in jobs);done=0
   def progress(item,current,size,speed):self.events.put(('progress',(item.name,done+current,total,speed)))
   for item,result in engine.download_many(jobs,self.cancel,progress):
    done+=item.size if result[0] in ('verified','already_verified') else 0;self.events.put(('queue',(item.name,result[0],result[2])))
   self.events.put(('status','Queue complete'))
  except Exception as e:self.events.put(('error',str(e)))
 def trash(self):
  chosen=[x for x in self.selected() if x.can_trash]
  if not chosen:return
  if not messagebox.askyesno('Confirm Trash',f'Move {len(chosen)} selected Drive item(s) to Trash? This is not permanent deletion.'):return
  threading.Thread(target=self._trash_worker,args=(chosen,),daemon=True).start()
 def _trash_worker(self,chosen):
  try:
   api=self.api()
   for i in chosen:api.trash(i);self.events.put(('queue',(i.name,'trashed','Moved to Drive Trash')))
   self.events.put(('status','Trash operation complete'))
  except Exception as e:self.events.put(('error',str(e)))
 def export_csv(self):
  path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')]);
  if not path:return
  with open(path,'w',newline='',encoding='utf-8-sig') as f:
   w=csv.writer(f);w.writerow(['Name','Path','Mime type','Size','Modified','Owner']);w.writerows((x.name,x.drive_path,x.mime_type,x.size,x.modified,x.owner) for x in self.items)
  self.status.set('CSV exported: '+path)
 def _drain(self):
  try:
   while True:
    kind,data=self.events.get_nowait()
    if kind=='items':self.items=data;self.render();self.status.set(f'{len(data)} items loaded')
    elif kind=='queue':self.queue.insert('','end',values=data)
    elif kind=='progress':name,done,total,speed=data;self.progress['value']=0 if not total else done*100/total;self.status.set(f'{name} — {speed/1024/1024:.2f} MB/s')
    elif kind=='status':self.status.set(data)
    elif kind=='error':self.status.set(data);messagebox.showerror('GDrive error',data)
  except queue.Empty:pass
  self.root.after(100,self._drain)
 def run(self):self.root.mainloop()
