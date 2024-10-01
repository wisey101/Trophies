import streamlit as st
from st_supabase_connection import SupabaseConnection, execute_query
import pandas as pd
import math
import streamlit_antd_components as sac


st.set_page_config(
    page_title="Trophy Manager",
    page_icon="🏆",
)

from utils import load_data

# Initialize connection and grab URL from secrets
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

materials_dict = {
    'trophies': ['acrylic', 'wood'],
    'medals': ['acrylic', 'wood', 'metal']
}

singular_to_plural = {
    'trophy': 'trophies',
    'medal': 'medals'
}

st.title("Trophy Monster Product Manager")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    load_data(materials_dict)

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
    load_data(materials_dict)
    
def display_pagination(key, total, page_size=25, align='center', jump=True, show_total=True):
    # Calculate total pages
    total_pages = math.ceil(total / page_size)

    # Initialize current_page in session state if not present
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1

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

# Main function to load data and handle search functionality.
def main():

    # Load data if not already loaded
    if 'products' not in st.session_state or st.session_state['products'].empty:
        load_data(materials_dict)

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
            current_page_df = result_df.iloc[start_idx:end_idx]

            # Display the sleek pagination bar above the search input
            st.markdown("<hr style='margin-top: 20px; margin-bottom: 10px;'>", unsafe_allow_html=True)
            display_pagination(key="top", total=total_results, page_size=PAGE_SIZE, align='center', jump=False, show_total=True)

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

            display_pagination(key="bottom", total=total_results, page_size=PAGE_SIZE, align='center', jump=False, show_total=True)
            st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px;'>", unsafe_allow_html=True)

        else:
            st.write("No products found.")
    else:
        st.write("Please enter a search term.")

# Run the main function
if __name__ == "__main__":
    main()