import os
import base64
from datetime import date
from typing import Any

import requests
import streamlit as st
from supabase import create_client, Client
import extra_streamlit_components as stx

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
    
    div.stButton > button[kind="primary"] {
        background-color: #E2D1F9;
        border-color: #E2D1F9;
        color: #4A3E48;
        border-radius: 10px;
        font-weight: 600;
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
        background-color: #F3E8FF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

OPENLIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPENLIBRARY_AUTHOR = "https://openlibrary.org/search/authors.json"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
HEADERS = {"User-Agent": "MinhaEstantePessoal/1.0 (personal-library-app)"}

# ============================================================
# GERENCIADOR DE COOKIES & SUPABASE
# ============================================================
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

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
        "resolved_author": None,
        "notice": None,
        "page": "Início",
        "active_folder_filter": "Todas as estantes",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session()

if supabase and st.session_state["user"] is None:
    saved_access = cookie_manager.get("sb_access_token")
    saved_refresh = cookie_manager.get("sb_refresh_token")
    if saved_access and saved_refresh:
        try:
            res = supabase.auth.set_session(saved_access, saved_refresh)
            if res and res.user:
                st.session_state["user"] = res.user
                st.session_state["access_token"] = saved_access
                st.session_state["refresh_token"] = saved_refresh
                st.session_state["auth_email"] = res.user.email or ""
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
    try:
        if supabase:
            supabase.auth.sign_out()
    except Exception:
        pass
    cookie_manager.delete("sb_access_token")
    cookie_manager.delete("sb_refresh_token")
    st.session_state["user"] = None
    st.session_state["access_token"] = None
    st.session_state["refresh_token"] = None
    st.session_state["search_results"] = []
    st.session_state["author_results"] = []
    st.session_state["resolved_author"] = None
    st.session_state["active_folder_filter"] = "Todas as estantes"
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
                    
                    cookie_manager.set("sb_access_token", result.session.access_token, key="set_acc", max_age=30*24*3600)
                    cookie_manager.set("sb_refresh_token", result.session.refresh_token, key="set_ref", max_age=30*24*3600)
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
                        
                        cookie_manager.set("sb_access_token", result.session.access_token, key="set_acc_sup", max_age=30*24*3600)
                        cookie_manager.set("sb_refresh_token", result.session.refresh_token, key="set_ref_sup", max_age=30*24*3600)
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

def create_folder(name: str, cover_data: str = ""):
    supabase.table("folders").insert({"name": name.strip(), "cover_data": cover_data, "user_id": user_id()}).execute()

def update_folder(folder_id: str, name: str, cover_data: str | None = None):
    payload = {"name": name.strip()}
    if cover_data is not None:
        payload["cover_data"] = cover_data
    supabase.table("folders").update(payload).eq("id", folder_id).eq("user_id", user_id()).execute()

def delete_folder(folder_id: str):
    supabase.table("books").update({"folder_id": None}).eq("folder_id", folder_id).eq("user_id", user_id()).execute()
    supabase.table("folders").delete().eq("id", folder_id).eq("user_id", user_id()).execute()

def image_to_base64(uploaded_file) -> str:
    raw = uploaded_file.getvalue()
    if len(raw) > 2_000_000:
        raise ValueError("Escolha uma imagem de até 2 MB.")
    mime = uploaded_file.type if uploaded_file.type in ("image/png", "image/jpeg", "image/webp") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("utf-8")

# ============================================================
# BUSCA HÍBRIDA EXPANDIDA (Sem restrições de limites curtos)
# ============================================================
def normalize_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    if value is None:
        return fallback
    return str(value)

def search_google_books(term: str, limit: int = 40) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            GOOGLE_BOOKS_API,
            params={"q": term, "maxResults": limit},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("items", []):
            vi = item.get("volumeInfo", {})
            image_links = vi.get("imageLinks", {})
            cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail") or ""
            if cover_url.startswith("http://"):
                cover_url = cover_url.replace("http://", "https://", 1)
            
            isbn = ""
            for identifier in vi.get("industryIdentifiers", []):
                if identifier.get("type") in ("ISBN_13", "ISBN_10"):
                    isbn = identifier.get("identifier", "")
                    break

            pub_date = vi.get("publishedDate", "")
            year = int(pub_date[:4]) if pub_date and len(pub_date) >= 4 and pub_date[:4].isdigit() else None

            results.append({
                "work_key": f"gb_{item.get('id', '')}",
                "title": normalize_text(vi.get("title"), "Título desconhecido"),
                "authors": normalize_text(vi.get("authors"), "Autor desconhecido"),
                "first_publish_year": year,
                "cover_url": cover_url,
                "genres": vi.get("categories", [])[:8],
                "languages": [vi.get("language", "pt")],
                "isbn": isbn,
                "publisher": vi.get("publisher", ""),
                "edition_count": 1,
                "source": "Google Books"
            })
        return results
    except Exception:
        return []

def search_openlibrary(term: str, limit: int = 40) -> list[dict[str, Any]]:
    try:
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
                "genres": (doc.get("subject") or [])[:8],
                "languages": doc.get("language") or [],
                "isbn": (doc.get("isbn") or [""])[0],
                "publisher": (doc.get("publisher") or [""])[0],
                "edition_count": doc.get("edition_count", 0),
                "source": "Open Library"
            })
        return results
    except Exception:
        return []

