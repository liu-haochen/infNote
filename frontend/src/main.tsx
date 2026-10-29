import React, { createContext, memo, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, NodeResizer, NodeResizeControl, applyNodeChanges, useReactFlow, type NodeProps, type Viewport } from '@xyflow/react';
import Markdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { Plus, ImagePlus, Type, Maximize, Undo2, Redo2, Layers, Copy, Check, Pencil, X, ArrowUpRight, LoaderCircle, AlertCircle } from 'lucide-react';
import { storage, SaveQueue, serialize, type Card, type Canvas, type Entry } from './storage';
import '@xyflow/react/dist/style.css';
import './style.css';

type Actions = { edit: (id:string, markdown:string)=>void; inspect:(asset:string)=>void; editing:(active:boolean)=>void };
const ActionsContext = createContext<Actions>(null!);
const TextCard = memo(function TextCard({id,data,selected}:NodeProps<Card>) {
  const actions = useContext(ActionsContext);
  const [editing,setEditing] = useState(false);
  const [draft,setDraft] = useState(data.markdown);
  const finish = () => {actions.edit(id,draft); setEditing(false); actions.editing(false);};
  useEffect(() => () => { if(editing) actions.editing(false); }, [editing,actions]);
  return <div className={'card text-card ' + (selected?'chosen':'')} onDoubleClick={() => {setDraft(data.markdown);setEditing(true);actions.editing(true);}}>
    {selected && !editing && <NodeResizeControl position="right" resizeDirection="horizontal" minWidth={200} className="text-width-handle"/>}
    <div className="card-label"><span className="label-dot"/>文字笔记 <Pencil size={12}/></div>
    {editing ? <textarea aria-label="编辑文字卡片" className="nodrag nowheel editor" autoFocus value={draft} onChange={e=>setDraft(e.target.value)} onBlur={finish} onKeyDown={e=>{e.stopPropagation();if(e.key==='Escape'||(e.ctrlKey&&e.key==='Enter'))e.currentTarget.blur();}}/> : <div className="markdown"><Markdown remarkPlugins={[remarkBreaks]} skipHtml disallowedElements={['img']}>{data.markdown || '双击，写下你的想法…'}</Markdown></div>}
    {editing && <div className="edit-hint">Markdown · 点击外部保存 · Ctrl+Enter 完成</div>}
  </div>;
});
const ImageCard = memo(function ImageCard({data,selected}:NodeProps<Card>) {
  const actions = useContext(ActionsContext);
  return <div className={'card image-card '+(selected?'chosen':'')} onDoubleClick={()=>actions.inspect(data.asset!)}>
    <NodeResizer isVisible={selected} keepAspectRatio minWidth={100} minHeight={60}/>
    <img draggable={false} src={storage.assetUrl(data.asset!)} alt="收集的截图"/>
    <div className="image-caption">原始截图 <span>{data.naturalWidth} × {data.naturalHeight} <ArrowUpRight size={12}/></span></div>
  </div>;
});
const nodeTypes = {text:TextCard,image:ImageCard};
const editable = (target:EventTarget|null) => target instanceof HTMLElement && !!target.closest('input,textarea,[contenteditable="true"]');

