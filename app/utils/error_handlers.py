"""
错误处理器
"""
from flask import jsonify, render_template

def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        return jsonify({
            'success': False,
            'error': '资源未找到',
            'code': 404
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        return jsonify({
            'success': False,
            'error': '服务器内部错误',
            'code': 500
        }), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        """403错误处理"""
        return jsonify({
            'success': False,
            'error': '权限不足',
            'code': 403
        }), 403
    
    @app.errorhandler(400)
    def bad_request(error):
        """400错误处理"""
        return jsonify({
            'success': False,
            'error': '请求参数错误',
            'code': 400
        }), 400
