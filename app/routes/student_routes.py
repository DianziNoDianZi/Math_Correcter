"""
学生端路由
"""
from flask import Blueprint, request, jsonify, session

student_bp = Blueprint('student', __name__, url_prefix='/api/student')

def init_student_routes(class_service, exam_service):
    """初始化学生路由"""
    
    @student_bp.route('/login', methods=['POST'])
    def login():
        """学生登录"""
        data = request.get_json() or {}
        student_number = data.get('student_number', '').strip()
        password = data.get('password', '').strip()
        
        if not student_number or not password:
            return jsonify({'success': False, 'error': '请输入学号和密码'}), 400
        
        student = class_service.verify_student(student_number, password)
        if student:
            session['student_logged_in'] = True
            session['student_number'] = student_number
            session['student_name'] = student.get('name')
            return jsonify({
                'success': True,
                'student': student
            })
        
        return jsonify({'success': False, 'error': '学号或密码错误'}), 401
    
    @student_bp.route('/logout', methods=['POST'])
    def logout():
        """学生登出"""
        session.pop('student_logged_in', None)
        session.pop('student_number', None)
        session.pop('student_name', None)
        return jsonify({'success': True})
    
    @student_bp.route('/status')
    def status():
        """获取登录状态"""
        if session.get('student_logged_in'):
            student = class_service.get_student(session.get('student_number'))
            if student:
                return jsonify({
                    'success': True,
                    'logged_in': True,
                    'student': student
                })
        
        return jsonify({
            'success': True,
            'logged_in': False
        })
    
    @student_bp.route('/change_password', methods=['POST'])
    def change_password():
        """修改密码"""
        if not session.get('student_logged_in'):
            return jsonify({'success': False, 'error': '请先登录'}), 401
        
        data = request.get_json() or {}
        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not old_password or not new_password:
            return jsonify({'success': False, 'error': '请填写完整信息'}), 400
        
        result = class_service.change_password(
            session.get('student_number'),
            old_password,
            new_password
        )
        
        return jsonify(result)
    
    @student_bp.route('/<student_number>/scores')
    def get_scores(student_number):
        """获取学生所有成绩"""
        scores = exam_service.get_student_scores(student_number)
        student = class_service.get_student(student_number)
        
        if not student:
            return jsonify({'success': False, 'error': '学生不存在'}), 404
        
        # 计算概览统计
        overview = {
            'total_exams': len(scores),
            'avg_score': 0,
            'best_score': 0,
            'avg_accuracy': 0
        }
        
        if scores:
            overview['avg_score'] = sum(s['score'] for s in scores) / len(scores)
            overview['best_score'] = max(s['score'] for s in scores)
            overview['avg_accuracy'] = sum(s['accuracy'] for s in scores) / len(scores)
        
        return jsonify({
            'success': True,
            'student': student,
            'exams': scores,
            'overview': overview
        })
    
    @student_bp.route('/<student_number>/wrong_questions')
    def get_wrong_questions(student_number):
        """获取错题本"""
        wrong_questions = exam_service.get_wrong_questions(student_number)
        return jsonify({
            'success': True,
            'wrong_questions': wrong_questions
        })
    
    return student_bp