function App() {
  const flow = useReactFlow<Card>();
  const [nodes,setNodes] = useState<Card[]>([]);
  const nodesRef = useRef<Card[]>([]);
  const [entries,setEntries] = useState<Entry[]>([]);
  const [active,setActive] = useState('');
  const activeRef = useRef('');
  const [dataDir,setDataDir] = useState('');
  const [status,setStatus] = useState<'saved'|'pending'|'saving'|'error'>('saved');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(true);
  const [uploading,setUploading] = useState(false);
  const [inspect,setInspect] = useState<string|null>(null);
  const [imageZoom,setImageZoom] = useState(1);
  const [copied,setCopied] = useState(false);
  const [space,setSpace] = useState(false);
  const [isEditing,setIsEditing] = useState(false);
  const editingRef = useRef(false);
  const [dialog,setDialog] = useState<'new'|'rename'|null>(null);
  const [name,setName] = useState('');
  const viewport = useRef<Viewport>({x:0,y:0,zoom:1});
  const dirty = useRef(false);
  const revision = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const queue = useRef(new SaveQueue());
  const history = useRef<Card[][]>([]), future = useRef<Card[][]>([]);
  const [,renderHistory] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const board = useRef<HTMLDivElement>(null);
  const interaction = useRef(false);
  const busyRef = useRef(true);
  const uploadRef = useRef(false);

  const showError = useCallback((e:unknown)=>setError(e instanceof Error?e.message:String(e)),[]);
  const flush = useCallback(async()=>{
    clearTimeout(timer.current);
    if(!dirty.current || !activeRef.current)return;
    const id = activeRef.current, rev = revision.current;
    const snapshot = serialize(nodesRef.current,viewport.current);
    setStatus('saving');
    try {
      await queue.current.save(id,snapshot);
      if(id===activeRef.current && rev===revision.current) {dirty.current=false;setStatus('saved');}
    } catch(e) {setStatus('error');showError(e);throw e;}
  },[showError]);
  const changed = useCallback(()=>{
    dirty.current=true;revision.current++;setStatus('pending');clearTimeout(timer.current);
    timer.current=setTimeout(()=>{void flush().catch(()=>{});},500);
  },[flush]);
  const assign = useCallback((next:Card[])=>{nodesRef.current=next;setNodes(next);},[]);
  const checkpoint = useCallback(()=>{history.current.push(structuredClone(nodesRef.current));if(history.current.length>60)history.current.shift();future.current=[];renderHistory(n=>n+1);},[]);
  const commit = useCallback((next:Card[])=>{checkpoint();assign(next);changed();},[checkpoint,assign,changed]);
  const switchCanvas = useCallback(async(id:string)=>{
    if(busyRef.current||uploadRef.current||id===activeRef.current)return;
    busyRef.current=true;setBusy(true);
    try {
      await flush();
      const canvas=await storage.load(id);
      activeRef.current=id;setActive(id);viewport.current=canvas.viewport;
      assign(canvas.nodes.map(n=>({...n,style:{width:n.width,...(n.type==='image'?{height:n.height}:{})}})));
      history.current=[];future.current=[];renderHistory(n=>n+1);setStatus('saved');
      requestAnimationFrame(()=>void flow.setViewport(canvas.viewport));
    }catch(e){showError(e);}finally{busyRef.current=false;setBusy(false);}
  },[flush,assign,flow,showError]);
  useEffect(()=>{let live=true;void Promise.all([storage.list(),storage.info()]).then(async([list,info])=>{
    if(!live)return;setEntries(list);setDataDir(info.dataDir);busyRef.current=false;await switchCanvas(list[0].id);
  }).catch(e=>{showError(e);busyRef.current=false;setBusy(false);});return()=>{live=false;};},[]);
  useEffect(()=>{const handler=(e:BeforeUnloadEvent)=>{if(dirty.current||uploadRef.current||editingRef.current){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[]);

  const addCards = useCallback((cards:Card[])=>{
    const box=board.current!.getBoundingClientRect();
    const center=flow.screenToFlowPosition({x:box.left+box.width/2,y:box.top+box.height/2});
    const placed=[...nodesRef.current];
    for(const card of cards){
      const w=card.width||360,h=card.height||220;
      let x=center.x-w/2,y=center.y-h/2;
      for(let attempt=0;attempt<10000;attempt++){
        const hits=placed.filter(n=>x<(n.position.x+(n.measured?.width||n.width||360))+24 && x+w+24>n.position.x && y<(n.position.y+(n.measured?.height||n.height||220))+24 && y+h+24>n.position.y);
        if(!hits.length)break;
        y=Math.max(...hits.map(n=>n.position.y+(n.measured?.height||n.height||220)))+32;
      }
      placed.push({...card,position:{x,y},selected:true,style:{width:w,...(card.type==='image'?{height:h}:{})}});
    }
    commit(placed.map(n=>cards.some(c=>c.id===n.id)?n:{...n,selected:false}));
    if(cards.length){const last=placed[placed.length-1];void flow.setCenter(last.position.x+(last.width||360)/2,last.position.y+(last.height||220)/2,{zoom:flow.getZoom(),duration:200});}
  },[flow,commit]);
  const addText=useCallback((markdown='')=>{if(busyRef.current||uploadRef.current||!activeRef.current)return;addCards([{id:crypto.randomUUID(),type:'text',position:{x:0,y:0},data:{markdown},width:360}]);},[addCards]);
  const importImages=useCallback(async(files:File[])=>{
    if(busyRef.current||uploadRef.current||!activeRef.current)return;
    uploadRef.current=true;setUploading(true);
    const cards:Card[]=[];
    try {
      for(const file of files){
        const image=await storage.upload(file);const scale=Math.min(1,600/Math.max(image.width,image.height));
        cards.push({id:crypto.randomUUID(),type:'image',position:{x:0,y:0},width:image.width*scale,height:image.height*scale,data:{markdown:'',asset:image.asset,naturalWidth:image.width,naturalHeight:image.height}});
      }
    }catch(e){showError(e);}finally{if(cards.length)addCards(cards);uploadRef.current=false;setUploading(false);}
  },[addCards,showError]);
  const undo=useCallback((redo=false)=>{
    if(busyRef.current||uploadRef.current)return;
    const from=redo?future:history,to=redo?history:future;
    const snapshot=from.current.pop();if(!snapshot)return;
    to.current.push(structuredClone(nodesRef.current));assign(snapshot);changed();renderHistory(n=>n+1);
  },[assign,changed]);
  useEffect(()=>{
    const paste=(e:ClipboardEvent)=>{
      if(editable(e.target)||inspect||dialog||busyRef.current||uploadRef.current)return;
      const files=Array.from(e.clipboardData?.files||[]).filter(f=>f.type.startsWith('image/'));
      if(files.length){e.preventDefault();void importImages(files);}else{const text=e.clipboardData?.getData('text/plain');if(text){e.preventDefault();addText(text);}}
    };
    const down=(e:KeyboardEvent)=>{
      if(editable(e.target))return;
      if(e.code==='Space'){e.preventDefault();setSpace(true);}
      if(e.key==='Escape')setInspect(null);
      if(inspect||dialog)return;
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();undo(e.shiftKey);}
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();undo(true);}
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();void flush().catch(()=>{});}
      if((e.key==='Delete'||e.key==='Backspace')&&!busyRef.current&&!uploadRef.current){e.preventDefault();if(nodesRef.current.some(n=>n.selected))commit(nodesRef.current.filter(n=>!n.selected));}
    };
    const up=()=>setSpace(false);
    window.addEventListener('paste',paste);window.addEventListener('keydown',down);window.addEventListener('keyup',up);window.addEventListener('blur',up);
    return()=>{window.removeEventListener('paste',paste);window.removeEventListener('keydown',down);window.removeEventListener('keyup',up);window.removeEventListener('blur',up);};
  },[addText,importImages,undo,commit,flush,inspect,dialog]);
  const actions=React.useMemo<Actions>(()=>({
    edit:(id,markdown)=>{if(nodesRef.current.find(n=>n.id===id)?.data.markdown!==markdown)commit(nodesRef.current.map(n=>n.id===id?{...n,data:{...n.data,markdown}}:n));},
    inspect:asset=>{setImageZoom(1);setInspect(asset);},editing:active=>{editingRef.current=active;setIsEditing(active);},
  }),[commit]);
  const submitName=async()=>{
    if(!name.trim()||busyRef.current)return;
    try{
      if(dialog==='new'){await flush();const entry=await storage.create(name.trim());setEntries(await storage.list());setDialog(null);await switchCanvas(entry.id);}
      else{await storage.rename(activeRef.current,name.trim());setEntries(await storage.list());setDialog(null);}
    }catch(e){showError(e);}
  };
  // Internal extension surface: read selection, retrieve original asset, batch-create cards.
  useEffect(()=>{const api={getSelectedCards:()=>structuredClone(nodesRef.current.filter(n=>n.selected)),getOriginalImage:(card:Card)=>card.data.asset?storage.assetUrl(card.data.asset):null,createCards:addCards};
    Object.assign(window,{infNote:api});return()=>{delete (window as unknown as Record<string,unknown>).infNote;};},[addCards]);
  const current=entries.find(e=>e.id===active);
  return <ActionsContext.Provider value={actions}><div className="app" onContextMenuCapture={event=>event.preventDefault()}>
    <aside><div className="brand"><div className="brand-icon"><Layers size={22}/></div><div>infNote<small>留住思考的片段</small></div></div>
      <div className="section-title">我的画布 <span>{entries.length}</span></div>
      <nav>{entries.map(entry=><button disabled={busy||uploading||isEditing} className={'canvas-item '+(active===entry.id?'active':'')} key={entry.id} onClick={()=>void switchCanvas(entry.id)}><Layers size={16}/><span>{entry.name}</span>{active===entry.id&&<span className="active-dot"/>}</button>)}</nav>
      <button className="new-canvas" disabled={busy||uploading||isEditing} onClick={()=>{setName('');setDialog('new');}}><Plus size={17}/>新建画布</button>
      <div className="sidebar-bottom"><div className="local-badge"><span/>仅保存在本机</div><p title={dataDir}>{dataDir||'正在读取保存位置…'}</p><button className="path-button" onClick={()=>{void navigator.clipboard.writeText(dataDir).then(()=>{setCopied(true);setTimeout(()=>setCopied(false),2000);}).catch(showError);}}>{copied?<Check size={13}/>:<Copy size={13}/>} {copied?'路径已复制':'复制保存路径'}</button></div>
    </aside>
    <main><header><div className="canvas-heading"><div className="eyebrow">个人知识空间 / 画布</div><div className="title-row"><h1>{current?.name||'我的画布'}</h1><button title="重命名画布" disabled={!active||busy||isEditing} className="icon-button" onClick={()=>{setName(current?.name||'');setDialog('rename');}}><Pencil size={14}/></button><span className="count">{nodes.length} 张卡片</span></div></div><div className={'save-state '+status}>{status==='saving'?<LoaderCircle size={14} className="spin"/>:status==='error'?<AlertCircle size={14}/>:<span className="status-dot"/>}{({saved:'所有更改已保存',pending:'等待保存',saving:'正在保存',error:'保存失败'})[status]}{status==='error'&&<button onClick={()=>void flush().catch(()=>{})}>重试</button>}</div></header>
    <div className="toolbar"><div className="tool-group"><button disabled={busy||uploading||isEditing} onClick={()=>addText()}><Type size={17}/>文字卡片</button><button disabled={busy||uploading||isEditing} onClick={()=>fileInput.current?.click()}><ImagePlus size={17}/>导入图片</button></div><div className="toolbar-right"><button title="撤销 Ctrl+Z" disabled={!history.current.length||busy||isEditing} onClick={()=>undo()}><Undo2 size={17}/></button><button title="重做 Ctrl+Shift+Z" disabled={!future.current.length||busy||isEditing} onClick={()=>undo(true)}><Redo2 size={17}/></button><span className="divider"/><button onClick={()=>void flow.fitView({padding:0.2,duration:250,maxZoom:1})}><Maximize size={16}/>适应全部</button></div></div>
    <div ref={board} className={'board '+(space?'panning':'')} onDragOver={e=>{e.preventDefault();}} onDrop={e=>{e.preventDefault();void importImages(Array.from(e.dataTransfer.files));}}>
      <ReactFlow<Card> nodes={nodes} edges={[]} nodeTypes={nodeTypes} onNodesChange={changes=>{
        if(busyRef.current)return;
        const meaningful=changes.some(c=>c.type==='position'&&!!c.position || c.type==='dimensions'&&!!c.resizing);
        if(meaningful&&!interaction.current){checkpoint();interaction.current=true;}
        const next=applyNodeChanges(changes,nodesRef.current);
        assign(next.map(n=>changes.some(c=>'id' in c&&c.id===n.id&&c.type==='dimensions'&&c.resizing!==undefined)?{...n,...(n.type==='text'?{height:undefined}:{}),style:{width:n.width,...(n.type==='image'?{height:n.height}:{})}}:n));
        if(meaningful)changed();
        if(changes.some(c=>(c.type==='position'&&c.dragging===false)||(c.type==='dimensions'&&c.resizing===false)))interaction.current=false;
      }} onMoveEnd={(_,v)=>{if(!busyRef.current&&(v.x!==viewport.current.x||v.y!==viewport.current.y||v.zoom!==viewport.current.zoom)){viewport.current=v;changed();}}}
        nodesConnectable={false} nodesDraggable={!busy&&!uploading} selectionOnDrag={!space} panOnDrag={space?[0,1,2]:[1,2]} panActivationKeyCode="Space" selectionKeyCode={null} multiSelectionKeyCode="Shift" deleteKeyCode={null} minZoom={0.1} maxZoom={4} onlyRenderVisibleElements>
        <Background color="#d8dedb" gap={24} size={1}/><Controls showInteractive={false}/><MiniMap pannable zoomable nodeColor={n=>n.type==='image'?'#c2d7cc':'#e4d8b7'} maskColor="rgba(246,248,245,.75)"/>
      </ReactFlow>
      {!nodes.length&&!busy&&<div className="empty-state"><div className="empty-icon"><Layers size={30}/><span>+</span></div><h2>让想法，有处安放。</h2><p>截图、复制，然后在这里按 <kbd>Ctrl</kbd> + <kbd>V</kbd><br/>把值得留下的片段，慢慢整理成自己的知识。</p><button onClick={()=>addText('## 我的第一张笔记\n\n在这里记录一个值得留下的想法。')}><Plus size={16}/>写下第一条笔记</button></div>}
      {(busy||uploading)&&<div className="loading-overlay"><LoaderCircle size={24} className="spin"/>{uploading?'正在保存原始图片…':'正在打开画布…'}</div>}
      <div className="board-hint">Ctrl+V 粘贴 · 空格拖动画布 · 滚轮缩放 · 双击编辑 / 查看</div>
    </div></main>
    <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp" multiple hidden onChange={e=>{void importImages(Array.from(e.target.files||[]));e.target.value='';}}/>
    {error&&<div className="toast" role="alert"><AlertCircle size={17}/><span>{error}</span><button aria-label="关闭提示" onClick={()=>setError('')}><X size={16}/></button></div>}
    {dialog&&<div className="modal-backdrop"><form className="dialog" onSubmit={e=>{e.preventDefault();void submitName();}}><h2>{dialog==='new'?'新建画布':'重命名画布'}</h2><p>给这片思考空间起个名字。</p><input autoFocus aria-label="画布名称" value={name} maxLength={100} onChange={e=>setName(e.target.value)}/><div className="dialog-actions"><button type="button" onClick={()=>setDialog(null)}>取消</button><button className="primary" disabled={!name.trim()} type="submit">确定</button></div></form></div>}
    {inspect&&<div className="image-viewer"><div className="viewer-bar"><span>原始截图</span><div><button onClick={()=>setImageZoom(z=>Math.max(.1,z-.25))}>−</button><span>{Math.round(imageZoom*100)}%</span><button onClick={()=>setImageZoom(z=>Math.min(5,z+.25))}>＋</button><a href={storage.assetUrl(inspect)} target="_blank" rel="noreferrer">打开原图 ↗</a><button aria-label="关闭原图" onClick={()=>setInspect(null)}><X size={21}/></button></div></div><div className="viewer-content" onWheel={e=>{if(e.ctrlKey){e.preventDefault();setImageZoom(z=>Math.max(.1,Math.min(5,z-e.deltaY*.002)));}}}><img alt="原始截图" src={storage.assetUrl(inspect)} style={{width:`${imageZoom*100}%`,maxWidth:imageZoom===1?'100%':'none'}}/></div></div>}
  </div></ActionsContext.Provider>;
}
createRoot(document.getElementById('root')!).render(<ReactFlowProvider><App/></ReactFlowProvider>);
