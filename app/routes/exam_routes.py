"""
考试管理路由
"""
from flask import Blueprint, request, jsonify
import sys
import os
from pathlib import Path

# 导入test_library用于扫描和分析
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import test_library

exams_bp = Blueprint('exams', __name__, url_prefix='/api/exams')

def init_exam_routes(exam_service):
    """初始化考试路由"""
    
    @exams_bp.route('', methods=['GET'])
    def get_all_exams():
        """获取所有考试"""
        exam_service.model.reload()  # 刷新缓存
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
        exam_service.model.reload()  # 刷新缓存，确保获取最新数据
        exam = exam_service.get_exam(exam_id)
        if exam:
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            scores = exam.get('scores', [])
            total_count = len(scores)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            # 计算统计数据（基于所有成绩）
            if scores:
                score_values = [s.get('total_score', 0) for s in scores]
                avg_score = sum(score_values) / len(score_values)
                pass_count = sum(1 for s in scores if s.get('accuracy', 0) >= 60)
                pass_rate = pass_count / len(scores) * 100 if scores else 0
            else:
                avg_score = 0
                pass_rate = 0
            
            # 分页获取当前页数据
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_scores = scores[start_idx:end_idx]
            
            return jsonify({
                'success': True,
                'exam': exam,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': total_count,
                    'total_pages': total_pages
                },
                'statistics': {
                    'total_students': total_count,
                    'average_score': round(avg_score, 2),
                    'pass_rate': round(pass_rate, 2)
                }
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
        correct_answer = data.get('correct_answer', '').strip()
        score = float(data.get('score', 5))
        knowledge_points = data.get('knowledge_points', [])
        question_type = data.get('type', 'choice').strip()
        
        result = exam_service.add_question(
            exam_id, number, content, correct_answer,
            score, knowledge_points, question_type
        )
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/questions/import', methods=['POST'])
    def import_questions(exam_id):
        """批量导入题目"""
        data = request.get_json() or {}
        questions = data.get('questions', [])
        
        if not questions:
            return jsonify({'success': False, 'error': '没有要导入的题目'}), 400
        
        result = exam_service.batch_import_questions(exam_id, questions)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/ready', methods=['POST'])
    def set_ready(exam_id):
        """设置考试为就绪"""
        result = exam_service.set_ready(exam_id)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/questions/<int:question_number>', methods=['PUT'])
    def update_question(exam_id, question_number):
        """更新题目"""
        data = request.get_json() or {}
        result = exam_service.update_question(exam_id, question_number, data)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/questions/<int:question_number>', methods=['DELETE'])
    def delete_question(exam_id, question_number):
        """删除题目"""
        result = exam_service.delete_question(exam_id, question_number)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/questions', methods=['DELETE'])
    def clear_questions(exam_id):
        """清空所有题目"""
        result = exam_service.clear_questions(exam_id)
        return jsonify(result)
    
    @exams_bp.route('/<exam_id>/duplicate', methods=['POST'])
    def duplicate_exam(exam_id):
        """复制考试"""
        data = request.get_json() or {}
        new_name = data.get('name', '').strip()
        result = exam_service.duplicate_exam(exam_id, new_name)
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
    
    @exams_bp.route('/<exam_id>/scan', methods=['POST'])
    def scan_exam(exam_id):
        """批量扫描答题卡"""
        try:
            if 'files' not in request.files:
                return jsonify({'success': False, 'error': '没有上传文件'}), 400
            
            files = request.files.getlist('files')
            if not files:
                return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400
            
            image_files = []
            for file in files:
                if file.filename == '':
                    continue
                image_files.append((file.filename, file.read()))
            
            if not image_files:
                return jsonify({'success': False, 'error': '没有有效的图片文件'}), 400
            
            result = test_library.batch_scan_answer_sheets(exam_id, image_files)
            exam_service.model.reload()  # 刷新缓存
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @exams_bp.route('/<exam_id>/adjust', methods=['POST'])
    def adjust_exam_score(exam_id):
        """调整单条成绩"""
        try:
            data = request.get_json() or {}
            student_number = data.get('student_number')
            score = data.get('score')
            reason = data.get('reason', '')
            
            if not student_number or score is None:
                return jsonify({'success': False, 'error': '参数不完整'}), 400
            
            result = test_library.adjust_score(exam_id, student_number, float(score), reason)
            exam_service.model.reload()  # 刷新缓存
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @exams_bp.route('/<exam_id>/scores/<student_number>/questions/<int:question_number>', methods=['PUT'])
    def adjust_question_score(exam_id, student_number, question_number):
        """调整单题成绩"""
        try:
            data = request.get_json() or {}
            new_score = data.get('score')
            adjust_reason = data.get('reason', '')
            
            if new_score is None:
                return jsonify({'success': False, 'error': '参数不完整'}), 400
            
            result = test_library.adjust_question_score(
                exam_id, student_number, question_number, float(new_score), adjust_reason
            )
            exam_service.model.reload()  # 刷新缓存
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @exams_bp.route('/<exam_id>/analysis', methods=['GET'])
    def get_exam_analysis(exam_id):
        """获取考试详细分析"""
        try:
            result = test_library.get_exam_analysis(exam_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @exams_bp.route('/<exam_id>/ai-report', methods=['GET'])
    def get_ai_exam_report(exam_id):
        """获取 AI 生成的考试分析报告"""
        try:
            result = test_library.generate_ai_exam_report(exam_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return exams_bp
