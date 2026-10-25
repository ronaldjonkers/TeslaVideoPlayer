#!/usr/bin/env node
// Test-only extractor. It never contacts YouTube.
const source=process.env.YT_TEST_SOURCE;if(!source)throw Error('No test media source');const data={id:'M7lc1UVf-VE',title:'Een YouTube-test',duration:15,channel:'Testkanaal',description:'Lokale testvideo',requested_formats:[{vcodec:'h264',acodec:'aac',url:source+'/youtube.mp4'}]};console.log(JSON.stringify(process.argv.some(x=>x.startsWith('ytsearch'))?{entries:[data]}:data));
