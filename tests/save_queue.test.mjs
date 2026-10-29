import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SaveQueue, serialize } from '../frontend/src/storage.ts';

test('writes stay serialized across canvases and recover after failure', async () => {
  const calls = [];
  const waiting = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push([url, JSON.parse(options.body)]);
    return new Promise(resolve => waiting.push(resolve));
  };
  try {
    const queue = new SaveQueue();
    const first = queue.save('canvas-a', {version:1, nodes:[], viewport:{x:1,y:2,zoom:1}});
    const rejected = assert.rejects(first, /disk full/);
    const second = queue.save('canvas-b', {version:1, nodes:[], viewport:{x:50,y:60,zoom:1}});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 1);
    waiting.shift()({ok:false, json:async()=>({detail:'disk full'})});
    await rejected;
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 2);
    assert.equal(calls[1][0], '/api/canvases/canvas-b');
    assert.equal(calls[1][1].viewport.x, 50);
    waiting.shift()({ok:true,json:async()=>({ok:true})});
    await second;
  } finally {globalThis.fetch=original;}
});

test('persisted cards omit transient selection and keep content and dimensions', () => {
  const result = serialize([{id:'one',type:'image',position:{x:10,y:20},width:300,height:200,selected:true,dragging:true,data:{markdown:'',asset:'original.png'}}], {x:0,y:0,zoom:.5});
  assert.equal(result.nodes[0].selected, undefined);
  assert.equal(result.nodes[0].dragging, undefined);
  assert.equal(result.nodes[0].width, 300);
  assert.equal(result.nodes[0].data.asset, 'original.png');
});
