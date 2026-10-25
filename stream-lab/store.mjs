import {DatabaseSync} from 'node:sqlite';
import {mkdirSync,readFileSync,writeFileSync,chmodSync} from 'node:fs';
import path from 'node:path';
import {randomBytes,randomUUID,scryptSync,timingSafeEqual,createHash,createCipheriv,createDecipheriv} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
export const defaults={method:'bitmap',resolution:540,fps:20};
const hash=value=>createHash('sha256').update(value).digest('hex');
export class Store{
 constructor(directory){mkdirSync(directory,{recursive:true,mode:0o700});chmodSync(directory,0o700);const keyPath=path.join(directory,'secret.key');try{this.key=readFileSync(keyPath);}catch(error){if(error.code!=='ENOENT')throw error;this.key=randomBytes(32);writeFileSync(keyPath,this.key,{mode:0o600,flag:'wx'});}this.db=new DatabaseSync(path.join(directory,'accounts.sqlite'));this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,settings TEXT NOT NULL,admin INTEGER DEFAULT 0,created INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,expires INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS playlists(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,url TEXT NOT NULL,cache TEXT,updated INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS favorites(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,channel_id TEXT NOT NULL,PRIMARY KEY(user_id,channel_id));
 CREATE TABLE IF NOT EXISTS plex(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,url TEXT NOT NULL,token TEXT NOT NULL,client_id TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS history(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,source_id TEXT NOT NULL,connection_id TEXT REFERENCES plex(id) ON DELETE CASCADE,item_id TEXT,details TEXT NOT NULL,viewed INTEGER NOT NULL,PRIMARY KEY(user_id,kind,source_id));
 CREATE TABLE IF NOT EXISTS progress(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,connection_id TEXT REFERENCES plex(id) ON DELETE CASCADE,item_id TEXT,position REAL,duration REAL,title TEXT,updated INTEGER,PRIMARY KEY(user_id,connection_id,item_id));`);this.db.prepare('DELETE FROM sessions WHERE expires < ?').run(Date.now());}
 seal(value){const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',this.key,iv);return Buffer.concat([iv,cipher.update(typeof value==='string'?value:JSON.stringify(value)),cipher.final(),cipher.getAuthTag()]).toString('base64');}
 open(value){const b=Buffer.from(value,'base64'),decipher=createDecipheriv('aes-256-gcm',this.key,b.subarray(0,12));decipher.setAuthTag(b.subarray(-16));return Buffer.concat([decipher.update(b.subarray(12,-16)),decipher.final()]).toString();}
 password(value){const salt=randomBytes(16).toString('hex');return salt+':'+scryptSync(value,salt,64).toString('hex');}
 verify(value,encoded){const [salt,digest]=encoded.split(':');const actual=scryptSync(value,salt,64),expected=Buffer.from(digest,'hex');return expected.length===actual.length&&timingSafeEqual(actual,expected);}
 createUser(username,name,password,admin=false){if(!/^[a-zA-Z0-9_.-]{3,32}$/.test(username))throw Error('Gebruik 3–32 letters, cijfers, punten of streepjes voor je gebruikersnaam.');if(typeof password!=='string'||password.length<10||password.length>128)throw Error('Kies een wachtwoord van 10 tot 128 tekens.');if(this.db.prepare('SELECT id FROM users WHERE username=?').get(username))throw Error('Deze gebruikersnaam bestaat al.');const id=randomUUID();this.db.prepare('INSERT INTO users VALUES(?,?,?,?,?,?,?)').run(id,username,String(name||username).slice(0,60),this.password(password),JSON.stringify(defaults),admin?1:0,Date.now());return this.user(id);}
 user(id){const u=this.db.prepare('SELECT * FROM users WHERE id=?').get(id);return u?{...u,settings:{...defaults,...JSON.parse(u.settings)}}:null;}
 publicUser(u){return {id:u.id,username:u.username,name:u.name,settings:u.settings};}
 login(username,password){const row=this.db.prepare('SELECT * FROM users WHERE username=?').get(String(username));if(!row||typeof password!=='string'||password.length>128||!this.verify(password,row.password))throw Error('Gebruikersnaam of wachtwoord is onjuist.');return this.user(row.id);}
 session(userId){const token=randomBytes(32).toString('base64url');this.db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(hash(token),userId,Date.now()+30*86400000);return token;}
 authenticate(token){if(!token)return null;const row=this.db.prepare('SELECT * FROM sessions WHERE token=? AND expires>?').get(hash(token),Date.now());return row?{...this.user(row.user_id),authId:hash(token)}:null;}
 logout(token){if(token)this.db.prepare('DELETE FROM sessions WHERE token=?').run(hash(token));}
 settings(userId,value){const next={method:value.method,resolution:Number(value.resolution),fps:Number(value.fps)};if(!['bitmap','mjpeg','webcodecs','webgl'].includes(next.method)||![360,480,540,720,1080].includes(next.resolution)||![20,24,25,30,50,60].includes(next.fps))throw Error('Kies een geldige methode, resolutie en framerate.');this.db.prepare('UPDATE users SET settings=? WHERE id=?').run(JSON.stringify(next),userId);return next;}
 changePassword(user,current,next){if(!this.verify(current,user.password))throw Error('Je huidige wachtwoord is onjuist.');if(typeof next!=='string'||next.length<10||next.length>128)throw Error('Kies een wachtwoord van 10 tot 128 tekens.');this.db.prepare('UPDATE users SET password=? WHERE id=?').run(this.password(next),user.id);this.db.prepare('DELETE FROM sessions WHERE user_id=? AND token<>?').run(user.id,user.authId);}
 playlists(userId){return this.db.prepare('SELECT id,name,updated FROM playlists WHERE user_id=? ORDER BY rowid').all(userId);}
 playlist(userId,id){const p=this.db.prepare('SELECT * FROM playlists WHERE user_id=? AND id=?').get(userId,id);if(!p)return null;return {...p,url:this.open(p.url)};}
 addPlaylist(userId,name,url){const id=randomUUID();this.db.prepare('INSERT INTO playlists(id,user_id,name,url) VALUES(?,?,?,?)').run(id,userId,String(name||'Mijn TV').slice(0,80),this.seal(url));return id;}
 cachePlaylist(userId,id,items){const cache=this.seal(gzipSync(JSON.stringify(items)).toString('base64'));this.db.prepare('UPDATE playlists SET cache=?,updated=? WHERE id=? AND user_id=?').run(cache,Date.now(),id,userId);}
 cachedItems(p){return p.cache?JSON.parse(gunzipSync(Buffer.from(this.open(p.cache),'base64')).toString()):[];}
 deletePlaylist(userId,id){this.db.prepare("DELETE FROM history WHERE user_id=? AND kind='tv' AND source_id LIKE ?").run(userId,id+'_%');this.db.prepare('DELETE FROM favorites WHERE user_id=? AND channel_id LIKE ?').run(userId,id+'_%');this.db.prepare('DELETE FROM playlists WHERE user_id=? AND id=?').run(userId,id);}
 favorites(userId){return new Set(this.db.prepare('SELECT channel_id FROM favorites WHERE user_id=?').all(userId).map(x=>x.channel_id));}
 favorite(userId,id,on){if(on)this.db.prepare('INSERT OR IGNORE INTO favorites VALUES(?,?)').run(userId,id);else this.db.prepare('DELETE FROM favorites WHERE user_id=? AND channel_id=?').run(userId,id);}
 plexList(userId){return this.db.prepare('SELECT id,name,url FROM plex WHERE user_id=? ORDER BY rowid').all(userId);}
 plex(userId,id){const p=this.db.prepare('SELECT * FROM plex WHERE user_id=? AND id=?').get(userId,id);return p?{...p,token:this.open(p.token)}:null;}
 addPlex(userId,name,url,token,clientId=randomUUID()){const id=randomUUID();this.db.prepare('INSERT INTO plex VALUES(?,?,?,?,?,?)').run(id,userId,String(name||'Plex').slice(0,80),url,this.seal(token),clientId);return id;}
 deletePlex(userId,id){this.db.prepare('DELETE FROM plex WHERE id=? AND user_id=?').run(id,userId);}
 progress(userId,connectionId,itemId){return this.db.prepare('SELECT * FROM progress WHERE user_id=? AND connection_id=? AND item_id=?').get(userId,connectionId,itemId);}
 saveProgress(userId,connectionId,itemId,position,duration,title){this.db.prepare('INSERT INTO progress VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,connection_id,item_id) DO UPDATE SET position=excluded.position,duration=excluded.duration,title=excluded.title,updated=excluded.updated').run(userId,connectionId,itemId,position,duration,title,Date.now());}
 historyItem(userId,kind,sourceId){const row=this.db.prepare('SELECT details FROM history WHERE user_id=? AND kind=? AND source_id=?').get(userId,kind,sourceId);return row?JSON.parse(row.details):null;}
 historyProgress(userId,kind,sourceId,position,duration){const details=this.historyItem(userId,kind,sourceId);if(details){details.position=position;details.duration=duration;this.db.prepare('UPDATE history SET details=? WHERE user_id=? AND kind=? AND source_id=?').run(JSON.stringify(details),userId,kind,sourceId);}}
 history(userId){return this.db.prepare('SELECT * FROM history WHERE user_id=? ORDER BY viewed DESC LIMIT 24').all(userId).map(row=>({...row,details:JSON.parse(row.details)}));}
 viewed(userId,kind,sourceId,connectionId,itemId,details){this.db.prepare('INSERT INTO history VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,kind,source_id) DO UPDATE SET details=excluded.details,viewed=excluded.viewed').run(userId,kind,sourceId,connectionId||null,itemId||null,JSON.stringify(details),Date.now());this.db.prepare('DELETE FROM history WHERE user_id=? AND rowid NOT IN (SELECT rowid FROM history WHERE user_id=? ORDER BY viewed DESC LIMIT 100)').run(userId,userId);}
 close(){this.db.close();}
}
