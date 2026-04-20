# -*- coding: utf-8 -*-

import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime
from processor import _parse_pending_filename
from concurrent.futures import ThreadPoolExecutor

import requests
import yaml
from flask import Flask, jsonify, request, render_template_string, flash, redirect, url_for, Response, session
from functools import wraps
from werkzeug.utils import secure_filename
from flask import send_from_directory


import processor
from config import get_config, ensure_defaults, save_config
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'changeme')

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return wrapper
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


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# --- 简易管理登录界面 ---
ADMIN_LOGIN_HTML = """
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\">
  <title>管理登录</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <style>body{font-family:Arial, sans-serif; padding:2rem;} .login{max-width:400px;margin:0 auto;border:1px solid #ddd;border-radius:6px;padding:1.5rem;}</style>
  </head>
  <body>
  <div class=\"login\">
    <h2>服务端管理登录</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div style=\"color: red; margin: 6px 0;\">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method=\"post\" action=\"/admin/login\">
      <div style=\"margin-bottom:8px\">
        <label>用户名</label><br>
        <input type=\"text\" name=\"username\" required style=\"width:100%\">
      </div>
      <div style=\"margin-bottom:8px\">
        <label>密码</label><br>
        <input type=\"password\" name=\"password\" required style=\"width:100%\">
      </div>
      <button type=\"submit\" style=\"padding:6px 12px\">登录</button>
    </form>
  </div>
  </body>
</html>
"""

