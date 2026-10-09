# 实训附录B Nginx + HTTPS 配置

## 一、目的

本附录为「前后端分离生产部署」的实操 How-to：使用 **Nginx 反向代理 + HTTPS** 对外提供安全访问。内容基于项目真实配置 `部署版code\nginx.conf`，说明 80→443 跳转、SSL 证书、`location /` 反代 FastAPI:8000（生产单端口一体化托管）、gzip 静态缓存、安全加固与负载均衡示例，并串联启动、语法检查、重载与 HTTPS 验证命令。

## 二、前置条件

- 一台已安装 **Nginx** 的服务器（Linux 常见发行版，如 Ubuntu/CentOS）。
- 后端已按生产单端口模式在 127.0.0.1:8000 运行：
  ```bash
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > app.log 2>&1 &
  ```
- 一份已签发的 SSL 证书（HTTPS 必需）。**本附录使用占位符路径，请替换为你自己的域名与证书。** 若仅做本地练习可用 `openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout server.key -out server.crt` 自签体验。
- 项目真实参考配置：
  `d:\trae_project\提示词自动迭代优化智能体\部署版code\nginx.conf`

> 生产形态说明：本系统为**前后端分离**，但生产推荐「单端口一体化」——前端构建产物已放入后端 `static/`，由 FastAPI 统一托管，Nginx 只需把 `location /` 所有请求反代到 `127.0.0.1:8000` 即可同时覆盖前端页面与 `/api/v1/*` 业务接口。

## 三、配置步骤

### 步骤1：确认后端单端口模式可访问

**操作命令：**

```bash
curl -s http://127.0.0.1:8000/health
# 预期输出: {"status":"ok"} 之类健康响应
```

**成功标志：** 后端在本机 8000 返回健康响应，说明可被 Nginx 反代。

### 步骤2：编写 `/etc/nginx/conf.d/prompt_opt.conf`

以下为完整示例，基于项目真实 `nginx.conf` 扩展 HTTPS / gzip / 安全项 / 负载均衡。**中文注释说明每段作用；证书路径、域名与 upstream 地址为占位符，请自行替换。**

```nginx
# ============================================================
# 提示词自动迭代优化智能体 —— Nginx 反向代理 + HTTPS
# 前置：后端以单端口模式监听 127.0.0.1:8000
# 替换项：server_name / ssl_certificate / ssl_certificate_key 占位符
# ============================================================

# ---- 0) 后端应用的负载均衡组（示例保留两个真实存在的后端地址）----
# 若仅单实例，可直接把全部 proxy_pass 写为 http://127.0.0.1:8000；
# 留作多后端示例，按需增删。
upstream prompt_opt_backend {
    server 127.0.0.1:8000;      # 第一个后端实例
    # server 127.0.0.1:8001;    # （示例）第二个后端实例，取消注释即启用负载均衡
}

# ---- 1) HTTP（80）端口：一律重定向到 HTTPS ----
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com;   # 替换为你的域名或公网 IP

    # 允许上传体积（报告导出 / 大量用例导入）
    client_max_body_size 20m;

    # 将所有 HTTP 请求 301 永久跳转到 HTTPS 同路径
    return 301 https://$host$request_uri;
}

# ---- 2) HTTPS（443）主服务 ----
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com;   # 替换为你的域名或公网 IP

    # SSL 证书路径（占位符，替换为你的实际证书）
    ssl_certificate     /etc/ssl/certs/your-domain.com.pem;
    ssl_certificate_key /etc/ssl/private/your-domain.com.key;
    # 推荐的现代 TLS 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 访问日志（按项目真实配置）
    access_log /var/log/nginx/prompt_opt.access.log;
    error_log  /var/log/nginx/prompt_opt.error.log;

    # ---- 安全性加固 ----
    server_tokens off;              # 隐藏 Nginx 版本号，避免信息泄露
    # 限制非必要请求头（即使仅传递白名单；禁传未知头可降低注入面）
    ignore_invalid_headers on;

    # 传输大小
    client_max_body_size 20m;

    # ---- 前端静态资源：gzip 压缩 + 长缓存（前端产物带 hash 指纹）----
    location ~* \.(js|css|png|jpg|jpeg|gif|svg|woff2|ico)$ {
        proxy_pass http://prompt_opt_backend;      # 交由后端读取 static/ 静态文件
        proxy_set_header Host $host;
        gzip on;                                  # 开启 gzip
        gzip_types text/plain text/css application/javascript application/json;
        gzip_min_length 1k;
        expires 7d;                               # 带 hash 的资源缓存 7 天
    }

    # ---- 主入口：所有非静态请求反代到 FastAPI（单端口一体化） ----
    location / {
        proxy_pass http://prompt_opt_backend;      # 解析到 upstream 负载均衡组
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;   # 传递真实客户端 IP
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme; # 让后端识别 http/https

        # 大模型接口耗时较长，放宽代理读写超时（单位秒）
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;

        # 若后端为纯静态托管可改用下方 history 回退（后端已实现 fallback，可保持代理）
        # try_files $uri $uri/ /index.html;
    }
}
```

