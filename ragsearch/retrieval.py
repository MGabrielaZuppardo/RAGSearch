"""Baseline lexical reproduzível, sem downloads de modelos ou APIs."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500_000
MAX_PAGES = 200
PORTUGUESE_STOP_WORDS = (
    "a ao aos as com como da das de do dos e em essa esse esta este eu foi ha "
    "isso isto ja mais na nas nao no nos o os ou para pela pelo por qual quais "
    "quando que quem se sem ser seu sua suas seus sao um uma uns umas voce"
).split()


@dataclass(frozen=True)
class Document:
    source: str
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Chunk:
    source: str
    text: str
    number: int
    page: int | None = None


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def read_document(name: str, content: bytes) -> list[Document]:
    """Extraia texto sem salvar uploads. PDFs digitalizados precisam de OCR externo."""
    source = PurePosixPath(name.replace("\\", "/")).name
    suffix = PurePosixPath(source).suffix.lower()
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("O arquivo deve ter conteúdo e no máximo 10 MB.")
    if suffix not in {".txt", ".md", ".pdf"}:
        raise ValueError("Use um arquivo PDF, TXT ou Markdown (.md).")
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("Remova a senha do PDF antes de enviá-lo.")
            if len(reader.pages) > MAX_PAGES:
                raise ValueError("Use um PDF com até 200 páginas.")
            documents = [
                Document(source, page.extract_text() or "", number)
                for number, page in enumerate(reader.pages, start=1)
            ]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Não foi possível ler o PDF. Verifique se ele está íntegro.") from exc
    else:
        try:
            documents = [Document(source, content.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise ValueError("Salve o documento de texto com codificação UTF-8.") from exc
    documents = [doc for doc in documents if doc.text.strip()]
    if not documents:
        raise ValueError("Nenhum texto encontrado. PDFs digitalizados precisam de OCR.")
    if sum(len(doc.text) for doc in documents) > MAX_TEXT_CHARS:
        raise ValueError("O documento excede o limite de 500 mil caracteres.")
    return documents


def chunk_documents(
    documents: list[Document], chunk_size: int = 160, overlap: int = 32
) -> list[Chunk]:
    if chunk_size < 1 or not 0 <= overlap < chunk_size:
        raise ValueError("O tamanho deve ser positivo e a sobreposição menor que o tamanho.")
    chunks = []
    for document in documents:
        words = document.text.split()
        for start in range(0, len(words), chunk_size - overlap):
            chunks.append(
                Chunk(
                    document.source,
                    " ".join(words[start : start + chunk_size]),
                    len(chunks) + 1,
                    document.page,
                )
            )
            if start + chunk_size >= len(words):
                break
    return chunks


class SearchIndex:
    def __init__(self, documents: list[Document]):
        self.chunks = chunk_documents(documents)
        if not self.chunks:
            raise ValueError("Adicione documentos com texto para criar a base.")
        self.vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words=PORTUGUESE_STOP_WORDS,
        )
        try:
            self.matrix = self.vectorizer.fit_transform(chunk.text for chunk in self.chunks)
        except ValueError as exc:
            raise ValueError("Os documentos não contêm palavras suficientes para a busca.") from exc

    def search(self, question: str, top_k: int = 3, min_score: float = 0.08) -> list[Hit]:
        if not question.strip() or len(question) > 2000:
            raise ValueError("Escreva uma pergunta com 1 a 2.000 caracteres.")
        if not 1 <= top_k <= 10 or not 0 < min_score <= 1:
            raise ValueError("Use entre 1 e 10 trechos e um limiar entre 0 e 1.")
        query = self.vectorizer.transform([question])
        scores = cosine_similarity(query, self.matrix)[0]
        order = scores.argsort()[::-1][:top_k]
        return [Hit(self.chunks[i], float(scores[i])) for i in order if scores[i] >= min_score]
