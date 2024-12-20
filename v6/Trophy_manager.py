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
    'trophies': ['acrylic', 'wood', 'glass'],
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

# Function to add items to the order
def add_to_order(product_code, quantity, notes=""):
    if product_code in st.session_state['order']:
        st.session_state['order'][product_code]['quantity'] += quantity
        st.session_state['order'][product_code]['notes'] = notes
    else:
        st.session_state['order'][product_code] = {"quantity": quantity, "notes": notes}
    trigger_scroll_to_top()

# Function to generate the live order table within the placeholder
def display_order_table():
    # Check if the order is not empty
    if st.session_state.get('order', {}):
        # Prepare data for the table
        order_data = {
            "Product": [],
            "Description": [],
            "Quantity": []
        }

        # Populate the table data from the order
        for product_code, details in st.session_state['order'].items():
            order_data["Product"].append(product_code)
            order_data["Description"].append(details.get("notes", ""))
            order_data["Quantity"].append(details.get("quantity", 0))

        # Convert to a DataFrame for displaying
        df = pd.DataFrame(order_data)

        # Display the table with checkbox selection using the event-based API
        event = st.dataframe(
            df,
            key="data",
            on_select="rerun",
            selection_mode=["multi-row"],
            hide_index="true",
            use_container_width=True
        )

        # Create a horizontal layout for buttons
        delete_button_clicked = st.button("Delete selected items", key="delete_button")

        # Handle button actions
        if delete_button_clicked and event and 'rows' in event.selection:
            selected_indices = event.selection['rows']
            for index in selected_indices:
                product_code_to_delete = df.iloc[index]['Product']
                del st.session_state['order'][product_code_to_delete]

            st.success("Selected items deleted from order.")
            st.session_state['refresh'] = not st.session_state.get('refresh', False)
            st.rerun()

    else:
        st.write("Your order is empty.")

# Search for products by name or code.
def search_products(df, search_query):
    if search_query:
        # Convert search query to lowercase and split into terms
        search_terms = search_query.lower().split()

        # Initialize masks for name and code matches
        name_matches = pd.Series(True, index=df.index)
        code_matches = pd.Series(True, index=df.index)

        for term in search_terms:
            # Use pandas string methods which handle NaN values
            name_matches &= df['product name'].str.lower().str.contains(term, na=False)
            code_matches &= df['code'].str.lower().str.contains(term, na=False)

        # Combine the masks
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
        # Determine the column name in the DataFrame
        if sort_by == 'product_name':
            sort_col = 'product name'  # Adjust based on actual column name
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
    # Initialize current_page in session state if not present
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1

    # Initialize sorting preferences if not present
    if 'sort_by' not in st.session_state:
        st.session_state['sort_by'] = None  # Options: 'product_name' or 'code'
    if 'sort_order' not in st.session_state:
        st.session_state['sort_order'] = 'asc'  # Options: 'asc' or 'desc'

    if key=="top":
        # Create columns for pagination and sorting
        col_pagination, col_sorting = st.columns([2, 1.4])

        with col_pagination:
            # Display the Ant Design pagination component
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

            # Update the current_page in session state if changed
            if selected_page != st.session_state['current_page']:
                st.session_state['current_page'] = selected_page
                st.rerun()
        
        with col_sorting:
            # Sorting Buttons
            title, sort_col1, sort_col2 = st.columns(3, vertical_alignment='center')
            
            with title:
                st.write("**Sort by:**")

            with sort_col1:
                # Determine arrow based on current sort order for 'name'
                if st.session_state['sort_by'] == 'product_name':
                    arrow = "↑" if st.session_state['sort_order'] == 'asc' else "↓"
                else:
                    arrow = ""
                
                # Button label with arrow
                name_label = f"Name {arrow}"
                
                if st.button(name_label, key=f"sort_name_{key}"):
                    # Toggle sort order if already sorted by product name
                    if st.session_state['sort_by'] == 'product_name':
                        st.session_state['sort_order'] = 'desc' if st.session_state['sort_order'] == 'asc' else 'asc'
                    else:
                        st.session_state['sort_by'] = 'product_name'
                        st.session_state['sort_order'] = 'asc'
                    st.session_state['current_page'] = 1  # Reset to first page
                    st.rerun()

            with sort_col2:
                # Determine arrow based on current sort order for 'code'
                if st.session_state['sort_by'] == 'code':
                    arrow = "↑" if st.session_state['sort_order'] == 'asc' else "↓"
                else:
                    arrow = ""
                
                # Button label with arrow
                code_label = f"Code {arrow}"
                
                if st.button(code_label, key=f"sort_code_{key}"):
                    # Toggle sort order if already sorted by code
                    if st.session_state['sort_by'] == 'code':
                        st.session_state['sort_order'] = 'desc' if st.session_state['sort_order'] == 'asc' else 'asc'
                    else:
                        st.session_state['sort_by'] = 'code'
                        st.session_state['sort_order'] = 'asc'
                    st.session_state['current_page'] = 1  # Reset to first page
                    st.rerun()

