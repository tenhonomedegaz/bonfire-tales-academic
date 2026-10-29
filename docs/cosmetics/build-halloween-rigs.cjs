/* Build numeric, versioned choreography data. No database or image editing. */
const fs = require('node:fs');
const path = require('node:path');
const filename = path.resolve(__dirname, '../../home/static/cosmetics/efeito-vigilia-das-lanternas.json');
const pack = JSON.parse(fs.readFileSync(filename,'utf8'));
const media = (file,width,height,placement,pivot) => ({slot:'banner',file,fallback:file,width,height,motion:'none',placement,...(pivot?{pivot}:{})});
const sequence = (duration,frames,backdrop=0,columns=1,rows=1,delay=0) => ({columns,rows,duration,delay,backdrop,frames});
function drift(duration,delay,phase){
  const frames = Array.from({length:24},(_,i)=>{
    const at=i/23,angle=2*Math.PI*at;
    return {at,frame:0,opacity:1,
      x:Number((4.2*Math.sin(angle+phase)).toFixed(4)),
      y:Number((3.5*Math.cos(angle)).toFixed(4)),
      rotate:Number((1.4*Math.sin(angle+phase)).toFixed(4))};
  });
  return sequence(duration,frames,0,1,1,delay);
}
function flame(x,y,width,delay,duration){
  return {...media('vigilia-flame-twelve-v3.webp',1024,768,{x,y,width},{x:50,y:85}),
    sequence:sequence(duration,Array.from({length:13},(_,i)=>({at:i/12,frame:i%12,opacity:1})),0,4,3,delay)};
}
const candleSpecs = [
  {file:'vigilia-candlestick-one-v3.webp',w:400,h:600,placement:{x:25,y:38,width:7},mobile:{x:22,y:42,width:14},duration:8.2,delay:-2.4,phase:.4,wicks:[[50.3,1.6,26]]},
  {file:'vigilia-candlestick-two-v3.webp',w:500,h:750,placement:{x:72,y:62,width:10},mobile:{x:72,y:72,width:20},duration:10.6,delay:-6.1,phase:1.7,wicks:[[29.3,1.2,22],[70.1,12,22]]},
  {file:'vigilia-candlestick-three-v3.webp',w:560,h:840,placement:{x:85,y:48,width:11},mobile:{x:83,y:38,width:24},duration:12.8,delay:-8.7,phase:3.2,wicks:[[21.6,25.3,21],[50.8,2.3,21],[78.2,14.9,21]]}
];
const candles = candleSpecs.map((spec,j)=>({...media(spec.file,spec.w,spec.h,spec.placement),mobile:spec.mobile,
  sequence:drift(spec.duration,spec.delay,spec.phase),
  parts:spec.wicks.map(([x,y,width],i)=>flame(x,y,width,-.17*(i+1+j),1.15+(i+j)*.11))}));
const gaze=[
  [0,0],[.08,0],[.14,0],[.16,-3],[.18,-10],[.20,-22],[.22,-36],[.24,-50],
  [.26,-60],[.28,-56],[.30,-45],[.32,-25],[.34,0],[.36,25],[.38,45],[.40,58],
  [.42,60],[.44,48],[.46,32],[.48,16],[.50,6],[.54,0],[.62,0],[1,0]
];
const pupils = [26.5,73.5].map(x=>({...media('vigilia-jack-pupil-v3.webp',128,128,{x,y:37,width:12}),
  sequence:sequence(18,gaze.map(([at,value])=>({at,frame:0,opacity:1,x:value,y:value/30,rotate:value/25})))}));
const face={...media('vigilia-jack-base-v3.webp',640,640,{x:50,y:47,width:23}),mobile:{x:50,y:47,width:42},
  sequence:sequence(18,gaze.map(([at])=>({at,frame:0,opacity:at<.14||at>=.62?0:.95})),.82),parts:pupils};
pack.layers=[...pack.layers.slice(0,3),...candles,face];
fs.writeFileSync(filename,JSON.stringify(pack,null,2)+'\n');
