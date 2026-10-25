import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {sessionArgs,profiles} from './media.mjs';

// One provider connection supplies both outputs. Browser audio retries never open
// extra provider connections, and a stalled audio player cannot block video.
export class PlaybackSessions {
 constructor({onDiagnostic}={}){this.sessions=new Map();this.onDiagnostic=onDiagnostic;}
 create(source,mode,demo,{profile='540p-20',audio=true,live=true,offset=0,headers,audioSource,subtitleOverlay}={}){
  if(!Object.hasOwn(profiles,profile))throw Error('Unknown quality profile');
  const session={id:randomBytes(24).toString('hex'),source,mode,demo,profile,audio,live,offset,headers,audioSource,subtitleOverlay,child:null,video:null,audioResponse:null,bytes:0,audioBytes:0,started:Date.now(),reason:null,reconnects:0};
  session.timer=setTimeout(()=>this.close(session,'No video connection opened'),15000);session.timer.unref();
  this.sessions.set(session.id,session);return session;
 }
 get(id){return this.sessions.get(id);}
 attachAudio(session,res){
  if(!session.audio){res.writeHead(404);res.end();return;}
  session.audioResponse?.end();session.audioResponse=res;
  res.writeHead(200,{'Content-Type':'audio/mpeg','Accept-Ranges':'none','Cache-Control':'no-store'});res.flushHeaders();
  res.on('close',()=>{if(session.audioResponse===res)session.audioResponse=null;});
 }
 attachVideo(session,res){
  if(session.child)throw Error('This playback session is already open');
  clearTimeout(session.timer);session.video=res;
  const child=spawn(process.env.FFMPEG_PATH||'ffmpeg',sessionArgs(session.source,session.mode,session.demo,{profile:session.profile,audio:session.audio,live:session.live,offset:session.offset,headers:session.headers,audioSource:session.audioSource,subtitleOverlay:session.subtitleOverlay}),{stdio:['ignore','pipe','pipe','pipe']});session.child=child;
  let opened=false;
  session.timer=setTimeout(()=>{if(!opened){if(!res.headersSent){res.writeHead(504,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'The source did not provide video within 30 seconds.'}));}this.close(session,'No video received');}},30000);session.timer.unref();
  child.stdout.on('data',chunk=>{
   if(res.destroyed)return;
   if(!opened){opened=true;clearTimeout(session.timer);res.writeHead(200,{'Content-Type':'application/octet-stream','X-Stream-FPS':String(profiles[session.profile].fps)});}
   session.bytes+=chunk.length;if(!res.write(chunk))child.stdout.pause();
  });
  res.on('drain',()=>child.stdout.resume());
  res.on('close',()=>this.close(session,'The player closed the connection'));
  child.stdio[3].on('data',chunk=>{
   session.audioBytes+=chunk.length;
   const audio=session.audioResponse;
   // Bound each subscriber's queue. A browser can replace its audio request
   // without holding up the common FFmpeg input or accumulating memory.
   if(audio&&!audio.destroyed){if(audio.writableLength>512*1024){audio.destroy();session.audioResponse=null;}else audio.write(chunk);}
  });
  child.stderr.on('data',chunk=>{
   // Never retain or print provider URLs, credentials, or raw stderr.
   const message=chunk.toString();this.onDiagnostic?.(message);
   if(/Will reconnect|reconnect in/i.test(message))session.reconnects++;
   if(/Output file does not contain any stream|does not contain any stream/.test(message))session.noAudio=true;
   if(/401 Unauthorized|403 Forbidden/.test(message))session.reason='The provider denied access';
   else if(/429 Too Many|maximum.*connections/i.test(message))session.reason='The provider limits simultaneous connections';
   else if(/timed out/i.test(message))session.reason='The provider connection timed out';
  });
  child.on('error',()=>{if(!res.headersSent){res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'FFmpeg could not start.'}));}this.close(session,'FFmpeg could not start');});
  child.on('close',code=>{
   clearTimeout(session.timer);
   if(!opened&&session.noAudio&&session.audio&&this.sessions.has(session.id)&&!res.destroyed){session.child=null;session.audio=false;session.audioResponse?.end();session.audioResponse=null;this.attachVideo(session,res);return;}
   if(!res.destroyed){if(!res.headersSent){res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({error:session.reason||'No video received from the provider.'}));}else if(code!==0)res.destroy();else res.end();}
   session.audioResponse?.end();session.audioResponse=null;
   session.reason ||=code===0?'The source ended the stream':'Source connection interrupted';
   // Keep only short-lived metadata so the UI can display a useful reason.
   if(this.sessions.has(session.id)){session.expiry=setTimeout(()=>this.sessions.delete(session.id),60000);session.expiry.unref();}
  });
 }
 close(session,reason){
  if(!this.sessions.has(session.id))return;
  this.sessions.delete(session.id);clearTimeout(session.timer);clearTimeout(session.expiry);
  session.reason ||=reason;session.audioResponse?.end();
  const child=session.child;
  if(child&&child.exitCode===null){child.kill('SIGTERM');const timer=setTimeout(()=>{if(child.exitCode===null)child.kill('SIGKILL');},2000);timer.unref();}
  if(session.video&&!session.video.destroyed)session.video.end();
 }
 closeAll(){for(const session of [...this.sessions.values()])this.close(session,'Server shutting down');}
}
