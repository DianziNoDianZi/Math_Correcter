# -*- coding: utf-8 -*-

import base64
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import wraps
from collections import deque
import json

import requests
from flask import Flask, jsonify, request, render_template, flash, redirect, url_for, Response, session, g
from flask import send_from_directory
from flask_cors import CORS

import processor
import test_library
from config import get_config, ensure_defaults, save_config, get_models_dict
from config import UPLOAD_FOLDER, PENDING_DIR, PROCESSING_DIR, RESULTS_DIR
from processor import _parse_pending_filename, call_llm_api, generate_explanation, call_tts_api

# IP封禁列表和请求统计
ipRequests = {}  # {ip: count}
bannedIPs = set()

# 速率限制器
rateLimitStore = {}  # {ip: deque(timestamps)}

# 统计数据
stats = {
    'total_requests': 0,
    'total_uploads': 0,
    'total_tasks_processed': 0,
    'total_audio_generated': 0,
    'start_time': datetime.now().isoformat(),
    'failed_requests': 0,
    'processing_times': []
}

# 任务模式存储：{query_code: mode}
task_modes = {}

# 初始化全局模型字典
models_dict = get_models_dict()

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'changeme')
SECRET_KEY = os.environ.get('SECRET_KEY', None)

# 配置
CORS_ENABLED = os.environ.get('CORS_ENABLED', 'false').lower() == 'true'
RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))  # 秒
RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '30'))  # 每个窗口最大请求数
TASK_RETENTION_DAYS = int(os.environ.get('TASK_RETENTION_DAYS', '7'))  # 任务保留天数

# 警告用户修改默认密码
if ADMIN_USER == 'admin' or ADMIN_PASS == 'changeme':
    print('WARNING: Using default admin credentials! Please set ADMIN_USER and ADMIN_PASS environment variables!')
if SECRET_KEY is None:
    print('WARNING: Using default secret key! Please set SECRET_KEY environment variable!')
    SECRET_KEY = 'dev-secret-key-change-in-production'

