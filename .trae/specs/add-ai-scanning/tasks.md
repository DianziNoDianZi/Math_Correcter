# Tasks

- [x] Task 1: 创建 AI 扫描服务模块 `app/services/ai_scan_service.py`
  - 封装从 config.yaml 读取 vision_model 配置的逻辑
  - 封装调用 `processor.call_llm_api` 进行学号识别的逻辑
  - 封装调用 `processor.call_llm_api` 进行答案识别的逻辑
  - 实现优雅降级：AI 不可用时回退到文件名提取和留空
  - **验证**: 单独运行测试，模拟 AI 可用和不可用两种场景

- [x] Task 2: 修改 `test_library.py` 的 `detect_student_number` 和 `detect_answers`
  - `detect_student_number` 增加 AI 视觉识别分支，失败时降级到文件名提取
  - `detect_answers` 增加 AI 视觉识别分支，失败时降级到返回空答案
  - 传入考试题目信息用于构造识别 prompt
  - **验证**: 修改后现有扫描流程测试不受影响

- [x] Task 3: 在成绩数据中添加 AI 识别标记
  - `scan_answer_sheet` 返回结果中添加 `ai_scanned` 标记
  - `batch_scan_answer_sheets` 的 score 数据传递该标记
  - **验证**: 扫描后的成绩数据包含 `ai_scanned` 字段

- [x] Task 4: 前端审核页展示 AI 识别状态
  - 在 teacher.html 审核表格中显示 AI 识别 vs 手动录入标记
  - 如果某题由 AI 识别但置信度低，给出视觉提示
  - 未匹配学生行的文件名学号回显提示
  - **验证**: 打开审核页面能看到 AI 识别状态标记

- [x] Task 5: 端到端测试
  - 创建考试 -> 添加题目 -> 上传答题卡 -> 验证 AI 扫描结果 -> 调整成绩
  - 测试 AI 未配置时降级行为
  - 测试成绩数据结构完整性
  - **验证**: 完整流程无错误

# Task Dependencies
- Task 2 依赖 Task 1（AI 服务模块需要先创建）
- Task 3 依赖 Task 2（标记需在扫描函数中增加）
- Task 4 依赖 Task 3（前端需要后端返回标记数据）
- Task 5 依赖 Task 1-4 全部完成