def search_combined_catalogs(term: str) -> list[dict[str, Any]]:
    # Busca máxima em ambos os servidores simultaneamente
    gb_results = search_google_books(term, limit=40)
    ol_results = search_openlibrary(term, limit=40)
    return gb_results + ol_results

def search_author_works(author_name: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
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
            params={"limit": 100},
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
                "source": "Open Library"
            })
        return results, chosen.get("name", author_name)
    except Exception:
        return [], None

def get_work_description(work_key: str) -> str:
    if not work_key or work_key.startswith("gb_"):
        return ""
    try:
        response = requests.get(
            f"https://openlibrary.org{work_key}.json",
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        description = response.json().get("description", "")
        if isinstance(description, dict):
            return description.get("value", "")
        if isinstance(description, str):
            return description
    except Exception:
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
# 2. COLEÇÃO
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

    query = st.text_input("🔍 Pesquisar por título, autor, editora ou ISBN", value="", key="search_collection_input")

    folder_options = {"Todas as estantes": ""}
    folder_options.update({name: fid for fid, name in folder_map.items()})
    
    active_folder_name = st.session_state.get("active_folder_filter", "Todas as estantes")
    if active_folder_name not in folder_options:
        active_folder_name = "Todas as estantes"
    folder_index = list(folder_options.keys()).index(active_folder_name)

    with st.expander("⚙️ Filtros avançados e ordenação", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1:
            status_filter = st.multiselect("Status de leitura", statuses, default=[])
        with f2:
            genre_filter = st.multiselect("Gêneros", all_genres, default=[])
            author_filter = st.multiselect("Autores", all_authors, default=[])
        with f3:
            folder_choice = st.selectbox(
                "Estante", 
                list(folder_options.keys()), 
                index=folder_index,
                key="collection_folder_selectbox"
            )
            sort_by = st.selectbox("Ordenar por", ["Mais recentes", "Título A–Z", "Melhor avaliação", "Ano de publicação"])

    st.session_state["active_folder_filter"] = folder_choice

    filtered = []
    for b in books:
        b_genres = b.get("genres") or []
        combined_text = f"{b.get('title', '')} {b.get('authors', '')} {b.get('publisher', '')} {b.get('isbn', '')}"
        if query.strip() and query.strip().casefold() not in combined_text.casefold():
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
        st.info("Nenhum livro encontrado nesta estante ou com os filtros selecionados.")
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
                    if book.get("publisher"):
                        st.caption(f"🏢 **Editora:** {book.get('publisher')}")
                    st.caption(f"📌 **Status:** {book.get('status', 'Quero ler')}")
                    
                    rating_val = int(book.get("rating") or 0)
                    if rating_val > 0:
                        st.caption(f"⭐ **Avaliação:** {'⭐' * rating_val}")
                    else:
                        st.caption("⭐ **Avaliação:** Sem nota")
                        
                    current_fid = str(book.get("folder_id") or "")
                    folder_name = folder_map.get(current_fid, "Sem estante")
                    st.caption(f"📁 **Estante:** {folder_name}")
                    
                    if book.get("personal_note"):
                        st.caption(f"💬 *Nota:* {book.get('personal_note')}")
                        
                with c_edit:
                    with st.expander("✏️ Editar"):
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
                                format_func=lambda x: "Sem nota" if x == 0 else "⭐" * x,
                                key=f"rating_{book_id}",
                            )
                            folder_names = ["Sem estante"] + [f["name"] for f in folders]
                            folder_ids = [""] + [str(f["id"]) for f in folders]
                            folder_index_edit = folder_ids.index(current_fid) if current_fid in folder_ids else 0
                            chosen_folder_name = st.selectbox(
                                "Estante",
                                folder_names,
                                index=folder_index_edit,
                                key=f"folder_{book_id}",
                            )
                            publisher = st.text_input("Editora", value=book.get("publisher") or "", key=f"publisher_{book_id}")
                            personal_note = st.text_area("Nota pessoal", value=book.get("personal_note") or "", key=f"note_{book_id}")
                            
                            save = st.form_submit_button("Salvar alterações", type="primary", use_container_width=True)
                        if save:
                            try:
                                save_book({
                                    "status": status,
                                    "rating": rating,
                                    "folder_id": next((f["id"] for f in folders if f["name"] == chosen_folder_name), None),
                                    "publisher": publisher.strip(),
                                    "personal_note": personal_note.strip(),
                                }, existing_id=book_id)
                                st.session_state["notice"] = ("success", "Livro atualizado com sucesso!")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Erro ao salvar: {exc}")
                        
                        if st.button("🗑️ Excluir livro", key=f"delete_{book_id}", use_container_width=True):
                            st.session_state[f"confirm_delete_{book_id}"] = True
                        if st.session_state.get(f"confirm_delete_{book_id}"):
                            st.warning("Tem certeza?")
                            yes, no = st.columns(2)
                            if yes.button("Sim", key=f"yes_delete_{book_id}"):
                                delete_book(book_id)
                                st.session_state["notice"] = ("success", "Livro excluído.")
                                st.rerun()
                            if no.button("Não", key=f"no_delete_{book_id}"):
                                st.session_state[f"confirm_delete_{book_id}"] = False
                                st.rerun()

# ============================================================
# 3. DESCOBRIR LIVROS (Sem limitações de quantidade)
# ============================================================
elif page == "Descobrir":
    st.title("🔍 Descobrir Livros")
    st.write("Pesquise no catálogo global para encontrar seus próximos livros.")
    with st.form("search_books_form"):
        term = st.text_input("O que você quer encontrar?", placeholder="Ex.: O Pequeno Príncipe, Colleen Hoover, fantasia")
        do_search = st.form_submit_button("Buscar livros", type="primary")
    if do_search:
        if not term.strip():
            st.warning("Digite um termo para a busca.")
        else:
            try:
                with st.spinner("Consultando catálogos globais..."):
                    st.session_state["search_results"] = search_combined_catalogs(term.strip())
                if not st.session_state["search_results"]:
                    st.info("Não encontrei resultados. Tente outro termo.")
            except Exception:
                st.error("Ocorreu um imprevisto na busca. Tente novamente.")

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
                if result.get("source"):
                    meta.append(f"Fonte: {result['source']}")
                if meta:
                    st.caption(" · ".join(meta))
            with c3:
                if result.get("work_key") in existing_keys:
                    st.caption("✨ Na estante")
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
        author_submit = st.form_submit_button("Buscar obras do autor", type="primary")
    if author_submit:
        if not author_query.strip():
            st.warning("Digite o nome de um autor.")
        else:
            try:
                with st.spinner("Procurando autor e obras..."):
                    results, resolved_name = search_author_works(author_query.strip())
                    st.session_state["author_results"] = results
                    st.session_state["resolved_author"] = resolved_name
                if not results:
                    st.info("Não encontrei obras para esse autor.")
            except Exception:
                st.error("Não foi possível carregar as obras agora. Tente novamente.")
    
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
                    st.caption("✨ Na estante")
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
# 5. ESTANTES
# ============================================================
elif page == "Estantes":
    st.title("📁 Gerenciar Estantes Navegáveis")
    st.write("Crie e visualize suas estantes temáticas lado a lado com capa personalizada.")
    
    with st.expander("✨ Criar nova estante", expanded=False):
        with st.form("new_folder_form"):
            new_name = st.text_input("Nome da estante", placeholder="Ex.: Clássicos, Favoritos, Romance")
            new_cover_file = st.file_uploader("Capa da estante (opcional)", type=["png", "jpg", "jpeg", "webp"])
            create_clicked = st.form_submit_button("Criar estante", type="primary", use_container_width=True)
            
        if create_clicked:
            if not new_name.strip():
                st.warning("Digite um nome para a estante.")
            elif any(f["name"].casefold() == new_name.strip().casefold() for f in folders):
                st.warning("Já existe uma estante com esse nome.")
            else:
                try:
                    cover_base64 = ""
                    if new_cover_file is not None:
                        cover_base64 = image_to_base64(new_cover_file)
                    create_folder(new_name, cover_base64)
                    st.session_state["notice"] = ("success", "Estante criada com sucesso!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao criar estante: {exc}")

    st.divider()

    if folders:
        st.subheader("Suas Estantes")
        cols = st.columns(3)
        for idx, folder in enumerate(folders):
            fid = str(folder["id"])
            books_in_folder = [b for b in books if str(b.get("folder_id") or "") == fid]
            
            with cols[idx % 3]:
                with st.container(border=True):
                    cover_data = folder.get("cover_data")
                    if cover_data:
                        st.image(cover_data, width=110)
                    else:
                        st.markdown("### 🌸 📁")
                        
                    st.markdown(f"**{folder['name']}**")
                    st.caption(f"{len(books_in_folder)} livro(s)")
                    
                    if st.button("📂 Ver livros", key=f"view_folder_{fid}", use_container_width=True):
                        st.session_state["active_folder_filter"] = folder["name"]
                        st.session_state["page"] = "Coleção"
                        st.rerun()
                        
                    with st.expander("⚙️ Editar / Gerenciar"):
                        with st.form(f"edit_folder_{fid}"):
                            renamed = st.text_input("Nome", value=folder["name"], key=f"rename_name_{fid}")
                            new_shelf_cover = st.file_uploader("Nova capa", type=["png", "jpg", "jpeg", "webp"], key=f"file_shelf_{fid}")
                            save_folder_btn = st.form_submit_button("Salvar", type="primary", use_container_width=True)
                            
                        if save_folder_btn:
                            if not renamed.strip():
                                st.warning("O nome não pode ficar vazio.")
                            else:
                                try:
                                    updated_cover = image_to_base64(new_shelf_cover) if new_shelf_cover else None
                                    update_folder(fid, renamed, updated_cover)
                                    st.session_state["notice"] = ("success", "Estante atualizada!")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Erro ao atualizar: {exc}")
                                    
                        if st.button("🗑️ Excluir estante", key=f"del_folder_{fid}", use_container_width=True):
                            st.session_state[f"confirm_folder_{fid}"] = True
                        if st.session_state.get(f"confirm_folder_{fid}"):
                            st.warning("Excluir estante?")
                            yes, no = st.columns(2)
                            if yes.button("Sim", key=f"confirm_del_{fid}"):
                                delete_folder(fid)
                                st.session_state["notice"] = ("success", "Estante excluída. Livros mantidos.")
                                st.rerun()
                            if no.button("Não", key=f"cancel_del_{fid}"):
                                st.session_state[f"confirm_folder_{fid}"] = False
                                st.rerun()
    else:
        st.info("Você ainda não criou nenhuma estante. Clique acima em '✨ Criar nova estante'.")