### 步骤3：语法检查与重载

**操作命令（Linux，PowerShell 请在 WSL 或远程执行）：**

```bash
# 语法检查
sudo nginx -t

# 检查通过后平滑重载（不断连生效配置）
sudo nginx -s reload
```

**成功标志：**
- `nginx -t` 输出 `syntax is ok` 与 `test is successful`。
- `nginx -s reload` 无报错即完成重载。

### 步骤4：验证 HTTPS 与反向代理

**操作命令：**

```bash
# 用自签证书验证可加 -k 忽略证书校验
curl -k https://your-domain.com/health
# 预期输出: 后端健康响应，证明反代链路贯通

# 验证 80 → 443 跳转
curl -sI http://your-domain.com/
# 预期输出: 状态码 301 且 Location 指向 https://...
```

**成功标志：**
- HTTPS 访问返回后端业务响应（如 `{"status":"ok"}`）。
- HTTP 请求会 301 跳转到 HTTPS。

## 四、验证清单

| 验证项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| 后端可访问 | `curl http://127.0.0.1:8000/health` | 返回健康响应 |
| 配置文件语法 | `nginx -t` | syntax is ok |
| 配置生效 | `nginx -s reload` | 无报错 |
| HTTPS 反代 | `curl -k https://域名/health` | 返回业务响应 |
| 80→443 跳转 | `curl -sI http://域名/` | 301 指向 https |
| 静态资源缓存 | 观察响应头 | 含 `expires: 7d`、gzip |

## 五、故障排除

### 问题1：`nginx -t` 提示缺少证书文件

**现象：** 证书路径占位符找不到 `/etc/ssl/certs/your-domain.com.pem`。

**解决方案：** 用你的真实证书路径替换，或在本地练习生成自签证书：
```bash
sudo openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout /etc/ssl/private/your-domain.com.key \
  -out /etc/ssl/certs/your-domain.com.pem -subj "/CN=your-domain.com"
```

### 问题2：`curl -k https://...` 返回 502

**现象：** 反代目标无响应。

**解决方案：** 确认后端 8000 已运行且配置中 proxy_pass 与之匹配：
```bash
# 后端必须监听 127.0.0.1:8000
curl -s http://127.0.0.1:8000/health
# 若本机根目录执行有误，检查 upstream 地址与端口
sudo tail -f /var/log/nginx/prompt_opt.error.log
```

### 问题3：大用例文件上传失败

**现象：** 上传返回 413 请求体过大。

**解决方案：** 调大 `client_max_body_size`（如 `20m` 或更多）后重载：`sudo nginx -s reload`。注意需与后端 body 限制一致。

### 问题4：浏览器提示 HTTPS 不受信任

**现象：** 使用自签证书时浏览器拦截。

**解决方案：** 训练/演示环境可临时 `curl -k` 或信任自签证书；正式环境请使用 CA 签发证书并把 `server_name` 与证书域名保持一致。

## 六、参考

- 项目真实配置：`d:\trae_project\提示词自动迭代优化智能体\部署版code\nginx.conf`
- 部署运维文档：`d:\trae_project\提示词自动迭代优化智能体\04.实训指导书\AI共创过程文档\提示词自动迭代优化智能体_部署运维文档.md`
- 架构：浏览器 → Nginx(80/443) → FastAPI(127.0.0.1:8000 单端口托管前端静态+业务 API)。
- 安全合规：依据《互联网信息服务深度合成管理规定》对 AI 内容显著标识；建议部署于内网/受控环境，`.env` 含密钥不予公开。