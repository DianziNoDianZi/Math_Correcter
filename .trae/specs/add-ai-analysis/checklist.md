# Checklist

- [x] `app/services/ai_analysis_service.py` 文件存在且可导入
- [x] `ai_analysis_service.py` 能正确读取 `config.yaml` 中的 `text_model` 配置
- [x] AI 可用时 `generate_exam_analysis` 返回结构化 Markdown 分析报告
- [x] AI 不可用时 `generate_exam_analysis` 返回 `None`
- [x] AI 可用时 `generate_class_report` 返回班级学情分析报告
- [x] AI 不可用时 `generate_class_report` 返回 `None`
- [x] 分析结果缓存机制正常工作（写入、读取、失效）
- [x] 成绩数据变更时缓存被正确清除
- [x] `GET /api/exams/<exam_id>/ai-report` 返回 `ai_report` 字段
- [x] `GET /api/classes/<class_id>/ai-report` 返回 `ai_report` 字段
- [x] teacher.html 学情分析区展示 AI 报告卡片（含 loading 状态）
- [x] teacher.html AI 不可用时隐藏报告区域
- [x] teacher.html 班级详情有 AI 分析按钮且功能正常
- [x] 现有分析功能（统计图表）不受影响
- [x] 完整端到端流程（创建考试 -> 录入成绩 -> 查看分析 -> AI 报告）可正常运行