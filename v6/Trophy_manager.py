import time
import streamlit as st
from st_supabase_connection import SupabaseConnection, execute_query
import pandas as pd
import math
import streamlit_antd_components as sac
from streamlit_scroll_to_top import scroll_to_here

st.set_page_config(
    page_title="Trophy Manager",
    page_icon="🏆",
)

from utils import load_data

# Initialize scroll states
if 'scroll_to_top' not in st.session_state:
    st.session_state.scroll_to_top = False

# Initialize connection and grab URL from secrets
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

materials_dict = {
    'trophies': ['acrylic', 'wood', 'glass', 'metal'],
    'medals': ['acrylic', 'wood', 'metal']
}

singular_to_plural = {
    'trophy': 'trophies',
    'medal': 'medals'
}

# Handle scrolling when needed
if st.session_state.scroll_to_top:
    scroll_to_here(0, key='top')
    st.session_state.scroll_to_top = False

# Initialize session state and load data on first run
if 'initialized' not in st.session_state:
    st.session_state['initialized'] = True
    st.session_state['order'] = {}
    st.session_state['products'] = load_data(materials_dict)

st.title("Trophy Monster Product Manager")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    load_data(materials_dict)

# Function to trigger scroll to top
def trigger_scroll_to_top():
    st.session_state.scroll_to_top = True
    st.rerun()

# Initialise the order in session state
if 'order' not in st.session_state:
    st.session_state['order'] = {}

# Initialise the products in session state for other page
if 'products' not in st.session_state:
    st.session_state['products'] = pd.DataFrame()

# Function to create a unique key for the order (internal use only)
def create_order_key(product_code, size):
    return f"{product_code}_{size}"

# Function to add items to the order
def add_to_order(product_code, quantity, notes="", size=""):
    order_key = create_order_key(product_code, size)
    if order_key in st.session_state['order']:
        st.session_state['order'][order_key]['quantity'] += quantity
        st.session_state['order'][order_key]['notes'] = notes
    else:
        st.session_state['order'][order_key] = {
            "product": product_code,
            "quantity": quantity,
            "notes": notes
        }
    trigger_scroll_to_top()

# Function to display the order table
def display_order_table():
    if st.session_state.get('order', {}):
        order_data = {
            "Product": [],
            "Description": [],
            "Quantity": []
        }

        for order_key, details in st.session_state['order'].items():
            order_data["Product"].append(details["product"])
            order_data["Description"].append(details["notes"])
            order_data["Quantity"].append(details["quantity"])

        df = pd.DataFrame(order_data)

        event = st.dataframe(
            df,
            key="data",
            on_select="rerun",
            selection_mode=["multi-row"],
            hide_index="true",
            use_container_width=True
        )

        delete_button_clicked = st.button("Delete selected items", key="delete_button")

        if delete_button_clicked and event and 'rows' in event.selection:
            selected_indices = event.selection['rows']
            for index in selected_indices:
                product_code = df.iloc[index]['Product']
                description = df.iloc[index]['Description']
                size = description.split()[-1]  # Assumes size is last part of description
                order_key = create_order_key(product_code, size)
                del st.session_state['order'][order_key]

            st.success("Selected items deleted from order.")
            st.session_state['refresh'] = not st.session_state.get('refresh', False)
            st.rerun()
    else:
        st.write("Your order is empty.")

# Search for products by name or code
def search_products(df, search_query):
    if search_query:
        search_terms = search_query.lower().split()
        name_matches = pd.Series(True, index=df.index)
        code_matches = pd.Series(True, index=df.index)

        for term in search_terms:
            name_matches &= df['product name'].str.lower().str.contains(term, na=False)
            code_matches &= df['code'].str.lower().str.contains(term, na=False)

        filtered_df = df[name_matches | code_matches]
        return filtered_df
    return df

# Edit product information, and update database accordingly
def edit_product(model, origin, name, sport):
    material = origin[0].lower()
    category = singular_to_plural.get(origin[1].lower(),origin[1].lower())
    origin_table = f"{category}_{material}"
    if name:
        execute_query(supabase.table(origin_table).update({"name": name}).eq("model", model))
    if sport:
        execute_query(supabase.table(origin_table).update({"sport": sport}).eq("model", model))
    st.cache_data.clear()
    st.rerun()
    load_data(materials_dict)

# Function to sort the DataFrame based on session state
def sort_results(df):
    sort_by = st.session_state.get('sort_by', None)
    sort_order = st.session_state.get('sort_order', 'asc')

    if sort_by:
        if sort_by == 'product_name':
            sort_col = 'product name'
        elif sort_by == 'code':
            sort_col = 'code'
        else:
            sort_col = None

        if sort_col and sort_col in df.columns:
            ascending = True if sort_order == 'asc' else False
            df = df.sort_values(by=sort_col, ascending=ascending)
    
    return df