# 记录跳转目标页面
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session['admin_logged_in'] = True
            next_url = request.args.get('next') or url_for('admin')
            return redirect(next_url)
        flash('无效的用户名或密码')
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# 任务控制：暂停、继续/恢复、取消任务
@app.route('/admin/pause_processing', methods=['POST'])
@admin_required
def admin_pause_processing():
    processor.pause_processing()
    flash('任务处理已暂停', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/resume_processing', methods=['POST'])
@admin_required
def admin_resume_processing():
    processor.resume_processing()
    flash('任务处理已恢复', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/cancel_task', methods=['POST'])
@admin_required
def admin_cancel_task():
    query_code = request.form.get('query_code')
    if not query_code:
        flash('请提供查询码（query_code）', 'error')
        return redirect(url_for('admin'))
    processor.cancel_task(query_code)
    flash(f'已请求取消任务 {query_code}', 'success')
    return redirect(url_for('admin'))


## 将配置加载/创建交给 config 模块
config = get_config()
models_dict = {m['name']: m for m in config.get('models', [])}
ensure_defaults()

# 将处理调用委托给 processor 模块
call_llm_api = processor.call_llm_api
FIRST_PROMPT = getattr(processor, 'FIRST_PROMPT', '')
SECOND_PROMPT = getattr(processor, 'SECOND_PROMPT', '')

# --- 辅助函数：确保字符串只包含 ASCII 字符（用于 API Key 等）---
def ensure_ascii(s, field_name):
    try:
        s.encode('ascii')
        return s
    except UnicodeEncodeError:
        raise ValueError(f"{field_name} 只能包含英文字母、数字和符号（ASCII字符），请检查是否有中文或特殊符号。")



WEB_UI_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数学作业智能批改助手</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        window.MathJax = {
            loader: { load: ['input/tex', 'output/chtml'] },
            chtml: { fontURL: '/static/output/chtml/fonts/woff-v2' },
            startup: { typeset: false }
        };
    </script>
    <script src="/static/tex-chtml.js" id="MathJax-script" async></script>
    <style>
        .result-content {
            white-space: pre-wrap;
            word-break: break-word;
            font-family: monospace;
            background-color: #f9fafb;
            border-radius: 0.5rem;
            padding: 1rem;
            margin: 0;
        }
        .spinner {
            border-top-color: transparent;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-4xl bg-white rounded-xl shadow-lg p-6">
        <h1 class="text-3xl font-bold text-center text-blue-600 mb-8">数学作业智能批改助手</h1>
        <div class="mb-6">
            <label class="block text-gray-700 text-sm font-bold mb-2" for="imageInput">选择包含数学题的图片</label>
            <input type="file" id="imageInput" accept="image/*" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
        </div>
        <div class="flex items-center justify-between mb-8">
            <button id="uploadBtn" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">上传图片</button>
            <div id="uploadStatus" class="text-sm text-gray-500">就绪</div>
        </div>
        <div class="mb-6">
            <label class="block text-gray-700 text-sm font-bold mb-2" for="queryCodeInput">查询码</label>
            <div class="flex">
                <input type="text" id="queryCodeInput" placeholder="上传后自动生成，或直接输入已有的查询码" class="shadow appearance-none border rounded-l w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                <button id="copyCodeBtn" class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold py-2 px-4 rounded-r focus:outline-none focus:shadow-outline">复制</button>
            </div>
            <p class="text-xs text-gray-500 mt-1">已有查询码？直接输入后点击“查询结果”即可查看批改。</p>
        </div>
        <div class="flex items-center justify-between mb-8">
            <button id="queryBtn" class="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">查询结果</button>
            <div id="queryStatus" class="text-sm text-gray-500">等待查询</div>
        </div>
        <div class="mt-8">
            <h2 class="text-xl font-semibold text-gray-800 mb-4">批改结果</h2>
            <div id="resultDisplay" class="bg-gray-50 border border-gray-200 rounded-lg p-6 min-h-[300px]">
                <p class="text-gray-500 italic">结果将在这里显示...</p>
            </div>
        </div>
    </div>
    <script>
        const SERVER_URL = window.location.origin;
        let lastRequestTime = 0;
        const BUTTON_COOLDOWN = 5000;
        function waitForMathJax(attempts = 0) {
            return new Promise((resolve) => {
                if (typeof MathJax !== 'undefined' && MathJax.startup) {
                    if (MathJax.startup.promise) {
                        MathJax.startup.promise.then(() => resolve()).catch(resolve);
                    } else {
                        resolve();
                    }
                } else if (attempts < 50) {
                    setTimeout(() => waitForMathJax(attempts + 1).then(resolve), 100);
                } else {
                    resolve();
                }
            });
        }
        async function renderLatex(element) {
            await waitForMathJax();
            if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
                try {
                    await MathJax.typesetPromise();
                    console.log('LaTeX 渲染完成');
                } catch (err) {
                    console.warn('MathJax 渲染错误:', err);
                }
            }
        }
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        document.addEventListener('DOMContentLoaded', function () {
            const imageInput = document.getElementById('imageInput');
            const uploadBtn = document.getElementById('uploadBtn');
            const uploadStatus = document.getElementById('uploadStatus');
            const queryCodeInput = document.getElementById('queryCodeInput');
            const copyCodeBtn = document.getElementById('copyCodeBtn');
            const queryBtn = document.getElementById('queryBtn');
            const queryStatus = document.getElementById('queryStatus');
            const resultDisplay = document.getElementById('resultDisplay');
            uploadBtn.addEventListener('click', async () => {
                const file = imageInput.files[0];
                if (!file) { alert('请选择一张图片！'); return; }
                const reader = new FileReader();
                reader.onload = async (event) => {
                    const base64Image = event.target.result;
                    try {
                        uploadStatus.textContent = '正在上传...';
                        uploadBtn.disabled = true;
                        uploadBtn.classList.add('opacity-50', 'cursor-not-allowed');
                        const response = await fetch(`${SERVER_URL}/upload_image`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ image_data: base64Image })
                        });
                        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                        const data = await response.json();
                        const queryCode = data.query_code;
                        queryCodeInput.value = queryCode;
                        uploadStatus.textContent = `上传成功！查询码: ${queryCode.slice(0, 8)}...`;
                    } catch (error) {
                        console.error('Upload error:', error);
                        uploadStatus.textContent = `上传失败: ${error.message}`;
                    } finally {
                        uploadBtn.disabled = false;
                        uploadBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    }
                };
                reader.readAsDataURL(file);
            });
            copyCodeBtn.addEventListener('click', () => {
                if (queryCodeInput.value) {
                    navigator.clipboard.writeText(queryCodeInput.value).then(() => alert('查询码已复制到剪贴板！')).catch(err => { console.error('Failed to copy: ', err); alert('复制失败，请手动复制。'); });
                } else { alert('请先上传图片获取查询码。'); }
            });
            queryBtn.addEventListener('click', async () => {
                const currentTime = new Date().getTime();
                if (currentTime - lastRequestTime < BUTTON_COOLDOWN) {
                    const remainingTime = Math.ceil((BUTTON_COOLDOWN - (currentTime - lastRequestTime)) / 1000);
                    queryStatus.textContent = `请稍候 ${remainingTime} 秒...`;
                    return;
                }
                lastRequestTime = currentTime;
                const queryCode = queryCodeInput.value.trim();
                if (!queryCode) { alert('请输入查询码或先上传图片！'); return; }
                try {
                    queryStatus.innerHTML = '<span class="flex items-center"><span class="spinner inline-block w-4 h-4 border-2 border-blue-500 rounded-full mr-2"></span> 正在查询...</span>';
                    queryBtn.disabled = true;
                    queryBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    const response = await fetch(`${SERVER_URL}/query_status`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query_code: queryCode })
                    });
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    const data = await response.json();
                    const status = data.status;
                    const result = data.result;
                    if (status === 'completed') {
                        queryStatus.textContent = '查询完成';
                        resultDisplay.innerHTML = `<div class="result-content">${escapeHtml(result)}</div>`;
                        setTimeout(async () => {
                            const contentDiv = resultDisplay.querySelector('.result-content');
                            if (contentDiv) await renderLatex(contentDiv);
                        }, 100);
                    } else if (status === 'processing') {
                        queryStatus.textContent = 'AI正在分析中，请稍后查询...';
                        resultDisplay.innerHTML = '<p class="text-yellow-600">AI正在分析中，请稍后刷新或再次查询。</p>';
                    } else if (status === 'pending') {
                        queryStatus.textContent = '任务排队中，请稍后查询...';
                        resultDisplay.innerHTML = '<p class="text-yellow-600">任务排队中，请稍后刷新或再次查询。</p>';
                    } else {
                        queryStatus.textContent = '未知状态';
                        resultDisplay.innerHTML = `<p class="text-red-500">服务器返回未知状态: ${status}</p>`;
                    }
                } catch (error) {
                    console.error('Query error:', error);
                    queryStatus.textContent = `查询失败: ${error.message}`;
                    resultDisplay.innerHTML = `<p class="text-red-500">查询失败: ${error.message}</p>`;
                } finally {
                    queryBtn.disabled = false;
                    queryBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
            });
        });
    </script>
