import {createHash} from 'node:crypto';
export function parsePlaylist(text,base){
 const items=[];let name='',group='',logo='';
 for(const raw of text.split(/\r?\n/)){const line=raw.trim();if(line.startsWith('#EXTINF:')){let quoted=false,comma=-1;for(let i=0;i<line.length;i++){if(line[i]==='"')quoted=!quoted;if(line[i]===','&&!quoted){comma=i;break;}}name=comma<0?'':line.slice(comma+1).trim();logo=/tvg-logo="([^"]*)"/.exec(line)?.[1]||'';group=/group-title="([^"]*)"/.exec(line)?.[1]||'';}else if(line&&!line.startsWith('#')){try{const url=new URL(line,base);if(['http:','https:'].includes(url.protocol))items.push({id:createHash('sha256').update(url.href).digest('hex').slice(0,24),name:name||`Kanaal ${items.length+1}`,group,logo,url:url.href});}catch{}name='';group='';logo='';}}
 return items;
}
