import os
from datetime import date
from typing import Any

import requests
import streamlit as st
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Minha Biblioteca",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta: papel creme, verde-oliva e marrom
st.markdown(
    """
    <style>
    :root {
        --cream: #F7F3E8;
        --paper: #FFFCF4;
        --olive: #65734A;
        --olive-dark: #465336;
        --brown: #70543E;
        --ink: #302D26;
        --muted: #777366;
    }
    .stApp { background: var(--cream); color: var(--ink); }
    [data-testid="stSidebar"] { background: #EAE5D6; }
    h1, h2, h3 { color: var(--olive-dark); }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--paper);
        border-color: #D8D0BC;
        border-radius: 14px;
    }
    .book-title { color: var(--olive-dark); font-size: 1.04rem; font-weight: 700; }
    .small-muted { color: var(--muted); font-size: .88rem; }
    div.stButton > button[kind="primary"] {
        background: var(--olive);
        border-color: var(--olive);
        color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        background: var(--olive-dark);
        border-color: var(--olive-dark);
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📚 Minha Biblioteca")
st.caption("Sua estante pessoal: organize, descubra e acompanhe suas leituras.")

OPENLIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPENLIBRARY_AUTHOR = "https://openlibrary.org/search/authors.json"
HEADERS = {"User-Agent": "MinhaBibliotecaPessoal/1.0 (personal-library-app)"}

# ============================================================
# SUPABASE
# ============================================================
def get_supabase() -> Client | None:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None

supabase = get_supabase()

def init_session():
    defaults = {
        "user": None,
        "access_token": None,
        "refresh_token": None,
        "auth_email": "",
        "search_results": [],
        "author_results": [],
        "selected_book": None,
        "notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session()

# Restaura a sessão do Supabase após reloads do Streamlit
if supabase and st.session_state.get("access_token") and st.session_state.get("refresh_token"):
    try:
        supabase.auth.set_session(
            st.session_state["access_token"],
            st.session_state["refresh_token"]
        )
    except Exception:
        pass

def show_notice():
    notice = st.session_state.get("notice")
    if notice:
        kind, message = notice
        if kind == "success":
            st.success(message)
        elif kind == "error":
            st.error(message)
        else:
            st.info(message)
        st.session_state["notice"] = None

def sign_out():
    st.session_state["user"] = None
    st.session_state["access_token"] = None
    st.session_state["refresh_token"] = None
    st.session_state["search_results"] = []
    st.session_state["author_results"] = []
    st.session_state["selected_book"] = None
    st.rerun()

# ============================================================
# AUTHENTICATION
# ============================================================
def auth_screen():
    st.subheader("Sua biblioteca privada")
    st.write("Entre na sua conta ou crie uma conta para sincronizar os livros entre computadores.")
    login_tab, signup_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("E-mail", key="login_email")
            password = st.text_input("Senha", type="password", key="login_password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            if not email.strip() or not password:
                st.warning("Preencha o e-mail e a senha.")
            else:
                try:
                    result = supabase.auth.sign_in_with_password(
                        {"email": email.strip(), "password": password}
                    )
                    st.session_state["user"] = result.user
                    st.session_state["access_token"] = result.session.access_token
                    st.session_state["refresh_token"] = result.session.refresh_token
                    st.session_state["auth_email"] = email.strip()
                    st.rerun()
                except Exception:
                    st.error("Não foi possível entrar. Confira os dados e, se necessário, confirme seu e-mail.")

    with signup_tab:
        with st.form("signup_form"):
            email_new = st.text_input("E-mail", key="signup_email")
            password_new = st.text_input("Crie uma senha", type="password", key="signup_password")
            password_confirm = st.text_input("Repita a senha", type="password", key="signup_confirm")
            submitted_new = st.form_submit_button("Criar minha conta", type="primary", use_container_width=True)
        if submitted_new:
            if not email_new.strip() or len(password_new) < 8:
                st.warning("Informe um e-mail e uma senha com pelo menos 8 caracteres.")
            elif password_new != password_confirm:
                st.warning("As senhas não são iguais.")
            else:
                try:
                    result = supabase.auth.sign_up(
                        {"email": email_new.strip(), "password": password_new}
                    )
                    if result.session:
                        st.session_state["user"] = result.user
                        st.session_state["access_token"] = result.session.access_token
                        st.session_state["refresh_token"] = result.session.refresh_token
                        st.session_state["auth_email"] = email_new.strip()
                        st.rerun()
                    else:
                        st.success("Conta criada! Se a confirmação de e-mail estiver ativa, confirme seu endereço e depois entre.")
                except Exception as exc:
                    st.error(f"Não foi possível criar a conta: {exc}")

# ============================================================
# DATA ACCESS
# ============================================================
def user_id() -> str:
    return str(st.session_state["user"].id)

def load_books() -> list[dict[str, Any]]:
    result = (
        supabase.table("books")
        .select("*")
        .eq("user_id", user_id())
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []

def load_folders() -> list[dict[str, Any]]:
    result = (
        supabase.table("folders")
        .select("*")
        .eq("user_id", user_id())
        .order("name")
        .execute()
    )
    return result.data or []

def save_book(book: dict[str, Any], existing_id: str | None = None):
    payload = {**book, "user_id": user_id()}
    if existing_id:
        supabase.table("books").update(payload).eq("id", existing_id).eq("user_id", user_id()).execute()
    else:
        supabase.table("books").insert(payload).execute()

def delete_book(book_id: str):
    supabase.table("books").delete().eq("id", book_id).eq("user_id", user_id()).execute()

def create_folder(name: str):
    supabase.table("folders").insert({"name": name.strip(), "user_id": user_id()}).execute()

def rename_folder(folder_id: str, name: str):
    supabase.table("folders").update({"name": name.strip()}).eq("id", folder_id).eq("user_id", user_id()).execute()

def delete_folder(folder_id: str):
    supabase.table("books").update({"folder_id": None}).eq("folder_id", folder_id).eq("user_id", user_id()).execute()
    supabase.table("folders").delete().eq("id", folder_id).eq("user_id", user_id()).execute()

# ============================================================
# OPEN LIBRARY SEARCH
# ============================================================
def normalize_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    if value is None:
        return fallback
    return str(value)

def search_books(term: str, limit: int = 20) -> list[dict[str, Any]]:
    response = requests.get(
        OPENLIBRARY_SEARCH,
        params={
            "q": term,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,cover_i,subject,language,isbn,publisher,edition_count",
        },
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for doc in data.get("docs", []):
        work_key = doc.get("key", "")
        cover_id = doc.get("cover_i")
        results.append({
            "work_key": work_key,
            "title": normalize_text(doc.get("title"), "Título desconhecido"),
            "authors": normalize_text(doc.get("author_name"), "Autor desconhecido"),
            "first_publish_year": doc.get("first_publish_year"),
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
            "genres": (doc.get("subject") or [])[:12],
            "languages": doc.get("language") or [],
            "isbn": (doc.get("isbn") or [""])[0],
            "publisher": (doc.get("publisher") or [""])[0],
            "edition_count": doc.get("edition_count", 0),
        })
    return results

def search_author_works(author_name: str, limit: int = 100) -> tuple[list[dict[str, Any]], str | None]:
    response = requests.get(
        OPENLIBRARY_AUTHOR,
        params={"q": author_name, "limit": 10},
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    docs = response.json().get("docs", [])
    if not docs:
        return [], None

    chosen = next(
        (d for d in docs if d.get("name", "").casefold() == author_name.casefold()),
        docs[0],
    )
    author_key = chosen.get("key")
    if not author_key:
        return [], chosen.get("name")

    works_response = requests.get(
        f"https://openlibrary.org{author_key}/works.json",
        params={"limit": limit},
        headers=HEADERS,
        timeout=20,
    )
    works_response.raise_for_status()
    works = works_response.json().get("entries", [])
    results = []
    for work in works:
        cover_ids = work.get("covers") or []
        cover_id = next((x for x in cover_ids if isinstance(x, int) and x > 0), None)
        results.append({
            "work_key": work.get("key", ""),
            "title": normalize_text(work.get("title"), "Título desconhecido"),
            "authors": chosen.get("name", author_name),
            "first_publish_year": None,
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
            "genres": [],
            "languages": [],
            "isbn": "",
            "publisher": "",
            "edition_count": 0,
        })
    return results, chosen.get("name", author_name)

def get_work_description(work_key: str) -> str:
    if not work_key:
        return ""
    try:
        response = requests.get(
            f"https://openlibrary.org{work_key}.json",
            headers=HEADERS,
            timeout=12,
        )
        response.raise_for_status()
        description = response.json().get("description", "")
        if isinstance(description, dict):
            return description.get("value", "")
        if isinstance(description, str):
            return description
    except requests.RequestException:
        pass
    return ""

def to_book_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": result["title"],
        "authors": result["authors"],
        "work_key": result.get("work_key", ""),
        "cover_url": result.get("cover_url", ""),
        "description": get_work_description(result.get("work_key", "")),
        "genres": result.get("genres", []),
        "country": "",
        "status": "Quero ler",
        "rating": 0,
        "personal_note": "",
        "date_started": None,
        "date_finished": None,
        "folder_id": None,
        "first_publish_year": result.get("first_publish_year"),
        "isbn": result.get("isbn", ""),
        "publisher": result.get("publisher", ""),
    }

# ============================================================
# AUTH GATE
# ============================================================
if supabase is None:
    st.error("Falta configurar a conexão com o Supabase.")
    st.markdown(
        """
        Crie `.streamlit/secrets.toml` na pasta do projeto com:

        ```toml
        SUPABASE_URL = "[https://SEU-PROJETO.supabase.co](https://SEU-PROJETO.supabase.co)"
        SUPABASE_ANON_KEY = "SUA_CHAVE_ANON_PUBLIC"
        ```

        Use a URL e a chave pública/anon do seu projeto Supabase. **Nunca coloque a chave `service_role` neste aplicativo.**
        """
    )
    st.stop()

if st.session_state["user"] is None:
    auth_screen()
    st.stop()

# Sidebar
with st.sidebar:
    st.markdown("## 🌿 Minha estante")
    st.caption(st.session_state.get("auth_email", "Conta conectada"))
    page = st.radio(
        "Navegação",
        ["Visão geral", "Minha coleção", "Descobrir livros", "Buscar por autor", "Pastas"],
    )
    if st.button("Sair da conta", use_container_width=True):
        sign_out()

show_notice()

try:
    books = load_books()
    folders = load_folders()
except Exception as exc:
    st.error("Não consegui carregar seus dados. Confira a configuração do banco Supabase.")
    st.exception(exc)
    st.stop()

folder_map = {str(f["id"]): f["name"] for f in folders}

# ============================================================
# DASHBOARD
# ============================================================
if page == "Visão geral":
    st.header("Sua biblioteca, no seu ritmo")
    total = len(books)
    read_count = sum(1 for b in books if b.get("status") == "Lido")
    reading_count = sum(1 for b in books if b.get("status") == "Lendo")
    wishlist_count = sum(1 for b in books if b.get("status") == "Quero ler")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Livros na estante", total)
    c2.metric("Lidos", read_count)
    c3.metric("Lendo", reading_count)
    c4.metric("Quero ler", wishlist_count)

    st.divider()
    st.subheader("Continue de onde parou")
    in_progress = [b for b in books if b.get("status") == "Lendo"]
    if not in_progress:
        st.info("Você ainda não marcou nenhum livro como “Lendo”.")
    else:
        cols = st.columns(4)
        for idx, book in enumerate(in_progress[:8]):
            with cols[idx % 4]:
                with st.container(border=True):
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=105)
                    st.markdown(f"**{book['title']}**")
                    st.caption(book.get("authors", "Autor desconhecido"))

    st.subheader("Adicionados recentemente")
    if not books:
        st.info("Sua estante está vazia. Abra “Descobrir livros” para adicionar seu primeiro título.")
    else:
        for book in books[:5]:
            with st.container(border=True):
                col1, col2 = st.columns([1, 8])
                with col1:
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=65)
                with col2:
                    st.markdown(f"**{book['title']}**")
                    st.caption(f"{book.get('authors', 'Autor desconhecido')} · {book.get('status', 'Quero ler')}")

# ============================================================
# COLLECTION
# ============================================================
elif page == "Minha coleção":
    st.header("Minha coleção")
    st.caption(f"{len(books)} livro(s) na sua biblioteca")

    all_genres = sorted({
        genre for b in books for genre in (b.get("genres") or [])
        if isinstance(genre, str) and genre.strip()
    })
    all_authors = sorted({b.get("authors", "") for b in books if b.get("authors")})
    statuses = ["Quero ler", "Lendo", "Lido", "Abandonado"]

    with st.expander("🔎 Filtrar e ordenar", expanded=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            query = st.text_input("Título, autor ou ISBN", key="collection_query")
            status_filter = st.multiselect("Status de leitura", statuses, default=[])
        with f2:
            genre_filter = st.multiselect("Gêneros", all_genres, default=[])
            author_filter = st.multiselect("Autores", all_authors, default=[])
        with f3:
            folder_options = {"Todas as pastas": ""}
            folder_options.update({name: fid for fid, name in folder_map.items()})
            folder_choice = st.selectbox("Pasta", list(folder_options.keys()))
            sort_by = st.selectbox("Ordenar por", ["Mais recentes", "Título A–Z", "Melhor avaliação", "Ano de publicação"])

    filtered = []
    for b in books:
        b_genres = b.get("genres") or []
        if query and query.casefold() not in " ".join([
            b.get("title", ""), b.get("authors", ""), b.get("isbn", "")
        ]).casefold():
            continue
        if status_filter and b.get("status") not in status_filter:
            continue
        if genre_filter and not set(genre_filter).intersection(set(b_genres)):
            continue
        if author_filter and b.get("authors", "") not in author_filter:
            continue
        if folder_choice != "Todas as pastas" and str(b.get("folder_id") or "") != folder_options[folder_choice]:
            continue
        filtered.append(b)

    if sort_by == "Título A–Z":
        filtered.sort(key=lambda b: b.get("title", "").casefold())
    elif sort_by == "Melhor avaliação":
        filtered.sort(key=lambda b: int(b.get("rating") or 0), reverse=True)
    elif sort_by == "Ano de publicação":
        filtered.sort(key=lambda b: b.get("first_publish_year") or 999999)

    if not filtered:
        st.info("Nenhum livro corresponde aos filtros selecionados.")
    else:
        cols = st.columns(5)
        for idx, book in enumerate(filtered):
            with cols[idx % 5]:
                with st.container(border=True):
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=115)
                    else:
                        st.caption("📖 Sem capa")
                    st.markdown(f"**{book.get('title', 'Sem título')}**")
                    st.caption(book.get("authors", "Autor desconhecido"))
                    st.caption(f"Status: {book.get('status', 'Quero ler')}")
                    if book.get("rating"):
                        st.caption("★" * int(book["rating"]))
                    book_id = str(book["id"])
                    with st.expander("Detalhes / editar"):
                        with st.form(f"edit_{book_id}"):
                            status = st.selectbox(
                                "Status",
                                statuses,
                                index=statuses.index(book.get("status", "Quero ler"))
                                if book.get("status", "Quero ler") in statuses else 0,
                                key=f"status_{book_id}",
                            )
                            rating = st.select_slider(
                                "Sua avaliação",
                                options=[0, 1, 2, 3, 4, 5],
                                value=int(book.get("rating") or 0),
                                format_func=lambda x: "Sem nota" if x == 0 else "★" * x,
                                key=f"rating_{book_id}",
                            )
                            folder_names = ["Sem pasta"] + [f["name"] for f in folders]
                            folder_ids = [""] + [str(f["id"]) for f in folders]
                            current_folder = str(book.get("folder_id") or "")
                            folder_index = folder_ids.index(current_folder) if current_folder in folder_ids else 0
                            chosen_folder_name = st.selectbox(
                                "Pasta personalizada",
                                folder_names,
                                index=folder_index,
                                key=f"folder_{book_id}",
                            )
                            country = st.text_input("País (autor ou edição)", value=book.get("country") or "", key=f"country_{book_id}")
                            personal_note = st.text_area("Sua nota", value=book.get("personal_note") or "", key=f"note_{book_id}")
                            started = st.date_input(
                                "Data de início",
                                value=date.fromisoformat(book["date_started"]) if book.get("date_started") else None,
                                key=f"started_{book_id}",
                            )
                            finished = st.date_input(
                                "Data de conclusão",
                                value=date.fromisoformat(book["date_finished"]) if book.get("date_finished") else None,
                                key=f"finished_{book_id}",
                            )
                            save = st.form_submit_button("Salvar alterações", type="primary", use_container_width=True)
                        if save:
                            try:
                                save_book({
                                    "status": status,
                                    "rating": rating,
                                    "folder_id": next((f["id"] for f in folders if f["name"] == chosen_folder_name), None),
                                    "country": country.strip(),
                                    "personal_note": personal_note.strip(),
                                    "date_started": started.isoformat() if started else None,
                                    "date_finished": finished.isoformat() if finished else None,
                                }, existing_id=book_id)
                                st.session_state["notice"] = ("success", "Livro atualizado.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível salvar: {exc}")
                        if st.button("Excluir livro", key=f"delete_{book_id}", use_container_width=True):
                            st.session_state[f"confirm_delete_{book_id}"] = True
                        if st.session_state.get(f"confirm_delete_{book_id}"):
                            st.warning("Tem certeza? Esta ação não pode ser desfeita.")
                            yes, no = st.columns(2)
                            if yes.button("Sim, excluir", key=f"yes_delete_{book_id}"):
                                delete_book(book_id)
                                st.session_state["notice"] = ("success", "Livro excluído.")
                                st.rerun()
                            if no.button("Cancelar", key=f"no_delete_{book_id}"):
                                st.session_state[f"confirm_delete_{book_id}"] = False
                                st.rerun()

# ============================================================
# DISCOVER BOOKS
# ============================================================
elif page == "Descobrir livros":
    st.header("Descobrir livros")
    st.write("Pesquise por título, autor ou assunto. Você poderá escolher entre vários resultados.")
    with st.form("search_books_form"):
        term = st.text_input("O que você quer encontrar?", placeholder="Ex.: Jane Eyre, Machado de Assis, fantasia")
        limit = st.selectbox("Quantidade de resultados", [10, 20, 40], index=1)
        do_search = st.form_submit_button("Buscar", type="primary")
    if do_search:
        if not term.strip():
            st.warning("Digite um título, autor ou assunto.")
        else:
            try:
                with st.spinner("Consultando a Open Library..."):
                    st.session_state["search_results"] = search_books(term.strip(), limit)
                if not st.session_state["search_results"]:
                    st.info("Não encontrei resultados. Tente outro termo.")
            except requests.RequestException:
                st.error("Não consegui acessar a Open Library agora. Verifique a conexão e tente novamente.")

    for idx, result in enumerate(st.session_state["search_results"]):
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 4, 1])
            with c1:
                if result.get("cover_url"):
                    st.image(result["cover_url"], width=95)
                else:
                    st.caption("Sem capa")
            with c2:
                st.markdown(f"**{result['title']}**")
                st.caption(result["authors"])
                meta = []
                if result.get("first_publish_year"):
                    meta.append(f"Primeira publicação: {result['first_publish_year']}")
                if result.get("edition_count"):
                    meta.append(f"{result['edition_count']} edição(ões)")
                if result.get("publisher"):
                    meta.append(f"Editora: {result['publisher']}")
                if meta:
                    st.caption(" · ".join(meta))
                if result.get("genres"):
                    st.caption("Gêneros/assuntos: " + ", ".join(result["genres"][:5]))
            with c3:
                with st.form(f"add_result_{idx}"):
                    add = st.form_submit_button("＋ Adicionar", type="primary", use_container_width=True)
                if add:
                    try:
                        record = to_book_record(result)
                        save_book(record)
                        st.session_state["notice"] = ("success", f"“{result['title']}” foi adicionado à sua biblioteca.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível adicionar o livro: {exc}")

# ============================================================
# AUTHOR SEARCH
# ============================================================
elif page == "Buscar por autor":
    st.header("Obras de um autor")
    st.write("Busque um autor para listar as obras catalogadas pela Open Library.")
    with st.form("author_search_form"):
        author_query = st.text_input("Nome do autor", placeholder="Ex.: Charlotte Brontë")
        author_limit = st.selectbox("Máximo de obras", [25, 50, 100], index=2)
        author_submit = st.form_submit_button("Buscar obras", type="primary")
    if author_submit:
        if not author_query.strip():
            st.warning("Digite o nome de um autor.")
        else:
            try:
                with st.spinner("Procurando autor e obras..."):
                    results, resolved_name = search_author_works(author_query.strip(), author_limit)
                    st.session_state["author_results"] = results
                    st.session_state["resolved_author"] = resolved_name
                if not results:
                    st.info("Não encontrei obras para esse autor.")
            except requests.RequestException:
                st.error("Não consegui acessar a Open Library agora. Tente novamente.")
    resolved = st.session_state.get("resolved_author")
    if resolved:
        st.subheader(f"Obras encontradas: {resolved}")
        st.caption(f"{len(st.session_state['author_results'])} resultado(s). A lista depende da cobertura do catálogo.")
    results = st.session_state["author_results"]
    if results:
        for idx, result in enumerate(results):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 5, 1])
                with c1:
                    if result.get("cover_url"):
                        st.image(result["cover_url"], width=75)
                    else:
                        st.caption("Sem capa")
                with c2:
                    st.markdown(f"**{result['title']}**")
                    st.caption(result["authors"])
                with c3:
                    with st.form(f"add_author_{idx}"):
                        add = st.form_submit_button("＋ Adicionar", type="primary", use_container_width=True)
                    if add:
                        try:
                            save_book(to_book_record(result))
                            st.session_state["notice"] = ("success", f"“{result['title']}” foi adicionado à sua biblioteca.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível adicionar o livro: {exc}")

# ============================================================
# FOLDERS
# ============================================================
elif page == "Pastas":
    st.header("Pastas personalizadas")
    st.write("Crie suas próprias estantes. Excluir uma pasta não exclui os livros: eles voltam a ficar sem pasta.")
    with st.form("new_folder_form"):
        new_name = st.text_input("Nome da nova pasta", placeholder="Ex.: Literatura brasileira")
        create = st.form_submit_button("Criar pasta", type="primary")
    if create:
        if not new_name.strip():
            st.warning("Digite um nome para a pasta.")
        elif any(f["name"].casefold() == new_name.strip().casefold() for f in folders):
            st.warning("Já existe uma pasta com esse nome.")
        else:
            try:
                create_folder(new_name)
                st.session_state["notice"] = ("success", "Pasta criada.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível criar a pasta: {exc}")

    if folders:
        st.subheader("Suas pastas")
        for folder in folders:
            fid = str(folder["id"])
            with st.container(border=True):
                books_in_folder = sum(1 for b in books if str(b.get("folder_id") or "") == fid)
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**📁 {folder['name']}**")
                    st.caption(f"{books_in_folder} livro(s)")
                with col2:
                    with st.form(f"rename_folder_{fid}"):
                        renamed = st.text_input("Renomear", value=folder["name"], key=f"rename_name_{fid}")
                        rename = st.form_submit_button("Salvar nome")
                    if rename:
                        if not renamed.strip():
                            st.warning("O nome não pode ficar vazio.")
                        elif any(f["id"] != folder["id"] and f["name"].casefold() == renamed.strip().casefold() for f in folders):
                            st.warning("Já existe uma pasta com esse nome.")
                        else:
                            try:
                                rename_folder(fid, renamed)
                                st.session_state["notice"] = ("success", "Pasta renomeada.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível renomear: {exc}")
                with col3:
                    if st.button("Excluir", key=f"del_folder_{fid}"):
                        st.session_state[f"confirm_folder_{fid}"] = True
                    if st.session_state.get(f"confirm_folder_{fid}"):
                        st.warning("Excluir?")
                        if st.button("Confirmar", key=f"confirm_del_folder_{fid}"):
                            try:
                                delete_folder(fid)
                                st.session_state["notice"] = ("success", "Pasta excluída. Os livros foram preservados.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível excluir: {exc}")
    else:
        st.info("Você ainda não criou nenhuma pasta.")
