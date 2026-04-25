# -*- coding: utf-8 -*-

import base64
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, jsonify, request, render_template, flash, redirect, url_for, Response, session, g
from flask import send_from_directory

import processor
from config import get_config, ensure_defaults, save_config, get_models_dict
from processor import _parse_pending_filename, call_llm_api, generate_explanation, call_tts_api

# IP封禁列表和请求统计
ipRequests = {}  # {ip: count}
bannedIPs = set()

# 初始化全局模型字典
models_dict = get_models_dict()

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'changeme')

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

def ensure_ascii(s, field_name):
    """确保字符串只包含ASCII字符"""
    if not s:
        raise ValueError(f"{field_name} 不能为空")
    try:
        s.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(f"{field_name} 只能包含英文字母、数字和符号（ASCII字符），请检查是否有中文或特殊符号。")

UPLOAD_FOLDER = 'uploads'
PENDING_DIR = 'pending'
PROCESSING_DIR = 'processing'
RESULTS_DIR = 'results'
CONFIG_FILE = 'config.yaml'


os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'your-secret-key-here'  # 用于 flash 消息

SERVER_START_TIME = time.time()

# 记录跳转目标页面
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session['admin_logged_in'] = True
            next_url = request.args.get('next') or url_for('admin_dashboard')
            return redirect(next_url)
        flash('无效的用户名或密码')
    return render_template('admin_login.html')

@app.before_request
def inject_customization():
    # IP统计和封禁检查
    ip = request.remote_addr
    if ip in bannedIPs:
        return jsonify({'error': 'IP已被封禁'}), 403
    ipRequests[ip] = ipRequests.get(ip, 0) + 1
    
    customization = {'bg_type': 'gradient', 'bg_color1': '#667eea', 'bg_color2': '#764ba2', 'bg_image': '', 'opacity': 100}
    try:
        cfg = get_config()
        if cfg and 'customization' in cfg:
            customization = cfg['customization']
    except Exception:
        pass
    g.customization = customization

