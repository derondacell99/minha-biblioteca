import os
from datetime import date
from typing import Any

import requests
import streamlit as st
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO E ESTÉTICA PINK AESTHETIC & LILÁS
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
        --bg-main: #FFF0F5;
        --paper-bg: #FFFFFF;
        --lilac-accent: #E2D1F9;
        --pink-accent: #FFC6FF;
        --pink-hover: #FFAFCC;
        --soft-lavender: #F3E8FF;
        --text-dark: #4A3E48;
        --muted: #8C7B8E;
        --border-color: #F5D6EE;
    }
    .stApp { background-color: var(--bg-main); color: var(--text-dark); }
    [data-testid="stSidebar"] { background-color: #F8EDF8; border-right: 1px solid var(--border-color); }
    h1, h2, h3 { color: #5D3B62; font-family: sans-serif; }
    
    /* Cartões / Containers fofos com sombra rosa/lilás */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--paper-bg);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(226, 209, 249, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 6px 20px rgba(255, 198, 255, 0.5);
    }
    
    /* Botões personalizados */
    div.stButton > button[kind="primary"] {
        background-color: #E2D1F9;
        border-color: #E2D1F9;
        color: #4A3E48;
        border-radius: 10px;
        font-weight: 600;
        transition: background-color 0.2s;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #FFC6FF;
        border-color: #FFC6FF;
        color: #4A3E48;
    }
    div.stButton > button[kind="secondary"] {
        border-radius: 10px;
        border-color: var(--border-color);
        background-color: var(--paper-bg);
        color: var(--text-dark);
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: var(--soft-lavender);
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
    st.title("🌸 Minha Estante")
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
# AUTH GATE & SIDEBAR
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
    
    nav_options = ["Início", "Coleção", "Descobrir", "Autores", "Estantes"]
    current_page = st.session_state.get("page", "Início")
    if current_page not in nav_options:
        current_page = "Início"
        
    for nav_item in nav_options:
        is_active = (current_page == nav_item)
        if st.button(
            ("🌸 " if is_active else "📖 ") + nav_item,
            key="nav_btn_" + nav_item,
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state["page"] = nav_item
            st.rerun()
            
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
# 1. INÍCIO
# ============================================================
if page == "Início":
    st.title("🌸 Minha Estante")
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
# 2. COLEÇÃO (Pesquisa visível e filtros)
# ============================================================
elif page == "Coleção":
    st.title("💖 Minha Coleção")
    st.caption(f"{len(books)} livro(s) na sua biblioteca")

    all_genres = sorted({
        genre for b in books for genre in (b.get("genres") or [])
        if isinstance(genre, str) and genre.strip()
    })
    all_authors = sorted({b.get("authors", "") for b in books if b.get("authors")})
    statuses = ["Quero ler", "Lendo", "Lido", "Abandonado"]

    # Barra de busca rápida visível
    search_col, filter_col = st.columns([3, 1])
    with search_col:
        query = st.text_input("🔍 Pesquisar na sua coleção", placeholder="Buscar por título, autor ou ISBN...", key="collection_query")
    
    with filter_col:
        st.write("") # Espaçamento
        st.write("")

    with st.expander("⚙️ Filtros avançados e ordenação", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1:
            status_filter = st.multiselect("Status de leitura", statuses, default=[])
        with f2:
            genre_filter = st.multiselect("Gêneros", all_genres, default=[])
            author_filter = st.multiselect("Autores", all_authors, default=[])
        with f3:
            folder_options = {"Todas as estantes": ""}
            folder_options.update({name: fid for fid, name in folder_map.items()})
            folder_choice = st.selectbox("Estante", list(folder_options.keys()))
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
        if folder_choice != "Todas as estantes" and str(b.get("folder_id") or "") != folder_options[folder_choice]:
            continue
        filtered.append(b)

    if sort_by == "Título A–Z":
        filtered.sort(key=lambda b: b.get("title", "").casefold())
    elif sort_by == "Melhor avaliação":
        filtered.sort(key=lambda b: int(b.get("rating") or 0), reverse=True)
    elif sort_by == "Ano de publicação":
        filtered.sort(key=lambda b: b.get("first_publish_year") or 999999)

    if not filtered:
        st.info("Nenhum livro corresponde à sua busca ou filtros.")
    else:
        for idx, book in enumerate(filtered):
            book_id = str(book["id"])
            with st.container(border=True):
                c_img, c_info, c_edit = st.columns([1, 4, 2])
                with c_img:
                    if book.get("cover_url"):
                        st.image(book["cover_url"], width=90)
                    else:
                        st.caption("📖 Sem capa")
                with c_info:
                    st.markdown(f"### {book.get('title', 'Sem título')}")
                    st.caption(f"✍️ **Autor:** {book.get('authors', 'Desconhecido')}")
                    st.caption(f"📌 **Status:** {book.get('status', 'Quero ler')}")
                    
                    rating_val = int(book.get("rating") or 0)
                    if rating_val > 0:
                        st.caption(f"⭐ **Avaliação:** {'⭐' * rating_val}")
                    else:
                        st.caption("⭐ **Avaliação:** Sem nota")
                        
                    current_fid = str(book.get("folder_id") or "")
                    folder_name = folder_map.get(current_fid, "Geral")
                    st.caption(f"📁 **Estante:** {folder_name}")
                    
                    if book.get("personal_note"):
                        st.caption(f"💬 *Nota:* {book.get('personal_note')}")
                        
                with c_edit:
                    with st.expander("✏️ Editar Livro"):
                        with st.form(f"edit_{book_id}"):
                            status = st.selectbox(
                                "Status",
                                statuses,
                                index=statuses.index(book.get("status", "Quero ler"))
                                if book.get("status", "Quero ler") in statuses else 0,
                                key=f"status_{book_id}",
                            )
                            rating = st.select_
