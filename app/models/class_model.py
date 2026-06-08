"""
班级和学生模型
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.models.base import BaseModel
from app.utils.helpers import generate_id, get_timestamp

class ClassModel(BaseModel):
    """班级数据模型"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        
    def _get_default_data(self) -> Dict[str, Any]:
        """获取默认数据结构"""
        return {
            'classes': [],
            'total_classes': 0,
            'total_students': 0
        }
    
    def get_all_classes(self) -> List[Dict[str, Any]]:
        """获取所有班级"""
        data = self._load()
        return data.get('classes', [])
    
    def get_class_by_id(self, class_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取班级"""
        classes = self.get_all_classes()
        for cls in classes:
            if cls.get('id') == class_id:
                return cls
        return None
    
    def create_class(self, name: str, grade: str = '10-12', teacher_name: str = '') -> Dict[str, Any]:
        """
        创建班级
        
        Args:
            name: 班级名称
            grade: 年级
            teacher_name: 班主任姓名
            
        Returns:
            创建结果，包含class_id
        """
        data = self._load()
        
        new_class = {
            'id': generate_id(),
            'name': name,
            'grade': grade,
            'teacher_name': teacher_name,
            'created_at': get_timestamp(),
            'students': [],
            'assigned_papers': []
        }
        
        data['classes'].append(new_class)
        data['total_classes'] = len(data['classes'])
        self._save()
        
        return {
            'success': True,
            'class_id': new_class['id'],
            'class': new_class
        }
    
    def delete_class(self, class_id: str) -> bool:
        """删除班级"""
        data = self._load()
        original_len = len(data['classes'])
        data['classes'] = [c for c in data['classes'] if c.get('id') != class_id]
        
        if len(data['classes']) < original_len:
            data['total_classes'] = len(data['classes'])
            # 更新学生总数
            data['total_students'] = sum(len(c.get('students', [])) for c in data['classes'])
            self._save()
            return True
        return False
    
    def add_student(self, class_id: str, student_data: Dict[str, Any]) -> bool:
        """
        添加学生到班级
        
        Args:
            class_id: 班级ID
            student_data: 学生信息字典，包含name, student_number, password
            
        Returns:
            是否成功
        """
        data = self._load()
        
        for cls in data['classes']:
            if cls.get('id') == class_id:
                student_number = student_data.get('student_number')
                
                # 检查学号是否已存在
                for student in cls.get('students', []):
                    if student.get('student_number') == student_number:
                        return False
                
                # 添加学生
                new_student = {
                    'id': generate_id(),
                    'name': student_data.get('name', ''),
                    'student_number': student_number,
                    'password': student_data.get('password', student_number),
                    'added_at': get_timestamp(),
                    'scores': []
                }
                
                cls.setdefault('students', []).append(new_student)
                data['total_students'] = data.get('total_students', 0) + 1
                self._save()
                return True
        
        return False
    
    def remove_student(self, class_id: str, student_number: str) -> bool:
        """从班级删除学生"""
        data = self._load()
        
        for cls in data['classes']:
            if cls.get('id') == class_id:
                original_len = len(cls.get('students', []))
                cls['students'] = [s for s in cls.get('students', []) 
                                   if s.get('student_number') != student_number]
                
                if len(cls['students']) < original_len:
                    data['total_students'] = max(0, data.get('total_students', 0) - 1)
                    self._save()
                    return True
        
        return False
    
    def get_student_by_number(self, student_number: str) -> Optional[Dict[str, Any]]:
        """根据学号查找学生"""
        classes = self.get_all_classes()
        for cls in classes:
            for student in cls.get('students', []):
                if student.get('student_number') == student_number:
                    return {
                        **student,
                        'class_id': cls.get('id'),
                        'class_name': cls.get('name')
                    }
        return None
    
    def verify_student_login(self, student_number: str, password: str) -> Optional[Dict[str, Any]]:
        """验证学生登录"""
        student = self.get_student_by_number(student_number)
        if student and student.get('password') == password:
            # 返回不包含密码的信息
            return {
                'id': student.get('id'),
                'name': student.get('name'),
                'student_number': student.get('student_number'),
                'class_name': student.get('class_name')
            }
        return None
    
    def reset_student_password(self, student_number: str, new_password: str) -> Dict[str, Any]:
        """重置学生密码"""
        data = self._load()
        
        for cls in data['classes']:
            for student in cls.get('students', []):
                if student.get('student_number') == student_number:
                    student['password'] = new_password
                    self._save()
                    return {'success': True, 'message': '密码重置成功'}
        
        return {'success': False, 'error': '学生未找到'}
    
    def change_student_password(self, student_number: str, old_password: str, 
                                new_password: str) -> Dict[str, Any]:
        """修改学生密码"""
        data = self._load()
        
        for cls in data['classes']:
            for student in cls.get('students', []):
                if student.get('student_number') == student_number:
                    if student.get('password') == old_password:
                        student['password'] = new_password
                        self._save()
                        return {'success': True, 'message': '密码修改成功'}
                    else:
                        return {'success': False, 'error': '原密码错误'}
        
        return {'success': False, 'error': '学号不存在'}
    
    def delete_students(self, class_id: str, student_numbers: List[str]) -> Dict[str, Any]:
        """批量删除学生"""
        data = self._load()
        
        for cls in data['classes']:
            if cls.get('id') == class_id:
                original_count = len(cls.get('students', []))
                cls['students'] = [s for s in cls.get('students', []) 
                                   if s.get('student_number') not in student_numbers]
                deleted_count = original_count - len(cls['students'])
                
                if deleted_count > 0:
                    data['total_students'] = max(0, data.get('total_students', 0) - deleted_count)
                    self._save()
                    return {'success': True, 'deleted': deleted_count}
        
        return {'success': False, 'error': '班级未找到'}
    
    def transfer_student(self, source_class_id: str, student_number: str, 
                         target_class_id: str) -> Dict[str, Any]:
        """将学生从源班级转到目标班级"""
        if source_class_id == target_class_id:
            return {'success': False, 'error': '源班级和目标班级不能相同'}
        
        data = self._load()
        
        # 找到源班级和学生
        source_class = None
        student = None
        
        for cls in data['classes']:
            if cls.get('id') == source_class_id:
                source_class = cls
                for s in cls.get('students', []):
                    if s.get('student_number') == student_number:
                        student = s
                        break
        
        if not source_class or not student:
            return {'success': False, 'error': '学生未找到'}
        
        # 找到目标班级
        target_class = None
        for cls in data['classes']:
            if cls.get('id') == target_class_id:
                target_class = cls
                break
        
        if not target_class:
            return {'success': False, 'error': '目标班级未找到'}
        
        # 检查目标班级是否已有同名学号学生
        for s in target_class.get('students', []):
            if s.get('student_number') == student_number:
                return {'success': False, 'error': '目标班级已有同名学号学生'}
        
        # 从源班级删除学生
        source_class['students'] = [s for s in source_class.get('students', []) 
                                    if s.get('student_number') != student_number]
        
        # 添加到目标班级
        target_class.setdefault('students', []).append(student)
        
        self._save()
        return {'success': True, 'message': '学生已转入目标班级'}
