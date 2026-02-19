# === vector_store_manager.py ===
# Unified FAISS + OpenAI embeddings handler (build, load, and query with threshold)

import os
import pickle
import numpy as np
import pandas as pd
import faiss
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv


class VectorStoreManager:
    def __init__(
        self,
        csv_path="data_pipeline/data.csv",
        question_col="description",
        solution_col="resolution",
        faiss_index_path="data_pipeline/faiss_qa.index",
        metadata_path="data_pipeline/metadata.pkl",
        model_name="text-embedding-3-small",
        similarity_threshold=0.5  # Default threshold (0.0–1.0)
    ):
        # Load API key
        load_dotenv(dotenv_path=".env", override=True)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ Missing OPENAI_API_KEY in .env file")

        self.client = OpenAI(api_key=api_key)
        self.csv_path = csv_path
        self.question_col = question_col
        self.solution_col = solution_col
        self.faiss_index_path = faiss_index_path
        self.metadata_path = metadata_path
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold

        self.index = None
        self.metadata = None


    # === Build the FAISS vector store (only using questions for embeddings) ===
    def build_vector_store(self):
        print("📥 Loading CSV data...")
        df = pd.read_csv(self.csv_path)

        if self.question_col not in df.columns or self.solution_col not in df.columns:
            raise ValueError(
                f"CSV must contain '{self.question_col}' and '{self.solution_col}' columns."
            )

        questions = df[self.question_col].astype(str).tolist()
        print(f"✅ Loaded {len(questions)} questions from CSV")

        # Generate embeddings only for the questions
        embeddings = []
        print(f"🧠 Generating embeddings for questions using model '{self.model_name}'...")
        for question in tqdm(questions, desc="Embedding questions"):
            response = self.client.embeddings.create(model=self.model_name, input=question)
            embeddings.append(response.data[0].embedding)

        embeddings = np.array(embeddings, dtype="float32")
        dim = embeddings.shape[1]

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        # Create FAISS index for cosine similarity
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Save the FAISS index and metadata (questions + solutions)
        os.makedirs(os.path.dirname(self.faiss_index_path), exist_ok=True)
        faiss.write_index(index, self.faiss_index_path)
        with open(self.metadata_path, "wb") as f:
            pickle.dump(df.to_dict(orient="records"), f)

        print(f"💾 Saved FAISS index → {self.faiss_index_path}")
        print(f"💾 Saved metadata → {self.metadata_path}")

        self.index = index
        self.metadata = df.to_dict(orient="records")


    # === Load existing vector store ===
    def load_vector_store(self):
        if not os.path.exists(self.faiss_index_path) or not os.path.exists(self.metadata_path):
            raise FileNotFoundError("❌ FAISS index or metadata not found. Run build_vector_store() first.")

        self.index = faiss.read_index(self.faiss_index_path)
        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)
        print(f"✅ Loaded FAISS index with {self.index.ntotal} vectors")


    # === Query the FAISS store ===
    def query(self, user_query, top_k=1):
        if self.index is None or self.metadata is None:
            raise RuntimeError("❌ Vector store not initialized. Call load_vector_store() first.")

        # Get query embedding
        response = self.client.embeddings.create(model=self.model_name, input=user_query)
        query_embedding = np.array(response.data[0].embedding, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(query_embedding)

        # Search index (cosine similarity)
        D, I = self.index.search(query_embedding, k=top_k)

        results = []
        for idx, score in zip(I[0], D[0]):
            similarity = float(score)
            results.append({
                "question": self.metadata[idx][self.question_col],
                "solution": self.metadata[idx][self.solution_col],
                "similarity": similarity,
            })

        # Apply similarity threshold
        filtered = [r for r in results if r["similarity"] >= self.similarity_threshold]

        if not filtered:
            print(f"⚠️ No match above similarity threshold ({self.similarity_threshold}).")
            return []

        return filtered


# === Helper function for external usage ===
_vector_manager = None  # Singleton instance

def get_answer(query: str, top_k: int = 1, threshold: float = 0.75):
    """
    Returns the most relevant answer(s) from the FAISS vector store for a given query.
    Usage:
        from vector_store_manager import get_answer
        print(get_answer("User cannot send emails in Outlook"))
    """
    global _vector_manager

    if _vector_manager is None:
        _vector_manager = VectorStoreManager(similarity_threshold=threshold)
        _vector_manager.load_vector_store()

    results = _vector_manager.query(query, top_k=top_k)

    if not results:
        return "❌ No sufficiently similar answer found."

    if top_k == 1:
        best = results[0]
        print(f"🔍 Similarity: {best['similarity']:.2f}")
        return best["solution"]
    else:
        return results


# === Example test ===
if __name__ == "__main__":
    query = "my computer is running slow"
    answer = get_answer(query)
    print(f"💡 Best Answer: {answer}")
