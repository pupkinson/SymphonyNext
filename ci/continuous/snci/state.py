"""One durable attempt per immutable input tuple; no implicit retry of writes."""
import datetime
import json
import sqlite3
from .common import canonical, require, sha256

class Journal:
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, target TEXT NOT NULL, policy TEXT NOT NULL, day TEXT NOT NULL, state TEXT NOT NULL, data TEXT NOT NULL)')
    def close(self):self.db.close()
    def claim(self,target,policy,limit):
        key=sha256(canonical([target,policy]));day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM attempts WHERE key=?',(key,)).fetchone():
                self.db.rollback();return None
            n=self.db.execute('SELECT count(*) FROM attempts WHERE day=?',(day,)).fetchone()[0]
            require(n<limit,'daily_budget')
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)',(key,json.dumps(target),policy,day,'running','{}'))
            self.db.commit();return key
        except BaseException:self.db.rollback();raise
    def set(self,key,state,data):
        require(state in ('running','publishing','success','hold','stale'),'state')
        with self.db:
            old=self.get(key)
            require(old is not None and old['state'] not in ('success','hold','stale'),'terminal_attempt')
            require(old['state']!='publishing' or state in ('publishing','success','hold','stale'),'publication_no_retry')
            self.db.execute('UPDATE attempts SET state=?,data=? WHERE key=?',(state,json.dumps(data,sort_keys=True),key))
    def get(self,key):
        row=self.db.execute('SELECT * FROM attempts WHERE key=?',(key,)).fetchone()
        if row is None:return None
        out=dict(row);out['target']=json.loads(out['target']);out['data']=json.loads(out['data']);return out
    def pending(self):
        return [self.get(r[0]) for r in self.db.execute("SELECT key FROM attempts WHERE state IN ('running','publishing') ORDER BY rowid")]
