import type { Node, Viewport } from '@xyflow/react';
export type CardData = { markdown: string; asset?: string; naturalWidth?: number; naturalHeight?: number };
export type Card = Node<CardData, 'text' | 'image'>;
export type Canvas = { version: 1; nodes: Card[]; viewport: Viewport };
export type Entry = { id: string; name: string };
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`);
  }
  return response.json();
}
const json = (method: string, body: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const storage = {
  info: () => request<{dataDir: string}>('/info'),
  list: () => request<Entry[]>('/canvases'),
  create: (name: string) => request<Entry>('/canvases', json('POST', {name})),
  rename: (id: string, name: string) => request('/canvases/' + id, json('PATCH', {name})),
  load: (id: string) => request<Canvas>('/canvases/' + id),
  save: (id: string, canvas: Canvas) => request('/canvases/' + id, json('PUT', canvas)),
  upload: (file: File) => { const body = new FormData(); body.append('file', file); return request<{asset: string; width: number; height: number}>('/assets', {method:'POST', body}); },
  assetUrl: (asset: string) => '/api/assets/' + encodeURIComponent(asset),
};
// Serialized persistence: snapshots captured by caller, never read from a later active canvas.
export class SaveQueue {
  private tail: Promise<unknown> = Promise.resolve();
  save(id: string, canvas: Canvas) {
    const result = this.tail.catch(() => {}).then(() => storage.save(id, canvas));
    this.tail = result;
    return result;
  }
}
export function serialize(nodes: Card[], viewport: Viewport): Canvas {
  return {version:1, viewport, nodes: nodes.map(n => ({id:n.id, type:n.type!, position:n.position, data:n.data, width:n.width || Number(n.style?.width) || 360, ...(n.type === 'image' ? {height:n.height || Number(n.style?.height)} : {})}))};
}
