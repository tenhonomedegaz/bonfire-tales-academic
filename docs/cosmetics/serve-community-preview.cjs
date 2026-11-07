/* Local illustrative catalog only: no credentials, project DB or write routes. */
'use strict';
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),port=Number(process.argv[2]||8897);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.ttf':'font/ttf','.woff2':'font/woff2'};
http.createServer((req,res)=>{
 if(req.method!=='GET'){res.writeHead(405);res.end();return;}
 const url=new URL(req.url,'http://127.0.0.1');
 if(url.pathname==='/perfil/cosmeticos/previa/'){
  const previews=JSON.parse(fs.readFileSync(path.join(__dirname,'community-preview-data.json')));
  const data=previews[url.searchParams.get('tipo')+':'+url.searchParams.get('key')];
  res.writeHead(data?200:404,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data||{error:'not found'}));return;
 }
 if(['/colaborador/','/perfil/'].includes(url.pathname)){res.writeHead(302,{Location:'https://bonfiretales.com.br'+url.pathname+url.hash});res.end();return;}
 const name=url.pathname==='/'?'/docs/cosmetics/20261102-community-catalog.html':decodeURIComponent(url.pathname);
 if(!name.startsWith('/static/')&&!name.startsWith('/docs/cosmetics/')){res.writeHead(404);res.end();return;}
 const target=path.resolve(root,name.startsWith('/static/')?'home'+name:'.'+name);
 const allowed=name.startsWith('/static/')?path.join(root,'home/static'):path.join(root,'docs/cosmetics');
 if(!target.startsWith(allowed+path.sep)){res.writeHead(403);res.end();return;}
 fs.stat(target,(error,stat)=>{
  if(error||!stat.isFile()){res.writeHead(404);res.end();return;}
  res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream','Cache-Control':'no-store'});
  fs.createReadStream(target).pipe(res);
 });
}).listen(port,'127.0.0.1',()=>console.log('http://127.0.0.1:'+port+'/docs/cosmetics/20261102-community-catalog.html'));
