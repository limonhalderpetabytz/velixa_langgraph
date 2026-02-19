import os
import pickle
import pandas as pd
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS

# === Step 0: Load environment variables ===
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

# === Step 1: Configuration ===
CSV_PATH = "data_pipeline/data.csv"              # Must contain 'description' and 'resolution'
QUESTION_COLUMN = "description"
SOLUTION_COLUMN = "resolution"

FAISS_DIR = "data_pipeline/faiss_store"          # Folder for FAISS storage
METADATA_PATH = "data_pipeline/metadata.pkl"


class KnowledgeBaseTool:
    """
    Self-contained FAISS knowledge base tool.
    Provides retrieval and persistent storage of problem-solution pairs.
    """

    def __init__(self, faiss_dir: str = FAISS_DIR):
        # Handle file/folder paths gracefully
        if faiss_dir.endswith(".index"):
            faiss_dir = os.path.dirname(faiss_dir) or "."
        os.makedirs(faiss_dir, exist_ok=True)
        self.faiss_dir = faiss_dir

        self.embeddings = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

        index_path = os.path.join(faiss_dir, "index.faiss")
        if os.path.exists(index_path):
            print("📂 Loading existing FAISS KB...")
            self.vectorstore = FAISS.load_local(
                faiss_dir, self.embeddings, allow_dangerous_deserialization=True
            )
        else:
            print("🆕 No FAISS index found — building from CSV...")
            self.vectorstore = self._build_from_csv()

    def _build_from_csv(self):
        """Load data from CSV and build FAISS index."""
        if not os.path.exists(CSV_PATH):
            print(f"⚠️ CSV not found at {CSV_PATH}. Empty KB created.")
            return None

        df = pd.read_csv(CSV_PATH)
        if QUESTION_COLUMN not in df.columns or SOLUTION_COLUMN not in df.columns:
            print(f"⚠️ Missing required columns: {QUESTION_COLUMN}, {SOLUTION_COLUMN}")
            return None

        texts = df[QUESTION_COLUMN].astype(str).tolist()
        metadatas = [{"solution": s} for s in df[SOLUTION_COLUMN].astype(str).tolist()]

        if not texts:
            print("⚠️ CSV is empty, FAISS not built.")
            return None

        vectorstore = FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)
        vectorstore.save_local(self.faiss_dir)
        print(f"✅ FAISS KB built from {len(texts)} entries in {CSV_PATH}")
        return vectorstore

    def add_solution(self, query: str, solution: str):
        """Add or update a problem-solution pair."""
        metadata = {"solution": solution}

        if self.vectorstore is None:
            self.vectorstore = FAISS.from_texts([query], self.embeddings, metadatas=[metadata])
        else:
            self.vectorstore.add_texts([query], [metadata])

        self.vectorstore.save_local(self.faiss_dir)
        with open(METADATA_PATH, "wb") as f:
            pickle.dump(metadata, f)

        print(f"✅ Added/updated solution for query: '{query}'")

    def retrieve_solution(self, query: str, threshold: float = 0.3, k: int = 3):
        """Retrieve solution from FAISS if similarity ≥ threshold."""
        if self.vectorstore is None:
            print("⚠️ Vectorstore not initialized yet (no data).")
            return None

        docs_and_scores = self.vectorstore.similarity_search_with_score(query, k=k)
        if not docs_and_scores:
            return None

        for doc, score in docs_and_scores:
            if score >= threshold:
                return doc.metadata.get("solution", None)
        return None

# ==============================================
# 📘 user_solution_node.py — Fully Autonomous Self-Learning Node
# ==============================================
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import os


# ---------------------------------------------------
# 🧠 Environment Setup
# ---------------------------------------------------
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

# ---------------------------------------------------
# 🧩 Knowledge Base Tools
# ---------------------------------------------------
kb_tool = KnowledgeBaseTool()


def retrieve_solution(query: str) -> str:
    solution = kb_tool.retrieve_solution(query)
    if solution:
        return f"✅ Found in Knowledge Base:\n{solution}"
    return None


