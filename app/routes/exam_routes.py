"""
考试管理路由
"""
from flask import Blueprint, request, jsonify

exams_bp = Blueprint('exams', __name__, url_prefix='/api/exams')

def init_exam_routes(exam_service):
    """初始化考试路由"""
    
    @exams_bp.route('', methods=['GET'])
    def get_all_exams():
        """获取所有考试"""
        exams = exam_service.get_all_exams()
        return jsonify({
            'success': True,
            'exams': exams,
            'total': len(exams)
        })
    
    @exams_bp.route('', methods=['POST'])
    def create_exam():
        """创建考试"""
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        class_id = data.get('class_id', '').strip()
        total_score = float(data.get('total_score', 100))
        grade = data.get('grade', '').strip()
        
        result = exam_service.create_exam(name, class_id, total_score, grade)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>', methods=['GET'])
    def get_exam(exam_id):
        """获取考试详情"""
        exam = exam_service.get_exam(exam_id)
        if exam:
            return jsonify({
                'success': True,
                'exam': exam
            })
        return jsonify({'success': False, 'error': '考试未找到'}), 404
    
    @exams_bp.route('/<exam_id>', methods=['DELETE'])
    def delete_exam(exam_id):
        """删除考试"""
        result = exam_service.delete_exam(exam_id)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/questions', methods=['POST'])
    def add_question(exam_id):
        """添加题目"""
        data = request.get_json() or {}
        
        number = data.get('number')
        content = data.get('content', '').strip()
        answer = data.get('answer', '').strip()
        score = float(data.get('score', 5))
        knowledge_point = data.get('knowledge_point', '').strip()
        question_type = data.get('type', 'choice').strip()
        
        result = exam_service.add_question(
            exam_id, number, content, answer,
            score, knowledge_point, question_type
        )
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/ready', methods=['POST'])
    def set_ready(exam_id):
        """设置考试为就绪"""
        result = exam_service.set_ready(exam_id)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/scores', methods=['POST'])
    def add_score(exam_id):
        """添加成绩"""
        data = request.get_json() or {}
        
        student_number = data.get('student_number', '').strip()
        student_name = data.get('student_name', '').strip()
        results = data.get('results', [])
        
        result = exam_service.add_score(exam_id, student_number, student_name, results)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/confirm', methods=['POST'])
    def confirm_scores(exam_id):
        """确认成绩"""
        result = exam_service.confirm_scores(exam_id)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/statistics', methods=['GET'])
    def get_statistics(exam_id):
        """获取考试统计"""
        result = exam_service.get_exam_statistics(exam_id)
        return jsonify(result)
    
    return exams_bp
