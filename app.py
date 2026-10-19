"""Execute a partir da raiz: uv run streamlit run app.py."""

import os
from pathlib import Path
from time import perf_counter

import streamlit as st
from dotenv import load_dotenv

from ragsearch.corpus import CorpusError, load_corpus
from ragsearch.generation import GenerationError, generate_answer
from ragsearch.retrieval import SearchIndex, read_document

ROOT = Path(__file__).parent
BASES = {
    "certbr": {
        "title": "Segurança digital · CERT.br",
        "description": "Orientações sobre golpes, senhas, backups e proteção de dados na internet.",
        "questions": [
            "Como conferir um boleto antes de pagar?",
            "O que fazer antes de descartar um celular?",
        ],
    },
    "example": {
        "title": "Políticas da empresa · Exemplo",
        "description": "Documentos fictícios sobre reembolsos, trabalho remoto e segurança.",
        "questions": [
            "Qual é o prazo para solicitar reembolso?",
            "Como solicitar trabalho remoto?",
        ],
    },
    "personal": {
        "title": "Meus documentos",
        "description": "Sua seleção de arquivos. Faça perguntas sobre o conteúdo que você enviou.",
        "questions": [],
    },
}
SOURCE_NAMES = {
    "fasciculo-backup.pdf": "Backup",
    "fasciculo-autenticacao.pdf": "Autenticação",
    "fasciculo-golpes-evite-fraudes.pdf": "Golpes: evite fraudes",
    "fasciculo-redes-sociais.pdf": "Redes sociais",
    "fasciculo-protecao-de-dados.pdf": "Proteção de dados",
    "reembolsos.md": "Reembolsos",
    "trabalho-remoto.md": "Trabalho remoto",
    "seguranca.md": "Segurança da informação",
}

