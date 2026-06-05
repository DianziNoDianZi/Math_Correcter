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
from pathlib import Path

# 配置、日志、临时文件存放目录

# 获取项目根目录（跨平台）
PROJECT_ROOT = Path(__file__).parent.absolute()

CONFIG_FILE = PROJECT_ROOT / 'config.yaml'
LOG_FILE = PROJECT_ROOT / 'logs' / 'app.log'
DATA_DIR = PROJECT_ROOT / 'data'

# 创建必要的目录
(DATA_DIR / 'logs').mkdir(parents=True, exist_ok=True)
PROJECT_ROOT.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_cross_platform_path(path: str) -> str:
    """获取跨平台路径
    支持环境变量（如 $TTS_OUTPUT_DIR）和相对路径
    """
    if not path:
        return str(DATA_DIR / 'tts_outputs')
    
    # 如果是绝对路径且包含反斜杠（Windows），尝试转换
    if '\\' in path:
        # 检查是否是绝对路径
        if path.startswith('D:\\') or path.startswith('C:\\') or path.startswith('E:\\'):
            # 提取相对部分
            relative_part = Path(path).name
            return str(DATA_DIR / 'tts_outputs' / relative_part)
    
    # 如果路径以$开头，尝试获取环境变量
    if path.startswith('$'):
        env_var = os.getenv(path[1:])
        if env_var:
            return env_var
        return str(DATA_DIR / 'tts_outputs')
    
    # 如果是相对路径，基于项目根目录
    if not os.path.isabs(path):
        return str(PROJECT_ROOT / path)
    
    return path

# ========== 文件上传安全验证 ==========

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES_COUNT = 200  # 单次最多上传文件数

def validate_file_upload(file, max_size: int = MAX_FILE_SIZE) -> tuple[bool, str]:
    """验证单个上传文件
    返回: (是否通过验证, 错误信息)
    """
    if not file or file.filename == '':
        return False, '文件名为空'
    
    # 检查文件大小
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset position
    
    if size > max_size:
        return False, f'文件大小超过限制（最大{max_size // (1024*1024)}MB）'
    
    if size == 0:
        return False, '文件为空'
    
    # 检查文件扩展名
    filename = file.filename.lower()
    has_valid_extension = any(filename.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS)
    if not has_valid_extension:
        return False, f'不支持的文件类型（仅支持: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}）'
    
    # 检查MIME类型
    content_type = file.content_type
    if content_type not in ALLOWED_MIME_TYPES:
        # 某些浏览器可能不发送content-type，再次检查文件内容
        # 这里简化处理，依赖扩展名验证
        pass
    
    return True, ''

def validate_batch_upload(files, max_count: int = MAX_FILES_COUNT, max_size: int = MAX_FILE_SIZE) -> tuple[bool, str]:
    """验证批量上传
    返回: (是否通过验证, 错误信息)
    """
    if not files or len(files) == 0:
        return False, '没有上传文件'
    
    if len(files) > max_count:
        return False, f'文件数量超过限制（最多{max_count}个）'
    
    # 验证每个文件
    for i, file in enumerate(files, 1):
        is_valid, error_msg = validate_file_upload(file, max_size)
        if not is_valid:
            return False, f'第{i}个文件验证失败: {error_msg}'
    
    return True, ''

# 目录常量
UPLOAD_FOLDER = 'uploads'
PENDING_DIR = 'pending'
PROCESSING_DIR = 'processing'
RESULTS_DIR = 'results'
PAUSE_FLAG_PATH = 'paused.flag'
CANCELLED_DIR = 'cancelled'
TEST_LIBRARY_DIR = 'test_library'  # 试卷库目录

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
        'output_dir': 'outputs',  # 相对路径，会自动转换
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
    """获取模型字典，自动从环境变量读取API密钥"""
    global _models_dict
    if not _models_dict:
        _reload_config()
    
    # 从环境变量覆盖API密钥
    enhanced_dict = {}
    for model_name, model_info in _models_dict.items():
        # 优先使用环境变量中的密钥
        env_key = f"DASHSCOPE_API_KEY_{model_name.upper().replace('-', '_').replace('.', '_')}"
        env_api_key = os.getenv(env_key) or os.getenv('DASHSCOPE_API_KEY')
        
        model_copy = model_info.copy()
        if env_api_key:
            model_copy['api_key'] = env_api_key
        
        enhanced_dict[model_name] = model_copy
    
    return enhanced_dict

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
