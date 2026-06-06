"""
学生管理路由
"""
from flask import Blueprint, request, jsonify

students_bp = Blueprint('students', __name__, url_prefix='/api/students')

def init_student_management_routes(class_service):
    """初始化学生管理路由"""
    
    @students_bp.route('/<student_number>/password', methods=['PUT'])
    def reset_password(student_number):
        """重置学生密码"""
        data = request.get_json() or {}
        new_password = data.get('password', student_number).strip()
        
        result = class_service.reset_password(student_number, new_password)
        return jsonify(result)
    
    return students_bp
