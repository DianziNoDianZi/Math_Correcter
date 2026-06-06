# v0.16.0 - AI 智能分析与答题卡扫描增强

## 新功能

### AI 智能分析
- 考试分析页新增 AI 智能分析报告，包含：
  - 总体评价
  - 高频错误分析
  - 薄弱知识点诊断
  - 教学改进建议
- 班级详情页新增 AI 班级学情分析
- 自动识别掌握率低于 50% 的知识点
- 自动分析错误率超过 50% 的题目
- 支持 Markdown 格式报告渲染

### AI 答题卡扫描增强
- 新增 app/services/ai_scan_service.py 模块
- AI 视觉模型自动识别学号
- AI 视觉模型自动识别答案
- 智能降级：AI 不可用时自动回退到文件名提取和空答案
- 新增 ai_scanned 标记，清晰区分 AI 扫描和手动录入的成绩

### 教师端功能优化
- 批量导入学生功能
- 编辑考试功能（增量修改而非删光重建）
- 复制考试功能
- 成绩审核表支持展开查看每题详情
- CSV 导出增加"录入方式"列
- 密码重置改为模态框操作
- 添加学生搜索功能

### 数据模型改进
- 统一字段名：correct_answer、knowledge_points
- add_score 自动将考试状态设置为 reviewing
- 新增考试服务方法：update_question、delete_question、clear_questions、duplicate_exam
- get_exam_statistics 完善统计计算

### 缓存机制
- AI 分析结果缓存，避免重复调用浪费资源
- 成绩数据变更时自动清除相关缓存
- 支持 exam 和 class 两种类型缓存

### 新增 API 路由
- GET /api/exams/{id}/ai-report - 获取 AI 考试分析报告
- GET /api/classes/{id}/ai-report - 获取 AI 班级学情分析报告
- 完善 scan/adjust/analysis 路由（之前缺失）

### 降级处理
- 所有 AI 功能均支持优雅降级
- 无模型配置时自动隐藏 AI 相关区域
- 不影响现有功能使用

## 改进
- 修复 BaseModel 缓存不一致问题
- 修复扫描学号识别错误问题（使用原始文件名）
- 修复准确率计算问题（使用总分而非题数）
- 修复调整总分不更新准确率问题
- 所有 GET 路由添加 model.reload() 解决缓存一致性
- 教师端所有 alert 和 prompt 替换为专业模态框
- 添加 Toast 通知系统和 Loading 遮罩

## 文件变更
- 新增: app/services/ai_analysis_service.py
- 新增: app/services/ai_scan_service.py
- 修改: test_library.py
- 修改: app/models/exam_model.py
- 修改: app/routes/exam_routes.py
- 修改: app/routes/class_routes.py
- 修改: templates/teacher.html
- 修改: README.md