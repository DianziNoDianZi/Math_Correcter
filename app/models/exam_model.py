"""
考试数据模型
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.models.base import BaseModel
from app.utils.helpers import generate_id, get_timestamp

class ExamModel(BaseModel):
    """考试数据模型"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        
    def _get_default_data(self) -> Dict[str, Any]:
        """获取默认数据结构"""
        return {
            'exams': [],
            'total_exams': 0
        }
    
    def get_all_exams(self) -> List[Dict[str, Any]]:
        """获取所有考试"""
        data = self._load()
        return data.get('exams', [])
    
    def get_exam_by_id(self, exam_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取考试"""
        exams = self.get_all_exams()
        for exam in exams:
            if exam.get('id') == exam_id:
                return exam
        return None
    
    def create_exam(self, exam_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建考试
        
        Args:
            exam_data: 考试信息字典
            
        Returns:
            创建结果，包含exam_id
        """
        data = self._load()
        
        exam_id = generate_id()
        new_exam = {
            'id': exam_id,
            'name': exam_data.get('name', '未命名考试'),
            'class_id': exam_data.get('class_id'),
            'grade': exam_data.get('grade'),
            'total_score': float(exam_data.get('total_score', 100)),
            'created_at': get_timestamp(),
            'status': 'draft',  # draft:草稿, ready:就绪, scanning:扫描中, reviewing:待审核, completed:已完成
            'questions': [],
            'scores': [],
            'statistics': {}
        }
        
        data['exams'].append(new_exam)
        data['total_exams'] = len(data['exams'])
        self._save()
        
        return {
            'success': True,
            'exam_id': exam_id
        }
    
    def delete_exam(self, exam_id: str) -> bool:
        """删除考试"""
        data = self._load()
        original_len = len(data['exams'])
        data['exams'] = [e for e in data['exams'] if e.get('id') != exam_id]
        
        if len(data['exams']) < original_len:
            data['total_exams'] = len(data['exams'])
            self._save()
            return True
        return False
    
    def add_question(self, exam_id: str, question_data: Dict[str, Any]) -> bool:
        """添加题目到考试"""
        data = self._load()
        
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                question = {
                    'number': question_data.get('number'),
                    'content': question_data.get('content', ''),
                    'correct_answer': question_data.get('correct_answer', ''),
                    'score': question_data.get('score', 5),
                    'knowledge_points': question_data.get('knowledge_points', []),
                    'type': question_data.get('type', 'choice')  # choice, fill, calculation
                }
                exam.setdefault('questions', []).append(question)
                self._save()
                return True
        return False
    
    def set_exam_ready(self, exam_id: str) -> bool:
        """设置考试为就绪状态"""
        data = self._load()
        
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                if not exam.get('questions'):
                    return False
                exam['status'] = 'ready'
                self._save()
                return True
        return False
    
    def update_question(self, exam_id: str, question_number: int, question_data: Dict[str, Any]) -> bool:
        """更新某道题目"""
        data = self._load()
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                for q in exam.get('questions', []):
                    if q.get('number') == question_number:
                        q['correct_answer'] = question_data.get('correct_answer', q.get('correct_answer', ''))
                        q['score'] = question_data.get('score', q.get('score', 5))
                        q['knowledge_points'] = question_data.get('knowledge_points', q.get('knowledge_points', []))
                        q['type'] = question_data.get('type', q.get('type', 'choice'))
                        self._save()
                        return True
        return False
    
    def delete_question(self, exam_id: str, question_number: int) -> bool:
        """删除某道题目"""
        data = self._load()
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                exam['questions'] = [q for q in exam.get('questions', []) if q.get('number') != question_number]
                self._save()
                return True
        return False
    
    def clear_questions(self, exam_id: str) -> bool:
        """清空所有题目"""
        data = self._load()
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                exam['questions'] = []
                exam['status'] = 'draft'
                self._save()
                return True
        return False
    
    def duplicate_exam(self, exam_id: str, new_name: str = '') -> Optional[Dict[str, Any]]:
        """复制考试"""
        data = self._load()
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                import copy
                new_exam = copy.deepcopy(exam)
                new_exam['id'] = generate_id()
                new_exam['name'] = new_name or f"{exam.get('name', '')} (副本)"
                new_exam['status'] = 'draft'
                new_exam['scores'] = []
                new_exam['statistics'] = {}
                new_exam['created_at'] = get_timestamp()
                data['exams'].append(new_exam)
                data['total_exams'] = len(data['exams'])
                self._save()
                return new_exam
        return None
    
    def add_score(self, exam_id: str, score_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加考试成绩
        
        Args:
            exam_id: 考试ID
            score_data: 成绩数据
            
        Returns:
            添加结果
        """
        data = self._load()
        
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                # 计算总分和正确率
                results = score_data.get('results', [])
                total_score = sum(r.get('score', 0) for r in results)
                total_max_score = sum(q.get('score', 0) for q in exam.get('questions', []))
                
                if not total_max_score:
                    total_max_score = exam.get('total_score', 100)
                
                correct_count = sum(1 for r in results if r.get('is_correct', False))
                accuracy = (total_score / total_max_score * 100) if total_max_score > 0 else 0
                
                new_score = {
                    'student_number': score_data.get('student_number'),
                    'student_name': score_data.get('student_name', ''),
                    'total_score': total_score,
                    'max_score': total_max_score,
                    'accuracy': accuracy,
                    'results': results,
                    'confirmed': False,
                    'created_at': get_timestamp()
                }
                
                # 检查是否已存在该学生成绩
                for i, existing_score in enumerate(exam.get('scores', [])):
                    if existing_score.get('student_number') == score_data.get('student_number'):
                        exam['scores'][i] = new_score
                        self._save()
                        return {'success': True, 'updated': True}
                
                exam.setdefault('scores', []).append(new_score)
                # 手动录入成绩后自动将考试状态改为reviewing
                if exam.get('status') in ['ready', 'draft']:
                    exam['status'] = 'reviewing'
                self._save()
                return {'success': True, 'updated': False}
        
        return {'success': False, 'error': '考试未找到'}
    
    def confirm_scores(self, exam_id: str) -> bool:
        """确认考试成绩"""
        data = self._load()
        
        for exam in data['exams']:
            if exam.get('id') == exam_id:
                for score in exam.get('scores', []):
                    score['confirmed'] = True
                exam['status'] = 'completed'
                self._save()
                return True
        return False
    
    def get_scores_by_student(self, student_number: str) -> List[Dict[str, Any]]:
        """获取某个学生的所有成绩"""
        exams = self.get_all_exams()
        scores = []
        
        for exam in exams:
            for score in exam.get('scores', []):
                if score.get('student_number') == student_number and score.get('confirmed'):
                    scores.append({
                        'exam_id': exam.get('id'),
                        'exam_name': exam.get('name'),
                        'score': score.get('total_score'),
                        'max_score': score.get('max_score'),
                        'accuracy': score.get('accuracy'),
                        'created_at': exam.get('created_at')
                    })
        
        return scores
    
    def get_wrong_questions(self, student_number: str) -> List[Dict[str, Any]]:
        """获取某个学生的错题"""
        exams = self.get_all_exams()
        wrong_questions = []
        
        for exam in exams:
            if exam.get('status') != 'completed':
                continue
                
            for score in exam.get('scores', []):
                if score.get('student_number') != student_number:
                    continue
                    
                results = score.get('results', [])
                questions = exam.get('questions', [])
                
                for result in results:
                    if not result.get('is_correct', True):
                        question_number = result.get('number')
                        # 找到对应的题目
                        question = next((q for q in questions if q.get('number') == question_number), None)
                        
                        if question:
                            wrong_questions.append({
                                'exam_id': exam.get('id'),
                                'exam_name': exam.get('name'),
                                'question_number': question_number,
                                'question_content': question.get('content', ''),
                                'correct_answer': question.get('correct_answer', ''),
                                'student_answer': result.get('student_answer', ''),
                                'knowledge_points': question.get('knowledge_points', []),
                                'score': result.get('score', 0),
                                'max_score': question.get('score', 5),
                                'created_at': exam.get('created_at')
                            })
        
        return wrong_questions
