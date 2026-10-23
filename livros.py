import os
from datetime import date
from typing import Any

import requests
import streamlit as st
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO E PALETA CREME & LILÁS
# ============================================================
st.set_page_config(
    page_title="Minha Estante",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --cream-bg: #FFF1E6;
        --paper-bg: #FFFFFF;
        --lilac-accent: #CDDAFD;
        --soft-lavender: #DFE7FD;
        --soft-pink: #FAD2E1;
        --peach-light: #FDE2E4;
        --sage: #E2ECE9;
        --text-dark: #302D26;
        --muted: #777366;
        --border-color: #DFE7FD;
    }
    .stApp { background-color: var(--cream-bg); color: var(--text-dark); }
    [data-testid="stSidebar"] { background-color: #F0EFEB; border-right: 1px solid var(--border-color); }
    h1, h2, h3 { color: var(--text-dark); font-family: sans-serif; }
    
    /* Cartões / Containers elegantes com toque lilás/creme */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--paper-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(205, 218, 253, 0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 14px rgba(205, 218, 253, 0.4);
    }
    
    /* Botões personalizados */
    div.stButton > button[kind="primary"] {
        background-color: var(--lilac-accent);
        border-color: var(--lilac-accent);
        color: var(--text-dark);
        border-radius: 8px;
        font-weight: 600;
        transition: background-color 0.2s;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: var(--soft-lavender);
        border-color: var(--soft-lavender);
        color: var(--text-dark);
    }
    div.stButton > button[kind="secondary"] {
        border-radius: 8px;
        border-color: var(--border-color);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

OPENLIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPENLIBRARY_AUTHOR = "https://openlibrary.org/search/authors.json"
HEADERS = {"User-Agent": "MinhaBibliotecaPessoal/1.0 (personal-library-app)"}

# ============================================================
# SUPABASE & SESSÃO
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
        "page": "Início",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session()

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
# AUTENTICAÇÃO
# ============================================================
def auth_screen():
    st.title("📚 Minha Estante")
    st.subheader("Sua biblioteca privada")
    st.write("Entre na sua conta ou crie uma conta para sincronizar seus livros com segurança.")
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
                    st.error("Não foi possível entrar. Confira seus dados.")

    with signup_tab:
        with st.form("signup_form"):
            email_new = st.text_input("E-mail", key="signup_email")
            password_new = st.text_input("Crie uma senha (mín. 8 caracteres)", type="password", key="signup_password")
            password_confirm = st.text_input("Repita a senha", type="password", key="signup_confirm")
            submitted_new = st.form_submit_button("Criar minha conta", type="primary", use_container_width=True)
        if submitted_new:
            if not email_new.strip() or len(password_new) < 8:
                st.warning("Informe um e-mail válido e senha com pelo menos 8 caracteres.")
            elif password_new != password_confirm:
                st.warning("As senhas não coincidem.")
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
                        st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                except Exception as exc:
                    st.error(f"Não foi possível criar a conta: {exc}")

# ============================================================
# ACESSO A DADOS
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
# OPEN LIBRARY API
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
# AUTH GATE & SIDEBAR (Segmented Control)
# ============================================================
if supabase is None:
    st.error("Falta configurar a conexão com o Supabase nos secrets.")
    st.stop()

if st.session_state["user"] is None:
    auth_screen()
    st.stop()

with st.sidebar:
    st.markdown("## 🌸 Minha Estante")
    st.caption(st.session_state.get("auth_email", "Conta conectada"))
    st.divider()
    
    # Navegação com Segmented Control
    nav_options = ["Início", "Coleção", "Descobrir", "Autores", "Pastas"]
    current_page = st.session_state.get("page", "Início")
    if current_page not in nav_options:
        current_page = "Início"
        
    selected_page = st.segmented_control(
        "Navegação",
        nav_options,
        default=current_page,
        key="nav_segmented_control",
        label_visibility="collapsed"
    )
    
    if selected_page:
        st.session_state["page"] = selected_page
        
    page = st.session_state.get("page", "Início")
    
    st.divider()
    if st.button("Sair da conta", use_container_width=True):
        sign_out()

show_notice()

try:
    books = load_books()
    folders = load_folders()
except Exception as exc:
    st.error("Não consegui carregar seus dados. Confira a configuração das políticas RLS no Supabase.")
    st.exception(exc)
    st.stop()

folder_map = {str(f["id"]): f["name"] for f in folders}

# ============================================================
# 1. INÍCIO (Meus livros, lendo agora, adicionados recentemente)
# ============================================================
if page == "Início":
    st.title("📚 Minha Estante")
    st.caption("Seus livros, leituras atuais e descobertas recentes.")
    
    total = len(books)
    read_count = sum(1 for b in books if b.get("status") == "Lido")
    reading_count = sum(1 for b in books if b.get("status") == "Lendo")
    wishlist_count = sum(1 for b in books if b.get("status") == "Quero ler")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total na estante", total)
    c2.metric("Lidos", read_count)
    c3.metric("Lendo agora", reading_count)
    c4.metric("Quero ler", wishlist_count)

    st.divider()
    
    # Livros que está lendo
    st.subheader("📖 Lendo no momento")
    in_progress = [b for b in books if b.get("status") == "Lendo"]
    if not in_progress:
        st.info("Você ainda não marcou nenhum livro como “Lendo”.")
    else:
        cols = st.columns(5)
        for idx, book in enumerate(in_progress[:5]):
            with cols[idx % 5]:
                with st.container(border=True):
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=85)
                    else:
                        st.caption("📖 Sem capa")
                    st.markdown(f"**{book.get('title', 'Sem título')}**")
                    st.caption(book.get("authors", "Autor desconhecido"))

    st.subheader("✨ Adicionados recentemente")
    if not books:
        st.info("Sua estante está vazia. Vá até a aba “Descobrir” para adicionar seu primeiro título.")
    else:
        cols_recent = st.columns(5)
        for idx, book in enumerate(books[:5]):
            with cols_recent[idx % 5]:
                with st.container(border=True):
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=85)
                    else:
                        st.caption("📖 Sem capa")
                    st.markdown(f"**{book.get('title', 'Sem título')}**")
                    st.caption(book.get("authors", "Autor desconhecido"))

