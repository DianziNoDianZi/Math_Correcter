#!/usr/bin/env python3
"""
示例数据生成脚本
用于创建测试用的考试、学生和成绩数据
"""
import sys
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from test_library import (
    create_exam,
    add_exam_score,
    add_class,
    add_student_to_class,
    ensure_student_password
)


def generate_sample_data():
    """生成示例数据"""
    print("开始生成示例数据...")
    
    # 创建班级
    class_result = add_class({
        "name": "高一(1)班",
        "grade": "高一",
        "teacher_name": "张老师"
    })
    
    class_id = None
    if class_result["success"]:
        class_id = class_result["class_id"]
        print(f"✓ 已创建班级: 高一(1)班 (ID: {class_id})")
    else:
        print(f"⚠ 创建班级失败: {class_result.get('error')}，将使用已有班级或继续")
    
    # 创建学生
    students_data = [
        {"name": "小明", "student_number": "2024001", "password": "2024001"},
        {"name": "小红", "student_number": "2024002", "password": "2024002"}
    ]
    
    for student in students_data:
        if class_id:
            result = add_student_to_class(class_id, student)
            if result:
                print(f"✓ 已添加学生: {student['name']} ({student['student_number']})")
            else:
                print(f"⚠ 添加学生失败: {student['name']}")
    
    # 创建几个示例考试
    exams_data = [
        {
            "name": "2024年下学期期中考试",
            "teacher_name": "张老师",
            "class_name": "高一(1)班",
            "subject": "数学",
            "description": "期中测试",
            "questions": [
                {"number": 1, "content": "计算：2 + 3 = ?", "type": "choice", "score": 5, "correct_answer": "5", "knowledge_points": ["加法"]},
                {"number": 2, "content": "计算：10 - 4 = ?", "type": "choice", "score": 5, "correct_answer": "6", "knowledge_points": ["减法"]},
                {"number": 3, "content": "计算：6 × 7 = ?", "type": "choice", "score": 5, "correct_answer": "42", "knowledge_points": ["乘法"]},
                {"number": 4, "content": "计算：36 ÷ 4 = ?", "type": "choice", "score": 5, "correct_answer": "9", "knowledge_points": ["除法"]},
                {"number": 5, "content": "解方程：2x = 10", "type": "fill", "score": 10, "correct_answer": "x=5", "knowledge_points": ["方程"]},
                {"number": 6, "content": "求圆面积，半径为3", "type": "calculation", "score": 15, "correct_answer": "28.26", "knowledge_points": ["几何"]},
            ]
        },
        {
            "name": "2024年下学期单元测验",
            "teacher_name": "李老师",
            "class_name": "高一(1)班",
            "subject": "数学",
            "description": "第三章测试",
            "questions": [
                {"number": 1, "content": "4 + 6 = ?", "type": "choice", "score": 5, "correct_answer": "10", "knowledge_points": ["加法"]},
                {"number": 2, "content": "9 × 8 = ?", "type": "choice", "score": 5, "correct_answer": "72", "knowledge_points": ["乘法"]},
                {"number": 3, "content": "100 ÷ 5 = ?", "type": "choice", "score": 5, "correct_answer": "20", "knowledge_points": ["除法"]},
            ]
        }
    ]
    
    created_exams = []
    for exam_data in exams_data:
        result = create_exam(exam_data)
        if result["success"]:
            created_exams.append(result["exam_id"])
            print(f"✓ 已创建考试: {exam_data['name']} (ID: {result['exam_id']})")
        else:
            print(f"✗ 创建考试失败: {result.get('error')}")
    
    if not created_exams:
        print("没有成功创建任何考试")
        return
    
    # 创建几个示例学生成绩
    exam_scores = [
        {
            "student_number": "2024001",
            "student_name": "小明",
            "exam_id": created_exams[0],
            "question_scores": [
                {"question_number": 1, "student_answer": "5", "is_correct": True, "score": 5},
                {"question_number": 2, "student_answer": "5", "is_correct": False, "score": 0},
                {"question_number": 3, "student_answer": "42", "is_correct": True, "score": 5},
                {"question_number": 4, "student_answer": "8", "is_correct": False, "score": 0},
                {"question_number": 5, "student_answer": "x=6", "is_correct": False, "score": 0},
                {"question_number": 6, "student_answer": "28", "is_correct": False, "score": 0},
            ]
        },
        {
            "student_number": "2024001",
            "student_name": "小明",
            "exam_id": created_exams[1],
            "question_scores": [
                {"question_number": 1, "student_answer": "10", "is_correct": True, "score": 5},
                {"question_number": 2, "student_answer": "70", "is_correct": False, "score": 0},
                {"question_number": 3, "student_answer": "20", "is_correct": True, "score": 5},
            ]
        },
        {
            "student_number": "2024002",
            "student_name": "小红",
            "exam_id": created_exams[0],
            "question_scores": [
                {"question_number": 1, "student_answer": "5", "is_correct": True, "score": 5},
                {"question_number": 2, "student_answer": "6", "is_correct": True, "score": 5},
                {"question_number": 3, "student_answer": "40", "is_correct": False, "score": 0},
                {"question_number": 4, "student_answer": "9", "is_correct": True, "score": 5},
                {"question_number": 5, "student_answer": "x=5", "is_correct": True, "score": 10},
                {"question_number": 6, "student_answer": "28.26", "is_correct": True, "score": 15},
            ]
        }
    ]
    
    # 添加考试成绩并确保学生账号存在
    for score_data in exam_scores:
        result = add_exam_score(
            exam_id=score_data["exam_id"],
            score_data={
                "student_number": score_data["student_number"],
                "student_name": score_data["student_name"],
                "question_scores": score_data["question_scores"]
            }
        )
        if result["success"]:
            print(f"✓ 已添加 {score_data['student_name']} 的成绩到考试 {score_data['exam_id']}")
        else:
            print(f"✗ 添加成绩失败: {result.get('error')}")
    
    # 确保所有有成绩的学生都有账号（兼容处理）
    for exam_id in created_exams:
        from test_library import get_exam_by_id
        exam = get_exam_by_id(exam_id)
        if exam:
            ensure_student_password(exam)
    
    print("\n示例数据生成完成！")
    print(f"共创建 {len(created_exams)} 个考试")
    print(f"共添加 2 名学生的成绩")
    print("\n你现在可以:")
    print("1. 运行 python server.py 启动服务器")
    print("2. 访问 http://localhost:8000 查看功能")
    print("3. 使用学生账号 2024001/2024001 或 2024002/2024002 登录学生端")


if __name__ == "__main__":
    generate_sample_data()
