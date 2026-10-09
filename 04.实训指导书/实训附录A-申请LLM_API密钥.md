# 实训附录A 申请 LLM API 密钥（以硅基流动 SiliconFlow 为例）

> 本附录给出获取 OpenAI 兼容大模型 API 密钥的实操流程，以**硅基流动（SiliconFlow）** 的 DeepSeek 系列模型为例（国内直连、免科学上网），并指导把密钥安全配置到本项目后端 `.env`，最后用一段 Python 脚本验证联通。本项目后端采用 OpenAI 兼容接口，因此适用于一切提供 `/v1/chat/completions` 的兼容服务。

| 项目 | 内容 |
|------|------|
| 实训编号 | 附录A |
| 适用场景 | 后端需调用大模型（变体生成 / 任务执行 / 评审打分）前必配 |
| 配置位置 | `d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend\.env` |
| 配置项 | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_DEFAULT_MODEL` |
| 前置依赖 | Python 3.12、`openai`（或 `httpx`）、`python-dotenv` |

---

## 一、目的

1. 学会在硅基流动平台注册账号并创建 API 密钥。
2. 学会把密钥与接口地址写入后端 `.env`，并理解各配置项含义。
3. 掌握用一段 Python 脚本（OpenAI 兼容 Chat 接口）验证 LLM 连通性的方法。
4. 掌握密钥安全注意事项（不提交 git、加 .gitignore、权限最小化）。

---

## 二、前置准备

1. 可正常上网（硅基流动为国内可直连的服务）。
2. 已安装 Python 3.12，可用 `python --version` 确认。
3. 建议在项目的后端虚拟环境中操作（可选，见故障排除问题2）。

**验证前置条件：**
```powershell
python --version
# 预期输出: Python 3.12.x 或以上

# 确认后端 .env 文件已存在
Test-Path "d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend\.env"
# 预期输出: True
```

---

## 三、操作步骤

> 每步包含操作与验证。请先阅读「五、安全提示」，全程不要把真实密钥复制进入任何聊天、文档或代码库。

### 步骤1：注册硅基流动账号

**操作：**
1. 打开硅基流动官网 `https://siliconflow.cn`。
2. 点击「登录 / 注册」，推荐使用手机号或邮箱注册。
3. 按提示完成验证（国内手机号可直接注册）。

**验证：** 成功登录后浏览器地址栏进入平台控制台首页。

**成功标志：** 能访问硅基流动控制台，页面显示账号欢迎信息。

---

### 步骤2：实名认证并获取免费额度（可选但推荐）

**操作：** 硅基流动新用户通常提供一定赠送额度，用于在控制台「账户/费用」处查看额度；某些模型或调用量需要实名认证。按平台提示完成认证。

**验证：** 控制台「费用中心 / 账户余额」能看到可用额度。

**成功标志：** 账户存在可用额度或已开通对应模型。

---

### 步骤3：进入控制台创建 API 密钥

**操作：**
1. 登录后进入控制台，左侧菜单找到「API 密钥（API Keys）」（或「账户」→「API 密钥」）。
2. 点击「新建 API 密钥」（New API Key）。
3. 填写密钥名称（建议命名如 `prompt-optimizer-dev`），点击创建。
4. 创建后立刻复制显示的密钥（形如 `sk-` 开头的长字符串）。

> 注意：密钥只在创建时完整显示一次，关闭页面后无法再查看明文，只能重新生成。请当场复制。

**验证：** 剪贴板中已有一串 `sk-` 开头的密钥。

**成功标志：** 在 API 密钥列表中能看到刚创建的密钥条目。

---

### 步骤4：确认所选模型的模型 ID 与 Base URL

**操作：** 在控制台「模型广场 / Models」搜索 DeepSeek 系列模型，复制其**模型 ID**（形如 `deepseek-ai/DeepSeek-V4-Flash`）。硅基流动的 OpenAI 兼容接口地址（Base URL）通常为：

