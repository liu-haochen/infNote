import io
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class Viewport(Position):
    zoom: float = Field(default=1, ge=0.1, le=4)


class CardData(BaseModel):
    markdown: str = ''
    asset: str | None = None
    naturalWidth: int | None = None
    naturalHeight: int | None = None


class Card(BaseModel):
    id: str
    type: Literal['text', 'image']
    position: Position
    data: CardData
    width: float = Field(default=360, ge=80, le=20000)
    height: float | None = Field(default=None, ge=20, le=100000)


class Canvas(BaseModel):
    version: Literal[1] = 1
    nodes: list[Card] = Field(default_factory=list)
    viewport: Viewport = Field(default_factory=lambda: Viewport(x=0, y=0))


class Name(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def create_app(data_dir: Path | None = None, serve_frontend: bool = True):
    root = Path(data_dir or os.environ.get('INFNOTE_DATA_DIR', Path.home() / 'infNoteData')).resolve()
    canvases, assets = root / 'canvases', root / 'assets'
    canvases.mkdir(parents=True, exist_ok=True)
    assets.mkdir(exist_ok=True)
    lock = threading.RLock()

    def atomic(path, value):
        temp = path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)

    def read(path):
        try:
            return json.loads(path.read_text('utf-8'))
        except (OSError, ValueError):
            return json.loads(path.with_suffix('.bak').read_text('utf-8'))

    index_path = root / 'index.json'
    if not index_path.exists():
        first = uuid.uuid4().hex
        atomic(canvases / f'{first}.json', Canvas().model_dump())
        atomic(index_path, [{'id': first, 'name': '临时收集'}])

    def index():
        return read(index_path)

    def canvas_path(canvas_id):
        if not re.fullmatch(r'[a-f0-9]{32}', canvas_id) or not any(c['id'] == canvas_id for c in index()):
            raise HTTPException(404, '画布不存在')
        return canvases / f'{canvas_id}.json'

    app = FastAPI(title='infNote Local API')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        if host not in ('localhost', '127.0.0.1', 'testserver'):
            return JSONResponse({'detail': '仅允许本机访问'}, status_code=403)
        origin = request.headers.get('origin')
        if origin:
            from urllib.parse import urlparse
            if urlparse(origin).hostname not in ('localhost', '127.0.0.1'):
                return JSONResponse({'detail': '拒绝外部来源'}, status_code=403)
        return await call_next(request)

    @app.exception_handler(OSError)
    async def storage_error(request, error):
        return JSONResponse({'detail': '本地文件读写失败，请检查磁盘空间和目录权限'}, status_code=500)

    @app.get('/api/info')
    def info():
        return {'dataDir': str(root), 'app': 'infNote'}

    @app.get('/api/canvases')
    def list_canvases():
        with lock:
            return index()

    @app.post('/api/canvases', status_code=201)
    def create_canvas(body: Name):
        with lock:
            entry = {'id': uuid.uuid4().hex, 'name': body.name.strip() or '未命名画布'}
            atomic(canvases / f"{entry['id']}.json", Canvas().model_dump())
            entries = index() + [entry]
            shutil.copyfile(index_path, index_path.with_suffix('.bak'))
            atomic(index_path, entries)
            return entry

    @app.patch('/api/canvases/{canvas_id}')
    def rename(canvas_id: str, body: Name):
        with lock:
            canvas_path(canvas_id)
            entries = index()
            for entry in entries:
                if entry['id'] == canvas_id:
                    entry['name'] = body.name.strip() or '未命名画布'
            shutil.copyfile(index_path, index_path.with_suffix('.bak'))
            atomic(index_path, entries)
            return {'ok': True}

    @app.get('/api/canvases/{canvas_id}')
    def get_canvas(canvas_id: str):
        with lock:
            path = canvas_path(canvas_id)
            try:
                return Canvas.model_validate(read(path))
            except (ValueError, TypeError):
                try:
                    return Canvas.model_validate_json(path.with_suffix('.bak').read_text('utf-8'))
                except (ValueError, OSError):
                    raise HTTPException(500, '画布及备份无法读取，请保留文件并恢复备份')

    @app.put('/api/canvases/{canvas_id}')
    def save_canvas(canvas_id: str, body: Canvas):
        with lock:
            path = canvas_path(canvas_id)
            for node in body.nodes:
                if node.type == 'image' and (not node.data.asset or not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp|gif|bmp)', node.data.asset) or not (assets / node.data.asset).is_file()):
                    raise HTTPException(422, '图片资源不存在')
            # Back up validated content, including recovery from a broken primary file.
            previous = get_canvas(canvas_id)
            atomic(path.with_suffix('.bak'), previous.model_dump())
            atomic(path, body.model_dump())
            return {'ok': True}

    @app.post('/api/assets', status_code=201)
    async def upload(file: UploadFile):
        content = await file.read(30 * 1024 * 1024 + 1)
        if len(content) > 30 * 1024 * 1024:
            raise HTTPException(413, '单张图片不能超过 30 MB')
        try:
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp', 'GIF': 'gif', 'BMP': 'bmp'}.get(image.format)
                image.verify()
            if not extension:
                raise ValueError()
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, '请选择有效的 PNG、JPEG、WebP、GIF 或 BMP 图片')
        name = f'{uuid.uuid4().hex}.{extension}'
        target = assets / name
        temporary = target.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        return {'asset': name, 'width': width, 'height': height}

    @app.get('/api/assets/{name}')
    def get_asset(name: str):
        if not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp|gif|bmp)', name) or not (assets / name).is_file():
            raise HTTPException(404, '图片不存在')
        return FileResponse(assets / name, headers={'X-Content-Type-Options': 'nosniff'})

    dist = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    if serve_frontend and dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app
