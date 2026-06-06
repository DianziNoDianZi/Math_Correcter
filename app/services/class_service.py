"""
班级和学生服务
"""
from typing import Dict, Any, List, Optional
from app.models import ClassModel
from pathlib import Path

class ClassService:
    """班级和学生服务类"""
    
    def __init__(self, data_dir: Path):
        self.model = ClassModel(data_dir)
    
    def get_all_classes(self) -> List[Dict[str, Any]]:
        """获取所有班级"""
        return self.model.get_all_classes()
    
    def get_class(self, class_id: str) -> Optional[Dict[str, Any]]:
        """获取单个班级"""
        return self.model.get_class_by_id(class_id)
    
    def create_class(self, name: str, grade: str = '10-12', 
                    teacher_name: str = '') -> Dict[str, Any]:
        """创建班级"""
        if not name:
            return {'success': False, 'error': '班级名称不能为空'}
        return self.model.create_class(name, grade, teacher_name)
    
    def delete_class(self, class_id: str) -> Dict[str, Any]:
        """删除班级"""
        if self.model.delete_class(class_id):
            return {'success': True}
        return {'success': False, 'error': '班级未找到'}
    
    def add_student(self, class_id: str, name: str, student_number: str,
                   password: str = '') -> Dict[str, Any]:
        """添加学生"""
        if not name or not student_number:
            return {'success': False, 'error': '姓名和学号不能为空'}
        
        # 如果没有设置密码，默认使用学号
        if not password:
            password = student_number
        
        student_data = {
            'name': name,
            'student_number': student_number,
            'password': password
        }
        
        if self.model.add_student(class_id, student_data):
            return {'success': True}
        return {'success': False, 'error': '添加失败，学号可能已存在'}
    
    def remove_student(self, class_id: str, student_number: str) -> Dict[str, Any]:
        """删除学生"""
        if self.model.remove_student(class_id, student_number):
            return {'success': True}
        return {'success': False, 'error': '学生未找到'}
    
    def verify_student(self, student_number: str, password: str) -> Optional[Dict[str, Any]]:
        """验证学生登录"""
        return self.model.verify_student_login(student_number, password)
    
    def reset_password(self, student_number: str, new_password: str) -> Dict[str, Any]:
        """重置密码"""
        return self.model.reset_student_password(student_number, new_password)
    
    def change_password(self, student_number: str, old_password: str,
                       new_password: str) -> Dict[str, Any]:
        """修改密码"""
        return self.model.change_student_password(student_number, old_password, new_password)
    
    def get_student(self, student_number: str) -> Optional[Dict[str, Any]]:
        """获取学生信息"""
        return self.model.get_student_by_number(student_number)
