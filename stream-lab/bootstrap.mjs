import {Store} from './store.mjs';import path from 'node:path';import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url)),store=new Store(process.env.DATA_DIR||path.join(root,'data'));
let text='';for await(const chunk of process.stdin)text+=chunk;
const data=JSON.parse(text),existing=store.db.prepare('SELECT id FROM users WHERE username=?').get(data.username);
if(!existing){store.createUser(data.username,data.name||data.username,data.password,true);console.log('Administrator account created. Add your sources in Settings.');}else console.log('Account already exists; password unchanged.');store.close();