```
https://api.siliconflow.cn/v1
```

**验证：** 确认该模型在你账号下可用（或为免费/已开通模型）。

```powershell
# 在浏览器访问模型广场并搜索 deekseek，确认模型 ID 存在
# （此步为人工操作，命令仅提示记录路径）
```
**成功标志：** 拿到一个有效模型 ID 与上面给出的 Base URL。

---

### 步骤5：把密钥写入后端 .env（用 python-dotenv）

**操作：** 编辑 `.env` 文件，填写三项配置。`.env` 中键名以项目实际为准（后端默认读取 `LLM_DEFAULT_MODEL`）。

```dotenv
# ============ LLM API（OpenAI 兼容，国内直连） ============
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-这里替换为你的真实密钥，不要在下文示例中写真实密钥
LLM_DEFAULT_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

> 手工编辑 .env 即可，也可用 python-dotenv 验证加载（见步骤6脚本）。

**验证：**
```powershell
Get-Content "d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend\.env" | Select-String "LLM_API_KEY=|LLM_BASE_URL=|LLM_DEFAULT_MODEL="
# 预期输出: 3 行均已填写，LLM_API_KEY 以 sk- 开头且非占位文本
```

**成功标志：** `.env` 中三项 LLM 配置已填入真实值。

---

### 步骤6：用一段 Python 脚本验证连通

**操作：** 在后端目录创建验证脚本并运行。脚本从 `.env` 读取配置，向 OpenAI 兼容接口发一条 chat 请求并打印回复。

**验证：** 运行脚本，看到模型返回的文本回复。

**成功标志：** 脚本无异常，并打印出 LLM 返回的回复内容。

---

### 步骤7：把密钥加进 .gitignore

**操作：** 确认后端目录的 `.gitignore`（或仓库根目录）包含 `.env`，避免密钥被 git 提交。

```gitignore
# 危险敏感文件，严禁提交
.env
.env.local
```

**验证：**
```powershell
Get-Content "d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend\.gitignore" -ErrorAction SilentlyContinue | Select-String "\.env"
# 若不存在 .gitignore，请新建并加入上述内容
```

**成功标志：** 仓库中 `.env` 被忽略，`git status` 不显示 `.env`。

---

## 四、验证

完成以上步骤后，请确认下表验证项：

| 验证项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| Python 已安装 | `python --version` | 3.12.x |
| .env 存在 | `Test-Path PATH\.env` | True |
| 三项配置已填 | `Get-Content .env | Select-String "LLM_"` | 3 行已填且含真实密钥占位 |
| 连通脚本运行 | `python veriy_llm.py` | 打印模型回复、无异常 |
| .env 已忽略 | `.gitignore` 含 `.env`，`git status` 无 `.env` | 忽略生效 |

---

## 五、安全提示（重要）

1. **密钥勿提交 git**：`.env` 必须加入 `.gitignore`，不要截图、粘贴到聊天记录或公开文档。泄露后应立即在控制台删除并重新生成密钥。
2. **权限最小化**：为开发/生产分别创建不同密钥，仅授予当前环境所需模型权限；不共用、不滥用通用的高权限密钥。
3. **仅保留本地**：不要把密钥写进硬编码代码或打包进前端静态资源；后端通过 `.env` 读取。
4. **脱敏调用**：调用大模型前对提示词中敏感字段做脱敏（占位替换），符合本项目安全规范。
5. **额度监控**：定期查看用量与费用，设置预算或用量告警，防止异常盗用造成损失。

---

## 六、故障排除

### 问题1：请求返回 401 Unauthorized

**现象：** 脚本报 401，密钥无效或未传入。

**解决方案：** 检查 `.env` 中 `LLM_API_KEY` 是否以 `sk-` 开头且完整复制（勿含空格/引号），确认密钥未被平台禁用或过期；必要时重新生成。

### 问题2：提示没有 `openai` 包

**现象：** `ModuleNotFoundError: No module named 'openai'`。

**解决方案：** 安装依赖后重试：
```powershell
pip install openai python-dotenv
python -c "import openai; print(openai.__version__)"
# 预期输出: 打印版本号
```

### 问题3：返回 `model not found` 或模型不可用

**现象：** 报错提示模型 ID 不存在或当前账号未开通。

**解决方案：** 到控制台模型广场核对模型 ID 拼写（含 `/`，如 `deepseek-ai/DeepSeek-V4-Flash`）；确认账号已实名/已开通该模型；更换为平台支持的免费模型。

### 问题4：`.env` 中值带引号导致解析异常

**现象：** 密钥值含 `""` 或行尾空格，脚本读到异常值。

**解决方案：** 移除值两端的引号与首尾空格，保持形如 `LLM_API_KEY=sk-xxxx` 单行格式；重新运行验证脚本。

### 问题5：无法访问硅基流动或请求超时

**现象：** 网络超时、连接被拒。

**解决方案：** 硅基流动为国内直连，确认未开代理导致路由异常；检查 Base URL 是否完整（`https://api.siliconflow.cn/v1`）；必要时换用其他 OpenAI 兼容服务并同步修改 `LLM_BASE_URL`。

