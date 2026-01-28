import os
import pickle
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticChunker:
    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 500):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.model = None

    def _get_model(self):
        if self.model is None:
            self.model = SentenceTransformer('intfloat/e5-base-v2')
        return self.model

    def _split_sentences(self, text: str) -> List[str]:
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if char in '.!?\n':
                if current.strip():
                    sentences.append(current.strip())
                current = ""
        
        if current.strip():
            sentences.append(current.strip())
        
        return sentences

    def _calculate_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        return cosine_similarity([emb1], [emb2])[0][0]

    def chunk_text(self, text: str, source: str = "", page_num: int = 1) -> List[Dict[str, Any]]:
        sentences = self._split_sentences(text)
        
        if not sentences:
            return []
        
        model = self._get_model()
        embeddings = model.encode([f"passage: {s}" for s in sentences])
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)
            
            if current_length + sentence_len > self.max_chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                if len(chunk_text) >= self.min_chunk_size:
                    chunks.append({
                        "text": chunk_text,
                        "source": source,
                        "page_num": page_num,
                        "chunk_index": len(chunks)
                    })
                current_chunk = [sentence]
                current_length = sentence_len
                continue
            
            if not current_chunk:
                current_chunk.append(sentence)
                current_length = sentence_len
                continue
            
            if i > 0:
                similarity = self._calculate_similarity(embeddings[i-1], embeddings[i])
                
                if similarity < 0.5 and current_length >= self.min_chunk_size:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        "text": chunk_text,
                        "source": source,
                        "page_num": page_num,
                        "chunk_index": len(chunks)
                    })
                    current_chunk = [sentence]
                    current_length = sentence_len
                else:
                    current_chunk.append(sentence)
                    current_length += sentence_len
            else:
                current_chunk.append(sentence)
                current_length += sentence_len
        
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size or not chunks:
                chunks.append({
                    "text": chunk_text,
                    "source": source,
                    "page_num": page_num,
                    "chunk_index": len(chunks)
                })
        
        return chunks


class EmbeddingGenerator:
    def __init__(self):
        self.model = None

    def _get_model(self):
        if self.model is None:
            self.model = SentenceTransformer('intfloat/e5-base-v2')
        return self.model

    def generate_embedding(self, text: str) -> np.ndarray:
        model = self._get_model()
        return model.encode(f"passage: {text}")

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        model = self._get_model()
        return model.encode([f"passage: {t}" for t in texts])

    def generate_query_embedding(self, query: str) -> np.ndarray:
        model = self._get_model()
        return model.encode(f"query: {query}")

    def embedding_to_blob(self, embedding: np.ndarray) -> bytes:
        return pickle.dumps(embedding)

    def blob_to_embedding(self, blob: bytes) -> np.ndarray:
        return pickle.loads(blob)
