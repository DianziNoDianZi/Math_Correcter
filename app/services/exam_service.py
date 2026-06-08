"""
考试服务
"""
from typing import Dict, Any, List, Optional
from app.models import ExamModel
from pathlib import Path

class ExamService:
    """考试服务类"""
    
    def __init__(self, data_dir: Path):
        self.model = ExamModel(data_dir)
    
    def get_all_exams(self) -> List[Dict[str, Any]]:
        """获取所有考试"""
        return self.model.get_all_exams()
    
    def get_exam(self, exam_id: str) -> Optional[Dict[str, Any]]:
        """获取单个考试"""
        return self.model.get_exam_by_id(exam_id)
    
    def create_exam(self, name: str, class_id: str = '', 
                   total_score: float = 100, grade: str = '') -> Dict[str, Any]:
        """创建考试"""
        if not name:
            return {'success': False, 'error': '考试名称不能为空'}
        
        exam_data = {
            'name': name,
            'class_id': class_id,
            'total_score': total_score,
            'grade': grade
        }
        
        result = self.model.create_exam(exam_data)
        return result
    
    def delete_exam(self, exam_id: str) -> Dict[str, Any]:
        """删除考试"""
        if self.model.delete_exam(exam_id):
            return {'success': True}
        return {'success': False, 'error': '考试未找到'}
    
    def add_question(self, exam_id: str, number: int, content: str,
                    correct_answer: str, score: float = 5,
                    knowledge_points: list = None,
                    question_type: str = 'choice') -> Dict[str, Any]:
        """添加题目"""
        if knowledge_points is None:
            knowledge_points = []
        question_data = {
            'number': number,
            'content': content,
            'correct_answer': correct_answer,
            'score': score,
            'knowledge_points': knowledge_points,
            'type': question_type
        }
        
        if self.model.add_question(exam_id, question_data):
            return {'success': True}
        return {'success': False, 'error': '考试未找到'}
    
    def set_ready(self, exam_id: str) -> Dict[str, Any]:
        """设置考试为就绪状态"""
        if self.model.set_exam_ready(exam_id):
            return {'success': True}
        return {'success': False, 'error': '考试未找到或无题目'}
    
    def update_question(self, exam_id: str, question_number: int,
                       question_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新题目"""
        if self.model.update_question(exam_id, question_number, question_data):
            return {'success': True}
        return {'success': False, 'error': '考试或题目未找到'}
    
    def delete_question(self, exam_id: str, question_number: int) -> Dict[str, Any]:
        """删除题目"""
        if self.model.delete_question(exam_id, question_number):
            return {'success': True}
        return {'success': False, 'error': '考试或题目未找到'}
    
    def clear_questions(self, exam_id: str) -> Dict[str, Any]:
        """清空所有题目"""
        if self.model.clear_questions(exam_id):
            return {'success': True}
        return {'success': False, 'error': '考试未找到'}
    
    def duplicate_exam(self, exam_id: str, new_name: str = '') -> Dict[str, Any]:
        """复制考试"""
        new_exam = self.model.duplicate_exam(exam_id, new_name)
        if new_exam:
            return {'success': True, 'exam': new_exam}
        return {'success': False, 'error': '考试未找到'}
    
    def add_score(self, exam_id: str, student_number: str, student_name: str,
                 results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """添加成绩"""
        score_data = {
            'student_number': student_number,
            'student_name': student_name,
            'results': results
        }
        
        return self.model.add_score(exam_id, score_data)
    
    def confirm_scores(self, exam_id: str) -> Dict[str, Any]:
        """确认成绩"""
        if self.model.confirm_scores(exam_id):
            return {'success': True}
        return {'success': False, 'error': '考试未找到'}
    
    def get_student_scores(self, student_number: str) -> List[Dict[str, Any]]:
        """获取学生所有成绩"""
        return self.model.get_scores_by_student(student_number)
    
    def get_wrong_questions(self, student_number: str) -> List[Dict[str, Any]]:
        """获取学生错题"""
        return self.model.get_wrong_questions(student_number)
    
    def get_exam_statistics(self, exam_id: str) -> Dict[str, Any]:
        """获取考试统计信息"""
        exam = self.get_exam(exam_id)
        if not exam:
            return {'success': False, 'error': '考试未找到'}
        
        scores = exam.get('scores', [])
        if not scores:
            return {
                'success': True,
                'statistics': {
                    'total_students': 0,
                    'average_score': 0,
                    'pass_rate': 0,
                    'excellent_rate': 0
                }
            }
        
        # 计算统计数据
        total = len(scores)
        score_values = [s.get('total_score', 0) for s in scores]
        avg_score = sum(score_values) / total
        pass_count = sum(1 for s in scores if s.get('accuracy', 0) >= 0.6)
        excellent_count = sum(1 for s in scores if s.get('accuracy', 0) >= 0.9)
        
        return {
            'success': True,
            'statistics': {
                'total_students': total,
                'average_score': round(avg_score, 2),
                'pass_rate': round(pass_count / total * 100, 2),
                'excellent_rate': round(excellent_count / total * 100, 2),
                'max_score': max(score_values) if score_values else 0,
                'min_score': min(score_values) if score_values else 0
            }
        }
    
    def _validate_question(self, question: Dict[str, Any]) -> Optional[str]:
        """验证题目格式，返回错误信息或None"""
        # 验证题号
        number = question.get('number')
        if number is None:
            return '题号不能为空'
        try:
            number = int(number)
            if number <= 0:
                return '题号必须是正整数'
        except (ValueError, TypeError):
            return '题号必须是正整数'
        
        # 验证内容
        content = question.get('content', '').strip()
        if not content:
            return '题目内容不能为空'
        
        # 验证类型
        valid_types = ['choice', 'true_false', 'fill_blank', 'subjective']
        question_type = question.get('type', '').strip()
        if question_type not in valid_types:
            return f'题型必须是以下之一: {", ".join(valid_types)}'
        
        # 验证分值
        score = question.get('score')
        if score is None:
            return '分值不能为空'
        try:
            score = float(score)
            if score <= 0:
                return '分值必须是正数'
        except (ValueError, TypeError):
            return '分值必须是正数'
        
        # 验证正确答案
        correct_answer = question.get('correct_answer', '').strip()
        if not correct_answer:
            return '正确答案不能为空'
        
        # 根据类型验证答案格式
        if question_type == 'choice':
            if correct_answer.upper() not in ['A', 'B', 'C', 'D']:
                return '选择题正确答案必须是 A/B/C/D'
        elif question_type == 'true_false':
            if correct_answer not in ['对', '错']:
                return '判断题正确答案必须是 对/错'
        
        return None
    
    def batch_import_questions(self, exam_id: str, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量导入题目
        
        Args:
            exam_id: 考试ID
            questions: 题目列表
            
        Returns:
            导入结果，包含added_count, failed_count, errors
        """
        if not self.model.get_exam_by_id(exam_id):
            return {'success': False, 'error': '考试未找到'}
        
        if not questions:
            return {'success': False, 'error': '没有要导入的题目'}
        
        added_count = 0
        failed_count = 0
        errors = []
        
        for i, q in enumerate(questions):
            # 验证题目
            error = self._validate_question(q)
            if error:
                failed_count += 1
                errors.append({
                    'index': i,
                    'number': q.get('number'),
                    'error': error
                })
                continue
            
            # 添加题目
            number = int(q['number'])
            content = q['content'].strip()
            correct_answer = q['correct_answer'].strip()
            score = float(q['score'])
            knowledge_points = q.get('knowledge_points', [])
            question_type = q.get('type', 'choice').strip()
            
            if self.model.add_question(exam_id, {
                'number': number,
                'content': content,
                'correct_answer': correct_answer,
                'score': score,
                'knowledge_points': knowledge_points,
                'type': question_type
            }):
                added_count += 1
            else:
                failed_count += 1
                errors.append({
                    'index': i,
                    'number': number,
                    'error': '添加失败'
                })
        
        return {
            'success': True,
            'added_count': added_count,
            'failed_count': failed_count,
            'errors': errors
        }
