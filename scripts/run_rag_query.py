"""Quick script to run a sample RAG query for validation."""
from __future__ import annotations

from app import create_app
from app.services.rag.rag_search import search_api
from app.models import KnowledgeBase


def main() -> None:
    app = create_app()
    with app.app_context():
        kb = KnowledgeBase.query.first()
        if not kb:
            print("No knowledge base records found.")
            return

        print(f"Using knowledge base id={kb.id}, kb_uuid={kb.kb_id}")
        engine = search_api.get_search_engine()
        if not engine:
            print("Failed to initialize search engine.")
            return

        query = "用水"
        results = engine.hybrid_search(kb_id=kb.id, query_text=query, top_k=5)
        print(f"Query '{query}' returned {len(results)} results.")
        for idx, item in enumerate(results, 1):
            snippet = (item.get("content") or "")[:120].replace("\n", " ")
            fused = item.get("fused_score")
            print(f"{idx}. fused_score={fused}, doc_id={item.get('doc_id')}, text={snippet}")


if __name__ == "__main__":
    main()