</body>
</html>
"""

# --- 模型管理界面 (内嵌 HTML) ---
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>模型管理</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-6xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold text-gray-800">模型管理</h1>
            <div>
                <a href="/" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mr-2">返回批改系统</a>
                <a href="/admin/chat_test" class="bg-purple-500 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded mr-2">对话测试</a>
                <a href="/admin/models/add" class="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded">添加模型</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="mb-4 p-3 rounded {% if category == 'error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- 任务控制: 暂停/恢复/取消 -->
        <section class="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 class="text-lg font-semibold mb-2">任务控制</h3>
            <form action="/admin/pause_processing" method="POST" style="display:inline-block; margin-right:12px;">
                <button type="submit" class="bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-2 px-4 rounded">暂停处理</button>
            </form>
            <form action="/admin/resume_processing" method="POST" style="display:inline-block; margin-right:12px;">
                <button type="submit" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded">恢复处理</button>
            </form>
            <form action="/admin/cancel_task" method="POST" onsubmit="return confirm('请输入查询码 (query_code) 以取消任务')" style="display:inline-block;">
                <input name="query_code" placeholder="查询码 (如: abc123)" required style="padding:6px; border:1px solid #ddd; border-radius:4px"/>
                <button type="submit" class="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded">取消任务</button>
            </form>
        </section>

        <!-- 设置视觉模型和文本模型 -->
        <div class="mb-8 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h2 class="text-xl font-semibold mb-4">批改模型配置</h2>
            <form action="/admin/set_models" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-gray-700 text-sm font-bold mb-2" for="vision_model">视觉模型（用于图片提取）</label>
                    <select name="vision_model" id="vision_model" class="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                        {% for model in models %}
                        <option value="{{ model.name }}" {% if model.name == vision_model %}selected{% endif %}>{{ model.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div>
                    <label class="block text-gray-700 text-sm font-bold mb-2" for="text_model">文本模型（用于批改）</label>
                    <select name="text_model" id="text_model" class="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                        {% for model in models %}
                        <option value="{{ model.name }}" {% if model.name == text_model %}selected{% endif %}>{{ model.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="md:col-span-2">
                    <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">保存设置</button>
                </div>
            </form>
        </div>

        <!-- 模型列表 -->
        <div class="overflow-x-auto">
            <table class="min-w-full bg-white border border-gray-200">
                <thead>
                    <tr class="bg-gray-50">
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">模型名称</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">API Base</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Temperature</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timeout</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for model in models %}
                    <td class="px-6 py-4 whitespace-nowrap">{{ model.api_base }}</td>
                        <td class="px-6 py-4 whitespace-nowrap">{{ model.default_temperature }}</td>
                        <td class="px-6 py-4 whitespace-nowrap">{{ model.timeout }}</td>
<td class="px-6 py-4 whitespace-nowrap">
                            {{ model.name }}
                            {% if model.name == vision_model %}<span class="ml-1 px-1 py-0.5 text-xs bg-green-100 text-green-800 rounded">视觉</span>{% endif %}
                            {% if model.name == text_model %}<span class="ml-1 px-1 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">文本</span>{% endif %}
                            {% if model.name == default_model %}<span class="ml-1 px-1 py-0.5 text-xs bg-gray-100 text-gray-800 rounded">默认</span>{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

MODEL_FORM_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% if action == 'add' %}添加模型{% else %}编辑模型{% endif %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <h1 class="text-2xl font-bold text-gray-800 mb-6">{% if action == 'add' %}添加模型{% else %}编辑模型{% endif %}</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="mb-4 p-3 rounded {% if category == 'error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="mb-4">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="name">模型名称</label>
                <input type="text" name="name" id="name" value="{{ model.name if model else '' }}" {% if action == 'edit' %}readonly{% endif %} required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                {% if action == 'edit' %}<p class="text-xs text-gray-500 mt-1">模型名称不可修改</p>{% endif %}
            </div>
            <div class="mb-4">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="api_base">API Base</label>
                <input type="url" name="api_base" id="api_base" value="{{ model.api_base if model else '' }}" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
            </div>
            <div class="mb-4">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="api_key">API Key</label>
                <input type="text" name="api_key" id="api_key" value="{{ model.api_key if model else '' }}" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                <p class="text-xs text-gray-500 mt-1">仅支持ASCII字符</p>
            </div>
            <div class="mb-4">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="default_temperature">Temperature</label>
                <input type="number" step="0.1" name="default_temperature" id="default_temperature" value="{{ model.default_temperature if model else 0.7 }}" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
            </div>
            <div class="mb-6">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="timeout">Timeout (秒)</label>
                <input type="number" name="timeout" id="timeout" value="{{ model.timeout if model else 60 }}" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
            </div>
            <div class="flex items-center justify-between">
                <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
                    保存
                </button>
                <a href="/admin" class="text-gray-600 hover:text-gray-800">取消</a>
            </div>
        </form>
    </div>
</body>
</html>
"""

