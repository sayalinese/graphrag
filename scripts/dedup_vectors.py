import sys
sys.path.insert(0, r'c:/Users/16960/Desktop/项目')
from app import create_app
app = create_app()
with app.app_context():
    from app.extensions import db
    from sqlalchemy import text

    r0 = db.session.execute(text('SELECT COUNT(*) FROM kg_pg_embedding')).scalar()
    print(f'清理前: {r0} 条')

    result = db.session.execute(text("""
        DELETE FROM kg_pg_embedding
        WHERE uuid IN (
            SELECT uuid FROM (
                SELECT uuid,
                       ROW_NUMBER() OVER (
                           PARTITION BY collection_id, custom_id
                           ORDER BY uuid DESC
                       ) AS rn
                FROM kg_pg_embedding
                WHERE custom_id IS NOT NULL AND custom_id != ''
            ) t WHERE rn > 1
        )
    """))
    db.session.commit()

    r1 = db.session.execute(text('SELECT COUNT(*) FROM kg_pg_embedding')).scalar()
    print(f'删除 {result.rowcount} 条重复，剩余: {r1} 条')