load_dotenv()
st.set_page_config(
    page_title="RAGSearch · Seus documentos, suas fontes", page_icon="🔎", layout="wide"
)
st.markdown(
    f"<style>{(ROOT / 'ui' / 'styles.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

for key, default in {
    "index": None,
    "result": None,
    "upload_version": 0,
    "base_kind": None,
    "base_error": None,
    "question": "",
}.items():
    st.session_state.setdefault(key, default)


def clear_base():
    st.session_state.index = None
    st.session_state.result = None
    st.session_state.upload_version += 1
    st.session_state.base_kind = None
    st.session_state.base_error = None
    st.session_state.question = ""


def choose_question(question):
    # Preenche o formulário; a consulta só acontece ao confirmar o envio.
    st.session_state.question = question
    st.session_state.result = None


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
        st.session_state.base_error = str(exc)
        return
    st.session_state.index = index
    st.session_state.result = None
    st.session_state.base_kind = base_kind
    st.session_state.base_error = None
    st.session_state.question = ""


def load_examples():
    samples = sorted((ROOT / "examples" / "documents").glob("*.md"))
    build_index([(path.name, path.read_bytes()) for path in samples], base_kind="example")


def load_public_base():
    try:
        with st.spinner("Preparando os documentos do CERT.br…"):
            build_index(load_corpus(), base_kind="certbr")
    except CorpusError as exc:
        st.session_state.base_error = str(exc)


def load_uploads():
    uploads = st.session_state.get(f"uploads_{st.session_state.upload_version}", [])
    if len(uploads) > 20:
        st.session_state.base_error = "Envie no máximo 20 documentos por base."
        return
    with st.spinner("Preparando seus documentos…"):
        build_index([(file.name, file.getvalue()) for file in uploads])


with st.sidebar:
    st.header("🔎 RAGSearch")
    st.caption("SEUS DOCUMENTOS, SUAS FONTES")
    st.subheader("1. Escolha uma base")
    st.caption("Ao trocar, você passa a consultar os documentos da nova base.")
    with st.container(border=True):
        st.markdown("**Segurança digital**")
        st.caption("5 PDFs públicos do CERT.br sobre proteção na internet.")
        st.button(
            "Carregar base pública CERT.br",
            use_container_width=True,
            on_click=load_public_base,
            type="primary",
        )
    with st.container(border=True):
        st.markdown("**Políticas da empresa**")
        st.caption("Exemplo fictício com reembolsos, trabalho remoto e segurança.")
        st.button("Experimentar base de exemplo", use_container_width=True, on_click=load_examples)
    with st.expander(
        "Usar meus próprios documentos", expanded=st.session_state.base_kind == "personal"
    ):
        st.caption("PDF com texto, TXT ou Markdown · até 10 MB por arquivo · até 20 arquivos")
        uploads = st.file_uploader(
            "Adicionar documentos",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            key=f"uploads_{st.session_state.upload_version}",
        )
        st.button(
            "Criar base com meus documentos",
            disabled=not uploads,
            use_container_width=True,
            on_click=load_uploads,
        )
    st.divider()
    st.subheader("Como você quer consultar?")
    has_key = bool(os.getenv("RAG_API_KEY"))
    use_llm = st.toggle(
        "Gerar resposta com IA",
        disabled=not has_key,
        help="A pergunta e os trechos selecionados são enviados à OpenAI.",
    )
    if not has_key:
        st.caption("Busca em documentos disponível. A geração por IA ainda não foi configurada.")
    else:
        st.caption("Com IA ativa, a pergunta e os trechos selecionados são enviados à OpenAI.")
    with st.expander("Ajustes da busca"):
        top_k = st.slider("Quantidade de fontes", 1, 5, 3)
        min_score = st.slider("Filtro de relevância", 0.01, 0.50, 0.08, 0.01)
        st.caption(
            "Um filtro maior reduz os resultados. A pontuação mede proximidade textual, "
            "não a probabilidade de a resposta estar correta."
        )
    with st.expander("Sobre seus dados e a IA"):
        st.write(
            "Os documentos enviados ficam na memória desta sessão. A busca local usa seus "
            "arquivos sem enviá-los a uma API."
        )
        st.write(
            "A geração por IA requer RAG_API_KEY nas configurações seguras do ambiente "
            "ou no arquivo .env local. As chamadas podem ter custo no provedor."
        )
    st.button(
        "Limpar base e resposta",
        use_container_width=True,
        on_click=clear_base,
        disabled=st.session_state.index is None,
    )

st.caption("DOCUMENTOS → PERGUNTAS → FONTES")
st.title("Encontre o que importa nos seus documentos.")
st.write("Escolha uma base, faça uma pergunta e confira os documentos que sustentam o resultado.")

if st.session_state.base_error:
    st.error(st.session_state.base_error)

index = st.session_state.index
if index is None:
    st.subheader("Por onde você quer começar?")
    public, example = st.columns(2)
    with public, st.container(border=True):
        st.caption("BASE PÚBLICA · 5 DOCUMENTOS")
        st.subheader("Segurança digital")
        st.write("Explore as orientações do CERT.br sobre golpes, senhas e proteção de dados.")
        st.caption("Experimente: Como conferir um boleto antes de pagar?")
        st.button(
            "Começar com o CERT.br",
            type="primary",
            use_container_width=True,
            on_click=load_public_base,
        )
    with example, st.container(border=True):
        st.caption("DEMONSTRAÇÃO · 3 DOCUMENTOS FICTÍCIOS")
        st.subheader("Políticas da empresa")
        st.write("Teste perguntas sobre reembolsos, trabalho remoto e procedimentos internos.")
        st.caption("Experimente: Qual é o prazo para solicitar reembolso?")
        st.button("Começar com o exemplo", use_container_width=True, on_click=load_examples)
    st.info("Prefere usar seus arquivos? Abra “Usar meus próprios documentos” na barra lateral.")
else:
    details = BASES[st.session_state.base_kind or "personal"]
    sources = sorted({chunk.source for chunk in index.chunks})
    with st.container(border=True, key="active_base"):
        title, count = st.columns([4, 1])
        with title:
            st.caption("BASE ATIVA · SUAS PERGUNTAS SERÃO FEITAS AQUI")
            st.subheader(details["title"])
            st.write(details["description"])
        with count:
            st.metric("Documentos", len(sources))
        with st.expander("Ver os documentos desta base"):
            for source in sources:
                st.text(SOURCE_NAMES.get(source, source))
            if st.session_state.base_kind == "certbr":
                st.caption("Fonte: Cartilha de Segurança para Internet · CERT.br/NIC.br")
                st.markdown(
                    "[Site oficial](https://cartilha.cert.br/) · "
                    "[Licença CC BY-NC-ND 4.0](https://cartilha.cert.br/cc/)"
                )

    st.subheader("2. Faça sua pergunta")
    if details["questions"]:
        st.caption("Não sabe por onde começar? Escolha uma sugestão para preencher o campo.")
        for column, suggestion in zip(st.columns(2), details["questions"]):
            column.button(
                suggestion,
                key=f"suggestion_{suggestion}",
                use_container_width=True,
                on_click=choose_question,
                args=(suggestion,),
            )
    with st.form("question_form"):
        question = st.text_input(
            "O que você quer saber?",
            key="question",
            max_chars=2000,
            placeholder=(
                details["questions"][0]
                if details["questions"]
                else "Escreva uma pergunta sobre os documentos que você enviou."
            ),
        )
        submitted = st.form_submit_button("Consultar documentos", type="primary")
    if submitted:
        started = perf_counter()
        st.session_state.result = None
        try:
            hits = index.search(question, top_k=top_k, min_score=min_score)
            answer, error = None, None
            if use_llm and hits:
                with st.spinner("Preparando a resposta com as fontes encontradas…"):
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
                "generated": bool(answer),
            }
        except ValueError as exc:
            st.warning(str(exc))

    result = st.session_state.result
    if result:
        st.divider()
        st.subheader("3. Confira o resultado e as fontes")
        st.write(result["question"])
        if not result["hits"]:
            st.warning("Não encontramos trechos suficientes nesta base para responder.")
            st.write(
                f"Você está consultando **{details['title']}**. "
                "Tente reformular a pergunta com termos dos documentos ou escolha outra base."
            )
            if details["questions"]:
                st.button(
                    "Experimentar uma pergunta desta base",
                    on_click=choose_question,
                    args=(details["questions"][0],),
                )
            if st.session_state.base_kind == "certbr":
                st.caption(
                    "Para perguntas sobre reembolsos e trabalho remoto, use a base de exemplo."
                )
                st.button("Trocar para a base de exemplo", on_click=load_examples)
        else:
            if result["error"]:
                st.error(result["error"])
                st.caption("Você ainda pode conferir os trechos encontrados abaixo.")
            elif result["answer"]:
                st.markdown(result["answer"])
            else:
                st.info("Busca nos documentos: confira os trechos originais abaixo.")
            st.caption(
                f"{len(result['hits'])} fonte(s) encontrada(s) · "
                f"{'Resposta com IA' if result['generated'] else 'Trechos dos documentos'}"
            )
            for number, hit in enumerate(result["hits"], start=1):
                page = f" · página {hit.chunk.page}" if hit.chunk.page else ""
                label = f"[{number}] {SOURCE_NAMES.get(hit.chunk.source, hit.chunk.source)}{page}"
                with st.expander(label, expanded=number == 1):
                    st.text(hit.chunk.text)
                    st.caption(f"Arquivo original: {hit.chunk.source}")
            with st.expander("Detalhes da busca"):
                st.caption(
                    f"Tempo da consulta: {result['elapsed']:.2f}s · "
                    f"{len(index.chunks)} trechos pesquisáveis"
                )
                for number, hit in enumerate(result["hits"], start=1):
                    st.caption(f"Fonte [{number}] · similaridade textual {hit.score:.3f}")
                st.caption(
                    "A pontuação ajuda a ordenar os resultados; confira a evidência no texto."
                )

with st.expander("Como o RAGSearch encontra as informações?"):
    st.write(
        "Os arquivos são divididos em trechos. A busca seleciona os mais próximos da sua "
        "pergunta e mostra a origem para você conferir. Quando a IA está ativa, "
        "esses trechos também são usados para redigir a resposta."
    )
    st.caption(
        "Esta versão usa busca lexical TF-IDF. Ela pode perder sinônimos e recuperar títulos "
        "em perguntas amplas. Citações ajudam na conferência, mas não garantem correção."
    )
