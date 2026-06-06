"""
路由注册
"""
from pathlib import Path
from app.routes.student_routes import init_student_routes
from app.routes.class_routes import init_class_routes
from app.routes.exam_routes import init_exam_routes
from app.routes.student_management_routes import init_student_management_routes

def register_blueprints(app):
    """
    注册所有蓝图
    
    Args:
        app: Flask应用实例
    """
    # 创建服务实例
    from app.services import ClassService, ExamService
    
    data_dir = Path(__file__).parent.parent / 'data'
    class_service = ClassService(data_dir)
    exam_service = ExamService(data_dir)
    
    # 注册蓝图
    student_bp = init_student_routes(class_service, exam_service)
    app.register_blueprint(student_bp)
    
    classes_bp = init_class_routes(class_service)
    app.register_blueprint(classes_bp)
    
    exams_bp = init_exam_routes(exam_service)
    app.register_blueprint(exams_bp)
    
    students_bp = init_student_management_routes(class_service)
    app.register_blueprint(students_bp)
    
    # 将服务实例存储在app中供其他模块使用
    app.class_service = class_service
    app.exam_service = exam_service
