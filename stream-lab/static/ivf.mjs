// Incremental IVF parser. Each VP8 record contains one complete encoded frame.
export class IVFParser{
 constructor(onFrame){this.onFrame=onFrame;this.buffer=new Uint8Array();this.header=false;}
 push(bytes){const next=new Uint8Array(this.buffer.length+bytes.length);next.set(this.buffer);next.set(bytes,this.buffer.length);this.buffer=next;
 if(!this.header){if(this.buffer.length<32)return;const d=new DataView(this.buffer.buffer);if(String.fromCharCode(...this.buffer.subarray(0,4))!=='DKIF'||String.fromCharCode(...this.buffer.subarray(8,12))!=='VP80')throw Error('Invalid IVF/VP8 format');if(d.getUint16(6,true)!==32)throw Error('Unsupported IVF header');this.rate=d.getUint32(16,true);this.scale=d.getUint32(20,true);if(!this.rate||!this.scale)throw Error('Invalid IVF time base');this.buffer=this.buffer.slice(32);this.header=true;}
 while(this.buffer.length>=12){const d=new DataView(this.buffer.buffer,this.buffer.byteOffset);const size=d.getUint32(0,true);if(size>8*1024*1024)throw Error('Frame is too large');if(this.buffer.length<12+size)return;const timestamp=Number(d.getBigUint64(4,true))*this.scale/this.rate*1e6;const data=this.buffer.slice(12,12+size);this.onFrame({data,timestamp:Math.round(timestamp),key:(data[0]&1)===0});this.buffer=this.buffer.slice(12+size);}
 }
 finish(){if(!this.header||this.buffer.length)throw Error('Incomplete IVF stream');}
}
