#!/usr/bin/env python3
"""
测试教师端完整流程的 API 测试脚本
"""
import sys
from pathlib import Path
import uuid

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import json
import test_library

print("=" * 60)
print("教师端完整流程测试")
print("=" * 60)

# ============================================
# 步骤 1: 创建班级
# ============================================
print("\n【步骤 1】创建班级")
print("-" * 60)
class_id = str(uuid.uuid4())
result = test_library.add_class({
    "id": class_id,
    "name": "测试班级 1",
    "grade": "高一",
    "teacher_name": "王老师",
    "students": []
})
print(f"创建班级结果: {result}")
if result:
    print(f"✓ 班级创建成功，班级 ID: {class_id}")
else:
    print("✗ 班级创建失败")
    class_id = None

# ============================================
# 步骤 2: 添加学生
# ============================================
if class_id:
    print("\n【步骤 2】添加学生")
    print("-" * 60)
    students = [
        {"name": "张三", "student_number": "2024001", "password": "123456"},
        {"name": "李四", "student_number": "2024002", "password": "123456"},
        {"name": "王五", "student_number": "2024003", "password": "123456"},
        {"name": "赵六", "student_number": "2024004", "password": "123456"},
        {"name": "钱七", "student_number": "2024005", "password": "123456"},
    ]
    for s in students:
        result = test_library.add_student_to_class(class_id, s)
        status = "✓" if result else "✗"
        print(f"{status} 添加学生 {s['name']}({s['student_number']})")

    # 查看班级学生列表
    class_info = test_library.get_class_by_id(class_id)
    if class_info:
        print(f"\n当前班级学生总数: {len(class_info.get('students', []))}")

# ============================================
# 步骤 3: 创建考试
# ============================================
if class_id:
    print("\n【步骤 3】创建考试")
    print("-" * 60)
    result = test_library.create_exam({
        "name": "单元测试 1",
        "class_id": class_id,
        "grade": "高一",
        "total_score": 100.0,
        "status": "draft",
        "questions": [],
        "scores": []
    })
    print(f"创建考试结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    if result.get('success'):
        exam_id = result.get('exam_id')
        print(f"✓ 考试创建成功，考试 ID: {exam_id}")
    else:
        exam_id = None

# ============================================
# 步骤 4: 批量导入题目
# ============================================
if exam_id:
    print("\n【步骤 4】批量导入题目")
    print("-" * 60)
    questions = [
        {
            "number": 1,
            "content": "1 + 1 = ?",
            "correct_answer": "B",
            "score": 10,
            "type": "choice",
            "knowledge_points": ["基础运算"]
        },
        {
            "number": 2,
            "content": "2 × 3 = ?",
            "correct_answer": "D",
            "score": 10,
            "type": "choice",
            "knowledge_points": ["乘法"]
        },
        {
            "number": 3,
            "content": "5 - 2 = ?",
            "correct_answer": "3",
            "score": 5,
            "type": "fill_blank",
            "knowledge_points": ["减法"]
        },
        {
            "number": 4,
            "content": "计算：10 ÷ 2 = ?",
            "correct_answer": "5",
            "score": 5,
            "type": "fill_blank",
            "knowledge_points": ["除法"]
        },
    ]
    for q in questions:
        result = test_library.add_question_to_exam(exam_id, q)
    print(f"✓ 成功添加 {len(questions)} 道题目")

    # 设置考试为就绪状态
    result = test_library.set_exam_ready(exam_id)
    print(f"设置考试状态为就绪: {'✓' if result else '✗'}")

# ============================================
# 步骤 5: 添加成绩
# ============================================
if exam_id and class_id:
    print("\n【步骤 5】添加学生成绩")
    print("-" * 60)
    
    # 为了测试方便，我们直接操作数据文件添加成绩
    # 先找到考试
    exam = test_library.get_exam_by_id(exam_id)
    if exam:
        scores = [
            {
                "student_number": "2024001",
                "student_name": "张三",
                "score": 90,
                "status": "matched",
                "answers": {1: "B", 2: "D", 3: "3", 4: "5"},
                "question_scores": {1: 10, 2: 10, 3: 5, 4: 5}
            },
            {
                "student_number": "2024002",
                "student_name": "李四",
                "score": 85,
                "status": "matched",
                "answers": {1: "B", 2: "C", 3: "3", 4: "5"},
                "question_scores": {1: 10, 2: 0, 3: 5, 4: 5}
            },
            {
                "student_number": "2024003",
                "student_name": "王五",
                "score": 95,
                "status": "matched",
                "answers": {1: "B", 2: "D", 3: "3", 4: "5"},
                "question_scores": {1: 10, 2: 10, 3: 5, 4: 5}
            },
            {
                "student_number": "2024004",
                "student_name": "赵六",
                "score": 70,
                "status": "matched",
                "answers": {1: "A", 2: "D", 3: "2", 4: "5"},
                "question_scores": {1: 0, 2: 10, 3: 0, 4: 5}
            },
            {
                "student_number": "2024005",
                "student_name": "钱七",
                "score": 88,
                "status": "matched",
                "answers": {1: "B", 2: "D", 3: "3", 4: "4"},
                "question_scores": {1: 10, 2: 10, 3: 5, 4: 0}
            },
        ]
        
        # 保存考试数据
        exams_meta = test_library.load_exams_metadata()
        for e in exams_meta.get('exams', []):
            if e.get('id') == exam_id:
                e['scores'] = scores
                e['status'] = 'reviewing'
                test_library.save_exams_metadata(exams_meta)
                print(f"✓ 成功添加 {len(scores)} 条成绩")
                break

# ============================================
# 步骤 6: 调整成绩（测试备注功能）
# ============================================
if exam_id:
    print("\n【步骤 6】成绩调整备注测试")
    print("-" * 60)
    result = test_library.adjust_score(exam_id, "2024001", 95, "题目难度较高，统一加分")
    print(f"调整成绩结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

    # 查看调整历史
    exam = test_library.get_exam_by_id(exam_id)
    if exam:
        scores = exam.get('scores', [])
        for s in scores:
            if s.get('student_number') == '2024001':
                history = s.get('adjustment_history', [])
                print(f"\n学生 2024001 调整历史: {len(history)} 条记录")
                for h in history:
                    print(f"  - {h.get('timestamp')}: {h.get('old_score')} -> {h.get('new_score')}, 原因: {h.get('reason')}")

# ============================================
# 步骤 7: 完成考试，查看分析
# ============================================
if exam_id:
    print("\n【步骤 7】完成考试并查看分析")
    print("-" * 60)
    result = test_library.confirm_exam_scores(exam_id)
    print(f"完成考试结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

    # 获取分析
    analysis = test_library.get_exam_analysis(exam_id)
    print(f"\n考试分析:")
    print(f"  - 平均分: {analysis.get('average_score')}")
    print(f"  - 最高分: {analysis.get('highest_score')}")
    print(f"  - 最低分: {analysis.get('lowest_score')}")
    print(f"  - 及格率: {analysis.get('pass_rate')}%")

# ============================================
# 步骤 8: 查看班级学情分析
# ============================================
if class_id:
    print("\n【步骤 8】班级学情分析")
    print("-" * 60)
    analysis = test_library.analyze_class_performance(class_id)
    print(f"班级分析:")
    print(f"  - 学生总数: {analysis.get('total_students')}")
    print(f"  - 考试次数: {analysis.get('total_exams')}")


print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