def generate_solution(query: str, memory: str = "None") -> str:
    """
    Generate solution using LLM when KB does not have an answer.
    """
    llm_solution = ChatOpenAI(model="gpt-4", temperature=0.2)
    prompt = f"""
You are a professional problem-solving assistant. The user asked:

User Query: {query}

Memory context: {memory}

Provide a clear, concise, and practical solution for the user.

💡 Generated Solution:
"""
    response = llm_solution.invoke([SystemMessage(prompt)])
    return response.content.strip()


def confirm_and_update_solution(query: str, solution: str, user_confirmed: bool) -> str:
    """
    Update KB with solution only after user confirms it worked.
    """
    if user_confirmed:
        kb_tool.add_solution(query, solution)
        return f"💾 Solution confirmed and added to KB:\n{solution}"
    else:
        return "⚠️ Solution not confirmed. KB not updated."


# ---------------------------------------------------
# Bind ServiceNow tools + KB tools
# ---------------------------------------------------
solution_tools = [retrieve_solution, generate_solution, confirm_and_update_solution]


import os
import pandas as pd
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

# ===========================
# Load environment
# ===========================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("Set your OPENAI_API_KEY in a .env file")


# ===========================
# Helper to convert row to text
# ===========================
def row_to_text(row: pd.Series) -> str:
    return f"""Ticket ID: {row['ticket_id']}.
Category: {row['category']}.
Priority Level: {row['priority_level']}.
Description: {row['description']}.
Resolution: {row['resolution']}."""


import os
import pandas as pd
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

# ===========================
# Load environment
# ===========================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("Set your OPENAI_API_KEY in a .env file")


# ===========================
# Helper to convert row to text
# ===========================
def row_to_text(row: pd.Series) -> str:
    return f"""Ticket ID: {row['ticket_id']}.
Category: {row['category']}.
Priority Level: {row['priority_level']}.
Description: {row['description']}.
Resolution: {row['resolution']}."""


# ===========================
# Main function
# ===========================
def get_ticket_answer(query: str, csv_file_path: str = "data_pipeline/data.csv") -> str | None:
    """
    Given a user query, return an answer from the ticket database using RAG.
    If no relevant information is found, return None.
    """
    # Load CSV
    df = pd.read_csv(csv_file_path)
    if df.empty:
        return None

    # Create documents
    documents = [Document(page_content=row_to_text(row)) for _, row in df.iterrows()]

    # Create embeddings & vector store
    embedding_model = OpenAIEmbeddings()
    vector_store = FAISS.from_documents(documents, embedding_model)

    # Create retriever
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # Prompt template
    prompt_template = """
You are a helpful IT support assistant. Use the context below to answer the user's question.

Context from ticket database:
{context}

User query: {question}

If the answer is not in the context, respond exactly with: "NO_INFO".
Answer concisely and based on the context.
"""
    prompt = PromptTemplate.from_template(prompt_template)

    # LLM
    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

    # RAG pipeline
    rag_pipeline = (
        {
            "context": retriever,
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    # Get model response
    answer = rag_pipeline.invoke(query).strip()

    # If model explicitly says no info, return None
    if answer.upper() == "NO_INFO":
        return None

    return answer


# ===========================
# Optional: Interactive testing
# ===========================
if __name__ == "__main__":
    while True:
        query = input("\nAsk a question (or type 'exit' to quit): ")
        if query.lower() == 'exit':
            break
        answer = get_ticket_answer(query)
        if answer is None:
            print("\nNo relevant information found in the ticket database.")
        else:
            print("\nAnswer:", answer)

# ===========================
# Optional interactive mode
# ===========================
# if __name__ == "__main__":
#     while True:
#         query = input("\nAsk a question (or type 'exit' to quit): ")
#         if query.lower() == 'exit':
#             break
#         answer = get_ticket_answer(query)
#         print("\nAnswer:", answer)