# Function to display the pagination bar and sorting buttons
def display_pagination(key, total, page_size=25, align='center', jump=True, show_total=True):
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1

    if 'sort_by' not in st.session_state:
        st.session_state['sort_by'] = None
    if 'sort_order' not in st.session_state:
        st.session_state['sort_order'] = 'asc'

    if key=="top":
        col_pagination, col_sorting = st.columns([2, 1.4])

        with col_pagination:
            selected_page = sac.pagination(
                total=total,
                index=st.session_state['current_page'],
                page_size=page_size,
                align=align,
                jump=jump,
                show_total=show_total,
                key=f"pagination_{key}",
                color="green"
            )

            if selected_page != st.session_state['current_page']:
                st.session_state['current_page'] = selected_page
                st.rerun()
        
        with col_sorting:
            title, sort_col1, sort_col2 = st.columns(3, vertical_alignment='center')
            
            with title:
                st.write("**Sort by:**")

            with sort_col1:
                if st.session_state['sort_by'] == 'product_name':
                    arrow = "↑" if st.session_state['sort_order'] == 'asc' else "↓"
                else:
                    arrow = ""
                name_label = f"Name {arrow}"
                
                if st.button(name_label, key=f"sort_name_{key}"):
                    if st.session_state['sort_by'] == 'product_name':
                        st.session_state['sort_order'] = 'desc' if st.session_state['sort_order'] == 'asc' else 'asc'
                    else:
                        st.session_state['sort_by'] = 'product_name'
                        st.session_state['sort_order'] = 'asc'
                    st.session_state['current_page'] = 1
                    st.rerun()

            with sort_col2:
                if st.session_state['sort_by'] == 'code':
                    arrow = "↑" if st.session_state['sort_order'] == 'asc' else "↓"
                else:
                    arrow = ""
                code_label = f"Code {arrow}"
                
                if st.button(code_label, key=f"sort_code_{key}"):
                    if st.session_state['sort_by'] == 'code':
                        st.session_state['sort_order'] = 'desc' if st.session_state['sort_order'] == 'asc' else 'asc'
                    else:
                        st.session_state['sort_by'] = 'code'
                        st.session_state['sort_order'] = 'asc'
                    st.session_state['current_page'] = 1
                    st.rerun()

# Main function to load data and handle search functionality
def main():
    final_df = st.session_state['products']
    display_order_table()
    search_query = st.text_input("Search for a product by name or code:")

    if 'last_search' not in st.session_state:
        st.session_state['last_search'] = ""

    if search_query != st.session_state['last_search']:
        st.session_state['current_page'] = 1
        st.session_state['last_search'] = search_query
    
    if search_query:
        result_df = search_products(final_df, search_query)
        
        if not result_df.empty:
            PAGE_SIZE = 25
            total_results = len(result_df)
            total_pages = math.ceil(total_results / PAGE_SIZE)

            sorted_df = sort_results(result_df)

            if 'current_page' not in st.session_state:
                st.session_state['current_page'] = 1

            if st.session_state['current_page'] > total_pages:
                st.session_state['current_page'] = total_pages
            if st.session_state['current_page'] < 1:
                st.session_state['current_page'] = 1

            start_idx = (st.session_state['current_page'] - 1) * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            current_page_df = sorted_df.iloc[start_idx:end_idx]

            st.markdown("<hr style='margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
            display_pagination(key="top", total=total_results, page_size=PAGE_SIZE, align='left', jump=False, show_total=True)
            st.markdown("<hr style='margin-top: 0px; margin-bottom: 10px;'>", unsafe_allow_html=True)

            for idx, row in current_page_df.iterrows():
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"**Product Name**: {row['product name']}")
                        st.write(f"**Product Code**: {row['code']}") 
                        if row['sizes']:
                            sizes_display = ", ".join([f"{size}mm" for size in row['sizes']])
                            st.write(f"**Available Sizes**: {sizes_display}")
                        else:
                            st.write("No sizes found for this product.")
                    
                    with col2:
                        with st.popover(f"Add to Order"):
                            if row['sizes']:
                                # Using a form to group inputs so that intermediate changes do not trigger re-runs
                                with st.form(key=f"order_form_{row['code']}_{idx}"):
                                    size_selected = st.selectbox(
                                        f"Select Size for {row['product name']}",
                                        options=[f"{size}mm" for size in row['sizes']],
                                        key=f"size_{row['code']}_{idx}"
                                    )

                                    quantity = st.number_input(
                                        f"Quantity for {row['product name']}",
                                        min_value=1,
                                        value=1,
                                        key=f"qty_{row['code']}_{idx}"
                                    )

                                    notes = st.text_input(
                                        f"Notes (e.g. colour) for {row['product name']}",
                                        key=f"notes_{row['code']}_{idx}"
                                    )

                                    submitted = st.form_submit_button("Confirm Add to Order")

                                    if submitted:
                                        # Optionally append sport information based on certain ranges
                                        ranges_to_append_sport = ['ACLA2101', 'MDAB', 'MDAA10']

                                        if row['range'] in ranges_to_append_sport:
                                            if row['sport']:
                                                if notes.strip():
                                                    notes += f", {row['sport']}"
                                                else:
                                                    notes = f"{row['sport']}"

                                        if notes.strip():
                                            notes += f", {size_selected}"
                                        else:
                                            notes = f"{size_selected}"
                                            
                                        add_to_order(row['code'], quantity, notes, size_selected)
                            else:
                                st.write("No sizes available for this product.")

                    with col3:
                        with st.popover(f"Edit"):
                            name = st.text_input("Enter a new model name", key=f"namechange_{row['product name']}_{idx}")
                            sport = st.text_input("Enter a new sport/category", key=f"sportchange_{row['product name']}_{idx}")
                            if st.button("Confirm", key=f"confirmedit_{row['product name']}_{idx}"):
                                origin = row['product name'].split()[-2:] if row['product name'] else []
                                edit_product(row['code'], origin, name, sport)
                    
                    st.image(row['image url'], width=175)
                    st.write('---')

            _, top, _ = st.columns([1.2,1,1])
            with top:
                st.button("⬆️ Back to Top", on_click=trigger_scroll_to_top)
            st.markdown("<hr style='margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)

        else:
            st.write("No products found.")
    else:
        st.write("Please enter a search term.")

if __name__ == "__main__":
    main()