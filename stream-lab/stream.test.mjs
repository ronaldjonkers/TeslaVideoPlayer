import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {parsePlaylist} from './playlist.mjs';
import {ffmpegArgs} from './media.mjs';
import {IVFParser} from './static/ivf.mjs';
test('playlist resolves relative URLs and excludes non-HTTP sources',()=>{const items=parsePlaylist('#EXTM3U\r\n#EXTINF:-1 group-title="Nieuws",Een\r\n/live/1.ts\nfile:///secret\n#EXTINF:-1,Twee\nhttps://example.com/2.ts','http://example.com/list');assert.equal(items.length,2);assert.equal(items[0].url,'http://example.com/live/1.ts');assert.equal(items[0].group,'Nieuws');assert.equal(items[1].name,'Twee');assert.equal(items[1].group,'');});
test('real FFmpeg VP8 output survives every incremental packet boundary',()=>{const result=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10','-frames:v','5','-c:v','libvpx','-deadline','realtime','-g','2','-f','ivf','pipe:1']);assert.equal(result.status,0,result.stderr.toString());const frames=[];const parser=new IVFParser(frame=>frames.push(frame));for(let i=0;i<result.stdout.length;i+=7)parser.push(result.stdout.subarray(i,i+7));parser.finish();assert.equal(frames.length,5);assert.equal(frames[0].key,true);assert.equal(frames[1].key,false);assert.equal(frames[2].key,true);assert.equal(frames[1].timestamp,100000);assert.equal(frames[4].timestamp,400000);});
test('IVF rejects invalid and truncated streams',()=>{assert.throws(()=>new IVFParser(()=>{}).push(new Uint8Array(32)),/Invalid/);assert.throws(()=>new IVFParser(()=>{}).finish(),/Incomplete/);});
test('four image routes with audio element and no video element',()=>{const html=readFileSync(new URL('./static/index.html',import.meta.url),'utf8');assert.doesNotMatch(html,/<video\b/i);assert.match(html,/<audio\b/i);for(const mode of ['mjpeg','webcodecs','webgl','bitmap'])assert.ok(html.includes(`value="${mode}"`));});

test('production FFmpeg arguments generate valid MJPEG frames',()=>{const args=ffmpegArgs(undefined,'mjpeg',true);args.splice(args.length-1,0,'-frames:v','3');const result=spawnSync('ffmpeg',args,{maxBuffer:8*1024*1024});assert.equal(result.status,0,result.stderr.toString());let frames=0;for(let i=1;i<result.stdout.length;i++)if(result.stdout[i-1]===255&&result.stdout[i]===217)frames++;assert.equal(frames,3);assert.equal(result.stdout[0],255);assert.equal(result.stdout[1],216);});
test('production VP8 route produces decodable IVF packets',()=>{const args=ffmpegArgs(undefined,'webcodecs',true);args.splice(args.length-1,0,'-frames:v','3');const result=spawnSync('ffmpeg',args,{maxBuffer:8*1024*1024});assert.equal(result.status,0,result.stderr.toString());let count=0;const parser=new IVFParser(()=>count++);parser.push(result.stdout);parser.finish();assert.equal(count,3);});

test('audio encoder emits MP3 from demo source',()=>{const args=ffmpegArgs(undefined,'audio',true);args.splice(args.length-1,0,'-t','0.2');const result=spawnSync('ffmpeg',args);assert.equal(result.status,0,result.stderr.toString());assert.ok(result.stdout.length>1000);assert.equal(result.stdout.subarray(0,3).toString(),'ID3');});

test('channel IDs remain stable when a playlist is reloaded',()=>{
 const text='#EXTM3U\n#EXTINF:-1,Een\nhttps://example.org/one.ts';
 assert.equal(parsePlaylist(text,'https://example.org/list')[0].id,parsePlaylist(text,'https://example.org/list')[0].id);
 assert.notEqual(parsePlaylist(text,'https://example.org/list')[0].id,parsePlaylist(text.replace('one.ts','two.ts'),'https://example.org/list')[0].id);
});
