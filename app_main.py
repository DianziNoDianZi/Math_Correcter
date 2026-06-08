"""
应用主入口 - 模块化版本
"""
import os
import sys
from pathlib import Path
from flask import send_from_directory

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.config import config, Config

def main():
    """主函数"""
    # 初始化配置
    Config.init_app()
    
    # 获取环境配置
    env = os.environ.get('FLASK_ENV', 'development')
    app_config = config.get(env, config['default'])
    
    # 创建应用
    app = create_app({
        'SECRET_KEY': app_config.SECRET_KEY,
        'DEBUG': app_config.DEBUG
    })
    
    # 获取模板目录路径
    templates_dir = str(Path(__file__).parent / 'templates')
    
    # 添加页面路由
    @app.route('/')
    def home():
        """首页"""
        return send_from_directory(templates_dir, 'index.html')
    
    @app.route('/teacher')
    def teacher_page():
        """教师端页面"""
        return send_from_directory(templates_dir, 'teacher.html')
    
    @app.route('/admin')
    def admin_page():
        """管理后台页面"""
        return send_from_directory(templates_dir, 'admin.html')
    
    @app.route('/answer_sheet_template.html')
    def answer_sheet_template():
        """答题卡模板下载"""
        return send_from_directory(templates_dir, 'answer_sheet_template.html')
    
    # 运行服务器
    print(f"启动服务器在 {app_config.HOST}:{app_config.PORT}")
    print(f"环境: {env}")
    print(f"调试模式: {app_config.DEBUG}")
    
    app.run(
        host=app_config.HOST,
        port=app_config.PORT,
        debug=app_config.DEBUG
    )

if __name__ == '__main__':
    main()
