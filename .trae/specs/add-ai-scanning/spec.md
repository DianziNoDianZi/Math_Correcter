# AI答题卡扫描 Spec

## Why
当前 `test_library.py` 中的 `detect_student_number` 仅从文件名提取学号，`detect_answers` 返回空字符串。项目已有完整的 AI 模型配置和调用基础设施（`config.py` / `processor.py` / `call_llm_api`），但答题卡扫描流程完全没有接入 AI 视觉识别能力。

## What Changes
- 将 `detect_student_number` 升级为支持 AI 视觉识别学号
- 将 `detect_answers` 升级为支持 AI 视觉识别答案
- 复用已有的 `config.py` 模型配置系统，读取 `vision_model` 配置
- 复用已有的 `processor.call_llm_api` 进行 API 调用
- AI 不可用时优雅降级回当前行为（文件名提取/留空）
- 扫描过程中显示 AI 识别进度
- **BREAKING**: 无，所有改动向后兼容

## Impact
- Affected specs: 无现有 spec
- Affected code: `test_library.py`, `processor.py`（复用）, `config.py`（复用）
- 新增文件: 无（在现有模块中增强）

## ADDED Requirements

### Requirement: AI 学号识别
系统 SHALL 支持使用配置的视觉模型从答题卡图片中识别学生学号。

#### Scenario: 视觉模型已配置
- **WHEN** 教师上传答题卡图片进行扫描
- **AND** `config.yaml` 中已配置 `vision_model`
- **THEN** 系统调用视觉模型识别图片中的学号
- **AND** 返回识别结果作为 `student_number`

#### Scenario: 视觉模型未配置
- **WHEN** 教师上传答题卡图片进行扫描
- **AND** `config.yaml` 中 `vision_model` 为空或模型不可用
- **THEN** 系统降级为从文件名提取学号
- **AND** 扫描继续进行不中断

#### Scenario: AI 识别失败
- **WHEN** AI 调用返回异常（超时、API 错误等）
- **THEN** 系统记录错误日志
- **AND** 降级为从文件名提取学号
- **AND** 扫描继续进行不中断

### Requirement: AI 答案识别
系统 SHALL 支持使用配置的视觉模型从答题卡图片中识别学生填涂的答案。

#### Scenario: 选择题答案识别
- **WHEN** 教师上传选择题答题卡图片
- **AND** 视觉模型已配置
- **THEN** 系统调用视觉模型识别每道选择题的填涂答案
- **AND** 返回如 `{"1": "A", "2": "B", "3": "C"}` 格式的答案映射

#### Scenario: 填空题答案识别
- **WHEN** 教师上传填空题答题卡图片
- **AND** 视觉模型已配置
- **THEN** 系统调用视觉模型识别每道填空题的手写答案
- **AND** 返回识别到的文本内容

#### Scenario: AI 不可用时降级
- **WHEN** 视觉模型未配置或 AI 调用失败
- **THEN** 系统返回空答案（所有题目留空）
- **AND** 教师在审核页手动批改
- **AND** 与当前行为一致

### Requirement: AI 答案自动比对
系统 SHALL 在识别到答案后自动与正确答案比对并计算得分。

#### Scenario: 答案自动比对
- **WHEN** AI 成功识别了学生答案
- **THEN** 系统将识别答案与标准答案比对
- **AND** 为每道题标记 `is_correct`
- **AND** 计算 `total_score` 和 `accuracy`
- **AND** 选择题和判断题做精确匹配，填空题做模糊匹配

#### Scenario: 主观题处理
- **WHEN** 题目类型为主观题
- **THEN** 系统不进行自动比对
- **AND** 标记 `is_correct: null`（待教师审核）
- **AND** 主观题得分默认为 0

### Requirement: AI 扫描结果标记
系统 SHALL 标记成绩数据的识别来源，便于教师区分 AI 识别和手动录入。

#### Scenario: AI 识别标记
- **WHEN** 成绩通过 AI 扫描产生
- **THEN** 成绩数据中包含 `ai_scanned: true` 标记
- **AND** `ai_confidence` 字段包含模型返回的置信度（如有）

#### Scenario: 手动录入标记
- **WHEN** 成绩通过手动录入
- **THEN** 成绩数据中 `ai_scanned: false`