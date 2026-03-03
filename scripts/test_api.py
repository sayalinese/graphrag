from __future__ import annotations

from app import create_app
from app.models import KnowledgeBase


def main() -> None:
    app = create_app()
    with app.app_context():
        kb = KnowledgeBase.query.first()
        if not kb:
            print("no kb")
            return
        client = app.test_client()
        resp = client.post(
            "/api/rag/search/query_pgvector",
            json={
                "kb_id": kb.id,
                "query": "用水",
                "top_k": 5,
                "mode": "hybrid",
                "vector_weight": 0.6,
                "bm25_weight": 0.4,
                "threshold": 0.0,
            },
        )
        print("status", resp.status_code)
        try:
            print(resp.get_json())
        except Exception as exc:  # noqa: BLE001
            print("failed to parse json", exc)
            print(resp.data[:200])


if __name__ == "__main__":
    main()
