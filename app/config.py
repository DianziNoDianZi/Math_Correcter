"""
应用配置管理
"""
import os
from pathlib import Path

class Config:
    """应用配置类"""
    
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # 服务器配置
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8000))
    
    # API密钥配置
    DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
    
    # 管理员账号配置
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'changeme')
    
    # 教师账号配置
    TEACHER_USER = os.environ.get('TEACHER_USER', 'teacher')
    TEACHER_PASS = os.environ.get('TEACHER_PASS', 'teacher123')
    
    # 数据存储路径
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / 'data'
    CLASSES_DIR = DATA_DIR / 'classes'
    EXAMS_DIR = DATA_DIR / 'exams'
    REPORTS_DIR = DATA_DIR / 'reports'
    EXPORTS_DIR = DATA_DIR / 'exports'
    LOGS_DIR = BASE_DIR / 'logs'
    
    # 上传配置
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # 任务清理配置
    TASK_CLEANUP_DAYS = int(os.environ.get('TASK_CLEANUP_DAYS', 7))
    
    @classmethod
    def init_app(cls):
        """初始化应用所需目录"""
        for directory in [cls.DATA_DIR, cls.CLASSES_DIR, cls.EXAMS_DIR, 
                         cls.REPORTS_DIR, cls.EXPORTS_DIR, cls.LOGS_DIR, 
                         cls.UPLOAD_FOLDER]:
            directory.mkdir(parents=True, exist_ok=True)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
