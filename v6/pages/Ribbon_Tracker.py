# pages/2_Ribbon_Tracker.py

import streamlit as st
import re
import collections
import pdfminer.high_level
from pdfminer.layout import LAParams
from io import StringIO, BytesIO
from bs4 import BeautifulSoup, NavigableString
import pandas as pd
import altair as alt

from backend import update_ribbon_stock, execute_query, supabase  # ✅ Make sure you have execute_query & supabase in backend.py!

# --- Regex patterns ---
ORDER_ID_RE = re.compile(r"\d{3}-\d{7}-\d{7}")
PACK_QTY_RE = re.compile(r'(\d+)x\b')

# --- Utilities ---
def is_integer(text):
    try:
        int(text.strip())
        return True
    except ValueError:
        return False

def is_price(text):
    return "£" in text

def pdf_to_html(file: BytesIO) -> str:
    output = StringIO()
    laparams = LAParams()
    pdfminer.high_level.extract_text_to_fp(
        file,
        output,
        laparams=laparams,
        output_type="html",
        codec=None
    )
    return output.getvalue()

def clean_html(raw_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(raw_html, "html.parser")
    for span in soup.find_all("span"):
        if not span.text.strip():
            span.decompose()
    for element in soup.find_all(string=True):
        if isinstance(element, NavigableString) and not element.strip():
            element.extract()
    return soup

def normalise_colour(colour: str) -> str:
    colour = colour.replace("/", "-")
    colour = colour.replace(" and ", "-")
    colour = re.sub(r'(?<=[a-z])([A-Z])', r'-\1', colour)
    return colour.lower().strip()

# --- Amazon parser ---
def parse_amazon_orders(soup):
    orders_items = []
    all_divs = soup.find_all("div")
    total_divs = len(all_divs)
    idx = 0

    while idx < total_divs:
        div = all_divs[idx]
        if "Dispatch to:" in div.get_text():
            order_id = "UNKNOWN"
            for i in range(idx, min(idx + 50, total_divs)):
                text = all_divs[i].get_text()
                match = ORDER_ID_RE.search(text)
                if match:
                    order_id = match.group()
                    break

            quantity_idx = None
            for i in range(idx, min(idx + 200, total_divs)):
                if "Quantity  Product Details" in all_divs[i].get_text():
                    quantity_idx = i
                    break

            if quantity_idx:
                content_divs = []
                for i in range(quantity_idx + 1, total_divs):
                    t = all_divs[i].get_text().strip()
                    if t:
                        if ORDER_ID_RE.search(t):
                            break
                        content_divs.append(t)

                has_ribbons = any(
                    "Type your clip-on ribbon colour choice here" in t
                    for t in content_divs
                )
                if not has_ribbons:
                    idx += 1
                    continue

                i = 0
                while i + 2 < len(content_divs):
                    qty_text = content_divs[i]
                    desc = content_divs[i+1]
                    price = content_divs[i+2]

                    if is_integer(qty_text) and desc and is_price(price):
                        base_qty = int(qty_text)
                        is_pack = "Pack of" in desc
                        pack_size = None
                        final_qty = base_qty

                        if is_pack:
                            j = i + 3
                            while j < len(content_divs):
                                if j + 2 < len(content_divs):
                                    maybe_qty = content_divs[j]
                                    maybe_desc = content_divs[j+1]
                                    maybe_price = content_divs[j+2]
                                    if is_integer(maybe_qty) and maybe_desc and is_price(maybe_price):
                                        break
                                if ORDER_ID_RE.search(content_divs[j]):
                                    break
                                if "::" in content_divs[j] and "x" in content_divs[j]:
                                    m = PACK_QTY_RE.search(content_divs[j])
                                    if m:
                                        pack_size = int(m.group(1))
                                        final_qty = base_qty * pack_size
                                j += 1

                        ribbon_colour = ""
                        j = i + 3
                        while j < len(content_divs):
                            if j + 2 < len(content_divs):
                                maybe_qty = content_divs[j]
                                maybe_desc = content_divs[j+1]
                                maybe_price = content_divs[j+2]
                                if is_integer(maybe_qty) and maybe_desc and is_price(maybe_price):
                                    break
                            if ORDER_ID_RE.search(content_divs[j]):
                                break

                            if "Type your clip-on ribbon colour choice here" in content_divs[j]:
                                line = content_divs[j]
                                if "::" in line:
                                    colour_part = line.split("::", 1)[1].strip()
                                elif ":" in line:
                                    colour_part = line.split(":", 1)[1].strip()
                                else:
                                    colour_part = line.strip()

                                next_line = ""
                                if j + 1 < len(content_divs):
                                    next_line = content_divs[j+1].strip()
                                    next_line_words = len(next_line.split())
                                    is_just_int = False
                                    try:
                                        int(next_line)
                                        is_just_int = True
                                    except:
                                        pass

                                    if (
                                        next_line_words <= 5 and
                                        "VAT" not in next_line.upper() and
                                        "PAGE" not in next_line.upper() and
                                        "TOTAL" not in next_line.upper() and
                                        ":" not in next_line and
                                        not is_just_int and
                                        next_line
                                    ):
                                        colour_part += " " + next_line

                                ribbon_colour = normalise_colour(colour_part)
                                break

                            j += 1

                        orders_items.append({
                            "ribbon_colour": ribbon_colour,
                            "final_qty": final_qty
                        })

                        i += 3
                    else:
                        i += 1
        idx += 1

    return orders_items

# --- Supplier parser ---
def parse_supplier_clipon_ribbons(soup):
    all_divs = soup.find_all("div")
    results = []

    for idx, div in enumerate(all_divs):
        text = div.get_text().strip()

        if "Clip on Medal Ribbon" in text:
            colour = text.split("Clip on Medal Ribbon")[0].strip()
            colour = normalise_colour(colour)

            qty = 0
            if idx + 1 < len(all_divs):
                next_text = all_divs[idx + 1].get_text().strip()
                m = re.search(r"(\d+)\s*ks", next_text)
                if m:
                    qty = int(m.group(1))

            results.append({
                "ribbon_colour": colour,
                "final_qty": qty
            })

    return results

# --- Shared summary ---
def make_summary(items):
    counts = collections.Counter()
    for item in items:
        counts[item['ribbon_colour']] += int(item['final_qty'])

    df = pd.DataFrame([{"colour": k, "quantity": v} for k, v in counts.items()])
    return df

# --- Streamlit UI ---
st.title("🎀 Ribbon Tracker")

# --- Visualiser ---
st.subheader("📊 Current Ribbon Stock")
if st.button("🔄 Refresh Ribbon Stock"):
    st.session_state["refresh_stock"] = True

if "refresh_stock" not in st.session_state:
    st.session_state["refresh_stock"] = True

if st.session_state["refresh_stock"]:
    response = execute_query(supabase.table("ribbons").select("*"))
    if response.data:
        stock_df = pd.DataFrame(response.data)

        # 👉 Sort by quantity ASCENDING
        stock_df = stock_df.sort_values(by="quantity", ascending=True)

        # 📊 Visualise with Altair
        chart = (
            alt.Chart(stock_df)
            .mark_bar()
            .encode(
                x=alt.X('colour:N', sort='-y'),
                y='quantity:Q',
                tooltip=['colour:N', 'quantity:Q']
            )
            .properties(width=700, height=400)
        )

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(stock_df)

    st.session_state["refresh_stock"] = False

# --- Upload PDFs ---
uploaded_files = st.file_uploader(
    "Upload one or more PDFs (Amazon and/or Supplier)",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    all_items = []
    with st.spinner("Processing PDFs..."):
        for uploaded_file in uploaded_files:
            raw_html = pdf_to_html(uploaded_file)
            soup = clean_html(raw_html)

            html_text = soup.get_text().lower()
            if "dispatch to:" in html_text:
                parsed_items = parse_amazon_orders(soup)
                detected_type = "Amazon"
            else:
                parsed_items = parse_supplier_clipon_ribbons(soup)
                detected_type = "Supplier"

            all_items.extend(parsed_items)
            st.write(f"✔️ `{uploaded_file.name}`: Detected **{detected_type}**, found {len(parsed_items)} entries.")

    summary_df = make_summary(all_items)

    if not summary_df.empty:
        st.subheader("Combined Ribbon Summary")
        st.dataframe(summary_df, use_container_width=True)

        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Combined Ribbon Summary CSV",
            data=csv,
            file_name="combined_ribbon_summary.csv",
            mime="text/csv"
        )

        if st.button("📝 Update Supabase Ribbon Stock"):
            updates = update_ribbon_stock(summary_df)
            for colour, before, subtracted, after in updates:
                if before is None:
                    st.warning(f"⚠️ '{colour}' not found in Supabase — skipped.")
                else:
                    st.success(f"✅ '{colour}': {before} − {subtracted} = {after}")
            st.info("✔️ Supabase ribbon stock updated.")
