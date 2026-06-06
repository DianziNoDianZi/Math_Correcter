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