# Main function to load data and handle search functionality.
def main():

    final_df = st.session_state['products']
    display_order_table()
    search_query = st.text_input("Search for a product by name or code:")

    # Reset current page when a new search is performed
    if 'last_search' not in st.session_state:
        st.session_state['last_search'] = ""

    if search_query != st.session_state['last_search']:
        st.session_state['current_page'] = 1
        st.session_state['last_search'] = search_query
    
    if search_query:
        result_df = search_products(final_df, search_query)
        
        if not result_df.empty:
            # Pagination parameters
            PAGE_SIZE = 25
            total_results = len(result_df)
            total_pages = math.ceil(total_results / PAGE_SIZE)

            # Sort the results based on user preference
            sorted_df = sort_results(result_df)

            # Initialize current_page in session state
            if 'current_page' not in st.session_state:
                st.session_state['current_page'] = 1

            # Ensure current_page is within valid range
            if st.session_state['current_page'] > total_pages:
                st.session_state['current_page'] = total_pages
            if st.session_state['current_page'] < 1:
                st.session_state['current_page'] = 1

            # Calculate start and end indices for slicing
            start_idx = (st.session_state['current_page'] - 1) * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            current_page_df = sorted_df.iloc[start_idx:end_idx]

            # Display the sleek pagination bar above the search input
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
                            # Size selection dropdown
                                size_selected = st.selectbox(
                                    f"Select Size for {row['product name']}",
                                    options=[f"{size}mm" for size in row['sizes']], 
                                    key=f"size_{row['product name']}_{idx}"
                                )

                                # Map the selected size back to the corresponding size_code
                                size_index = [f"{size}mm" for size in row['sizes']].index(size_selected)
                                size_code = row['size_codes'][size_index]  # Get the corresponding size_code

                            # Quantity input
                            quantity = st.number_input(f"Quantity for {row['product name']}", min_value=1, value=1, key=f"qty_{row['product name']}_{idx}")
                            
                            # Text input for notes
                            notes = st.text_input(f"Notes (e.g. colour) for {row['product name']}", key=f"notes_{row['product name']}_{idx}")
                            
                            # Confirmation button to add to cart
                            if st.button("Confirm Add to Order", key=f"confirm_{row['product name']}_{idx}"):
                                # Define the ranges that require appending 'sport' to notes
                                ranges_to_append_sport = ['ACLA2101', 'MDAB', 'MDAA10']
                                
                                # Check if the product's range is in the specified list
                                if row['product code'] in ranges_to_append_sport:
                                    # Append 'sport' to the notes
                                    if notes.strip():  # Check if notes are not empty
                                        notes += f", {row['sport']}"
                                    else:
                                        notes = f"{row['sport']}"
                                
                                if notes.strip():  # Check if notes are not empty
                                    notes += f", {size_selected}"
                                else:
                                    notes = f"{size_selected}"


                                # Add the product to the order with the updated notes
                                add_to_order(size_code, quantity, notes)
                                st.rerun()


                    with col3:
                        with st.popover(f"Edit"):
                            name = st.text_input("Enter a new model name", key=f"namechange_{row['product name']}_{idx}")
                            sport = st.text_input("Enter a new sport/category", key=f"sportchange_{row['product name']}_{idx}")
                            if st.button("Confirm", key=f"confirmedit_{row['product name']}_{idx}"):
                                edit_product(row['code'], row['product name'].split()[-2:], name, sport)
                    
                    # Display the image below the text and button
                    st.image(row['image url'], width=175)
                    st.write('---')

            # Modified Back to Top button
            _, top, _ = st.columns([1.2,1,1])
            with top:
                st.button("⬆️ Back to Top", on_click=trigger_scroll_to_top)
            st.markdown("<hr style='margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)

        else:
            st.write("No products found.")
    else:
        st.write("Please enter a search term.")

# Run the main function
if __name__ == "__main__":
    main()