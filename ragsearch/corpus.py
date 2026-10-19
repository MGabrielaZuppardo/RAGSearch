"""Importe PDFs oficiais: uv run python -m ragsearch.corpus."""

import hashlib
import json
import re
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pypdf import PdfReader

from ragsearch.retrieval import MAX_FILE_BYTES, read_document

CORPUS_ROOT = Path(__file__).resolve().parents[1] / "corpora" / "certbr"
HOST = "cartilha.cert.br"


class CorpusError(RuntimeError):
    """Uma base indisponível ou incompleta não deve ser apresentada como carregada."""


class OfficialRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname != HOST:
            raise CorpusError("A fonte tentou redirecionar para fora do HTTPS oficial.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)


def _links(html: str, base: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return sorted({urljoin(base, link).split("#")[0] for link in parser.links})


def _fetch(url: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != HOST:
        raise CorpusError("O download deve usar o endereço HTTPS oficial do CERT.br.")
    try:
        request = Request(url, headers={"User-Agent": "RAGSearch/0.1 corpus-import"})
        with build_opener(OfficialRedirectHandler()).open(request, timeout=30) as response:
            if urlsplit(response.url).hostname != HOST or urlsplit(response.url).scheme != "https":
                raise CorpusError("O site redirecionou para fora da fonte oficial.")
            content = response.read(max_bytes + 1)
    except URLError as exc:
        raise CorpusError(
            "Não foi possível acessar cartilha.cert.br. Verifique a permissão de rede "
            "e tente novamente. Nenhuma base nova foi instalada."
        ) from exc
    if len(content) > max_bytes:
        raise CorpusError("O arquivo oficial excede o limite de download.")
    return content


def _license(links: list[str]) -> str:
    pattern = r"/licenses/(by(?:-nc)?(?:-sa|-nd)?)/(\d\.\d)(?:/|$)"
    for link in links:
        parsed = urlsplit(link)
        if parsed.hostname not in {"creativecommons.org", "www.creativecommons.org"}:
            continue
        match = re.match(pattern, parsed.path)
        if match:
            return f"https://creativecommons.org/licenses/{match[1]}/{match[2]}/"
    raise CorpusError(
        "Licença não identificada na página oficial. Revise antes de distribuir PDFs."
    )


def _license_from_site(index_links: list[str], index_url: str) -> tuple[str, str]:
    try:
        return _license(index_links), index_url
    except CorpusError:
        for link in index_links:
            parsed = urlsplit(link)
            if parsed.scheme == "https" and parsed.hostname == HOST and parsed.path == "/cc/":
                page_links = _links(_fetch(link, 2_000_000).decode("utf-8"), link)
                return _license(page_links), link
        raise


def _pdf_links(links: list[str]) -> list[str]:
    return [
        link
        for link in links
        if urlsplit(link).hostname == HOST
        and urlsplit(link).scheme == "https"
        and Path(urlsplit(link).path).name
        == f"fasciculo-{Path(urlsplit(link).path).parent.name}.pdf"
    ]


def load_corpus(root: Path = CORPUS_ROOT) -> list[tuple[str, bytes]]:
    snapshot = root / "snapshot"
    try:
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        if not manifest["documents"]:
            raise ValueError("Manifesto sem documentos.")
        files = []
        for document in manifest["documents"]:
            filename = document["filename"]
            if Path(filename).name != filename or not filename.endswith(".pdf"):
                raise ValueError("Nome de arquivo inválido no manifesto.")
            content = (snapshot / "pdfs" / filename).read_bytes()
            if hashlib.sha256(content).hexdigest() != document["sha256"]:
                raise ValueError("O arquivo difere do checksum registrado.")
            files.append((filename, content))
        return files
    except FileNotFoundError as exc:
        raise CorpusError(
            "Os PDFs públicos ainda não foram importados. Execute: "
            "uv run python -m ragsearch.corpus"
        ) from exc
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise CorpusError(
            "A base pública está incompleta ou foi alterada. Confira o manifesto."
        ) from exc


def import_corpus(root: Path = CORPUS_ROOT) -> list[tuple[str, bytes]]:
    if (root / "snapshot").exists():
        return load_corpus(root)
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    index_url = catalog["index_url"]
    index_links = _links(_fetch(index_url, 2_000_000).decode("utf-8"), index_url)
    license_url, license_source_url = _license_from_site(index_links, index_url)
    pdfs = _pdf_links(index_links)
    # Algumas versões do site apresentam os PDFs somente nas páginas de cada fascículo.
    if not pdfs:
        pages = [
            link
            for link in index_links
            if urlsplit(link).hostname == HOST
            and urlsplit(link).scheme == "https"
            and re.fullmatch(r"/fasciculos/[^/]+/", urlsplit(link).path)
        ]
        for page in pages[:20]:
            pdfs.extend(_pdf_links(_links(_fetch(page, 2_000_000).decode("utf-8"), page)))
    if not pdfs:
        raise CorpusError("Nenhum fascículo em PDF foi encontrado. Revise a página oficial.")
    topics = catalog["preferred_topics"]

    def priority(url):
        return next((i for i, topic in enumerate(topics) if topic in url), len(topics)), url

    selected = sorted(set(pdfs), key=priority)[: catalog["document_limit"]]
    manifest = {
        "name": catalog["name"],
        "publisher": catalog["publisher"],
        "homepage": catalog["homepage"],
        "index_url": index_url,
        "license_url": license_url,
        "license_source_url": license_source_url,
        "license_scope": "Licença oficial dos fascículos; preserve os avisos de cada PDF.",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "documents": [],
    }
    # O snapshot só aparece depois da validação de todos os downloads.
    with tempfile.TemporaryDirectory(prefix=".import-", dir=root) as temporary:
        stage = Path(temporary) / "snapshot"
        (stage / "pdfs").mkdir(parents=True)
        for url in selected:
            filename = Path(unquote(urlsplit(url).path)).name
            content = _fetch(url)
            if not content.startswith(b"%PDF-"):
                raise CorpusError("O site retornou um conteúdo que não é PDF.")
            if (stage / "pdfs" / filename).exists():
                raise CorpusError("A fonte contém nomes de arquivos duplicados.")
            try:
                read_document(filename, content)
                reader = PdfReader(BytesIO(content))
            except ValueError as exc:
                raise CorpusError(f"O PDF {filename} não pode ser usado: {exc}") from exc
            (stage / "pdfs" / filename).write_bytes(content)
            manifest["documents"].append(
                {
                    "filename": filename,
                    "url": url,
                    "bytes": len(content),
                    "pages": len(reader.pages),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        stage.rename(root / "snapshot")
    return load_corpus(root)


if __name__ == "__main__":
    try:
        documents = import_corpus()
    except CorpusError as exc:
        print(f"Importação não concluída: {exc}")
        raise SystemExit(1) from None
    print(f"Base CERT.br disponível: {len(documents)} PDFs originais, com fontes e checksums.")
