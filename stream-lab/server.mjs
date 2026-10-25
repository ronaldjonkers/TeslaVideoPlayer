import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {Store} from './store.mjs';
import {Plex} from './plex.mjs';
import {YouTube,youtubeId} from './youtube.mjs';
const youtube=new YouTube({imageBase:process.env.ALLOW_PRIVATE_NETWORKS==='1'?process.env.YT_TEST_IMAGE_BASE:undefined});
import {upstream,validUrl} from './network.mjs';
import {parsePlaylist} from './playlist.mjs';
import {profiles} from './media.mjs';
import {PlaybackSessions} from './playback.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const store=new Store(process.env.DATA_DIR||path.join(root,'data')),plex=new Plex(store),playback=new PlaybackSessions();
const host=process.env.HOST||'127.0.0.1',port=Number(process.env.PORT||8765);
const caches=new Map(),loads=new Map(),attempts=new Map();
const json=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
async function body(req){let data='';for await(const chunk of req){data+=chunk;if(Buffer.byteLength(data)>64000)throw Error('Request too large.');}try{return data?JSON.parse(data):{};}catch{throw Error('Invalid request.');}}
function token(req){return /(?:^|;\s*)media_session=([^;]+)/.exec(req.headers.cookie||'')?.[1];}
function setCookie(req,res,value){const secure=req.headers['x-forwarded-proto']==='https'||req.socket.encrypted;res.setHeader('Set-Cookie',`media_session=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${value?2592000:0}${secure?'; Secure':''}`);}
function limit(req,action,max){const ip=req.headers['x-real-ip']||req.socket.remoteAddress;const key=action+':'+ip,now=Date.now();let item=attempts.get(key);if(!item||item.until<now)item={count:0,until:now+(action==='register'?3600000:600000)};item.count++;attempts.set(key,item);if(attempts.size>10000)for(const [k,v]of attempts)if(v.until<now)attempts.delete(k);if(item.count>max)throw Error('Too many attempts. Try again later.');}
function publicChannel(item,favs){return {id:item.id,name:item.name,group:item.group,playlistId:item.playlistId,logo:item.logo?'/api/tv/logo?id='+encodeURIComponent(item.id):null,favorite:favs.has(item.id)};}
async function playlistItems(user,p,refresh=false){if(!refresh&&p.updated&&p.updated>Date.now()-86400000){const cached=caches.get(p.id);if(cached?.updated===p.updated)return cached.items;const items=store.cachedItems(p);caches.set(p.id,{updated:p.updated,items});return items;}
 if(loads.has(p.id))return loads.get(p.id);const task=(async()=>{const result=await upstream(p.url,{allowPrivate:!!user.admin});if(!result.bytes.toString('utf8',0,100).trimStart().startsWith('#EXTM3U'))throw Error('The URL did not return an M3U playlist.');const items=parsePlaylist(result.bytes.toString(),result.url).map(item=>({...item,id:p.id+'_'+item.id,playlistId:p.id}));if(!items.length)throw Error('No HTTP(S) channels found.');store.cachePlaylist(user.id,p.id,items);const fresh=store.playlist(user.id,p.id);caches.set(p.id,{updated:fresh.updated,items});while(caches.size>12)caches.delete(caches.keys().next().value);return items;})();loads.set(p.id,task);try{return await task;}finally{loads.delete(p.id);}}
