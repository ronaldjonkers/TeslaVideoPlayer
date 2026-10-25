import {test} from 'node:test';
import assert from 'node:assert/strict';
import {subtitleTracks,preferredSubtitle,languageCode} from './subtitles.mjs';
import {parseSubtitles,captionAt} from './static/subtitles.js';
test('subtitle tracks normalize languages and choose supported preferences',()=>{
 const tracks=subtitleTracks({Media:[{Part:[{Stream:[{id:1,streamType:3,codec:'srt',languageCode:'nld'},{id:2,streamType:3,codec:'srt',languageCode:'eng',selected:1},{id:3,streamType:3,codec:'pgs',languageCode:'eng',index:4},{id:4,streamType:3,codec:'pgs',languageCode:'deu'}]}]}]});
 assert.equal(languageCode('POR_BR'),'pt-br');assert.equal(preferredSubtitle(tracks,'nl'),'1');assert.equal(preferredSubtitle(tracks,'auto'),'2');assert.equal(preferredSubtitle(tracks,'fr'),'off');assert.equal(preferredSubtitle(tracks,'off'),'off');assert.equal(tracks[2].mode,'bitmap');assert.equal(tracks[3].supported,false);
});
test('SRT and WebVTT cues follow absolute playback time with safe plain text',()=>{
 const cues=parseSubtitles('WEBVTT\n\n00:01.000 --> 00:03.000\n<b>Hello</b> &amp; world\n\n00:02.000 --> 00:04.000\nSecond line\n');
 assert.equal(captionAt(cues,0),'');assert.equal(captionAt(cues,1.5),'Hello & world');assert.equal(captionAt(cues,2),'Hello & world\nSecond line');assert.equal(captionAt(cues,4),'');
 assert.equal(parseSubtitles('1\n01:02:03,000 --> 01:02:05,000\n&lt;script&gt;\n')[0].start,3723);
 assert.throws(()=>parseSubtitles('<html>Error</html>'),/readable/);
});
test('ASS subtitles remove style overrides and retain dialogue commas and line breaks',()=>{
 const cues=parseSubtitles('[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,{\\i1}Hello, world\\NNext line\n');
 assert.equal(captionAt(cues,2),'Hello, world\nNext line');
});
