"""Execute a partir da raiz: uv run streamlit run app.py."""

import os
from pathlib import Path
from time import perf_counter

import streamlit as st
from dotenv import load_dotenv

from ragsearch.corpus import CorpusError, load_corpus
from ragsearch.generation import NO_EVIDENCE, GenerationError, generate_answer
from ragsearch.retrieval import SearchIndex, read_document

load_dotenv()
st.set_page_config(
    page_title="RAGSearch · Converse com seus documentos", page_icon="🔎", layout="wide"
)

st.caption("RAGSEARCH / LABORATÓRIO DE CONHECIMENTO")
st.title("Suas perguntas. Seus documentos. Fontes à vista.")
st.write("Explore uma base de conhecimento e veja os trechos que sustentam cada resposta.")

for key, default in {"index": None, "result": None, "upload_version": 0, "base_kind": None}.items():
    st.session_state.setdefault(key, default)


def clear_base():
    st.session_state.index = None
    st.session_state.result = None
    st.session_state.upload_version += 1
    st.session_state.base_kind = None


def build_index(files, base_kind="personal"):
    documents = []
    sources = set()
    try:
        for name, content in files:
            extracted = read_document(name, content)
            if extracted[0].source in sources:
                raise ValueError("Há arquivos com o mesmo nome. Renomeie-os antes de criar a base.")
            sources.add(extracted[0].source)
            documents.extend(extracted)
        if sum(len(doc.text) for doc in documents) > 2_000_000:
            raise ValueError("A base excede 2 milhões de caracteres. Use menos documentos.")
        index = SearchIndex(documents)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state.index = index
    st.session_state.result = None
    st.session_state.base_kind = base_kind
    st.success(f"Base criada com {len(files)} arquivo(s) e {len(index.chunks)} trecho(s).")


with st.sidebar:
    st.header("Sua base de conhecimento")
    st.caption("PDF com texto, TXT ou Markdown · até 10 MB por arquivo")
    uploads = st.file_uploader(
        "Adicionar documentos",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        key=f"uploads_{st.session_state.upload_version}",
    )
    if st.button("Criar base com meus documentos", disabled=not uploads, use_container_width=True):
        if len(uploads) > 20:
            st.error("Envie no máximo 20 documentos por base.")
        else:
            with st.spinner("Extraindo e indexando os documentos…"):
                build_index([(file.name, file.getvalue()) for file in uploads])
    if st.button("Experimentar base de exemplo", use_container_width=True):
        samples = sorted((Path(__file__).parent / "examples" / "documents").glob("*.md"))
        build_index([(path.name, path.read_bytes()) for path in samples], base_kind="example")
    if st.button("Carregar base pública CERT.br", use_container_width=True):
        try:
            with st.spinner("Verificando e indexando os PDFs do CERT.br…"):
                build_index(load_corpus(), base_kind="certbr")
        except CorpusError as exc:
            st.error(str(exc))
    st.button("Limpar base e resposta", use_container_width=True, on_click=clear_base)
    st.divider()
    top_k = st.slider("Trechos por busca", 1, 5, 3)
    min_score = st.slider("Similaridade mínima", 0.01, 0.50, 0.08, 0.01)
    st.caption("Similaridade é uma medida de busca, não uma probabilidade de resposta correta.")
    has_key = bool(os.getenv("RAG_API_KEY"))
    use_llm = st.toggle("Gerar resposta com IA", disabled=not has_key)
    if not has_key:
        st.caption("Modo de demonstração ativo. Para gerar respostas, configure RAG_API_KEY.")
    st.caption(
        "Documentos ficam na memória da sessão. Com IA, os trechos selecionados e a pergunta "
        "são enviados à API da OpenAI."
    )

index = st.session_state.index
if index is None:
    st.info("Carregue uma base na barra lateral ou envie seus documentos.")
    col1, col2, col3 = st.columns(3)
    col1.markdown(
        "**01 · Adicione conhecimento**\n\nDocumentos transformados em trechos pesquisáveis."
    )
    col2.markdown("**02 · Faça uma pergunta**\n\nBusca lexical seleciona o contexto mais próximo.")
    col3.markdown("**03 · Confira as fontes**\n\nLeia a evidência e avalie a resposta.")
else:
    left, right = st.columns(2)
    left.metric("Documentos na base", len({chunk.source for chunk in index.chunks}))
    right.metric("Trechos indexados", len(index.chunks))
    if st.session_state.base_kind == "example":
        st.caption(
            "Sugestões da base de exemplo: Qual é o prazo de reembolso? "
            "Como solicitar trabalho remoto? Por quanto tempo os backups são mantidos?"
        )
    elif st.session_state.base_kind == "certbr":
        st.caption(
            "Fonte: CERT.br / NIC.br · Cartilha de Segurança para Internet · "
            "https://cartilha.cert.br/"
        )
        st.caption("Experimente: Por que devo fazer backup? Como proteger minhas senhas?")
    with st.form("question_form"):
        question = st.text_input(
            "O que você quer saber?",
            max_chars=2000,
            placeholder="Qual é o prazo para solicitar reembolso?",
        )
        submitted = st.form_submit_button("Consultar documentos", type="primary")
    if submitted:
        started = perf_counter()
        st.session_state.result = None
        try:
            hits = index.search(question, top_k=top_k, min_score=min_score)
            answer = NO_EVIDENCE if not hits else None
            error = None
            if use_llm and hits:
                with st.spinner("Gerando resposta a partir das fontes…"):
                    try:
                        answer = generate_answer(
                            question,
                            hits,
                            os.environ["RAG_API_KEY"],
                            os.getenv("RAG_MODEL", "gpt-4.1-mini"),
                        )
                    except GenerationError as exc:
                        error = str(exc)
            st.session_state.result = {
                "question": question,
                "hits": hits,
                "answer": answer,
                "error": error,
                "elapsed": perf_counter() - started,
                "generated": bool(use_llm and answer and hits),
            }
        except ValueError as exc:
            st.warning(str(exc))
    result = st.session_state.result
    if result:
        st.subheader(result["question"])
        if result["error"]:
            st.error(result["error"])
        if result["answer"]:
            st.markdown(result["answer"])
        elif result["hits"] and not result["error"]:
            st.info(
                "Demonstração de recuperação: estes são os trechos encontrados. "
                "Ative a geração por IA para obter uma resposta sintetizada."
            )
        st.caption(
            f"{'Resposta com IA' if result['generated'] else 'Busca local'} · "
            f"{result['elapsed']:.2f}s · {len(result['hits'])} fonte(s)"
        )
        for number, hit in enumerate(result["hits"], start=1):
            page = f" · página {hit.chunk.page}" if hit.chunk.page else ""
            label = f"[{number}] {hit.chunk.source}{page} · similaridade {hit.score:.3f}"
            with st.expander(label, expanded=True):
                st.text(hit.chunk.text)

with st.expander("Como funciona este projeto?"):
    st.markdown(
        "**Ingestão → trechos com sobreposição → TF-IDF → similaridade de cosseno → "
        "contexto → geração opcional com citações.**\n\n"
        "Esta versão usa busca lexical. Ela pode perder sinônimos e paráfrases; "
        "embeddings semânticos e busca híbrida são próximos experimentos. "
        "Citações ajudam a inspecionar a resposta, mas exigem conferência humana."
    )