# --- 对话测试界面 (内嵌 HTML) ---
CHAT_TEST_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>对话测试</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .result-box {
            white-space: pre-wrap;
            word-break: break-word;
            background-color: #f9fafb;
            border-radius: 0.5rem;
            padding: 1rem;
            min-height: 200px;
        }
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold text-gray-800">对话测试</h1>
            <a href="/admin" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">返回管理</a>
        </div>

        <form id="chatForm" class="space-y-4">
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="model">选择模型</label>
                <select name="model" id="model" class="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                    {% for model in models %}
                    <option value="{{ model.name }}">{{ model.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="prompt">提示词</label>
                <textarea name="prompt" id="prompt" rows="5" class="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" placeholder="输入您的消息..."></textarea>
            </div>
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="imageFile">图片（可选）</label>
                <input type="file" id="imageFile" accept="image/*" class="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline">
                <div id="imagePreview" class="mt-2 hidden">
                    <img id="previewImg" class="max-h-48 rounded" alt="预览">
                </div>
            </div>
            <div>
                <button type="submit" id="sendBtn" class="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">发送请求</button>
                <span id="loading" class="ml-4 text-gray-500 hidden">处理中...</span>
            </div>
        </form>

        <div class="mt-8">
            <h2 class="text-xl font-semibold text-gray-800 mb-4">响应结果</h2>
            <div id="result" class="result-box border border-gray-200">
                <p class="text-gray-500 italic">等待测试...</p>
            </div>
        </div>
    </div>

    <script>
        const form = document.getElementById('chatForm');
        const sendBtn = document.getElementById('sendBtn');
        const loading = document.getElementById('loading');
        const resultDiv = document.getElementById('result');
        const imageFileInput = document.getElementById('imageFile');
        const imagePreview = document.getElementById('imagePreview');
        const previewImg = document.getElementById('previewImg');

        // 预览图片
        imageFileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewImg.src = e.target.result;
                    imagePreview.classList.remove('hidden');
                };
                reader.readAsDataURL(this.files[0]);
            } else {
                imagePreview.classList.add('hidden');
                previewImg.src = '';
            }
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            sendBtn.disabled = true;
            loading.classList.remove('hidden');
            resultDiv.innerHTML = '<p class="text-gray-500 italic">请求发送中...</p>';

            const model = document.getElementById('model').value;
            const prompt = document.getElementById('prompt').value;
            const imageFile = imageFileInput.files[0];

            let imageData = null;
            if (imageFile) {
                const reader = new FileReader();
                imageData = await new Promise((resolve) => {
                    reader.onload = (e) => resolve(e.target.result);
                    reader.readAsDataURL(imageFile);
                });
            }

            try {
                const response = await fetch('/chat_test_api', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: model,
                        prompt: prompt,
                        image_data: imageData
                    })
                });
                const data = await response.json();
                if (response.ok) {
                    resultDiv.innerHTML = `<div class="whitespace-pre-wrap">${escapeHtml(data.response)}</div>`;
                } else {
                    resultDiv.innerHTML = `<div class="text-red-600">错误: ${escapeHtml(data.error)}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="text-red-600">请求失败: ${escapeHtml(error.message)}</div>`;
            } finally {
                sendBtn.disabled = false;
                loading.classList.add('hidden');
            }
        });

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
    </script>
