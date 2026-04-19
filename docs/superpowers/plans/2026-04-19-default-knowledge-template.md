# 默认知识库样板实施计划

> **给执行型 agent 的说明：** 实施本计划时，必须使用 `superpowers:executing-plans`，并按任务顺序落实。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 为每个用户提供一套开箱即用的默认知识库样板。新创建用户自动生成，现有用户支持一次性补发；整个能力完全复用现有知识库、文件、文本入库和向量化链路，不新增新的产品模块。

**架构：** 将“默认样板内容定义”与“默认知识库初始化逻辑”拆开实现。模板定义集中在一个后端模块中；初始化服务负责幂等判断、创建知识库、写入 5 篇默认文本模板、触发现有入库/向量化链路；路由层只负责在合适时机调用初始化服务，以及提供管理员补发入口。

**技术栈：** Python、FastAPI、SQLAlchemy、现有 `Knowledges` / `Files` / `process_file()` 链路、pytest

---

## 文件地图

- 新建：`backend/open_webui/utils/default_knowledge_templates.py`
  - 维护默认知识库名称、描述、版本号，以及 5 篇模板的标题、key 和正文
- 新建：`backend/open_webui/utils/default_knowledge_initializer.py`
  - 负责默认知识库幂等初始化、单用户补发、全量用户补发
- 修改：`backend/open_webui/routers/auths.py`
  - 在用户注册、管理员创建用户后接入默认知识库初始化
- 修改：`backend/open_webui/routers/users.py`
  - 增加管理员补发现有用户默认知识库样板的入口
- 新建：`tests/test_default_knowledge_initializer.py`
  - 覆盖模板定义、幂等初始化、回填逻辑
- 修改：`tests/test_auth_usernames.py`
  - 补充用户创建后触发默认知识库初始化的测试

## 任务 1：先补红灯测试，锁定默认样板行为

**文件：**
- 新建：`tests/test_default_knowledge_initializer.py`
- 修改：`tests/test_auth_usernames.py`

- [ ] **步骤 1：先写模板定义的静态测试**

覆盖点：
- 默认知识库名称是 `部门业务知识沉淀样板库`
- 模板版本号为当前 spec 约定值
- 默认模板数量是 5 篇
- 模板 key 和标题包含 3 篇通用 + 2 篇采购专项

- [ ] **步骤 2：先写初始化服务的幂等测试**

覆盖点：
- 首次执行时创建 1 个知识库和 5 个模板文件
- 再次执行不会重复创建第二套
- 如果知识库已存在但缺失某几篇模板，只补缺失的模板

- [ ] **步骤 3：先写用户创建链路的失败测试**

覆盖点：
- `signup_handler()` 创建用户成功后会调用默认知识库初始化服务
- `/auths/add` 管理员创建用户成功后会调用默认知识库初始化服务
- 初始化失败时不会导致用户创建回滚，但会记录日志并继续返回成功

- [ ] **步骤 4：先写管理员补发入口测试**

覆盖点：
- 管理员触发后会遍历现有用户
- 返回总用户数、成功数、失败数
- 同一用户不会重复创建样板

## 任务 2：实现默认模板定义模块

**文件：**
- 新建：`backend/open_webui/utils/default_knowledge_templates.py`
- 测试：`tests/test_default_knowledge_initializer.py`

- [ ] **步骤 1：定义默认知识库元信息**

建议常量：
- `DEFAULT_KNOWLEDGE_TEMPLATE_KEY = "department-knowhow-starter"`
- `DEFAULT_KNOWLEDGE_TEMPLATE_VERSION = 2`
- `DEFAULT_KNOWLEDGE_NAME = "部门业务知识沉淀样板库"`
- `DEFAULT_KNOWLEDGE_DESCRIPTION = "..."`

- [ ] **步骤 2：定义 5 篇默认模板正文**

模板清单：
- `01-业务知识Knowhow沉淀说明与范文`
- `02-业务知识Knowhow填空模板`
- `03-常见问题与易错点模板`
- `04-采购Commercial会议总结模板（老板视角）`
- `05-采购商品分类与数据治理模板（按名称和规格）`

要求：
- 文案是中文
- 既能直接阅读，也能直接复制修改
- 通用模板结构稳定，采购模板体现真实业务语境

- [ ] **步骤 3：提供统一读取函数**

