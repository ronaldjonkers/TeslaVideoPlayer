import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawnSync} from 'node:child_process';
import {PlaybackSessions} from './playback.mjs';
import {sessionArgs,profiles,httpReconnectArgs} from './media.mjs';
import {IVFParser} from './static/ivf.mjs';
const listen=server=>new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const close=server=>new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});

test('quality settings apply frames before scaling and shares one input for audio/video',()=>{
 const args=sessionArgs('https://example.org/live','webcodecs',false);
 assert.equal(args.filter(x=>x==='-i').length,1);
 assert.match(args[args.indexOf('-vf')+1],/^fps=20,scale=-2:540/);
 assert.ok(args.includes('pipe:1'));assert.ok(args.includes('pipe:3'));
 assert.equal(args[args.indexOf('-reconnect_at_eof')+1],'1');
});

test('single session survives provider EOF and repeated audio requests', {timeout:20000},async()=>{
 const encoded=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=160x90:rate=15','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','mpeg2video','-c:a','mp2','-f','mpegts','pipe:1']);
 assert.equal(encoded.status,0,encoded.stderr.toString());
 let sourceRequests=0;
 const source=http.createServer((req,res)=>{sourceRequests++;res.writeHead(200,{'Content-Type':'video/mp2t'});res.write(encoded.stdout);setTimeout(()=>res.destroy(),80);});
 await listen(source);
 let debug='';const playback=new PlaybackSessions({onDiagnostic:message=>debug+=message});const session=playback.create(`http://127.0.0.1:${source.address().port}/live`,'webcodecs',false);
 const relay=http.createServer((req,res)=>{if(req.url==='/audio')playback.attachAudio(session,res);else playback.attachVideo(session,res);});await listen(relay);
 const base=`http://127.0.0.1:${relay.address().port}`;
 const abort=new AbortController();
 try{
  const a1=await fetch(base+'/audio');const ar1=a1.body.getReader();
  const videoPromise=fetch(base+'/video',{signal:abort.signal});
  const firstAudio=await ar1.read();assert.ok(firstAudio.value.length);await ar1.cancel();
  const child=session.child;
  const a2=await fetch(base+'/audio');const ar2=a2.body.getReader();assert.ok((await ar2.read()).value.length);await ar2.cancel();
  assert.equal(session.child,child,'Audio retry must reuse the same FFmpeg process');
  const video=await videoPromise;assert.equal(video.status,200);const reader=video.body.getReader();let frames=0;
  const parser=new IVFParser(()=>frames++);
  const started=Date.now();while(Date.now()-started<6500){const {value,done}=await reader.read();assert.equal(done,false,'requests='+sourceRequests+' '+debug);parser.push(value);}
  assert.ok(sourceRequests>1,'Provider EOF should reconnect');assert.ok(frames>40,'Frames must keep flowing across reconnects');
 }finally{abort.abort();playback.closeAll();await close(relay);await close(source);}
});

test('channel without audio keeps video playing', {timeout:15000},async()=>{
 const encoded=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=160x90:rate=15','-t','2','-c:v','mpeg2video','-f','mpegts','pipe:1']);
 assert.equal(encoded.status,0);
 const source=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'video/mp2t'});res.write(encoded.stdout);setTimeout(()=>res.destroy(),80);});await listen(source);
 const playback=new PlaybackSessions();const session=playback.create(`http://127.0.0.1:${source.address().port}/live`,'mjpeg',false);
 const relay=http.createServer((req,res)=>playback.attachVideo(session,res));await listen(relay);
 const abort=new AbortController();
 try{const response=await fetch(`http://127.0.0.1:${relay.address().port}`,{signal:abort.signal});assert.equal(response.status,200);const reader=response.body.getReader();assert.ok((await reader.read()).value.length);assert.equal(session.audio,false);}
 finally{abort.abort();playback.closeAll();await close(relay);await close(source);}
});

test('all resolution and framerate combinations are supported with a 20 fps minimum',()=>{for(const height of [360,480,540,720,1080])for(const fps of [20,24,25,30,50,60]){const args=sessionArgs(undefined,'webcodecs',true,{profile:`${height}p-${fps}`});assert.equal(args[args.indexOf('-vf')+1],`fps=${fps},scale=-2:${height}:flags=fast_bilinear`);}for(const preset of Object.values(profiles))assert.ok(preset.fps>=20);});

test('older FFmpeg builds only receive supported HTTP reconnect options',()=>{const options=httpReconnectArgs('  -reconnect <boolean>\n  -reconnect_streamed <boolean>\n  -reconnect_at_eof <boolean>\n');assert.ok(options.includes('-reconnect'));assert.ok(!options.includes('-reconnect_delay_total_max'));assert.deepEqual(httpReconnectArgs(''),[]);});