---

## 七、参考代码（联通验证脚本）

在 `d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend\` 下新建文件 `verify_llm.py`，内容如下：

```python
"""
联通验证脚本：从 .env 读取 LLM 配置，向 OpenAI 兼容接口发送一条 chat 请求并打印回复。
用途：在配置 API 密钥后验证后端能否调用大模型（变体生成/执行/评审的基础）。
依赖：pip install python-dotenv
"""
import os

# 读取 backend 目录下的 .env 配置
from dotenv import load_dotenv
from openai import OpenAI

# 定位 .env 文件：脚本位于 backend 目录，与 .env 同级
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(ENV_PATH)  # 将 .env 中的键值加载为环境变量


def main() -> None:
    """读取配置并发送一条 chat 请求，打印模型回复。"""
    # 从环境变量读取 LLM 配置（由 .env 提供）
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_DEFAULT_MODEL")

    # 校验关键配置是否缺失，缺失则直接报错退出
    if not api_key or api_key.startswith("sk-") is False or api_key == "sk-":
        raise SystemExit("[ERROR] LLM_API_KEY 未配置或为占位值，请先在 .env 中填写真实密钥")

    # 构造 OpenAI 兼容客户端（国内直连的硅基流动等服务均可）
    client = OpenAI(base_url=base_url, api_key=api_key)

    # 发送一条 chat 请求，temperature 调低以获得稳定输出
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是连通性测试助手。"},
            {"role": "user", "content": "请只回复：连接成功"},
        ],
        temperature=0.1,
    )
    # 从响应中抽取模型回复文本
    reply = resp.choices[0].message.content.strip()
    print(f"[模型] {model}")
    print(f"[回复] {reply}")


if __name__ == "__main__":
    main()
```

**运行与验证：**
```powershell
# 进入 backend 目录，安装依赖后运行脚本
cd "d:\trae_project\提示词自动迭代优化智能体\01.code\prompt_optimizer\backend"
pip install python-dotenv openai
python -m pip show python-dotenv   # 确认已安装
# 预期输出: 显示 python-dotenv 版本

python verify_llm.py
# 预期输出: [模型] deepseek-ai/DeepSeek-V4-Flash
#          [回复] 连接成功
```

> 说明：若项目后端依赖清单中未含 `openai`，此脚本属独立验证用途；正式联通后仍以 [开发技术文档](AI共创过程文档/提示词自动迭代优化智能体_开发技术文档.md) 中的 `llm/client.py` 封装为准，无需重复引入。上例中的 `sk-` 占位仅供演示，切勿写入任何真实密钥。