@app.route('/')
def index():
    """主页，返回网页版客户端UI"""
    return render_template('index.html')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """接收客户端上传的图片"""
    try:
        data = request.get_json()
        if not data or 'image_data' not in data:
            return jsonify({'error': 'No image data provided'}), 400

        query_code = str(uuid.uuid4())
        image_data = data['image_data']
        extension = image_data.split(';')[0].split('/')[-1]
        # 支持可选的优先级，默认 0，越小优先级越高
        priority = int(data.get('priority', 0))
        # 文件名形如: 00000001_<query_code>.<ext>
        filename = f"{priority:08d}_{query_code}.{extension}"
        filepath = os.path.join(PENDING_DIR, filename)

        image_data = image_data.split(',')[1]
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(image_data))

        logger.info(f"图片已上传，生成查询码: {query_code}")
        return jsonify({'query_code': query_code}), 200

    except Exception as e:
        logger.error(f"上传图片时发生错误: {e}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/query_status', methods=['POST'])
def query_status():
    """处理客户端的查询请求"""
    try:
        data = request.get_json()
        if not data or 'query_code' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

        query_code = data['query_code']

        result_file = None
        for f in os.listdir(RESULTS_DIR):
            if f.startswith(query_code) and f.endswith('.txt'):
                result_file = os.path.join(RESULTS_DIR, f)
                break

        status = 'pending'
        result_text = ''

        if result_file:
            status = 'completed'
            with open(result_file, 'r', encoding='utf-8') as f:
                result_text = f.read()
        else:
            for f in os.listdir(PROCESSING_DIR):
                if f.startswith(query_code):
                    status = 'processing'
                    break
            if status == 'pending':
                for f in os.listdir(PENDING_DIR):
                    if f.startswith(query_code):
                        status = 'pending'
                        break
                else:
                    return jsonify({'error': 'Query code not found'}), 404

        audio_path = os.path.join(RESULTS_DIR, f"{query_code}_audio.wav")
        has_audio = os.path.exists(audio_path)

        return jsonify({'status': status, 'result': result_text, 'has_audio': has_audio})

    except Exception as e:
        logger.error(f"Query status error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/generate_audio', methods=['POST'])
def generate_audio_api():
    """生成语音讲解"""
    try:
        data = request.get_json()
        if not data or 'query_code' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

        query_code = data['query_code']
        cfg = get_config()
        tts_cfg = cfg.get('tts', {})

        if not tts_cfg.get('enabled', False):
            return jsonify({'error': 'TTS 功能未启用'}), 400

        audio_path = os.path.join(RESULTS_DIR, f"{query_code}_audio.wav")
        if os.path.exists(audio_path):
            return jsonify({'status': 'exists', 'audio_url': f'/results/{query_code}_audio.wav'})

        audio_path, explanation_text = generate_explanation(query_code)
        audio_filename = os.path.basename(audio_path)

        return jsonify({
            'status': 'generated',
            'audio_url': f'/results/{audio_filename}',
            'explanation': explanation_text[:500]
        })

    except Exception as e:
        logger.error(f"生成语音错误: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/results/<path:filename>')
def serve_audio(filename):
    """提供音频文件"""
    return send_from_directory(RESULTS_DIR, filename)

from flask import render_template

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 数据聚合
    try:
        cfg = get_config()
        pending = len([f for f in os.listdir(PENDING_DIR)])
        processing = len([f for f in os.listdir(PROCESSING_DIR)])
        completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
        models_list = cfg.get('models', [])
        default_model = cfg.get('default_model', '')
        uptime = int(time.time() - SERVER_START_TIME)
        # 最近结果预览
        recent_results = []
        for f in sorted(os.listdir(RESULTS_DIR), key=lambda x: os.path.getmtime(os.path.join(RESULTS_DIR, x)), reverse=True)[:5]:
            path = os.path.join(RESULTS_DIR, f)
            try:
                with open(path, 'r', encoding='utf-8') as rf:
                    first_line = rf.readline().strip()
            except Exception:
                first_line = ''
            code = f.rsplit('.', 1)[0]
            recent_results.append({'code': code, 'time': time.ctime(os.path.getmtime(path)), 'preview': first_line[:80]})
        # 任务简览
        tasks = []
        for fname in os.listdir(PENDING_DIR):
            full = os.path.join(PENDING_DIR, fname)
            if os.path.isfile(full):
                priority, code = _parse_pending_filename(fname)
                tasks.append({'priority': priority, 'code': code, 'status': 'pending'})
        for fname in os.listdir(PROCESSING_DIR):
            full = os.path.join(PROCESSING_DIR, fname)
            if os.path.isfile(full):
                code = fname.split('.', 1)[0]
                tasks.append({'priority': 99999999, 'code': code, 'status': 'processing'})
        vision_model = cfg.get('vision_model', '')
        text_model = cfg.get('text_model', '')
        customization = cfg.get('customization', {'bg_type': 'gradient', 'bg_color1': '#667eea', 'bg_color2': '#764ba2', 'bg_image': ''})
        summary = {
            'pending': pending,
            'processing': processing,
            'completed': completed
        }
        return render_template('admin_dashboard.html', summary=summary, models=models_list, default_model=default_model, vision_model=vision_model, text_model=text_model, uptime=uptime, recent_results=recent_results, tasks=tasks, customization=customization)
    except Exception as e:
        logger.error(f"admin_dashboard error: {e}")
        # 回退到简单文本页面，避免阻塞
        return f"Admin dashboard error: {e}"

@app.route('/admin')
@admin_required
def admin():
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logs', methods=['GET'])
@admin_required
def admin_logs():
    logs = _tail_log(500)
    return render_template('logs.html', logs=logs)

@app.route('/admin/ip')
@admin_required
def ip_management():
    return render_template('ip_management.html', stats=ipRequests, banned=list(bannedIPs))

@app.route('/admin/ip/ban', methods=['POST'])
@admin_required
def ban_ip():
    ip = request.form.get('ip', '').strip()
    if ip:
        bannedIPs.add(ip)
        flash(f'已封禁 IP: {ip}', 'success')
    return redirect(url_for('ip_management'))

@app.route('/admin/ip/unban', methods=['POST'])
@admin_required
def unban_ip():
    ip = request.form.get('ip', '').strip()
    if ip and ip in bannedIPs:
        bannedIPs.discard(ip)
        flash(f'已解封 IP: {ip}', 'success')
    return redirect(url_for('ip_management'))

def _tail_log(n=200):
    log_path = 'server.log'
    if not os.path.exists(log_path):
        return ''
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception:
        return ''

def _collect_tasks():
    tasks = []
    try:
        for fname in os.listdir(PENDING_DIR):
            full = os.path.join(PENDING_DIR, fname)
            if os.path.isfile(full):
                priority, code = _parse_pending_filename(fname)
                tasks.append({'priority': priority, 'code': code, 'status': 'pending'})
        for fname in os.listdir(PROCESSING_DIR):
            full = os.path.join(PROCESSING_DIR, fname)
            if os.path.isfile(full):
                code = fname.split('.', 1)[0]
                tasks.append({'priority': 99999999, 'code': code, 'status': 'processing'})
        tasks.sort(key=lambda t: (t['priority'], t['code']))
    except Exception:
        pass
    return tasks
@admin_required
def admin_api_summary():
    cfg = get_config()
    pending = len([f for f in os.listdir(PENDING_DIR)])
    processing = len([f for f in os.listdir(PROCESSING_DIR)])
    completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
    models_list = cfg.get('models', [])
    default_model = cfg.get('default_model', '')
    uptime = int(time.time() - SERVER_START_TIME)
    return jsonify({
        'pending': pending,
        'processing': processing,
        'completed': completed,
        'models_count': len(models_list),
        'default_model': default_model,
        'uptime_seconds': uptime
    })

@app.route('/admin/api/models', methods=['GET'])
@admin_required
def admin_api_models():
    return jsonify(get_config().get('models', []))

@app.route('/admin/api/tasks', methods=['GET'])
@admin_required
def admin_api_tasks():
    return jsonify({'tasks': _collect_tasks()})

@app.route('/admin/set_default_models', methods=['POST'])
@admin_required
def set_default_models():
    cfg = get_config()
    vision_model = request.form.get('vision_model')
    text_model = request.form.get('text_model')
    if vision_model and text_model and vision_model in models_dict and text_model in models_dict:
        cfg['vision_model'] = vision_model
        cfg['text_model'] = text_model
        save_config(cfg)
        flash(f'默认视觉模型已设为 {vision_model}，默认文本模型已设为 {text_model}', 'success')
    else:
        flash('请选择两个有效的模型', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/set_models', methods=['POST'])
@admin_required
def set_models():
    """设置视觉模型和文本模型"""
    cfg = get_config()
    vision_model = request.form.get('vision_model')
    text_model = request.form.get('text_model')
    if vision_model and text_model:
        if vision_model in models_dict and text_model in models_dict:
            cfg['vision_model'] = vision_model
            cfg['text_model'] = text_model
            save_config(cfg)
            flash(f'视觉模型已设为 {vision_model}，文本模型已设为 {text_model}', 'success')
        else:
            flash('所选模型不存在', 'error')
    else:
        flash('请选择两个模型', 'error')
    return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin'))

@app.route('/admin/customization', methods=['GET', 'POST'])
@admin_required
def customization_page():
    """个性化设置页面"""
    cfg = get_config()
    if request.method == 'POST':
        cfg.setdefault('customization', {})
        cfg['customization']['bg_type'] = request.form.get('bg_type', 'gradient')
        cfg['customization']['bg_color1'] = request.form.get('bg_color1', '#667eea')
        cfg['customization']['bg_color2'] = request.form.get('bg_color2', '#764ba2')
        cfg['customization']['bg_image'] = request.form.get('bg_image', '')
        cfg['customization']['opacity'] = int(request.form.get('opacity', 100))
        save_config(cfg)
        flash('个性化设置已保存', 'success')
        return redirect(url_for('customization_page'))
    customization = cfg.get('customization', {'bg_type': 'gradient', 'bg_color1': '#667eea', 'bg_color2': '#764ba2', 'bg_image': ''})
    return render_template('customization.html', customization=customization)


@app.route('/admin/tts', methods=['GET', 'POST'])
@admin_required
def tts_page():
    """TTS 设置页面"""
    cfg = get_config()
    if request.method == 'POST':
        cfg.setdefault('tts', {})
        cfg['tts']['enabled'] = request.form.get('enabled') == 'on'
        cfg['tts']['engine'] = request.form.get('engine', 'qwen-tts')
        cfg['tts']['api_base'] = request.form.get('api_base', '').strip()
        cfg['tts']['voice'] = request.form.get('voice', 'default')
        cfg['tts']['speed'] = float(request.form.get('speed', 1.0))
        cfg['tts']['model_name'] = request.form.get('model_name', 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice')
        cfg['tts']['output_dir'] = request.form.get('output_dir', 'D:\\qwen-tts-webui\\core\\outputs').strip()
        cfg['tts']['refer_wav'] = request.form.get('refer_wav', '').strip()
        cfg['tts']['prompt_text'] = request.form.get('prompt_text', '').strip()
        cfg['tts']['prompt_language'] = request.form.get('prompt_language', 'zh')
        cfg['tts']['sovits_model'] = request.form.get('sovits_model', '').strip()
        cfg['tts']['gpt_model'] = request.form.get('gpt_model', '').strip()
        save_config(cfg)
        flash('TTS 设置已保存', 'success')
        return redirect(url_for('tts_page'))
    tts_cfg = cfg.get('tts', {'enabled': False, 'engine': 'qwen-tts', 'api_base': 'http://127.0.0.1:7860', 'voice': 'default', 'speed': 1.0, 'model_name': 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', 'output_dir': 'D:\\qwen-tts-webui\\core\\outputs', 'refer_wav': '', 'prompt_text': '', 'prompt_language': 'zh', 'sovits_model': '', 'gpt_model': ''})
    return render_template('tts_settings.html', tts=tts_cfg)


@app.route('/admin/tts/test', methods=['POST'])
@admin_required
def test_tts():
    """测试 TTS 连接"""
    try:
        from processor import call_tts_api
        cfg = get_config()
        tts_cfg = cfg.get('tts', {})
        
        if not tts_cfg.get('enabled'):
            flash('TTS 功能未启用', 'error')
            return redirect(url_for('tts_page'))
        
        test_text = "你好，这是语音测试。"
        test_code = f"test_{uuid.uuid4().hex[:8]}"
        
        audio_path = call_tts_api(test_text, test_code)
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        flash('TTS 连接测试成功！', 'success')
    except Exception as e:
        flash(f'TTS 连接测试失败: {str(e)}', 'error')
    
    return redirect(url_for('tts_page'))

@app.route('/admin/models')
@admin_required
def models_page():
    """模型管理页面"""
    cfg = get_config()
    models_list = cfg.get('models', [])
    vision_model = cfg.get('vision_model', '')
    text_model = cfg.get('text_model', '')
    return render_template('models.html', models=models_list, vision_model=vision_model, text_model=text_model)

@app.route('/admin/models/add', methods=['GET', 'POST'])
@admin_required
def add_model():
    if request.method == 'POST':
        cfg = get_config()
        name = request.form['name'].strip()
        if not name:
            flash('模型名称不能为空', 'error')
            return redirect(url_for('add_model'))
        if name in models_dict:
            flash(f'模型 "{name}" 已存在', 'error')
            return redirect(url_for('add_model'))
        try:
            ensure_ascii(request.form['api_key'].strip(), 'API key')
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('add_model'))

        new_model = {
            'name': name,
            'api_base': request.form['api_base'].strip(),
            'api_key': request.form['api_key'].strip(),
            'default_temperature': float(request.form['default_temperature']),
            'timeout': int(request.form['timeout'])
        }
        is_default = request.form.get('is_default') == 'on'
        cfg['models'].append(new_model)
        if is_default:
            cfg['default_model'] = name
        save_config(cfg)
        logger.info(f"模型 {name} 已添加。")
        flash(f'模型 "{name}" 添加成功', 'success')
        return redirect(url_for('admin'))
    return render_template('model_form.html', action='add', model=None)

@app.route('/admin/models/edit/<path:name>', methods=['GET', 'POST'])
@admin_required
def edit_model(name):
    cfg = get_config()
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        try:
            ensure_ascii(request.form['api_key'].strip(), 'API key')
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('edit_model', name=name))

        model = models_dict[name]
        model['api_base'] = request.form['api_base'].strip()
        model['api_key'] = request.form['api_key'].strip()
        model['default_temperature'] = float(request.form['default_temperature'])
        model['timeout'] = int(request.form['timeout'])

        save_config(cfg)
        logger.info(f"模型 {name} 已更新。")
        flash(f'模型 "{name}" 更新成功', 'success')
        return redirect(url_for('admin'))

    model = models_dict[name]
    return render_template('model_form.html', action='edit', model=model)

@app.route('/admin/models/delete/<path:name>', methods=['POST'])
@admin_required
def delete_model(name):
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))

    cfg = get_config()
    
    cfg['models'] = [m for m in cfg['models'] if m['name'] != name]
    del models_dict[name]

    if cfg.get('default_model') == name:
        cfg['default_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    if cfg.get('vision_model') == name:
        cfg['vision_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    if cfg.get('text_model') == name:
        cfg['text_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    save_config(cfg)
    logger.info(f"模型 {name} 已删除。")
    flash(f'模型 "{name}" 删除成功', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/models/set_default/<path:name>', methods=['POST'])
@admin_required
def set_default_model(name):
    cfg = get_config()
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))

    cfg['default_model'] = name
    save_config(cfg)
    logger.info(f"默认模型已设置为 {name}。")
    flash(f'默认模型已设为 "{name}"', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/models/test/<path:name>', methods=['POST'])
@admin_required
def test_model(name):
    """测试模型连接是否正常"""
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))
    
    try:
        model_info = models_dict[name]
        test_messages = [{"role": "user", "content": "hello"}]
        result = call_llm_api(name, test_messages)
        flash(f'模型 "{name}" 连接测试成功！响应: {result[:200]}...', 'success')
    except Exception as e:
        flash(f'模型 "{name}" 连接测试失败: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/chat_test')
def chat_test():
    """对话测试页面"""
    return render_template('chat_test.html', models=get_config().get('models', []))

@app.route('/chat_test_api', methods=['POST'])
def chat_test_api():
    """对话测试 API，支持文本和图片"""
    try:
        data = request.get_json()
        if not data or 'model' not in data or 'prompt' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        model_name = data['model']
        prompt = data['prompt']
        image_data = data.get('image_data')  # base64 data URL

        # 构建消息
        messages = [{"role": "user", "content": prompt}]
        image_url = image_data if image_data else None

        # 调用 API
        response = call_llm_api(model_name, messages, image_url)
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"对话测试错误: {e}")
        return jsonify({'error': str(e)}), 500

# --- 代理端点 ---
@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """转发请求到配置的模型，用于兼容其他客户端"""
    cfg = get_config()
    try:
        body = request.get_json()
        if not body:
            return jsonify({'error': 'Invalid JSON'}), 400

        model_name = body.get('model') or cfg.get('default_model')
        if not model_name:
            return jsonify({'error': 'No model specified and no default model configured'}), 400

        model_cfg = models_dict.get(model_name)
        if not model_cfg:
            return jsonify({'error': f'Model "{model_name}" not found in configuration'}), 400

        api_base = model_cfg['api_base']
        api_key = model_cfg['api_key']
        default_temperature = model_cfg.get('default_temperature', 0.7)
        timeout = model_cfg.get('timeout', 60)

        if 'temperature' not in body:
            body['temperature'] = default_temperature

        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"转发请求到模型: {model_name}, URL: {url}")
        resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

    except requests.exceptions.Timeout:
        logger.error("上游请求超时")
        return jsonify({'error': 'Upstream timeout'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"上游请求错误: {str(e)}")
        return jsonify({'error': f'Upstream error: {str(e)}'}), 502
    except Exception as e:
        logger.error(f"处理代理请求时发生错误: {str(e)}")
        return jsonify({'error': f'Proxy error: {str(e)}'}), 500

# --- 初始化 ---
_SCANNER_INITIALIZED = False
_EXECUTOR = None

def _init_scanner_once():
    global _SCANNER_INITIALIZED, _EXECUTOR
    if _SCANNER_INITIALIZED:
        return
    _EXECUTOR = ThreadPoolExecutor(max_workers=4)
    # 将后台任务扫描交给 processor 模块管理
    processor.start_scanner(_EXECUTOR)
    logger.info("后台任务扫描已启动")
    _SCANNER_INITIALIZED = True

if __name__ == '__main__':
    _init_scanner_once()
    logger.info("服务器启动，开始监听...")

    # 从环境变量获取端口，默认 8000
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # 在非主模块运行时（如某些 WSGI 服务器），也尝试启动后台扫描以处理任务
    _init_scanner_once()