</body>
</html>
"""

STATUS_HTML = """
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>服务端状态</title>
  <style>body{font-family:Arial, sans-serif; padding:2rem;} .card{border:1px solid #ddd; padding:1rem; border-radius:6px; margin:1rem 0;}</style>
</head>
<body>
  <h2>服务端状态</h2>
  <div class=\"card\">Pending: {{ pending }} 条</div>
  <div class=\"card\">Processing: {{ processing }} 条</div>
  <div class=\"card\">Completed: {{ completed }} 条</div>
  <div class=\"card\">Last Updated: {{ last_updated }} UTC</div>
  <p><a href=\"/admin\">返回管理面板</a></p>
</body>
</html>
"""

@app.route('/admin/status')
@admin_required
def admin_status():
    try:
        pending = len([f for f in os.listdir(PENDING_DIR)])
        processing = len([f for f in os.listdir(PROCESSING_DIR)])
        completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
        last_updated = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pending = processing = completed = 0
        last_updated = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(STATUS_HTML, pending=pending, processing=processing, completed=completed, last_updated=last_updated)

# 简单的健康检查接口，供运维监控
@app.route('/healthz', methods=['GET'])
def healthz():
    try:
        pending = len([f for f in os.listdir(PENDING_DIR)])
        processing = len([f for f in os.listdir(PROCESSING_DIR)])
        completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
        uptime = int(time.time() - SERVER_START_TIME)
        return jsonify({
            'status': 'ok',
            'uptime_seconds': uptime,
            'pending': pending,
            'processing': processing,
            'completed': completed
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# 简单的日志查看页面，便于运维查看最近日志
LOGS_HTML = """
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\">
  <title>运行日志</title>
  <style>pre{white-space:pre-wrap; word-break:break-word;}</style>
</head>
<body style=\"font-family:Arial, sans-serif; padding:2rem;\">
  <h2>最近日志</h2>
  <pre style=\"background:#f6f6f6; padding:1rem; border-radius:6px; max-height:70vh; overflow:auto;\">{{ logs }}</pre>
  <p><a href=\"/admin\">返回管理面板</a></p>
</body>
</html>
"""

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

@app.route('/admin/logs', methods=['GET'])
@admin_required
def admin_logs():
    logs = _tail_log(500)
    return render_template_string(LOGS_HTML, logs=logs)
# --- API 路由 ---
@app.route('/')
def index():
    """主页，返回网页版客户端UI"""
    return render_template_string(WEB_UI_HTML)

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

        return jsonify({'status': status, 'result': result_text})

    except Exception as e:
        logger.error(f"Query status error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

from flask import render_template

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
  # 数据聚合
    try:
        pending = len([f for f in os.listdir(PENDING_DIR)])
        processing = len([f for f in os.listdir(PROCESSING_DIR)])
        completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
        models_list = config.get('models', [])
        default_model = config.get('default_model', '')
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
        vision_model = config.get('vision_model', '')
        text_model = config.get('text_model', '')
        summary = {
            'pending': pending,
            'processing': processing,
            'completed': completed
        }
        return render_template('admin_dashboard.html', summary=summary, models=models_list, default_model=default_model, vision_model=vision_model, text_model=text_model, uptime=uptime, recent_results=recent_results, tasks=tasks)
    except Exception as e:
        logger.error(f"admin_dashboard error: {e}")
        # 回退到简单文本页面，避免阻塞
        return f"Admin dashboard error: {e}"

@app.route('/admin')
@admin_required
def admin():
    return redirect(url_for('admin_dashboard'))

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
    pending = len([f for f in os.listdir(PENDING_DIR)])
    processing = len([f for f in os.listdir(PROCESSING_DIR)])
    completed = len([f for f in os.listdir(RESULTS_DIR) if f.endswith('.txt')])
    models_list = config.get('models', [])
    default_model = config.get('default_model', '')
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
    return jsonify(config.get('models', []))

@app.route('/admin/api/tasks', methods=['GET'])
@admin_required
def admin_api_tasks():
    return jsonify({'tasks': _collect_tasks()})

@app.route('/admin/set_default_models', methods=['POST'])
@admin_required
def set_default_models():
    vision_model = request.form.get('vision_model')
    text_model = request.form.get('text_model')
    if vision_model and text_model and vision_model in models_dict and text_model in models_dict:
        config['vision_model'] = vision_model
        config['text_model'] = text_model
        save_config(config)
        flash(f'默认视觉模型已设为 {vision_model}，默认文本模型已设为 {text_model}', 'success')
    else:
        flash('请选择两个有效的模型', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/set_models', methods=['POST'])
@admin_required
def set_models():
    """设置视觉模型和文本模型"""
    vision_model = request.form.get('vision_model')
    text_model = request.form.get('text_model')
    if vision_model and text_model:
        if vision_model in models_dict and text_model in models_dict:
            config['vision_model'] = vision_model
            config['text_model'] = text_model
            save_config(config)
            flash(f'视觉模型已设为 {vision_model}，文本模型已设为 {text_model}', 'success')
        else:
            flash('所选模型不存在', 'error')
    else:
        flash('请选择两个模型', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/models/add', methods=['GET', 'POST'])
@admin_required
def add_model():
    if request.method == 'POST':
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
        config['models'].append(new_model)
        models_dict[name] = new_model
        if not config.get('default_model'):
            config['default_model'] = name
        save_config(config)
        logger.info(f"模型 {name} 已添加。")
        flash(f'模型 "{name}" 添加成功', 'success')
        return redirect(url_for('admin'))
    return render_template_string(MODEL_FORM_HTML, action='add', model=None)

@app.route('/admin/models/edit/<path:name>', methods=['GET', 'POST'])
@admin_required
def edit_model(name):
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

        save_config(config)
        logger.info(f"模型 {name} 已更新。")
        flash(f'模型 "{name}" 更新成功', 'success')
        return redirect(url_for('admin'))

    model = models_dict[name]
    return render_template_string(MODEL_FORM_HTML, action='edit', model=model)

@app.route('/admin/models/delete/<path:name>', methods=['POST'])
@admin_required
def delete_model(name):
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))

    config['models'] = [m for m in config['models'] if m['name'] != name]
    del models_dict[name]

    if config.get('default_model') == name:
        config['default_model'] = config['models'][0]['name'] if config['models'] else ''
    if config.get('vision_model') == name:
        config['vision_model'] = config['models'][0]['name'] if config['models'] else ''
    if config.get('text_model') == name:
        config['text_model'] = config['models'][0]['name'] if config['models'] else ''
    save_config(config)
    logger.info(f"模型 {name} 已删除。")
    flash(f'模型 "{name}" 删除成功', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/models/set_default/<path:name>', methods=['POST'])
@admin_required
def set_default_model(name):
    if name not in models_dict:
        flash(f'模型 "{name}" 不存在', 'error')
        return redirect(url_for('admin'))

    config['default_model'] = name
    save_config(config)
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
    return render_template_string(CHAT_TEST_HTML, models=config['models'])

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
    try:
        body = request.get_json()
        if not body:
            return jsonify({'error': 'Invalid JSON'}), 400

        model_name = body.get('model') or config.get('default_model')
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
