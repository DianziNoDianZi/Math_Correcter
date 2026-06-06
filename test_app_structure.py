"""
模块化架构测试脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试1: 模块导入")
    print("=" * 60)
    
    try:
        from app import create_app
        print("✓ app.create_app")
    except Exception as e:
        print(f"✗ app.create_app: {e}")
    
    try:
        from app.config import Config
        print("✓ app.config.Config")
    except Exception as e:
        print(f"✗ app.config.Config: {e}")
    
    try:
        from app.models import ClassModel, ExamModel
        print("✓ app.models")
    except Exception as e:
        print(f"✗ app.models: {e}")
    
    try:
        from app.services import ClassService, ExamService
        print("✓ app.services")
    except Exception as e:
        print(f"✗ app.services: {e}")
    
    try:
        from app.utils import generate_id, validate_student_number
        print("✓ app.utils")
    except Exception as e:
        print(f"✗ app.utils: {e}")
    
    try:
        from app.routes import register_blueprints
        print("✓ app.routes")
    except Exception as e:
        print(f"✗ app.routes: {e}")

def test_config():
    """测试配置"""
    print("\n" + "=" * 60)
    print("测试2: 配置管理")
    print("=" * 60)
    
    try:
        from app.config import Config
        
        Config.init_app()
        print("✓ 配置初始化")
        
        print(f"✓ 数据目录: {Config.DATA_DIR}")
        print(f"✓ 日志目录: {Config.LOGS_DIR}")
        print(f"✓ 上传目录: {Config.UPLOAD_FOLDER}")
        
    except Exception as e:
        print(f"✗ 配置测试失败: {e}")

def test_helpers():
    """测试工具函数"""
    print("\n" + "=" * 60)
    print("测试3: 工具函数")
    print("=" * 60)
    
    try:
        from app.utils import generate_id, validate_student_number, format_score
        
        # 测试生成ID
        test_id = generate_id()
        print(f"✓ 生成唯一ID: {test_id}")
        
        # 测试学号验证
        assert validate_student_number("2024001") == True
        print("✓ 学号验证 (有效): 2024001")
        
        assert validate_student_number("123") == False
        print("✓ 学号验证 (无效): 123")
        
        # 测试分数格式化
        score_info = format_score(85, 100)
        print(f"✓ 分数格式化: 85/100 = {score_info['grade']} ({score_info['level']})")
        
    except Exception as e:
        print(f"✗ 工具函数测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_directory_structure():
    """测试目录结构"""
    print("\n" + "=" * 60)
    print("测试4: 目录结构")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    app_dir = base_dir / 'app'
    
    # 检查app目录结构
    required_dirs = [
        'app',
        'app/models',
        'app/services',
        'app/routes',
        'app/utils',
        'templates',
        'data'
    ]
    
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/ (不存在)")

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("Math_Correcter 模块化架构测试")
    print("=" * 60 + "\n")
    
    test_imports()
    test_config()
    test_helpers()
    test_directory_structure()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60 + "\n")
    
    print("要运行完整的应用测试，请确保已安装所有依赖：")
    print("pip install flask flask-cors requests Pillow pyyaml")
    print("\n然后运行：")
    print("python app_main.py")

if __name__ == '__main__':
    main()