# ============================================================
# 2. COLEÇÃO (Cartões menores, grade com 6 colunas, expandir/minimizar detalhes)
# ============================================================
elif page == "Coleção":
    st.title("📖 Minha Coleção")
    st.caption(f"{len(books)} livro(s) na sua biblioteca")

    all_genres = sorted({
        genre for b in books for genre in (b.get("genres") or [])
        if isinstance(genre, str) and genre.strip()
    })
    all_authors = sorted({b.get("authors", "") for b in books if b.get("authors")})
    statuses = ["Quero ler", "Lendo", "Lido", "Abandonado"]

    with st.expander("🔎 Filtrar e ordenar", expanded=False):
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
        # Grade compacta com 6 colunas para cartões menores
        cols = st.columns(6)
        for idx, book in enumerate(filtered):
            with cols[idx % 6]:
                with st.container(border=True):
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=85)
                    else:
                        st.caption("📖 Sem capa")
                    st.markdown(f"**{book.get('title', 'Sem título')}**")
                    st.caption(book.get("authors", "Autor desconhecido"))
                    st.caption(f"Status: {book.get('status', 'Quero ler')}")
                    if book.get("rating"):
                        st.caption("★" * int(book["rating"]))
                    
                    book_id = str(book["id"])
                    with st.expander("⚙️ Detalhes"):
                        with st.form(f"edit_{book_id}"):
                            status = st.selectbox(
                                "Status",
                                statuses,
                                index=statuses.index(book.get("status", "Quero ler"))
                                if book.get("status", "Quero ler") in statuses else 0,
                                key=f"status_{book_id}",
                            )
                            rating = st.select_slider(
                                "Avaliação",
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
                                "Pasta",
                                folder_names,
                                index=folder_index,
                                key=f"folder_{book_id}",
                            )
                            personal_note = st.text_area("Nota pessoal", value=book.get("personal_note") or "", key=f"note_{book_id}")
                            
                            save = st.form_submit_button("Atualizar", type="primary", use_container_width=True)
                        if save:
                            try:
                                save_book({
                                    "status": status,
                                    "rating": rating,
                                    "folder_id": next((f["id"] for f in folders if f["name"] == chosen_folder_name), None),
                                    "personal_note": personal_note.strip(),
                                }, existing_id=book_id)
                                st.session_state["notice"] = ("success", "Livro atualizado.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Erro ao salvar: {exc}")
                        
                        if st.button("🗑️ Excluir", key=f"delete_{book_id}", use_container_width=True):
                            st.session_state[f"confirm_delete_{book_id}"] = True
                        if st.session_state.get(f"confirm_delete_{book_id}"):
                            st.warning("Excluir este livro?")
                            yes, no = st.columns(2)
                            if yes.button("Sim", key=f"yes_delete_{book_id}"):
                                delete_book(book_id)
                                st.session_state["notice"] = ("success", "Livro excluído.")
                                st.rerun()
                            if no.button("Não", key=f"no_delete_{book_id}"):
                                st.session_state[f"confirm_delete_{book_id}"] = False
                                st.rerun()

