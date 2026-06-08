"""
后台管理路由模块
"""
import os
import uuid
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, render_template, flash, redirect, url_for, session, g, jsonify

from config import get_config, save_config, get_models_dict, ensure_ascii

# 全局变量
models_dict = get_models_dict()
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'changeme')

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """管理员认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.admin_login'))
        # 加载个性化设置
        cfg = get_config()
        g.customization = cfg.get('customization', {
            'bg_type': 'gradient',
            'bg_color1': '#667eea',
            'bg_color2': '#764ba2',
            'bg_image': ''
        })
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    return render_template('admin_login.html')


@admin_bp.route('/logout')
def admin_logout():
    """管理员登出"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """管理仪表盘"""
    cfg = get_config()
    models_list = cfg.get('models', [])
    default_model = cfg.get('default_model', '')
    vision_model = cfg.get('vision_model', '')
    text_model = cfg.get('text_model', '')
    return render_template(
        'admin_dashboard.html',
        models=models_list,
        default_model=default_model,
        vision_model=vision_model,
        text_model=text_model,
        summary={'pending': 0, 'processing': 0, 'completed': 0},
        recent_results=[],
        tasks=[]
    )


@admin_bp.route('/models')
@admin_required
def models_page():
    """模型管理页面"""
    cfg = get_config()
    models_list = cfg.get('models', [])
    vision_model = cfg.get('vision_model', '')
    text_model = cfg.get('text_model', '')
    return render_template(
        'models.html',
        models=models_list,
        vision_model=vision_model,
        text_model=text_model
    )


@admin_bp.route('/models/add', methods=['GET', 'POST'])
@admin_required
def add_model():
    """添加模型"""
    global models_dict
    if request.method == 'POST':
        cfg = get_config()
        name = request.form['name'].strip()
        if not name:
            flash('模型名称不能为空', 'error')
            return redirect(url_for('admin.add_model'))
        if name in models_dict:
            flash(f'模型 "{name}" 已存在', 'error')
            return redirect(url_for('admin.add_model'))
        try:
            ensure_ascii(request.form['api_key'].strip(), 'API key')
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('admin.add_model'))

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
        # 更新全局模型字典
        models_dict = get_models_dict()
        flash(f'模型 "{name}" 添加成功', 'success')
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('model_form.html', action='add', model=None)


@admin_bp.route('/models/edit/<path:name>', methods=['GET', 'POST'])
@admin_required
def edit_model(name):
    """编辑模型"""
    global models_dict
    cfg = get_config()
    model = next((m for m in cfg['models'] if m['name'] == name), None)
    if not model:
        flash('模型不存在', 'error')
        return redirect(url_for('admin.models_page'))

    if request.method == 'POST':
        try:
            ensure_ascii(request.form['api_key'].strip(), 'API key')
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('admin.edit_model', name=name))

        model['api_base'] = request.form['api_base'].strip()
        model['api_key'] = request.form['api_key'].strip()
        model['default_temperature'] = float(request.form['default_temperature'])
        model['timeout'] = int(request.form['timeout'])
        save_config(cfg)
        # 更新全局模型字典
        models_dict = get_models_dict()
        flash(f'模型 "{name}" 已更新', 'success')
        return redirect(url_for('admin.models_page'))

    return render_template('model_form.html', action='edit', model=model)


@admin_bp.route('/models/delete/<path:name>', methods=['POST'])
@admin_required
def delete_model(name):
    """删除模型"""
    global models_dict
    cfg = get_config()
    cfg['models'] = [m for m in cfg['models'] if m['name'] != name]
    if cfg.get('default_model') == name:
        cfg['default_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    if cfg.get('vision_model') == name:
        cfg['vision_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    if cfg.get('text_model') == name:
        cfg['text_model'] = cfg['models'][0]['name'] if cfg['models'] else ''
    save_config(cfg)
    # 更新全局模型字典
    models_dict = get_models_dict()
    flash(f'模型 "{name}" 已删除', 'success')
    return redirect(url_for('admin.models_page'))


@admin_bp.route('/models/set_default/<path:name>', methods=['POST'])
@admin_required
def set_default_model(name):
    """设置默认模型"""
    cfg = get_config()
    cfg['default_model'] = name
    save_config(cfg)
    flash(f'默认模型已设为 {name}', 'success')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/models/test/<path:name>', methods=['POST'])
@admin_required
def test_model(name):
    """测试模型连接"""
    try:
        from processor import call_llm_api
        test_messages = [{"role": "user", "content": "Hi"}]
        result = call_llm_api(name, test_messages)
        if result:
            flash(f'模型 "{name}" 测试成功！', 'success')
        else:
            flash(f'模型 "{name}" 测试失败', 'error')
    except Exception as e:
        flash(f'模型测试失败: {str(e)}', 'error')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/set_default_models', methods=['POST'])
@admin_required
def set_default_models():
    """设置默认视觉和文本模型"""
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
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/set_models', methods=['POST'])
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
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/chat_test')
@admin_required
def chat_test():
    """对话测试页面"""
    cfg = get_config()
    models_list = cfg.get('models', [])
    return render_template('admin.html', models=models_list, default_model=cfg.get('default_model', ''))


@admin_bp.route('/customization', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.customization_page'))
    customization = cfg.get('customization', {'bg_type': 'gradient', 'bg_color1': '#667eea', 'bg_color2': '#764ba2', 'bg_image': ''})
    return render_template('customization.html', customization=customization)


@admin_bp.route('/api/models', methods=['GET'])
@admin_required
def admin_api_models():
    """获取模型列表 API"""
    cfg = get_config()
    models_list = cfg.get('models', [])
    return jsonify({'models': models_list})