async function channels(user){const lists=store.playlists(user.id);const results=await Promise.allSettled(lists.map(p=>playlistItems(user,store.playlist(user.id,p.id))));return {items:results.flatMap(x=>x.status==='fulfilled'?x.value:[]),errors:results.flatMap((x,i)=>x.status==='rejected'?[{name:lists[i].name,error:'Loading failed. Check the URL or try refreshing.'}]:[])};}
function ownedSession(user,id){const session=playback.get(id);return session?.userId===user.id?session:null;}
const server=http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','no-store');res.setHeader('Vary','Cookie');res.setHeader('Referrer-Policy','same-origin');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
 let user;
 try{
 const url=new URL(req.url,'http://localhost'),route=url.pathname;
 if(req.method!=='GET'&&req.method!=='HEAD'&&req.headers.origin&&req.headers.origin!==`${req.headers['x-forwarded-proto']==='https'?'https':'http'}://${req.headers.host}`)return json(res,403,{error:'This request originated from another website.'});
 user=store.authenticate(token(req));
 if(route==='/api/auth/register'&&req.method==='POST'){limit(req,'register',10);const data=await body(req),account=store.createUser(String(data.username||'').trim(),data.name,data.password);setCookie(req,res,store.session(account.id));return json(res,201,{user:{...store.publicUser(account),features:{youtube:youtube.available}}});}
 if(route==='/api/auth/login'&&req.method==='POST'){limit(req,'login',30);const data=await body(req),account=store.login(data.username,data.password);setCookie(req,res,store.session(account.id));return json(res,200,{user:{...store.publicUser(account),features:{youtube:youtube.available}}});}
 if(route.startsWith('/api/')||route==='/audio'){
  if(!user)return json(res,401,{error:'Sign in to access your media.'});
  if(route==='/api/auth/me')return json(res,200,{user:{...store.publicUser(user),features:{youtube:youtube.available}}});
  if(route==='/api/auth/logout'&&req.method==='POST'){for(const session of [...playback.sessions.values()])if(session.authId===user.authId)playback.close(session,'Signed out');store.logout(token(req));setCookie(req,res,'');return json(res,200,{ok:true});}
  if(route==='/api/auth/password'&&req.method==='POST'){const data=await body(req);store.changePassword(user,data.current,data.password);return json(res,200,{ok:true});}
  if(route==='/api/home'){
   const records=store.history(user.id),all=records.some(x=>x.kind==='tv')?await channels(user):{items:[]},favs=store.favorites(user.id);
   const items=records.flatMap(row=>{if(row.kind==='youtube')return [{...row.details,kind:'youtube',position:row.details.position>=row.details.duration-3?0:row.details.position,viewedAt:row.viewed}];if(row.kind==='tv'){const channel=all.items.find(x=>x.id===row.source_id);return channel?[{...publicChannel(channel,favs),kind:'tv',viewedAt:row.viewed}]:[];}const connection=store.plex(user.id,row.connection_id);if(!connection)return [];const progress=store.progress(user.id,row.connection_id,row.item_id),item={...row.details};if(progress)item.position=progress.position>=progress.duration-3?0:progress.position;return [{...item,kind:'plex',connectionId:row.connection_id,viewedAt:row.viewed}];});
   return json(res,200,{items,name:user.name});
  }
  if(route==='/api/history/view'&&req.method==='POST'){
   const session=ownedSession(user,(await body(req)).session);if(!session?.history)throw Error('No active playback session.');const h=session.history;store.viewed(user.id,h.kind,h.sourceId,h.connectionId,h.itemId,h.details);return json(res,200,{ok:true});
  }
  if(route==='/api/settings'&&req.method==='POST')return json(res,200,{settings:store.settings(user.id,await body(req))});
  if(route==='/api/tv/playlists'){
   if(req.method==='GET')return json(res,200,{playlists:store.playlists(user.id)});
   const data=await body(req);
   if(req.method==='DELETE'){store.deletePlaylist(user.id,data.id);caches.delete(data.id);return json(res,200,{ok:true});}
   if(store.playlists(user.id).length>=10)throw Error('You can add up to ten playlists.');
   const source=await validUrl(data.url,!!user.admin);const id=store.addPlaylist(user.id,data.name,source.href);try{await playlistItems(user,store.playlist(user.id,id),true);}catch(error){store.deletePlaylist(user.id,id);throw error;}return json(res,201,{playlists:store.playlists(user.id)});
  }
  if(route==='/api/tv/sync'&&req.method==='POST'){const data=await body(req),lists=store.playlists(user.id);const results=await Promise.allSettled(lists.map(p=>playlistItems(user,store.playlist(user.id,p.id),!!data.refresh)));return json(res,200,{count:results.reduce((n,x)=>n+(x.status==='fulfilled'?x.value.length:0),0),errors:results.flatMap((x,i)=>x.status==='rejected'?[{name:lists[i].name,error:'Loading failed; check the source.'}]:[])});}
  if(route==='/api/tv/channels'){const all=await channels(user),favs=store.favorites(user.id),query=(url.searchParams.get('q')||'').toLowerCase(),group=url.searchParams.get('group'),list=url.searchParams.get('playlist'),favorite=url.searchParams.get('favorites')==='1',page=Math.max(0,Math.min(10000,Number(url.searchParams.get('page'))||0));const filtered=all.items.filter(x=>(!list||x.playlistId===list)&&(!favorite||favs.has(x.id))&&(!group||x.group===group)&&(!query||(x.name+' '+x.group).toLowerCase().includes(query)));return json(res,200,{items:filtered.slice(page*72,page*72+72).map(x=>publicChannel(x,favs)),total:filtered.length,page,groups:[...new Set(all.items.map(x=>x.group).filter(Boolean))].sort(),errors:all.errors});}
  if(route==='/api/tv/favorite'&&req.method==='POST'){const data=await body(req),all=await channels(user);if(!all.items.some(x=>x.id===data.id))throw Error('Channel not found.');store.favorite(user.id,data.id,!!data.favorite);return json(res,200,{ok:true});}
  if(route==='/api/tv/logo'){const all=await channels(user),item=all.items.find(x=>x.id===url.searchParams.get('id'));if(!item?.logo){res.writeHead(404);return res.end();}try{const image=await upstream(item.logo,{allowPrivate:!!user.admin,limit:2*1024*1024,timeout:8000});if(!image.type.startsWith('image/'))throw Error();res.writeHead(200,{'Content-Type':image.type,'Cache-Control':'private, max-age=86400','Content-Security-Policy':"default-src 'none'; sandbox"});return res.end(image.bytes);}catch{res.writeHead(404);return res.end();}}
  if(route==='/api/youtube/search'){limit(req,'youtube',60);return json(res,200,await youtube.search(url.searchParams.get('q')));}
  if(route==='/api/youtube/item'){const data=youtube.public(await youtube.info(url.searchParams.get('id'))),history=store.historyItem(user.id,'youtube',data.id);if(history)data.position=history.position>=history.duration-3?0:history.position;return json(res,200,data);}
  if(route==='/api/youtube/image'){const image=await youtube.image(url.searchParams.get('id'));res.writeHead(200,{'Content-Type':image.type,'Cache-Control':'private, max-age=86400'});return res.end(image.bytes);}
  if(route==='/api/youtube/progress'&&req.method==='POST'){const data=await body(req),id=youtubeId(data.itemId),position=Number(data.position),duration=Number(data.duration);if(!id||!Number.isFinite(position)||!Number.isFinite(duration)||position<0||position>duration+120||duration<0||duration>864000)throw Error('Invalid playback position.');store.historyProgress(user.id,'youtube',id,position,duration);return json(res,200,{saved:true});}
  if(route==='/api/plex/connections'){
   if(req.method==='GET')return json(res,200,{connections:store.plexList(user.id)});const data=await body(req);
   if(req.method==='DELETE'){store.deletePlex(user.id,data.id);return json(res,200,{ok:true});}
   await plex.connect(user,data);return json(res,201,{connections:store.plexList(user.id)});
  }
  if(route==='/api/plex/pin'&&req.method==='POST')return json(res,200,await plex.pin(user));
  if(route==='/api/plex/poll')return json(res,200,await plex.poll(user));
  if(route==='/api/plex/select'&&req.method==='POST'){await plex.select(user,(await body(req)).id);return json(res,200,{connections:store.plexList(user.id)});}
  if(route==='/api/plex/libraries')return json(res,200,{libraries:await plex.libraries(user,url.searchParams.get('connection'))});
  if(route==='/api/plex/browse')return json(res,200,await plex.browse(user,url.searchParams.get('connection'),{section:url.searchParams.get('section'),query:url.searchParams.get('q'),parent:url.searchParams.get('parent'),page:url.searchParams.get('page'),continueWatching:url.searchParams.get('continue')==='1'}));
  if(route==='/api/plex/item')return json(res,200,(await plex.metadata(user,url.searchParams.get('connection'),url.searchParams.get('id'))).public);
  if(route==='/api/plex/subtitles'){const text=await plex.subtitles(user,url.searchParams.get('connection'),url.searchParams.get('id'),url.searchParams.get('stream'));res.writeHead(200,{'Content-Type':'text/plain; charset=utf-8'});return res.end(text);}
  if(route==='/api/plex/progress'&&req.method==='POST')return json(res,200,await plex.progress(user,await body(req)));
  if(route==='/api/plex/image'){const image=await plex.image(user,url.searchParams.get('connection'),url.searchParams.get('key')||'',url.searchParams.get('id'));if(!image.type.startsWith('image/')){res.writeHead(404);return res.end();}res.writeHead(200,{'Content-Type':image.type,'Cache-Control':image.fallback?'private, max-age=60':'private, max-age=3600','Content-Security-Policy':"default-src 'none'; sandbox"});return res.end(image.bytes);}
  if(route==='/api/session'&&req.method==='POST'){
   const data=await body(req),method=data.method||user.settings.method,mode=['webcodecs','webgl'].includes(method)?'webcodecs':'mjpeg';
   if(!['bitmap','mjpeg','webcodecs','webgl'].includes(method))throw Error('Choose a valid playback method.');
   const profile=data.profile||`${user.settings.resolution}p-${user.settings.fps}`;if(!Object.hasOwn(profiles,profile))throw Error('Choose a valid video quality.');
   if([...playback.sessions.values()].filter(x=>x.userId===user.id).length>=3)throw Error('Stop one of your other players first.');if(playback.sessions.size>=12)throw Error('The server currently has too many active players.');
   let source,demo=data.kind==='demo',metadata=null,offset=0,headers,audioSource,subtitleOverlay,live=true;
   if(data.kind==='youtube'){const media=await youtube.media(data.itemId);source=media.source;audioSource=media.audioSource;headers=media.headers;metadata=media.metadata;data.itemId=metadata.id;offset=Math.max(0,Math.min(Number(data.offset)||0,metadata.duration));live=false;}
   else if(data.kind==='plex'){const media=await plex.media(user,data.connectionId,data.itemId);source=media.source;headers=media.headers;metadata=media.public;const subtitleId=String(data.subtitleId??metadata.defaultSubtitleId??'off'),track=metadata.subtitles.find(x=>x.id===subtitleId);if(subtitleId!=='off'&&!track?.supported)throw Error('This subtitle track is unavailable.');if(track?.mode==='bitmap'){const sourceTrack=media.item.Media[0].Part[0].Stream.find(x=>String(x.id)===track.id);subtitleOverlay=Number(sourceTrack.index);}metadata.selectedSubtitleId=subtitleId;offset=Math.max(0,Math.min(Number(data.offset)||0,metadata.duration));live=false;}
   else if(!demo){const all=await channels(user),channel=all.items.find(x=>x.id===data.id);if(!channel)throw Error('Channel not found.');source=(await validUrl(channel.url,!!user.admin)).href;metadata=publicChannel(channel,store.favorites(user.id));}
   const session=playback.create(source,mode,demo,{profile,audio:data.audio!==false,live,offset,headers,audioSource,subtitleOverlay});session.userId=user.id;session.authId=user.authId;if(!demo)session.history={kind:live?'tv':data.kind,sourceId:live?data.id:(data.kind==='youtube'?data.itemId:data.connectionId+':'+data.itemId),connectionId:data.kind==='plex'?data.connectionId:null,itemId:live?null:String(data.itemId),details:live?metadata:{...metadata,position:offset}};
   return json(res,200,{session:session.id,fps:profiles[profile].fps,metadata,offset});
  }
  if(route==='/audio'){const session=ownedSession(user,url.searchParams.get('session'));if(!session){res.writeHead(404);return res.end();}playback.attachAudio(session,res);return;}
  if(route==='/api/stop'&&req.method==='POST'){const session=ownedSession(user,(await body(req)).session);if(session)playback.close(session,'Player stopped');return json(res,200,{ok:true});}
  if(route==='/api/play'&&req.method==='POST'){const session=ownedSession(user,(await body(req)).session);if(!session)throw Error('Playback session expired.');playback.attachVideo(session,res);return;}
  return json(res,404,{error:'Niet gevonden.'});
 }
 const assets={'/':['index.html','text/html; charset=utf-8'],'/static/app.js':['app.js','text/javascript'],'/static/player.js':['player.js','text/javascript'],'/static/subtitles.js':['subtitles.js','text/javascript'],'/static/style.css':['style.css','text/css'],'/static/ivf.mjs':['ivf.mjs','text/javascript']};
 const asset=assets[route]||(!route.startsWith('/static/')&&!route.includes('.')?assets['/']:null);if(!asset){res.writeHead(404);return res.end();}const content=await readFile(path.join(root,'static',asset[0]));res.writeHead(200,{'Content-Type':asset[1]});res.end(content);
 }catch(error){if(!res.headersSent){const message=error.name==='TimeoutError'?'The source did not respond in time. Try again.':error.message;const safe=/https?:|password=|username=|SQLITE|ENOENT|fetch failed|Unexpected/.test(message)?'The source is unreachable or its credentials are invalid.':message;json(res,400,{error:safe});}else res.destroy();}
});
server.on('error',error=>{console.error('Server could not start ('+error.code+').');process.exitCode=1;});
server.listen(port,host,()=>console.log(`Tesla Media: http://${host}:${server.address().port}`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{playback.closeAll();server.close(()=>{store.close();process.exit();});setTimeout(()=>process.exit(),3000).unref();});