# ============================================================
# 3. DESCOBRIR LIVROS
# ============================================================
elif page == "Descobrir":
    st.title("🔍 Descobrir Livros")
    st.write("Pesquise no catálogo global da Open Library e adicione direto à sua estante.")
    with st.form("search_books_form"):
        term = st.text_input("O que você quer encontrar?", placeholder="Ex.: Jane Eyre, Machado de Assis, fantasia")
        limit = st.selectbox("Quantidade de resultados", [10, 20, 40], index=1)
        do_search = st.form_submit_button("Buscar", type="primary")
    if do_search:
        if not term.strip():
            st.warning("Digite um termo para a busca.")
        else:
            try:
                with st.spinner("Consultando a Open Library..."):
                    st.session_state["search_results"] = search_books(term.strip(), limit)
                if not st.session_state["search_results"]:
                    st.info("Não encontrei resultados. Tente outro termo.")
            except requests.RequestException:
                st.error("Não consegui acessar a Open Library agora. Tente novamente.")

    existing_keys = {b.get("work_key") for b in books}
    for idx, result in enumerate(st.session_state.get("search_results", [])):
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 5, 1])
            with c1:
                if result.get("cover_url"):
                    st.image(result["cover_url"], width=80)
                else:
                    st.caption("Sem capa")
            with c2:
                st.markdown(f"**{result['title']}**")
                st.caption(result["authors"])
                meta = []
                if result.get("first_publish_year"):
                    meta.append(f"Ano: {result['first_publish_year']}")
                if result.get("publisher"):
                    meta.append(f"Editora: {result['publisher']}")
                if meta:
                    st.caption(" · ".join(meta))
            with c3:
                if result.get("work_key") in existing_keys:
                    st.caption("✓ Na estante")
                else:
                    with st.form(f"add_result_{idx}"):
                        add = st.form_submit_button("＋ Adicionar", type="primary", use_container_width=True)
                    if add:
                        try:
                            record = to_book_record(result)
                            save_book(record)
                            st.session_state["notice"] = ("success", f"“{result['title']}” adicionado à estante!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao adicionar: {exc}")

# ============================================================
# 4. BUSCAR POR AUTOR
# ============================================================
elif page == "Autores":
    st.title("✍️ Buscar por Autor")
    st.write("Explore obras catalogadas de um autor específico.")
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
                st.error("Não consegui acessar a Open Library. Tente novamente.")
    
    resolved = st.session_state.get("resolved_author")
    if resolved:
        st.subheader(f"Obras de: {resolved}")
        st.caption(f"{len(st.session_state.get('author_results', []))} resultado(s).")
    
    existing_keys = {b.get("work_key") for b in books}
    for idx, result in enumerate(st.session_state.get("author_results", [])):
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 5, 1])
            with c1:
                if result.get("cover_url"):
                    st.image(result["cover_url"], width=70)
                else:
                    st.caption("Sem capa")
            with c2:
                st.markdown(f"**{result['title']}**")
                st.caption(result["authors"])
            with c3:
                if result.get("work_key") in existing_keys:
                    st.caption("✓ Na estante")
                else:
                    with st.form(f"add_author_{idx}"):
                        add = st.form_submit_button("＋ Adicionar", type="primary", use_container_width=True)
                    if add:
                        try:
                            save_book(to_book_record(result))
                            st.session_state["notice"] = ("success", f"“{result['title']}” adicionado à estante!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao adicionar: {exc}")

# ============================================================
# 5. PASTAS
# ============================================================
elif page == "Pastas":
    st.title("📁 Pastas Personalizadas")
    st.write("Organize sua coleção em estantes temáticas.")
    with st.form("new_folder_form"):
        new_name = st.text_input("Nome da nova pasta", placeholder="Ex.: Clássicos, Ficção Científica")
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
                st.error(f"Erro ao criar pasta: {exc}")

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
                                st.error(f"Erro ao renomear: {exc}")
                with col3:
                    if st.button("Excluir", key=f"del_folder_{fid}"):
                        st.session_state[f"confirm_folder_{fid}"] = True
                    if st.session_state.get(f"confirm_folder_{fid}"):
                        st.warning("Excluir pasta?")
                        if st.button("Confirmar", key=f"confirm_del_folder_{fid}"):
                            try:
                                delete_folder(fid)
                                st.session_state["notice"] = ("success", "Pasta excluída.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Erro ao excluir: {exc}")
    else:
        st.info("Você ainda não criou nenhuma pasta.")
