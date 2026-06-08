"""
班级管理路由
"""
from flask import Blueprint, request, jsonify
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.services.exam_service import ExamService

classes_bp = Blueprint('classes', __name__, url_prefix='/api/classes')

def init_class_routes(class_service):
    """初始化班级路由"""
    
    exam_service = ExamService(Path(__file__).parent.parent.parent / 'data')
    
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
    
    @classes_bp.route('/<class_id>/students/batch', methods=['POST'])
    def batch_add_students(class_id):
        """批量导入学生"""
        data = request.get_json() or {}
        students = data.get('students', [])
        if not students:
            return jsonify({'success': False, 'error': '没有学生数据'}), 400
        
        success_count = 0
        fail_list = []
        for s in students:
            name = s.get('name', '').strip()
            number = s.get('student_number', '').strip()
            password = s.get('password', '').strip()
            if not name or not number:
                fail_list.append(str(s))
                continue
            result = class_service.add_student(class_id, name, number, password)
            if result.get('success'):
                success_count += 1
            else:
                fail_list.append(f"{name}({number})")
        
        return jsonify({
            'success': True,
            'added': success_count,
            'failed': len(fail_list),
            'fail_list': fail_list[:10]
        })
    
    @classes_bp.route('/<class_id>/ai-report', methods=['GET'])
    def get_ai_class_report(class_id):
        """获取 AI 生成的班级学情分析报告"""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            import test_library
            result = test_library.generate_ai_class_report(class_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @classes_bp.route('/<class_id>/students/batch-delete', methods=['POST'])
    def batch_delete_students(class_id):
        """批量删除学生"""
        data = request.get_json() or {}
        student_numbers = data.get('student_numbers', [])
        if not student_numbers:
            return jsonify({'success': False, 'error': '没有学生数据'}), 400
        
        result = class_service.delete_students(class_id, student_numbers)
        return jsonify(result)
    
    @classes_bp.route('/<source_class_id>/students/<student_number>/transfer', methods=['POST'])
    def transfer_student(source_class_id, student_number):
        """转班"""
        data = request.get_json() or {}
        target_class_id = data.get('target_class_id', '').strip()
        
        if not target_class_id:
            return jsonify({'success': False, 'error': '目标班级不能为空'}), 400
        
        result = class_service.transfer_student(source_class_id, student_number, target_class_id)
        return jsonify(result)
    
    @classes_bp.route('/<class_id>/students/<student_number>/history', methods=['GET'])
    def get_student_history(class_id, student_number):
        """获取学生历史成绩"""
        try:
            # 获取班级信息
            class_info = class_service.get_class(class_id)
            if not class_info:
                return jsonify({'success': False, 'error': '班级未找到'}), 404
            
            # 获取学生信息
            student = None
            for s in class_info.get('students', []):
                if s.get('student_number') == student_number:
                    student = s
                    break
            
            if not student:
                return jsonify({'success': False, 'error': '学生未找到'}), 404
            
            student_name = student.get('name', '')
            
            # 获取所有考试
            all_exams = exam_service.get_all_exams()
            history = []
            
            for exam in all_exams:
                scores = exam.get('scores', [])
                # 找到该学生的成绩
                student_score = None
                for score in scores:
                    if score.get('student_number') == student_number:
                        student_score = score
                        break
                
                if student_score:
                    # 计算排名
                    sorted_scores = sorted(scores, key=lambda x: x.get('total_score', 0), reverse=True)
                    rank = 1
                    for i, s in enumerate(sorted_scores):
                        if s.get('student_number') == student_number:
                            rank = i + 1
                            break
                    
                    total_students = len(sorted_scores)
                    
                    history.append({
                        'exam_id': exam.get('id'),
                        'exam_name': exam.get('name', ''),
                        'total_score': student_score.get('total_score', 0),
                        'max_score': student_score.get('max_score', 100),
                        'accuracy': student_score.get('accuracy', 0),
                        'rank': rank,
                        'total_students': total_students,
                        'date': exam.get('created_at', '')[:10] if exam.get('created_at') else ''
                    })
            
            # 按日期倒序排列
            history.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            return jsonify({
                'success': True,
                'student_number': student_number,
                'student_name': student_name,
                'history': history
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @classes_bp.route('/compare', methods=['GET'])
    def compare_classes():
        """对比两个班级的成绩"""
        try:
            ids_param = request.args.get('ids', '')
            if not ids_param:
                return jsonify({'success': False, 'error': '需要提供班级ID'}), 400
            
            class_ids = [id.strip() for id in ids_param.split(',')]
            if len(class_ids) != 2:
                return jsonify({'success': False, 'error': '需要提供两个班级ID'}), 400
            
            all_exams = exam_service.get_all_exams()
            result_classes = []
            
            for class_id in class_ids:
                class_info = class_service.get_class(class_id)
                if not class_info:
                    continue
                
                # 获取该班级的所有已完成考试
                class_exams = [e for e in all_exams if e.get('class_id') == class_id and e.get('status') == 'completed']
                
                all_scores = []
                for exam in class_exams:
                    all_scores.extend(exam.get('scores', []))
                
                if not all_scores:
                    result_classes.append({
                        'class_id': class_id,
                        'class_name': class_info.get('name', ''),
                        'statistics': {
                            'average_score': 0,
                            'pass_rate': 0,
                            'highest_score': 0,
                            'lowest_score': 0,
                            'total_students': len(class_info.get('students', []))
                        }
                    })
                    continue
                
                # 计算统计
                total_students = len(all_scores)
                score_values = [s.get('total_score', 0) for s in all_scores]
                avg_score = sum(score_values) / total_students if total_students > 0 else 0
                pass_count = sum(1 for s in all_scores if s.get('accuracy', 0) >= 60)
                pass_rate = pass_count / total_students * 100 if total_students > 0 else 0
                
                result_classes.append({
                    'class_id': class_id,
                    'class_name': class_info.get('name', ''),
                    'statistics': {
                        'average_score': round(avg_score, 2),
                        'pass_rate': round(pass_rate, 2),
                        'highest_score': max(score_values) if score_values else 0,
                        'lowest_score': min(score_values) if score_values else 0,
                        'total_students': total_students
                    }
                })
            
            return jsonify({
                'success': True,
                'classes': result_classes
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return classes_bp
