"""
班级管理路由
"""
from flask import Blueprint, request, jsonify

classes_bp = Blueprint('classes', __name__, url_prefix='/api/classes')

def init_class_routes(class_service):
    """初始化班级路由"""
    
    @classes_bp.route('', methods=['GET'])
    def get_all_classes():
        """获取所有班级"""
        classes = class_service.get_all_classes()
        return jsonify({
            'success': True,
            'classes': classes,
            'total': len(classes)
        })
    
    @classes_bp.route('', methods=['POST'])
    def create_class():
        """创建班级"""
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        grade = data.get('grade', '10-12').strip()
        teacher_name = data.get('teacher_name', '').strip()
        
        result = class_service.create_class(name, grade, teacher_name)
        return jsonify(result)
    
    @classes_bp.route('/<class_id>', methods=['DELETE'])
    def delete_class(class_id):
        """删除班级"""
        result = class_service.delete_class(class_id)
        return jsonify(result)
    
    @classes_bp.route('/<class_id>/students', methods=['POST'])
    def add_student(class_id):
        """添加学生"""
        data = request.get_json() or {}
        student = data.get('student', {})
        
        name = student.get('name', '').strip()
        student_number = student.get('student_number', '').strip()
        password = student.get('password', '').strip()
        
        result = class_service.add_student(class_id, name, student_number, password)
        return jsonify(result)
    
    @classes_bp.route('/<class_id>/students/<student_number>', methods=['DELETE'])
    def remove_student(class_id, student_number):
        """删除学生"""
        result = class_service.remove_student(class_id, student_number)
        return jsonify(result)
    
    return classes_bp
