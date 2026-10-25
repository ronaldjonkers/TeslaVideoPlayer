import {spawnSync} from 'node:child_process';
export const profiles={};
for(const height of [360,480,540,720,1080])for(const fps of [20,24,25,30,50,60]){
 profiles[`${height}p-${fps}`]={height,fps,bitrate:Math.round(1100*(height/360)**2*(fps/25)**0.7)+'k',jpeg:height>=720?'4':'5'};
}
// Compatibility for existing clients; every preset now uses at least 20 fps.
profiles.economy={width:480,fps:20,bitrate:'800k',jpeg:'7'};
profiles.balanced={width:640,fps:25,bitrate:'1100k',jpeg:'5'};
export function httpReconnectArgs(help){const options=[['reconnect','1'],['reconnect_streamed','1'],['reconnect_at_eof','1'],['reconnect_on_network_error','1'],['reconnect_on_http_error','429,5xx'],['reconnect_delay_max','3'],['reconnect_delay_total_max','30']];return options.filter(([name])=>new RegExp('(?:^|\\s)-'+name+'(?:\\s|$)').test(help)).flatMap(([name,value])=>['-'+name,value]);}
const reconnectArgs=httpReconnectArgs(spawnSync(process.env.FFMPEG_PATH||'ffmpeg',['-hide_banner','-h','protocol=http'],{encoding:'utf8',timeout:5000}).stdout||'');
function inputArgs(source,demo,audio=false,{live=true,offset=0,headers}={}){
 if(demo)return ['-re','-f','lavfi','-i','testsrc2=size=640x360:rate=25',...(audio?['-re','-f','lavfi','-i','sine=frequency=440:sample_rate=44100']:[])];
 return ['-re','-rw_timeout','15000000',...(live?['-seekable','0',...reconnectArgs]:['-ss',String(Math.max(0,offset))]),...(headers?['-headers',headers]:[]),...(process.platform==='darwin'?['-hwaccel','auto']:[]),'-i',source];
}
function videoOutput(mode,profile,subtitleOverlay){
 const p=profiles[profile];
 // Drop frames before scaling and encoding: this saves actual server work.
 const filter=`fps=${p.fps},scale=${p.height?'-2:'+p.height:p.width+':-2'}:flags=fast_bilinear`;const base=Number.isInteger(subtitleOverlay)?['-filter_complex',`[0:${subtitleOverlay}][0:v:0]scale2ref[subs][base];[base][subs]overlay=eof_action=pass:shortest=0,${filter}[captioned]`,'-map','[captioned]','-an','-threads','2']:['-map','0:v:0','-an','-vf',filter,'-threads','2'];
 return mode==='webcodecs'?[...base,'-c:v','libvpx','-deadline','realtime','-cpu-used','8','-b:v',p.bitrate,'-g',String(p.fps),'-lag-in-frames','0','-f','ivf','pipe:1']:[...base,'-c:v','mjpeg','-q:v',p.jpeg,'-f','image2pipe','pipe:1'];
}
export function sessionArgs(source,mode,demo=false,{profile='540p-20',audio=true,live=true,offset=0,headers,audioSource,subtitleOverlay}={}){
 return ['-hide_banner','-loglevel','warning',...inputArgs(source,demo,audio,{live,offset,headers}),...(audio&&audioSource?inputArgs(audioSource,false,false,{live:false,offset,headers}):[]),...videoOutput(mode,profile,subtitleOverlay),...(audio?['-map',demo||audioSource?'1:a:0':'0:a:0?','-vn','-c:a','libmp3lame','-threads','1','-ac','2','-ar','44100','-b:a','96k','-f','mp3','pipe:3']:[])];
}
// Retained for isolated encoder tests.
export function ffmpegArgs(source,mode,demo=false){
 if(mode==='audio')return ['-hide_banner','-loglevel','error',...(demo?['-re','-f','lavfi','-i','sine=frequency=440:sample_rate=44100']:inputArgs(source,false)),'-vn','-c:a','libmp3lame','-b:a','128k','-f','mp3','pipe:1'];
 return sessionArgs(source,mode,demo,{profile:'balanced',audio:false});
}
