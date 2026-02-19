import os
import pandas as pd
from dotenv import load_dotenv

# LangChain components for our RAG system
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.runnables.passthrough import RunnablePassthrough  # for RunnablePassthrough :contentReference[oaicite:1]{index=1}
from langchain_core.output_parsers.string import StrOutputParser     # for StrOutputParser :contentReference[oaicite:2]{index=2}
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.passthrough import RunnablePassthrough
# If StrOutputParser is available:
# from langchain_core.schema.output_parser import StrOutputParser
from langchain_core.documents import Document

# Then your code using these...

# ===========================
# 1. Load environment
# ===========================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("Set your OPENAI_API_KEY in a .env file")


# ===========================
# 2. Load CSV
# ===========================
csv_file_path = "data_pipeline/data.csv"  # replace with your CSV path
df = pd.read_csv(csv_file_path)
print(f"Loaded {len(df)} tickets.")

# ===========================
# 3. Convert each row to readable text
# ===========================
def row_to_text(row: pd.Series) -> str:
    return f"""Ticket ID: {row['ticket_id']}.
Category: {row['category']}.
Priority Level: {row['priority_level']}.
Description: {row['description']}.
Resolution: {row['resolution']}."""

documents = [Document(page_content=row_to_text(row)) for _, row in df.iterrows()]
print(f"Created {len(documents)} documents for embedding.")

# ===========================
# 4. Create embeddings & FAISS vector store
# ===========================
embedding_model = OpenAIEmbeddings()  # uses OpenAI API
vector_store = FAISS.from_documents(documents, embedding_model)
print("Vector store created successfully!")

# ===========================
# 5. Create retriever
# ===========================
retriever = vector_store.as_retriever(search_kwargs={"k": 3})  # top 3 similar tickets

# ===========================
# 6. LLM + Prompt
# ===========================
prompt_template = """
You are a helpful IT support assistant. Use the context below to answer the user's question.

Context from ticket database:
{context}

User query: {question}

Answer concisely and based on the context. If the answer is not in the context, respond: "I don't have that information in the ticket database."
"""

prompt = PromptTemplate.from_template(prompt_template)

llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")  # choose your model

rag_pipeline = (
    {
        "context": retriever,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

# ===========================
# 7. Query interface
# ===========================
if __name__ == "__main__":
    while True:
        query = input("\nAsk a question (or type 'exit' to quit): ")
        if query.lower() == 'exit':
            break
        answer = rag_pipeline.invoke(query)
        print("\nAnswer:", answer)