建议函数：
- `build_default_knowledge_form()`
- `get_default_seed_documents()`

## 任务 3：实现默认知识库初始化服务

**文件：**
- 新建：`backend/open_webui/utils/default_knowledge_initializer.py`
- 测试：`tests/test_default_knowledge_initializer.py`

- [ ] **步骤 1：实现查找现有样板知识库的函数**

要求：
- 优先根据 `meta.seed_template_key` 判断
- 不只依赖知识库名称，因为用户后续可能改名

- [ ] **步骤 2：实现单篇模板文件创建函数**

建议流程：
- 创建一个 `.txt` 文件记录，复用 `Files.insert_new_file()`
- `data.content` 直接写入模板正文
- `meta` 中写入 `seeded_by_system`、`seed_template_key`、`seed_document_key`
- 然后调用现有 `process_file(..., collection_name=knowledge_id)` 入向量库
- 最后调用 `Knowledges.add_file_to_knowledge_by_id(...)`

- [ ] **步骤 3：实现单用户初始化入口**

建议函数：
- `ensure_default_knowledge_templates_for_user(request, user, db=None) -> SeedInitializationResult`

要求：
- 缺知识库则创建
- 缺模板则补齐
- 已存在则跳过
- 任何单篇模板失败都要记录在结果中，方便管理员排查

- [ ] **步骤 4：实现现有用户批量补发入口**

建议函数：
- `seed_default_knowledge_templates_for_existing_users(request, db=None) -> SeedBackfillResult`

要求：
- 复用单用户初始化逻辑
- 汇总成功/失败统计

## 任务 4：接入新用户自动初始化与管理员补发入口

**文件：**
- 修改：`backend/open_webui/routers/auths.py`
- 修改：`backend/open_webui/routers/users.py`
- 测试：`tests/test_auth_usernames.py`
- 测试：`tests/test_default_knowledge_initializer.py`

- [ ] **步骤 1：在 `signup_handler()` 末尾接入初始化服务**

要求：
- 放在用户创建成功、默认分组分配完成之后
- 初始化失败只记日志，不影响注册成功

- [ ] **步骤 2：在 `/auths/add` 管理员创建用户逻辑中接入初始化服务**

要求：
- 行为与注册保持一致
- 不影响现有返回结构

- [ ] **步骤 3：在 `users.py` 增加管理员补发入口**

建议接口：
- `POST /api/v1/users/admin/default-knowledge/seed`

返回：
- `total_users`
- `processed_users`
- `created_knowledge_bases`
- `created_documents`
- `failed_users`

## 任务 5：验证、整理文档并准备提交

**文件：**
- 新建：`tests/test_default_knowledge_initializer.py`
- 修改：`tests/test_auth_usernames.py`
- 修改：`backend/open_webui/utils/default_knowledge_templates.py`
- 修改：`backend/open_webui/utils/default_knowledge_initializer.py`
- 修改：`backend/open_webui/routers/auths.py`
- 修改：`backend/open_webui/routers/users.py`

- [ ] **步骤 1：运行聚焦测试**

运行：
```bash
pytest tests/test_default_knowledge_initializer.py tests/test_auth_usernames.py -q -p no:cacheprovider
```

- [ ] **步骤 2：如果涉及前端展示副作用，补跑构建或相关回归**

运行：
```bash
npm run build
```

- [ ] **步骤 3：检查差异范围**

运行：
```bash
git diff -- backend/open_webui/utils/default_knowledge_templates.py backend/open_webui/utils/default_knowledge_initializer.py backend/open_webui/routers/auths.py backend/open_webui/routers/users.py tests/test_default_knowledge_initializer.py tests/test_auth_usernames.py
```

- [ ] **步骤 4：提交本次默认知识库样板功能**

建议提交信息：
```bash
git commit -m "feat: seed default knowledge templates for users"
```

## 自检

- 新用户注册后会自动看到默认样板知识库
- 管理员新增用户后，该用户也会自动拥有默认样板知识库
- 现有用户可以通过管理员补发入口拿到同样的样板
- 每个用户只会有 1 套默认样板知识库
- 默认样板包含 5 篇模板，且包含 2 篇采购专项模板
- 用户可以自由修改、删除、重命名，不会被系统强制恢复
- 不新增新的产品模块或前端入口，完全复用现有知识库结构
