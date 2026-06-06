"""
应用包初始化
"""
from flask import Flask
from flask_cors import CORS

def create_app(config=None):
    """
    应用工厂函数
    
    Args:
        config: 配置字典，可选
        
    Returns:
        Flask应用实例
    """
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    
    # 加载配置
    if config:
        app.config.update(config)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册蓝图
    from app.routes import register_blueprints
    register_blueprints(app)
    
    # 注册错误处理器
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    return app
