# -*- coding: utf-8 -*-
"""配置管理：加载/保存/提供模型配置和字典查询。

职责：
- 提供全局配置对象（来自 config.yaml），在需要时自动创建默认配置。
- 提供模型字典（name -> 模型配置）的快速获取接口。
- 提供确保默认字段的实用函数，避免运行时缺失字段导致错误。
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.yaml'

# 目录常量
UPLOAD_FOLDER = 'uploads'
PENDING_DIR = 'pending'
PROCESSING_DIR = 'processing'
RESULTS_DIR = 'results'
PAUSE_FLAG_PATH = 'paused.flag'
CANCELLED_DIR = 'cancelled'

# 默认配置（初次创建时使用）
DEFAULT_CONFIG = {
    'default_model': '',
    'vision_model': '',
    'text_model': '',
    'models': [],
    'customization': {
        'bg_type': 'gradient',
        'bg_color1': '#667eea',
        'bg_color2': '#764ba2',
        'bg_image': ''
    },
    'tts': {
        'enabled': False,
        'engine': 'qwen-tts',
        'api_base': 'http://127.0.0.1:7860',
        'voice': 'default',
        'speed': 1.0,
        'model_name': 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
        'output_dir': 'D:\\qwen-tts-webui\\core\\outputs',
        'refer_wav': '',
        'prompt_text': '',
        'prompt_language': '中文',
        'sovits_model': '',
        'gpt_model': ''
    }
}

# 全局配置对象与模型字典缓存
_config = None
_models_dict = {}

def _reload_config():
    global _config, _models_dict
    # 如果没有配置文件，创建默认配置并写入磁盘
    if not os.path.exists(CONFIG_FILE):
        _config = DEFAULT_CONFIG.copy()
        try:
            _save_config(_config)
            logger.info(f"Created default config file at {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
    else:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config file {CONFIG_FILE}: {e}, using default config")
            data = {}
        
        _config = {
            'default_model': data.get('default_model', DEFAULT_CONFIG['default_model']),
            'vision_model': data.get('vision_model', DEFAULT_CONFIG['vision_model']),
            'text_model': data.get('text_model', DEFAULT_CONFIG['text_model']),
            'models': data.get('models', []),
            'customization': data.get('customization', DEFAULT_CONFIG.get('customization', {})),
            'tts': data.get('tts', DEFAULT_CONFIG.get('tts', {}))
        }
        # 兼容性：确保 models 字段存在
        if not isinstance(_config.get('models', []), list):
            _config['models'] = []
        try:
            _save_config(_config)  # 保证磁盘与内存一致性
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    # 构建模型字典
    _models_dict = {m['name']: m for m in _config.get('models', [])}

def _save_config(cfg):
    try:
        # 确保目录存在
        dir_name = os.path.dirname(CONFIG_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        logger.error(f"Failed to write config to {CONFIG_FILE}: {e}")
        raise

def get_config():
    global _config
    if _config is None:
        _reload_config()
    return _config

def save_config(cfg):
    global _config
    _config = cfg
    _save_config(_config)
    # 重新加载以刷新缓存字典
    _reload_config()

def get_models_dict():
    global _models_dict
    if not _models_dict:
        _reload_config()
    return _models_dict

def ensure_defaults():
    """确保配置中包含必要的字段，如无则保持为空，由用户自行配置。"""
    cfg = get_config()
    changed = False
    if 'vision_model' not in cfg:
        cfg['vision_model'] = ''
        changed = True
    if 'text_model' not in cfg:
        cfg['text_model'] = ''
        changed = True
    if changed:
        save_config(cfg)

# 初始化加载，确保基础字段存在
_reload_config()
ensure_defaults()