# 装饰器：统计请求
def track_request_stats(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        global stats
        stats['total_requests'] += 1
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            return result
        except Exception as e:
            stats['failed_requests'] += 1
            raise e
        finally:
            processing_time = time.time() - start_time
            stats['processing_times'].append(processing_time)
            if len(stats['processing_times']) > 1000:
                stats['processing_times'] = stats['processing_times'][-1000:]
    return wrapper

# 装饰器：速率限制
def rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not RATE_LIMIT_ENABLED:
            return f(*args, **kwargs)
            
        client_ip = request.remote_addr
        now = time.time()
        
        if client_ip not in rateLimitStore:
            rateLimitStore[client_ip] = deque()
        
        # 清理过期的请求记录
        while rateLimitStore[client_ip] and now - rateLimitStore[client_ip][0] > RATE_LIMIT_WINDOW:
            rateLimitStore[client_ip].popleft()
        
        # 检查是否超过限制
        if len(rateLimitStore[client_ip]) >= RATE_LIMIT_MAX:
            return jsonify({
                'error': 'Too many requests',
                'retry_after': RATE_LIMIT_WINDOW - (now - rateLimitStore[client_ip][0])
            }), 429
        
        # 记录当前请求
        rateLimitStore[client_ip].append(now)
        return f(*args, **kwargs)
    return wrapper

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

def is_safe_filename(filename):
    """简单的文件名安全检查"""
    if not filename:
        return False
    # 防止路径遍历攻击
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    return True

def is_valid_base64_image(data):
    """验证 base64 图片数据"""
    if not data or not isinstance(data, str):
        return False
    # 简单检查格式
    if not data.startswith('data:image/'):
        return False
    return True



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 确保所有必要的目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = SECRET_KEY

# 启用CORS
if CORS_ENABLED:
    CORS(app)
    logger.info('CORS enabled')

# 添加安全头
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

SERVER_START_TIME = time.time()

# 健康检查端点
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
@track_request_stats
def health_check():
    """健康检查端点，用于监控服务状态"""
    try:
        # 检查目录是否可写
        dir_check = os.access(UPLOAD_FOLDER, os.W_OK) and \
                   os.access(PENDING_DIR, os.W_OK) and \
                   os.access(PROCESSING_DIR, os.W_OK) and \
                   os.access(RESULTS_DIR, os.W_OK)
        
        # 检查配置
        config = get_config()
        config_check = config is not None
        
        uptime_seconds = time.time() - SERVER_START_TIME
        
        # 统计当前状态
        pending_count = len([f for f in os.listdir(PENDING_DIR) if not f.endswith('_mode.txt') and not f.endswith('_grade.txt') and not f.startswith('.')])
        processing_count = len([f for f in os.listdir(PROCESSING_DIR) if not f.endswith('_mode.txt') and not f.endswith('_grade.txt') and not f.startswith('.')])
        
        return jsonify({
            'status': 'healthy' if dir_check and config_check else 'degraded',
            'uptime_seconds': uptime_seconds,
            'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
            'directories': {
                'upload': {'path': UPLOAD_FOLDER, 'writable': os.access(UPLOAD_FOLDER, os.W_OK)},
                'pending': {'path': PENDING_DIR, 'writable': os.access(PENDING_DIR, os.W_OK)},
                'processing': {'path': PROCESSING_DIR, 'writable': os.access(PROCESSING_DIR, os.W_OK)},
                'results': {'path': RESULTS_DIR, 'writable': os.access(RESULTS_DIR, os.W_OK)}
            },
            'queue': {
                'pending': pending_count,
                'processing': processing_count
            },
            'config': config_check,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f'Health check failed: {e}')
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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


@app.route('/teacher')
@admin_required
def teacher_page():
    """教师阅卷系统"""
    return render_template('teacher.html')

@app.route('/library')
@admin_required
def library_page():
    """试卷库管理页面"""
    return render_template('library.html')

@app.route('/upload_image', methods=['POST'])
@rate_limit
@track_request_stats
def upload_image():
    """接收客户端上传的图片"""
    try:
        data = request.get_json()
        if not data or 'image_data' not in data:
            return jsonify({'error': 'No image data provided'}), 400
        
        image_data = data['image_data']
        if not is_valid_base64_image(image_data):
            return jsonify({'error': 'Invalid image data format'}), 400

        query_code = str(uuid.uuid4())
        extension = image_data.split(';')[0].split('/')[-1]
        # 验证扩展名
        if extension not in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
            return jsonify({'error': 'Unsupported image format'}), 400
        # 支持可选的优先级，默认 0，越小优先级越高
        priority = int(data.get('priority', 0))
        # 获取模式，默认 quick
        mode = data.get('mode', 'quick')
        if mode not in ['quick', 'guided']:
            mode = 'quick'
        
        # 获取年级，默认高中
        grade = data.get('grade', '10-12')
        valid_grades = ['1-2', '3-4', '5-6', '7-9', '10-12']
        if grade not in valid_grades:
            grade = '10-12'
        
        # 保存任务模式和年级信息到文件
        mode_filepath = os.path.join(PENDING_DIR, f"{query_code}_mode.txt")
        grade_filepath = os.path.join(PENDING_DIR, f"{query_code}_grade.txt")
        try:
            with open(mode_filepath, 'w', encoding='utf-8') as f:
                f.write(mode)
            with open(grade_filepath, 'w', encoding='utf-8') as f:
                f.write(grade)
        except Exception:
            pass
        
        # 文件名形如: 00000001_<query_code>.<ext>
        filename = f"{priority:08d}_{query_code}.{extension}"
        filepath = os.path.join(PENDING_DIR, filename)

        image_data = image_data.split(',')[1]
        # 验证base64数据
        try:
            decoded = base64.b64decode(image_data, validate=True)
            # 限制文件大小，比如 10MB
            if len(decoded) > 10 * 1024 * 1024:
                return jsonify({'error': 'Image too large (max 10MB)'}), 413
        except Exception:
            return jsonify({'error': 'Invalid base64 data'}), 400
        
        with open(filepath, 'wb') as f:
            f.write(decoded)
        
        # 更新统计
        global stats
        stats['total_uploads'] += 1

        logger.info(f"图片已上传，生成查询码: {query_code}，模式: {mode}，年级: {grade}")
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
        # 验证查询码格式，防止路径遍历
        if not isinstance(query_code, str) or not query_code or '..' in query_code:
            return jsonify({'error': 'Invalid query code'}), 400
        # 限制查询码长度
        if len(query_code) > 64:
            return jsonify({'error': 'Query code too long'}), 400

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
        # 验证查询码
        if not isinstance(query_code, str) or not query_code or '..' in query_code:
            return jsonify({'error': 'Invalid query code'}), 400
        if len(query_code) > 64:
            return jsonify({'error': 'Query code too long'}), 400
        
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
    # 防止路径遍历攻击
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    # 只允许访问wav文件和txt文件
    if not filename.endswith('.wav') and not filename.endswith('.txt'):
        return jsonify({'error': 'Invalid file type'}), 400
    return send_from_directory(RESULTS_DIR, filename)

@app.route('/get_hints', methods=['POST'])
def get_hints():
    """获取逐步指导的提示"""
    try:
        data = request.get_json()
        if not data or 'query_code' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        query_code = data['query_code']
        
        # 验证查询码
        if not isinstance(query_code, str) or not query_code or '..' in query_code:
            return jsonify({'error': 'Invalid query code'}), 400
        if len(query_code) > 64:
            return jsonify({'error': 'Query code too long'}), 400
        
        # 检查是否有提示
        from processor import get_hints as get_hints_from_processor
        hints = get_hints_from_processor(query_code)
        
        if hints is not None:
            return jsonify({
                'status': 'ready',
                'hints': hints
            })
        
        # 检查任务状态
        # 先看是否在处理中
        processing_file = None
        for f in os.listdir(PROCESSING_DIR):
            if f.startswith(query_code):
                processing_file = f
                break
        
        if processing_file:
            return jsonify({'status': 'processing'})
        
        # 再看是否在等待中
        pending_file = None
        for f in os.listdir(PENDING_DIR):
            if f.startswith(query_code):
                pending_file = f
                break
        
        if pending_file:
            return jsonify({'status': 'pending'})
        
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"获取提示错误: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/get_knowledge', methods=['POST'])
def get_knowledge():
    """获取知识点图谱"""
    try:
        data = request.get_json()
        if not data or 'query_code' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        query_code = data['query_code']
        
        # 验证查询码
        if not isinstance(query_code, str) or not query_code or '..' in query_code:
            return jsonify({'error': 'Invalid query code'}), 400
        if len(query_code) > 64:
            return jsonify({'error': 'Query code too long'}), 400
        
        # 获取知识点
        from processor import get_knowledge_points
        knowledge = get_knowledge_points(query_code)
        
        if knowledge is not None:
            return jsonify({
                'status': 'ready',
                'knowledge': knowledge
            })
        
        # 检查任务状态
        processing_file = None
        for f in os.listdir(PROCESSING_DIR):
            if f.startswith(query_code):
                processing_file = f
                break
        
        if processing_file:
            return jsonify({'status': 'processing'})
        
        pending_file = None
        for f in os.listdir(PENDING_DIR):
            if f.startswith(query_code):
                pending_file = f
                break
        
        if pending_file:
            return jsonify({'status': 'pending'})
        
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"获取知识点错误: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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
@app.route('/admin/api/summary', methods=['GET'])
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

# --- 公共统计API ---
@app.route('/api/stats', methods=['GET'])
@rate_limit
@track_request_stats
def get_public_stats():
    """获取公共统计信息（无需登录）"""
    uptime_seconds = time.time() - SERVER_START_TIME
    
    # 计算平均处理时间
    avg_processing_time = 0
    if stats['processing_times']:
        avg_processing_time = sum(stats['processing_times']) / len(stats['processing_times'])
    
    return jsonify({
        'uptime_seconds': uptime_seconds,
        'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
        'total_requests': stats['total_requests'],
        'success_rate': max(0, 100 - (stats['failed_requests'] / max(1, stats['total_requests']) * 100)) if stats['total_requests'] > 0 else 100,
        'avg_processing_time_ms': avg_processing_time * 1000,
        'timestamp': datetime.now().isoformat()
    })

# --- 任务取消API ---
@app.route('/api/task/cancel', methods=['POST'])
@rate_limit
@track_request_stats
def cancel_task():
    """取消待处理的任务"""
    try:
        data = request.get_json()
        if not data or 'query_code' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        query_code = data['query_code']
        
        # 验证查询码
        if not isinstance(query_code, str) or not query_code or '..' in query_code:
            return jsonify({'error': 'Invalid query code'}), 400
        if len(query_code) > 64:
            return jsonify({'error': 'Query code too long'}), 400
        
        # 查找任务文件
        cancelled = False
        
        # 在待处理队列中查找
        for fname in os.listdir(PENDING_DIR):
            if query_code in fname and not fname.endswith('_mode.txt') and not fname.endswith('_grade.txt'):
                filepath = os.path.join(PENDING_DIR, fname)
                if os.path.isfile(filepath):
                    # 同时删除模式和年级文件
                    for suffix in ['_mode.txt', '_grade.txt']:
                        sf = os.path.join(PENDING_DIR, f'{query_code}{suffix}')
                        if os.path.exists(sf):
                            os.remove(sf)
                    os.remove(filepath)
                    cancelled = True
                    logger.info(f"任务 {query_code} 已从待处理队列中取消")
        
        if cancelled:
            return jsonify({'status': 'cancelled', 'query_code': query_code})
        
        # 检查是否已经在处理中
        for fname in os.listdir(PROCESSING_DIR):
            if query_code in fname:
                return jsonify({
                    'error': 'Task is already processing and cannot be cancelled',
                    'status': 'processing'
                }), 400
        
        # 检查是否已经完成
        for fname in os.listdir(RESULTS_DIR):
            if query_code in fname and fname.endswith('.txt'):
                return jsonify({
                    'error': 'Task is already completed',
                    'status': 'completed'
                }), 400
        
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"取消任务错误: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# --- 任务清理函数 ---
def cleanup_old_tasks():
    """清理过期的任务文件"""
    try:
        cutoff_date = datetime.now() - timedelta(days=TASK_RETENTION_DAYS)
        deleted_count = 0
        
        # 清理结果目录中的旧文件
        for fname in os.listdir(RESULTS_DIR):
            fpath = os.path.join(RESULTS_DIR, fname)
            if os.path.isfile(fpath):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if file_mtime < cutoff_date:
                    try:
                        os.remove(fpath)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除文件 {fpath} 失败: {e}")
        
        if deleted_count > 0:
            logger.info(f"清理了 {deleted_count} 个过期任务文件")
        
        return deleted_count
    except Exception as e:
        logger.error(f"任务清理失败: {e}")
        return 0

# --- 管理员API：统计和清理 ---
@app.route('/admin/api/stats', methods=['GET'])
@admin_required
def admin_stats():
    """获取详细的统计信息（管理员）"""
    global stats
    
    # 更新任务处理计数
    result_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')]
    audio_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.wav')]
    stats['total_tasks_processed'] = len(result_files)
    stats['total_audio_generated'] = len(audio_files)
    
    # 计算平均处理时间
    avg_processing_time = 0
    if stats['processing_times']:
        avg_processing_time = sum(stats['processing_times']) / len(stats['processing_times'])
    
    # 计算成功响应率
    success_rate = 100
    if stats['total_requests'] > 0:
        success_rate = max(0, 100 - (stats['failed_requests'] / stats['total_requests'] * 100))
    
    # 统计各个队列的数量
    pending_count = len([f for f in os.listdir(PENDING_DIR) if not f.endswith('_mode.txt') and not f.endswith('_grade.txt') and not f.startswith('.')])
    processing_count = len([f for f in os.listdir(PROCESSING_DIR) if not f.endswith('_mode.txt') and not f.endswith('_grade.txt') and not f.startswith('.')])
    
    return jsonify({
        'system': {
            'start_time': stats['start_time'],
            'uptime_seconds': time.time() - SERVER_START_TIME,
            'uptime_formatted': str(timedelta(seconds=int(time.time() - SERVER_START_TIME)))
        },
        'requests': {
            'total': stats['total_requests'],
            'failed': stats['failed_requests'],
            'success_rate': success_rate,
            'avg_processing_time_ms': avg_processing_time * 1000
        },
        'tasks': {
            'pending': pending_count,
            'processing': processing_count,
            'completed': len(result_files),
            'audio_generated': len(audio_files)
        },
        'features': {
            'cors_enabled': CORS_ENABLED,
            'rate_limit_enabled': RATE_LIMIT_ENABLED,
            'task_retention_days': TASK_RETENTION_DAYS
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/admin/api/cleanup', methods=['POST'])
@admin_required
def admin_cleanup():
    """手动触发任务清理"""
    try:
        data = request.get_json() or {}
        days = data.get('days', TASK_RETENTION_DAYS)
        
        if not isinstance(days, int) or days <= 0:
            return jsonify({'error': 'Invalid days value'}), 400
        
        # 修改清理函数接受天数参数
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        # 清理结果目录中的旧文件
        for fname in os.listdir(RESULTS_DIR):
            fpath = os.path.join(RESULTS_DIR, fname)
            if os.path.isfile(fpath):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if file_mtime < cutoff_date:
                    try:
                        os.remove(fpath)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除文件 {fpath} 失败: {e}")
        
        if deleted_count > 0:
            logger.info(f"清理了 {deleted_count} 个过期任务文件")
        
        return jsonify({
            'status': 'success',
            'deleted_count': deleted_count,
            'cleanup_days': days
        })
    except Exception as e:
        logger.error(f"管理员清理失败: {e}")
        return jsonify({'error': 'Cleanup failed'}), 500

# --- 配置管理API ---
@app.route('/admin/api/config/reload', methods=['POST'])
@admin_required
def reload_config():
    """重新加载配置文件"""
    try:
        global models_dict
        models_dict = get_models_dict()  # 重新加载模型字典
        logger.info("配置已重新加载")
        return jsonify({
            'status': 'success',
            'models_count': len(models_dict),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        return jsonify({'error': str(e)}), 500

# --- 试卷库管理 API ---
@app.route('/api/library/status', methods=['GET'])
@track_request_stats
def get_library_status():
    """获取试卷库状态"""
    try:
        metadata = test_library.load_library_metadata()
        return jsonify({
            'success': True,
            'total_papers': len(metadata['papers']),
            'total_questions': metadata['total_questions'],
            'last_updated': metadata.get('last_updated'),
            'papers': metadata['papers']
        })
    except Exception as e:
        logger.error(f'获取试卷库状态失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/upload', methods=['POST'])
@rate_limit
@track_request_stats
def batch_upload_papers():
    """批量上传试卷"""
    try:
        # 检查是否有文件上传
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        files = request.files.getlist('files')
        paper_name = request.form.get('name', '未命名试卷')
        grade = request.form.get('grade', '10-12')
        class_id = request.form.get('class_id', '')  # 可选：关联班级
        auto_detect = request.form.get('auto_detect', 'true').lower() == 'true'
        work_mode = request.form.get('work_mode', 'auto')  # auto/manual_score/hybrid
        
        if not files:
            return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400
        
        if work_mode not in ['auto', 'manual_score', 'hybrid']:
            return jsonify({'success': False, 'error': '无效的工作模式'}), 400
        
        # 读取文件内容
        image_files = []
        for file in files:
            if file.filename == '':
                continue
            image_files.append((file.filename, file.read()))
        
        if not image_files:
            return jsonify({'success': False, 'error': '没有有效的图片文件'}), 400
        
        # 调用增强版的批量分析
        result = test_library.batch_analyze_papers(
            image_files=image_files,
            grade=grade,
            paper_name=paper_name,
            concurrency=int(request.form.get('concurrency', 4)),
            class_id=class_id if class_id else None,
            auto_detect_names=auto_detect,
            work_mode=work_mode
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f'批量上传试卷失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/paper/<paper_id>', methods=['GET'])
@track_request_stats
def get_paper_detail(paper_id):
    """获取单张试卷的详细分析"""
    try:
        analysis = test_library.load_paper_analysis(paper_id)
        if not analysis:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404
        
        return jsonify({'success': True, 'analysis': analysis})
    except Exception as e:
        logger.error(f'获取试卷详情失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/paper/<paper_id>', methods=['DELETE'])
@admin_required
def delete_paper(paper_id):
    """删除试卷"""
    try:
        success = test_library.delete_paper(paper_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        logger.error(f'删除试卷失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/optimize', methods=['POST'])
@admin_required
def generate_optimization_suggestions():
    """生成提示词优化建议"""
    try:
        data = request.get_json() or {}
        paper_ids = data.get('paper_ids')
        grade = data.get('grade')
        
        result = test_library.generate_prompt_optimization_suggestions(
            paper_ids=paper_ids,
            grade=grade
        )
        
        return jsonify(result)
    except Exception as e:
        logger.error(f'生成优化建议失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/statistics', methods=['GET'])
@admin_required
def get_library_statistics():
    """获取完整的试卷库统计"""
    try:
        stats = test_library.export_library_statistics()
        return jsonify({'success': True, 'statistics': stats})
    except Exception as e:
        logger.error(f'获取统计信息失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 新增试卷库功能 API ---

@app.route('/api/library/wrong_questions', methods=['POST'])
@rate_limit
@track_request_stats
def get_wrong_questions():
    """获取错题"""
    try:
        data = request.get_json() or {}
        paper_ids = data.get('paper_ids')
        grade = data.get('grade')
        
        wrong_questions = test_library.get_all_wrong_questions(paper_ids, grade)
        return jsonify({
            'success': True,
            'wrong_questions': wrong_questions,
            'total_count': len(wrong_questions)
        })
    except Exception as e:
        logger.error(f'获取错题失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/search', methods=['POST'])
@rate_limit
@track_request_stats
def search_questions_api():
    """搜索题目"""
    try:
        data = request.get_json() or {}
        keyword = data.get('keyword', '')
        paper_ids = data.get('paper_ids')
        knowledge_point = data.get('knowledge_point')
        question_type = data.get('question_type')
        is_correct = data.get('is_correct')
        
        questions = test_library.search_questions(
            keyword, paper_ids, knowledge_point, question_type, is_correct
        )
        return jsonify({
            'success': True,
            'questions': questions,
            'total_count': len(questions)
        })
    except Exception as e:
        logger.error(f'搜索题目失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/knowledge_points', methods=['GET'])
@track_request_stats
def get_knowledge_points_list():
    """获取所有知识点列表"""
    try:
        knowledge_points = test_library.get_all_knowledge_points()
        return jsonify({
            'success': True,
            'knowledge_points': knowledge_points
        })
    except Exception as e:
        logger.error(f'获取知识点列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/knowledge_graph', methods=['GET'])
@track_request_stats
def get_knowledge_graph():
    """获取知识点关联图谱"""
    try:
        graph_data = test_library.build_knowledge_point_graph()
        return jsonify({
            'success': True,
            'graph': graph_data
        })
    except Exception as e:
        logger.error(f'获取知识点图谱失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/tags', methods=['GET'])
@track_request_stats
def get_all_tags():
    """获取所有标签"""
    try:
        tags = test_library.get_all_tags()
        return jsonify({'success': True, 'tags': tags})
    except Exception as e:
        logger.error(f'获取标签失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/paper/<paper_id>/tags', methods=['POST'])
@admin_required
def update_paper_tags_api(paper_id):
    """更新试卷标签"""
    try:
        data = request.get_json() or {}
        tags = data.get('tags', [])
        
        success = test_library.update_paper_tags(paper_id, tags)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '试卷未找到'}), 404
    except Exception as e:
        logger.error(f'更新标签失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/paper/tags/<tag>', methods=['GET'])
@track_request_stats
def get_papers_by_tag(tag):
    """按标签获取试卷"""
    try:
        papers = test_library.get_papers_by_tag(tag)
        return jsonify({'success': True, 'papers': papers})
    except Exception as e:
        logger.error(f'按标签获取试卷失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/generate_practice', methods=['POST'])
@rate_limit
@track_request_stats
def generate_practice():
    """生成错题练习"""
    try:
        data = request.get_json() or {}
        paper_ids = data.get('paper_ids')
        max_questions = data.get('max_questions', 50)
        
        practice_data = test_library.generate_wrong_questions_practice(paper_ids, max_questions)
        return jsonify({'success': True, 'practice': practice_data})
    except Exception as e:
        logger.error(f'生成练习失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/export', methods=['POST'])
@admin_required
def export_questions():
    """导出题目"""
    try:
        data = request.get_json() or {}
        questions = data.get('questions', [])
        paper_name = data.get('paper_name', '导出题目')
        
        filename = test_library.export_questions_to_json(questions, paper_name)
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        logger.error(f'导出题目失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 班级管理API ---

@app.route('/api/classes', methods=['GET'])
@track_request_stats
def get_classes():
    """获取所有班级"""
    try:
        classes = test_library.get_all_classes()
        return jsonify({'success': True, 'classes': classes})
    except Exception as e:
        logger.error(f'获取班级列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes', methods=['POST'])
@admin_required
def create_class():
    """创建新班级"""
    try:
        data = request.get_json() or {}
        class_name = data.get('name', '')
        grade = data.get('grade', '10-12')
        teacher_name = data.get('teacher_name', '')
        
        if not class_name:
            return jsonify({'success': False, 'error': '班级名称不能为空'}), 400
        
        class_id = test_library.add_class(class_name, grade, teacher_name)
        return jsonify({'success': True, 'class_id': class_id})
    except Exception as e:
        logger.error(f'创建班级失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/students', methods=['POST'])
@admin_required
def add_student(class_id):
    """添加学生到班级"""
    try:
        data = request.get_json() or {}
        student_info = data.get('student', {})
        
        success = test_library.add_student_to_class(class_id, student_info)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '班级未找到'}), 404
    except Exception as e:
        logger.error(f'添加学生失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/papers', methods=['POST'])
@admin_required
def assign_paper_to_class(class_id):
    """将试卷分配给班级"""
    try:
        data = request.get_json() or {}
        paper_id = data.get('paper_id', '')
        
        success = test_library.assign_paper_to_class(class_id, paper_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '班级未找到'}), 404
    except Exception as e:
        logger.error(f'分配试卷失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/performance', methods=['GET'])
@track_request_stats
def get_class_performance(class_id):
    """获取班级成绩分析"""
    try:
        performance = test_library.analyze_class_performance(class_id)
        return jsonify(performance)
    except Exception as e:
        logger.error(f'获取班级成绩分析失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/report', methods=['POST'])
@admin_required
def generate_class_report(class_id):
    """生成班级成绩报告"""
    try:
        report = test_library.export_class_report(class_id)
        return jsonify(report)
    except Exception as e:
        logger.error(f'生成班级报告失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>', methods=['DELETE'])
@admin_required
def delete_class(class_id):
    """删除班级"""
    try:
        success = test_library.delete_class(class_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '班级未找到'}), 404
    except Exception as e:
        logger.error(f'删除班级失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 学生成绩管理 API ---

@app.route('/api/classes/<class_id>/scores', methods=['POST'])
@admin_required
def add_student_score(class_id):
    """添加学生成绩"""
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        score_data = data.get('score', {})
        
        if not student_id:
            return jsonify({'success': False, 'error': '学生ID不能为空'}), 400
        
        success = test_library.add_student_score(class_id, student_id, score_data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '添加失败'}), 500
    except Exception as e:
        logger.error(f'添加学生成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/scores', methods=['GET'])
@track_request_stats
def get_class_scores(class_id):
    """获取班级成绩"""
    try:
        paper_id = request.args.get('paper_id')
        scores = test_library.get_class_scores(class_id, paper_id)
        return jsonify({'success': True, 'scores': scores})
    except Exception as e:
        logger.error(f'获取班级成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/scores/statistics', methods=['GET'])
@track_request_stats
def get_class_score_statistics(class_id):
    """获取班级成绩统计"""
    try:
        paper_id = request.args.get('paper_id')
        statistics = test_library.calculate_class_statistics(class_id, paper_id)
        return jsonify({'success': True, 'statistics': statistics})
    except Exception as e:
        logger.error(f'获取成绩统计失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/scores/ranking', methods=['GET'])
@track_request_stats
def get_class_score_ranking(class_id):
    """获取班级成绩排名"""
    try:
        paper_id = request.args.get('paper_id')
        ranking = test_library.get_student_ranking(class_id, paper_id)
        return jsonify({'success': True, 'ranking': ranking})
    except Exception as e:
        logger.error(f'获取成绩排名失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/classes/<class_id>/students/<student_id>/progress', methods=['GET'])
@track_request_stats
def get_student_progress(class_id, student_id):
    """获取学生进步情况"""
    try:
        progress = test_library.get_student_progress(class_id, student_id)
        return jsonify({'success': True, 'progress': progress})
    except Exception as e:
        logger.error(f'获取学生进步情况失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500



# ========== 考试管理 API ==========

@app.route('/api/exams', methods=['GET'])
@track_request_stats
def get_exams():
    """获取所有考试"""
    try:
        # 初始化元数据以确保目录存在
        test_library.init_exams_metadata()
        from test_library import load_exams_metadata
        all_exams = load_exams_metadata().get('exams', [])
        
        return jsonify({'success': True, 'exams': all_exams})
    except Exception as e:
        logger.error(f'获取考试列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams', methods=['POST'])
@admin_required
def create_exam():
    """创建考试"""
    try:
        data = request.get_json() or {}
        
        result = test_library.create_exam(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f'创建考试失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>', methods=['GET'])
@track_request_stats
def get_exam(exam_id):
    """获取考试详情"""
    try:
        exam = test_library.get_exam_by_id(exam_id)
        if exam:
            return jsonify({'success': True, 'exam': exam})
        else:
            return jsonify({'success': False, 'error': '考试不存在'}), 404
    except Exception as e:
        logger.error(f'获取考试详情失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>', methods=['DELETE'])
@admin_required
def delete_exam(exam_id):
    """删除考试"""
    try:
        success = test_library.delete_exam(exam_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        logger.error(f'删除考试失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/questions', methods=['POST'])
@admin_required
def add_exam_question(exam_id):
    """添加题目到考试"""
    try:
        data = request.get_json() or {}
        
        success = test_library.add_question_to_exam(exam_id, data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '添加失败'}), 500
    except Exception as e:
        logger.error(f'添加题目失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/ready', methods=['POST'])
@admin_required
def set_exam_ready(exam_id):
    """设置考试就绪"""
    try:
        success = test_library.set_exam_ready(exam_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '设置失败'}), 500
    except Exception as e:
        logger.error(f'设置考试就绪失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/scan', methods=['POST'])
@admin_required
def scan_exam_answer_sheets(exam_id):
    """批量扫描答题卡"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400
        
        image_files = []
        for file in files:
            if file.filename == '':
                continue
            image_files.append((file.filename, file.read()))
        
        if not image_files:
            return jsonify({'success': False, 'error': '没有有效的图片文件'}), 400
        
        result = test_library.batch_scan_answer_sheets(exam_id, image_files)
        return jsonify(result)
    except Exception as e:
        logger.error(f'扫描答题卡失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/confirm', methods=['POST'])
@admin_required
def confirm_exam(exam_id):
    """确认考试成绩"""
    try:
        result = test_library.confirm_exam_scores(exam_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f'确认成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/adjust', methods=['POST'])
@admin_required
def adjust_exam_score(exam_id):
    """调整单条成绩"""
    try:
        data = request.get_json() or {}
        student_number = data.get('student_number')
        score = data.get('score')
        
        if not student_number or score is None:
            return jsonify({'success': False, 'error': '参数不完整'}), 400
        
        result = test_library.adjust_score(exam_id, student_number, float(score))
        return jsonify(result)
    except Exception as e:
        logger.error(f'调整成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/analysis', methods=['GET'])
@track_request_stats
def get_exam_analysis(exam_id):
    """获取考试详细分析"""
    try:
        result = test_library.get_exam_analysis(exam_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f'获取考试分析失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
# --- 初始化 ---
_SCANNER_INITIALIZED = False
_EXECUTOR = None
_CLEANUP_RUNNING = False

def _init_scanner_once():
    global _SCANNER_INITIALIZED, _EXECUTOR
    if _SCANNER_INITIALIZED:
        return
    _EXECUTOR = ThreadPoolExecutor(max_workers=4)
    # 将后台任务扫描交给 processor 模块管理
    processor.start_scanner(_EXECUTOR)
    logger.info("后台任务扫描已启动")
    _SCANNER_INITIALIZED = True

# 启动后台任务清理（每天一次）
def _start_cleanup_task():
    """启动后台清理任务"""
    def cleanup_loop():
        global _CLEANUP_RUNNING
        _CLEANUP_RUNNING = True
        logger.info(f"任务清理任务已启动，保留天数: {TASK_RETENTION_DAYS}")
        
        while True:
            try:
                # 每天在固定时间清理（例如凌晨3点）
                now = datetime.now()
                # 简单的实现：每24小时清理一次
                time.sleep(24 * 60 * 60)
                cleanup_old_tasks()
            except Exception as e:
                logger.error(f"清理循环错误: {e}")
                time.sleep(60)  # 出错后等待一分钟重试
    
    import threading
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()

if __name__ == '__main__':
    _init_scanner_once()
    _start_cleanup_task()  # 启动清理任务
    logger.info("服务器启动，开始监听...")

    # 从环境变量获取端口，默认 8000
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # 在非主模块运行时（如某些 WSGI 服务器），也尝试启动后台扫描以处理任务
    _init_scanner_once()
    # _start_cleanup_task()  # 可选：在非主模块也启动清理任务
