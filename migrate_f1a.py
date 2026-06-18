"""迁移脚本：为现有 data.db 的 users 表新增 F1-A 审计字段"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')

if not os.path.exists(DB_PATH):
    print('data.db 不存在，应用启动时将自动创建新 schema。无需迁移。')
    exit(0)

with sqlite3.connect(DB_PATH) as db:
    cols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
    print('现有 users 字段:', cols)

    missing = [c for c in ['created_by_id', 'created_ip', 'updated_at'] if c not in cols]

    if not missing:
        print('所有审计字段已存在，无需迁移。')
        exit(0)

    print('缺失字段:', missing)
    db.execute('ALTER TABLE users ADD COLUMN created_by_id INTEGER REFERENCES users(id)')
    db.execute("ALTER TABLE users ADD COLUMN created_ip TEXT NOT NULL DEFAULT '127.0.0.1'")
    db.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")
    db.commit()
    print('迁移完成：已新增 created_by_id、created_ip、updated_at 三个审计字段。')

    # 验证
    cols_after = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
    print('迁移后 users 字段:', cols_after)
