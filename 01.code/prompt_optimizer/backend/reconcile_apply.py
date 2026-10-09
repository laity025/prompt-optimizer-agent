"""增量补 schema：把已有 SQLite 库的表补充到最新模型结构（仅 ADD COLUMN，幂等、不动数据）。"""
from app.db.base import engine
from sqlalchemy import inspect as sa_inspect

# (表, 列, DDL) —— tasks 在知识库阶段(Phase3/4)新增的列
DDLS = [
    ("tasks", "enable_rag", "ALTER TABLE tasks ADD COLUMN enable_rag INTEGER NOT NULL DEFAULT 0"),
    ("tasks", "kb_id", "ALTER TABLE tasks ADD COLUMN kb_id INTEGER"),
]

insp = sa_inspect(engine)
with engine.begin() as conn:
    for table, col, ddl in DDLS:
        existing = {c["name"] for c in insp.get_columns(table)}
        if col in existing:
            print(f"[SKIP] {table}.{col} 已存在")
            continue
        conn.execute(__import__("sqlalchemy").text(ddl))
        print(f"[OK]  added {table}.{col}")

# 校验
insp2 = sa_inspect(engine)
tasks_cols = {c["name"] for c in insp2.get_columns("tasks")}
print("tasks cols now contain kb_id/enable_rag:",
      "kb_id" in tasks_cols, "enable_rag" in tasks_cols)