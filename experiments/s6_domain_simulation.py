import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.context.semantic_gate import SemanticGate
from app.context.sufficiency import SufficiencyEngine, extract_keywords
from app.retrieval.embeddings import EmbeddingModel
from app.core.config import settings

def main():
    embedder = EmbeddingModel()
    gate = SemanticGate(embedder)
    retriever = Retriever(embedder)
    chunks = load_and_chunk(settings.sample_document)
    retriever.index_chunks(chunks)

    # 1. Domain Queries (S1 Authentic Set)
    s1_queries = [
        ("Q1", "Direct factual", "What is Retrieval-Augmented Generation (RAG)?"),
        ("Q2", "Direct factual", "What embedding model does Synapse use in Sprint 0.2?"),
        ("Q3", "Multi-chunk factual", "How do Sentence Transformers and FAISS work together in the Synapse retrieval pipeline?"),
        ("Q4", "Multi-chunk factual", "How does a query move from text to retrieved document chunks in the baseline?"),
        ("Q5", "Relationship / multi-hop", "Why is chunking necessary, and how does chunk overlap help retrieval?"),
        ("Q6", "Relationship / multi-hop", "What roles do FAISS, Sentence Transformers, and Ollama each play in the baseline RAG pipeline?"),
        ("Q7", "Synthesis / comparison", "What are the respective purposes of RAG, FAISS, Sentence Transformers, and Ollama in Synapse?"),
        ("Q8", "Synthesis / comparison", "Why does Synapse use local Ollama/Mistral instead of relying on cloud-based model APIs during baseline research?"),
        ("Q9", "Unanswerable", "What is the population of France?"),
        ("Q10", "Unanswerable", "What accuracy percentage did the Synapse baseline achieve in Sprint 0.2?"),
    ]

    print("\n" + "=" * 115)
    print("  AUTHENTIC SYNAPSE DOMAIN QUERY SET (data/sample.txt)")
    print("=" * 115)
    print(f"{'ID':<5} | {'Type':<22} | {'Top-1 Retr':<10} | {'Stage 1 Lex Cov':<16} | {'Stage 1 Sem Sim':<16} | {'Status':<12}")
    print("-" * 115)

    for qid, qtype, q in s1_queries:
        res = retriever.query(q, top_k=3)
        top1 = [res["results"][0]] if res["results"] else []
        sem_res = gate.evaluate(q, top1) if top1 else None
        
        # Lexical coverage
        q_kw = extract_keywords(q)
        ev_kw = extract_keywords(top1[0]["text"]) if top1 else set()
        matched = q_kw & ev_kw
        cov = len(matched) / len(q_kw) if q_kw else 0.0
        score = top1[0]["score"] if top1 else 0.0
        sem_sim = sem_res.semantic_score if sem_res else 0.0
        
        status = "UNANSWERABLE" if qid in ("Q9", "Q10") else "ANSWERABLE"
        print(f"{qid:<5} | {qtype:<22} | {score:<10.4f} | {cov:<16.4f} | {sem_sim:<16.4f} | {status:<12}")

    print("=" * 115 + "\n")

if __name__ == "__main__":
    main()
