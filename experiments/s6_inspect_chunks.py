import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.context.semantic_gate import SemanticGate
from app.retrieval.embeddings import EmbeddingModel
from app.core.config import settings

def main():
    embedder = EmbeddingModel()
    gate = SemanticGate(embedder)
    retriever = Retriever(embedder)
    chunks = load_and_chunk(settings.sample_document)
    retriever.index_chunks(chunks)

    from experiments.s6_experiment import load_queries
    queries = load_queries()

    print("\n" + "=" * 110)
    print("  RETRIEVED TOP-1 CHUNK INSPECTION PER QUERY")
    print("=" * 110)

    for item in queries:
        qid, q = item["id"], item["question"]
        res = retriever.query(q, top_k=3)
        top_chunk = res["results"][0] if res["results"] else {}
        sem_res = gate.evaluate(q, [top_chunk]) if top_chunk else None
        
        text_preview = top_chunk.get("text", "").replace("\n", " ")[:80] + "..."
        print(f"\n{qid}: {q}")
        print(f"  Top-1 Score: {top_chunk.get('score', 0):.4f} | Semantic Sim: {sem_res.semantic_score if sem_res else 0:.4f}")
        print(f"  Chunk ID:    {top_chunk.get('chunk_id')}")
        print(f"  Text:        {text_preview}")

    print("\n" + "=" * 110 + "\n")

if __name__ == "__main__":
    main()
